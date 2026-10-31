import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import jwt from 'jsonwebtoken';
import { createApp } from '../src/app.js';
import { loadConfig } from '../src/config/env.js';

const SECRET = 'test-secret-that-is-long-enough-for-hs256-1234567890';
const ISSUER = 'smartgn-iam-service';
const AUDIENCE = 'smartgn-api';

const listen = (server) =>
  new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server.address().port)));

const sign = (claims = {}, opts = {}) =>
  jwt.sign({ role: 'USER', ...claims }, SECRET, {
    algorithm: 'HS256',
    subject: 'user-1',
    issuer: ISSUER,
    audience: [AUDIENCE],
    expiresIn: '5m',
    ...opts,
  });

let backend, gateway, slow, gw, rateGw, closeList;
const seen = [];

before(async () => {
  backend = http.createServer((req, res) => {
    let body = '';
    req.on('data', (c) => (body += c));
    req.on('end', () => {
      seen.push({ method: req.method, url: req.url, body, headers: req.headers });
      if (req.url.startsWith('/api/v1/properties/403')) {
        res.writeHead(403, { 'content-type': 'application/json' });
        return res.end('{"detail":"not your property"}');
      }
      res.writeHead(201, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ echo: body, url: req.url }));
    });
  });
  slow = http.createServer(() => {
    /* never answers */
  });
  const backendPort = await listen(backend);
  const slowPort = await listen(slow);

  const base = loadConfig({
    JWT_SECRET: SECRET,
    CORS_ORIGINS: 'http://localhost:4200',
    IAM_URL: `http://127.0.0.1:${backendPort}`,
    INSTALLATION_URL: `http://127.0.0.1:${backendPort}`,
    SUPPORT_URL: `http://127.0.0.1:${slowPort}`,
    BILLING_URL: 'http://127.0.0.1:1', // nothing listening
    PROXY_TIMEOUT_MS: '400',
    RATE_LIMIT_MAX: '1000',
  });

  gateway = http.createServer(createApp(base));
  gw = `http://127.0.0.1:${await listen(gateway)}`;

  const limited = loadConfig({
    JWT_SECRET: SECRET,
    IAM_URL: `http://127.0.0.1:${backendPort}`,
    RATE_LIMIT_MAX: '1000',
    RATE_LIMIT_SIGN_IN_MAX: '2',
  });
  const limitedServer = http.createServer(createApp(limited));
  rateGw = `http://127.0.0.1:${await listen(limitedServer)}`;
  closeList = [backend, slow, gateway, limitedServer];
});

after(() => {
  for (const s of closeList) {
    s.closeAllConnections?.();
    s.close();
  }
});

test('config: requires JWT_SECRET', () => {
  assert.throws(() => loadConfig({}), /JWT_SECRET/);
});

test('valid JWT is routed unchanged (path, method, body, status)', async () => {
  seen.length = 0;
  const res = await fetch(`${gw}/api/v1/properties?x=1`, {
    method: 'POST',
    headers: { authorization: `Bearer ${sign()}`, 'content-type': 'application/json' },
    body: '{"name":"Casa"}',
  });
  assert.equal(res.status, 201);
  assert.equal(seen.length, 1);
  assert.equal(seen[0].method, 'POST');
  assert.equal(seen[0].url, '/api/v1/properties?x=1');
  assert.equal(seen[0].body, '{"name":"Casa"}');
  assert.ok(seen[0].headers['x-correlation-id']);
});

test('missing token -> 401, backend not reached', async () => {
  seen.length = 0;
  const res = await fetch(`${gw}/api/v1/properties`);
  assert.equal(res.status, 401);
  assert.equal(seen.length, 0);
  const body = await res.json();
  assert.ok(body.correlationId);
});

