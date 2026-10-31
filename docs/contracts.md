# HTTP contracts

The Gateway public contract is available at `/v3/api-docs` and in `openapi.json`. Schemas and tags are namespaced by owning service. Runtime routing accepts the documented method/path combinations; unknown operations and internal paths return 404.

| Owner | Routed resource prefixes under /api/v1 |
|---|---|
| IAM | auth, profiles, subusers |
| Installation | properties, supply-points, installers, installations, devices, meters, operations/outbox |
| Support | support |
| Billing | checkout, payment-methods, subscriptions, payments, billing-documents, technical-statements |

Only documented sign-in, activation/recovery, provisional installation creation and checkout operations omit a user JWT. Checkout still requires its private secret and idempotency headers. Protected operations validate the HMAC signature (HS256, HS384 or HS512), issuer, audience, expiry, issued-at, account UUID, matching subject/accountId, session version and USER/SUPERADMIN role. Each service checks the current session and resource permissions; a signature alone does not authorize a revoked session.

CORS is applied at the Gateway using the configured exact origin list. It permits Authorization, Content-Type, X-Correlation-Id, Idempotency-Key and X-Checkout-Secret and exposes X-Correlation-Id, X-Total-Count, Content-Disposition, Location and Retry-After. After validating browser origin, the proxy removes Origin so that downstream standalone CORS policies do not override the perimeter policy. Client-asserted identity headers are removed; authenticated ownership is derived by each service from IAM.

Upstream bodies, methods, paths, query strings and statuses are preserved, including multipart photographs and binary fiscal artifacts. Gateway-generated errors use application/problem+json with status, detail and correlationId; legacy error/message properties remain available. Service error responses remain owned by their service. Rate limiting returns 429 with retry metadata. Limits are per process/IP and use the actual socket peer; arbitrary forwarded IP headers are not trusted.

GET /health reports Gateway liveness; GET /ready reports four dependency states with a bounded deadline and no private URLs. GET /v3/api-docs and /swagger-ui/index.html expose the public contract. Gateway-local health/documentation routes do not expose internal backend endpoints.
