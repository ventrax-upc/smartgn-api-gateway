# Local execution

The Gateway uses Node.js 22. Integrated execution requires the sibling IAM, Installation & Device Management, Support & Maintenance and Payments & Billing repositories and Docker Compose with support for the !override tag. Run `./scripts/start-local.ps1 -Integrated` to prepare missing local configuration, build images and wait for healthy application containers. The shared Billing environment provides integrated service credentials; Gateway preparation verifies its local IAM key matches without printing it.

Standalone mode uses `compose.yml` and the Gateway `.env`. It connects to host ports IAM 18080, Installation 18081, Support 8082 and Billing 28083. Integrated mode uses private Docker origins http://iam:8080, http://installation:8081, http://support:8082 and http://billing:8083. The Gateway listens on 8000. Existing environment values and database volumes are retained.

Configuration variables are API_PORT, CORS_ORIGINS, RATE_LIMIT_WINDOW_MS, RATE_LIMIT_MAX, RATE_LIMIT_SIGN_IN_MAX, PROXY_TIMEOUT_MS, JWT_SECRET, JWT_ISSUER, JWT_AUDIENCE, IAM_URL, INSTALLATION_URL, SUPPORT_URL and BILLING_URL. `.env.example` lists their defaults. Startup validates numeric limits, HTTP(S) backend origins and the IAM signing key. Placeholder or short signing keys prevent startup.

GET `/health` reports process liveness. GET `/ready` checks the four backend health endpoints and returns 503 while a dependency is unavailable. Swagger UI is `/swagger-ui/index.html`; the public contract is `/v3/api-docs`.

Financial events use the local authenticated broker on 1885. Device provisioning uses a separate EMQX instance on MQTT 1886 and administration 18086. The Telemetry fixture on 18090 supplies controlled device-contact and buffer evidence; the delivery fixture on 18091 accepts activation/recovery messages. These fixtures are not the external providers or the Telemetry service.

Stop the composition with `docker compose --env-file ../smartgn-payments-billing/.env -f compose.integration.yml stop`. Stopping retains persistent volumes.
