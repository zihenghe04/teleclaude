#!/bin/bash
# teleclaude one-click start/stop script

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-YOUR_BOT_TOKEN_HERE}"
TMUX_SESSION="${TMUX_SESSION:-claude}"
PORT="${PORT:-8080}"
BRIDGE_PID_FILE="$PROJECT_DIR/.bridge.pid"
TUNNEL_PID_FILE="$PROJECT_DIR/.tunnel.pid"
TUNNEL_LOG="$PROJECT_DIR/.tunnel.log"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_ok()   { echo -e "${GREEN}[+]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_err()  { echo -e "${RED}[-]${NC} $1"; }

start() {
    echo "========== teleclaude start =========="

    if [ "$BOT_TOKEN" = "YOUR_BOT_TOKEN_HERE" ]; then
        log_err "Set TELEGRAM_BOT_TOKEN first"
        exit 1
    fi

    # 1. tmux session
    if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
        log_ok "tmux '$TMUX_SESSION' already running"
    else
        tmux new-session -d -s "$TMUX_SESSION"
        sleep 2
        if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
            log_ok "tmux '$TMUX_SESSION' started"
        else
            log_err "tmux failed to start"
            exit 1
        fi
    fi

    # 2. Bridge server
    if [ -f "$BRIDGE_PID_FILE" ] && kill -0 "$(cat "$BRIDGE_PID_FILE")" 2>/dev/null; then
        log_ok "Bridge already running (PID: $(cat "$BRIDGE_PID_FILE"))"
    else
        cd "$PROJECT_DIR"
        TELEGRAM_BOT_TOKEN="$BOT_TOKEN" "$PROJECT_DIR/.venv/bin/python" bridge.py &
        BRIDGE_PID=$!
        echo "$BRIDGE_PID" > "$BRIDGE_PID_FILE"
        sleep 2
        if kill -0 "$BRIDGE_PID" 2>/dev/null; then
            log_ok "Bridge started (PID: $BRIDGE_PID, port: $PORT)"
        else
            log_err "Bridge failed to start"
            rm -f "$BRIDGE_PID_FILE"
            exit 1
        fi
    fi

    # 3. Cloudflare Tunnel (bypass proxy for QUIC)
    if [ -f "$TUNNEL_PID_FILE" ] && kill -0 "$(cat "$TUNNEL_PID_FILE")" 2>/dev/null; then
        log_ok "Tunnel already running (PID: $(cat "$TUNNEL_PID_FILE"))"
        TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" | head -1)
    else
        no_proxy="*" http_proxy="" https_proxy="" HTTP_PROXY="" HTTPS_PROXY="" \
            cloudflared tunnel --url "http://localhost:$PORT" > "$TUNNEL_LOG" 2>&1 &
        TUNNEL_PID=$!
        echo "$TUNNEL_PID" > "$TUNNEL_PID_FILE"

        echo -n "   Waiting for tunnel URL"
        TUNNEL_URL=""
        for i in $(seq 1 15); do
            sleep 1
            echo -n "."
            TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1)
            if [ -n "$TUNNEL_URL" ]; then
                break
            fi
        done
        echo ""

        if [ -n "$TUNNEL_URL" ]; then
            log_ok "Tunnel started: $TUNNEL_URL"
        else
            log_err "Tunnel URL timeout, check $TUNNEL_LOG"
            exit 1
        fi
    fi

    # 4. Set webhook
    if [ -n "$TUNNEL_URL" ]; then
        sleep 2
        RESULT=$(curl -s --max-time 10 "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${TUNNEL_URL}")
        if echo "$RESULT" | grep -q '"ok":true'; then
            log_ok "Webhook set: $TUNNEL_URL"
        else
            log_err "Webhook failed: $RESULT"
        fi
    fi

    echo ""
    echo "========== Ready =========="
    echo "Bot is online. Send a message on Telegram!"
    echo "Stop: $0 stop"
}

stop() {
    echo "========== teleclaude stop =========="

    curl -s --max-time 10 "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook" > /dev/null 2>&1
    log_ok "Webhook deleted"

    if [ -f "$TUNNEL_PID_FILE" ]; then
        PID=$(cat "$TUNNEL_PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null
            log_ok "Tunnel stopped (PID: $PID)"
        fi
        rm -f "$TUNNEL_PID_FILE" "$TUNNEL_LOG"
    else
        log_warn "Tunnel not running"
    fi

    if [ -f "$BRIDGE_PID_FILE" ]; then
        PID=$(cat "$BRIDGE_PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null
            log_ok "Bridge stopped (PID: $PID)"
        fi
        rm -f "$BRIDGE_PID_FILE"
    else
        log_warn "Bridge not running"
    fi

    rm -f ~/.claude/telegram_pending

    echo ""
    echo "========== Stopped =========="
    echo "Note: tmux session '$TMUX_SESSION' is still alive. Kill with: tmux kill-session -t $TMUX_SESSION"
}

status() {
    echo "========== Status =========="
    if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
        log_ok "tmux '$TMUX_SESSION': running"
    else
        log_err "tmux '$TMUX_SESSION': not running"
    fi

    if [ -f "$BRIDGE_PID_FILE" ] && kill -0 "$(cat "$BRIDGE_PID_FILE")" 2>/dev/null; then
        log_ok "Bridge: running (PID: $(cat "$BRIDGE_PID_FILE"))"
    else
        log_err "Bridge: not running"
    fi

    if [ -f "$TUNNEL_PID_FILE" ] && kill -0 "$(cat "$TUNNEL_PID_FILE")" 2>/dev/null; then
        URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1)
        log_ok "Tunnel: running (PID: $(cat "$TUNNEL_PID_FILE"), URL: $URL)"
    else
        log_err "Tunnel: not running"
    fi
}

case "${1:-}" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 1; start ;;
    status)  status ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo ""
        echo "  start    Start all services (tmux + bridge + tunnel + webhook)"
        echo "  stop     Stop bridge and tunnel"
        echo "  restart  Restart all services"
        echo "  status   Check running status"
        ;;
esac
