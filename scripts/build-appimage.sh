#!/usr/bin/env bash
set -Eeuo pipefail
# Hotdesk AppImage Build Script
# Erstellt eine neue AppImage-Version

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APPIMAGETOOL="${APPIMAGETOOL:-$(command -v appimagetool || echo "$PROJECT_ROOT/bin/appimagetool")}"

cd "$PROJECT_ROOT"

# Clean previous build
rm -rf "$PROJECT_ROOT/build/AppDir" "$PROJECT_ROOT/build/pyinstaller" "$PROJECT_ROOT/build/pyinstaller-work"

# Run PyInstaller
python3 -m PyInstaller --noconfirm --clean --onedir --windowed \
    --name hotdesk \
    --distpath "$PROJECT_ROOT/build/pyinstaller" \
    --workpath "$PROJECT_ROOT/build/pyinstaller-work" \
    --specpath "$PROJECT_ROOT/build" \
    --paths "$PROJECT_ROOT" \
    --add-data "$PROJECT_ROOT/app:app" \
    --collect-all tkinter \
    --collect-all reportlab \
    --collect-all PyPDF2 \
    "$PROJECT_ROOT/hotdesk/__init__.py"

# Build AppImage using packaging script
APPIMAGETOOL="$APPIMAGETOOL" "$PROJECT_ROOT/packaging/appimage/build-appimage.sh"

echo "✅ AppImage gebaut!"
