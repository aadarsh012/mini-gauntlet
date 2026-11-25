# ---- build stage: install dependencies into a virtualenv ----
FROM python:3.12.8-slim-bookworm AS build
RUN python -m venv /venv
COPY requirements.txt .
RUN /venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- final stage: just the venv and our code, running as a non-root user ----
FROM python:3.12.8-slim-bookworm
ENV PATH="/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INVENTORY_PATH=/app/data/inventory.json \
    DB_PATH=/data/mini_gauntlet.db
RUN useradd --create-home --uid 10001 app && mkdir /data && chown app:app /data
COPY --from=build /venv /venv
WORKDIR /app
COPY app ./app
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=2)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
