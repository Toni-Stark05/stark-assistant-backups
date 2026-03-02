#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

STATUS=$(git status --porcelain)
if [ -z "$STATUS" ]; then
  echo "No changes to back up"
  exit 0
fi

STAMP=$(TZ=UTC+3 date +"%Y-%m-%d %H:%M:%S %Z")
COMMIT_MSG="backup: ${STAMP}"

git add -A
git commit -m "$COMMIT_MSG"
git push origin master
