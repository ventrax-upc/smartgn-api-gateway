import 'dotenv/config';

const toInt = (value, fallback) => {
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
};

const toList = (value) =>
  (value ?? '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

export function loadConfig(env = process.env) {
  if (!env.JWT_SECRET) {
    throw new Error('JWT_SECRET is required (use the same secret as the IAM service)');
  }

  return {
    port: toInt(env.API_PORT, 8000),
    corsOrigins: toList(env.CORS_ORIGINS),
    rateLimit: {
      windowMs: toInt(env.RATE_LIMIT_WINDOW_MS, 60000),
      max: toInt(env.RATE_LIMIT_MAX, 100),
      signInMax: toInt(env.RATE_LIMIT_SIGN_IN_MAX, 10),
    },
    proxyTimeoutMs: toInt(env.PROXY_TIMEOUT_MS, 10000),
    jwt: {
      secret: env.JWT_SECRET,
      issuer: env.JWT_ISSUER || 'smartgn-iam-service',
      audience: env.JWT_AUDIENCE || 'smartgn-api',
    },
    services: {
      iam: env.IAM_URL || 'http://localhost:18080',
      installation: env.INSTALLATION_URL || 'http://localhost:18081',
      support: env.SUPPORT_URL || 'http://localhost:8082',
      billing: env.BILLING_URL || 'http://localhost:28083',
    },
  };
}
