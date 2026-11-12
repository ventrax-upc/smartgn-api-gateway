# Service overview

SmartGN API Gateway provides the public HTTP entry point for IAM, Installation & Device Management, Support & Maintenance and Payments & Billing. It uses Node.js 22, Express, HMAC JWT validation, exact CORS origins, rate limiting, request correlation, bounded proxies and Swagger UI.

It does not own accounts, properties, tickets, visits, payments or databases. IAM defines USER and SUPERADMIN accounts and current sessions; technicians and installers remain external personnel. Each owning service validates authorization independently. The Gateway does not route broker traffic or internal REST/gRPC contracts.

The [integrated port table](integrated-local.md#access) lists the listening ports used on localhost and inside Docker. The Gateway exposes liveness, readiness and public Swagger on port 8000.
