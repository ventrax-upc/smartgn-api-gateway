# Architecture

The Gateway is a stateless Express adapter at the HTTP perimeter. It owns no business data and does not introduce domain aggregates or database migrations. Its route inventory contains public operations exported by six owning services. No internal REST contract, service credential, broker topic or private gRPC interface is routed.

Requests pass through correlation, path validation, origin checks, CORS, rate limits, operation matching and JWT validation before the service proxy. Bodies are streamed without a JSON or multipart parser. Alerting additionally requires IAM session introspection before trusted account and role headers are forwarded. Monitoring verifies the JWT and performs per-meter authorization itself. SUPERADMIN installer administration is also checked at the perimeter.

Liveness is independent of dependency availability. Readiness performs bounded health requests to the six routed services. Upstream failures return controlled 502, 503 or 504 responses. The Gateway does not retry mutations automatically; caller idempotency headers and service durable processing remain authoritative.

The integrated Docker composition has eleven SmartGN services, six isolated PostgreSQL databases on one local PostgreSQL server, Redis, InfluxDB and EMQX. Gateway-to-service traffic uses private Docker DNS. Only Gateway and Admin have host bindings. The composition uses local HTTP and per-process rate-limit state.
