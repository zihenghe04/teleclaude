#!/usr/bin/env python3
"""Claude Code <-> Telegram Bridge"""

import os
import json
import re
import subprocess
import threading
import time
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

TMUX_SESSION = os.environ.get("TMUX_SESSION", "claude")
CHAT_ID_FILE = os.path.expanduser("~/.claude/telegram_chat_id")
PENDING_FILE = os.path.expanduser("~/.claude/telegram_pending")
HOOK_RESPONSE_FILE = os.path.expanduser("~/.claude/telegram_hook_response")
HISTORY_FILE = os.path.expanduser("~/.claude/history.jsonl")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", "8080"))
PROXY = os.environ.get("TELEGRAM_PROXY", "http://127.0.0.1:7897")

_proxy_handler = urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
_opener = urllib.request.build_opener(_proxy_handler)

BOT_COMMANDS = [
    {"command": "clear", "description": "Clear conversation"},
    {"command": "resume", "description": "Resume session (shows picker)"},
    {"command": "continue_", "description": "Continue most recent session"},
    {"command": "loop", "description": "Ralph Loop: /loop <prompt>"},
    {"command": "stop", "description": "Interrupt Claude (Escape)"},
    {"command": "status", "description": "Check tmux status"},
]

BLOCKED_COMMANDS = []


def telegram_api(method, data):
    if not BOT_TOKEN:
        return None
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"}
    )
    try:
        with _opener.open(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"Telegram API {method}: {e}")
        return None


def setup_bot_commands():
    result = telegram_api("setMyCommands", {"commands": BOT_COMMANDS})
    if result and result.get("ok"):
        print("Bot commands registered")


def send_typing_loop(chat_id):
    while os.path.exists(PENDING_FILE):
        telegram_api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
        time.sleep(4)


def tmux_exists():
    return subprocess.run(["tmux", "has-session", "-t", TMUX_SESSION], capture_output=True).returncode == 0


