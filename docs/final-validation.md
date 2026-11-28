# SmartGN validation

This validation covers local changes to IAM, Alerting, the Payments entitlement
contract, Monitoring, Config and integrated Compose. Product acceptance and AWS
readiness are open.

## Repositories

| Repository | Baseline revision | Local change |
| --- | --- | --- |
| smartgn-admin | `a04383e` | — |
| smartgn-alerting-notifications | `1053a67` | Resend adapter, device report receipts and contract tests |
| smartgn-api-gateway | `3f01399` | Public OpenAPI and integrated SPA startup |
| smartgn-config | `7463bdd` | Payments gRPC configuration names |
| smartgn-iam | `4e30701` | Generic recovery challenge and regression test |
| smartgn-installation-device-management | `553ba8a` | — |
| smartgn-message-broker | `6a74a2e` | — |
| smartgn-monitoring-analytics | `f33a377` | Payments entitlement client and configuration |
| smartgn-payments-billing | `336759d` | Payments entitlement server protocol |
| smartgn-support-maintenance | `d14be8a` | — |
| smartgn-telemetry-data-ingestion | `1861cbf` | Device report parsing and Alerting payload |
| smartgn-frontend | `eb2e6f2` | Generic recovery feedback in Spanish and English |
| smartgn-landing | `5cc0cf4` | — |

## Behavior and evidence

| Behavior | Implementation | Verification |
| --- | --- | --- |
| Password recovery | Valid requests receive an opaque challenge. IAM sends a code only for eligible accounts outside the resend cooldown. | 8 focused IAM recovery tests passed. |
| Alert email | Resend accepts the email through `POST /emails`. The outbox stores the provider's ID as acceptance and reuses a stable request key on retry. | 19 Alerting tests passed on Java 25 and disposable PostgreSQL. Commercial delivery remains unverified. |
| Payments entitlement | Producer and consumer use `smartgn.payments.v1.SubscriptionEntitlementService/GetProEntitlement`. Monitoring reads `PAYMENTS_GRPC_URL`. | 41 Monitoring tests passed. |
| Public REST contracts | Regenerated Gateway OpenAPI from service exports. | 117 public operations and 25 Gateway tests passed. |
| Integrated SPA | Compose defines the Nginx build and startup with Gateway as its local upstream. | Compose configuration, SPA lint, 12 SPA tests and the host production build passed. |
| Paid periods and technical coverage | Payments stores period bounds in `subscription_periods`. `coverage_decisions` stores the visit key, completion instant, cost, balance and optional payment order. | 46 Payments tests passed with disposable PostgreSQL, including historical coverage, concurrent confirmations, fiscal migration and idempotency. Active Pro entitlement and completion-to-coverage smoke passed. The full renewal lifecycle remains open. |
| Durable telemetry | Telemetry stores the ingestion state in PostgreSQL and writes time series to InfluxDB. | 101 Telemetry tests passed with disposable PostgreSQL. Integrated smoke confirmed authenticated MQTT QoS 1 publication and a telemetry-driven alert. |

## Integrated runtime

The 12 application images were built from the local checkouts. The existing
Compose project started with 18 healthy containers. The EMQX initializer
exited successfully. The smoke run probed 263 REST entries, exercised the
Payments and Telemetry gRPC paths through Monitoring, and verified local email
dispatch, account isolation, a revoked session, technical coverage, and
rejection of duplicate visit completion.

A separate Compose project started with new data volumes and a separate seed
checkpoint. It passed the same 263 REST probes and integrated smoke scenarios.
The clean project was stopped after the run. Its volumes and the original
project volumes were preserved.

The original project was restored with 18 healthy containers. The 12 running
application image IDs matched the local build tags. Headless Chromium loaded the
SPA through Nginx and verified that recovery for a synthetic unknown email
returned HTTP 202, an opaque challenge and generic recovery instructions.

Existing migrations remain unchanged. Alerting migration
`V3__reported_valve_state.sql` adds nullable device-report fields to
`telemetry_receipt` so legacy events remain readable.

A subsequent build of Telemetry and Alerting added separate values for leak
detection, observed valve position, reported autonomous actuation and its
result. All 104 Telemetry tests passed with disposable PostgreSQL. An
authenticated Alerting HTTP probe on the rebuilt stack verified the stored
fields and measurement timestamp. Replaying the event with a different
observed state preserved the original receipt. An isolated project with a
provisioned test device also verified the new fields from MQTT publication
through Telemetry to the Alerting PostgreSQL receipt. The 19 Alerting tests
and 263 integrated REST probes passed again.

All 13 originally clean working trees retained their starting HEAD and were
aligned with their locally recorded upstream. Changes are unstaged. No commits
or pushes were made.

## Architecture and data model follow-up

