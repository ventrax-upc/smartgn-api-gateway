# SmartGN API Gateway

## Overview

Public entry point for IAM, Installation, Support, Billing, Alerting and Monitoring. Validates IAM tokens, applies CORS and rate limits, and forwards documented routes to their owning services.

**Stack**  Node.js 22, Express.

## Run locally

Requirements are Docker Desktop with the Linux engine and PowerShell 7. Keep the SmartGN repositories as siblings for the integrated stack.

```powershell
./scripts/start-local.ps1
```

Run `./scripts/start-integrated.ps1` to start all 11 services through the integrated Compose.

| Endpoint | Local URL |
| --- | --- |
| Swagger UI | [Open](http://localhost:8000/swagger-ui/index.html) |
| OpenAPI | [JSON](http://localhost:8000/v3/api-docs) |
| Health | [Open](http://localhost:8000/ready) |

## Configuration

Standalone settings use the variables in `.env.example`. Copy it to an ignored `.env` when the local startup script requires it. Integrated credentials and generated files are stored under `.local` in the Gateway repository.

## Verification

```powershell
./scripts/test.ps1
./scripts/smoke-integrated.ps1
```

The integrated smoke verifies REST contracts, Admin registrations and seeded workflows.

## Repository layout

- `src` contains the service implementation.
- `test` contains service tests.
- `docs` contains service documentation.
- `scripts` contains local startup and verification commands.
- `tools` contains verification helpers and supporting assets.
- `fixtures/db.json` defines demo fixtures for local verification.

## Documentation

- [Local development](docs/local-development.md)
- [Integrated stack](docs/integrated-local.md)
- [Architecture](docs/architecture.md)
- [Contracts](docs/contracts.md)
- [OpenAPI export](docs/openapi.json)
- [Service overview](docs/service-overview.md)

## License

Distributed under the [MIT License](LICENSE).
