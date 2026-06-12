# radio2 supervisor — Node B. ARM64-first (Pi 3B), non-root, tini PID-1.
#
# Decoder binaries (rtl_airband, AIS-catcher, satdump) are layered in per their
# milestone (P8/P9/P10). Phase 7 ships the supervisor + Python deps; the
# decoders are exercised in CI/dev via the scripted fake (RADIO2_FAKE).
FROM python:3.12-slim AS build
WORKDIR /src
COPY docker/radio2/requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
COPY services/radio2/pyproject.toml ./
COPY services/radio2/app ./app
RUN pip install --no-cache-dir --no-deps --prefix=/install .

FROM python:3.12-slim
# tini reaps decoder children; tzdata for schedule-block local time; rtl-sdr
# userland + the decoders are added on their milestone branches.
RUN apt-get update && apt-get install -y --no-install-recommends tini tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -u 10002 radio2 \
    && mkdir -p /data && chown radio2 /data
COPY --from=build /install /usr/local
USER radio2
ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "app.main"]
