# Service overview

SmartGN API Gateway provides the public HTTP entry point for IAM, Installation & Device Management, Support & Maintenance and Payments & Billing. It uses Node.js 22, Express, HMAC JWT validation, exact CORS origins, rate limiting, request correlation, bounded proxies and Swagger UI.

It does not own accounts, properties, tickets, visits, payments or databases. IAM defines USER and SUPERADMIN accounts and current sessions; technicians and installers remain external personnel. Each owning service validates authorization independently. The Gateway does not route broker traffic or internal REST/gRPC contracts.

The local integrated application ports are Gateway 8000, IAM 18080, Installation 18081, Support 8082 and Billing 28083. Service-to-service ports remain IAM 8080, Installation 8081, Support 8082 and Billing 8083. Health and public API documentation are available directly on the Gateway.
