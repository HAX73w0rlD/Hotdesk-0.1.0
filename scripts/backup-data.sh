#!/usr/bin/env bash
set -Eeuo pipefail
# Hotdesk Backup Script
# Erstellt ein Backup der Hotdesk-Datenbank

DATA_DIR="${HOTDESK_DATA_DIR:-$HOME/.local/share/hotdesk}"
BACKUP_DIR="${HOME}/hotdesk-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

if [[ -f "$DATA_DIR/hotdesk.sqlite" ]]; then
    cp "$DATA_DIR/hotdesk.sqlite" "$BACKUP_DIR/hotdesk-backup-$TIMESTAMP.sqlite"
    # WAL files too
    cp "$DATA_DIR/hotdesk.sqlite-wal" "$BACKUP_DIR/hotdesk-backup-$TIMESTAMP.sqlite-wal" 2>/dev/null || true
    cp "$DATA_DIR/hotdesk.sqlite-shm" "$BACKUP_DIR/hotdesk-backup-$TIMESTAMP.sqlite-shm" 2>/dev/null || true
    echo "✅ Backup erstellt: $BACKUP_DIR/hotdesk-backup-$TIMESTAMP.sqlite"
else
    echo "⚠️  Keine Datenbank gefunden unter $DATA_DIR"
fi
