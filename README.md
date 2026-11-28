# SmartGN API Gateway

## Overview

Public entry point for IAM, Installation, Support, Payments, Alerting and Monitoring. Validates IAM tokens, applies CORS and rate limits, and forwards documented routes to their owning services.

**Stack**  Node.js 22, Express.

## Run locally

Use the integrated setup below for the full platform. To run only the
Gateway against separately started dependencies, run `./scripts/start-local.ps1`.

### Start all 13 repositories locally

Requirements are Docker Desktop with the Linux engine and Compose v2,
PowerShell 7, and Python 3 to serve the Landing. Keep the repository directory
names as shown. The 11 backend repositories are siblings inside `SmartGN`.

```text
workspace/
├── SmartGN/
│   ├── smartgn-admin/
│   ├── smartgn-alerting-notifications/
│   ├── smartgn-api-gateway/
│   ├── smartgn-config/
│   ├── smartgn-iam/
│   ├── smartgn-installation-device-management/
│   ├── smartgn-message-broker/
│   ├── smartgn-monitoring-analytics/
│   ├── smartgn-payments-billing/
│   ├── smartgn-support-maintenance/
│   └── smartgn-telemetry-data-ingestion/
├── smartgn-frontend/
└── smartgn-landing/
```

Use the coordinated `develop` revisions for the handoff. From
`workspace`, run the following in PowerShell 7. The first script creates
the local credentials, builds the twelve application images and starts
the integrated stack.

```powershell
$gateway = './SmartGN/smartgn-api-gateway'
& "$gateway/scripts/start-integrated.ps1"
& "$gateway/scripts/seed-local.ps1"
& "$gateway/scripts/smoke-integrated.ps1"
```

In a separate terminal, from `workspace`, run
`py -m http.server 5500 --bind 127.0.0.1 --directory ./smartgn-landing`.
Use `python3` in place of `py` if your system has no Python launcher.

