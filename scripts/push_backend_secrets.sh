#!/usr/bin/env bash
# Upload every entry in the backend dotenv file as a GitHub Actions repository secret.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${project_root}/.env"
repo=""

usage() {
  cat <<'EOF'
Usage: scripts/push_backend_secrets.sh [--env-file PATH] [--repo OWNER/REPO]

Upload all entries from the backend .env file as GitHub Actions repository secrets.
Defaults to the repository containing this script and its root .env file.
Requires GitHub CLI authentication (`gh auth login`).
EOF
}

while (($#)); do
  case "$1" in
    --env-file|--repo)
      if (($# < 2)) || [[ -z "$2" ]]; then
        echo "Missing value for $1" >&2
        exit 2
      fi
      if [[ "$1" == "--env-file" ]]; then env_file="$2"; else repo="$2"; fi
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "$env_file" || ! -r "$env_file" ]]; then
  echo "Backend env file is missing or unreadable: $env_file" >&2
  exit 1
fi
duplicate_keys="$(awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/ { if (seen[$1]++) print $1 }' "$env_file" | sort -u)"
if [[ -n "$duplicate_keys" ]]; then
  echo "Duplicate env key(s); keep one assignment per key before uploading:" >&2
  echo "$duplicate_keys" >&2
  exit 1
fi
if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required." >&2
  exit 1
fi

if [[ -z "$repo" ]]; then
  repo="$(cd "$project_root" && gh repo view --json nameWithOwner --jq .nameWithOwner)"
fi
if [[ ! "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "Invalid repository; use --repo OWNER/REPO." >&2
  exit 1
fi

echo "Uploading backend environment entries to GitHub Actions secrets in $repo."
gh secret set --app actions --repo "$repo" --env-file "$env_file"
echo "Backend secrets uploaded to $repo."
