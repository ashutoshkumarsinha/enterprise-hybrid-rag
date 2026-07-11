#!/usr/bin/env bash
# Sync Langfuse API keys from observability headless-init into query/.env (IF-5).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OBS_ENV="${OBS_ENV_FILE:-$ROOT/observability/.env}"
QUERY_ENV="${QUERY_ENV_FILE:-$ROOT/query/.env}"
ENV_SET="${ROOT}/scripts/env_set.py"

PY=python3
if [[ -x "$ROOT/query/.venv/bin/python" ]]; then PY="$ROOT/query/.venv/bin/python"; fi

if [[ ! -f "$OBS_ENV" ]]; then
  chmod +x "$ROOT/observability/scripts/ensure_langfuse_init.sh"
  OBS_ENV_FILE="$OBS_ENV" "$ROOT/observability/scripts/ensure_langfuse_init.sh"
fi

read_env() {
  "$PY" -c '
import re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8")
for line in text.splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
    if not m:
        continue
    key, val = m.group(1), m.group(2)
    if len(val) >= 2 and val[0] == val[-1] == "\"":
        val = val[1:-1].replace("\\\\", "\\").replace("\\\"", "\"")
    print(f"{key}={val}")
' "$OBS_ENV"
}

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  key="${line%%=*}"
  val="${line#*=}"
  export "$key=$val"
done < <(read_env)

PUBLIC_KEY="${LANGFUSE_PUBLIC_KEY:-${LANGFUSE_INIT_PROJECT_PUBLIC_KEY:-}}"
SECRET_KEY="${LANGFUSE_SECRET_KEY:-${LANGFUSE_INIT_PROJECT_SECRET_KEY:-}}"
HOST="${LANGFUSE_HOST:-http://langfuse:3000}"

if [[ -z "$PUBLIC_KEY" || -z "$SECRET_KEY" ]]; then
  echo "FAIL: Langfuse keys missing in $OBS_ENV (run observability/scripts/ensure_langfuse_init.sh)" >&2
  exit 1
fi

if [[ ! -f "$QUERY_ENV" ]]; then
  cp "$ROOT/query/.env.example" "$QUERY_ENV"
fi

echo "==> Langfuse keys → $QUERY_ENV"
"$PY" "$ENV_SET" "$QUERY_ENV" LANGFUSE_PUBLIC_KEY "$PUBLIC_KEY"
"$PY" "$ENV_SET" "$QUERY_ENV" LANGFUSE_SECRET_KEY "$SECRET_KEY"
"$PY" "$ENV_SET" "$QUERY_ENV" LANGFUSE_HOST "$HOST"

# Wait for Langfuse health when stack is up
LF_URL="${LANGFUSE_PUBLIC_URL:-http://127.0.0.1:${LANGFUSE_PORT:-3000}}"
if curl -sf "${LF_URL%/}/api/public/health" >/dev/null 2>&1; then
  echo "OK: Langfuse healthy at $LF_URL"
else
  echo "WARN: Langfuse not reachable at $LF_URL (keys written; start observability stack)"
fi

echo "OK: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY set in query/.env"
