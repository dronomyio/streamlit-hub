#!/usr/bin/env bash
set -euo pipefail
#
APP_NAME="${APP_NAME:-app}"
APP_FILE="${APP_FILE:-app.py}"
#
# Install deps if present (per-app requirements)
if [ -f "/app/requirements.txt" ]; then
  pip install --no-cache-dir -r /app/requirements.txt
fi
#
exec streamlit run "/app/${APP_FILE}" \
  --server.address=0.0.0.0 \
  --server.port=8501 \
  --server.baseUrlPath="app/${APP_NAME}"
