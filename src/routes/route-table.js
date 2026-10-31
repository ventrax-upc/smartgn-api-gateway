const API = '/api/v1';

// Prefix -> service. Paths, methods, status codes and bodies are forwarded untouched.
export const ROUTE_TABLE = {
  iam: [`${API}/auth`, `${API}/profiles`, `${API}/subusers`],
  installation: [
    `${API}/properties`,
    `${API}/supplypoints`,
    `${API}/installers`,
    `${API}/installations`,
    `${API}/devices`,
    `${API}/meters`,
  ],
  support: [`${API}/support`],
  billing: [
    `${API}/checkout`,
    `${API}/payment-methods`,
    `${API}/subscriptions`,
    `${API}/billing-documents`,
    `${API}/billingdocuments`, // naming inconsistency in the report; both supported
    `${API}/payments`,
  ],
};

export const matchesPrefix = (path, prefixes) =>
  prefixes.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
