"""Record REST contract inventory and exercise the integrated services."""
import base64
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from datetime import timedelta
from urllib.parse import urlencode, urlsplit
from seed import GATEWAY, SERVICE, WORKSPACE, call, eventually, fixtures, login, now, stable

SERVICES = {
    "iam": (8080, "/actuator/health", "/v3/api-docs"),
    "installation": (8081, "/actuator/health", "/v3/api-docs"),
    "support": (8082, "/actuator/health", "/v3/api-docs"),
    "billing": (8083, "/actuator/health", "/v3/api-docs"),
    "alerting": (8086, "/actuator/health", "/v3/api-docs"),
    "telemetry": (8085, "/ready", "/v3/api-docs"),
    "monitoring": (8084, "/health", "/v3/api-docs"),
    "message-broker": (8087, "/actuator/health", "/v3/api-docs"),
    "config": (8088, "/actuator/health", None),
    "admin": (8089, "/actuator/health", None),
    "api-gateway": (8000, "/ready", "/v3/api-docs"),
}
OPENAPI_REPOS = {
    "iam": "iam", "installation": "installation-device-management", "support": "support-maintenance",
    "billing": "payments-billing", "alerting": "alerting-notifications", "telemetry": "telemetry-data-ingestion",
    "monitoring": "monitoring-analytics", "message-broker": "message-broker", "api-gateway": "api-gateway",
}
METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
PUBLIC_REJECTIONS = {
    ("POST", "/api/v1/auth/sign-in"): (400,),
    ("POST", "/api/v1/auth/reset-password"): (400,),
    ("POST", "/api/v1/auth/forgot-password"): (400,),
    ("POST", "/api/v1/auth/activate-password"): (400,),
    ("POST", "/api/v1/installations"): (400,),
    ("POST", "/api/v1/checkout/orders"): (400,),
    ("POST", "/api/v1/checkout/orders/{id}/sessions"): (400,),
    ("GET", "/api/v1/checkout/orders/{id}"): (400,),
}


