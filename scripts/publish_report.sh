#!/usr/bin/env bash
# RETIRED. This pushed report.html to a public GitHub Pages repo; that pattern
# (auto-created public repo + frequent automated pushes) triggered a GitHub
# account suspension on 2026-06-20. Do not use.
#
# The report is now served PRIVATELY:
#   - Local SSH tunnel:     scripts/serve_report.sh   (zero pushes)
#   - Private GitLab Pages: push report.html to GitLab; .gitlab-ci.yml deploys it,
#                           restricted to project members (pages_access_level=private).
echo "publish_report.sh is RETIRED (caused a GitHub suspension). Use scripts/serve_report.sh"
echo "for a local private view, or push to GitLab (private Pages via .gitlab-ci.yml)."
exit 1
