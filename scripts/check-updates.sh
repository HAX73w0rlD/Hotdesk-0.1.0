#!/usr/bin/env bash
set -Eeuo pipefail
# Hotdesk Update Check Script
# Prüft auf Updates und zeigt Versionsinformationen

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔍 Hotdesk Versionsprüfung"
echo "=========================="
echo "Version: $(grep version $PROJECT_ROOT/pyproject.toml | head -1 | cut -d'"' -f2)"
echo "Python:  $(python3 --version)"
echo "AppImage: $(ls -lh $PROJECT_ROOT/Hotdesk-0.1.0-x86_64.AppImage 2>/dev/null | awk '{print $5, $9}' || echo 'Nicht gefunden')"
echo ""
echo "📁 Projektstruktur:"
find "$PROJECT_ROOT" -not -path '*/.git/*' -not -path '*/__pycache__/*' -not -path '*/build/*' -type f | sort
echo ""
echo "🔒 Integrität:"
if [[ -f "$PROJECT_ROOT/INTEGRITY.json" ]]; then
    echo "✅ INTEGRITY.json vorhanden ($(wc -l < $PROJECT_ROOT/INTEGRITY.json) Zeilen)"
else
    echo "❌ INTEGRITY.json fehlt"
fi
