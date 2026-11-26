#!/usr/bin/env bash
# Runs the Avron writer on Render, not on GitHub Actions.
# Every 5 minutes: pull, run writer.py, and push queue.jsonl only if it changed.
# The token and the Anthropic key come from Render's environment variables. Never print them.
set -u
: "${GITHUB_TOKEN:?GITHUB_TOKEN is not set}"
: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY is not set}"
REPO="x97n545d74-cmd/avron-plan"
BRANCH="avron-x-merger"
DIR=/tmp/avron-work

rm -rf "$DIR"
git clone -q --branch "$BRANCH" "https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO}.git" "$DIR" || { echo "clone failed"; exit 1; }
cd "$DIR"
git config user.name "avron-x-merger"
git config user.email "avron-x-merger@users.noreply.github.com"

while true; do
  git pull -q --rebase origin "$BRANCH" || echo "pull failed this round"
  python3 avron-x-merger/writer.py || echo "writer failed this round"
  if ! git diff --quiet -- avron-x-merger/queue.jsonl; then
    git add avron-x-merger/queue.jsonl
    git commit -q -m "Headlines $(TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M') IST"
    git pull -q --rebase origin "$BRANCH"
    git push -q origin "HEAD:$BRANCH" || echo "push failed this round"
  fi
  sleep 300
done
