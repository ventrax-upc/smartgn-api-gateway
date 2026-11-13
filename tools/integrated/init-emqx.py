"""Provision local service accounts and topic ACLs in the real EMQX broker."""
import base64
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USERS = "/authentication/password_based%3Abuilt_in_database/users"
RULES = "/authorization/sources/built_in_database/rules/users"
BASE = "http://emqx:18083/api/v5"


def request(method, path, body=None, accepted=()):
    credentials = ":".join(os.environ[key] for key in (
        "DEVICE_BROKER_API_KEY", "DEVICE_BROKER_API_SECRET"
    ))
    headers = {
        "Authorization": "Basic " + base64.b64encode(credentials.encode()).decode(),
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urlopen(Request(BASE + path, data=data, headers=headers, method=method), timeout=5) as response:
            return response.status
    except HTTPError as exc:
        if exc.code not in accepted:
            raise
        return exc.code


def provision(username, password, grants):
    user = {"password": password, "is_superuser": False}
    if request("POST", USERS, {"user_id": username, **user}, (409,)) == 409:
        request("PUT", f"{USERS}/{username}", user)
    rules = [{"permission": "allow", "action": action, "topic": topic} for action, topic in grants]
    if request("PUT", f"{RULES}/{username}", {"username": username, "rules": rules}, (404,)) == 404:
        request("POST", RULES, [{"username": username, "rules": rules}])


for attempt in range(30):
    try:
        request("GET", USERS)
        break
    except (HTTPError, URLError, TimeoutError):
        if attempt == 29:
            raise
        time.sleep(2)

provision("billing-service", os.environ["MQTT_BILLING_PASSWORD"], [
    ("publish", "smartgn/events/payments/#"),
    ("subscribe", "smartgn/events/support/#"),
    ("subscribe", "smartgn/events/installation/#"),
])
provision("support-service", os.environ["MQTT_SUPPORT_PASSWORD"], [
    ("publish", "smartgn/events/support/#"),
    ("subscribe", "smartgn/events/payments/CoverageCalculated"),
])
provision("telemetry-service", os.environ["MQTT_TELEMETRY_PASSWORD"], [
    ("subscribe", "smartgn/devices/+/telemetry"),
])
provision("broker-service", os.environ["MQTT_BROKER_PASSWORD"], [
    ("publish", "smartgn/events/broker/#"),
])
print("EMQX local service accounts and ACLs are ready.")
