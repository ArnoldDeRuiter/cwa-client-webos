#!/bin/sh
# Starts loginfill.py in the background, unless it's already running.
DIR="$(dirname "$0")"
PIDFILE=/tmp/cwa-loginfill.pid

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    exit 0
fi

nohup python3 "$DIR/loginfill.py" >/tmp/cwa-loginfill.log 2>&1 &
echo $! > "$PIDFILE"
