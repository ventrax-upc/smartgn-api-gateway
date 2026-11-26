"""Spool and replay a seeded device's readings from SQLite in the local test stack."""
import argparse
import json
import os
import sqlite3
from datetime import timedelta
from urllib.parse import urlencode
from uuid import UUID, uuid4

import seed
from seed import BILLING, DELIVERY, FIXTURE, GATEWAY, SERVICE, Mqtt5, STATE_FILE, call, eventually, fixtures, login, now


def prepare_fixture(batch, path, session_base):
    # Each run uses a new account and meter, isolated from the demo seed checkpoint.
    seed.STATE_FILE = path
    records = fixtures()
    device = records["demo-meter-primary"]
    device["deviceId"] = str(UUID(batch))
    records["demo-supply-point-primary"]["serialNumber"] = "SP-" + batch[:12]
    email = f"sprint3-{batch[:12]}@smartgn.test"
    origin = {"Origin": "http://localhost:5500"}

    def message(purpose):
        return eventually(
            lambda: next((item for item in call(
                "GET", "/fixtures/messages?" + urlencode({"email": email}),
                headers=FIXTURE, base=DELIVERY) if item["purpose"] == purpose), None),
            purpose,
        )

    challenge = call("POST", "/api/v1/installations/email-verifications", {"email": email},
                     origin, expected=(202,))
    proof = call("POST", "/api/v1/installations/email-verifications/confirm", {
        "challengeId": challenge["challengeId"], "code": message("CHECKOUT_EMAIL")["code"],
    }, origin)
    installation = call("POST", "/api/v1/installations/verified", {
        **proof, "contact": {"name": "Sprint Three", "email": email, "phone": "999999999"},
        "address": "Lima fixture",
    }, origin, expected=(201,))["id"]
    checkout = {**origin, "Idempotency-Key": str(uuid4()), "X-Checkout-Secret": uuid4().hex + uuid4().hex}
    order = call("POST", "/api/v1/checkout/orders", {
        "installationId": installation, "email": email, "firstName": "Sprint", "lastName": "Three",
    }, checkout, expected=(201,))
    order_path = f"/api/v1/checkout/orders/{order['id']}"
    session_headers = checkout if session_base == GATEWAY else {
        key: value for key, value in checkout.items() if key != "Origin"
    }
    session = call("POST", order_path + "/sessions", headers=session_headers, base=session_base)
    assert session["testMode"] and session["provider"] == "LOCAL_TEST_DOUBLE"
    assert call("GET", order_path, headers=checkout)["status"] == "PENDING"
    reference = "sprint3-" + batch
    call("POST", "/internal/v1/local-provider/results", {
        "reference": reference, "orderId": order["id"], "status": "CONFIRMED", "amount": order["amount"],
    }, SERVICE, BILLING)
    confirmation = {"orderId": order["id"], "providerReference": reference}
    call("POST", "/internal/v1/payments/confirmations", confirmation, SERVICE, BILLING)
    call("POST", "/internal/v1/payments/confirmations", confirmation, SERVICE, BILLING)
    assert call("GET", order_path, headers=checkout)["status"] == "CONFIRMED"
    password = os.environ["DEMO_USER_PASSWORD"]
    call("POST", "/api/v1/auth/activate-password", {
        "activationToken": message("ACTIVATION")["token"], "newPassword": password,
    }, origin, expected=(204,))
    owner, account = login(email, password, GATEWAY)

    def receipt():
        orders = call("GET", "/api/v1/payments/history?reason=INITIAL", headers=owner)
        matches = [item for item in orders if item["id"] == order["id"]]
        return matches[0]["documents"] if matches else None

    documents = eventually(receipt, "initial billing document")
    assert len(documents) == 1
    assert documents[0]["test_mode"]
    print("PASS verified checkout, idempotent payment, activation, sign-in and one local billing document")
    admin, _ = login("admin@smartgn.test", os.environ["BOOTSTRAP_SUPERADMIN_PASSWORD"])
    installer = call("POST", "/api/v1/installers", {
        "firstName": "Sprint", "lastName": "Fixture",
        "identification": str(10000000 + int(batch[:12], 16) % 90000000),
        "phone": "999999999", "email": f"installer-{batch[:12]}@smartgn.test",
        "accreditationCode": "LOCAL-" + batch[:12], "available": True,
    }, admin, expected=(201,))["id"]
    state = {"demo-installer": installer}
    point = seed.setup_meter(records, state, admin, owner, installation, device_serial="METER-" + batch[:12])
    active = next(item["device"] for item in call("GET", "/api/v1/devices?limit=100", headers=admin)
                  if item["device"]["id"] == device["deviceId"])
    state["device"] = device["deviceId"]
    state["version"] = active["associationVersion"]
    state["point"] = point
    state["email"] = email
    state["account"] = account
    path.write_text(json.dumps(state), encoding="utf-8")
    print("PASS fresh installation completed and real MQTT meter provisioned")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "spool", "send", "repeat"])
    parser.add_argument("batch", type=lambda value: UUID(value).hex)
    parser.add_argument("--count", type=int, default=360, choices=range(1, 361), metavar="1-360")
    parser.add_argument("--session-base", default=GATEWAY)
    args = parser.parse_args()
    path = STATE_FILE.with_name("telemetry-" + args.batch + ".json")
    if args.mode == "prepare":
        prepare_fixture(args.batch, path, args.session_base)
        return

    state = json.loads(path.read_text(encoding="utf-8"))
    device = state["device"]
    credentials = state["demo-meter-primary"]
    with sqlite3.connect(STATE_FILE.with_name("telemetry-" + args.batch + ".sqlite")) as spool:
        spool.execute("CREATE TABLE IF NOT EXISTS reading (sequence INTEGER PRIMARY KEY, payload TEXT, sent INTEGER DEFAULT 0)")
        if args.mode == "spool":
            # Model 60 minutes at one sample every 10 seconds without wall-clock waiting.
            timestamp = now() - timedelta(hours=1)
            for sequence in range(args.count):
                # The first two events deliberately share a timestamp.
                measured_at = timestamp + timedelta(seconds=max(0, sequence - 1) * 10)
                event = {
                    "schemaVersion": 1, "deviceId": device, "associationVersion": state["version"],
                    "eventId": f"{args.batch}-{sequence}", "sequenceNumber": sequence,
                    "measuredAt": measured_at.isoformat(),
                    "metrics": {"totalVolumeM3": 10 + sequence / 1000, "pressureKpa": 1.5,
                                "gasDetected": 1 if sequence == 0 else 0, "valveOpen": 1},
                }
                spool.execute("INSERT INTO reading(sequence,payload) VALUES (?,?)", (sequence, json.dumps(event)))
            print(f"Spooled {args.count} readings while disconnected")
            return

        rows = spool.execute(
            "SELECT sequence,payload FROM reading WHERE sent=0 ORDER BY sequence"
            if args.mode == "send" else
            "SELECT sequence,payload FROM reading WHERE sequence=0"
        ).fetchall()
        client = Mqtt5("emqx", 1883, credentials["mqttUsername"], credentials["oneTimeCredential"])
        try:
            if client.reason != 0:
                raise RuntimeError("Seeded device MQTT authentication failed")
            for sequence, payload in rows:
                event = json.loads(payload)
                if client.publish(f"smartgn/devices/{device}/telemetry", event) >= 128:
                    raise RuntimeError(f"EMQX did not accept reading {sequence}")
                spool.execute("UPDATE reading SET sent=1 WHERE sequence=?", (sequence,))
                spool.commit()
                if args.mode == "repeat":
                    event["sequenceNumber"] = 999
                    if client.publish(f"smartgn/devices/{device}/telemetry", event) >= 128:
                        raise RuntimeError("EMQX did not accept the deliberate identity conflict")
        finally:
            client.close()
        print(f"EMQX acknowledged {len(rows)} original readings ({args.mode})")


if __name__ == "__main__":
    main()
