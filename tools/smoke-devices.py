"""Real application services and EMQX; labeled provider/contact/Telemetry fixtures."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import secrets
import sys
import time
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'smartgn-installation-device-management/tools'))
from mqtt_client import Mqtt5

settings = dict(line.split('=', 1) for line in (ROOT.parent/'smartgn-payments-billing/.env').read_text(encoding='utf-8-sig').splitlines() if '=' in line and not line.startswith('#'))
GATEWAY = 'http://localhost:8000'
SERVICE = {'Authorization': 'Bearer '+settings['INTERNAL_SERVICE_TOKEN']}
FIXTURE = {'Authorization': 'Bearer '+settings['FIXTURE_ADMIN_TOKEN']}
CHECKS = []


def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc).isoformat()


def call(method, path, body=None, headers=None, base=GATEWAY, expected=200):
    request = Request(base+path, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Content-Type':'application/json', **(headers or {})})
    try:
        with urlopen(request, timeout=20) as response: status, raw = response.status, response.read()
    except HTTPError as error: status, raw = error.code, error.read()
    assert status == expected, f'{method} {path}: {status} != {expected}: {raw[:200]!r}'
    return json.loads(raw) if raw else None


def eventually(fn):
    for _ in range(90):
        try:
            value = fn()
            if value: return value
        except (AssertionError, URLError, ConnectionError, TimeoutError): pass
        time.sleep(1)
    raise AssertionError('Device verification dependency did not become ready')


def check(message): CHECKS.append(message); print('PASS', message, flush=True)


def purchase(email):
    installation = call('POST', '/api/v1/installations', {'contact':{'name':'Device Verification','email':email,'phone':'999999999'},'address':'Lima LOCAL TEST'}, expected=201)['id']
    headers = {'Idempotency-Key':uid(), 'X-Checkout-Secret':secrets.token_urlsafe(32)}
    order = call('POST','/api/v1/checkout/orders',{'installationId':installation,'email':email,'firstName':'Device','lastName':'Verification'},headers,expected=201)
    reference = 'device-local-'+uid()
    call('POST','/internal/v1/local-provider/results',{'reference':reference,'orderId':order['id'],'status':'CONFIRMED','amount':250},SERVICE,base='http://localhost:28083')
    call('POST','/internal/v1/payments/confirmations',{'orderId':order['id'],'providerReference':reference},SERVICE,base='http://localhost:28083')
    return installation


def main():
    email = 'device-'+uuid.uuid4().hex+'@example.test'
    installation = purchase(email)
    messages = eventually(lambda: call('GET','/fixtures/messages?email='+email,headers=FIXTURE,base='http://localhost:18091'))
    activation = next(m['token'] for m in messages if m.get('purpose')=='ACTIVATION')
    password = 'Device-'+secrets.token_hex(12)
    call('POST','/api/v1/auth/activate-password',{'activationToken':activation,'newPassword':password},expected=204)
    session = call('POST','/api/v1/auth/sign-in',{'email':email,'password':password})
    owner = {'Authorization':'Bearer '+session['token']}
    account = session['id']
    admin = {'Authorization':'Bearer '+call('POST','/api/v1/auth/sign-in',{'email':'admin@smartgn.test','password':settings['BOOTSTRAP_SUPERADMIN_PASSWORD']})['token']}
    prop = call('POST','/api/v1/properties',{'name':'Device verification','address':'Local Lima','propertyType':'HOUSE'},owner,expected=201)
    point = call('POST','/api/v1/properties/'+prop['id']+'/supply-points',{'serialNumber':'device-'+uid(),'locationName':'Kitchen'},owner,expected=201)
    path = '/api/v1/installations/'+installation
    paid = eventually(lambda: (value if (value:=call('GET',path,headers=owner)['installation'])['status']=='PENDING' else None))
    call('POST','/api/v1/installers',{'firstName':'External','lastName':'Verification','identification':uid(),'phone':'999999999','email':'installer@example.test','accreditationCode':uid(),'available':True},admin,expected=201)
    call('PUT',path+'/target',{'propertyId':prop['id'],'supplyPointId':point['id'],'version':paid['version']},owner)
    assigned = eventually(lambda: (value if (value:=call('GET',path,headers=owner).get('installation',{})).get('status')=='ASSIGNED' else None))
    check('Real checkout provisions IAM and a paid installation through Gateway')
    second = call('POST','/api/v1/installers',{'firstName':'Second','lastName':'Verification','identification':uid(),'phone':'999999999','accreditationCode':uid(),'available':True},admin,expected=201)
    call('PATCH',path+'/reassign',{'installerId':second['id'],'version':assigned['version'],'reason':'Local device verification'},admin)
    current = call('GET',path,headers=owner)['installation']
    start = datetime.now(timezone.utc)+timedelta(hours=1)
    call('PUT',path+'/appointment',{'from':start.isoformat(),'to':(start+timedelta(hours=1)).isoformat(),'version':current['version']},admin)
    call('PATCH',path+'/status',{'status':'IN_PROGRESS'},admin)
    device = uid()
    receipt = call('POST','/api/v1/devices',{'deviceId':device,'installationId':installation,'supplyPointId':point['id'],'installerId':second['id'],'serialNumber':'verification-'+uid(),'location':'Kitchen','installedAt':now()},admin,expected=202)
    def current_device():
        return next((row['device'] for row in call('GET','/api/v1/devices?limit=100',headers=admin) if row['device']['id']==device),None)
    eventually(lambda: (value if (value:=current_device()) and value['status']=='ACTIVE' else None))
    client = Mqtt5('localhost',1886,receipt['mqttUsername'],receipt['oneTimeCredential'])
    assert client.reason==0
    assert client.publish('smartgn/devices/'+device+'/telemetry',{'fixture':'LOCAL_DEVICE_VERIFICATION'})<128
    assert client.publish('smartgn/devices/'+uid()+'/telemetry',{'fixture':'FORBIDDEN_TOPIC'})>=128
    client.close()
    check('Device provisioning reaches real EMQX with per-device topic authorization')
    call('POST',path+'/complete',{},admin,expected=409)
    call('POST','/fixtures/device-status',{'accountId':account,'deviceId':device,'connectionState':'CONNECTED','lastContact':now()},FIXTURE,base='http://localhost:18090')
    completed = call('POST',path+'/complete',{},admin)
    assert completed['status']=='COMPLETED'
    assert call('POST',path+'/complete',{},admin)['completedAt']==completed['completedAt']
    eventually(lambda: call('GET','/api/v1/subscriptions/me',headers=owner).get('plan')=='FREE')
    check('Recent-contact fixture permits idempotent completion and real Billing receives InstallationCompleted')
    rotated = call('POST','/api/v1/devices/'+device+'/credentials/rotate',{},admin,expected=202)
    eventually(lambda: (value if (value:=current_device()) and value['status']=='ACTIVE' else None))
    rejected = Mqtt5('localhost',1886,receipt['mqttUsername'],receipt['oneTimeCredential'])
    assert rejected.reason != 0
    rejected.close()
    client = Mqtt5('localhost',1886,rotated['mqttUsername'],rotated['oneTimeCredential'])
    assert client.reason==0
    client.close()
    call('POST','/api/v1/devices/'+device+'/credentials/revoke',{},admin,expected=202)
    eventually(lambda: (value if (value:=current_device()) and value['status']=='REVOKED' and value['brokerConfirmed'] else None))
    rejected = Mqtt5('localhost',1886,rotated['mqttUsername'],rotated['oneTimeCredential'])
    assert rejected.reason != 0
    rejected.close()
    history = call('GET','/api/v1/devices/'+device+'/associations',headers=admin)
    assert len(history)>=1
    assert not call('GET','/internal/v1/devices/'+device+'/authorization?associationVersion=1',headers=SERVICE,base='http://localhost:18081')['authorized']
    check('Credential rotation and broker-confirmed revocation invalidate old credentials')
    call('GET','/api/v1/operations/outbox?limit=10',headers=admin)
    call('GET','/api/v1/operations/outbox?limit=10',headers=owner,expected=403)
    check('Synchronization inspection is restricted to SuperAdmin')
    print('Device scenarios passed:',len(CHECKS),flush=True)


if __name__=='__main__': main()
