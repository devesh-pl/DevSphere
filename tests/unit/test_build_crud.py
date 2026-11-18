"""Build API/worker contract tests against a disposable PostgreSQL schema.

Set TEST_BUILD_DATABASE_URL. Tests never connect to or truncate the real public tables.
"""
import importlib.util
import os
from pathlib import Path
import sys
import types
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def platform(monkeypatch, request):
    url = os.environ.get('TEST_BUILD_DATABASE_URL')
    if not url:
        pytest.skip('TEST_BUILD_DATABASE_URL required for isolated PostgreSQL tests')
    schema = 'test_build_' + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA {schema}'))
    def cleanup():
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()
    request.addfinalizer(cleanup)
    engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    request.addfinalizer(engine.dispose)
    with engine.begin() as db:
        for file in sorted((ROOT / 'services/build-service/migrations').glob('*.sql')):
            db.connection.driver_connection.execute(file.read_text())
    common = types.ModuleType('app.common')
    common.SessionLocal = sessionmaker(engine, expire_on_commit=False)
    common.AUTH = 'http://auth.test'
    common.ORCH = 'http://orchestrator.test'
    common.DEPLOY = 'http://deployment.test'
    common.runner = Mock()
    common.cipher = Mock()
    common.cipher.encrypt.return_value = b'encrypted-test-token'
    common.utc_now = lambda: None
    def serialize(row):
        if row is None:
            return None
        return {key: value for key, value in dict(row).items()
                if key not in ('token_ciphertext', 'lease_owner')}
    common.row_to_dict = serialize
    def get_job(job_id):
        with common.SessionLocal() as db:
            return serialize(db.execute(text('SELECT * FROM build_jobs WHERE id=:id'),
                                        {'id': job_id}).mappings().first())
    common.get_job = get_job
    monkeypatch.setitem(sys.modules, 'app', types.ModuleType('app'))
    monkeypatch.setitem(sys.modules, 'app.common', common)
    def load(name, file):
        spec = importlib.util.spec_from_file_location(name, ROOT / file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    api = load('build_api_test', 'services/build-service/app/main.py')
    worker = load('build_worker_test', 'services/build-service/app/worker.py')
    monkeypatch.setattr(api, 'authenticate', lambda header: ('test-token', {'id': 'owner', 'role': 'developer'}))
    def insert(status='queued', owner='owner'):
        job_id = uuid4().hex
        with engine.begin() as db:
            db.execute(text('''INSERT INTO build_jobs
                (id,operation_id,owner_id,project_slug,status,token_ciphertext)
                VALUES (:id,:operation,:owner,'test-api',:status,'encrypted')'''),
                {'id': job_id, 'operation': str(uuid4()), 'owner': owner, 'status': status})
        return job_id
    yield api, worker, common, insert


def test_queued_metadata_edit_preserves_operational_identity(platform):
    api, _, common, insert = platform
    job = insert()
    result = api.update_build(job, api.BuildMetadata(label='Practical demo'), 'Bearer test')
    assert result['label'] == 'Practical demo'
    assert result['project_slug'] == 'test-api'
    assert result['status'] == 'queued'
    assert 'token_ciphertext' not in result


def test_cancelled_job_is_retained_and_cannot_be_claimed_or_retried(platform):
    api, worker, common, insert = platform
    job = insert()
    result = api.delete_build(job, 'Bearer test')
    assert result['status'] == 'failed'
    assert result['archived_at'] is not None
    assert worker.claim_job() is None
    assert common.get_job(job) is not None
    with pytest.raises(api.HTTPException) as exc:
        api.retry_build(job, 'Bearer test')
    assert exc.value.status_code == 409


def test_worker_claim_wins_preventing_cancel_or_edit(platform):
    api, worker, common, insert = platform
    job = insert()
    assert worker.claim_job()['id'] == job
    for work in (lambda: api.delete_build(job, 'Bearer test'),
                 lambda: api.update_build(job, api.BuildMetadata(label='late'), 'Bearer test')):
        with pytest.raises(api.HTTPException) as exc:
            work()
        assert exc.value.status_code == 409
    assert common.get_job(job)['status'] == 'building'


@pytest.mark.parametrize('status', ['completed', 'failed'])
def test_terminal_archive_keeps_lifecycle_and_audit(platform, status):
    api, _, common, insert = platform
    job = insert(status)
    assert api.delete_build(job, 'Bearer test')['status'] == status
    assert common.get_job(job)['archived_at'] is not None
    assert api.list_builds('Bearer test') == []
    assert api.delete_build(job, 'Bearer test')['status'] == status


def test_cross_user_edit_and_archive_hidden(platform):
    api, _, _, insert = platform
    job = insert(owner='other')
    for work in (lambda: api.delete_build(job, 'Bearer test'),
                 lambda: api.update_build(job, api.BuildMetadata(label='stolen'), 'Bearer test')):
        with pytest.raises(api.HTTPException) as exc:
            work()
        assert exc.value.status_code == 404


def test_failed_visible_job_remains_retryable(platform):
    api, worker, _, insert = platform
    job = insert('failed')
    assert api.retry_build(job, 'Bearer test')['status'] == 'queued'
    assert worker.claim_job()['id'] == job


def test_metadata_rejects_operational_fields(platform):
    api, _, _, _ = platform
    with pytest.raises(ValueError):
        api.BuildMetadata(label='demo', operation_id=str(uuid4()))
