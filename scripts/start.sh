#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT_DIR="$PWD"
if [ ! -x backend/venv/bin/python ] || [ ! -d frontend/node_modules ]; then
  echo 'Run ./scripts/setup.sh first.' >&2; exit 1
fi
make -C native/cpp
if [ ! -f frontend/.next/BUILD_ID ]; then (cd frontend && npm run build); fi
mkdir -p work
(cd backend && exec ./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000) > work/backend.log 2>&1 &
BACKEND_PID=$!
(cd frontend && exec ./node_modules/.bin/next start --hostname 127.0.0.1 --port 3000) > work/frontend.log 2>&1 &
FRONTEND_PID=$!
cleanup(){ kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
sleep 2
kill -0 "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || { cat work/backend.log work/frontend.log; exit 1; }
echo 'UI: http://127.0.0.1:3000/dashboard/overview'
echo 'API: http://127.0.0.1:8000/docs'
echo 'Press Ctrl+C to stop both. Logs: work/backend.log and work/frontend.log'
wait
