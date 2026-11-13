const API = '/api/v1';

export const ROUTE_TABLE = {
  iam: [`${API}/auth`, `${API}/profiles`, `${API}/subusers`],
  installation: [
    `${API}/properties`, `${API}/supply-points`, `${API}/installers`,
    `${API}/installations`, `${API}/devices`, `${API}/meters`, `${API}/operations/outbox`,
  ],
  support: [`${API}/support`],
  billing: [
    `${API}/checkout`, `${API}/payment-methods`, `${API}/subscriptions`,
    `${API}/billing-documents`, `${API}/payments`, `${API}/technical-statements`,
  ],
  alerting: [
    `${API}/alerts`, `${API}/alert-rules`, `${API}/notifications`,
    `${API}/notification-preferences`,
  ],
  monitoring: [`${API}/analytics`],
};

export const matchesPrefix = (path, prefixes) =>
  prefixes.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
