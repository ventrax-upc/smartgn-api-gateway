# SmartGN API Gateway

Stateless Node.js 22 / Express HTTP entry point for the SmartGN services. Public routes retain their path, method, body and upstream status. The Gateway verifies IAM JWTs, CORS origins and request limits. Current sessions, principal/delegated account rules, ownership and meter/function permissions remain enforced by each owning service. It has no business database, gRPC server or MQTT ingestion endpoint.

## Local execution

Run `./scripts/start-local.ps1 -Integrated` to build and start the five services and their isolated storage dependencies in Docker. The sibling repositories must be present. The integrated composition uses the existing shared environment in `../smartgn-payments-billing/.env` and prepares the Gateway's ignored `.env` with the matching IAM key. Existing secrets and volumes are preserved.

| Component | Local URL |
|---|---|
| API Gateway | http://localhost:8000/swagger-ui/index.html |
| IAM | http://localhost:18080/swagger-ui/index.html |
| Installation & Device Management | http://localhost:18081/swagger-ui/index.html |
| Support & Maintenance | http://localhost:8082/swagger-ui/index.html |
| Payments & Billing | http://localhost:28083/swagger-ui/index.html |

`./scripts/start-local.ps1` starts only the Gateway and uses host-exposed backend ports. `-SkipBuild` reuses existing images. For host development use `npm ci --ignore-scripts` followed by `npm run dev` after preparing `.env`.

## Verification

`./scripts/test.ps1` runs middleware and routing tests in Node 22 Docker. `./scripts/smoke-local.ps1` executes Billing, Support and device-provisioning acceptance through the Gateway with real local IAM, Installation and EMQX. Provider confirmations, activation delivery and synthetic integration events are explicit fixtures. The Billing suite restarts Billing to verify durable reconciliation; run it only against the local verification environment.

The Gateway OpenAPI aggregates the public contracts of its four backend services. Routing tests exercise all current public operations against a controlled upstream; these checks are separate from business acceptance with the real local services.

## API documentation

Swagger UI is available at `/swagger-ui/index.html`, with the public OpenAPI contract at `/v3/api-docs`. `/health` reports process liveness; `/ready` checks all four backends and returns 503 when a dependency is unavailable. Neither exposes credentials or private dependency URLs. `/internal/**` routes are not published.

See [architecture](docs/architecture.md), [contracts](docs/contracts.md), [local development](docs/local-development.md) and [service overview](docs/service-overview.md). Secrets belong only in ignored local environments. HTTP and in-memory rate limits are intended for local execution; production TLS termination, trusted ingress and a shared rate-limit store require deployment configuration.
