#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 [--replace-agents] [--no-watch] [--ref REF] --project-id ID TARGET_PROJECT" >&2
  exit 2
}

replace_agents=false
activate_watch=true
ref="main"
project_id=""
while (($#)); do
  case "$1" in
    --replace-agents) replace_agents=true; shift ;;
    --no-watch) activate_watch=false; shift ;;
    --project-id) (($# >= 2)) || usage; project_id="$2"; shift 2 ;;
    --ref) (($# >= 2)) || usage; ref="$2"; shift 2 ;;
    -h|--help) usage ;;
    -*) usage ;;
    *) break ;;
  esac
done

[[ $# -eq 1 && -n "$project_id" ]] || usage
[[ "$project_id" =~ ^[A-Za-z0-9._-]+$ ]] || {
  echo "Project id must contain only letters, numbers, dots, underscores, or hyphens." >&2
  exit 2
}
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

if [[ "$activate_watch" == true && "$(uname -s)" == "Darwin" ]]; then
  runtime_root="${CODEX_HOME:-$HOME/.codex}/agent-workflow/$project_id"
  mkdir -p "$runtime_root/control-plane" "$runtime_root/state" "$HOME/Library/LaunchAgents"
  for file in checkin.py watcher.py dispatcher_wake.py codex_watch.py; do
    cp "$source_root/.agents/control-plane/$file" "$runtime_root/control-plane/$file"
    chmod +x "$runtime_root/control-plane/$file"
  done
  label="com.codex.agent-workflow.$project_id.codex-watch"
  plist="$HOME/Library/LaunchAgents/$label.plist"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  python3 - "$plist" "$runtime_root" "$label" <<'PY'
import pathlib
import sys

plist, root, label = map(pathlib.Path, sys.argv[1:])
state = root / "state"
script = root / "control-plane" / "codex_watch.py"
plist.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>{label}</string>
<key>ProgramArguments</key><array>
<string>/usr/bin/python3</string><string>{script}</string><string>{state}</string>
<string>--signal</string><string>{state / "dispatcher-check-required.json"}</string>
<string>--interval-seconds</string><string>2</string>
</array>
<key>WorkingDirectory</key><string>{root}</string>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>/tmp/{label}.log</string>
<key>StandardErrorPath</key><string>/tmp/{label}.err.log</string>
</dict></plist>\n''', encoding="utf-8")
PY
  launchctl bootstrap "gui/$(id -u)" "$plist"
  launchctl kickstart -k "gui/$(id -u)/$label"
  printf 'Activated local watcher for project %s at %s\n' "$project_id" "$runtime_root"
else
  printf 'Watcher activation skipped; install the shared runtime manually for this host.\n'
fi
