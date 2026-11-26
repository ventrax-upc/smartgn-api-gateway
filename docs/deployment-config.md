# SmartGN deployment configuration

Follow the [AWS deployment guide](../README.md#deploy-the-backend-and-spa-on-aws)
for EC2 and the public endpoints. The 12 application images share a release
tag. Only the API Gateway and the SPA receive public HTTP traffic through the
ALB. The SPA calls the Gateway over Compose DNS. The Landing calls the public
API origin directly.

## Publish the release images

Run from the Gateway checkout on a release machine with the sibling
repositories present. Use a host matching the EC2 architecture or set
`DOCKER_DEFAULT_PLATFORM` to the required platform before building.

```bash
export SMARTGN_DOCKERHUB_NAMESPACE=your-namespace
export SMARTGN_IMAGE_TAG=your-release
spa=../../smartgn-frontend
umask 077
pwsh -File scripts/start-integrated.ps1 -PrepareOnly
compose=(docker compose -p smartgn-release --env-file .local/integrated.env \
  -f compose.integration.yml -f "$spa/compose.frontend.yml")
services=(config admin message-broker iam installation support billing alerting telemetry monitoring api-gateway)
"${compose[@]}" build "${services[@]}"
docker build -t smartgn-frontend:local "$spa"
docker login
for service in "${services[@]}" frontend; do
  source="smartgn-release-$service"
  if [ "$service" = frontend ]; then source=smartgn-frontend:local; fi
  target="$SMARTGN_DOCKERHUB_NAMESPACE/smartgn:$SMARTGN_IMAGE_TAG-$service"
  docker tag "$source" "$target" && docker push "$target" || exit 1
done
```

## Deployment configuration and secrets

Prepare the EC2 files once and preserve them across releases. The preparation
script supplies the credentials required by the base Compose manifest and
generates the EMQX bootstrap file and a test signing certificate. Populate
provider settings afterwards. Restrict access to the files and back them up
with the volumes. Use files or a deployment secret store for credentials.

| Scope | Required inputs and defaults |
| --- | --- |
| Gateway and service authentication | `JWT_SECRET` shared with IAM and `INTERNAL_SERVICE_TOKEN` shared by internal clients. Compose wires the DNS endpoints and aligns the issuer and audience. |
| Identity, admin and encryption | `BOOTSTRAP_SUPERADMIN_PASSWORD`, `SMARTGN_ADMIN_PASSWORD`, `DELIVERY_ENCRYPTION_KEY`, `DEVICE_CREDENTIAL_KEY`, `CARD_ENCRYPTION_KEY`. Preserve signing and encryption keys when reusing data. |
| PostgreSQL | `POSTGRES_PASSWORD`, `DB_IAM_DB`, `DB_INSTALLATION_DB`, `DB_SMARTGN_SUPPORT_DB`, `DB_BILLING_DB`, `DB_SMARTGN_ALERTING_DB`, `DB_SMARTGN_MONITORING`, `DB_TELEMETRY_ADMIN`, `DB_TELEMETRY`. Telemetry uses a dedicated PostgreSQL instance. |
| InfluxDB and Redis | `INFLUX_PASSWORD` and `INFLUX_TOKEN` bootstrap InfluxDB. Redis uses the private Compose network. |
| EMQX | `DEVICE_BROKER_API_KEY`, `DEVICE_BROKER_API_SECRET`, `MQTT_PASSWORD`, `MQTT_BROKER_PASSWORD`, `MQTT_SUPPORT_PASSWORD`, `MQTT_BILLING_PASSWORD`, `MQTT_TELEMETRY_PASSWORD`. Use a private network or VPN for external test devices. |
| Email | `CHECKOUT_EMAIL_MODE=resend` on Installation and `IAM_EMAIL_MODE=resend` on IAM enable delivery. Both require `RESEND_API_KEY` and a verified `RESEND_FROM_EMAIL`. `APP_PASSWORD_RESET_FROM_EMAIL` is an accepted Compose alias. |
| Test billing and delivery | The registry overlay disables browser payment simulation. It can use `NIUBIZ_SANDBOX_ENABLED=true` with `NIUBIZ_SANDBOX_MERCHANT`, `NIUBIZ_SANDBOX_USER` and `NIUBIZ_SANDBOX_PASSWORD`. Fiscal status still uses the local adapter and the generated test `TAX_KEY_PASSWORD` certificate. Alerting and internal fixture contracts retain their local configuration. `FIXTURE_ADMIN_TOKEN` and `DEMO_USER_PASSWORD` remain required Compose inputs. |

Compose handles the Gateway's `IAM_URL`, `INSTALLATION_URL`, `SUPPORT_URL`,
`BILLING_URL`, `ALERTING_URL` and `MONITORING_URL` through private DNS.
Outside this Compose network, set their private HTTP origins and align
`JWT_ISSUER` and `JWT_AUDIENCE` with IAM. Telemetry exposes
`TELEMETRY_MQTT_CLIENT_ID`, `TELEMETRY_MQTT_TOPIC` and
`TELEMETRY_PENDING_CAPACITY` for deployments that need to tune ingestion.

The registry composition is suitable for acceptance testing. Commercial
Niubiz charging, fiscal certification, real Alerting channels and invoice
email need their own provider integration and verification before customer
traffic. The local demo seed and its shared demo accounts belong to local
development.

## Release checklist

- Verify both ALB targets, Gateway readiness, the SPA health endpoint and a
  direct visit to the SPA activation route.
- Verify the browser CORS preflight from the published Landing origin. Submit
  a test checkout, receive the email, exercise approval and rejection using
  test cards, then verify activation, login and password recovery with a
  test inbox. Verify the fiscal document is identified as a test document.
- Verify Monitoring, Alerting and MQTT from the private network. Check data
  survives a service restart and verify backups independently.
- For rollback, restore the previous release tag and rerun the Compose pull
  and up commands only if its schema is compatible. Back up before a release
  with migrations and use the documented database restore procedure for an
  incompatible schema.
