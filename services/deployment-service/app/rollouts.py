"""Deployment configuration updates and rollback history."""

from fastapi import APIRouter, Depends, HTTPException
from kubernetes.client.exceptions import ApiException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.main import (
    NAMESPACE,
    apps_api,
    allowed_development_image,
    current_user,
    get_db,
    get_owned_record,
)

router = APIRouter(tags=["Deployment Rollouts"])


class DeploymentUpdate(BaseModel):
    image: str | None = Field(default=None, max_length=255)
    replicas: int | None = Field(default=None, ge=1, le=2)


class RollbackRequest(BaseModel):
    revision: int = Field(ge=1)


def ensure_history(db, record):
    """Record the original configuration exactly once."""
    db.execute(
        text("""
            INSERT INTO deployment_revisions
            (deployment_id, revision_number, image,
             replicas, change_type)
            VALUES (:id, 1, :image, :replicas, 'initial')
            ON CONFLICT (deployment_id, revision_number)
            DO NOTHING
        """),
        {
            "id": record["id"],
            "image": record["image"],
            "replicas": record["replicas"],
        },
    )


def next_revision(db, deployment_id):
    return db.execute(
        text("""
            SELECT COALESCE(MAX(revision_number), 0) + 1
            FROM deployment_revisions
            WHERE deployment_id=:id
        """),
        {"id": deployment_id},
    ).scalar_one()


def apply_configuration(record, image, replicas):
    """Apply image and replica changes to the Kubernetes Deployment."""
    body = {
        "spec": {
            "replicas": replicas,
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "application",
                            "image": image,
                            "imagePullPolicy": "IfNotPresent",
                        }
                    ]
                }
            },
        }
    }

    try:
        apps_api.patch_namespaced_deployment(
            name=record["name"],
            namespace=NAMESPACE,
            body=body,
        )
    except ApiException as error:
        if error.status == 404:
            raise HTTPException(
                409, "Kubernetes Deployment no longer exists"
            )
        raise HTTPException(
            502, "Kubernetes update failed"
        )


def update_revision(db, record, image, replicas, change_type):
    ensure_history(db, record)

    revision = next_revision(db, record["id"])

    # The database transaction holds the deployment row lock.
    # If Kubernetes rejects the patch, rollback the database transaction.
    apply_configuration(record, image, replicas)

    db.execute(
        text("""
            UPDATE deployments
            SET image=:image,
                replicas=:replicas,
                status='deploying'
            WHERE id=:id
        """),
        {
            "id": record["id"],
            "image": image,
            "replicas": replicas,
        },
    )

    db.execute(
        text("""
            INSERT INTO deployment_revisions
            (deployment_id, revision_number, image,
             replicas, change_type)
            VALUES
            (:id, :revision, :image, :replicas, :change)
        """),
        {
            "id": record["id"],
            "revision": revision,
            "image": image,
            "replicas": replicas,
            "change": change_type,
        },
    )

    return {
        "deployment_id": record["id"],
        "revision": revision,
        "image": image,
        "replicas": replicas,
        "status": "deploying",
        "change_type": change_type,
    }


def locked_owned_record(db, deployment_id, user):
    # Validate the ID and ownership before locking.
    record = get_owned_record(db, deployment_id, user)

    row = db.execute(
        text("""
            SELECT * FROM deployments
            WHERE id=:id AND owner_id=:owner
            FOR UPDATE
        """),
        {"id": record["id"], "owner": user["id"]},
    ).mappings().first()

    if not row or row["status"] == "deleted":
        raise HTTPException(404, "Active deployment not found")

    return dict(row)


@router.patch("/deployments/{deployment_id}")
def update_deployment(
    deployment_id: str,
    payload: DeploymentUpdate,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    if payload.image is None and payload.replicas is None:
        raise HTTPException(422, "Specify image or replicas")

    if (
        payload.image is not None
        and not allowed_development_image(payload.image)
    ):
        raise HTTPException(422, "Image not allowed")

    with db.begin():
        record = locked_owned_record(db, deployment_id, user)

        image = (
            payload.image
            if payload.image is not None
            else record["image"]
        )
        replicas = (
            payload.replicas
            if payload.replicas is not None
            else record["replicas"]
        )

        if image == record["image"] and replicas == record["replicas"]:
            return {
                "deployment_id": record["id"],
                "status": "unchanged",
                "image": image,
                "replicas": replicas,
            }

        return update_revision(
            db, record, image, replicas, "update"
        )


@router.get("/deployments/{deployment_id}/revisions")
def list_revisions(
    deployment_id: str,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    record = get_owned_record(db, deployment_id, user)

    rows = db.execute(
        text("""
            SELECT revision_number, image, replicas,
                   change_type, created_at
            FROM deployment_revisions
            WHERE deployment_id=:id
            ORDER BY revision_number DESC
        """),
        {"id": record["id"]},
    ).mappings().all()

    return [
        {
            **dict(row),
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]


@router.post("/deployments/{deployment_id}/rollback")
def rollback_deployment(
    deployment_id: str,
    payload: RollbackRequest,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    with db.begin():
        record = locked_owned_record(db, deployment_id, user)

        target = db.execute(
            text("""
                SELECT image, replicas
                FROM deployment_revisions
                WHERE deployment_id=:id
                  AND revision_number=:revision
            """),
            {
                "id": record["id"],
                "revision": payload.revision,
            },
        ).mappings().first()

        if not target:
            raise HTTPException(404, "Revision not found")

        if not allowed_development_image(target["image"]):
            raise HTTPException(
                422, "Historical image no longer allowed"
            )

        if (
            target["image"] == record["image"]
            and target["replicas"] == record["replicas"]
        ):
            return {
                "deployment_id": record["id"],
                "status": "unchanged",
                "restored_from": payload.revision,
            }

        result = update_revision(
            db,
            record,
            target["image"],
            target["replicas"],
            "rollback",
        )

        result["restored_from"] = payload.revision
        return result
