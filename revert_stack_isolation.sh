#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

restore_file() {
  local target="$1"
  local baseline="${target}.baseline"
  if [[ ! -f "$baseline" ]]; then
    echo "Missing baseline: $baseline" >&2
    exit 1
  fi
  cp "$baseline" "$target"
  echo "Restored $target"
}

restore_file "docker-compose-census-counters-visitor-vehicle.yml"
restore_file "nginx/nginx.conf"
restore_file "stop_all_containers.sh"

if [[ -f ".env" ]]; then
  rm -f ".env"
  echo "Removed .env"
fi

if [[ -f "src/frontend/finalfrsproject/__init__.py.baseline" ]]; then
  restore_file "src/frontend/finalfrsproject/__init__.py"
fi

if [[ -f "src/frontend/finalfrsproject/helpers/auth_helper.py.baseline" ]]; then
  restore_file "src/frontend/finalfrsproject/helpers/auth_helper.py"
fi

if [[ -f "src/frontend/finalfrsproject/routes.py.baseline-parallel" ]]; then
  cp "src/frontend/finalfrsproject/routes.py.baseline-parallel" "src/frontend/finalfrsproject/routes.py"
  echo "Restored src/frontend/finalfrsproject/routes.py from routes.py.baseline-parallel"
fi

echo "Combined stack isolation reverted to pre-isolation settings."
echo "Recreate combined webservice after revert: docker compose -f docker-compose-census-counters-visitor-vehicle.yml --profile visitor_vehicle up -d --force-recreate census_counters_webservice_fr census_counters_nginx"
