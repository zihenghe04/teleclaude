# teleclaude

[English](README.md) | **中文**

通过 Telegram 远程控制 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — 实时流式输出、交互式提示转发、自主执行。

- **实时流式输出** — 通过读取 transcript JSONL 实时显示工具调用和文本
- **交互式提示** — 选择菜单和 yes/no 确认通过 inline keyboard 按钮转发
- **自主执行** — 支持 `--dangerously-skip-permissions`，发完任务去喝杯咖啡
- **Shell 回退** — Claude 未运行时，命令直接在 shell 中执行并返回结果
- **Claude 内部命令** — `/model`、`/cost` 等命令直接通过 Telegram 发送

## 对比官方 Remote Control

| 特性 | 官方 Remote Control | teleclaude |
| --- | --- | --- |
| **订阅要求** | 仅 Max 计划（$100+/月） | 无限制，API key 或任何订阅 |
| **并发会话** | 每台机器一个 | 通过 tmux 支持多个 |
| **实时输出** | 仅显示最终结果 | 实时工具调用 + 文本，每 3 秒更新 |
| **自主模式** | 每步需手动批准 | 完全支持 `--dangerously-skip-permissions` |
| **会话持久性** | 网络中断 ~10 分钟后超时 | tmux 永久保持 |
| **终端要求** | 必须保持活跃 | tmux 后台运行，终端随便关 |
| **客户端** | Claude 官方 App 或 claude.ai/code | Telegram（iOS/Android/桌面/网页） |
| **网络环境** | 需直连 Anthropic | 支持代理，国内可用 |
| **Shell 回退** | 不支持 | Claude 退出后自动切换 shell |

**核心优势：**

1. **放养式开发** — 发送任务后无需盯屏，Claude 自主完成后 Telegram 通知你
2. **实时可见** — 实时看到 Claude 在读哪个文件、执行什么命令、写了什么代码
3. **零门槛** — 不需要 Max 订阅，不需要特定客户端，一个 Telegram 就够
4. **国内友好** — 内置代理支持 + Cloudflare Tunnel 穿透

## 快速开始

### 环境准备

```bash
# macOS
brew install tmux cloudflared jq python3
```

### 1. 获取 Telegram Bot Token

在 Telegram 找 [@BotFather](https://t.me/BotFather) → `/newbot` → 保存 token。

### 2. 克隆 & 安装

```bash
git clone https://github.com/zihenghe04/teleclaude
cd teleclaude
python3 -m venv .venv && source .venv/bin/activate
```

### 3. 一键启动

```bash
export TELEGRAM_BOT_TOKEN="你的token"
./run.sh start
```

这一条命令会自动完成：
- 安装 Claude Code hooks（自动，无需手动复制）
- 创建 tmux 会话
- 启动 bridge 服务
- 开启 Cloudflare Tunnel
- 设置 Telegram webhook

### 4. 在 tmux 中启动 Claude

```bash
tmux attach -t claude
claude --dangerously-skip-permissions
```

然后去 Telegram 给你的 bot 发消息就行了。

## Bot 命令

| 命令 | 说明 |
| --- | --- |
| `/status` | 查看 tmux 会话状态 |
| `/stop` | 中断 Claude（发送 Escape） |
| `/clear` | 清除 Claude 对话 |
| `/continue_` | 继续最近的会话 |
| `/resume` | 选择要恢复的会话（inline keyboard） |
| `/loop <prompt>` | 启动 Ralph Loop（5 次迭代） |

其他 `/command`（如 `/model`、`/cost`、`/config`）作为 Claude Code 内部命令转发。

普通文本消息发给 Claude 作为提示词。Claude 未运行时，消息作为 shell 命令执行。

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

- **Handler**：接收 webhook，通过 `send-keys` 注入 tmux
- **PaneWatcher**：读取 transcript 实现流式输出，监控交互提示，检测 Claude 运行状态
- **Hooks**：`PostToolUse` 保存 transcript 路径；`Stop` 转换响应为 HTML 写入文件

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | *（必填）* | BotFather 的 token |
| `TMUX_SESSION` | `claude` | tmux 会话名称 |
| `PORT` | `8080` | Bridge HTTP 端口 |
| `TELEGRAM_PROXY` | `http://127.0.0.1:7897` | Telegram API 代理 |

### 代理

默认代理 `127.0.0.1:7897` 适用于国内环境。修改 `TELEGRAM_PROXY` 或编辑 `bridge.py` 移除。

Cloudflare Tunnel 使用 QUIC 协议，可能和 HTTP 代理冲突。`run.sh` 用 `no_proxy="*"` 绕过。
