# SmartGN API Gateway

Single entry point for the SmartGN web clients (Angular SPA and Landing Page). Built with Node.js and Express.

## Responsibilities (AD-12)

- Route requests by prefix to the owning microservice, without altering path, method, status code or body.
- Validate the JWT issued by IAM on protected routes (HS256, issuer, audience, expiry). Invalid or missing token returns `401`.
- Restrict `/api/v1/installers/**` to `SUPERADMIN` (`403` otherwise).
- CORS, rate limiting (stricter on sign-in), correlation id.
- Controlled errors: `503` (service down), `504` (timeout), `502` (bad gateway), without leaking internals.
- Never publish `/internal/**`.

Resource-level authorization (ownership, subuser grants) remains in each microservice. The Gateway is stateless and has no database. IoT telemetry (MQTT) does not go through the Gateway.

## Route table

| Service | Prefixes |
|---|---|
| IAM | `/api/v1/auth`, `/profiles`, `/subusers` |
| Installation | `/api/v1/properties`, `/supplypoints`, `/installers`, `/installations`, `/devices`, `/meters` |
| Support | `/api/v1/support` |
| Billing | `/api/v1/checkout`, `/payment-methods`, `/subscriptions`, `/billing-documents` (also `/billingdocuments`), `/payments` |

Public routes (no JWT): `POST /api/v1/auth/{sign-in,activate-password,forgot-password,reset-password}`, `POST /api/v1/installations`, `/api/v1/checkout/**`.

To add a route or change a public rule, edit `src/routes/route-table.js` and `src/middlewares/jwt-validator.js`.

## Run locally

```bash
npm install
cp .env.example .env     # set JWT_SECRET = the same secret used by IAM
npm run dev              # http://localhost:8000
```

Start the services first (IAM 18080, Installation 18081, Support 8082, Billing 28083 in the integrated setup).

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

The compose file points the services to `host.docker.internal`.

## Environment variables

See `.env.example`. `JWT_SECRET` is required, must match IAM, and must never be committed.

## Tests

```bash
npm test
```

Covers valid routing, `401` for missing/expired/forged tokens, backend `403` passthrough, SUPERADMIN restriction, public routes, `503`/`504`, `/internal` blocking, CORS and rate limiting.

## Docs

OpenAPI summary in `docs/openapi.yaml`. Health check: `GET /health`.
