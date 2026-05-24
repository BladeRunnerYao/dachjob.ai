FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app
RUN groupadd --system app && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

ARG GIT_BRANCH=unknown
ARG GIT_COMMIT_SHA=unknown

COPY app/backend/pyproject.toml .
COPY app/backend/ .
RUN pip install --no-cache-dir -e ".[dev]"

RUN echo "{\"branch\": \"${GIT_BRANCH}\", \"commit\": \"${GIT_COMMIT_SHA}\"}" > /app/version.json

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
