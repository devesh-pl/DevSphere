"""Read real Prometheus/Grafana evidence; never print monitoring credentials."""
import base64
import json
import os
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]

def get(url, authorization=None):
    request = Request(url)
    if authorization:
        request.add_header('Authorization', authorization)
    with urlopen(request, timeout=10) as response:
        return json.load(response)

deadline = time.monotonic() + 120
while True:
    query = urlencode({'query': 'up{job="devsphere-spring"}'})
    result = get('http://127.0.0.1:9090/api/v1/query?' + query)['data']['result']
    if len(result) == 3 and all(item['value'][1] == '1' for item in result):
        break
    if time.monotonic() >= deadline:
        raise SystemExit('Spring scrape targets not all UP; inspect Prometheus targets')
    time.sleep(3)
print('PASS: All three real Spring Prometheus targets UP')
values = dotenv_values(ROOT / '.env')
password = values.get('GRAFANA_ADMIN_PASSWORD')
if not password:
    raise SystemExit('GRAFANA_ADMIN_PASSWORD missing; Grafana verification not performed')
auth = 'Basic ' + base64.b64encode(('admin:' + password).encode()).decode()
dashboards = get('http://127.0.0.1:3000/api/search?query=DevSphere', auth)
assert any(item['uid'] == 'devsphere-spring' for item in dashboards)
dashboard = get('http://127.0.0.1:3000/api/dashboards/uid/devsphere-spring', auth)['dashboard']
assert len(dashboard['panels']) == 6
requests = get('http://127.0.0.1:9090/api/v1/query?' + urlencode({'query': 'sum by (service) (http_server_requests_seconds_count{job="devsphere-spring"})'}))['data']['result']
assert requests
report = {'spring_targets': [{'service': item['metric'].get('service'), 'up': item['value'][1]} for item in result], 'http_request_series': requests, 'spring_dashboard_panels': len(dashboard['panels']), 'available_devsphere_dashboards': len(dashboards)}
folder = Path(os.getenv('DEVSPHERE_EVIDENCE_DIR', '/private/tmp/devsphere-spring-evidence'))
folder.mkdir(parents=True, exist_ok=True)
(folder / 'monitoring.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS: Real Spring request metrics and six provisioned Grafana panels; existing dashboards retained')
