#!/usr/bin/env bash
# ==============================================================================
# sign_appimage.sh - GPG-Signatur für die Hotdesk AppImage erstellen
# ==============================================================================
# Dieses Skript generiert eine GPG-Signatur für die AppImage-Datei und
# speichert diese zusammen mit der AppImage-Datei ab.
#
# Verwendungsmöglichkeiten:
#   ./sign_appimage.sh          - Signiert die AppImage-Datei
#   ./sign_appimage.sh --verify  - Verifiziert die Signaturen
#   ./sign_appimage.sh --gpg-info - Zeigt GPG-Schlüsselinformationen
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
APPIMAGE_DIR="$PROJECT_ROOT"
APPIMAGE_FILE="$APPIMAGE_DIR/Hotdesk-0.1.0-x86_64.AppImage"
SIGNATURE_FILE="$APPIMAGE_FILE.sig"
SIGNATURE_ASC="$APPIMAGE_FILE.asc"
PASSPHRASE_FILE="$SCRIPT_DIR/.gpg_passphrase"
GNUPGHOME="${GNUPGHOME:-$HOME/.gnupg}"

# Farben für Ausgabe
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Prüfe ob AppImage existiert
check_appimage() {
    if [[ ! -f "$APPIMAGE_FILE" ]]; then
        log_error "AppImage-Datei nicht gefunden: $APPIMAGE_FILE"
        exit 1
    fi
    log_info "AppImage gefunden: $APPIMAGE_FILE"
}

# Prüfe ob GPG verfügbar ist
check_gpg() {
    if ! command -v gpg &>/dev/null; then
        log_error "gpg ist nicht installiert."
        exit 1
    fi
    log_info "GPG gefunden: $(gpg --version | head -1)"
}

# Erstelle GPG-Schlüssel falls nicht vorhanden
create_gpg_key() {
    local key_id
    key_id=$(gpg --list-secret-keys --keyidformat=long 2>/dev/null | grep "^sec" | head -1 | awk '{print $2}' | cut -d'/' -f2) || true

    if [[ -z "$key_id" ]]; then
        log_warn "Kein GPG-Schlüssel gefunden. Erstelle einen neuen Schlüssel..."
        log_info "Dies kann einige Zeit dauern. Bitte warten..."

        # GPG-Konfiguration erstellen
        mkdir -p "$GNUPGHOME"
        chmod 700 "$GNUPGHOME"

        # GPG-Parameter für automatisierte Schlüsselerstellung
        cat > "$GNUPGHOME/gpg-key-config.txt" <<EOF
%echo Erstelle GPG-Schlüssel für Hotdesk
Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Subkey-Length: 4096
Name-Real: Hotdesk Security
Name-Email: security@hotdesk.local
Expire-Date: 0
%no-protection
%commit
%echo Fertig
EOF

        gpg --batch --generate-key "$GNUPGHOME/gpg-key-config.txt" 2>&1 || {
            log_error "GPG-Schlüsselgenerierung fehlgeschlagen."
            exit 1
        }
        rm -f "$GNUPGHOME/gpg-key-config.txt"

        key_id=$(gpg --list-secret-keys --keyidformat=long 2>/dev/null | grep "^sec" | head -1 | awk '{print $2}' | cut -d'/' -f2) || true
        log_ok "Neuer GPG-Schlüssel erstellt: $key_id"
    else
        log_ok "GPG-Schlüssel gefunden: $key_id"
    fi

    echo "$key_id"
}

