"""Verify real service registration; never substitute a static discovery URL."""
import json
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen

EUREKA = os.getenv('EUREKA_VERIFY_URL', 'http://127.0.0.1:8761')

def get(url):
    with urlopen(Request(url, headers={'Accept': 'application/json'}), timeout=8) as response:
        return json.load(response)

for port in (8761, 8087, 8088):
    assert get(f'http://127.0.0.1:{port}/actuator/health')['status'] == 'UP'
    print(f'PASS: Java health on {port}')
deadline = time.monotonic() + 120
while True:
    registry = get(EUREKA + '/eureka/apps')
    apps = registry.get('applications', {}).get('application', [])
    if isinstance(apps, dict): apps = [apps]
    names = set()
    for app in apps:
        instances = app.get('instance', [])
        if isinstance(instances, dict): instances = [instances]
        if any(item.get('status') == 'UP' for item in instances): names.add(app['name'])
    if {'PROJECT-SERVICE', 'DEPLOYMENT-SERVICE'} <= names: break
    if time.monotonic() >= deadline: raise AssertionError('Two Spring business services did not register UP')
    time.sleep(3)
print('PASS: PROJECT-SERVICE and DEPLOYMENT-SERVICE registered UP in real Eureka')
assert get('http://127.0.0.1:8006/health')['status'] == 'ok'
print('PASS: Existing Python Build API health')
destination = Path(os.getenv('DEVSPHERE_EVIDENCE_DIR', '/private/tmp/devsphere-spring-evidence'))
destination.mkdir(parents=True, exist_ok=True)
(destination / 'eureka-registration.json').write_text(json.dumps(registry, indent=2) + '\n')