- Persistence represents the paid entitlement as a time interval tied to
  a unique payment order. The technical coverage decision is keyed by visit
  and can reference a separate payment order. These constraints belong in
  the persistence model independently of the domain class structure.
- Successful email submission records provider acceptance. Confirmed delivery
  requires a separate provider signal. The current local delivery fixture
  exercises the dispatch lifecycle.
- Corrective visits need an explicit relationship to the preceding
  intervention and recorded assignments. The valve model needs separate
  fields for leak detection, reported actuation and observed state.

## Reproduction

Use the [integrated local guide](integrated-local.md) for workspace layout,
prerequisites, startup and fixtures.

```powershell
# API Gateway checkout
node tools/export-openapi.mjs --check
npm test
./scripts/start-integrated.ps1
./scripts/seed-local.ps1
./scripts/smoke-integrated.ps1

# In the owning Java checkouts
./mvnw.cmd '-Dtest=PasswordRecoveryCodesTest,PasswordRecoveryServiceTest' test
./scripts/test.ps1 # Alerting, including disposable PostgreSQL
./scripts/test.ps1 # Payments, including disposable PostgreSQL

# Monitoring checkout
dotnet test

# SPA checkout
npm run lint
npm test -- --watch=false
npm run build
```

For a clean-volume check, use a separate Compose project name and an override
with the 12 image references from the existing build. Mount an empty directory
at `/state` in the `verify` service so its seed checkpoint is isolated. Stop
the existing project while the clean project uses the same loopback ports.
Run the seed and smoke containers in the clean project, stop it, then start
the existing project again. Use `stop` to keep both projects' data.

## Open acceptance items

- Corrective installation and technical visits have runtime evidence. The
  administrative Support queue honors safety and verified Pro priority.
- Device reports were verified through MQTT, the REST contract and the
  Chromium alert detail view.
- Historical database identifiers and fiscal document names are preserved.
- Production profiles, AWS provisioning with two Gateway replicas, traffic
  through the ALB, backups, MQTT/TLS and real provider flows require validation.
  The existing EC2 instructions cover a single-host acceptance stack and
  support routing SPA API requests to the certified ALB hostname.
- Niubiz is configured for Sandbox checkout only. Local payment fixtures
  cover token and charge workflows with synthetic data. Sandbox card and
  renewal verification remains separate from local fixture validation.
  SUNAT production remains outside the validated local environment.
- Independent audit and full requirement traceability remain open.

## Local scope audit

The scope below allows Niubiz Sandbox and isolated local provider fixtures.
Cloud deployment is user-operated. A contract probe verifies routing and
documented responses. Feature acceptance requires exercising the applicable
workflow and its data or authorization effects.

| Requirements | Components inspected | Evidence and remaining acceptance |
| --- | --- | --- |
| RF01–RF05 | Landing, IAM, SPA, Gateway | Sign-in, session revocation and generic recovery have runtime evidence. Complete checkout-to-activation and profile workflows were not rerun in this audit. |
| RF06, RF38–RF41, RF48–RF50 | Payments, Landing, SPA | Local Pro entitlement and payment persistence are covered. Sandbox checkout has its own adapter. Recurring token charges use the local implementation or an unavailable fallback. Sandbox renewals, failed-renewal transitions and the external fiscal flow lack complete acceptance evidence. |
| RF07–RF12, RF31–RF37 | Installation, IAM, SPA, Broker | Seeded property, meter and installation flow has local evidence. Corrective installation has runtime and persistence evidence without repeating the original completion event. |
| RF13–RF19 | Monitoring, Telemetry, Payments, Redis, SPA | Consumption, reports, private entitlement and cross-account denial were exercised. Complete multi-meter, latency and browser acceptance remains open. |
| RF20–RF25, RF51 | Telemetry, Alerting, SPA, Broker | MQTT-to-receipt persistence, replay protection and simulated notification dispatch passed. Device-reported leaks and failed autonomous actuation have separate rules and SPA labels. The SPA displays the stored device report and its measurement timestamp. |
| RF26–RF30, RF42–RF47, RF55 | Support, Payments, SPA | Technical completion, coverage and duplicate protection passed. Corrective visits preserve earlier history and use a different technician. The Support queue orders critical safety incidents ahead of standard Pro and standard Free. Full rating acceptance remains open. |
| RF52–RF54 | IAM, Gateway, Monitoring, SPA | Service-level checks and account isolation have evidence. A complete browser matrix for invitation, permission changes and revocation remains open. |
| RNF01–RNF04, RNF09, RNF12 | Compose, Gateway, Telemetry, Monitoring | Build, readiness and REST regression passed. PostgreSQL inbox load and a browser latency sample passed. System-wide load, availability and maintainability acceptance remain open. |
| RNF05–RNF07, RNF16, RNF21 | IAM, Gateway, Message Broker, Config, Admin | JWT, session revocation, account denial and authenticated MQTT have local evidence. TLS, encryption at rest and the complete credential rotation and revocation matrix require further verification. |
| RNF08, RNF13, RNF15, RNF17–RNF20 | Telemetry, Alerting, Payments, Admin | Disposable PostgreSQL tests, replay evidence, audit rows and service registration passed. Full failure recovery, retention and retry acceptance remain open. |
| RNF10–RNF11, RNF14 | SPA, Landing | Automated accessibility scans and selected flows across Chromium, Edge, Firefox and WebKit passed. Native Safari, the two-version matrix and manual accessibility checks remain open. |
| QAS1–QAS25 | All components | Component and runtime evidence is captured above. A scenario-by-scenario acceptance run with defined measurements remains outstanding. |

