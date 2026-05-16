#!/usr/bin/env bash
# Claude Code status line — bash
# Reads JSON from stdin, prints one line to stdout.

set -eu

input="$(cat)"
[ -z "$input" ] && exit 0

if ! command -v jq >/dev/null 2>&1; then
  printf "[statusline: install jq]"
  exit 0
fi

model="$(printf '%s' "$input" | jq -r '.model.display_name // "claude"')"
cwd="$(printf '%s' "$input" | jq -r '.workspace.current_dir // ""')"
dir="$(basename "${cwd:-$HOME}")"

branch=""
if [ -n "$cwd" ] && [ -d "$cwd" ]; then
  b="$(git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  [ -n "$b" ] && branch=" ($b)"
fi

cost="$(printf '%s' "$input" | jq -r '.cost.total_cost_usd // empty')"
cost_str=""
if [ -n "$cost" ]; then
  cost_str=" \$$(awk -v c="$cost" 'BEGIN { if (c+0 >= 1) printf "%.2f", c; else printf "%.3f", c }')"
fi

CYAN=$'\e[36m'
GREEN=$'\e[32m'
GRAY=$'\e[90m'
YELLOW=$'\e[33m'
RESET=$'\e[0m'

printf "%s[%s]%s %s%s%s%s%s%s%s%s%s" \
  "$CYAN" "$model" "$RESET" \
  "$GREEN" "$dir" "$RESET" \
  "$GRAY" "$branch" "$RESET" \
  "$YELLOW" "$cost_str" "$RESET"
