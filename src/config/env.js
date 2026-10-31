import 'dotenv/config';

const integer = (env, key, fallback, max = 2147483647) => {
  const raw = env[key] ?? String(fallback);
  if (!/^\d+$/.test(raw) || Number(raw) < 1 || Number(raw) > max) {
    throw new Error(`${key} must be a positive integer up to ${max}`);
  }
  return Number(raw);
};

export function loadConfig(env = process.env) {
  if (!env.JWT_SECRET || Buffer.byteLength(env.JWT_SECRET) < 32 ||
      /^(change-me|replace-)/i.test(env.JWT_SECRET)) {
    throw new Error('JWT_SECRET must contain at least 32 bytes and match IAM');
  }
  const services = {};
  for (const [name, key, port] of [
    ['iam', 'IAM_URL', 18080], ['installation', 'INSTALLATION_URL', 18081],
    ['support', 'SUPPORT_URL', 8082], ['billing', 'BILLING_URL', 28083],
  ]) {
    const url = new URL(env[key] || `http://localhost:${port}`);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
        url.pathname !== '/' || url.search || url.hash) {
      throw new Error(`${key} must be an HTTP(S) service origin without credentials`);
    }
    services[name] = url.origin;
  }
  return {
    port: integer(env, 'API_PORT', 8000, 65535),
    corsOrigins: (env.CORS_ORIGINS ?? '').split(',').map((v) => v.trim()).filter(Boolean),
    rateLimit: {
      windowMs: integer(env, 'RATE_LIMIT_WINDOW_MS', 60000),
      max: integer(env, 'RATE_LIMIT_MAX', 100),
      signInMax: integer(env, 'RATE_LIMIT_SIGN_IN_MAX', 10),
    },
    proxyTimeoutMs: integer(env, 'PROXY_TIMEOUT_MS', 10000),
    jwt: {
      secret: env.JWT_SECRET,
      issuer: env.JWT_ISSUER || 'smartgn-iam-service',
      audience: env.JWT_AUDIENCE || 'smartgn-api',
    },
    services,
  };
}
