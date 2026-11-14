FROM python:3.14-slim

WORKDIR /app

COPY services/deployment-service/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY services/deployment-service/app ./app

RUN useradd -u 10001 -m appuser

USER 10001

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
