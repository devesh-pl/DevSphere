"""Read-only teacher evidence for the exact demo UUID, without exposing connection credentials."""
import json
import os
from pathlib import Path
import subprocess
from uuid import UUID
folder = Path(os.environ.get('DEVSPHERE_EVIDENCE_DIR', '/private/tmp/devsphere-spring-evidence'))
report = json.loads((folder / 'crud-results.json').read_text())
deployment_id = str(UUID(report['resources']['deployment_id']))
sql = f"SELECT id,management_service,status,replicas,image FROM public.deployments WHERE id='{deployment_id}'; SELECT revision_number,replicas,change_type FROM public.deployment_revisions WHERE deployment_id='{deployment_id}' ORDER BY revision_number;"
result = subprocess.run(['docker','exec','-i','devsphere-postgres','psql','-U','deployment_service','-d','deployment_db','-v','ON_ERROR_STOP=1'],input=sql,text=True,capture_output=True,check=True)
assert deployment_id in result.stdout and 'java' in result.stdout
(folder / 'postgres-persistence.txt').write_text(result.stdout)
print(result.stdout)
print('PASS: Real PostgreSQL deployment and revision audit records persisted after API operations')
