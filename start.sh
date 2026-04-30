#!/usr/bin/env bash
# IVC Dashboard 2026 — start both backend and frontend
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Starting IVC Dashboard 2026..."

# Kill any existing instances
pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "vite.*ivc" 2>/dev/null || true
sleep 1

# Start backend
echo "⚙️  Starting FastAPI backend on port 8000..."
cd "$SCRIPT_DIR/backend"
.venv/bin/uvicorn main:app --port 8000 --log-level warning &
BACKEND_PID=$!

# Wait for backend to be ready
echo "⏳ Waiting for data to load (~10s)..."
for i in {1..20}; do
  sleep 1
  if curl -s http://localhost:8000/api/health 2>/dev/null | grep -q "ok"; then
    echo "✅ Backend ready!"
    break
  fi
done

# Start frontend
echo "🎨 Starting React frontend..."
cd "$SCRIPT_DIR/frontend"
npm run dev -- --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!
sleep 3

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   IVC Deep Analysis Dashboard 2026           ║"
echo "║                                              ║"
echo "║   Frontend: http://localhost:5173            ║"
echo "║   Backend:  http://localhost:8000/api/health ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "Press Ctrl+C to stop both servers."

# Wait for both
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" INT TERM
wait