test('expired, wrong secret, wrong issuer, wrong audience, alg none -> 401', async () => {
  const bad = [
    sign({}, { expiresIn: -10 }),
    jwt.sign({ role: 'USER' }, 'other-secret-other-secret-other-secret', {
      issuer: ISSUER,
      audience: AUDIENCE,
    }),
    sign({}, { issuer: 'evil' }),
    sign({}, { audience: 'other-api' }),
    jwt.sign({ role: 'USER' }, '', { algorithm: 'none', issuer: ISSUER, audience: AUDIENCE }),
    'garbage.token.value',
  ];
  for (const token of bad) {
    const res = await fetch(`${gw}/api/v1/profiles/me`, {
      headers: { authorization: `Bearer ${token}` },
    });
    assert.equal(res.status, 401);
  }
});

test('resource-level authorization stays in the backend (403 passes through)', async () => {
  const res = await fetch(`${gw}/api/v1/properties/403`, {
    headers: { authorization: `Bearer ${sign()}` },
  });
  assert.equal(res.status, 403);
  assert.deepEqual(await res.json(), { detail: 'not your property' });
});

test('/installers is SUPERADMIN only', async () => {
  const user = await fetch(`${gw}/api/v1/installers`, {
    headers: { authorization: `Bearer ${sign({ role: 'USER' })}` },
  });
  assert.equal(user.status, 403);
  const admin = await fetch(`${gw}/api/v1/installers`, {
    headers: { authorization: `Bearer ${sign({ role: 'SUPERADMIN' })}` },
  });
  assert.equal(admin.status, 201);
  const prefixed = await fetch(`${gw}/api/v1/installers`, {
    headers: { authorization: `Bearer ${sign({ role: 'ROLE_SUPERADMIN' })}` },
  });
  assert.equal(prefixed.status, 201);
});

test('public routes need no token', async () => {
  for (const [method, path] of [
    ['POST', '/api/v1/auth/sign-in'],
    ['POST', '/api/v1/auth/forgot-password'],
    ['POST', '/api/v1/installations'],
  ]) {
    const res = await fetch(`${gw}${path}`, { method, body: '{}' });
    assert.equal(res.status, 201, `${method} ${path}`);
  }
  // Same path, other method is protected.
  const res = await fetch(`${gw}/api/v1/installations`);
  assert.equal(res.status, 401);
});

test('unavailable backend -> controlled 503 without internals', async () => {
  const res = await fetch(`${gw}/api/v1/checkout/session`, { method: 'POST', body: '{}' });
  assert.equal(res.status, 503);
  const text = await res.text();
  assert.ok(!/ECONNREFUSED|127\.0\.0\.1|stack/i.test(text));
});

test('slow backend -> 504', async () => {
  const res = await fetch(`${gw}/api/v1/support/tickets`, {
    headers: { authorization: `Bearer ${sign()}` },
  });
  assert.equal(res.status, 504);
});

test('/internal/** is never exposed; unknown route is 404', async () => {
  const a = await fetch(`${gw}/internal/v1/anything`, {
    headers: { authorization: `Bearer ${sign()}` },
  });
  assert.equal(a.status, 404);
  const b = await fetch(`${gw}/api/v1/unknown`, { headers: { authorization: `Bearer ${sign()}` } });
  assert.equal(b.status, 404);
});

test('health endpoint', async () => {
  const res = await fetch(`${gw}/health`);
  assert.equal(res.status, 200);
  assert.equal((await res.json()).status, 'UP');
});

test('CORS: allowed origin and preflight', async () => {
  const pre = await fetch(`${gw}/api/v1/properties`, {
    method: 'OPTIONS',
    headers: {
      origin: 'http://localhost:4200',
      'access-control-request-method': 'GET',
      'access-control-request-headers': 'authorization',
    },
  });
  assert.equal(pre.status, 204);
  assert.equal(pre.headers.get('access-control-allow-origin'), 'http://localhost:4200');

  const evil = await fetch(`${gw}/health`, { headers: { origin: 'http://evil.com' } });
  assert.equal(evil.headers.get('access-control-allow-origin'), null);
});

test('rate limit: sign-in is stricter -> 429', async () => {
  const codes = [];
  for (let i = 0; i < 4; i++) {
    const res = await fetch(`${rateGw}/api/v1/auth/sign-in`, { method: 'POST', body: '{}' });
    codes.push(res.status);
  }
  assert.deepEqual(codes, [201, 201, 429, 429]);
});
