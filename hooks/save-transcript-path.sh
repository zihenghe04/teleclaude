#!/bin/bash
# PostToolUse hook — save transcript path for the Telegram bridge watcher.
# Scoped to tmux "claude" session only. Lightweight: just writes one line.
#
# Install: cp hooks/save-transcript-path.sh ~/.claude/hooks/
#          chmod +x ~/.claude/hooks/save-transcript-path.sh

[ -z "$TMUX" ] && exit 0
CURRENT_SESSION=$(tmux display-message -p '#S' 2>/dev/null)
[ "$CURRENT_SESSION" != "claude" ] && exit 0

INPUT=$(cat)
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')
[ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ] && \
    echo "$TRANSCRIPT_PATH" > ~/.claude/telegram_transcript_path
exit 0
