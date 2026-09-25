#!/usr/bin/env bash
# ============================================================
# Hotdesk Installations-Schutz
# Verhindert mehrfache Installation der AppImage
# ============================================================

set -euo pipefail

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Pfade
HOTDESK_DIR="$HOME/.hotdesk"
INSTALL_MARKER="$HOTDESK_DIR/installed.lock"
APP_MARKER="$HOTDESK_DIR/app.lock"
INSTALL_LOG="$HOTDESK_DIR/install.log"
INSTALL_SCRIPT="$(realpath "${BASH_SOURCE[0]}")"
APPIMAGE_PATH="${1:-$(realpath "${BASH_SOURCE[0]%/*}/../Hotdesk-0.1.0-x86_64.AppImage")}"

# Funktionen
log() {
    local level="$1"
    local msg="$2"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $msg" | tee -a "$INSTALL_LOG"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
    log "INFO" "$1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    log "SUCCESS" "$1"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
    log "WARNING" "$1"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    log "ERROR" "$1"
}

check_already_installed() {
    if [[ -f "$INSTALL_MARKER" ]]; then
        local installed_date
        installed_date=$(cat "$INSTALL_MARKER" 2>/dev/null || echo "unbekannt")
        print_error "Hotdesk ist bereits installiert!"
        print_error "Installationsdatum: $installed_date"
        print_error ""
        print_error "Eine mehrfache Installation wird durch den Kopierschutz verhindert."
        print_error ""
        print_error "Optionen:"
        print_error "  1. Nutzen Sie die bereits installierte Version"
        print_error "  2. Deinstallieren Sie zuerst: $0 --uninstall"
        print_error "  3. Für eine neue Installation: $0 --force-reinstall"
        return 1
    fi
    return 0
}

check_running_instance() {
    # Prüfen ob Hotdesk bereits läuft
    if pgrep -f "Hotdesk-0.1.0-x86_64.AppImage" >/dev/null 2>&1; then
        print_warning "Hotdesk läuft bereits!"
        return 1
    fi
    
    # Prüfe App-Lock-Datei
    if [[ -f "$APP_MARKER" ]]; then
        local lock_pid
        lock_pid=$(cat "$APP_MARKER" 2>/dev/null || echo "")
        if [[ -n "$lock_pid" ]] && kill -0 "$lock_pid" 2>/dev/null; then
            print_warning "Hotdesk wird bereits von Prozess $lock_pid ausgeführt!"
            return 1
        else
            # Veralteter Lock entfernen
            rm -f "$APP_MARKER"
        fi
    fi
    return 0
}

create_install_marker() {
    mkdir -p "$HOTDESK_DIR"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    {
        echo "$timestamp"
        echo "APPIMAGE_PATH=$APPIMAGE_PATH"
        echo "INSTALL_USER=$(whoami)"
        echo "INSTALL_HOST=$(hostname)"
        echo "VERSION=0.1.0"
        echo "SHA256=$(sha256sum "$APPIMAGE_PATH" 2>/dev/null | cut -d' ' -f1 || echo 'unbekannt')"
    } > "$INSTALL_MARKER"
    print_success "Installations-Marker erstellt: $INSTALL_MARKER"
}

create_app_lock() {
    echo $$ > "$APP_MARKER"
    print_info "App-Lock erstellt (PID: $$)"
}

remove_app_lock() {
    rm -f "$APP_MARKER"
    print_info "App-Lock entfernt"
}

verify_appimage() {
    if [[ ! -f "$APPIMAGE_PATH" ]]; then
        print_error "AppImage nicht gefunden: $APPIMAGE_PATH"
        return 1
    fi
    
    if [[ ! -x "$APPIMAGE_PATH" ]]; then
        print_info "Setze Ausführungsrecht..."
        chmod +x "$APPIMAGE_PATH"
    fi
    
    # Integritätsprüfung
    local sha256
    sha256=$(sha256sum "$APPIMAGE_PATH" | cut -d' ' -f1)
    print_info "AppImage SHA-256: $sha256"
    
    # Prüfe ob INTEGRITY.json existiert und vergleiche
    local integrity_file="$HOME/.hotdesk/INTEGRITY.json"
    if [[ -f "$integrity_file" ]]; then
        local expected_sha256
        expected_sha256=$(grep -A2 "Hotdesk-0.1.0-x86_64.AppImage" "$integrity_file" 2>/dev/null | grep "sha256" | cut -d'"' -f4 || echo "")
        if [[ -n "$expected_sha256" && "$expected_sha256" != "$sha256" ]]; then
            print_error "INTEGRITÄTS-FEHLER: AppImage-Prüfsumme stimmt nicht überein!"
            print_error "Erwartet: $expected_sha256"
            print_error "Gefunden: $sha256"
            return 1
        fi
    fi
    
    print_success "AppImage-Verifikation bestanden"
    return 0
}

install_appimage() {
    print_info "Installiere Hotdesk v0.1.0..."
    
    # Verzeichnisse erstellen
    mkdir -p "$HOME/.local/share/applications"
    mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps"
    mkdir -p "$HOME/.local/share/hotdesk"
    
    # AppImage in lokales Bin-Verzeichnis kopieren
    local bin_dir="$HOME/.local/bin"
    mkdir -p "$bin_dir"
    local target_appimage="$bin_dir/hotdesk"
    
    if [[ -f "$target_appimage" ]]; then
        rm -f "$target_appimage"
    fi
    
    cp "$APPIMAGE_PATH" "$target_appimage"
    chmod +x "$target_appimage"
    
    # Desktop-Datei installieren
    cat > "$HOME/.local/share/applications/hotdesk.desktop" << 'DESKTOP_EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Hotdesk
GenericName=Buchhaltung
Comment=Lokale Desktop-Anwendung für Kunden, Rechnungen und Zahlungen
Exec=/home/%u/.local/bin/hotdesk
Icon=hotdesk
Terminal=false
Categories=Office;Finance;
StartupNotify=true
Keywords=invoice;billing;accounting;datev;
DESKTOP_EOF
    
    # Icon kopieren (falls vorhanden)
    local icon_src="$(dirname "$APPIMAGE_PATH")/packaging-appimage/hotdesk.svg"
    if [[ -f "$icon_src" ]]; then
        cp "$icon_src" "$HOME/.local/share/icons/hicolor/scalable/apps/hotdesk.svg"
    fi
    
    # Desktop-Datenbank aktualisieren
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    fi
    
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
    fi
    
    create_install_marker
    print_success "Hotdesk erfolgreich installiert!"
    print_info "Starten Sie mit: hotdesk"
    print_info "Oder im Anwendungsmenü unter 'Buchhaltung' → 'Hotdesk'"
}

uninstall_appimage() {
    print_info "Deinstalliere Hotdesk..."
    
    # App-Lock prüfen
    if [[ -f "$APP_MARKER" ]]; then
        local lock_pid
        lock_pid=$(cat "$APP_MARKER" 2>/dev/null || echo "")
        if [[ -n "$lock_pid" ]] && kill -0 "$lock_pid" 2>/dev/null; then
            print_error "Hotdesk läuft noch (PID: $lock_pid). Bitte zuerst beenden."
            return 1
        fi
    fi
    
    # Dateien entfernen
    rm -f "$HOME/.local/bin/hotdesk"
    rm -f "$HOME/.local/share/applications/hotdesk.desktop"
    rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/hotdesk.svg"
    
    # Installations-Marker entfernen
    rm -f "$INSTALL_MARKER"
    
    # Datenbank nicht löschen (Benutzerdaten bleiben)
    print_warning "Benutzerdaten in ~/.local/share/hotdesk/ wurden NICHT gelöscht."
    print_warning "Zum vollständigen Entfernen: rm -rf ~/.local/share/hotdesk/"
    
    # Desktop-Datenbank aktualisieren
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    fi
    
    print_success "Hotdesk deinstalliert."
}

force_reinstall() {
    print_warning "Erzwinge Neuinstallation..."
    uninstall_appimage
    sleep 1
    install_appimage
}

show_status() {
    echo "========================================"
    echo "  Hotdesk Installations-Status"
    echo "========================================"
    echo ""
    
    if [[ -f "$INSTALL_MARKER" ]]; then
        print_success "STATUS: INSTALLIERT"
        echo ""
        cat "$INSTALL_MARKER"
    else
        print_warning "STATUS: NICHT INSTALLIERT"
    fi
    
    echo ""
    echo "AppImage-Pfad: $APPIMAGE_PATH"
    if [[ -f "$APPIMAGE_PATH" ]]; then
        echo "AppImage: $(ls -lh "$APPIMAGE_PATH" | awk '{print $5}')"
        echo "SHA-256: $(sha256sum "$APPIMAGE_PATH" | cut -d' ' -f1)"
    else
        print_error "AppImage nicht gefunden!"
    fi
    
    echo ""
    echo "Laufende Prozesse:"
    pgrep -f "Hotdesk-0.1.0-x86_64.AppImage" || echo "  Keine"
    
    echo ""
    echo "Lizenz-Status:"
    python3 -c "
import sys
sys.path.insert(0, '$HOME/.hotdesk')
try:
    from scripts.license_check import LicenseChecker
    checker = LicenseChecker()
    result = checker.check_license()
    print(f'  Status: {result[\"status\"]}')
    print(f'  Nachricht: {result[\"message\"]}')
except Exception as e:
    print(f'  Fehler: {e}')
" 2>/dev/null || echo "  Lizenz-Prüfung nicht verfügbar"
}

show_help() {
    cat << 'HELP_EOF'
Hotdesk Installations-Schutz v0.1.0

VERWENDUNG:
  ./install-hotdesk.sh [OPTIONEN]

OPTIONEN:
  (keine)          Normale Installation (fehlschlägt wenn bereits installiert)
  --uninstall      Hotdesk vollständig deinstallieren
  --force-reinstall Erzwingt Neuinstallation (entfernt vorherige Installation)
  --status         Zeigt Installations- und Lizenz-Status
  --verify         Prüft nur die AppImage-Integrität
  --help           Zeigt diese Hilfe

SCHUTZMECHANISMEN:
  - Erstellt ~/.hotdesk/installed.lock bei erster Installation
  - Verhindert mehrfache Installation
  - Verhindert gleichzeitiges Ausführen mehrerer Instanzen
  - Verifiziert AppImage-Prüfsumme gegen INTEGRITY.json
  - Integriert mit Lizenz-System (Trial/Pro/Enterprise)

BEISPIELE:
  ./install-hotdesk.sh                    # Normale Installation
  ./install-hotdesk.sh --uninstall        # Deinstallation
  ./install-hotdesk.sh --force-reinstall  # Neuinstallation
  ./install-hotdesk.sh --status           # Status anzeigen

KONTAKT:
  buyandlucky@gmail.com
HELP_EOF
}

# ============================================================
# HAUPTPROGRAMM
# ============================================================

mkdir -p "$HOTDESK_DIR"

case "${1:-}" in
    --uninstall)
        uninstall_appimage
        ;;
    --force-reinstall)
        force_reinstall
        ;;
    --status)
        show_status
        ;;
    --verify)
        verify_appimage
        ;;
    --help|-h)
        show_help
        ;;
    *)
        # Normale Installation
        print_info "=== Hotdesk Installation v0.1.0 ==="
        print_info "Prüfe Installations-Schutz..."
        
        if ! check_already_installed; then
            exit 1
        fi
        
        if ! check_running_instance; then
            exit 1
        fi
        
        if ! verify_appimage; then
            exit 1
        fi
        
        install_appimage
        
        # Lizenz initialisieren
        print_info "Initialisiere Lizenz-System..."
        python3 -c "
import sys
sys.path.insert(0, '$(dirname "$INSTALL_SCRIPT")')
try:
    from generate_license import generate_license
    generate_license(license_type='trial', customer_name='$(whoami)', customer_email='buyandlucky@gmail.com')
except Exception as e:
    print(f'Lizenz-Initialisierung fehlgeschlagen: {e}')
" 2>/dev/null || print_warning "Lizenz-Initialisierung übersprungen"
        
        print_success "=== Installation abgeschlossen ==="
        print_info "Sie können Hotdesk jetzt starten mit: hotdesk"
        ;;
esac