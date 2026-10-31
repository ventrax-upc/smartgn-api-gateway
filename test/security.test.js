import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import jwt from 'jsonwebtoken';
import { createApp } from '../src/app.js';
import { loadConfig } from '../src/config/env.js';
import { CONTRACTS } from '../src/routes/contracts.js';
import { ROUTE_TABLE, matchesPrefix } from '../src/routes/route-table.js';

const secret = 'gateway-test-only-0123456789-0123456789-0123456789';
const account = '11111111-1111-4111-8111-111111111111';
const token = (claims = {}, options = {}) => jwt.sign({
  sub: account, accountId: account, sessionVersion: 0, role: 'SUPERADMIN', ...claims,
}, secret, { issuer: 'smartgn-iam-service', audience: 'smartgn-api', expiresIn: '2m', ...options });

async function setup(t, environment = {}) {
  const seen = [];
  const backend = http.createServer((req, res) => {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      seen.push({ url: req.url, method: req.method, body: Buffer.concat(chunks), headers: req.headers });
      if (req.url === '/actuator/health') {
        res.writeHead(200, { 'content-type': 'application/json' });
        return res.end('{"status":"UP"}');
      }
      res.writeHead(201, { 'content-type': 'application/octet-stream', 'x-total-count': '7', 'content-disposition': 'attachment; filename="test.bin"' });
      res.end(Buffer.concat(chunks));
    });
  });
  await new Promise((resolve) => backend.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${backend.address().port}`;
  const config = loadConfig({ JWT_SECRET: secret, RATE_LIMIT_MAX: '1000',
    IAM_URL: url, INSTALLATION_URL: url, SUPPORT_URL: url, BILLING_URL: url,
    CORS_ORIGINS: 'http://localhost:4200', ...environment });
  const gateway = http.createServer(createApp(config));
  await new Promise((resolve) => gateway.listen(0, '127.0.0.1', resolve));
  t.after(() => { for (const server of [backend, gateway]) { server.closeAllConnections(); server.close(); } });
  return { url: `http://127.0.0.1:${gateway.address().port}`, seen };
}

test('every public service operation has an exact route and reaches the owning proxy', async (t) => {
  const { url, seen } = await setup(t);
  assert.equal(CONTRACTS.length, 90);
  for (const contract of CONTRACTS) {
    assert.ok(matchesPrefix(contract.path, ROUTE_TABLE[contract.service]), contract.path);
    const path = contract.path.replace(/\{[^}]+\}/g, account);
    const response = await fetch(url + path, { method: contract.method,
      headers: contract.public ? {} : { authorization: `Bearer ${token()}` } });
    await response.arrayBuffer();
    assert.equal(response.status, 201, `${contract.method} ${path}`);
    assert.equal(seen.at(-1).url, path);
    assert.equal(seen.at(-1).method, contract.method);
  }
});

test('rejects missing IAM identity, expiry, issued-at, future issued-at and unsupported roles', async (t) => {
  const { url, seen } = await setup(t);
  for (const bad of [
    token({ accountId: 'another' }), token({ role: 'TECHNICIAN' }),
    token({ sessionVersion: -1 }), token({ sub: 'not-a-uuid', accountId: 'not-a-uuid' }),
    token({}, { noTimestamp: true }), token({ iat: Math.floor(Date.now() / 1000) + 120 }),
    jwt.sign({ sub: account, accountId: account, sessionVersion: 0, role: 'USER' }, secret,
      { issuer: 'smartgn-iam-service', audience: 'smartgn-api' }),
  ]) {
    const response = await fetch(url + '/api/v1/profiles/me', { headers: { authorization: `Bearer ${bad}` } });
    assert.equal(response.status, 401);
    assert.match(response.headers.get('content-type'), /application\/problem\+json/);
  }
  assert.equal(seen.length, 0);
});

test('accepts IAM HMAC algorithms HS256, HS384 and HS512', async (t) => {
  const { url } = await setup(t);
  for (const algorithm of ['HS256', 'HS384', 'HS512']) {
    const response = await fetch(url + '/api/v1/profiles/me', { headers: { authorization: `Bearer ${token({}, { algorithm })}` } });
    assert.equal(response.status, 201);
    await response.arrayBuffer();
  }
});

test('unknown methods, invented aliases and internal routes never reach a backend', async (t) => {
  const { url, seen } = await setup(t);
  for (const [method, path] of [
    ['GET', '/internal/v1/accounts'], ['POST', '/api/v1/checkout/anything'],
    ['DELETE', '/api/v1/checkout/orders'], ['GET', '/api/v1/supplypoints'],
    ['GET', '/api/v1/billingdocuments'], ['GET', '/api/v1/support/internal/v1/events'],
  ]) {
    assert.equal((await fetch(url + path, { method })).status, 404, path);
  }
  assert.equal(seen.length, 0);
});

