"""Optional live failure test: stop/restart only the new Project container, always restore it."""
import json
import secrets
import subprocess
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = 'http://127.0.0.1:8080'
CONTAINER = 'devsphere-project-service-spring-1'


def call(method, path, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = Request(BASE + path, headers=headers, method=method,
                      data=None if body is None else json.dumps(body).encode())
    try:
        with urlopen(request, timeout=90 if '/api/auth/' in path else 30) as result:
            return result.status, json.load(result) if result.status != 204 else None
    except HTTPError as error:
        return error.code, None


credentials = {'email': 'discovery-failure-' + secrets.token_hex(8) + '@example.com',
               'password': secrets.token_urlsafe(24)}
assert call('POST', '/api/auth/register', {**credentials, 'full_name': 'Isolated Discovery Failure'})[0] == 201
status, login = call('POST', '/api/auth/login', credentials)
assert status == 200
token = login['access_token']
status, project = call('POST', '/api/projects', {'name': 'Discovery failure test',
    'slug': 'failure-' + secrets.token_hex(6), 'description': '', 'templateId': 'fastapi-basic'}, token)
assert status == 201
path = '/api/deployment-spring/discovery/projects/' + project['id']
try:
    assert call('GET', path, token=token)[0] == 200
    subprocess.run(['docker', 'stop', CONTAINER], check=True, capture_output=True)
    assert call('GET', path, token=token)[0] == 503
    print('PASS: Actual unavailable Project instance produces HTTP 503 through Eureka/LoadBalancer', flush=True)
finally:
    subprocess.run(['docker', 'start', CONTAINER], check=True, capture_output=True)
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        try:
            with urlopen('http://127.0.0.1:8087/actuator/health', timeout=5) as response:
                if json.load(response)['status'] == 'UP':
                    break
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(3)
    else:
        raise TimeoutError('Project container restored but did not become healthy; inspect its logs')
    assert call('DELETE', '/api/projects/' + project['id'], token=token)[0] == 204
    print('PASS: Project service restored and only the failure-test Project record removed', flush=True)
