"""Unit tests for deployment rollout classification."""

from pathlib import Path
from types import SimpleNamespace
import importlib.util


path = (
    Path(__file__).resolve().parents[2]
    / "services/deployment-service/app/reconciler.py"
)

spec = importlib.util.spec_from_file_location(
    "deployment_reconciler", path
)

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

classify = module.classify_rollout


def obj(**kwargs):
    return SimpleNamespace(**kwargs)


def deployment(
    *,
    replicas=1,
    ready=1,
    available=1,
    updated=1,
    generation=2,
    observed=2,
    image="example:v1",
    failed=False,
):
    conditions = []

    if failed:
        conditions.append(obj(
            type="Progressing",
            status="False",
            reason="ProgressDeadlineExceeded",
        ))

    return obj(
        metadata=obj(generation=generation),
        spec=obj(
            replicas=replicas,
            template=obj(
                spec=obj(
                    containers=[
                        obj(name="application", image=image)
                    ]
                )
            ),
        ),
        status=obj(
            ready_replicas=ready,
            available_replicas=available,
            updated_replicas=updated,
            observed_generation=observed,
            conditions=conditions,
        ),
    )


def test_ready_rollout_becomes_running():
    result = classify(
        deployment(),
        "example:v1",
        1,
    )
    assert result == ("running", None)


def test_unready_rollout_remains_deploying():
    result = classify(
        deployment(ready=0, available=0),
        "example:v1",
        1,
    )
    assert result == ("deploying", None)


def test_old_generation_is_not_completed():
    result = classify(
        deployment(generation=3, observed=2),
        "example:v1",
        1,
    )
    assert result == ("deploying", None)


def test_failed_rollout_detected():
    result = classify(
        deployment(failed=True),
        "example:v1",
        1,
    )
    assert result[0] == "failed"


def test_changed_image_is_ignored():
    result = classify(
        deployment(image="example:v2"),
        "example:v1",
        1,
    )
    assert result is None


def test_changed_replica_target_is_ignored():
    result = classify(
        deployment(replicas=2),
        "example:v1",
        1,
    )
    assert result is None
