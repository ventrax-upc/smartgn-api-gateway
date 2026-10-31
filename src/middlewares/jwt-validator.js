import jwt from 'jsonwebtoken';
import { sendError } from './http-errors.js';
import { findContract } from '../routes/contracts.js';

export const isPublic = (method, path) => findContract(method, path)?.public === true;
export function extractRoles(payload) {
  return ['USER', 'SUPERADMIN'].includes(payload.role) ? [payload.role] : [];
}

export function createJwtValidator({ jwt: jwtConfig }) {
  return (req, res, next) => {
    if (isPublic(req.method, req.path)) return next();
    const match = /^Bearer ([^\s]+)$/i.exec(req.headers.authorization ?? '');
    if (!match) return sendError(req, res, 401, 'Missing or malformed Authorization header');
    let payload;
    try {
      payload = jwt.verify(match[1], jwtConfig.secret, {
        algorithms: ['HS256', 'HS384', 'HS512'],
        issuer: jwtConfig.issuer, audience: jwtConfig.audience,
      });
      if (typeof payload !== 'object' || !Number.isFinite(payload.exp) ||
          !Number.isFinite(payload.iat) || payload.iat > Date.now() / 1000 + 60 ||
          !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(payload.sub ?? '') ||
          payload.accountId !== payload.sub || !Number.isInteger(payload.sessionVersion) ||
          payload.sessionVersion < 0 || !extractRoles(payload).length) {
        return sendError(req, res, 401, 'Invalid IAM identity claims');
      }
    } catch {
      return sendError(req, res, 401, 'Invalid or expired token');
    }
    if ((req.path === '/api/v1/installers' || req.path.startsWith('/api/v1/installers/')) &&
        payload.role !== 'SUPERADMIN') return sendError(req, res, 403, 'Insufficient permissions');
    req.auth = { sub: payload.sub, roles: extractRoles(payload) };
    next();
  };
}