def verify_rest_operations(inventory, broker):
    failures = []
    for operation in inventory:
        service, method, path = (operation[key] for key in ("service", "method", "path"))
        concrete = re.sub(r"\{[^}]+\}", "ea456f05-dd15-47cf-9c8e-b4867d47432c", path)
        if service == "alerting":
            concrete = re.sub(r"\{[^}]+\}", "1", path)
        base = f"http://{service}:{SERVICES[service][0]}"
        if (method, path) in PUBLIC_REJECTIONS:
            expected = PUBLIC_REJECTIONS[(method, path)]
            scenario = "incomplete public request"
        elif path in ("/health", "/ready"):
            expected = (200,)
            scenario = "health response"
        elif operation["requiresAuthentication"]:
            expected = (401,)
            scenario = "anonymous request"
        else:
            raise RuntimeError(f"Missing runtime case for {service} {method} {path}")
        data = b"{}" if method in ("POST", "PUT", "PATCH") else None
        if service == "message-broker" and path == "/api/v1/broker/messages/publish":
            data = json.dumps({field: broker[field] for field in ("topic", "qos", "payload")}).encode()
        request = Request(base + concrete, method=method, data=data,
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=12) as response:
                status = response.status
        except HTTPError as error:
            status = error.code
        documented = str(status) in operation["documentedStatuses"]
        passed = status in expected and documented
        operation["verification"] = {
            "scenario": scenario,
            "expectedStatuses": expected,
            "observedStatus": status,
            "documented": documented,
            "passed": passed,
        }
        if not passed:
            failures.append(f"{service} {method} {path}: got {status}, expected {expected}, documented={documented}")
    Path("/state/rest-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    if failures:
        raise RuntimeError("REST operation probes failed:\n" + "\n".join(failures))
    print(f"PASS runtime probes for all {len(inventory)} REST entries", flush=True)


def get(url, headers=None):
    with urlopen(Request(url, headers=headers or {}), timeout=12) as response:
        return response.read()


def wait_admin(expected):
    credentials = os.environ["SMARTGN_ADMIN_USERNAME"] + ":" + os.environ["SMARTGN_ADMIN_PASSWORD"]
    headers = {"Authorization": "Basic " + base64.b64encode(credentials.encode()).decode(),
               "Accept": "application/json"}
    healthy = set()
    for _ in range(40):
        try:
            rows = json.loads(get("http://admin:8089/instances", headers))
        except (URLError, TimeoutError):
            time.sleep(2)
            continue
        registered_urls = (urlsplit(row["registration"]["serviceUrl"])
                           for row in rows if row["statusInfo"]["status"] == "UP")
        healthy = {url.hostname for url in registered_urls
                   if url.hostname in SERVICES and url.port == SERVICES[url.hostname][0]}
        if expected <= healthy:
            return
        time.sleep(2)
    raise RuntimeError(f"Admin has no UP instance for {sorted(expected - healthy)}")


def openapi_operations(spec):
    return {(path, method): (
                operation.get("security", spec.get("security", [])),
                operation.get("parameters", []),
                operation.get("requestBody", {}),
                {code: response.get("content", {}) for code, response in operation.get("responses", {}).items()},
            )
            for path, operations in spec["paths"].items()
            for method, operation in operations.items() if method in METHODS}


def verify_swagger_ui(service, base, spec):
    ui = "/swagger" if service in ("monitoring", "telemetry") else "/swagger-ui"
    index = get(base + ui + "/index.html").decode()
    assert "SmartGN" in index and "smartgn.css" in index, f"Missing SmartGN theme in {service}"
    theme = (WORKSPACE / "smartgn-api-gateway/src/swagger/smartgn.css").read_bytes()
    assert get(base + ui + "/smartgn.css") == theme, f"Swagger theme drift in {service}"
    assert get(base + ui + "/swagger-ui-bundle.js"), f"Missing Swagger bundle in {service}"
    assert spec.get("openapi", "").startswith("3.1."), f"OpenAPI 3.1 is required for {service}"
    assert spec["info"]["title"] and spec["info"]["description"], f"Missing API overview in {service}"
    assert spec["info"].get("license", {}).get("name") == "MIT", f"Missing MIT license in {service}"
    assert "contact" not in spec["info"], f"Unexpected API contact in {service}"
    sections = {tag["name"]: tag.get("description") for tag in spec.get("tags", [])}
    assert len(sections) == len(spec.get("tags", [])), f"Duplicate Swagger section in {service}"
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if method in METHODS:
                assert operation.get("summary") and operation.get("description"), (
                    f"Missing documentation for {service} {method.upper()} {path}"
                )
                assert operation.get("tags") and all(sections.get(tag) for tag in operation["tags"]), (
                    f"Missing section description for {service} {method.upper()} {path}"
                )


def verify_session_revocation(account, password, session):
    path = "/api/v1/auth/change-password"
    temporary = stable("demo-session-rotation")
    call("GET", "/api/v1/alerts", headers=session)
    call("POST", path, {"currentPassword": password, "newPassword": temporary}, session, expected=(204,))
    try:
        call("GET", "/api/v1/alerts", headers=session, expected=(401,))
    finally:
        new_session, _ = login(account["email"], temporary)
        call("POST", path, {"currentPassword": temporary, "newPassword": password},
             new_session, expected=(204,))
    print("PASS Alerting rejects an IAM session revoked by password rotation", flush=True)


def verify_notification_delivery(owner, other, recipient):
    preferences = call("GET", "/api/v1/notification-preferences", headers=owner)
    assert any(item["active"] and item["channel"] == "EMAIL" and item["recipient"] == recipient
               for item in preferences), "Missing active demo EMAIL preference"

    def delivered():
        notifications = call("GET", "/api/v1/notifications", headers=owner)
        return next((item for item in notifications
                     if item["recipient"] == recipient and item["channel"] == "EMAIL"
                     and item["alertId"] is not None and item["status"] in ("ACCEPTED", "DELIVERED")), None)

    notification = eventually(delivered, "simulated EMAIL delivery from the telemetry alert")
    path = f"/api/v1/notifications/{notification['id']}"
    assert call("GET", path, headers=owner)["id"] == notification["id"]
    assert call("GET", path + "/attempts", headers=owner), "Missing simulated delivery attempt"
    call("GET", path, headers=other, expected=(403,))
    alert_path = f"/api/v1/alerts/{notification['alertId']}"
    assert call("GET", alert_path, headers=owner)["id"] == notification["alertId"]
    assert any(item["id"] == notification["id"]
               for item in call("GET", alert_path + "/notifications", headers=owner))
    print("PASS telemetry alert dispatched a simulated EMAIL with an auditable delivery attempt", flush=True)



def verify_support_billing(records, state, owner):
    admin, _ = login("admin@smartgn.test", os.environ["BOOTSTRAP_SUPERADMIN_PASSWORD"])
    ticket_id = state["demo-ticket-primary"]["ticketId"]
    visit_id = state["demo-support-visit"]["visitId"]
    visit_path = f"/api/v1/support/visits/{visit_id}"
    visit = next(item for item in call("GET", f"/api/v1/support/tickets/{ticket_id}/visits",
                                      headers=owner) if item["visitId"] == visit_id)
    if visit["status"] == "REQUESTED":
        fixture = records["demo-support-technician"]
        technician = next((item for item in call("GET", "/api/v1/support/technicians", headers=admin)
                           if item["accreditationCode"] == fixture["accreditationCode"]), None)
        if not technician:
            fields = ("fullName", "accreditationCode", "specialty", "email", "phone")
            technician = call("POST", "/api/v1/support/technicians",
                              {field: fixture[field] for field in fields}, admin, expected=(201,))
        call("POST", visit_path + "/assign", {"technicianId": technician["technicianId"],
                                             "reason": "Local demo acceptance"}, admin, expected=(201,))
        visit["status"] = "ASSIGNED"
    if visit["status"] == "ASSIGNED":
        call("POST", visit_path + "/schedule", {
            "requestedWindowStart": visit["requestedWindowStart"],
            "requestedWindowEnd": visit["requestedWindowEnd"],
        }, admin)
        visit["status"] = "SCHEDULED"
    if visit["status"] == "SCHEDULED":
        call("POST", visit_path + "/start", {}, admin)
        visit["status"] = "IN_PROGRESS"
    diagnosis = {"performedWork": "Read demo meter", "diagnosis": "Fixture reading verified", "finalCost": 42.50}
    if visit["status"] == "IN_PROGRESS":
        call("POST", visit_path + "/complete", diagnosis, admin, expected=(201,))
    call("POST", visit_path + "/complete", diagnosis, admin, expected=(409,))
    statement_path = f"/api/v1/technical-statements/{visit_id}"
    statement = eventually(lambda: (item if (item := call("GET", statement_path, headers=owner,
                                                          expected=(200, 404))).get("covered")
                                    else None), "Support completion delivered to Billing")
    assert float(statement["balance"]) == 0
    print("PASS Support visit completion reached Billing and duplicate completion was rejected", flush=True)



def main():
    records = fixtures()
    inventory = []
    for service, (port, health, spec_path) in SERVICES.items():
        base = f"http://{service}:{port}"
        get(base + health)
        print(f"PASS {service} health", flush=True)
        if not spec_path:
            continue
        try:
            spec = json.loads(get(base + spec_path))
        except HTTPError as exc:
            if exc.code != 404 or service not in ("telemetry", "monitoring"):
                raise
            spec = json.loads(get(base + "/openapi/v1.json"))
        repo = WORKSPACE / f"smartgn-{OPENAPI_REPOS[service]}"
        exported = json.loads((repo / "docs/openapi.json").read_text(encoding="utf-8-sig"))
        verify_swagger_ui(service, base, spec)
        assert openapi_operations(spec) == openapi_operations(exported), f"OpenAPI drift in {service}"
        for section in ("schemas", "securitySchemes"):
            assert spec.get("components", {}).get(section, {}) == exported.get("components", {}).get(section, {}), (
                f"OpenAPI {section} drift in {service}"
            )
        print(f"PASS {service} Swagger theme and OpenAPI documentation", flush=True)
        for path, operations in spec["paths"].items():
            for method, operation in operations.items():
                if method not in METHODS:
                    continue
                if service == "api-gateway" and path.startswith(("/internal/", "/actuator/")):
                    raise RuntimeError(f"Private route in public catalog: {path}")
                inventory.append({
                    "service": service, "method": method.upper(), "path": path,
                    "documentedStatuses": list(operation.get("responses", {})),
                    "requiresAuthentication": bool(operation.get("security", spec.get("security", []))),
                    "runtimeContract": "matched exported operation, security and request/response schemas",
                })
    verify_rest_operations(inventory, records["demo-broker-event"])
    config = records["demo-config-profile"]
    for application in sorted(config["applications"]):
        environment = json.loads(get(f"http://config:8088/{application}/{config['profile']}"))
        assert environment["propertySources"], f"No central properties for {application}/local"
    print("PASS central Config sources for 10 consumers", flush=True)
    wait_admin(set(records["demo-admin-instances"]["services"]))
    print("PASS Admin shows 11 UP services", flush=True)
    origin = os.environ.get("SMOKE_CORS_ORIGIN") or records["demo-gateway-spa"]["origin"]
    preflight = Request(GATEWAY + "/api/v1/analytics/live", method="OPTIONS",
                        headers={"Origin": origin, "Access-Control-Request-Method": "GET",
                                 "Access-Control-Request-Headers": "authorization"})
    with urlopen(preflight, timeout=5) as response:
        assert response.status == 204
        assert response.headers["Access-Control-Allow-Origin"] == origin
    print("PASS SPA CORS preflight", flush=True)
    broker = records["demo-broker-event"]
    payload = {field: broker[field] for field in ("topic", "qos", "payload")}
    payload["eventId"] = stable(broker["alias"])
    base = "http://message-broker:8087"
    path = "/api/v1/broker/messages"
    call("POST", path + "/publish", payload, base=base, expected=(401,))
    history = call("GET", path, headers=SERVICE, base=base)
    if not any(item["eventId"] == payload["eventId"] for item in history):
        ack = call("POST", path + "/publish", payload, headers=SERVICE, base=base, expected=(202,))
        assert ack["eventId"] == payload["eventId"] and ack["qos"] == 1
    print("PASS authenticated QoS 1 broker publication", flush=True)
    for path in ("/api/v1/alerts", "/api/v1/notifications", "/api/v1/analytics/live"):
        call("GET", path, expected=(401,))
        print(f"PASS unauthenticated {path} rejected", flush=True)
    state = json.loads(Path("/state/seed-state.json").read_text())
    point = state["demo-supply-point-primary"]
    password = os.environ["DEMO_USER_PASSWORD"]
    owner, _ = login(records["demo-account-pro"]["email"], password)
    other, _ = login(records["demo-account-other"]["email"], password)
    live = f"/api/v1/analytics/live?meterId={point}"
    reading = call("GET", live, headers=owner)
    assert reading.get("freshness") in ("current", "delayed")
    call("GET", live, headers=other, expected=(403,))
    assert call("GET", "/api/v1/subscriptions/me", headers=owner)["proActive"]
    consumption = call("GET", f"/api/v1/analytics/consumption?meterIds={point}", headers=owner)
    assert consumption, "Monitoring consumption did not return a result"
    end = now()
    report_query = urlencode({"meterIds": point, "from": (end - timedelta(days=records["demo-analytics-window"]["reportDays"])).isoformat(),
                              "to": end.isoformat()})
    report = call("GET", "/api/v1/analytics/reports?" + report_query, headers=owner)
    assert report, "Billing gRPC and Monitoring report did not return a result"
    assert call("GET", "/api/v1/alerts", headers=owner)
    assert call("GET", "/api/v1/support/tickets", headers=owner)
    verify_notification_delivery(owner, other, records["demo-account-pro"]["email"])
    verify_support_billing(records, state, owner)
    verify_session_revocation(records["demo-account-other"], password, other)
    print(f"PASS seeded analytics, account isolation, Pro and Alerting; {len(inventory)} REST operations inventoried")


if __name__ == "__main__":
    main()
