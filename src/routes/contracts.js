import { readFileSync } from 'node:fs';

export const CONTRACTS = JSON.parse(readFileSync(new URL('../config/contracts.json', import.meta.url)));
const compiled = CONTRACTS.map((contract) => ({
  ...contract,
  pattern: new RegExp(`^${contract.path.split('/').map((part) =>
    part.startsWith('{') ? '[^/]+' : part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('/')}/?$`),
}));

export function findContract(method, path) {
  return compiled.find((contract) =>
    (contract.method === method || (method === 'HEAD' && contract.method === 'GET')) &&
    contract.pattern.test(path));
}
