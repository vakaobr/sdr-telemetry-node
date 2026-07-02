#!/bin/sh
# Render icecast.xml from env (no secrets baked into the image) and run.
set -eu
: "${ICECAST_SOURCE_PASSWORD:=hackme}"
: "${ICECAST_ADMIN_PASSWORD:=admin}"
export ICECAST_SOURCE_PASSWORD ICECAST_ADMIN_PASSWORD
envsubst < /etc/icecast/icecast.xml.tmpl > /tmp/icecast.xml
exec icecast2 -c /tmp/icecast.xml
