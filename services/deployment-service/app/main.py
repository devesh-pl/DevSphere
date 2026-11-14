"""DevSphere Kubernetes Deployment Service."""

import os
import re
import json
import logging
import urllib.error
import urllib.request

from uuid import uuid4
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, Header
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("devsphere.deployment")

DATABASE_URL = os.environ["DATABASE_URL"]
AUTH_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
NAMESPACE = "devsphere-apps"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=1,
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

config.load_kube_config(
    config_file=os.getenv("KUBECONFIG", "/app/kubeconfig/config")
)

apps_api = client.AppsV1Api()
core_api = client.CoreV1Api()

app = FastAPI(
    title="DevSphere Deployment Service",
    version="0.1.0",
)


class DeploymentCreate(BaseModel):
    name: str = Field(
        min_length=3,
        max_length=40,
        pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$",
    )
    image: str = Field(max_length=255)
    container_port: int = Field(default=80, ge=1, le=65535)
    replicas: int = Field(default=1, ge=1, le=2)


# Initial development allowlist. Broaden later with policy controls.
ALLOWED_IMAGES = {"nginxinc/nginx-unprivileged:stable-alpine"}


def get_db():
    with SessionLocal() as db:
        yield db


def current_user(
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")

    request = urllib.request.Request(
        f"{AUTH_URL}/auth/me",
        headers={"Authorization": authorization},
    )

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            user = json.load(response)

    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise HTTPException(401, "Invalid access token")
        raise HTTPException(503, "Authentication service unavailable")

    except (urllib.error.URLError, TimeoutError, ValueError):
        raise HTTPException(503, "Authentication service unavailable")

    if not user.get("id") or user.get("role") not in (
        "developer", "admin"
    ):
        raise HTTPException(403, "Developer access required")

    return user


def get_owned_record(db, deployment_id, user):
    try:
        normalized = str(__import__("uuid").UUID(deployment_id))
    except ValueError:
        raise HTTPException(404, "Deployment not found")

    record = db.execute(
        text("SELECT * FROM deployments WHERE id=:id AND owner_id=:owner"),
        {"id": normalized, "owner": user["id"]},
    ).mappings().first()

    if not record:
        raise HTTPException(404, "Deployment not found")

    return dict(record)


def get_kubernetes_status(name):
    try:
        deployment = apps_api.read_namespaced_deployment(
            name=name,
            namespace=NAMESPACE,
        )

        desired = deployment.spec.replicas or 0
        ready = deployment.status.ready_replicas or 0

        return {
            "status": "running" if ready >= desired and desired > 0
                      else "deploying",
            "ready_replicas": ready,
            "desired_replicas": desired,
        }

    except ApiException as error:
        if error.status == 404:
            return {
                "status": "missing",
                "ready_replicas": 0,
                "desired_replicas": 0,
            }

        raise HTTPException(502, "Kubernetes status check failed")


def to_response(record, live=False):
    result = {
        "id": record["id"],
        "name": record["name"],
        "image": record["image"],
        "namespace": record["namespace"],
        "status": record["status"],
        "container_port": record["container_port"],
        "replicas": record["replicas"],
        "created_at": record["created_at"].isoformat(),
    }

    if live and record["status"] not in ("failed", "deleted"):
        result.update(get_kubernetes_status(record["name"]))

    return result


@app.get("/health")
def health():
    return {"status": "ok", "service": "deployment-service"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        core_api.read_namespace(NAMESPACE)
        return {"status": "ready"}
    except Exception:
        raise HTTPException(503, "Deployment dependencies unavailable")


@app.post("/deployments", status_code=201)
def create_deployment(
    payload: DeploymentCreate,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    if payload.image not in ALLOWED_IMAGES:
        raise HTTPException(
            422,
            "Image not in development allowlist",
        )

    deployment_id = str(uuid4())
    k8s_name = "ds-" + deployment_id[:12]

    db.execute(
        text("""
            INSERT INTO deployments
            (id, owner_id, name, image, container_port,
             replicas, namespace, status)
            VALUES
            (:id, :owner, :name, :image, :port,
             :replicas, :namespace, 'deploying')
        """),
        {
            "id": deployment_id,
            "owner": user["id"],
            "name": k8s_name,
            "image": payload.image,
            "port": payload.container_port,
            "replicas": payload.replicas,
            "namespace": NAMESPACE,
        },
    )
    db.commit()

    labels = {
        "app": k8s_name,
        "app.kubernetes.io/managed-by": "devsphere",
        "devsphere.io/owner": user["id"],
    }

    container = client.V1Container(
        name="application",
        image=payload.image,
        ports=[
            client.V1ContainerPort(
                container_port=payload.container_port
            )
        ],
        resources=client.V1ResourceRequirements(
            requests={"cpu": "25m", "memory": "32Mi"},
            limits={"cpu": "200m", "memory": "128Mi"},
        ),
        security_context=client.V1SecurityContext(
            allow_privilege_escalation=False,
            capabilities=client.V1Capabilities(drop=["ALL"]),
            run_as_non_root=True,
            run_as_user=101,
            seccomp_profile=client.V1SeccompProfile(
                type="RuntimeDefault"
            ),
        ),
        readiness_probe=client.V1Probe(
            http_get=client.V1HTTPGetAction(
                path="/",
                port=payload.container_port,
            ),
            initial_delay_seconds=3,
            period_seconds=5,
        ),
    )

    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(
            name=k8s_name,
            namespace=NAMESPACE,
            labels=labels,
        ),
        spec=client.V1DeploymentSpec(
            replicas=payload.replicas,
            selector=client.V1LabelSelector(match_labels={"app": k8s_name}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=client.V1PodSpec(
                    containers=[container],
                    automount_service_account_token=False,
                ),
            ),
        ),
    )

    service = client.V1Service(
        metadata=client.V1ObjectMeta(
            name=k8s_name,
            namespace=NAMESPACE,
            labels=labels,
        ),
        spec=client.V1ServiceSpec(
            selector={"app": k8s_name},
            type="ClusterIP",
            ports=[
                client.V1ServicePort(
                    port=payload.container_port,
                    target_port=payload.container_port,
                )
            ],
        ),
    )

    try:
        apps_api.create_namespaced_deployment(
            namespace=NAMESPACE,
            body=deployment,
        )

        core_api.create_namespaced_service(
            namespace=NAMESPACE,
            body=service,
        )

    except ApiException:
        logger.exception("Kubernetes deployment creation failed")

        # Attempt to clean up resources created before the failure.
        try:
            core_api.delete_namespaced_service(k8s_name, NAMESPACE)
        except ApiException:
            pass

        try:
            apps_api.delete_namespaced_deployment(
                k8s_name, NAMESPACE
            )
        except ApiException:
            pass

        db.execute(
            text("""
                UPDATE deployments SET status='failed'
                WHERE id=:id
            """),
            {"id": deployment_id},
        )
        db.commit()

        raise HTTPException(
            502,
            "Kubernetes deployment creation failed",
        )

    return {
        "id": deployment_id,
        "name": k8s_name,
        "status": "deploying",
        "namespace": NAMESPACE,
        "image": payload.image,
        "service_dns": (
            f"{k8s_name}.{NAMESPACE}.svc.cluster.local"
        ),
    }


@app.get("/deployments")
def list_deployments(
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    records = db.execute(
        text("""
            SELECT * FROM deployments
            WHERE owner_id=:owner
            ORDER BY created_at DESC
            LIMIT 100
        """),
        {"owner": user["id"]},
    ).mappings().all()

    return [to_response(dict(record)) for record in records]


@app.get("/deployments/{deployment_id}")
def get_deployment(
    deployment_id: str,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    record = get_owned_record(db, deployment_id, user)
    return to_response(record, live=True)


@app.delete("/deployments/{deployment_id}")
def delete_deployment(
    deployment_id: str,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    record = get_owned_record(db, deployment_id, user)

    if record["status"] == "deleted":
        return {"status": "deleted", "id": deployment_id}

    name = record["name"]

    try:
        core_api.delete_namespaced_service(
            name=name,
            namespace=NAMESPACE,
        )
    except ApiException as error:
        if error.status != 404:
            raise HTTPException(502, "Service deletion failed")

    try:
        apps_api.delete_namespaced_deployment(
            name=name,
            namespace=NAMESPACE,
        )
    except ApiException as error:
        if error.status != 404:
            raise HTTPException(502, "Deployment deletion failed")

    db.execute(
        text("""
            UPDATE deployments
            SET status='deleted'
            WHERE id=:id
        """),
        {"id": deployment_id},
    )
    db.commit()

    return {"id": deployment_id, "status": "deleted"}