### Source findings

- An incoming event without active rules receives a retryable HTTP 503 before
  any receipt or watermark is written. Previously processed events keep their
  idempotent response.
- Alerting evaluates device-reported leaks and failed autonomous actuation
  independently of the valve position. The SPA labels the two new alert metrics.
  The SPA shows all four values and the measurement timestamp.
- Payments runs renewals through the generic payment gateway. Local token and
  charge fixtures and Niubiz Sandbox checkout are separate paths.
- Compose, Gateway, Config and the HTTP and gRPC integrations use the Payments service name.

### Payments rename and alert retry regression

- The active Compose Payments service, container and image use `payments`.
  The replaced development container and image were removed without removing
  volumes. The historical database and fiscal identifiers remain in use.
- Payments passed 46 tests with disposable PostgreSQL. Gateway passed 25
  tests. The SPA passed lint and 12 tests.
- Alerting passed 21 tests with disposable PostgreSQL, including a retry
  after activation of a rule. A runtime probe produced separate leak and
  failed-actuation alerts with the valve reported closed. A replay did not
  produce additional alerts.

### Telemetry dependency-failure validation

The current integrated stack passed `scripts/smoke-telemetry-recovery.ps1`.
All 360 readings remained queued across a Telemetry restart with InfluxDB and
Alerting stopped. After both dependencies returned, PostgreSQL recorded 360
completed events and 360 unique Alerting receipts, and InfluxDB contained 360
points. A replay added no records. Two readings with the same measurement
timestamp retained distinct Influx point identities. The test also exercised
email verification, idempotent fixture checkout, account activation, a single
test receipt and provisioning a distinct MQTT device.

The checkout prerequisite uses the local payment fixture. Niubiz Sandbox was
restored after the run.

### Support and browser validation

Support passed `scripts/test.ps1` with disposable PostgreSQL and an
authenticated MQTT broker. Maven verify completed with 21 tests and no
failures, errors or skips. The suite covers the existing visit workflow,
technical coverage, MQTT, authorization, photos and migrations.

Chromium exercised the password recovery form at 1366 and 390 pixels. Both
viewports exposed one accessible email label, accepted keyboard input, kept
the submit button disabled for an invalid address, enabled it for a valid
address and showed no horizontal overflow or page errors.

### Isolated payment fixture compatibility

The financial acceptance script now restarts the `payments` Compose service
and reads `PAYMENTS_SMOKE_URL`. The standalone broker preparation adds the
`payments-service` credential if an existing local password file predates the
rename. It preserves existing entries. The updated preparation was exercised
against the existing standalone fixture configuration.

### IAM validation

IAM passed `scripts/test.ps1` with disposable PostgreSQL and authenticated
MQTT. Maven verify completed with 46 tests and no failures, errors or skips.
The integrated Compose configuration also parsed successfully and resolved
`smartgn-dev-payments`. All 13 working trees passed Git diff checks and the
changed PowerShell scripts parsed successfully.

### Installation validation

Installation & Device Management passed `scripts/test.ps1` with disposable
dependencies. Maven verify completed with 64 tests and no failures, errors
or skips. This covers the existing implementation, including its database
migrations, device provisioning, HTTP contracts and IAM compatibility.

### Local read latency

The integrated Gateway passed a local RNF02 sample using an authenticated
fixture account and the profile, property list and supply-point list routes.
After one warm-up per route, 20 successful requests per route ran with
concurrency four. Nearest-rank p95 was 0.085 s for profile, 0.295 s for
properties and 0.154 s for supply points. Maximum observed latencies were
0.095 s, 0.300 s and 0.163 s respectively. The sample passed the 3 s
threshold. Production-scale and browser rendering performance require
separate measurements.

### Financial workflow with local provider fixtures