# Signiert die AppImage-Datei
sign_appimage() {
    check_appimage
    check_gpg

    local key_id
    key_id=$(create_gpg_key)

    log_info "Signiere AppImage-Datei..."

    # Erstelle die Signatur (binär und ASCII-Format)
    gpg --detach-sign --armor --local-user "$key_id" \
        --output "$SIGNATURE_ASC" "$APPIMAGE_FILE" 2>&1 || {
        log_error "Fehler beim Erstellen der ASCII-Signatur."
        exit 1
    }

    gpg --detach-sign --local-user "$key_id" \
        --output "$SIGNATURE_FILE" "$APPIMAGE_FILE" 2>&1 || {
        log_error "Fehler beim Erstellen der binären Signatur."
        exit 1
    }

    # Berechne SHA-256 der AppImage-Datei
    local sha256_hash
    sha256_hash=$(sha256sum "$APPIMAGE_FILE" | awk '{print $1}')

    # Speichere die Signatur-Informationen
    cat > "$SCRIPT_DIR/signature_info.json" <<EOF
{
  "appimage": "Hotdesk-0.1.0-x86_64.AppImage",
  "sha256": "$sha256_hash",
  "signing_key_id": "$key_id",
  "signature_file": "Hotdesk-0.1.0-x86_64.AppImage.sig",
  "signature_ascii_file": "Hotdesk-0.1.0-x86_64.AppImage.asc",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "algorithm": "RSA-4096 + SHA512"
}
EOF

    log_ok "AppImage erfolgreich signiert!"
    log_ok "  Binäre Signatur: $SIGNATURE_FILE"
    log_ok "  ASCII-Signatur:  $SIGNATURE_ASC"
    log_ok "  SHA-256:         $sha256_hash"
    log_ok "  Signatur-Info:   $SCRIPT_DIR/signature_info.json"
}

# Verifiziert die GPG-Signatur
verify_signature() {
    check_appimage
    check_gpg

    if [[ ! -f "$SIGNATURE_FILE" ]]; then
        log_error "Binäre Signatur nicht gefunden: $SIGNATURE_FILE"
        log_info "Bitte zuerst mit 'sign_appimage.sh' signieren."
        exit 1
    fi

    if [[ ! -f "$SIGNATURE_ASC" ]]; then
        log_warn "ASCII-Signatur nicht gefunden: $SIGNATURE_ASC"
        log_info "Nur binäre Signatur wird verifiziert."
    fi

    log_info "Verifiziere GPG-Signatur..."

    if gpg --verify "$SIGNATURE_FILE" "$APPIMAGE_FILE" 2>&1; then
        log_ok "✅ GPG-Signatur ist gültig!"
    else
        log_error "❌ GPG-Signatur ist INVALID!"
        exit 1
    fi

    # Prüfe die SHA-256-Prüfsumme
    if [[ -f "$SCRIPT_DIR/signature_info.json" ]]; then
        local stored_sha256
        stored_sha256=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/signature_info.json'))['sha256'])")
        local current_sha256
        current_sha256=$(sha256sum "$APPIMAGE_FILE" | awk '{print $1}')

        if [[ "$stored_sha256" == "$current_sha256" ]]; then
            log_ok "✅ SHA-256-Prüfsumme stimmt überein."
        else
            log_error "❌ SHA-256-Prüfsumme weicht ab!"
            log_error "  Erwartet: $stored_sha256"
            log_error "  Aktuell:  $current_sha256"
        fi
    fi
}

# Zeigt GPG-Schlüsselinformationen
show_gpg_info() {
    check_gpg
    echo "=========================================="
    echo " GPG-Schlüsselinformationen"
    echo "=========================================="
    gpg --list-keys 2>/dev/null || true
    echo ""
    gpg --list-secret-keys 2>/dev/null || true
    echo ""
    if [[ -f "$SCRIPT_DIR/signature_info.json" ]]; then
        echo "Letzte Signatur-Information:"
        python3 -m json.tool "$SCRIPT_DIR/signature_info.json" 2>/dev/null || cat "$SCRIPT_DIR/signature_info.json"
    fi
}

# Hauptprogramm
main() {
    case "${1:-}" in
        --verify)
            verify_signature
            ;;
        --gpg-info)
            show_gpg_info
            ;;
        *)
            sign_appimage
            ;;
    esac
}

main "$@"
