FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app
RUN groupadd --system app && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app
COPY app/backend/pyproject.toml .
COPY app/backend/ .
RUN pip install --no-cache-dir -e ".[dev]"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
