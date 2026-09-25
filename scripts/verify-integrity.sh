#!/usr/bin/env bash
set -Eeuo pipefail
# Hotdesk Integrity Verification Script
# Prüft die Dateiintegrität des Hotdesk-Projekts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INTEGRITY_FILE="$PROJECT_ROOT/INTEGRITY.json"

if [[ ! -f "$INTEGRITY_FILE" ]]; then
    echo "❌ INTEGRITY.json nicht gefunden in $PROJECT_ROOT"
    exit 1
fi

echo "🔍 Prüfe Dateiintegrität..."
ERRORS=0

python3 -c "
import json, hashlib, os, sys

with open('$INTEGRITY_FILE') as f:
    integrity = json.load(f)

errors = 0
for path, info in integrity.items():
    if info.get('type') != 'file':
        continue
    full_path = os.path.join('$PROJECT_ROOT', path)
    if not os.path.exists(full_path):
        print(f'❌ FEHLT: {path}')
        errors += 1
        continue
    with open(full_path, 'rb') as fh:
        actual = hashlib.sha256(fh.read()).hexdigest()
    if actual != info['sha256']:
        print(f'❌ VERFÄLSCHT: {path}')
        errors += 1
    else:
        print(f'✅ OK: {path}')

if errors > 0:
    print(f'\n❌ {errors} Fehler gefunden!')
    sys.exit(1)
else:
    print(f'\n✅ Alle Dateien intakt ({len(integrity)} Einträge)')
"

exit $?
