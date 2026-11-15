#!/usr/bin/env bash
# Install (or uninstall) the pm-* skills at user level by symlinking each
# skills/<name>/ folder of this repo into the agents' user skill directories:
#
#   Claude Code: ~/.claude/skills   (override with CLAUDE_SKILLS_DIR)
#   Codex:       ~/.agents/skills   (override with CODEX_SKILLS_DIR)
#
# It also registers the pm-lint hook (hooks/pm_lint_hook.py) in:
#
#   Claude Code: ~/.claude/settings.json   (override with CLAUDE_SETTINGS)
#   Codex:       ~/.codex/hooks.json       (override with CODEX_HOOKS)
#
# Usage: ./install.sh [--uninstall]
#
# Safe to re-run: correct links are left alone, links to skills that no longer
# exist in this repo are removed, and anything that isn't a symlink into this
# repo is never touched. Only the pm-lint hook entries are added to or removed
# from the settings files; everything else in them is kept.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SKILLS_DIR="$REPO_DIR/skills"
TARGET_DIRS=(
  "${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
  "${CODEX_SKILLS_DIR:-$HOME/.agents/skills}"
)
HOOK_SETTINGS=(
  "${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"
  "${CODEX_HOOKS:-$HOME/.codex/hooks.json}"
)

uninstall=false
case "${1:-}" in
  "") ;;
  --uninstall) uninstall=true ;;
  -h|--help) sed -n '2,19s/^# \{0,1\}//p' "$0"; exit 0 ;;
  *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
esac

status=0

# Remove links in $1 that point into this repo's skills/ but whose target is
# gone (or all of them when uninstalling).
prune() {
  local target_dir=$1 link dest
  for link in "$target_dir"/*; do
    [[ -L "$link" ]] || continue
    dest="$(readlink "$link")"
    [[ "$dest" == "$SKILLS_DIR"/* ]] || continue
    if $uninstall || [[ ! -f "$dest/SKILL.md" ]]; then
      rm "$link"
      echo "removed: $link"
    fi
  done
}

install() {
  local target_dir=$1 skill name link
  mkdir -p "$target_dir"
  for skill in "$SKILLS_DIR"/*/; do
    skill="${skill%/}"
    [[ -f "$skill/SKILL.md" ]] || continue
    name="$(basename "$skill")"
    link="$target_dir/$name"
    if [[ -L "$link" && "$(readlink "$link")" == "$skill" ]]; then
      echo "ok:      $link"
    elif [[ -e "$link" || -L "$link" ]]; then
      echo "skipped: $link already exists and isn't a link to $skill" >&2
      status=1
    else
      ln -s "$skill" "$link"
      echo "linked:  $link -> $skill"
    fi
  done
}

for target_dir in "${TARGET_DIRS[@]}"; do
  [[ -d "$target_dir" ]] && prune "$target_dir"
  $uninstall || install "$target_dir"
done

for settings in "${HOOK_SETTINGS[@]}"; do
  "${PYTHON:-python3}" "$REPO_DIR/hooks/register_hooks.py" "$($uninstall && echo uninstall || echo install)" "$settings" \
    || status=1
done

exit $status
