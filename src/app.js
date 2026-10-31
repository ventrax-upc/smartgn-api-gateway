import express from 'express';
import cors from 'cors';
import { correlationId } from './middlewares/correlation-id.js';
import { createRateLimiters } from './middlewares/rate-limiter.js';
import { createJwtValidator } from './middlewares/jwt-validator.js';
import { notFoundHandler, errorHandler } from './middlewares/http-errors.js';
import { createProxies } from './routes/proxies.js';

export function createApp(config) {
  const app = express();
  app.disable('x-powered-by');

  app.use(correlationId);

  app.use(
    cors({
      origin: (origin, cb) => cb(null, !origin || config.corsOrigins.includes(origin)),
      methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
      allowedHeaders: ['Authorization', 'Content-Type', 'X-Correlation-Id'],
      exposedHeaders: ['X-Correlation-Id'],
      maxAge: 600,
    }),
  );

  const { general, signIn } = createRateLimiters(config);
  app.use(general);

  app.get('/health', (_req, res) => res.json({ status: 'UP', service: 'api-gateway' }));

  // Internal endpoints are never published through the Gateway.
  app.use('/internal', notFoundHandler);

  app.post('/api/v1/auth/sign-in', signIn);

  app.use(createJwtValidator(config));

  // No body parsers before the proxies: bodies must reach services untouched.
  for (const proxy of createProxies(config)) app.use(proxy);

  app.use(notFoundHandler);
  app.use(errorHandler);
  return app;
}
