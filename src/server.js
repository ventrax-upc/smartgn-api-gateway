import { loadConfig } from './config/env.js';
import { loadRemoteConfig } from './config/remote-config.js';
import { createApp } from './app.js';
import { startAdminRegistration } from './config/admin-registration.js';

const remoteConfig = await loadRemoteConfig();
const config = loadConfig({ ...remoteConfig, ...process.env });
const app = createApp(config);

const server = app.listen(config.port, () => {
  console.log(`SmartGN API Gateway listening on port ${config.port}`);
  for (const [name, url] of Object.entries(config.services)) {
    console.log(`  ${name} -> ${url}`);
  }
  stopAdminRegistration = startAdminRegistration(config);
});

let stopAdminRegistration = () => {};

const shutdown = (signal) => {
  console.log(`${signal} received, shutting down`);
  server.close(() => process.exit(0));
  stopAdminRegistration();
  setTimeout(() => process.exit(1), 5000).unref();
};
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
