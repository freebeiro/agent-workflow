#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 [--replace-agents] [--ref REF] TARGET_PROJECT" >&2
  exit 2
}

replace_agents=false
ref="main"
while (($#)); do
  case "$1" in
    --replace-agents) replace_agents=true; shift ;;
    --ref) (($# >= 2)) || usage; ref="$2"; shift 2 ;;
    -h|--help) usage ;;
    -*) usage ;;
    *) break ;;
  esac
done

(( $# == 1 )) || usage
target=$(cd "$1" 2>/dev/null && pwd -P) || {
  echo "Target project does not exist: $1" >&2
  exit 1
}

source_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
staging=""
if [[ ! -d "$source_root/.agents" ]]; then
  command -v curl >/dev/null || { echo "curl is required for remote installation." >&2; exit 1; }
  command -v tar >/dev/null || { echo "tar is required for remote installation." >&2; exit 1; }
  staging=$(mktemp -d)
  trap 'rm -rf "$staging"' EXIT
  curl -fsSL "https://github.com/freebeiro/agent-workflow/archive/refs/heads/${ref}.tar.gz" | tar -xzf - -C "$staging"
  source_root=$(find "$staging" -mindepth 1 -maxdepth 1 -type d -print -quit)
fi

mkdir -p "$target/.agents"

if [[ "$source_root" == "$target" ]]; then
  echo "Refusing to install the workflow repository into itself." >&2
  exit 1
fi

cp -R "$source_root/.agents/." "$target/.agents/"

if [[ -e "$target/AGENTS.md" && "$replace_agents" != true ]]; then
  echo "Installed .agents/; preserved existing AGENTS.md."
  echo "Review and merge the shared contract into: $target/AGENTS.md"
else
  if [[ -e "$target/AGENTS.md" ]]; then
    backup="$target/AGENTS.md.backup.$(date +%Y%m%d%H%M%S)"
    cp "$target/AGENTS.md" "$backup"
    echo "Backed up existing AGENTS.md to $backup"
  fi
  cp "$source_root/AGENTS.md" "$target/AGENTS.md"
  echo "Installed shared AGENTS.md."
fi

printf 'Installed shared agent workflow at %s (source ref: %s)\n' "$target/.agents" "$ref"
