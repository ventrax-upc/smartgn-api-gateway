export async function readiness(config, req, res) {
  const dependencies = Object.fromEntries(await Promise.all(
    Object.entries(config.services).map(async ([name, origin]) => {
      try {
        const response = await fetch(`${origin}/actuator/health`, {
          signal: AbortSignal.timeout(Math.min(config.proxyTimeoutMs, 2000)),
        });
        const body = await response.json();
        return [name, response.ok && body.status === 'UP' ? 'UP' : 'DOWN'];
      } catch { return [name, 'DOWN']; }
    }),
  ));
  const up = Object.values(dependencies).every((status) => status === 'UP');
  res.status(up ? 200 : 503).json({ status: up ? 'UP' : 'DOWN', dependencies });
}
