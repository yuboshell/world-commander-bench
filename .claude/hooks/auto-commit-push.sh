#!/usr/bin/env bash
# Stop-hook: auto-commit and push when the working tree has changes.
# Wired up in .claude/settings.json. No-op on a clean tree (e.g. pure
# conversational turns). .env, runs/, venvs are gitignored, so secrets and
# large run outputs never get committed.
set -uo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$root" || exit 0

# Nothing staged or unstaged or untracked -> nothing to do.
if [ -z "$(git status --porcelain)" ]; then
  exit 0
fi

ts="$(date '+%Y-%m-%d %H:%M:%S %Z')"
git add -A
git commit -q \
  -m "auto: session checkpoint ${ts}" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" \
  || exit 0

branch="$(git rev-parse --abbrev-ref HEAD)"
if git push -q origin "$branch" 2>/tmp/wcb-autopush.err; then
  printf '{"systemMessage": "auto-commit + push OK (%s) on %s"}\n' "$ts" "$branch"
else
  err="$(tr '\n' ' ' < /tmp/wcb-autopush.err)"
  printf '{"systemMessage": "auto-commit done but PUSH FAILED: %s"}\n' "$err"
fi
