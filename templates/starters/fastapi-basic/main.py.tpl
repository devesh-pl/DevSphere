from fastapi import FastAPI

app = FastAPI(title="{{PROJECT_NAME}}")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "{{PROJECT_SLUG}}"
    }


@app.get("/")
def home():
    return {
        "message": "Welcome to {{PROJECT_NAME}}"
    }
