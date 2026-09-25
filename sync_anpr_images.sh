#!/usr/bin/env bash
# Seed combined ANPR thumbnails for /recognize_vehicle.
# The cleanup container deletes files in anpr_webhook/images older than 15 days
# (by mtime). Images copied from Downloads often have 2025 timestamps and are
# removed within minutes. This script syncs from the NCPass branch (or Downloads)
# and refreshes mtimes on each stack start.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMBINED_IMAGES="${SCRIPT_DIR}/src/ANPR/anpr_webhook/images"
NCPASS_IMAGES="${SCRIPT_DIR}/../../NCPass/Visitor-Vehicle-Management/src/ANPR/anpr_webhook/images"
DOWNLOADS_IMAGES="${HOME}/Downloads/images"

SOURCE=""
if [[ -d "${NCPASS_IMAGES}" ]] && compgen -G "${NCPASS_IMAGES}/*.jpg" > /dev/null; then
  SOURCE="${NCPASS_IMAGES}"
elif [[ -d "${DOWNLOADS_IMAGES}" ]] && compgen -G "${DOWNLOADS_IMAGES}/*.jpg" > /dev/null; then
  SOURCE="${DOWNLOADS_IMAGES}"
fi

if [[ -z "${SOURCE}" ]]; then
  echo "sync_anpr_images: no ANPR image source found; recognize_vehicle thumbnails may be missing."
  exit 0
fi

mkdir -p "${COMBINED_IMAGES}"
rsync -a "${SOURCE}/" "${COMBINED_IMAGES}/"
find "${COMBINED_IMAGES}" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) -exec touch {} +

COUNT="$(find "${COMBINED_IMAGES}" -type f | wc -l)"
echo "sync_anpr_images: synced ${COUNT} files from ${SOURCE}"
