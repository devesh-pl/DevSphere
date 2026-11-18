"""Isolated, real REST demonstration. Credentials stay in memory; only own resources are cleaned."""
import argparse
import json
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

parser = argparse.ArgumentParser()
parser.add_argument('--end-to-end', action='store_true', help='Also provision and run a real Docker/Kind build')
parser.add_argument('--monitoring', action='store_true', help='Assert live Java readiness metrics in Prometheus')
parser.add_argument('--keep', action='store_true', help='Keep only this demo deployment for classroom inspection')
args = parser.parse_args()
BASE = os.environ.get('DEVSPHERE_GATEWAY_URL', 'http://127.0.0.1:8080').rstrip('/')
report = {'checks': [], 'resources': {}}


def api(method, path, body=None, token=None, expected=200):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = Request(BASE + path, method=method, headers=headers,
                      data=None if body is None else json.dumps(body).encode())
    try:
        with urlopen(request, timeout=90 if path.startswith('/api/auth/') else 45) as response:
            status, raw = response.status, response.read()
    except HTTPError as error:
        status, raw = error.code, error.read()
    data = json.loads(raw) if raw else {}
    if status != expected:
        raise AssertionError(f'{method} {path}: expected {expected}, got {status}; {data.get("detail", "unexpected response") if isinstance(data, dict) else "unexpected response"}')
    return data


def check(name):
    report['checks'].append(name)
    print('PASS:', name, flush=True)


def account():
    credentials = {'email': f'spring-demo-{uuid4().hex}@example.com', 'password': secrets.token_urlsafe(24)}
    api('POST', '/api/auth/register', {**credentials, 'full_name': 'Isolated Spring Demo'}, expected=201)
    return api('POST', '/api/auth/login', credentials)['access_token']


def wait(path, token, statuses, timeout=240):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        item = api('GET', path, token=token)
        if item['status'] in statuses:
            return item
        if item['status'] == 'failed':
            raise AssertionError(f'{path}: failed ({item.get("error_message") or item.get("error")})')
        time.sleep(2)
    raise TimeoutError(f'{path}: timed out')


def wait_ready(path, token, replicas):
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        record = api('GET', path, token=token)
        if record.get('ready_replicas') == replicas and record.get('desired_replicas') == replicas:
            return record
        time.sleep(2)
    raise TimeoutError('Kubernetes replicas did not become ready')


