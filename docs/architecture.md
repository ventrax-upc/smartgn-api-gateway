# Architecture

The Gateway is a stateless Express adapter at the HTTP perimeter. It owns no business data and does not introduce domain aggregates or database migrations. Its route inventory contains only public operations exported by the four owning services. No internal REST contract, service credential, broker topic or private gRPC interface is routed.

Requests pass through correlation, path validation, origin checks, CORS, rate limits, operation matching and JWT validation before the service proxy. Bodies are streamed without a JSON or multipart parser. Owning services independently enforce active sessions, account ownership, role restrictions and delegated meter functions. SUPERADMIN installer administration is also checked at the perimeter.

Liveness is independent of dependency availability. Readiness performs bounded health requests to the four services. Upstream failures return controlled 502, 503 or 504 responses. The Gateway does not retry mutations automatically; caller idempotency headers and service durable processing remain authoritative.

The integrated Docker composition has five application services and four independent PostgreSQL databases, plus authenticated financial-event and device brokers and explicitly labeled delivery/Telemetry fixtures. Gateway-to-service traffic uses private Docker DNS. Local host bindings use loopback. The composition uses local HTTP and per-process rate-limit state.
