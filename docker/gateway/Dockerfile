# gateway — multi-stage, ARM64-first (Pi 3B), runs as non-root
FROM python:3.12-slim AS build
WORKDIR /src
# deps layer first: app-code changes don't re-resolve dependencies (slow on Pi)
COPY docker/gateway/requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
COPY services/gateway/pyproject.toml ./
COPY services/gateway/app ./app
RUN pip install --no-cache-dir --no-deps --prefix=/install .

FROM python:3.12-slim
RUN useradd -r -u 10001 gateway \
    && mkdir -p /data/tiles /data/media \
    && chown -R gateway /data   # named volume inherits this ownership on first use
COPY --from=build /install /usr/local
COPY shared/config/config.example.yaml /config/config.example.yaml
USER gateway
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).status==200 else 1)"]
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
