#!/usr/bin/env bash
# Issue, list, or revoke read-only GitHub deploy keys for this repository.
# Run on a workstation that already has a clone and an admin `gh` login.
# Private keys are written outside the repo:
#   ${XDG_DATA_HOME:-$HOME/.local/share}/census-counters/deploy-keys/
set -euo pipefail

REPO="CensusCounters/NewVisitorVehicleManagement-Combined"
KEYDIR="${XDG_DATA_HOME:-$HOME/.local/share}/census-counters/deploy-keys"

usage() {
  cat <<'EOF'
Usage:
  scripts/issue_github_deploy_key.sh issue <clientname>
  scripts/issue_github_deploy_key.sh list
  scripts/issue_github_deploy_key.sh revoke <key-id>

Registers a read-only deploy key named census-vv-<clientname> on
CensusCounters/NewVisitorVehicleManagement-Combined.
Requires the GitHub CLI (`gh`), authenticated as a user with admin access to that repository.
One key per machine. Keep the private key mode 600 and delete the workstation copy
after it is installed on the machine.
EOF
}

require_gh() {
  local login admin
  if ! command -v gh >/dev/null 2>&1; then
    echo "gh is required: https://cli.github.com/" >&2
    exit 1
  fi
  if ! gh auth status >/dev/null 2>&1; then
    echo "gh is not logged in. Run: gh auth login" >&2
    exit 1
  fi
  login=$(gh api user --jq .login)
  if ! admin=$(gh api "/repos/${REPO}" --jq .permissions.admin); then
    echo "Cannot read ${REPO}. Confirm this gh login can see that repository." >&2
    exit 1
  fi
  if [ "$admin" != "true" ]; then
    echo "${login} does not have admin access to ${REPO}." >&2
    echo "Deploy keys require admin. GitHub returns HTTP 404 on /repos/${REPO}/keys without it." >&2
    exit 1
  fi
}

valid_client() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,39}$ ]]
}

cmd_list() {
  require_gh
  printf '%s\t%s\t%s\t%s\n' "id" "read_only" "created_at" "title"
  gh api --paginate "/repos/${REPO}/keys" \
    --jq '.[] | [.id, .read_only, .created_at, .title] | @tsv'
}

cmd_revoke() {
  local id="$1"
  local title
  require_gh
  if [[ ! "$id" =~ ^[0-9]+$ ]]; then
    echo "key id must be a number from 'list'." >&2
    exit 1
  fi
  title=$(gh api "/repos/${REPO}/keys/${id}" --jq .title)
  gh api --method DELETE "/repos/${REPO}/keys/${id}" >/dev/null
  echo "Revoked deploy key ${id} (${title}). Delete ~/.ssh/${title} on that machine."
}

cmd_issue() {
  local client="$1"
  local name priv pub id existing
  require_gh
  if ! command -v ssh-keygen >/dev/null 2>&1; then
    echo "ssh-keygen is required (openssh-client)." >&2
    exit 1
  fi
  client="${client#census-vv-}"
  if ! valid_client "$client"; then
    echo "client name must match [A-Za-z0-9][A-Za-z0-9-]{0,39} (example: kupwara)." >&2
    exit 1
  fi
  name="census-vv-${client}"

  existing=$(gh api --paginate "/repos/${REPO}/keys" --jq ".[] | select(.title == \"${name}\") | .id")
  if [ -n "$existing" ]; then
    echo "A deploy key titled '${name}' already exists (id ${existing}). Revoke it before issuing another." >&2
    exit 1
  fi

  install -d -m 700 "$KEYDIR"
  priv="${KEYDIR}/${name}"
  pub="${priv}.pub"
  if [ -e "$priv" ] || [ -e "$pub" ]; then
    echo "Refusing to overwrite ${priv}. Move it aside or pick another client name." >&2
    exit 1
  fi

  # Empty passphrase: git pull on the machine uses the key file and does not ask for a password.
  ssh-keygen -t ed25519 -C "${name} deploy key" -f "$priv" -N "" >/dev/null
  chmod 600 "$priv"

  if ! id=$(gh api --method POST \
    -H "Accept: application/vnd.github+json" \
    "/repos/${REPO}/keys" \
    -f title="$name" \
    -f key="$(cat "$pub")" \
    -F read_only=true \
    --jq .id); then
    rm -f "$priv" "$pub"
    echo "GitHub rejected the key. The local key pair was deleted." >&2
    exit 1
  fi

  echo "Registered read-only deploy key ${id} for ${name}."
  ssh-keygen -lf "$pub"
  echo "Private key on this workstation: ${priv}"
  echo "On the new machine, copy:"
  echo "  scripts/setup_git.sh -> ~/Projects/setup_git.sh"
  echo "  ${priv} -> ~/.ssh/${name}"
  echo "Then run: bash ~/Projects/setup_git.sh ${client}"
  echo "Delete ${priv} from this workstation after the new machine has the key."
}

if [ $# -lt 1 ]; then
  usage >&2
  exit 1
fi

case "$1" in
  issue)
    if [ $# -ne 2 ]; then
      usage >&2
      exit 1
    fi
    cmd_issue "$2"
    ;;
  list)
    if [ $# -ne 1 ]; then
      usage >&2
      exit 1
    fi
    cmd_list
    ;;
  revoke)
    if [ $# -ne 2 ]; then
      usage >&2
      exit 1
    fi
    cmd_revoke "$2"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
