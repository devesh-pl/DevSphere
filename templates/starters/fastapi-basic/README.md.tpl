# {{PROJECT_NAME}}

Generated using the DevSphere FastAPI starter template.

## Run locally

Install dependencies:

    python -m pip install -r requirements.txt

Start the application:

    uvicorn main:app --reload

API documentation:

    http://localhost:8000/docs

## Docker

Build the image:

    docker build -t {{PROJECT_SLUG}} .

Start the container:

    docker run --rm -p 8000:8000 {{PROJECT_SLUG}}

## Health endpoint

GET /health
