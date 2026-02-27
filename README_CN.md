# teleclaude

[English](README.md) | **中文**

通过 Telegram 远程控制 [Claude Code](https://docs.anthropic.com/en/docs/claude-code)。实时流式输出、交互式提示转发、自主执行。

- **基于 Transcript 的实时流式输出** — 通过读取 JSONL transcript 实现工具调用和文本的实时更新
- **单发送者架构** — hook 写文件，watcher 统一发送到 Telegram，避免竞态条件
- **交互式提示转发** — 选择菜单和 yes/no 确认通过 inline keyboard 按钮转发
- **Shell 回退模式** — Claude 未运行时，命令直接在 shell 中执行并返回结果
- **Claude 内部命令** — `/model`、`/cost` 等内部命令转发并捕获 TUI 输出

## 与官方 Remote Control 的对比

Anthropic 于 2026 年 2 月发布了 Claude Code Remote Control 功能，允许通过手机/平板远程控制本地 Claude Code 会话。以下是本项目与官方方案的对比：

| 特性 | 官方 Remote Control | teleclaude |
| --- | --- | --- |
| **订阅要求** | 仅 Max 计划（Pro 即将支持），不支持 Team/Enterprise/API | 无限制，API key 或任何订阅均可 |
| **并发会话** | 每台机器仅支持一个会话 | 通过 tmux 支持多个会话 |
| **实时流式输出** | 仅显示最终结果 | 实时显示工具调用和中间文本，每 3 秒更新 |
| **自主执行** | 不支持 `--dangerously-skip-permissions`，每步需手动批准 | 完全支持自主执行，适合放养式开发 |
| **交互式提示** | 通过官方 UI 操作 | Telegram inline keyboard 按钮，随时随地操作 |
| **会话持久性** | 网络中断约 10 分钟后超时断开 | tmux 会话永久保持，断网无影响 |
| **终端要求** | 本地终端必须保持活跃 | tmux 后台运行，终端可关闭 |
| **客户端** | 需使用 Claude 官方 App 或 claude.ai/code | Telegram 全平台客户端（手机/电脑/网页） |
| **网络环境** | 需直连 Anthropic 服务器 | 支持代理，适合国内网络环境 |
| **Shell 回退** | 不支持 | Claude 未运行时自动切换到 shell 模式 |
| **内部命令** | 通过 UI 操作 | `/model`、`/cost` 等命令直接通过 Telegram 发送 |
| **已知问题** | "Contact your administrator" 报错 | 稳定运行 |
| **费用** | 需 Max 计划（$100/月起） | 免费开源 + 任意 API 计划 |

**核心优势总结：**

1. **放养式开发**：支持 `--dangerously-skip-permissions`，发送任务后无需盯着屏幕，Claude 自主完成后通过 Telegram 通知你
2. **实时可见**：不是等最终结果，而是实时看到 Claude 在做什么——正在读哪个文件、执行什么命令、写了什么代码
3. **零门槛**：不需要 Max 订阅，不需要特定客户端，一个 Telegram 就够了
4. **国内友好**：内置代理支持，Cloudflare Tunnel 穿透，无需担心网络问题

## 架构

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

**Handler**：接收 Telegram webhook，通过 `send-keys` 将消息注入 tmux。

**PaneWatcher**（后台线程）：

1. 读取 Claude Code transcript JSONL 实现流式输出（工具调用、文本）
2. 读取 hook 响应文件获取最终格式化 HTML 响应
3. 监控 tmux pane 的交互式提示（选择菜单、y/n 确认）
4. 检测 Claude 是否运行并清理过期状态

**Hooks**（Claude Code 侧）：

- `PostToolUse` → 保存 transcript 路径，确保 watcher 跟踪正确的会话
- `Stop` → 提取响应文本，Markdown 转 HTML，写入响应文件

## 环境要求

- Python 3.10+
- tmux
- cloudflared（Cloudflare Tunnel）
- jq（hooks 脚本需要）

```bash
# macOS
brew install tmux cloudflared jq
```

## 安装

```bash
git clone https://github.com/zihenghe04/teleclaude
cd teleclaude
python3 -m venv .venv && source .venv/bin/activate
```

## 配置

### 1. 创建 Telegram Bot

在 Telegram 中找 [@BotFather](https://t.me/BotFather)，创建一个 bot，保存 token。

### 2. 安装 Claude Code Hooks

```bash
cp hooks/send-to-telegram.sh ~/.claude/hooks/
cp hooks/save-transcript-path.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh
```

在 `~/.claude/settings.json` 中添加：

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

### 3. 启动 tmux 会话

```bash
tmux new -s claude
claude --dangerously-skip-permissions
```

### 4. 运行

使用一键脚本：

```bash
# 先编辑 run.sh —— 设置 BOT_TOKEN
./run.sh start
```

或手动启动：

```bash
export TELEGRAM_BOT_TOKEN="your_token"
python bridge.py &

# 通过 Cloudflare Tunnel 暴露服务
cloudflared tunnel --url http://localhost:8080

# 设置 webhook（替换 URL）
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=https://YOUR-TUNNEL.trycloudflare.com"
```

## Bot 命令

| 命令 | 说明 |
| --- | --- |
| `/status` | 查看 tmux 会话状态 |
| `/stop` | 中断 Claude（发送 Escape） |
| `/clear` | 清除 Claude 对话 |
| `/continue_` | 继续最近的会话 |
| `/resume` | 选择要恢复的会话（inline keyboard） |
| `/loop <prompt>` | 启动 Ralph Loop（5 次迭代） |

其他 `/command`（如 `/model`、`/cost`、`/config`）会作为 Claude Code 内部命令转发。

普通文本消息发送给 Claude Code 作为提示词。当 Claude 未在 tmux 会话中运行时，消息作为 shell 命令执行并返回输出。

## 功能特性

### 实时流式输出

Claude 响应期间，bot 发送实时更新，显示工具调用和中间文本，每 3 秒通过读取 transcript JSONL 更新一次。

### 交互式提示

当 Claude 显示选择菜单或 yes/no 提示时，通过 Telegram inline keyboard 按钮转发，方便操作。

### 最终格式化响应

Claude 完成后，Stop hook 将 Markdown 响应转换为 Telegram HTML（粗体、斜体、代码块、行内代码），替换实时消息。

### Shell 回退

当 Claude 未在 tmux 会话中运行时，消息发送到 shell 并捕获输出返回。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | *��必填）* | BotFather 提供的 bot token |
| `TMUX_SESSION` | `claude` | tmux 会话名称 |
| `PORT` | `8080` | Bridge HTTP 端口 |
| `TELEGRAM_PROXY` | `http://127.0.0.1:7897` | Telegram API 代理（国内使用） |

## 代理说明

默认代理 (`127.0.0.1:7897`) 适用于无法直接访问 Telegram API 的网络环境（如中国大陆）。设置 `TELEGRAM_PROXY` 为你的代理地址，或修改 `bridge.py` 移除代理。

Cloudflare Tunnel (`cloudflared`) 使用 QUIC 协议，可能与 HTTP 代理冲突。`run.sh` 脚本使用 `no_proxy="*"` 绕过代理设置。
