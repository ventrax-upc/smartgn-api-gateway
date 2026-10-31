import rateLimit from 'express-rate-limit';
import { sendError } from './http-errors.js';

const handler = (req, res) => sendError(req, res, 429, 'Too many requests, try again later');

export function createRateLimiters({ rateLimit: cfg }) {
  const common = {
    windowMs: cfg.windowMs,
    standardHeaders: true,
    legacyHeaders: false,
    handler,
  };

  const general = rateLimit({
    ...common,
    limit: cfg.max,
    skip: (req) => req.method === 'OPTIONS' || ['/health', '/ready'].includes(req.path),
  });

  // Stricter limit against credential stuffing / brute force.
  const signIn = rateLimit({ ...common, limit: cfg.signInMax });

  return { general, signIn };
}
