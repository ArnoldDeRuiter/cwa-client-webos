#!/bin/sh
# Starts readerfix.py in the background, unless it's already running.
DIR="$(dirname "$0")"
PIDFILE=/tmp/cwa-readerfix.pid

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    exit 0
fi

nohup python3 "$DIR/readerfix.py" >/tmp/cwa-readerfix.log 2>&1 &
echo $! > "$PIDFILE"
