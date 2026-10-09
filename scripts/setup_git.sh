#!/usr/bin/env bash
# Install git, use the deploy key at ~/.ssh/census-vv-<clientname>, and clone this repository.
# This file lives at ~/Projects/setup_git.sh on the new machine.
# Usage: bash ~/Projects/setup_git.sh <clientname>
set -euo pipefail

REPO_SSH="git@github.com:CensusCounters/NewVisitorVehicleManagement-Combined.git"
REPO_GREETING="CensusCounters/NewVisitorVehicleManagement-Combined"
DEST="$HOME/Projects/NewVisitorVehicleManagement-Combined"

usage() {
  cat <<'EOF'
Usage: bash ~/Projects/setup_git.sh <clientname>

The private key must already be at ~/.ssh/census-vv-<clientname>.
Installs git, configures that key for github.com, and clones this repository
into ~/Projects/NewVisitorVehicleManagement-Combined.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi
if [ $# -ne 1 ]; then
  usage >&2
  exit 1
fi

client="${1#census-vv-}"
if [[ ! "$client" =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,39}$ ]]; then
  echo "client name must match [A-Za-z0-9][A-Za-z0-9-]{0,39} (example: kupwara)." >&2
  exit 1
fi

key_name="census-vv-${client}"
identity="$HOME/.ssh/$key_name"
config="$HOME/.ssh/config"
install -d -m 700 "$HOME/.ssh"
if [ ! -f "$identity" ]; then
  echo "Put the private key at ${identity}" >&2
  exit 1
fi
chmod 600 "$identity"

sudo apt-get update
sudo apt-get install -y git openssh-client

if [ -f "$config" ] && grep -q "IdentityFile ${identity}" "$config"; then
  :
elif [ -f "$config" ] && grep -q '^Host github.com$' "$config"; then
  echo "Host github.com is already set in ${config}." >&2
  echo "Point its IdentityFile at ${identity}, or remove that Host block, then run this script again." >&2
  exit 1
else
  cat >> "$config" << EOF

Host github.com
  HostName github.com
  User git
  IdentityFile ${identity}
  IdentitiesOnly yes
EOF
fi
chmod 600 "$config"

set +e
greeting=$(ssh -T git@github.com 2>&1)
status=$?
set -e
printf '%s\n' "$greeting"
if [ "$status" -ne 1 ] || ! printf '%s\n' "$greeting" | grep -q "$REPO_GREETING"; then
  echo "GitHub did not accept ${key_name}." >&2
  exit 1
fi

if [ -d "$DEST/.git" ]; then
  echo "Repository already present at ${DEST}"
else
  if [ -e "$DEST" ]; then
    echo "${DEST} exists and is not a git checkout." >&2
    exit 1
  fi
  mkdir -p "$HOME/Projects"
  git clone "$REPO_SSH" "$DEST"
fi

echo "Ready: ${DEST}"
