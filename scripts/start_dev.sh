#!/usr/bin/env bash
# scripts/start_dev.sh — Start the backend API and serve the standalone UI.
# Usage: bash scripts/start_dev.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "╔══════════════════════════════════════════════════╗"
echo "║  Autonomous AI Scientist — Dev Server            ║"
echo "╚══════════════════════════════════════════════════╝"

# Determine Python
if [ -f "$PROJECT_ROOT/.venv/Scripts/python.exe" ]; then
  PYTHON="$PROJECT_ROOT/.venv/Scripts/python.exe"
elif [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
  PYTHON="$PROJECT_ROOT/.venv/bin/python"
else
  PYTHON="python"
fi

echo "[1/2] Starting FastAPI backend on http://localhost:8000"
cd "$PROJECT_ROOT/backend"
$PYTHON -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "[2/2] Serving standalone UI on http://localhost:8080"
cd "$PROJECT_ROOT/ui"
$PYTHON -m http.server 8080 &
UI_PID=$!

echo ""
echo "  Backend API:   http://localhost:8000"
echo "  Standalone UI: http://localhost:8080"
echo "  API docs:      http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "echo 'Shutting down...'; kill $BACKEND_PID $UI_PID 2>/dev/null; exit 0" INT TERM
wait
