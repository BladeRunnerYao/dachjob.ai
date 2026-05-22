FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app
COPY apps/api/pyproject.toml .
COPY apps/api/ .
RUN pip install --no-cache-dir -e ".[dev]"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
