# teleclaude

**English** | [中文](README_CN.md)

Control [Claude Code](https://docs.anthropic.com/en/docs/claude-code) from Telegram — live streaming, interactive prompts, and autonomous execution.

- **Transcript-based live streaming** — real-time tool call and text updates via JSONL transcript reading
- **Single-sender architecture** — hook writes file, watcher sends to Telegram, no race conditions
- **Interactive prompt forwarding** — selection menus and yes/no prompts with inline keyboard buttons
- **Shell fallback** — when Claude is not running, commands execute in shell and return clean output
- **Claude internal commands** — `/model`, `/cost` etc. forwarded with TUI output captured

## Comparison with Official Remote Control

Anthropic released Claude Code Remote Control (Feb 2026), which lets you control a local Claude Code session from phone/tablet via their app. Here's how this project compares:

| Feature | Official Remote Control | teleclaude |
| --- | --- | --- |
| **Subscription** | Max plan only (Pro coming), no Team/Enterprise/API | Any plan or API key |
| **Concurrent sessions** | One session per machine | Multiple via tmux |
| **Live streaming** | Final result only | Real-time tool calls and text, updated every 3s |
| **Autonomous execution** | No `--dangerously-skip-permissions`, manual approval needed | Full autonomous execution |
| **Interactive prompts** | Via official UI | Telegram inline keyboard buttons |
| **Session persistence** | ~10 min network outage = timeout | tmux session persists indefinitely |
| **Terminal requirement** | Local terminal must stay active | tmux runs in background |
| **Client** | Claude app or claude.ai/code | Telegram (all platforms) |
| **Network** | Direct connection to Anthropic | Proxy support, works behind firewalls |
| **Shell fallback** | No | Auto-switches to shell when Claude not running |
| **Internal commands** | Via UI | `/model`, `/cost` etc. via Telegram |
| **Cost** | Max plan ($100+/mo) | Free + any API plan |

## Architecture

```
Telegram ──webhook──> Cloudflare Tunnel ──> Bridge (bridge.py :8080)
                                                │
                                  ┌─────────────┼─────────────┐
                                  ▼             ▼             ▼
                              Handler      PaneWatcher    Hooks
                            (HTTP POST)   (background)   (Claude)
                                │             │             │
                                │ tmux        │ read        │ write
                                │ send-keys   │ transcript  │ response
                                ▼             ▼             ▼
                            ┌─────────────────────────────────┐
                            │  tmux session "claude"          │
                            │  └── Claude Code                │
                            │       └── transcript.jsonl      │
                            └─────────────────────────────────┘
```

**Handler**: receives Telegram webhooks, injects messages into tmux via `send-keys`.

**PaneWatcher** (background thread):

1. Reads Claude Code transcript JSONL for live streaming (tool calls, text)
2. Reads hook response file for final formatted HTML response
3. Monitors tmux pane for interactive prompts (selection menus, y/n)
4. Detects when Claude is not running and cleans up stale state

**Hooks** (Claude Code side):

- `PostToolUse` → saves transcript path so watcher follows the correct session
- `Stop` → extracts response text, converts Markdown to HTML, writes to response file

## Prerequisites

- Python 3.10+
- tmux
- cloudflared (Cloudflare Tunnel)
- jq (for hooks)

```bash
# macOS
brew install tmux cloudflared jq
```

## Install

```bash
git clone https://github.com/zihenghe04/teleclaude
cd teleclaude
python3 -m venv .venv && source .venv/bin/activate
```

## Setup

### 1. Create Telegram Bot

Message [@BotFather](https://t.me/BotFather) on Telegram, create a bot, and save the token.

### 2. Install Claude Code Hooks

```bash
cp hooks/send-to-telegram.sh ~/.claude/hooks/
cp hooks/save-transcript-path.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh
```

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/save-transcript-path.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/send-to-telegram.sh"
          }
        ]
      }
    ]
  }
}
```

### 3. Start tmux Session

```bash
tmux new -s claude
claude --dangerously-skip-permissions
```

### 4. Run

Use the one-click script:

```bash
# Edit run.sh first — set BOT_TOKEN
./run.sh start
```

Or manually:

```bash
export TELEGRAM_BOT_TOKEN="your_token"
python bridge.py &

# Expose via Cloudflare Tunnel
cloudflared tunnel --url http://localhost:8080

# Set webhook (replace URL)
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=https://YOUR-TUNNEL.trycloudflare.com"
```

## Bot Commands


| Command          | Description                              |
| ---------------- | ---------------------------------------- |
| `/status`        | Check tmux session status                |
| `/stop`          | Interrupt Claude (send Escape)           |
| `/clear`         | Clear Claude conversation                |
| `/continue_`     | Continue most recent session             |
| `/resume`        | Pick session to resume (inline keyboard) |
| `/loop <prompt>` | Start Ralph Loop (5 iterations)          |


Any other `/command` (like `/model`, `/cost`, `/config`) is forwarded to Claude Code as an internal command.

Regular text messages are sent to Claude Code as prompts. When Claude is not running in the tmux session, messages are executed as shell commands with output returned.

## Features

### Live Streaming

During Claude's response, the bot sends live updates showing tool calls and intermediate text, updated every 3 seconds via transcript JSONL reading.

### Interactive Prompts

When Claude shows selection menus or yes/no prompts, they're forwarded to Telegram with inline keyboard buttons for easy interaction.

### Final Formatted Response

When Claude finishes, the Stop hook converts the Markdown response to Telegram HTML (bold, italic, code blocks, inline code) and replaces the live message.

### Shell Fallback

When Claude is not running in the tmux session, messages are sent to the shell and output is captured and returned.

## Environment Variables


| Variable             | Default                 | Description                              |
| -------------------- | ----------------------- | ---------------------------------------- |
| `TELEGRAM_BOT_TOKEN` | *(required)*            | Bot token from BotFather                 |
| `TMUX_SESSION`       | `claude`                | tmux session name                        |
| `PORT`               | `8080`                  | Bridge HTTP port                         |
| `TELEGRAM_PROXY`     | `http://127.0.0.1:7897` | Proxy for Telegram API (useful in China) |


## Proxy Note

The default proxy (`127.0.0.1:7897`) is configured for environments where Telegram API is not directly accessible (e.g., China mainland). Set `TELEGRAM_PROXY` to your proxy, or modify `bridge.py` to remove proxy if not needed.

Cloudflare Tunnel (`cloudflared`) uses QUIC protocol which may conflict with HTTP proxies. The `run.sh` script starts it with `no_proxy="*"` to bypass proxy settings.