#!/bin/sh
# One isolated agent run. $1 = arm (lint|mcp|nolint), $2 = run number.
# Env: MODEL (default haiku), EFFORT, RUNS (output folder). The mcp arm reads mcp.json here.
AB="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$AB/../.." && pwd)"
export PATH="$REPO/.venv/Scripts:$REPO/.venv/bin:$PATH"
export CLAUDE_CODE_DISABLE_CLAUDE_MDS=1 CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
PROMPT="$(cat "$AB/task.txt")"
case "$1" in lint|mcp|nolint) ;; *) echo "arm must be lint, mcp or nolint" >&2; exit 2 ;; esac
case "$2" in ""|*[!0-9]*) echo "run must be a number" >&2; exit 2 ;; esac
dir="$AB/${RUNS:-runs}/$1_$2"
rm -rf "$dir" && mkdir -p "$dir"
case "$1" in
  lint) extra="--plugin-dir $REPO --allowedTools Bash(robocop:*)" ;;
  mcp) extra="--mcp-config $AB/mcp.json --allowedTools mcp__robocop"
       PROMPT="$PROMPT You can check the file with the robocop MCP tools." ;;
  *) extra="" ;;
esac
cd "$dir" && claude -p "$PROMPT" --model ${MODEL:-haiku} ${EFFORT:+--effort $EFFORT} --permission-mode acceptEdits \
  --allowedTools "Bash(robot:*)" \
  --setting-sources project --disable-slash-commands --strict-mcp-config \
  --no-session-persistence --output-format stream-json --verbose $extra \
  > "$dir.jsonl" 2> "$dir.err"
