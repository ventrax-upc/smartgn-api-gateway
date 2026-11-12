# Local execution

The Gateway uses Node.js 22. Integrated execution requires the ten sibling repositories and Docker Compose. Run `./scripts/start-integrated.ps1` to create ignored local credentials, build images sequentially and start all 11 services.

Standalone mode uses `compose.yml` and the Gateway `.env`. The integrated network uses service DNS names for the six routed services and keeps backend services on the Compose network. The Gateway listens on loopback port 8000, reads non-secret defaults from Config, and registers health with authenticated Admin. The integrated stack stores generated secrets in ignored `.local` files.

Configuration variables include the API and rate limit settings, shared JWT and internal service secrets, six routed service origins, and Config/Admin URLs and credentials. `.env.example` lists safe local templates. Startup validates numeric limits, HTTP(S) backend origins and the IAM signing key. Placeholder or short signing keys prevent startup.

GET `/health` reports process liveness. GET `/ready` checks the six routed service health endpoints and returns 503 while a dependency is unavailable. Swagger UI is `/swagger-ui/index.html`; the 108-operation public contract is `/v3/api-docs`.

Telemetry and service events use the shared EMQX instance with distinct users and topic ACLs. Local payments and activation delivery use labeled fixtures. For the full service startup, seed and smoke commands, see [integrated local SmartGN](integrated-local.md).

Stop the composition with `docker compose --env-file .local/integrated.env -f compose.integration.yml stop`. Stopping retains the local data volumes. Use `./scripts/reset-integrated.ps1` only when you intend to recreate the seeded local databases and broker data.
