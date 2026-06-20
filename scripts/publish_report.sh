#!/usr/bin/env bash
# Publish report.html to the unlisted GitHub Pages mirror as index.html.
#
#   scripts/publish_report.sh [report.html]
#
# The target repo (an opaque-slug public repo) is read from WCB_REPORT_REPO so
# the "secret" URL never lands in this repo's git history (it open-sources later).
# report.html already carries a noindex meta; the slug is the soft password.
set -euo pipefail

# load .env (for WCB_REPORT_REPO) if present
if [ -f .env ]; then set -a; . ./.env; set +a; fi

src="${1:-report.html}"
repo="${WCB_REPORT_REPO:-}"
[ -n "$repo" ] || { echo "set WCB_REPORT_REPO=owner/slug in .env first"; exit 1; }
[ -f "$src" ] || { echo "no $src — run scripts/visualize.py first"; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
git clone -q "https://github.com/$repo.git" "$tmp"
cp "$src" "$tmp/index.html"
touch "$tmp/.nojekyll"
git -C "$tmp" add -A
if git -C "$tmp" diff --cached --quiet; then
  echo "no change to publish"
  exit 0
fi
git -C "$tmp" commit -q -m "Update arena report"
git -C "$tmp" push -q
echo "published -> https://${repo%%/*}.github.io/${repo#*/}/"
