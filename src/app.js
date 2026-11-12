import express from 'express';
import cors from 'cors';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import swaggerUi from 'swagger-ui-dist';
import { correlationId } from './middlewares/correlation-id.js';
import { createRateLimiters } from './middlewares/rate-limiter.js';
import { createJwtValidator } from './middlewares/jwt-validator.js';
import { sendError, notFoundHandler, errorHandler } from './middlewares/http-errors.js';
import { createProxies } from './routes/proxies.js';
import { findContract } from './routes/contracts.js';
import { readiness } from './routes/readiness.js';

export function createApp(config) {
  const app = express();
  app.disable('x-powered-by');
  app.use(correlationId);
  app.use((req, res, next) => {
    // Reject ambiguous encoded paths before routing. Never normalize them into another service.
    try {
      const decoded = decodeURIComponent(req.path);
      if (decoded.includes('\\') || decoded.includes('%') || decoded.includes('//') ||
          decoded.split('/').some((p) => p === '.' || p === '..') ||
          /%2f|%5c/i.test(req.path)) return sendError(req, res, 400, 'Ambiguous request path');
    } catch { return sendError(req, res, 400, 'Malformed request path'); }
    next();
  });
  app.use((req, res, next) => {
    if (req.headers.origin && !config.corsOrigins.includes(req.headers.origin)) {
      return sendError(req, res, 403, 'Origin is not allowed');
    }
    next();
  });
  app.use(cors({
    origin: (origin, cb) => cb(null, !origin || config.corsOrigins.includes(origin)),
    methods: ['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Authorization', 'Content-Type', 'X-Correlation-Id', 'Idempotency-Key', 'X-Checkout-Secret'],
    exposedHeaders: ['X-Correlation-Id', 'X-Total-Count', 'Content-Disposition', 'Location', 'Retry-After'],
    maxAge: 600,
  }));
  const { general, signIn } = createRateLimiters(config);
  app.use(general);
  app.get('/health', (_req, res) => res.json({ status: 'UP', service: 'api-gateway' }));
  app.get('/ready', (req, res) => readiness(config, req, res));
  const api = JSON.parse(readFileSync(new URL('../docs/openapi.json', import.meta.url)));
  app.get('/v3/api-docs', (_req, res) => res.json(api));
  app.get('/swagger-ui.html', (_req, res) => res.redirect('/swagger-ui/index.html'));
  app.use('/swagger-ui', express.static(fileURLToPath(new URL('./swagger/', import.meta.url))));
  app.use('/swagger-ui', express.static(swaggerUi.getAbsoluteFSPath()));
  app.use((req, res, next) => {
    if (!findContract(req.method, req.path)) return notFoundHandler(req, res);
    next();
  });
  // Resource ownership and current session/grant checks remain in the owning service.
  app.post('/api/v1/auth/sign-in', signIn);
  app.use(createJwtValidator(config));
  app.use(async (req, res, next) => {
    if (!findContract(req.method, req.path) || findContract(req.method, req.path).service !== 'alerting') return next();
    if (!config.jwt.internalServiceToken) return sendError(req, res, 503, 'Session verification unavailable');
    try {
      const response = await fetch(`${config.services.iam}/internal/v1/sessions/introspect`, {
        method: 'POST',
        headers: {
          authorization: `Bearer ${config.jwt.internalServiceToken}`,
          'content-type': 'application/json',
        },
        body: JSON.stringify({ token: req.headers.authorization.slice(7) }),
        signal: AbortSignal.timeout(Math.min(config.proxyTimeoutMs, 2000)),
      });
      if (response.status === 401 || response.status === 403) return sendError(req, res, 401, 'Invalid or revoked session');
      if (!response.ok) return sendError(req, res, 503, 'Session verification unavailable');
      const actor = await response.json();
      if (actor.status !== 'ACTIVE' || actor.accountId !== req.auth.sub || !['USER', 'SUPERADMIN'].includes(actor.role)) {
        return sendError(req, res, 401, 'Invalid or revoked session');
      }
      req.auth.roles = [actor.role];
      next();
    } catch {
      return sendError(req, res, 503, 'Session verification unavailable');
    }
  });
  // No body parser: JSON, multipart and binary payloads stream unchanged.
  for (const proxy of createProxies(config)) app.use(proxy);
  app.use(notFoundHandler);
  app.use(errorHandler);
  return app;
}
