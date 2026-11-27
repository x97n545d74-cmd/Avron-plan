#!/usr/bin/env bash
# Runs the Avron writer on Render, not on GitHub Actions.
# Every 5 minutes: sync with GitHub, run writer.py, push any new queue lines.
# It never stops on an error: it logs what went wrong, waits and tries again.
# It also keeps a short health report in the branch "render-status" (file status.txt),
# so the state of the writer can be read from GitHub without opening Render.
# The token and the Anthropic key come from Render's environment variables. Never print them.
set -u

REPO="x97n545d74-cmd/avron-plan"
BRANCH="avron-x-merger"
STATUS_BRANCH="render-status"
DIR=/tmp/avron-work
SDIR=/tmp/avron-status
LOG=/tmp/avron-writer.log
NEW=/tmp/avron-new-lines.jsonl
QUEUE="avron-x-merger/queue.jsonl"
WRITER="${AVRON_WRITER:-avron-x-merger/writer.py}"
INTERVAL="${AVRON_INTERVAL:-300}"
export AVRON_STATE="${AVRON_STATE:-/tmp/avron_x_merger_state.json}"

# Hide the two secrets (and anything shaped like one) in whatever is printed or reported.
redact() {
  python3 -c '
import os, re, sys
t = sys.stdin.read()
for k in ("GITHUB_TOKEN", "ANTHROPIC_API_KEY"):
    v = os.environ.get(k, "").strip()
    if len(v) >= 8:
        t = t.replace(v, "[hidden]")
t = re.sub(r"(sk-ant-|github_pat_|ghp_|x-access-token:)[A-Za-z0-9_\-]+", r"\1[hidden]", t)
sys.stdout.write(t)'
}
say() { echo "[worker $(TZ=Asia/Kolkata date '+%H:%M')] $*" | redact; }

if [ -z "${GITHUB_TOKEN:-}" ] && [ -z "${AVRON_REMOTE:-}" ]; then
  say "GITHUB_TOKEN is not set. Add it in Render: avron-writer > Environment, then redeploy."
  sleep 600
  exit 1
fi
REMOTE="${AVRON_REMOTE:-https://x-access-token:${GITHUB_TOKEN:-}@github.com/${REPO}.git}"

STARTED="$(TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M IST')"
ROUNDS=0
WROTE=0
LAST_KEY=""
LAST_PUSH=0

# report "<one-line state>": write status.txt to the status branch.
# Pushes when the state changes, and otherwise at most every 30 minutes.
report() {
  local key="$1" now
  now="$(TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M IST')"
  if [ "$key" = "$LAST_KEY" ] && [ $(( $(date +%s) - LAST_PUSH )) -lt 1800 ]; then return 0; fi
  rm -rf "$SDIR" && mkdir -p "$SDIR"
  {
    echo "updated: $now"
    echo "state: $key"
    echo "worker started: $STARTED"
    echo "rounds run: $ROUNDS"
    echo "rounds that added headlines: $WROTE"
    echo
    echo "last writer output:"
    [ -f "$LOG" ] && tail -n 30 "$LOG"
  } | redact > "$SDIR/status.txt"
  if ( cd "$SDIR" && git init -q && git config user.name "avron-x-merger" \
       && git config user.email "avron-x-merger@users.noreply.github.com" \
       && git add status.txt && git commit -q -m "Writer status $now" \
       && git push -q -f "$REMOTE" "HEAD:refs/heads/$STATUS_BRANCH" ) >/dev/null 2>&1; then
    LAST_KEY="$key"
    LAST_PUSH=$(date +%s)
  else
    say "could not push the status report"
  fi
}

# Clone, and keep trying: a wrong token or a GitHub outage must not kill the worker.
until [ -d "$DIR/.git" ]; do
  rm -rf "$DIR"
  if git clone -q --branch "$BRANCH" "$REMOTE" "$DIR" 2>/tmp/avron-clone.err; then
    break
  fi
  say "clone failed, trying again in 60 seconds. GitHub said: $(tail -n 2 /tmp/avron-clone.err | tr '\n' ' ')"
  say "If this repeats: the GITHUB_TOKEN in Render must be a token for ${REPO} with Contents: Read and write."
  rm -rf "$DIR"
  sleep 60
done
cd "$DIR" || exit 1
git config user.name "avron-x-merger"
git config user.email "avron-x-merger@users.noreply.github.com"
SELF_SUM="$(sha256sum "$0" | cut -d' ' -f1)"
say "started. Repo ${REPO}, branch ${BRANCH}, one round every ${INTERVAL} seconds."


while true; do
  ROUNDS=$((ROUNDS + 1))
  state="OK"

  if ! git fetch -q origin "$BRANCH" 2>/tmp/avron-fetch.err || ! git reset -q --hard "origin/$BRANCH"; then
    say "could not sync with GitHub this round: $(tail -n 2 /tmp/avron-fetch.err | tr '\n' ' ')"
    state="FAILING: cannot read the GitHub repo (check GITHUB_TOKEN)"
  else
    # Pick up a newer copy of this script without waiting for a Render deploy.
    if [ -f render/worker.sh ] && [ "$(sha256sum render/worker.sh | cut -d' ' -f1)" != "$SELF_SUM" ]; then
      say "worker.sh changed in the repo, restarting with the new copy"
      cp render/worker.sh /tmp/avron-worker-next.sh && exec bash /tmp/avron-worker-next.sh
    fi

    python3 "$WRITER" > "$LOG" 2>&1
    rc=$?
    redact < "$LOG"
    if [ "$rc" -ne 0 ]; then
      why="$(grep -m1 -iE 'error|failed|not set' "$LOG" | cut -c1-180)"
      state="FAILING: writer could not run: ${why:-exit code $rc}"
    fi

    # New queue lines = what the writer just appended. Re-apply them on top of the
    # latest GitHub copy so a push from the poster in the same minute never blocks us.
    git diff -U0 -- "$QUEUE" | grep '^+{' | cut -c2- > "$NEW"
    if [ -s "$NEW" ]; then
      n="$(wc -l < "$NEW" | tr -d ' ')"
      pushed=0
      for try in 1 2 3; do
        git fetch -q origin "$BRANCH" 2>/dev/null && git reset -q --hard "origin/$BRANCH" || { sleep 5; continue; }
        [ -n "$(tail -c1 "$QUEUE")" ] && echo >> "$QUEUE"
        cat "$NEW" >> "$QUEUE"
        git add "$QUEUE"
        git commit -q -m "Headlines $(TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M') IST: $n items"
        if git push -q origin "HEAD:$BRANCH" 2>/tmp/avron-push.err; then pushed=1; break; fi
        say "push attempt $try failed: $(tail -n 2 /tmp/avron-push.err | tr '\n' ' ')"
        sleep 5
      done
      if [ "$pushed" -eq 1 ]; then
        WROTE=$((WROTE + 1))
        say "pushed $n new headline(s)"
      else
        state="FAILING: wrote $n headline(s) but cannot push (GITHUB_TOKEN needs Contents: Read and write)"
        git reset -q --hard "origin/$BRANCH" 2>/dev/null
      fi
    fi
  fi

  say "round $ROUNDS done: $state"
  report "$state"
  [ "${AVRON_ONCE:-}" = "1" ] && exit 0
  sleep "$INTERVAL"
done
