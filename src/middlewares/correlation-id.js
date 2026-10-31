import { randomUUID } from 'node:crypto';

const HEADER = 'x-correlation-id';

export function correlationId(req, res, next) {
  const incoming = req.headers[HEADER];
  const valid = typeof incoming === 'string' && /^[\w-]{8,64}$/.test(incoming);
  req.id = valid ? incoming : randomUUID();
  req.headers[HEADER] = req.id;
  res.setHeader('X-Correlation-Id', req.id);
  next();
}
