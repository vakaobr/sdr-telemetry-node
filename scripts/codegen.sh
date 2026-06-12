#!/usr/bin/env bash
# Regenerate typed models from shared/schemas (single source of truth).
# CI runs this then `git diff --exit-code` on generated paths — drift fails the build.
set -euo pipefail
cd "$(dirname "$0")/.."

WS=shared/schemas/ws.schema.json
MQTT=shared/schemas/mqtt.schema.json

PY_COMMON_ARGS=(
  --input-file-type jsonschema
  --output-model-type pydantic_v2.BaseModel
  --target-python-version 3.11
  --use-union-operator
  --use-schema-description
  --disable-timestamp
)

echo "==> pydantic models (gateway)"
datamodel-codegen "${PY_COMMON_ARGS[@]}" \
  --input "$WS" --output services/gateway/app/models/generated_ws.py
datamodel-codegen "${PY_COMMON_ARGS[@]}" \
  --input "$MQTT" --output services/gateway/app/models/generated_mqtt.py

echo "==> pydantic models (radio2: mqtt only)"
datamodel-codegen "${PY_COMMON_ARGS[@]}" \
  --input "$MQTT" --output services/radio2/app/models/generated_mqtt.py

echo "==> typescript types (web)"
BANNER="/* AUTO-GENERATED from shared/schemas — do not edit. Run scripts/codegen.sh */"
(cd web && npx --no-install json2ts -i "../$WS" -o src/types/generated/ws.ts \
  --bannerComment "$BANNER" --additionalProperties false)
(cd web && npx --no-install json2ts -i "../$MQTT" -o src/types/generated/mqtt.ts \
  --bannerComment "$BANNER" --additionalProperties false)

echo "==> done"
