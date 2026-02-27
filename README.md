# teleclaude

**English** | [中文](README_CN.md)

Control [Claude Code](https://docs.anthropic.com/en/docs/claude-code) remotely from Telegram — live streaming, interactive prompts, and autonomous execution.

- **Live streaming** — real-time tool calls and text via transcript JSONL reading
- **Interactive prompts** — selection menus and yes/no forwarded as inline keyboard buttons
- **Autonomous execution** — supports `--dangerously-skip-permissions` for fire-and-forget workflows
- **Shell fallback** — when Claude is not running, commands execute in shell with output returned
- **Claude internal commands** — `/model`, `/cost` etc. forwarded with TUI output captured

## vs. Official Remote Control

| Feature | Official Remote Control | teleclaude |
| --- | --- | --- |
| **Subscription** | Max plan only ($100+/mo) | Any plan or API key |
| **Concurrent sessions** | One per machine | Multiple via tmux |
| **Live streaming** | Final result only | Real-time tool calls + text, every 3s |
| **Autonomous mode** | Must approve each action | Full `--dangerously-skip-permissions` |
| **Session persistence** | ~10 min network outage = timeout | tmux persists indefinitely |
| **Terminal** | Must stay active | tmux background, close terminal anytime |
| **Client** | Claude app or claude.ai/code | Telegram (iOS/Android/Desktop/Web) |
| **Network** | Direct to Anthropic only | Proxy support, works behind firewalls |
| **Shell fallback** | No | Auto shell mode when Claude not running |

## Quick Start

### Prerequisites

```bash
# macOS
brew install tmux cloudflared jq python3
```

### 1. Get a Telegram Bot Token

Message [@BotFather](https://t.me/BotFather) → `/newbot` → save the token.

### 2. Clone & Install

```bash
git clone https://github.com/zihenghe04/teleclaude
cd teleclaude
python3 -m venv .venv && source .venv/bin/activate
```

### 3. Start

```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
./run.sh start
```

This single command will:
- Install Claude Code hooks automatically
- Create a tmux session
- Start the bridge server
- Open a Cloudflare Tunnel
- Set the Telegram webhook

### 4. Launch Claude in tmux

```bash
tmux attach -t claude
claude --dangerously-skip-permissions
```

Now send a message to your bot on Telegram.

## Bot Commands

| Command | Description |
| --- | --- |
| `/status` | Check tmux session status |
| `/stop` | Interrupt Claude (send Escape) |
| `/clear` | Clear Claude conversation |
| `/continue_` | Continue most recent session |
| `/resume` | Pick session to resume (inline keyboard) |
| `/loop <prompt>` | Start Ralph Loop (5 iterations) |

Other `/commands` (like `/model`, `/cost`, `/config`) are forwarded to Claude Code as internal commands.

Regular text messages are sent as prompts. When Claude is not running, messages execute as shell commands.

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

- **Handler**: receives Telegram webhooks, injects messages into tmux via `send-keys`
- **PaneWatcher**: reads transcript JSONL for streaming, monitors for interactive prompts, detects Claude running state
- **Hooks**: `PostToolUse` saves transcript path; `Stop` converts response to HTML and writes to file

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | *(required)* | Bot token from BotFather |
| `TMUX_SESSION` | `claude` | tmux session name |
| `PORT` | `8080` | Bridge HTTP port |
| `TELEGRAM_PROXY` | `http://127.0.0.1:7897` | Proxy for Telegram API |

### Proxy

Default proxy `127.0.0.1:7897` is for environments where Telegram API is blocked (e.g. China). Change `TELEGRAM_PROXY` or edit `bridge.py` to remove.

Cloudflare Tunnel uses QUIC which may conflict with HTTP proxies. `run.sh` starts it with `no_proxy="*"` to bypass.
