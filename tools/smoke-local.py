"""Run existing real-service acceptance through the public Gateway.

Internal provisioning, delivery and provider results remain explicitly labeled fixtures.
No user credentials, JWTs, checkout secrets or bodies are written to the observations.
"""
import json
import os
from pathlib import Path
import runpy
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = os.environ.get('GATEWAY_SMOKE_URL', 'http://localhost:8000')
original = urllib.request.urlopen
observations = []


def through_gateway(request, *args, **kwargs):
    url = request.full_url if isinstance(request, urllib.request.Request) else request
    parsed = urlsplit(url)
    if parsed.path.startswith('/api/v1/') and parsed.port in (8000, 18080, 18081, 8082, 28083):
        if not isinstance(request, urllib.request.Request):
            request = urllib.request.Request(url)
        request = urllib.request.Request(
            GATEWAY + parsed.path + ('?' + parsed.query if parsed.query else ''),
            data=request.data, method=request.get_method(),
            headers={**dict(request.header_items()), 'Origin': 'http://localhost:4200'},
        )
        record = {'method': request.get_method(), 'path': parsed.path}
        try:
            response = original(request, *args, **kwargs)
            record['status'] = response.status
            return response
        except HTTPError as error:
            record['status'] = error.code
            raise
        finally:
            observations.append(record)
    return original(request, *args, **kwargs)


def ready():
    for _ in range(90):
        try:
            with original(GATEWAY + '/ready', timeout=12) as response:
                if json.load(response)['status'] == 'UP':
                    return
        except (URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(1)
    raise AssertionError('Five-service stack did not become ready')


def main():
    ready()
    urllib.request.urlopen = through_gateway
    try:
        suites = [('smartgn-payments-billing', 'tools/smoke-service.py'),
                  ('smartgn-support-maintenance', 'tools/smoke-local.py')]
        support_only = '--support-only' in sys.argv
        if '--devices-only' in sys.argv:
            suites = []
        elif support_only:
            suites = suites[1:]
        for repo, script in suites:
            print('RUN Gateway acceptance with', repo, flush=True)
            directory = ROOT.parent / repo
            os.chdir(directory)
            sys.path.insert(0, str(directory / 'tools'))
            sys.argv = [str(directory / script)]
            runpy.run_path(str(directory / script), run_name='__main__')
        if not support_only:
            print('RUN Gateway device acceptance with real EMQX and labeled Telemetry fixture', flush=True)
            os.chdir(ROOT)
            runpy.run_path(str(ROOT / 'tools/smoke-devices.py'), run_name='__main__')
        ready()
        print('PASS Five services ready after Gateway acceptance', flush=True)
    finally:
        urllib.request.urlopen = original
        os.chdir(ROOT)
        output = ROOT / '.local/gateway-observations.json'
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(observations, indent=2) + '\n', encoding='utf-8')
        print('Public requests exercised through Gateway:', len(observations), flush=True)


if __name__ == '__main__':
    main()
