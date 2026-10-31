import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const owners = {
  iam: ['smartgn-iam', 'IAM'],
  installation: ['smartgn-installation-device-management', 'Installation & Device Management'],
  support: ['smartgn-support-maintenance', 'Support & Maintenance'],
  billing: ['smartgn-payments-billing', 'Payments & Billing'],
};
const api = {
  openapi: '3.1.0',
  info: {
    title: 'SmartGN - API Gateway', version: 'v1', license: { name: 'MIT' },
    description: 'Public HTTP entry point for IAM, Installation & Device Management, Support & Maintenance and Payments & Billing. Validates IAM JWTs, applies CORS and request limits, and forwards service contracts without changing their paths. Each owning service verifies current sessions, ownership and delegated functions. Internal routes are excluded. Local HTTP execution does not establish a production TLS or AWS deployment.',
  },
  servers: [{ url: '/', description: 'Current Gateway origin' }],
  tags: [{ name: 'Gateway health', description: 'Process liveness and dependency readiness.' }],
  paths: {},
  components: { securitySchemes: { bearerAuth: { type: 'http', scheme: 'bearer', bearerFormat: 'JWT', description: 'Current IAM JWT. Roles USER and SUPERADMIN; resource authorization stays in the owning service.' } }, schemas: {
    GatewayProblem: { type: 'object', properties: { type: { type: 'string' }, title: { type: 'string' }, status: { type: 'integer' }, detail: { type: 'string' }, instance: { type: 'string' }, correlationId: { type: 'string' } } },
  } },
};
const contracts = [];
const refs = (value, prefix) => {
  if (Array.isArray(value)) return value.map((v) => refs(v, prefix));
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(Object.entries(value).map(([key, child]) => [key,
    key === '$ref' && typeof child === 'string' && child.startsWith('#/components/')
      ? child.replace(/(#\/components\/[^/]+\/)(.+)/, `$1${prefix}_$2`) : refs(child, prefix)]));
};
for (const [owner, [repo, name]] of Object.entries(owners)) {
  const source = JSON.parse(readFileSync(path.join(root, '..', repo, 'docs/openapi.json')));
  for (const tag of source.tags ?? []) api.tags.push({ ...tag, name: `${name} / ${tag.name}` });
  for (const [section, values] of Object.entries(source.components ?? {})) {
    if (section === 'securitySchemes') continue;
    api.components[section] ??= {};
    for (const [key, value] of Object.entries(values)) api.components[section][`${owner}_${key}`] = refs(value, owner);
  }
  for (const [route, item] of Object.entries(source.paths)) {
    if (!route.startsWith('/api/v1/')) continue;
    api.paths[route] ??= {};
    for (const [method, original] of Object.entries(item)) {
      if (!['get', 'post', 'put', 'patch', 'delete', 'head'].includes(method)) continue;
      if (api.paths[route][method]) throw new Error(`Duplicate route ${method} ${route}`);
      const operation = refs(original, owner);
      const publicRoute = (original.security ?? source.security ?? []).length === 0;
      contracts.push({ method: method.toUpperCase(), path: route, service: owner, public: publicRoute });
      operation.operationId = `${owner}_${original.operationId}`;
      operation.tags = (original.tags ?? []).map((tag) => `${name} / ${tag}`);
      operation.security = publicRoute ? [] : [{ bearerAuth: [] }];
      operation['x-upstream-service'] = owner;
      for (const code of ['429', '502', '503', '504']) {
        operation.responses[code] ??= {
          description: { 429: 'Gateway request limit exceeded.', 502: 'Upstream connection failed.', 503: 'Upstream unavailable.', 504: 'Upstream deadline exceeded.' }[code],
          content: { 'application/problem+json': { schema: { $ref: '#/components/schemas/GatewayProblem' } } },
        };
      }
      api.paths[route][method] = operation;
    }
  }
}
for (const [route, summary, description, responses] of [
  ['/health', 'Get Gateway liveness', 'Returns UP while the Gateway process is responding. Does not imply that dependencies are ready.', { 200: { description: 'Gateway process is up.' } }],
  ['/ready', 'Get Gateway dependency readiness', 'Checks the four owning services with bounded health requests. Returns 503 if a dependency is unavailable.', { 200: { description: 'All dependencies are healthy.' }, 503: { description: 'A dependency is unavailable.' } }],
]) api.paths[route] = { get: { operationId: route.slice(1), tags: ['Gateway health'], summary, description, security: [], responses } };
// Keep only component definitions reachable from public operations.
const used = new Set();
const visit = (value) => {
  if (!value || typeof value !== 'object') return;
  if (value.$ref?.startsWith('#/components/')) {
    const [, , section, key] = value.$ref.split('/');
    const id = `${section}/${key}`;
    if (!used.has(id)) { used.add(id); visit(api.components[section]?.[key]); }
  }
  for (const child of Object.values(value)) visit(child);
};
visit(api.paths);
for (const [section, values] of Object.entries(api.components)) {
  if (section === 'securitySchemes') continue;
  for (const key of Object.keys(values)) if (!used.has(`${section}/${key}`)) delete values[key];
}
const assignedTags = new Set(Object.values(api.paths).flatMap((item) => Object.values(item).flatMap((op) => op.tags ?? [])));
api.tags = api.tags.filter((tag) => assignedTags.has(tag.name));
for (const [name, value] of [['docs/openapi.json', api], ['src/config/contracts.json', contracts]]) {
  const content = JSON.stringify(value, null, 2) + '\n';
  const file = path.join(root, name);
  if (process.argv.includes('--check')) {
    if (readFileSync(file, 'utf8').replace(/\r\n/g, '\n') !== content) throw new Error(`${name} is stale; run npm run generate:openapi`);
  } else writeFileSync(file, content);
}
console.log(`Gateway contracts: ${contracts.length} public operations, internal routes excluded`);