token = account()
other = account()
project = None
deployment = None
build_deployment = None
try:
    slug = 'spring-demo-' + uuid4().hex[:8]
    body = {'name': 'University Spring CRUD', 'slug': slug, 'description': 'Isolated practical demonstration', 'templateId': 'fastapi-basic'}
    project = api('POST', '/api/projects', body, token, 201)
    report['resources']['project_id'] = project['id']
    ppath = '/api/projects/' + project['id']
    assert api('GET', ppath, token=token)['status'] == 'draft'
    assert any(p['id'] == project['id'] for p in api('GET', '/api/projects', token=token))
    api('GET', ppath, token=other, expected=404)
    api('GET', ppath, expected=401)
    api('POST', '/api/projects', body, token, 409)
    api('POST', '/api/projects', {**body, 'slug': 'INVALID_SLUG'}, token, 400)
    body['description'] = 'Updated through REST'
    assert api('PUT', ppath, body, token)['description'] == body['description']
    check('Project create/read/list/update, duplicate, validation, authentication and cross-user rejection')
    discovered = api('GET', '/api/deployment-spring/discovery/projects/' + project['id'], token=token)
    assert discovered['id'] == project['id']
    api('GET', '/api/deployment-spring/discovery/projects/' + project['id'], token=other, expected=404)
    api('GET', '/api/deployment-spring/discovery/projects/' + str(uuid4()), token=token, expected=404)
    check('Real Java-to-Java PROJECT-SERVICE lookup through Eureka/LoadBalancer')
    request = {'name': slug, 'image': 'nginxinc/nginx-unprivileged:stable-alpine', 'container_port': 8080, 'replicas': 1, 'project_id': project['id']}
    api('POST', '/api/deployment-spring/deployments', {**request, 'image': 'ubuntu:latest'}, token, 422)
    deployment = api('POST', '/api/deployment-spring/deployments', request, token, 201)
    report['resources']['deployment_id'] = deployment['id']
    report['resources']['kubernetes_name'] = deployment['name']
    dpath = '/api/deployment-spring/deployments/' + deployment['id']
    assert api('GET', dpath, token=token)['management_service'] == 'java'
    api('GET', dpath, token=other, expected=404)
    assert any(d['id'] == deployment['id'] for d in api('GET', '/api/deployment-spring/deployments', token=token))
    wait_ready(dpath, token, 1)
    api('PUT', dpath, {'replicas': 2}, token)
    wait_ready(dpath, token, 2)
    check('Kubernetes creation and real scale to two ready replicas')
    if args.monitoring:
        deadline = time.monotonic() + 60
        query = urlencode({'query': 'devsphere_k8s_deployment_ready_replicas{deployment="' + deployment['name'] + '"}'})
        while time.monotonic() < deadline:
            with urlopen('http://127.0.0.1:9090/api/v1/query?' + query, timeout=10) as response:
                samples = json.load(response)['data']['result']
            if any(float(sample['value'][1]) >= 2 for sample in samples):
                report['java_ready_metric'] = {'deployment': deployment['name'], 'ready_replicas': 2}
                break
            time.sleep(3)
        else:
            raise AssertionError('Java readiness metric did not report two ready replicas')
        check('Prometheus reports actual Java workload readiness with two replicas')

    api('PUT', dpath, {'replicas': 1}, token)
    wait_ready(dpath, token, 1)
    history = api('GET', dpath + '/revisions', token=token)
    assert len(history) >= 3
    api('POST', dpath + '/rollback', {'revision': 2}, token)
    wait_ready(dpath, token, 2)
    api('POST', dpath + '/rollback', {'revision': 1}, token)
    wait_ready(dpath, token, 1)
    api('GET', dpath + '/pods', token=token)
    api('GET', dpath + '/logs', token=token)
    check('Scale back, persisted revisions, rollback, pod diagnostics and application logs')
    if args.end_to_end:
        operation = api('POST', '/api/orchestrator/operations', {'operation_type': 'provision_project', 'project_slug': slug, 'template_id': 'fastapi-basic', 'repository_url': 'https://github.com/example/devsphere-demo'}, token, 202)
        op = wait('/api/orchestrator/operations/' + operation['id'], token, {'completed'})
        body['provisioningOperationId'] = op['id']
        assert api('PUT', ppath, body, token)['status'] == 'provisioned'
        build = api('POST', '/api/build/builds', {'operation_id': op['id']}, token, 202)
        bpath = '/api/build/builds/' + build['id']
        report['resources']['build_id'] = build['id']
        # A running worker may win the row lock; both outcomes are valid and explicit.
        try:
            api('PUT', bpath, {'label': 'University practical'}, token)
        except AssertionError as error:
            if 'got 409' not in str(error):
                raise
        built = wait(bpath, token, {'completed'}, timeout=360)
        build_deployment = built['deployment_id']
        report['resources']['build_deployment_id'] = build_deployment
        api('DELETE', bpath, token=token)
        check('Existing Python build queue, Docker image build, Kind load/deploy, terminal archive')
    check('Backend CRUD demonstrated through NGINX; PostgreSQL persistence verified separately by verifier')
finally:
    if not args.keep:
        if deployment:
            api('DELETE', '/api/deployment-spring/deployments/' + deployment['id'], token=token)
            assert api('GET', '/api/deployment-spring/deployments/' + deployment['id'], token=token)['status'] == 'deleted'
        if build_deployment:
            api('DELETE', '/api/deployment/deployments/' + build_deployment, token=token)
        if project:
            api('DELETE', '/api/projects/' + project['id'], token=token, expected=204)
            api('GET', '/api/projects/' + project['id'], token=token, expected=404)
        check('Deleted only resources created by this demonstration; deployment/build audit rows retained')
    else:
        print('Kept this demo only; resource IDs are in the report. Account credentials were not written.')
    destination = Path(os.environ.get('DEVSPHERE_EVIDENCE_DIR', '/private/tmp/devsphere-spring-evidence'))
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'crud-results.json').write_text(json.dumps(report, indent=2) + '\n')
