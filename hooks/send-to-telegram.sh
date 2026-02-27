#!/bin/bash
# Claude Code Stop hook — writes formatted response for the bridge watcher to send.
# The watcher (bridge.py) is the sole Telegram sender. No race conditions.
#
# Install: cp hooks/send-to-telegram.sh ~/.claude/hooks/
#          chmod +x ~/.claude/hooks/send-to-telegram.sh

INPUT=$(cat)
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path')
PENDING_FILE=~/.claude/telegram_pending
RESPONSE_FILE=~/.claude/telegram_hook_response

# Only from the telegram-connected tmux session
[ -z "$TMUX" ] && exit 0
CURRENT_SESSION=$(tmux display-message -p '#S' 2>/dev/null)
[ "$CURRENT_SESSION" != "claude" ] && exit 0

# Save transcript path for the watcher (so it follows the right session)
[ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ] && \
    echo "$TRANSCRIPT_PATH" > ~/.claude/telegram_transcript_path

[ ! -f "$TRANSCRIPT_PATH" ] && exit 0

LAST_USER_LINE=$(grep -n '"type":"user"' "$TRANSCRIPT_PATH" | tail -1 | cut -d: -f1)
[ -z "$LAST_USER_LINE" ] && exit 0

TMPFILE=$(mktemp)
tail -n "+$LAST_USER_LINE" "$TRANSCRIPT_PATH" | \
  grep '"type":"assistant"' | \
  jq -rs '[.[].message.content[] | select(.type == "text") | .text] | join("\n\n")' > "$TMPFILE" 2>/dev/null

[ ! -s "$TMPFILE" ] && rm -f "$TMPFILE" && exit 0

python3 - "$TMPFILE" "$RESPONSE_FILE" << 'PYEOF'
import sys, json, os, re

tmpfile, response_file = sys.argv[1], sys.argv[2]
with open(tmpfile) as f:
    text = f.read().strip()

if not text or text == "null":
    sys.exit(0)

if len(text) > 4000:
    text = text[:4000] + "\n..."

def to_html(s):
    blocks, inlines = [], []
    s = re.sub(r'```(\w*)\n?(.*?)```', lambda m: (blocks.append((m.group(1), m.group(2))), f"\x00B{len(blocks)-1}\x00")[1], s, flags=re.DOTALL)
    s = re.sub(r'`([^`\n]+)`', lambda m: (inlines.append(m.group(1)), f"\x00I{len(inlines)-1}\x00")[1], s)
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', s)
    esc = lambda t: t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    for i, (lang, code) in enumerate(blocks):
        s = s.replace(f"\x00B{i}\x00", f'<pre>{esc(code.strip())}</pre>')
    for i, code in enumerate(inlines):
        s = s.replace(f"\x00I{i}\x00", f'<code>{esc(code)}</code>')
    return s

html = to_html(text)

# Atomic write: tmp file then rename (prevents watcher reading partial JSON)
tmp = response_file + ".tmp"
with open(tmp, "w") as f:
    json.dump({"html": html, "text": text}, f)
os.rename(tmp, response_file)
PYEOF

rm -f "$TMPFILE" "$PENDING_FILE"
exit 0
