#!/usr/bin/env bash
# Copy this repository to another machine over SSH, keeping .git so the
# destination stays a real clone. TensorRT engines are not copied: they only
# load on the GPU and TensorRT version that built them. ONNX models are copied.
#
# Usage: ./scripts/sync_to_host.sh <user@host> [dest]
# SSH must already work (key or agent). The default destination is
# ~/Projects/NewVisitorVehicleManagement-Combined on the remote host.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/sync_to_host.sh <user@host> [dest]

rsync this repository to dest on the host (default
~/Projects/NewVisitorVehicleManagement-Combined). Keeps .git. Leaves the
remote .env, compose file and helper scripts in place, and does not copy
TensorRT engines, .venv, .idea or __pycache__.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ $# -lt 1 ] || [ $# -gt 2 ]; then
  usage >&2
  [ $# -ge 1 ] && [ $# -le 2 ] && exit 0
  exit 1
fi

host="$1"
dest="${2:-~/Projects/NewVisitorVehicleManagement-Combined}"
root="$(cd "$(dirname "$0")/.." && pwd)"

rsync -az --delete \
  --exclude '.venv/' \
  --exclude '.idea/' \
  --exclude '__pycache__/' \
  --exclude 'src/fr_engine/models/trt-engines/' \
  --exclude 'docker-compose-*.yml' \
  --exclude '.env' \
  --exclude 'build_all_containers.sh' \
  --exclude 'run_all_containers.sh' \
  --exclude 'stop_all_containers.sh' \
  -e "ssh -o StrictHostKeyChecking=accept-new" \
  "$root/" "${host}:${dest}/"

echo "Synced $root to ${host}:${dest}"