test('checkout preflight allows required headers and pagination/download headers are exposed', async (t) => {
  const { url } = await setup(t);
  const response = await fetch(url + '/api/v1/checkout/orders', { method: 'OPTIONS', headers: {
    origin: 'http://localhost:4200', 'access-control-request-method': 'POST',
    'access-control-request-headers': 'idempotency-key,x-checkout-secret,content-type',
  } });
  assert.equal(response.status, 204);
  assert.match(response.headers.get('access-control-allow-headers'), /Idempotency-Key/);
  assert.match(response.headers.get('access-control-allow-headers'), /X-Checkout-Secret/);
  const denied = await fetch(url + '/health', { headers: { origin: 'https://untrusted.example' } });
  assert.equal(denied.status, 403);
  const allowed = await fetch(url + '/api/v1/properties', { headers: { origin: 'http://localhost:4200', authorization: `Bearer ${token()}` } });
  assert.match(allowed.headers.get('access-control-expose-headers'), /X-Total-Count/);
  assert.match(allowed.headers.get('access-control-expose-headers'), /Content-Disposition/);
  await allowed.arrayBuffer();
});

test('multipart/binary bodies and private checkout headers are preserved; asserted identities are removed', async (t) => {
  const { url, seen } = await setup(t);
  const bytes = Buffer.from([0, 255, 1, 2, 13, 10]);
  const response = await fetch(url + '/api/v1/support/tickets/' + account + '/photos', {
    method: 'POST', body: bytes, headers: { authorization: `Bearer ${token()}`,
      'content-type': 'multipart/form-data; boundary=test', 'origin': 'http://localhost:4200', 'idempotency-key': 'stable-test',
      'x-checkout-secret': 'private-test', 'x-account-id': account },
  });
  assert.deepEqual(Buffer.from(await response.arrayBuffer()), bytes);
  assert.deepEqual(seen[0].body, bytes);
  assert.equal(seen[0].headers['idempotency-key'], 'stable-test');
  assert.equal(seen[0].headers['x-checkout-secret'], 'private-test');
  assert.equal(seen[0].headers['x-account-id'], undefined);
  assert.equal(seen[0].headers.origin, undefined);
});

test('OpenAPI exposes only public contracts and reports readiness separately from liveness', async (t) => {
  const { url } = await setup(t);
  const api = await (await fetch(url + '/v3/api-docs')).json();
  assert.equal(api.info.title, 'SmartGN - API Gateway');
  assert.equal(api.info.version, 'v1');
  assert.ok(!Object.keys(api.paths).some((path) => path.startsWith('/internal')));
  assert.equal(Object.values(api.paths).reduce((n, item) => n + Object.keys(item).length, 0), 92);
  assert.equal((await fetch(url + '/ready')).status, 200);
  assert.equal((await fetch(url + '/swagger-ui/index.html')).status, 200);
  assert.match(await (await fetch(url + '/swagger-ui/swagger-initializer.js')).text(), /persistAuthorization:false/);
});

test('readiness fails closed when a dependency is unavailable while liveness remains UP', async (t) => {
  const { url } = await setup(t, { BILLING_URL: 'http://127.0.0.1:1' });
  assert.equal((await fetch(url + '/health')).status, 200);
  const response = await fetch(url + '/ready');
  assert.equal(response.status, 503);
  assert.equal((await response.json()).dependencies.billing, 'DOWN');
});

test('configuration rejects malformed ports, weak secrets and credential-bearing service URLs', () => {
  for (const environment of [ { API_PORT: '8000garbage' }, { API_PORT: '65536' },
    { RATE_LIMIT_MAX: '0' }, { JWT_SECRET: 'short' }, { IAM_URL: 'http://user:secret@localhost' },
    { SUPPORT_URL: 'file:///tmp/private' },
  ]) assert.throws(() => loadConfig({ JWT_SECRET: secret, ...environment }));
});

test('ambiguous encoded paths are rejected without forwarding to a service', async (t) => {
  const { url, seen } = await setup(t);
  for (const path of ['/api/v1/support/../internal/v1/events',
    '/api/v1/support/%2f..%2finternal', '/api/v1/support/%252e%252e/internal',
    '/api/v1/support/%zz', '/api/v1/support//tickets']) {
    const status = await new Promise((resolve, reject) => {
      const parsed = new URL(url);
      const request = http.request({ hostname: parsed.hostname, port: parsed.port, path,
        headers: { authorization: `Bearer ${token()}` } }, (response) => {
        response.resume(); response.on('end', () => resolve(response.statusCode));
      });
      request.on('error', reject); request.end();
    });
    assert.equal(status, 400, path);
  }
  assert.equal(seen.length, 0);
});
