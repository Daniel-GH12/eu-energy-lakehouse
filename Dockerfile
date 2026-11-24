FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY dbt/ ./dbt/

RUN pip install --no-cache-dir .

ENTRYPOINT ["python", "-m", "energy_lakehouse.pipeline"]
