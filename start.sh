#!/bin/bash
set -e
cd "$(dirname "$0")"

# Load .env if present
[ -f .env ] && export $(grep -v '^#' .env | xargs)

# Default CWD to current dir if not set
VIBE_WALK_CWD="${VIBE_WALK_CWD:-$(pwd)}"
export VIBE_WALK_CWD
PORT="${PORT:-8000}"

echo "Working dir: $VIBE_WALK_CWD"
echo ""

# ── Optional: start Kokoro TTS via Docker ─────────────────────────────────────
if command -v docker &>/dev/null; then
  echo "Starting Kokoro TTS (Docker)…"
  docker compose up -d kokoro 2>/dev/null || echo "  (Kokoro not started — will fall back to macOS say)"
else
  echo "Docker not found — TTS will use macOS say command"
fi
echo ""

# ── Tailscale HTTPS setup ─────────────────────────────────────────────────────
SSL_KEYFILE=""
SSL_CERTFILE=""
TAILSCALE_HOST=""

if command -v tailscale &>/dev/null; then
  TAILSCALE_HOST=$(tailscale status --json 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Self',{}).get('DNSName','').rstrip('.'))" \
    2>/dev/null || true)
fi

if [ -n "$TAILSCALE_HOST" ]; then
  echo "Tailscale host: $TAILSCALE_HOST"
  tailscale cert "$TAILSCALE_HOST" 2>/dev/null || true
  if [ -f "${TAILSCALE_HOST}.key" ] && [ -f "${TAILSCALE_HOST}.crt" ]; then
    SSL_KEYFILE="${TAILSCALE_HOST}.key"
    SSL_CERTFILE="${TAILSCALE_HOST}.crt"
    echo "Phone URL: https://${TAILSCALE_HOST}:${PORT}"
  else
    echo "TLS cert not available. Running HTTP on all interfaces."
    echo "Phone URL (Tailscale IP): http://$(tailscale ip -4 2>/dev/null | head -1):${PORT}"
    echo ""
    echo "To enable HTTPS, run in your tailnet admin panel:"
    echo "  https://login.tailscale.com/admin/dns -> enable HTTPS certificates"
    echo "  then re-run this script"
  fi
else
  echo "No Tailscale — HTTP only (localhost)"
  echo "Phone URL: http://$(ipconfig getifaddr en0 2>/dev/null || echo 'YOUR_IP'):${PORT}"
fi
echo ""

# ── Start server ──────────────────────────────────────────────────────────────
if [ -n "$SSL_KEYFILE" ]; then
  exec .venv/bin/uvicorn server.main:app \
    --host 0.0.0.0 --port "$PORT" \
    --ssl-keyfile "$SSL_KEYFILE" --ssl-certfile "$SSL_CERTFILE"
else
  exec .venv/bin/uvicorn server.main:app --host 0.0.0.0 --port "$PORT"
fi
