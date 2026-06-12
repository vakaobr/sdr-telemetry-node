# radio2 supervisor — Node B. ARM64-first (Pi 3B), non-root, tini PID-1.
# Bundles rtl_airband (ATC, P8). AIS-catcher (P9) + satdump (P10) layer in later.

# -- rtl_airband build (RTLSDR-Airband, with SoapySDR for remote SDR) ----------
FROM debian:trixie-slim AS airband
RUN apt-get update && apt-get install -y --no-install-recommends \
      git ca-certificates cmake build-essential pkg-config \
      libusb-1.0-0-dev librtlsdr-dev libmp3lame-dev libshout3-dev \
      libconfig++-dev libfftw3-dev libsoapysdr-dev \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch v5.0.1 \
      https://github.com/charlie-foxtrot/RTLSDR-Airband.git /src
WORKDIR /src/build
# SOAPYSDR=ON enables the remote SDR source (capture-on-A / decode-on-B, ADR-009)
RUN cmake -DPLATFORM=native -DNFM=ON -DSOAPYSDR=ON .. && make -j"$(nproc)" && make install
# → /usr/local/bin/rtl_airband

# -- python deps --------------------------------------------------------------
FROM python:3.12-slim AS build
WORKDIR /pysrc
COPY docker/radio2/requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
COPY services/radio2/pyproject.toml ./
COPY services/radio2/app ./app
RUN pip install --no-cache-dir --no-deps --prefix=/install .

# -- runtime ------------------------------------------------------------------
FROM python:3.12-slim
# Soapy: install ONLY the rtlsdr + remote modules. A full host install pulls all
# 12 device modules (uhd/audio/...) which collide on load — "Hash collision!!!
# Fatal error!!" (found live 2026-06-12). Two modules → no conflict; the pinned
# SOAPY_SDR_PLUGIN_PATH is belt-and-suspenders.
RUN apt-get update && apt-get install -y --no-install-recommends \
      tini tzdata \
      librtlsdr0 libmp3lame0 libshout3 libconfig++9v5 libfftw3-single3 libusb-1.0-0 \
      libsoapysdr0.8 soapysdr-module-rtlsdr soapysdr-module-remote \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -u 10002 radio2 \
    && mkdir -p /data /run && chown radio2 /data /run
COPY --from=airband /usr/local/bin/rtl_airband /usr/local/bin/rtl_airband
COPY --from=build /install /usr/local
ENV SOAPY_SDR_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/SoapySDR/modules0.8
USER radio2
ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "app.main"]
