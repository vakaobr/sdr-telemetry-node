# Icecast for ATC audio (ADR-007). Debian package = reliable multi-arch (arm64).
# Source/admin passwords injected from env at start so no secrets in the image.
FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends icecast2 gettext-base \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -u 10003 icecast || true
COPY docker/icecast/icecast.xml.tmpl /etc/icecast/icecast.xml.tmpl
COPY docker/icecast/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && mkdir -p /var/log/icecast && chown -R 10003 /var/log/icecast
USER 10003
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