The isolated Payments acceptance run passed all 25 checks. It exercised
checkout and activation, Pro activation, historical technical coverage,
signed test fiscal documents, a single reconciled debit after a Payments
restart, failed renewal without extending the paid period, removal of IAM
Pro authorization after expiry, and disabling auto-renewal when the card was
unlinked. The environment used synthetic provider and fiscal data and a
real local PostgreSQL and MQTT broker. Sandbox provider recurrence still
requires its own evidence.

### Niubiz Sandbox session

A verified installation checkout through the integrated Gateway returned
`provider=NIUBIZ_SANDBOX`, `testMode=true` and a nonempty provider session
key and merchant ID. The probe ended before payment authorization and printed
no credentials, session key or merchant ID. The current adapter covers
initial checkout. The local recurring-payment test uses synthetic provider
evidence, and direct Sandbox recurrence remains unverified.

### Critical notification latency sample

A provisioned local device published a critical leak with the valve reported
closed over authenticated MQTT. Alerting persisted the first simulated
notification attempt with status `ACCEPTED` 2.869 s after the measurement
timestamp set immediately before publication. This single local measurement
passed the 5 s threshold for the simulated dispatch path. External provider
latency and provider failure recovery require separate measurements.


### Corrective support visits and device report

Alerting migration V4 backfills the device report onto alerts from the
corresponding telemetry receipts. Chromium verified the actual stored valve
position, original measurement timestamp and safety guidance in alert details.

Support migration V5 links a corrective visit to its completed predecessor.
The new Gateway operation was verified with an isolated fixture ticket:
the owner was denied administrative coordination, the SuperAdmin created
and replayed the same request, the original visit and diagnosis were
preserved, and assigning the previous technician was rejected. A different
accredited technician was assigned automatically. Chromium showed the
corrective reason and original diagnosis on the same ticket.

The rebuilt integrated stack passed 265 REST probes, plus MQTT,
private gRPC, session revocation and the existing coverage checks. The SPA
passed lint and 12 tests.


### Corrective installation and Support queue

Installation migration V3 persists corrective reviews with the prior installer,
prior lifecycle state, original completion timestamp and reason. The administrative
operation rejects owners, stale requests and the original installer. A test with a
provisioned local meter completed the corrective review after a fresh authenticated
MQTT reading. PostgreSQL retained the completed review and exactly one original
InstallationCompleted event. Replaying completion returned the same result.

Support migration V6 stores the reported critical-safety flag and the verified Pro
entitlement at ticket creation. The admin queue orders open critical tickets ahead
of standard Pro and then standard Free. Three real tickets created by seeded Free
and Pro owners verified that ordering; the Free critical case took precedence.
Existing corrective Support suites passed 21 tests, and Installation passed 64
tests against isolated dependencies after adding V3.

The rebuilt integration passed 267 REST probes after the Installation and
Support contract exports were synchronized. The SPA passed lint and 12 tests.
Chromium also verified that the installation form exposes the reason and
alternative installer selection. The Support suite passed 21 tests after V6.

The mobile recovery, sign-in and device-report flows passed in Chromium
158.0.8127.18, Edge 158.0.4370.45, Firefox 159.0 and Playwright WebKit 27.2.
This is a sample of those flows and engines. Native Safari and two stable
versions per browser still require separate evidence.

The SPA proxy now supports HTTPS to the certified ALB hostname. The rebuilt
image passed local HTTP and HTTPS configuration checks. A TLS fixture confirmed
successful forwarding with a trusted matching certificate and rejection when the
upstream hostname did not match. The AWS ALB itself was not deployed or tested.

### Release composition and local measurements

Rendering the integration, SPA and registry manifests together resolves 12
application images from the selected release tag, including the `-payments`
image. Local builds are disabled for those 12 services and the SPA retains the
configured HTTPS upstream.

A fresh Compose project with newly initialized volumes passed demo seeding and
the integrated verification, which inventoried 267 REST operations and
exercised authenticated MQTT, an auditable alert delivery, Support completion,
duplicate rejection, session revocation and account isolation. The seed saves
the notification preference before publishing and waits for the new association
to accommodate ordered readings without future timestamps. This run used
isolated payment fixtures.

The Telemetry PostgreSQL suite passed 105 tests against an isolated database.
Its load case durably wrote ten one-second batches of 500 events from 5,000
simulated device IDs and a one-second burst of 1,000 events. It also checked
the total persisted count and replay deduplication. This measures the durable
inbox boundary. Full sustained traffic through authenticated MQTT, InfluxDB
and Alerting needs a separate load run.

An MQTT-to-SPA sample returned three visible readings in 613 ms, 417 ms and
637 ms. An axe-core 4.10.3 run found zero WCAG 2.0 and 2.1 A/AA violations across
20 sampled public, owner and admin page states. Manual assistive technology
and interaction coverage remain separate checks.
