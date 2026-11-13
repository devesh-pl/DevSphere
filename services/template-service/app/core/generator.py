from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.core.config import settings


TEMPLATES = {
    "fastapi-basic": {
        "id": "fastapi-basic",
        "name": "FastAPI Starter",
        "language": "Python",
        "framework": "FastAPI",
    },
    "express-basic": {
        "id": "express-basic",
        "name": "Express Starter",
        "language": "JavaScript",
        "framework": "Express",
    },
}


def list_templates():
    return list(TEMPLATES.values())


def generate_project(template_id: str, project_slug: str) -> bytes:
    if template_id not in TEMPLATES:
        raise ValueError("Unknown template")

    if not (
        3 <= len(project_slug) <= 63
        and __import__("re").fullmatch(
            r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", project_slug
        )
    ):
        raise ValueError("Invalid project name")

    root = settings.template_root.resolve()
    directory = (root / template_id).resolve()

    if not directory.is_relative_to(root) or not directory.is_dir():
        raise ValueError("Template unavailable")

    variables = {
        "{{PROJECT_SLUG}}": project_slug,
        "{{PROJECT_NAME}}": project_slug.replace("-", " ").title(),
    }

    buffer = BytesIO()
    total_size = 0

    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        files = sorted(directory.rglob("*"))

        for file in files:
            if file.is_symlink():
                raise ValueError("Symbolic links are not supported")

            if not file.is_file():
                continue

            relative = file.relative_to(directory)
            content = file.read_bytes()

            if file.suffix == ".tpl":
                text = content.decode("utf-8")
                for key, value in variables.items():
                    text = text.replace(key, value)
                content = text.encode("utf-8")
                relative = relative.with_suffix("")

            total_size += len(content)
            if total_size > 2 * 1024 * 1024:
                raise ValueError("Template too large")

            archive.writestr(
                str(Path(project_slug) / relative),
                content,
            )

    return buffer.getvalue()
