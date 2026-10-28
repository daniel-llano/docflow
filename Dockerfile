# API and worker image. Build from the repository root.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY services/api/requirements.txt .
RUN pip install -r requirements.txt && useradd --system --uid 10001 docflow
COPY services/api/app ./app
COPY services/api/alembic ./alembic
COPY services/api/alembic.ini .
USER docflow
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
