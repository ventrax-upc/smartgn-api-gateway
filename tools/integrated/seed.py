"""Load reproducible demo records using the integrated network and local adapters."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid5

WORKSPACE = Path("/workspace")
GATEWAY = "http://api-gateway:8000"
BILLING = "http://billing:8083"
DELIVERY = "http://delivery:8091"
SERVICE = {"Authorization": "Bearer " + os.environ["INTERNAL_SERVICE_TOKEN"]}
FIXTURE = {"Authorization": "Bearer " + os.environ["FIXTURE_ADMIN_TOKEN"]}
STATE_FILE = Path("/state/seed-state.json")
REPOS = (
    "admin", "alerting-notifications", "api-gateway", "config", "iam",
    "installation-device-management", "message-broker", "monitoring-analytics",
    "payments-billing", "support-maintenance", "telemetry-data-ingestion",
)
sys.path.insert(0, str(WORKSPACE / "smartgn-installation-device-management/tools"))
from mqtt_client import Mqtt5


def fixtures():
    catalog = {}
    for repo in REPOS:
        path = WORKSPACE / f"smartgn-{repo}" / "fixtures/db.json"
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
        if doc["version"] != 1 or not isinstance(doc["service"], str) or not isinstance(doc["records"], list):
            raise ValueError(f"Invalid fixture manifest: {path}")
        for record in doc["records"]:
            alias = record["alias"]
            if alias in catalog:
                raise ValueError(f"Duplicate fixture alias {alias}")
            catalog[alias] = record
    return catalog


def call(method, path, data=None, headers=None, base=GATEWAY, expected=(200,)):
    request = Request(base + path, method=method, data=None if data is None else json.dumps(data).encode(),
                      headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(request, timeout=15) as response:
            status, body = response.status, response.read()
    except HTTPError as error:
        status, body = error.code, error.read()
    if status not in expected:
        raise RuntimeError(f"{method} {path.split('?')[0]} returned {status}, expected {expected}")
    return json.loads(body) if body else None


def eventually(check, name):
    for _ in range(75):
        result = check()
        if result:
            return result
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {name}")


def stable(label):
    return str(uuid5(NAMESPACE_URL, "smartgn-dev/fixture/v1/" + label))


def now():
    return datetime.now(timezone.utc)


def checkpoint(state, key, create):
    if key not in state:
        state[key] = create()
        temp = STATE_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        temp.replace(STATE_FILE)
    return state[key]


def login(email, password, base="http://iam:8080"):
    result = call("POST", "/api/v1/auth/sign-in", {"email": email, "password": password}, base=base)
    return {"Authorization": "Bearer " + result["token"]}, result["id"]


def account(record, state, amount):
    alias, email = record["alias"], record["email"]
    installation = checkpoint(state, alias + "/installation", lambda: call(
        "POST", "/api/v1/installations",
        {"contact": {"name": record["firstName"] + " " + record["lastName"],
                     "email": email, "phone": "999999999"}, "address": "Lima demo"},
        expected=(201,))["id"])
    order = call("POST", "/api/v1/checkout/orders", {
        "installationId": installation, "email": email, "firstName": record["firstName"],
        "lastName": record["lastName"],
    }, {"Idempotency-Key": stable(alias + "/purchase"), "X-Checkout-Secret": stable(alias + "/secret")},
        expected=(201,))
    reference = "demo-" + stable(alias + "/provider")
    call("POST", "/internal/v1/local-provider/results", {
        "reference": reference, "orderId": order["id"], "status": "CONFIRMED", "amount": amount,
    }, SERVICE, BILLING)
    call("POST", "/internal/v1/payments/confirmations", {
        "orderId": order["id"], "providerReference": reference,
    }, SERVICE, BILLING)
    password = os.environ["DEMO_USER_PASSWORD"]
    try:
        return (*login(email, password), installation)
    except RuntimeError as exc:
        if "returned 401" not in str(exc) and "returned 403" not in str(exc):
            raise
    messages = eventually(lambda: call("GET", "/fixtures/messages?" + urlencode({"email": email}),
                                       headers=FIXTURE, base=DELIVERY), email + " activation")
    token = next(message["token"] for message in reversed(messages) if message["purpose"] == "ACTIVATION")
    call("POST", "/api/v1/auth/activate-password", {"activationToken": token, "newPassword": password},
         expected=(204,))
    return (*login(email, password), installation)


def setup_meter(records, state, admin, owner, installation):
    prop_fixture = records["demo-property-primary"]
    point_fixture = records["demo-supply-point-primary"]
    meter = records["demo-meter-primary"]
    prop = checkpoint(state, prop_fixture["alias"], lambda: call(
        "POST", "/api/v1/properties",
        {field: prop_fixture[field] for field in ("name", "address", "propertyType")}, owner,
        expected=(201,))["id"])
    point = checkpoint(state, point_fixture["alias"], lambda: call(
        "POST", f"/api/v1/properties/{prop}/supply-points",
        {field: point_fixture[field] for field in ("serialNumber", "locationName")}, owner,
        expected=(201,))["id"])
    device_id = meter["deviceId"]
    path = "/api/v1/installations/" + installation

    def current():
        return call("GET", path, headers=owner)["installation"]

    def device():
        return next((row["device"] for row in call("GET", "/api/v1/devices?limit=100", headers=admin)
                     if row["device"]["id"] == device_id), None)

    installer = checkpoint(state, "demo-installer", lambda: call(
        "POST", "/api/v1/installers", {
            "firstName": "SmartGN", "lastName": "Demo", "identification": "90000521",
            "phone": "999999999", "email": "installer@smartgn.test",
            "accreditationCode": "LOCAL-DEMO", "available": True,
        }, admin, expected=(201,))["id"])
    if not device():
        if current()["status"] == "PENDING":
            call("PUT", path + "/target", {"propertyId": prop, "supplyPointId": point,
                                          "version": current()["version"]}, owner)
        assigned = eventually(lambda: (item if (item := current())["status"] in ("ASSIGNED", "IN_PROGRESS")
                                         else None), "installation assignment")
        if assigned["status"] == "ASSIGNED":
            if assigned.get("installerId") != installer:
                call("PATCH", path + "/reassign", {"installerId": installer, "version": assigned["version"],
                                                  "reason": "Local demo assignment"}, admin)
            start = now() + timedelta(hours=1)
            call("PUT", path + "/appointment", {"from": start.isoformat(),
                 "to": (start + timedelta(hours=1)).isoformat(), "version": current()["version"]}, admin)
            call("PATCH", path + "/status", {"status": "IN_PROGRESS"}, admin)
        checkpoint(state, meter["alias"], lambda: call("POST", "/api/v1/devices", {
            "deviceId": device_id, "installationId": installation, "supplyPointId": point,
            "installerId": installer, "serialNumber": "SMARTGN-DEMO-METER", "location": "Kitchen",
            "installedAt": (now() - timedelta(days=3)).isoformat(),
        }, admin, expected=(202,)))
    if current()["status"] == "COMPLETED":
        return point
    credentials = state[meter["alias"]]
    active = eventually(lambda: (item if (item := device()) and item["status"] == "ACTIVE" else None),
                        "device provisioning")
    client = Mqtt5("emqx", 1883, credentials["mqttUsername"], credentials["oneTimeCredential"])
    try:
        if client.reason != 0:
            raise RuntimeError("Demo device MQTT authentication failed")
        associations = call("GET", f"/api/v1/devices/{device_id}/associations", headers=admin)
        association = next(item for item in associations if item["version"] == active["associationVersion"])
        valid_from = datetime.fromisoformat(association["validFrom"])
        for reading in reversed(meter["readings"]):
            timestamp = now() + timedelta(days=reading.get("measuredAtOffsetDays", 0),
                                          minutes=reading.get("measuredAtOffsetMinutes", 0))
            # Fresh stores cannot contain readings before the first confirmed association.
            timestamp = max(timestamp, valid_from + timedelta(seconds=3 - reading["sequenceNumber"]))
            payload = {key: reading[key] for key in ("eventId", "sequenceNumber", "metrics")}
            payload.update(schemaVersion=1, deviceId=device_id, associationVersion=active["associationVersion"],
                           measuredAt=timestamp.isoformat())
            if client.publish(f"smartgn/devices/{device_id}/telemetry", payload) >= 128:
                raise RuntimeError("Demo device publish failed")
        heartbeat = dict(payload, eventId=f"demo-contact-{int(now().timestamp())}",
                         sequenceNumber=max(reading["sequenceNumber"] for reading in meter["readings"]) + 1,
                         measuredAt=now().isoformat(), metrics=meter["readings"][-1]["metrics"])
        if client.publish(f"smartgn/devices/{device_id}/telemetry", heartbeat) >= 128:
            raise RuntimeError("Demo device heartbeat failed")
    finally:
        client.close()
    eventually(lambda: call("GET", "/api/v1/analytics/live?" + urlencode({"meterId": point}),
                            headers=owner).get("freshness") in ("current", "delayed"), "real telemetry")
    def complete():
        result = call("POST", path + "/complete", {}, admin, expected=(200, 409))
        if result.get("status") == "COMPLETED":
            return True
        if result.get("detail") == "Current device connectivity is not confirmed":
            return False
        raise RuntimeError(f"Could not complete the demo installation: {result.get('code')}")
    eventually(complete, "device connectivity and installation completion")
    return point


def ensure_alert_notification(records, state, admin, owner, account_id):
    preference = records["demo-notification-preference-pro"]
    contact = records[preference["accountAlias"]]
    saved = call("PUT", "/api/v1/notification-preferences", {
        "accountId": account_id,
        "notificationType": preference["notificationType"],
        "channel": preference["channel"],
        "recipient": contact["email"],
        "active": preference["active"],
    }, owner)
    preferences = call("GET", "/api/v1/notification-preferences", headers=owner)
    if (saved.get("accountId") != account_id or not saved.get("active") or
            not any(item.get("notificationType") == preference["notificationType"] and
                    item.get("channel") == preference["channel"] and
                    item.get("recipient") == contact["email"] and item.get("active")
                    for item in preferences)):
        raise RuntimeError("Demo alert notification preference was not saved")

    meter = records["demo-meter-primary"]
    device_id = meter["deviceId"]
    probe = meter["notificationProbe"]

    def current_probe():
        alerts = call("GET", "/api/v1/alerts?size=100", headers=owner)
        alert = next((item for item in alerts if item.get("eventId") == probe["eventId"]), None)
        if not alert:
            return None
        notifications = call("GET", f"/api/v1/alerts/{alert['id']}/notifications", headers=owner)
        notification = next((item for item in notifications
                             if item.get("recipient") == contact["email"] and
                             item.get("channel") == preference["channel"]), None)
        return alert, notification

    existing = current_probe()
    if existing:
        _, prior_notification = existing
        if prior_notification is None:
            raise RuntimeError("Demo alert probe already exists without its notification")
        def accepted_existing_notification():
            current = current_probe()
            if current and current[1] and current[1].get("status") == "ACCEPTED":
                return current
            return None

        alert, notification = eventually(
            accepted_existing_notification, "existing simulated demo alert notification delivery")
        verify_listed_notification(owner, alert["id"], notification, contact["email"],
                                   preference["channel"])
        print(f"Demo alert notification {notification['id']} was already accepted by the local delivery adapter.")
        return

    device = eventually(lambda: next((row["device"] for row in
        call("GET", "/api/v1/devices?limit=100", headers=admin)
        if row["device"]["id"] == device_id and row["device"]["status"] == "ACTIVE"), None),
        "active demo device for notification probe")
    credentials = state[meter["alias"]]
    payload = {
        "schemaVersion": 1,
        "deviceId": device_id,
        "associationVersion": device["associationVersion"],
        "eventId": probe["eventId"],
        "sequenceNumber": probe["sequenceNumber"],
        "measuredAt": now().isoformat(),
        "metrics": probe["metrics"],
    }
    client = Mqtt5("emqx", 1883, credentials["mqttUsername"], credentials["oneTimeCredential"])
    try:
        if client.reason != 0:
            raise RuntimeError("Demo device MQTT authentication failed during notification probe")
        if client.publish(f"smartgn/devices/{device_id}/telemetry", payload) >= 128:
            raise RuntimeError("Demo notification telemetry publish failed")
    finally:
        client.close()

    def delivered_notification():
        current = current_probe()
        if not current:
            return None
        alert, notification = current
        if not notification or notification.get("status") != "ACCEPTED":
            return None
        return alert, notification

    alert, notification = eventually(delivered_notification, "simulated demo alert notification delivery")
    verify_listed_notification(owner, alert["id"], notification, contact["email"], preference["channel"])
    print(f"Demo alert notification {notification['id']} was accepted by the local delivery adapter.")


def verify_listed_notification(owner, alert_id, notification, recipient, channel):
    listed = call("GET", "/api/v1/notifications?size=100", headers=owner)
    if not any(item.get("id") == notification.get("id") and item.get("alertId") == alert_id and
               item.get("recipient") == recipient and item.get("channel") == channel and
               item.get("status") == "ACCEPTED" for item in listed):
        raise RuntimeError("Accepted demo alert notification is missing from GET /api/v1/notifications")


def main():
    records = fixtures()
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    admin, _ = login("admin@smartgn.test", os.environ["BOOTSTRAP_SUPERADMIN_PASSWORD"])
    plan = records["demo-plan-pro"]
    for alias in ("demo-account-free", "demo-account-other"):
        account(records[alias], state, plan["amount"])
    owner, account_id, installation = account(records["demo-account-pro"], state, plan["amount"])
    rule = records["demo-rule-low-pressure"]
    checkpoint(state, rule["alias"], lambda: call("POST", "/api/v1/alert-rules", {
        field: rule[field] for field in ("name", "metric", "operator", "threshold", "severity", "description", "active")
    }, admin, expected=(201, 409)))
    point = setup_meter(records, state, admin, owner, installation)
    ensure_alert_notification(records, state, admin, owner, account_id)
    ticket = records["demo-ticket-primary"]
    created_ticket = checkpoint(state, ticket["alias"], lambda: call("POST", "/api/v1/support/tickets", {
        "principalAccountId": account_id, "meterId": point, "subject": ticket["subject"],
        "description": ticket["description"],
    }, owner, expected=(201,)))
    eventually(lambda: call("GET", "/api/v1/subscriptions/me", headers=owner).get("installationCompleted"),
               "Billing completion")
    checkpoint(state, "demo-support-visit", lambda: call(
        "POST", f"/api/v1/support/tickets/{created_ticket['ticketId']}/visits", {
            "requestedWindowStart": (now() + timedelta(days=1)).isoformat(),
            "requestedWindowEnd": (now() + timedelta(days=1, hours=2)).isoformat(),
        }, owner, expected=(201,)))
    card_token = "test_" + stable("demo-card")
    call("POST", "/internal/v1/local-provider/cards", {
        "accountId": account_id, "providerToken": card_token, "brand": plan["brand"],
        "lastFour": plan["lastFour"], "recurringAuthorized": True, "nextStatus": "CONFIRMED",
    }, SERVICE, BILLING)
    card = checkpoint(state, "demo-card", lambda: call(
        "POST", "/api/v1/payment-methods", {"providerToken": card_token}, owner)["id"])
    if not call("GET", "/api/v1/subscriptions/me", headers=owner).get("proActive"):
        call("POST", "/api/v1/subscriptions/pro", {"paymentMethodId": card, "autoRenew": False},
             {**owner, "Idempotency-Key": stable("demo-plan-pro")})
    eventually(lambda: call("GET", "/api/v1/subscriptions/me", headers=owner).get("proActive"), "Pro plan")
    print("Demo users, meter, real telemetry and Pro entitlement are ready.")


if __name__ == "__main__":
    main()
