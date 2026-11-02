#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x backend/venv/bin/python ]; then python3 -m venv backend/venv; fi
backend/venv/bin/python -m pip install -r backend/requirements.txt
make -C native/cpp
cd frontend
npm install --legacy-peer-deps
npm run build