def claude_running_in_tmux():
    """Check if a Claude Code process is running inside the tmux pane."""
    try:
        pane_pid = subprocess.check_output(
            ["tmux", "display-message", "-t", TMUX_SESSION, "-p", "#{pane_pid}"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        if not pane_pid:
            return False
        # Check for claude child process
        result = subprocess.run(
            ["pgrep", "-P", pane_pid, "-f", "claude"],
            capture_output=True
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def tmux_send(text, literal=True):
    cmd = ["tmux", "send-keys", "-t", TMUX_SESSION]
    if literal:
        cmd.append("-l")
    cmd.append(text)
    subprocess.run(cmd)


def tmux_send_enter():
    subprocess.run(["tmux", "send-keys", "-t", TMUX_SESSION, "Enter"])


def tmux_send_escape():
    subprocess.run(["tmux", "send-keys", "-t", TMUX_SESSION, "Escape"])


def get_recent_sessions(limit=5):
    if not os.path.exists(HISTORY_FILE):
        return []
    sessions = []
    try:
        with open(HISTORY_FILE) as f:
            for line in f:
                try:
                    sessions.append(json.loads(line.strip()))
                except:
                    continue
    except:
        return []
    sessions.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return sessions[:limit]


def get_session_id(project_path):
    encoded = project_path.replace("/", "-").lstrip("-")
    for prefix in [f"-{encoded}", encoded]:
        project_dir = Path.home() / ".claude" / "projects" / prefix
        if project_dir.exists():
            jsonls = list(project_dir.glob("*.jsonl"))
            if jsonls:
                return max(jsonls, key=lambda p: p.stat().st_mtime).stem
    return None


class PaneWatcher(threading.Thread):
    """Monitors Claude's transcript for live updates and tmux for interactive prompts."""
    daemon = True

    POLL_INTERVAL = 2    # seconds between checks
    LIVE_INTERVAL = 3    # seconds between live message updates
    IDLE_THRESHOLD = 4   # seconds of tmux stability for interactive detection
    COOLDOWN = 15        # minimum seconds between interactive prompt forwards

    INTERACTIVE_PATTERNS = [
        '(y/n)', '(Y/n)', '(yes/no)',
        'Do you want', 'Would you like',
        'approve', 'proceed?', 'continue?',
        'Plan mode',
        'Enter to select',
        'Esc to cancel',
        'Tab/Arrow keys',
    ]

    # Lines matching any of these patterns are TUI chrome, not content
    NOISE_PATTERNS = [
        'bypass permissions',
        'shift+tab to cycle',
        'esc to interrupt',
        'Enter to select',
        'to navigate',
        'Esc to cancel',
        'Press Enter to send',
        '⏵⏵',
    ]

    def __init__(self):
        super().__init__()
        # Tmux state (for interactive prompt detection only)
        self.last_content = ""
        self.tmux_stable_since = time.time()
        self.last_forwarded = ""
        self.last_forward_time = 0
        # Live streaming state
        self.live_msg_id = None
        self.last_live_text = ""
        self.last_live_update = 0
        # Transcript-based streaming
        self._transcript_path = None
        self._transcript_pos = 0
        self._last_scan = 0
        self._response_parts = []
        # Hook writes response to file; watcher is sole Telegram sender
        self.hook_msg_id = None
        # Track pending file mtime to detect new user messages from Telegram
        self._pending_mtime = 0

    def run(self):
        time.sleep(10)
        # Initialize transcript position to current end (skip history)
        t = self._find_transcript()
        if t:
            self._transcript_path = t
            try:
                self._transcript_pos = os.path.getsize(t)
            except OSError:
                pass
        while True:
            try:
                self._tick()
            except Exception as e:
                print(f"Watcher: {e}")
            time.sleep(self.POLL_INTERVAL)

    # ── Transcript reading ──────────────────────────────────────────

    TRANSCRIPT_HINT = os.path.expanduser("~/.claude/telegram_transcript_path")

    def _find_transcript(self):
        """Find the tmux claude session's transcript via hint file from hooks."""
        now = time.time()
        if (self._transcript_path
                and now - self._last_scan < 10
                and os.path.exists(self._transcript_path)):
            return self._transcript_path
        self._last_scan = now

        # Read the hint file written by PostToolUse / Stop hooks
        try:
            with open(self.TRANSCRIPT_HINT) as f:
                path = f.read().strip()
            if path and os.path.exists(path):
                return path
        except (FileNotFoundError, IOError):
            pass

        # No hint available yet — don't guess (avoids picking wrong session)
        return None

    def _read_transcript(self):
        """Read new entries from the active transcript. Returns True if new text found."""
        path = self._find_transcript()
        if not path:
            return False
        if path != self._transcript_path:
            self._transcript_path = path
            try:
                self._transcript_pos = os.path.getsize(path)
            except OSError:
                self._transcript_pos = 0
            self._response_parts = []
            self.live_msg_id = None
            self.last_live_text = ""
            self.hook_msg_id = None
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size <= self._transcript_pos:
            return False
        grew = False
        try:
            with open(path) as f:
                f.seek(self._transcript_pos)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(entry, dict):
                        continue
                    etype = entry.get("type")
                    if etype == "user":
                        msg_content = entry.get("message", {}).get("content")
                        # String content = human message; list = tool_result
                        if isinstance(msg_content, str):
                            # Actual user message — new response cycle
                            self._response_parts = []
                            self.live_msg_id = None
                            self.last_live_text = ""
                            self.hook_msg_id = None
                        # For tool_result entries (list content): keep accumulating
                    elif etype == "assistant":
                        msg_content = entry.get("message", {}).get("content", [])
                        if not isinstance(msg_content, list):
                            continue
                        for block in msg_content:
                            if not isinstance(block, dict):
                                continue
                            btype = block.get("type")
                            if btype == "text" and block.get("text", "").strip():
                                self._response_parts.append(("text", block["text"]))
                                grew = True
                            elif btype == "tool_use":
                                name = block.get("name", "tool")
                                self._response_parts.append(("tool", name))
                                grew = True
                self._transcript_pos = f.tell()
        except (OSError, IOError):
            return False
        if grew:
            self._transcript_last_growth = time.time()
        return grew

    def _format_response(self):
        """Format accumulated response parts for display."""
        lines = []
        pending_tools = []
        for ptype, text in self._response_parts:
            if ptype == "text":
                if pending_tools:
                    lines.append(" → ".join(f"[{t}]" for t in pending_tools))
                    pending_tools = []
                lines.append(text)
            elif ptype == "tool":
                pending_tools.append(text)
        if pending_tools:
            lines.append(" → ".join(f"[{t}]" for t in pending_tools))
        result = "\n\n".join(lines)
        if len(result) > 4000:
            result = result[-4000:]
        return result

    # ── Hook response handling ────────────────────────────────────────

    def _read_hook_response(self):
        """Check if the hook has written a formatted response file."""
        try:
            with open(HOOK_RESPONSE_FILE) as f:
                data = json.load(f)
            os.remove(HOOK_RESPONSE_FILE)
            return data
        except (FileNotFoundError, json.JSONDecodeError, IOError):
            return None

    def _finalize_with_hook(self, data, now):
        """Edit live message (or send new) with hook's formatted HTML response."""
        chat_id = self._chat_id()
        if not chat_id:
            return
        html = data.get("html", "")
        text = data.get("text", "")
        if not html and not text:
            return

        result_msg_id = None

        if self.live_msg_id:
            # Edit existing live message with formatted response
            if html:
                r = telegram_api("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": self.live_msg_id,
                    "text": html,
                    "parse_mode": "HTML",
                })
                if r and r.get("ok"):
                    result_msg_id = self.live_msg_id
            if not result_msg_id:
                r = telegram_api("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": self.live_msg_id,
                    "text": text,
                })
                if r and r.get("ok"):
                    result_msg_id = self.live_msg_id

        if not result_msg_id:
            # No live message to edit — send new
            if html:
                r = telegram_api("sendMessage", {
                    "chat_id": chat_id,
                    "text": html,
                    "parse_mode": "HTML",
                })
                if r and r.get("ok"):
                    result_msg_id = r["result"]["message_id"]
            if not result_msg_id:
                r = telegram_api("sendMessage", {
                    "chat_id": chat_id,
                    "text": text,
                })
                if r and r.get("ok"):
                    result_msg_id = r["result"]["message_id"]

        self.hook_msg_id = result_msg_id
        self.live_msg_id = None
        self.last_live_text = ""
        self._response_parts = []
        self.last_live_update = now
        # Advance transcript position to EOF — prevents re-reading data that
        # the hook already covered, which would cause duplicate messages
        if self._transcript_path:
            try:
                self._transcript_pos = os.path.getsize(self._transcript_path)
            except OSError:
                pass
        print(f"Watcher: hook response applied (msg {result_msg_id})")

    # ── Main tick ───────────────────────────────────────────────────

    def _tick(self):
        if not tmux_exists():
            return

        now = time.time()

        # --- Detect new user message from Telegram (reset state early) ---
        if os.path.exists(PENDING_FILE):
            try:
                pt = os.path.getmtime(PENDING_FILE)
                if pt != self._pending_mtime:
                    self._pending_mtime = pt
                    self.live_msg_id = None
                    self.last_live_text = ""
                    self.hook_msg_id = None
                    self._response_parts = []
                    self._last_scan = 0  # Force re-scan of transcript
            except OSError:
                pass

            # Safety net: if Claude not running and PENDING_FILE is stale, clean up
            try:
                pending_age = now - os.path.getmtime(PENDING_FILE)
            except OSError:
                pending_age = 0
            if pending_age > 10 and not claude_running_in_tmux():
                try:
                    os.remove(PENDING_FILE)
                except OSError:
                    pass
                return

        # --- Always read transcript (keeps position current, detects user messages) ---
        self._read_transcript()

        # --- Priority 1: Hook response → finalize and return ---
        hook_response = self._read_hook_response()
        if hook_response:
            self._finalize_with_hook(hook_response, now)
            return

        # --- Phase 1: Live updates from transcript (if there's unsent content) ---
        if self._response_parts and now - self.last_live_update >= self.LIVE_INTERVAL:
            response = self._format_response()
            if response and response != self.last_live_text:
                self._update_live(response)
                self.last_live_update = now

        # --- Phase 3: Interactive prompt detection (via tmux capture) ---
        content = self._capture()
        if not content:
            return

        tmux_changed = content != self.last_content
        if tmux_changed:
            self.last_content = content
            self.tmux_stable_since = now
            self.hook_msg_id = None  # New activity invalidates old hook msg

        tmux_idle = now - self.tmux_stable_since

        if (tmux_idle >= self.IDLE_THRESHOLD
                and not tmux_changed
                and content != self.last_forwarded
                and now - self.last_forward_time >= self.COOLDOWN
                and self._looks_interactive(content)):
            chat_id = self._chat_id()
            if chat_id:
                options = self._parse_options(content)
                keyboard = self._build_selection_keyboard(options) if options else self._build_generic_keyboard(content)

                # Try to add buttons to an existing message
                target_msg = self.hook_msg_id or self.live_msg_id
                if target_msg:
                    telegram_api("editMessageReplyMarkup", {
                        "chat_id": chat_id,
                        "message_id": target_msg,
                        "reply_markup": {"inline_keyboard": keyboard},
                    })
                    print(f"Watcher: buttons added to msg {target_msg} ({len(options)} opts)")
                    self.hook_msg_id = None
                elif self._response_parts:
                    # Use transcript text + parsed options
                    base = self._format_response()
                    if options:
                        opt_lines = "\n".join(f"{o['num']}. {o['text']}" for o in options)
                        text = f"{base}\n\n{opt_lines}" if base else opt_lines
                    else:
                        text = base
                    telegram_api("sendMessage", {
                        "chat_id": chat_id,
                        "text": text[-4000:],
                        "reply_markup": {"inline_keyboard": keyboard},
                    })
                    print(f"Watcher: transcript + buttons ({len(options)} opts)")
                else:
                    # Fallback: no transcript, no hook — screen capture
                    self._forward(content)
                    print("Watcher: screen capture fallback")
                self.live_msg_id = None
                self.last_live_text = ""
            self.last_forwarded = content
            self.last_forward_time = now

    def _capture(self):
        r = subprocess.run(
            ["tmux", "capture-pane", "-t", TMUX_SESSION, "-p"],
            capture_output=True, text=True
        )
        return r.stdout.rstrip() if r.returncode == 0 else ""

    def _pane_text(self, content, max_lines=20):
        """Extract last N non-empty lines from pane content, stripping TUI noise."""
        lines = []
        for l in content.split('\n'):
            stripped = l.strip()
            if not stripped:
                continue
            # Skip separator lines
            if all(c in '─━═┄┅┈┉╌╍─' for c in stripped):
                continue
            # Skip status bar and navigation hints
            if any(p in stripped for p in self.NOISE_PATTERNS):
                continue
            lines.append(l)
        return '\n'.join(lines[-max_lines:])

    @staticmethod
    def _esc(s):
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def _update_live(self, text):
        """Send or edit a live message with transcript text."""
        chat_id = self._chat_id()
        if not chat_id or not text or text == self.last_live_text:
            return
        self.last_live_text = text

        if self.live_msg_id:
            telegram_api("editMessageText", {
                "chat_id": chat_id,
                "message_id": self.live_msg_id,
                "text": text,
            })
        else:
            result = telegram_api("sendMessage", {
                "chat_id": chat_id,
                "text": text,
            })
            if result and result.get("ok"):
                self.live_msg_id = result["result"]["message_id"]
                print(f"Watcher: live message started (msg {self.live_msg_id})")

    def _looks_interactive(self, content):
        lines = [l for l in content.split('\n') if l.strip()]
        if not lines:
            return False
        tail = '\n'.join(lines[-10:])
        return any(p in tail for p in self.INTERACTIVE_PATTERNS)

    def _parse_options(self, content):
        if 'Enter to select' not in content:
            return []
        options = []
        for line in content.split('\n'):
            m = re.match(r'\s*(?:❯\s*)?(\d+)\.\s+(.+)', line)
            if m:
                options.append({'num': int(m.group(1)), 'text': m.group(2).strip()})
        return options

    def _build_selection_keyboard(self, options):
        keyboard = []
        for opt in options:
            label = f"{opt['num']}. {opt['text']}"
            if len(label) > 40:
                label = label[:38] + ".."
            keyboard.append([{
                "text": label,
                "callback_data": f"sel:{opt['num']}:{len(options)}",
            }])
        keyboard.append([{"text": "Esc", "callback_data": "pane:esc"}])
        return keyboard

    def _build_generic_keyboard(self, content):
        tail = '\n'.join(content.split('\n')[-5:]).lower()
        kb = []
        if any(p in tail for p in ['(y/n)', '(yes/no)', 'yes', ' no']):
            kb.append([
                {"text": "Yes", "callback_data": "pane:y"},
                {"text": "No", "callback_data": "pane:n"},
            ])
        kb.append([
            {"text": "Enter", "callback_data": "pane:enter"},
            {"text": "Esc", "callback_data": "pane:esc"},
        ])
        return kb

    def _forward(self, content):
        chat_id = self._chat_id()
        if not chat_id:
            return
        text = self._pane_text(content, 25)
        if not text:
            return

        options = self._parse_options(content)
        keyboard = self._build_selection_keyboard(options) if options else self._build_generic_keyboard(content)

        msg_data = {
            "chat_id": chat_id,
            "text": text[-4000:],
            "reply_markup": {"inline_keyboard": keyboard},
        }

        if self.live_msg_id:
            # Edit existing live message to add buttons instead of sending duplicate
            msg_data["message_id"] = self.live_msg_id
            telegram_api("editMessageText", msg_data)
        else:
            telegram_api("sendMessage", msg_data)

        print(f"Watcher: forwarded prompt ({len(options)} options)")

    def _chat_id(self):
        try:
            with open(CHAT_ID_FILE) as f:
                return f.read().strip()
        except:
            return None


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            update = json.loads(body)
            if "callback_query" in update:
                self.handle_callback(update["callback_query"])
            elif "message" in update:
                self.handle_message(update)
        except Exception as e:
            print(f"Error: {e}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Claude-Telegram Bridge")

    def handle_callback(self, cb):
        chat_id = cb.get("message", {}).get("chat", {}).get("id")
        data = cb.get("data", "")
        telegram_api("answerCallbackQuery", {"callback_query_id": cb.get("id")})

        if not tmux_exists():
            self.reply(chat_id, "tmux session not found")
            return

        if data.startswith("pane:"):
            action = data.split(":", 1)[1]
            if action == "y":
                tmux_send("y")
                tmux_send_enter()
            elif action == "n":
                tmux_send("n")
                tmux_send_enter()
            elif action == "enter":
                tmux_send_enter()
            elif action == "esc":
                tmux_send_escape()
            return

        if data.startswith("sel:"):
            # sel:{target}:{total} — navigate selection list via arrow keys
            target = int(data.split(":")[1])
            # Read current ❯ position in real time
            r = subprocess.run(
                ["tmux", "capture-pane", "-t", TMUX_SESSION, "-p"],
                capture_output=True, text=True,
            )
            current = 1
            if r.returncode == 0:
                for line in r.stdout.split('\n'):
                    m = re.match(r'\s*❯\s*(\d+)\.', line)
                    if m:
                        current = int(m.group(1))
                        break
            delta = target - current
            key = "Down" if delta > 0 else "Up"
            for _ in range(abs(delta)):
                tmux_send(key, literal=False)
                time.sleep(0.05)
            time.sleep(0.15)
            tmux_send_enter()
            return

        if data.startswith("resume:"):
            session_id = data.split(":", 1)[1]
            tmux_send_escape()
            time.sleep(0.2)
            tmux_send("/exit")
            tmux_send_enter()
            time.sleep(0.5)
            tmux_send(f"claude --resume {session_id} --dangerously-skip-permissions")
            tmux_send_enter()
            self.reply(chat_id, f"Resuming: {session_id[:8]}...")

        elif data == "continue_recent":
            tmux_send_escape()
            time.sleep(0.2)
            tmux_send("/exit")
            tmux_send_enter()
            time.sleep(0.5)
            tmux_send("claude --continue --dangerously-skip-permissions")
            tmux_send_enter()
            self.reply(chat_id, "Continuing most recent...")

    def handle_message(self, update):
        msg = update.get("message", {})
        text, chat_id, msg_id = msg.get("text", ""), msg.get("chat", {}).get("id"), msg.get("message_id")
        if not text or not chat_id:
            return

        with open(CHAT_ID_FILE, "w") as f:
            f.write(str(chat_id))

        if text.startswith("/"):
            cmd = text.split()[0].lower()

            if cmd == "/status":
                status = "running" if tmux_exists() else "not found"
                self.reply(chat_id, f"tmux '{TMUX_SESSION}': {status}")
                return

            if cmd == "/stop":
                if tmux_exists():
                    tmux_send_escape()
                if os.path.exists(PENDING_FILE):
                    os.remove(PENDING_FILE)
                self.reply(chat_id, "Interrupted")
                return

            if cmd == "/clear":
                if not tmux_exists():
                    self.reply(chat_id, "tmux not found")
                    return
                tmux_send_escape()
                time.sleep(0.2)
                tmux_send("/clear")
                tmux_send_enter()
                self.reply(chat_id, "Cleared")
                return

            if cmd == "/continue_":
                if not tmux_exists():
                    self.reply(chat_id, "tmux not found")
                    return
                tmux_send_escape()
                time.sleep(0.2)
                tmux_send("/exit")
                tmux_send_enter()
                time.sleep(0.5)
                tmux_send("claude --continue --dangerously-skip-permissions")
                tmux_send_enter()
                self.reply(chat_id, "Continuing...")
                return

            if cmd == "/loop":
                if not tmux_exists():
                    self.reply(chat_id, "tmux not found")
                    return
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    self.reply(chat_id, "Usage: /loop <prompt>")
                    return
                prompt = parts[1].replace('"', '\\"')
                full = f'{prompt} Output <promise>DONE</promise> when complete.'
                with open(PENDING_FILE, "w") as f:
                    f.write(str(int(time.time())))
                threading.Thread(target=send_typing_loop, args=(chat_id,), daemon=True).start()
                tmux_send(f'/ralph-loop:ralph-loop "{full}" --max-iterations 5 --completion-promise "DONE"')
                time.sleep(0.3)
                tmux_send_enter()
                self.reply(chat_id, "Ralph Loop started (max 5 iterations)")
                return

            if cmd == "/resume":
                sessions = get_recent_sessions()
                if not sessions:
                    self.reply(chat_id, "No sessions")
                    return
                kb = [[{"text": "Continue most recent", "callback_data": "continue_recent"}]]
                for s in sessions:
                    sid = get_session_id(s.get("project", ""))
                    if sid:
                        kb.append([{"text": s.get("display", "?")[:40] + "...", "callback_data": f"resume:{sid}"}])
                telegram_api("sendMessage", {"chat_id": chat_id, "text": "Select session:", "reply_markup": {"inline_keyboard": kb}})
                return

            if cmd in BLOCKED_COMMANDS:
                self.reply(chat_id, f"'{cmd}' not supported (interactive)")
                return

            # Unrecognized /command while Claude is running → Claude internal command
            if claude_running_in_tmux():
                def handle_claude_cmd(c_text=text, c_chat=chat_id):
                    tmux_send(c_text)
                    tmux_send_enter()
                    time.sleep(2.5)
                    try:
                        raw = subprocess.check_output(
                            ["tmux", "capture-pane", "-t", TMUX_SESSION, "-p"],
                            stderr=subprocess.DEVNULL
                        ).decode()
                        noise = ['bypass permissions', 'shift+tab', 'esc to interrupt',
                                 'Press Enter to send', 'to navigate']
                        lines = []
                        for line in raw.split("\n"):
                            stripped = line.strip()
                            if not stripped:
                                continue
                            if any(n in stripped.lower() for n in noise):
                                continue
                            lines.append(line.rstrip())
                        out = "\n".join(lines).strip()
                        if out:
                            telegram_api("sendMessage", {
                                "chat_id": c_chat,
                                "text": out[-4000:],
                            })
                    except Exception as e:
                        telegram_api("sendMessage", {"chat_id": c_chat, "text": f"Error: {e}"})
                threading.Thread(target=handle_claude_cmd, daemon=True).start()
                return

        # Regular message
        print(f"[{chat_id}] {text[:50]}...")

        if not tmux_exists():
            self.reply(chat_id, "tmux not found")
            return

        if msg_id:
            telegram_api("setMessageReaction", {"chat_id": chat_id, "message_id": msg_id, "reaction": [{"type": "emoji", "emoji": "\u2705"}]})

        if not claude_running_in_tmux():
            # Shell mode: run command directly and return output
            def run_shell():
                try:
                    cwd = subprocess.check_output(
                        ["tmux", "display-message", "-t", TMUX_SESSION, "-p", "#{pane_current_path}"],
                        stderr=subprocess.DEVNULL
                    ).decode().strip() or os.path.expanduser("~")
                    tmux_send(text)
                    tmux_send_enter()
                    time.sleep(1.5)  # Wait for command to finish
                    # Capture pane scrollback and extract last command's output
                    raw = subprocess.check_output(
                        ["tmux", "capture-pane", "-t", TMUX_SESSION, "-p", "-S", "-100"],
                        stderr=subprocess.DEVNULL
                    ).decode()
                    # Split into lines, strip trailing blanks, find the output
                    lines = raw.rstrip().split("\n")
                    # Walk backwards to find the command we sent
                    output_lines = []
                    found_cmd = False
                    for line in reversed(lines):
                        if not found_cmd:
                            # Skip the current prompt line (usually last non-empty line)
                            if line.strip().endswith("$") or line.strip().endswith("#") or line.strip().endswith("%"):
                                continue
                            found_cmd = True
                        if found_cmd:
                            # Stop when we hit the line containing our command
                            if text.strip() in line:
                                break
                            output_lines.insert(0, line)
                    output = "\n".join(output_lines).strip()
                    if not output:
                        output = "(no output)"
                    self.reply(chat_id, output[-4000:])
                except Exception as e:
                    self.reply(chat_id, f"Error: {e}")
            threading.Thread(target=run_shell, daemon=True).start()
            return

        with open(PENDING_FILE, "w") as f:
            f.write(str(int(time.time())))

        threading.Thread(target=send_typing_loop, args=(chat_id,), daemon=True).start()
        tmux_send(text)
        tmux_send_enter()

    def reply(self, chat_id, text):
        telegram_api("sendMessage", {"chat_id": chat_id, "text": text})

    def log_message(self, *args):
        pass


def main():
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        return
    setup_bot_commands()
    PaneWatcher().start()
    print(f"Bridge on :{PORT} | tmux: {TMUX_SESSION}")
    try:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")


if __name__ == "__main__":
    main()
