#!/usr/bin/env bash
# ==============================================================================
# verify.sh - Vollständige Verifizierung der Hotdesk AppImage-Signatur
# ==============================================================================
# Dieses Skript führt eine vollständige Verifizierung durch:
#   1. GPG-Signaturprüfung
#   2. SHA-256-Prüfsummenvergleich
#   3. Integritätsprüfung über INTEGRITY.json
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
APPIMAGE_FILE="$PROJECT_ROOT/Hotdesk-0.1.0-x86_64.AppImage"
SIGNATURE_FILE="$APPIMAGE_FILE.sig"
SIGNATURE_ASC="$APPIMAGE_FILE.asc"
INTEGRITY_FILE="$PROJECT_ROOT/INTEGRITY.json"
SIGNATURE_INFO="$SCRIPT_DIR/signature_info.json"

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

RESULTS=()
PASSED=0
FAILED=0

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[PASS]${NC} $1"; PASSED=$((PASSED + 1)); }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_fail()  { echo -e "${RED}[FAIL]${NC} $1"; FAILED=$((FAILED + 1)); }

echo "=========================================="
echo "  Hotdesk AppImage - Verifizierung"
echo "=========================================="
echo ""

# Prüfe 1: AppImage existiert
if [[ ! -f "$APPIMAGE_FILE" ]]; then
    log_fail "AppImage-Datei nicht gefunden: $APPIMAGE_FILE"
    echo ""
    echo "Ergebnisse: $PASSED bestanden, $FAILED fehlgeschlagen"
    exit 1
fi
log_ok "AppImage-Datei gefunden"

# Prüfe 2: GPG-Signatur
if [[ -f "$SIGNATURE_FILE" ]]; then
    log_info "Überprüfe GPG-Signatur (binär)..."
    if gpg --verify "$SIGNATURE_FILE" "$APPIMAGE_FILE" 2>/dev/null; then
        log_ok "GPG-Signatur ist gültig"
    else
        log_fail "GPG-Signatur ist ungültig!"
    fi
else
    log_warn "GPG-Signatur-Datei nicht gefunden: $SIGNATURE_FILE"
    log_fail "Keine GPG-Signatur vorhanden"
fi

# Prüfe 3: ASCII-Signatur
if [[ -f "$SIGNATURE_ASC" ]]; then
    log_info "Überprüfe ASCII-Signatur..."
    if gpg --verify "$SIGNATURE_ASC" "$APPIMAGE_FILE" 2>/dev/null; then
        log_ok "ASCII-Signatur ist gültig"
    else
        log_fail "ASCII-Signatur ist ungültig!"
    fi
fi

# Prüfe 4: SHA-256 Vergleich mit Signatur-Info
if [[ -f "$SIGNATURE_INFO" ]]; then
    log_info "Überprüfe SHA-256-Prüfsumme..."
    STORED_SHA256=$(python3 -c "import json; print(json.load(open('$SIGNATURE_INFO'))['sha256'])" 2>/dev/null || echo "")
    CURRENT_SHA256=$(sha256sum "$APPIMAGE_FILE" | awk '{print $1}')

    if [[ "$STORED_SHA256" == "$CURRENT_SHA256" ]]; then
        log_ok "SHA-256-Prüfsumme stimmt überein"
    else
        log_fail "SHA-256-Prüfsumme weicht ab!"
        log_info "  Erwartet: $STORED_SHA256"
        log_info "  Aktuell:  $CURRENT_SHA256"
    fi
fi

# Prüfe 5: INTEGRITY.json
if [[ -f "$INTEGRITY_FILE" ]]; then
    log_info "Überprüfe Integrität über INTEGRITY.json..."
    python3 "$SCRIPT_DIR/check_integrity.py" --verify 2>/dev/null && {
        log_ok "INTEGRITY.json Prüfung bestanden"
    } || {
        log_fail "INTEGRITY.json Prüfung fehlgeschlagen"
    }
else
    log_warn "INTEGRITY.json nicht gefunden"
    log_fail "Keine Integritätsdaten vorhanden"
fi

# Prüfe 6: Lizenzdatei
if [[ -f "$PROJECT_ROOT/.hotdesk/license.key" ]]; then
    log_info "Lizenzdatei gefunden..."
    log_ok "Lizenzdatei vorhanden"
else
    log_warn "Lizenzdatei nicht gefunden: $PROJECT_ROOT/.hotdesk/license.key"
    log_fail "Lizenzdatei fehlt"
fi

# Prüfe 7: Python-Dateien auf Syntaxfehler
log_info "Überprüfe Python-Dateien auf Syntaxfehler..."
PYTHON_SYNTAX_OK=$(python3 -m py_compile "$PROJECT_ROOT/scripts"/*.py 2>&1 || echo "FAILED")
if [[ "$PYTHON_SYNTAX_OK" == *"FAILED"* ]]; then
    log_fail "Python-Syntaxfehler gefunden"
else
    log_ok "Keine Python-Syntaxfehler gefunden"
fi

# Ergebnis zusammenfassen
echo ""
echo "=========================================="
if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}  ✅ Alle Prüfungen bestanden ($PASSED)${NC}"
else
    echo -e "${RED}  ❌ $FAILED Prüfung(en) fehlgeschlagen ($PASSED bestanden)${NC}"
fi
echo "=========================================="

if [[ $FAILED -gt 0 ]]; then
    exit 1
fi
exit 0
