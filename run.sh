#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

PORT="${PORT:-28491}"
HOST="${HOST:-127.0.0.1}"
PID_FILE="$DIR/.server.pid"
LOG_FILE="$DIR/.server.log"

get_port_pids() {
    lsof -ti tcp:"$PORT" 2>/dev/null || fuser "$PORT"/tcp 2>/dev/null || true
}

stop_server() {
    local stopped=0
    
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null || true)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "Stopping server process PID $pid..."
            kill "$pid" 2>/dev/null || true
            for _ in {1..20}; do
                if ! kill -0 "$pid" 2>/dev/null; then
                    break
                fi
                sleep 0.1
            done
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
            stopped=1
        fi
        rm -f "$PID_FILE"
    fi

    local port_pids
    port_pids=$(get_port_pids)
    if [ -n "$port_pids" ]; then
        echo "Clearing lingering process(es) on port $PORT: $port_pids"
        for p in $port_pids; do
            kill "$p" 2>/dev/null || true
        done
        sleep 0.3
        for p in $port_pids; do
            if kill -0 "$p" 2>/dev/null; then
                kill -9 "$p" 2>/dev/null || true
            fi
        done
        stopped=1
    fi

    if [ "$stopped" -eq 1 ]; then
        echo "Port $PORT is clean and server is stopped."
    fi
}

status_server() {
    local running=0
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null || true)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "Server is running (PID: $pid, Port: $PORT)."
            running=1
        fi
    fi

    local port_pids
    port_pids=$(get_port_pids)
    if [ -n "$port_pids" ]; then
        echo "Process listening on port $PORT: $port_pids"
        running=1
    fi

    if [ "$running" -eq 0 ]; then
        echo "Server is not running."
        return 1
    fi
    return 0
}

start_server() {
    local daemon=0
    for arg in "$@"; do
        if [ "$arg" = "-d" ] || [ "$arg" = "--daemon" ]; then
            daemon=1
        fi
    done

    # Idempotent cleanup of any old instance
    stop_server

    PYTHON_BIN="$DIR/.venv/bin/python"
    if [ ! -f "$PYTHON_BIN" ]; then
        echo "Creating virtual environment..."
        uv venv "$DIR/.venv"
        uv pip install --python "$PYTHON_BIN" fastapi uvicorn websockets pydantic pillow pyinstaller
    fi

    echo "=========================================================="
    echo " Android Automation Engine (Idempotent Runner)"
    echo " URL: http://${HOST}:${PORT}"
    echo " Unique Port: ${PORT}"
    echo "=========================================================="

    if [ "$daemon" -eq 1 ]; then
        nohup "$PYTHON_BIN" -u -m app.main --host "$HOST" --port "$PORT" >> "$LOG_FILE" 2>&1 &
        local s_pid=$!
        echo "$s_pid" > "$PID_FILE"
        disown "$s_pid" 2>/dev/null || true
        echo "Server started in background (PID: $s_pid)."
        echo "Logs available at: $LOG_FILE"
        exit 0
    fi

    # Foreground runner with cleanup trap
    "$PYTHON_BIN" -m app.main --host "$HOST" --port "$PORT" &
    SERVER_PID=$!
    echo "$SERVER_PID" > "$PID_FILE"

    cleanup() {
        echo ""
        echo "Terminating server (PID: $SERVER_PID)..."
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo "Server exited cleanly. No processes left running."
    }

    trap cleanup INT TERM EXIT

    wait "$SERVER_PID"
}

case "$1" in
    stop)
        stop_server
        ;;
    status)
        status_server
        ;;
    restart)
        shift || true
        stop_server
        sleep 1
        start_server "$@"
        ;;
    start)
        shift || true
        start_server "$@"
        ;;
    *)
        start_server "$@"
        ;;
esac
