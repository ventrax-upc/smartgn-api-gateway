# Integrated local SmartGN

The [workspace startup guide](../README.md#start-all-13-repositories-locally)
covers the backend, SPA and Landing. The Compose project runs 11 SmartGN services and their local infrastructure. Run
the commands from this repository with the other ten repositories checked out as
siblings. The SPA uses the Gateway at http://localhost:8000 and can run separately.

```powershell
./scripts/start-integrated.ps1
./scripts/seed-local.ps1
./scripts/smoke-integrated.ps1
```

Use `-SkipBuild` when the local images already contain your changes.
`-InfrastructureOnly` starts PostgreSQL, Redis, InfluxDB, EMQX and the delivery
fixture. Application images build sequentially. The Compose limits target a
5.5 GiB running stack, with memory samples written to `.local/docker-stats.jsonl`.

Keep `.local/seed-state.json` with the database volumes used by the demo seed.
A checkout conflict can occur if the checkpoint and those volumes come from
different runs. Use a separate Compose project and seed state to validate a
clean start while keeping existing demo data.

## Access

The integrated Compose publishes these ports on loopback. The HTTP port in the table is also the listening port inside each container. Service-to-service calls use the Docker DNS name and that port. Telemetry and Billing retain private gRPC listeners at 9084 and 9083.

| Service | Local port | Browser path |
| --- | ---: | --- |
| API Gateway | 8000 | `/swagger-ui.html` |
| IAM | 8080 | `/swagger-ui/index.html` |
| Installation & Device Management | 8081 | `/swagger-ui/index.html` |
| Support & Maintenance | 8082 | `/swagger-ui/index.html` |
| Payments & Billing | 8083 | `/swagger-ui/index.html` |
| Monitoring & Analytics | 8084 | `/swagger/index.html` |
| Telemetry & Data Ingestion | 8085 | `/swagger/index.html` |
| Alerting & Notifications | 8086 | `/swagger-ui/index.html` |
| Message Broker | 8087 | `/swagger-ui/index.html` |
| SmartGN Config | 8088 | `/actuator/health` |
| SmartGN Admin | 8089 | `/` |

- Sign in to Admin as `smartgn-local` with `SMARTGN_ADMIN_PASSWORD` from `.local/integrated.env`.
- Use the three IAM addresses in the IAM `fixtures/db.json` with
  `DEMO_USER_PASSWORD` from the same ignored file. The bootstrap administrator is
  `admin@smartgn.test` with `BOOTSTRAP_SUPERADMIN_PASSWORD`.
- The integrated CORS allowlist includes the local SPA, the local Landing Page
  and GitHub Pages. Both Compose configurations allow
  `http://localhost:5500`, `http://127.0.0.1:5500` and
  `https://ventrax-upc.github.io`. The SPA overlay uses its configured
  host port for the SPA origins. Override `CORS_ORIGINS` with the full list
  when using other origins and set `SMOKE_CORS_ORIGIN` to one of those origins
  when testing a different SPA origin.

The project uses PostgreSQL with independent databases and roles for domain
services. Telemetry uses its dedicated `telemetry-postgres` instance for
durable processing and InfluxDB for time-series readings. Monitoring uses Redis for cache.
EMQX has separate accounts and ACLs for service events and per-device telemetry.
Local payment results and activation delivery use fixtures.

## Lifecycle

```powershell
docker compose --env-file .local/integrated.env -f compose.integration.yml ps
docker compose --env-file .local/integrated.env -f compose.integration.yml down
```

The commands above preserve volumes. `./scripts/reset-integrated.ps1` removes
the current integrated project volumes and seed checkpoints and restarts on
empty stores. `./scripts/retire-legacy-local.ps1` archives and checks volumes
from named legacy SmartGN projects before removing their resources. Its archives
and hashes are under `.local/retired-*`. Keep these files private.

## Integration contracts

The smoke command compares live and versioned OpenAPI routes, authentication
requirements, and request and response schemas. It records an HTTP result for
each REST operation in `.local/rest-inventory.json`. Protected routes must
reject anonymous access, public operations must reject incomplete inputs,
and health requests must succeed. Each observed status must be documented.
The smoke also exercises authenticated
workflows, including simulated notification delivery from a telemetry alert,
Support visit completion and Billing coverage, and session revocation.
Service docs define request and response details for REST,
gRPC and MQTT. Config uses the local profile and application names. Supply secrets
through the environment. Deployment-specific URLs, transport security and external
provider settings belong in the deployment environment.

## Telemetry recovery smoke

Run `./scripts/smoke-telemetry-recovery.ps1` on a local integration stack with the Billing simulator and the fixture notification provider. It creates a uniquely identified checkout, account and test meter, persists 360 simulator readings in SQLite under `.local`, interrupts InfluxDB and Alerting, restarts Telemetry and checks recovery. The sample timestamps model one hour of offline collection. The simulator performs the MQTT publisher part of the recovery test. The command temporarily stops those local services and restores them on exit.

Telemetry stores its processing ledger in the dedicated `telemetry-postgres-data` volume. The standard startup script creates credentials for that database and keeps existing integrated volumes. Use `TELEMETRY_MQTT_CLIENT_ID` and `TELEMETRY_MQTT_TOPIC` to configure the integrated subscriber.
