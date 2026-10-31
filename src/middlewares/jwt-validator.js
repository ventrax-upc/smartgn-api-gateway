import jwt from 'jsonwebtoken';
import { sendError } from './http-errors.js';

const API = '/api/v1';

// Public routes (no JWT). Everything else requires a valid token.
const PUBLIC_RULES = [
  { method: 'POST', path: `${API}/auth/sign-in` },
  { method: 'POST', path: `${API}/auth/activate-password` },
  { method: 'POST', path: `${API}/auth/forgot-password` },
  { method: 'POST', path: `${API}/auth/reset-password` },
  { method: 'POST', path: `${API}/installations` },
  { prefix: `${API}/checkout` },
];

// Role restrictions enforced at the perimeter. Resource-level authorization
// (ownership, subuser grants) stays in each microservice (AD-12).
const ROLE_RULES = [{ prefix: `${API}/installers`, roles: ['SUPERADMIN'] }];

const stripTrailingSlash = (p) => (p.length > 1 && p.endsWith('/') ? p.slice(0, -1) : p);
const hasPrefix = (path, prefix) => path === prefix || path.startsWith(`${prefix}/`);

export function isPublic(method, rawPath) {
  const path = stripTrailingSlash(rawPath);
  return PUBLIC_RULES.some((rule) =>
    rule.prefix ? hasPrefix(path, rule.prefix) : rule.method === method && rule.path === path,
  );
}

export function extractRoles(payload) {
  const raw = payload.role ?? payload.roles ?? payload.authorities ?? [];
  const list = Array.isArray(raw) ? raw : [raw];
  return list
    .map((r) => (typeof r === 'string' ? r : (r?.authority ?? r?.name ?? '')))
    .map((r) => r.replace(/^ROLE_/i, '').toUpperCase())
    .filter(Boolean);
}

export function createJwtValidator({ jwt: jwtConfig }) {
  return (req, res, next) => {
    if (req.method === 'OPTIONS') return next();

    const path = req.path;
    if (isPublic(req.method, path)) return next();

    const header = req.headers.authorization ?? '';
    const [scheme, token] = header.split(' ');
    if (scheme?.toLowerCase() !== 'bearer' || !token) {
      return sendError(req, res, 401, 'Missing or malformed Authorization header');
    }

    let payload;
    try {
      payload = jwt.verify(token, jwtConfig.secret, {
        algorithms: ['HS256', 'HS384', 'HS512'],
        issuer: jwtConfig.issuer,
        audience: jwtConfig.audience,
      });
    } catch {
      return sendError(req, res, 401, 'Invalid or expired token');
    }

    const rule = ROLE_RULES.find((r) => hasPrefix(stripTrailingSlash(path), r.prefix));
    if (rule) {
      const roles = extractRoles(payload);
      if (!rule.roles.some((role) => roles.includes(role))) {
        return sendError(req, res, 403, 'Insufficient permissions');
      }
    }

    req.auth = { sub: payload.sub, roles: extractRoles(payload) };
    next();
  };
}
