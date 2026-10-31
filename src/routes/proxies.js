import { createProxyMiddleware } from 'http-proxy-middleware';
import { ROUTE_TABLE, matchesPrefix } from './route-table.js';
import { sendError } from '../middlewares/http-errors.js';

function buildProxy(name, target, prefixes, timeoutMs) {
  return createProxyMiddleware({
    target,
    changeOrigin: true,
    proxyTimeout: timeoutMs,
    xfwd: true,
    pathFilter: (pathname) => matchesPrefix(pathname, prefixes),
    on: {
      proxyReq: (proxyReq, req) => {
        req._proxyStartedAt = Date.now();
        if (req.id) proxyReq.setHeader('x-correlation-id', req.id);
      },
      error: (err, req, res) => {
        // Log without secrets; the client gets a generic controlled error.
        console.error(`[${req.id}] upstream "${name}" error: ${err.code ?? err.message}`);
        if (typeof res.status !== 'function') {
          res.destroy?.();
          return;
        }
        const elapsed = Date.now() - (req._proxyStartedAt ?? Date.now());
        if (err.code === 'ECONNREFUSED' || err.code === 'ENOTFOUND' || err.code === 'EAI_AGAIN') {
          return sendError(req, res, 503, 'Service temporarily unavailable');
        }
        if (err.code === 'ETIMEDOUT' || err.code === 'ESOCKETTIMEDOUT' || elapsed >= timeoutMs) {
          return sendError(req, res, 504, 'Upstream service timed out');
        }
        return sendError(req, res, 502, 'Bad gateway');
      },
    },
  });
}

export function createProxies(config) {
  return Object.entries(ROUTE_TABLE).map(([name, prefixes]) =>
    buildProxy(name, config.services[name], prefixes, config.proxyTimeoutMs),
  );
}
