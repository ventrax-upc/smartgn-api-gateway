export async function registerWithAdmin(config, env = process.env, fetchImpl = fetch) {
  const adminUrl = env.SMARTGN_ADMIN_URL;
  if (!adminUrl) return false;
  const username = env.SMARTGN_ADMIN_USERNAME;
  const password = env.SMARTGN_ADMIN_PASSWORD;
  if (!username || !password) throw new Error('SMARTGN_ADMIN_USERNAME and SMARTGN_ADMIN_PASSWORD are required');

  const serviceUrl = env.ADMIN_SERVICE_URL || `http://api-gateway:${config.port}`;
  const managementUrl = env.ADMIN_MANAGEMENT_URL || serviceUrl;
  const healthUrl = env.ADMIN_HEALTH_URL || `${serviceUrl}/health`;
  const credentials = Buffer.from(`${username}:${password}`).toString('base64');
  const response = await fetchImpl(`${adminUrl.replace(/\/$/, '')}/instances`, {
    method: 'POST',
    headers: {
      authorization: `Basic ${credentials}`,
      'content-type': 'application/json',
      accept: 'application/json',
    },
    body: JSON.stringify({
      name: 'smartgn-api-gateway',
      serviceUrl,
      managementUrl,
      healthUrl,
    }),
    signal: AbortSignal.timeout(3000),
  });

  if (!response.ok) throw new Error(`Admin returned ${response.status} during Gateway registration`);
  return true;
}

export function startAdminRegistration(config, env = process.env) {
  if (!env.SMARTGN_ADMIN_URL) return () => {};

  let stopped = false;
  let timer;
  let retryDelay = 1000;
  let registered = false;

  const register = async () => {
    try {
      await registerWithAdmin(config, env);
      if (!registered) console.log('SmartGN API Gateway registered with Admin');
      registered = true;
      retryDelay = 1000;
      if (!stopped) timer = setTimeout(register, 30000);
    } catch {
      registered = false;
      if (!stopped) {
        console.warn('SmartGN API Gateway Admin registration failed; retrying');
        timer = setTimeout(register, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 30000);
      }
    }
  };

  register();
  return () => {
    stopped = true;
    clearTimeout(timer);
  };
}
