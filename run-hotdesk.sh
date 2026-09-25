#!/bin/bash
# run-hotdesk.sh – Wrapper für Hotdesk AppImage
# Erhöht das FD-Limit und startet die AppImage im Extract-and-Run-Modus.
# So vermeidet man den "FD_SETSIZE"-Absturz.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPIMAGE="${SCRIPT_DIR}/Hotdesk-0.1.0-x86_64.AppImage"

if [[ ! -f "${APPIMAGE}" ]]; then
    echo "❌ AppImage nicht gefunden: ${APPIMAGE}" >&2
    echo "Bitte stelle sicher, dass Hotdesk-0.1.0-x86_64.AppImage im selben Verzeichnis liegt." >&2
    exit 1
fi

# FD-Limit erhöhen (verhindert "bit out of range 0 - FD_SETSIZE")
ulimit -n 4096

echo "🚀 Starte Hotdesk ..."
exec "${APPIMAGE}" --appimage-extract-and-run "$@"