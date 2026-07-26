#!/bin/bash
set -e

PG_ROOT="/home/amjad/apps/postgresql16/root"
PG_BIN="$PG_ROOT/usr/lib/postgresql/16/bin"
PG_DATA="/home/amjad/english_learning_app_data/postgres/16/data"
PG_SOCKET="/home/amjad/english_learning_app_data/postgres/16/socket"
PG_LOG="/home/amjad/english_learning_app_data/postgres/16/postgres.log"

if [ ! -x "$PG_BIN/pg_ctl" ] || [ ! -f "$PG_DATA/PG_VERSION" ]; then
    echo "PLP PostgreSQL is not installed under /home. See README.md setup instructions." >&2
    exit 1
fi

case "${1:-status}" in
    start)
        mkdir -p "$PG_SOCKET"
        if "$PG_BIN/pg_ctl" -D "$PG_DATA" status >/dev/null 2>&1; then
            echo "PLP PostgreSQL is already running."
        else
            "$PG_BIN/pg_ctl" -D "$PG_DATA" -l "$PG_LOG" \
                -o "-k $PG_SOCKET -h 127.0.0.1 -p 5432" start
        fi
        ;;
    stop)
        if "$PG_BIN/pg_ctl" -D "$PG_DATA" status >/dev/null 2>&1; then
            "$PG_BIN/pg_ctl" -D "$PG_DATA" stop -m fast
        else
            echo "PLP PostgreSQL is already stopped."
        fi
        ;;
    status)
        "$PG_BIN/pg_ctl" -D "$PG_DATA" status
        ;;
    *)
        echo "Usage: $0 {start|stop|status}" >&2
        exit 2
        ;;
esac