Open the [SPA](http://localhost:4200/), the
[Landing](http://localhost:5500/#request-installation), or
[SmartGN Admin](http://localhost:8089/). See the
[integrated guide](docs/integrated-local.md) for demo account and Admin
credentials. The integrated default uses the email fixture and payment
simulator. Enable [Niubiz Sandbox](https://github.com/ventrax-upc/smartgn-landing/blob/develop/readme.md#try-niubiz-sandbox)
only when explicitly testing the external sandbox.

Record the exact revisions used when sharing a reproducible handoff:

```powershell
@((Get-ChildItem ./SmartGN -Directory).FullName) + @('./smartgn-frontend', './smartgn-landing') |
  ForEach-Object { "$(Split-Path $_ -Leaf) $(git -C $_ rev-parse HEAD)" }
```

| Endpoint | Local URL |
| --- | --- |
| Swagger UI | [Open](http://localhost:8000/swagger-ui/index.html) |
| OpenAPI | [JSON](http://localhost:8000/v3/api-docs) |
| Health | [Open](http://localhost:8000/ready) |

## Configuration

Standalone settings use the variables in `.env.example`. Copy it to an ignored `.env` when the local startup script requires it. Integrated credentials and generated files are stored under `.local` in the Gateway repository.

## Deploy the backend and SPA on AWS

The deployment below runs the 11 backend services and the SPA on one EC2
Docker Compose host. It supports a public acceptance environment with Niubiz
Sandbox and optional Resend delivery. GitHub Pages hosts the Landing separately.
See [deployment configuration](docs/deployment-config.md) for secret groups,
provider modes, and the release and rollback checklist.

1. On a release machine, use the sibling checkouts from the local guide. Build
   the 11 backend images and the SPA for the EC2 architecture. Tag and push the
   images as `<namespace>/smartgn:<release>-<service>`. The [release commands](docs/deployment-config.md#publish-the-release-images)
   use the exact Compose service names.
2. On EC2, keep the checkout layout, install Docker with Compose 2.24.4+
   and PowerShell 7, and sign in to Docker Hub if the images are private.
   Prepare the persistent deployment inputs from the Gateway directory.

   ```bash
   umask 077
   pwsh -File scripts/start-integrated.ps1 -PrepareOnly
   chmod 600 .local/integrated.env .local/bootstrap-api-keys .local/tax.p12
   ```

3. Set these values in the Gateway's `.local/integrated.env` on EC2. Use the
   instance private IPv4 address for both bindings and replace the example
   domains with your DNS names.

   | Variable | Example or purpose |
   | --- | --- |
   | `SMARTGN_DOCKERHUB_NAMESPACE`, `SMARTGN_IMAGE_TAG` | Docker Hub namespace and release tag for all 12 images. |
   | `SMARTGN_GATEWAY_BIND`, `SMARTGN_FRONTEND_BIND` | EC2 private address accessible from the ALB, e.g. `10.0.1.25`. |
   | `SMARTGN_FRONTEND_PORT` | `4200` by default. Match the SPA target group port. |
   | `SMARTGN_PUBLIC_ORIGIN` | `https://app.smartgn.example`. Sets IAM's activation and reset URLs. |
   | `CORS_ORIGINS` | `https://ventrax-upc.github.io,https://app.smartgn.example`. Use origins without paths and include the actual Pages custom domain if configured. |
   | `CHECKOUT_EMAIL_MODE`, `IAM_EMAIL_MODE` | Set both to `resend` for delivery to external inboxes. |
   | `RESEND_API_KEY`, `RESEND_FROM_EMAIL` | Server-side key and verified sender. Required in Resend mode. |
   | `NIUBIZ_SANDBOX_ENABLED`, `NIUBIZ_SANDBOX_MERCHANT`, `NIUBIZ_SANDBOX_USER`, `NIUBIZ_SANDBOX_PASSWORD` | Set the flag to `true` and supply Sandbox credentials for card checkout. |
   | `RATE_LIMIT_MAX` | General Gateway rate limit. Gateway currently counts requests by its immediate network peer behind a proxy. Validate shared limits under expected traffic and enforce per-client protection at ingress. |

4. Run the following commands from the Gateway checkout.

   ```bash
   spa=../../smartgn-frontend
   compose=(docker compose -p smartgn-aws --env-file .local/integrated.env \
     -f compose.integration.yml -f "$spa/compose.frontend.yml" -f "$spa/compose.registry.yml")
   "${compose[@]}" config --quiet
   "${compose[@]}" pull
   "${compose[@]}" up -d --no-build --wait --wait-timeout 300
   "${compose[@]}" ps
   ```

5. Configure an HTTPS Application Load Balancer and certificate for the API
   and SPA hostnames. Route the API hostname to EC2 port `8000` with
   `/health` as the target health check. Route the SPA hostname to port
   `4200` with `/healthz`. Point both DNS records to the ALB. On EC2, allow
   the two target ports only from the ALB security group. Keep databases,
   EMQX, internal services, Config and Admin off the public listeners.
   See the [AWS target security group instructions](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/target-group-register-targets.html).
6. Check `https://<api-host>/ready`, `https://<spa-host>/healthz` and the
   SPA route `/activate-password`. Set `SMARTGN_GATEWAY_URL` to the API HTTPS
   origin in [the Landing repository](https://github.com/ventrax-upc/smartgn-landing/blob/develop/readme.md#publish-with-github-pages)
   and republish. Verify the published form and SPA with the release checklist.

To check the Landing's CORS configuration before publishing, replace the
example API and Landing origins in this request.

```bash
curl -i -X OPTIONS 'https://api.smartgn.example/api/v1/installations/email-verifications' \
  -H 'Origin: https://ventrax-upc.github.io' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type'
```

Expect HTTP 204 and an `Access-Control-Allow-Origin` value matching the
Landing origin.

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

## Acceptance scenarios

See the [Gherkin acceptance scenarios](docs/acceptance/scenarios.gherkin). These are acceptance specifications. Use the verification commands above to run the automated checks.

## License

Distributed under the [MIT License](LICENSE).
