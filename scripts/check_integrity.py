"""SHA-256 Integritätsprüfung für die Hotdesk-Anwendung.

Dieses Skript berechnet die SHA-256-Prüfsummen aller Python-Dateien
und der AppImage-Datei und vergleicht sie mit den gespeicherten Werten
in INTEGRITY.json. Es wird bei jedem Start der App automatisch aufgerufen.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tkinter as tk
from pathlib import Path
from typing import Any

# Projektroot-Verzeichnis erkennen (gehe von scripts/ aus nach oben)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Dateien, die geprüft werden sollen
INTEGRITY_FILE = PROJECT_ROOT / "INTEGRITY.json"
APPIMAGE_PATH = PROJECT_ROOT / "Hotdesk-0.1.0-x86_64.AppImage"

# Python-Quelldateien
SOURCE_DIRS = [
    PROJECT_ROOT / "app",
    PROJECT_ROOT / "hotdesk",
    PROJECT_ROOT / "packaging",
]


def compute_sha256(filepath: Path) -> str | None:
    """Berechnet die SHA-256-Prüfsumme einer Datei."""
    try:
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, IOError) as exc:
        print(f"[WARN] Datei nicht lesbar: {filepath} ({exc})")
        return None


def collect_files() -> dict[str, str]:
    """Sammelt alle zu prüfenden Dateien und deren Prüfsummen."""
    checksums: dict[str, str] = {}

    # Python-Quelldateien
    for source_dir in SOURCE_DIRS:
        if source_dir.exists():
            for py_file in sorted(source_dir.rglob("*.py")):
                # Cache-Dateien ausschließen
                if "__pycache__" in py_file.parts:
                    continue
                rel_path = py_file.relative_to(PROJECT_ROOT)
                checksums[str(rel_path)] = compute_sha256(py_file) or ""

    # AppImage-Datei
    if APPIMAGE_PATH.exists():
        checksums["Hotdesk-0.1.0-x86_64.AppImage"] = compute_sha256(APPIMAGE_PATH) or ""

    # Weitere Konfigurationsdateien
    for extra in [
        PROJECT_ROOT / "pyproject.toml",
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "packaging" / "appimage" / "AppRun",
        PROJECT_ROOT / "packaging" / "appimage" / "hotdesk.desktop",
    ]:
        if extra.exists():
            rel_path = extra.relative_to(PROJECT_ROOT)
            checksums[str(rel_path)] = compute_sha256(extra) or ""

    return checksums


def save_integrity(checksums: dict[str, str]) -> None:
    """Speichert die Prüfsummen in INTEGRITY.json."""
    data: dict[str, Any] = {
        "version": "1.0",
        "generated": _get_timestamp(),
        "checksums": checksums,
        "metadata": {
            "application": "Hotdesk",
            "description": "SHA-256 Integritätsprüfung",
        },
    }
    with open(INTEGRITY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def load_integrity() -> dict[str, Any] | None:
    """Lädt die gespeicherten Prüfsummen aus INTEGRITY.json."""
    if not INTEGRITY_FILE.exists():
        return None
    try:
        with open(INTEGRITY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as exc:
        print(f"[ERROR] INTEGRITY.json kann nicht gelesen werden: {exc}")
        return None


def _get_timestamp() -> str:
    """Gibt den aktuellen Zeitstempel zurück."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def verify_integrity() -> tuple[bool, list[str]]:
    """
    Prüft alle Dateien auf Modifikation.

    Returns:
        (is_valid, warnings): True wenn alles intakt, sonst False.
        Liste von Warnungsnachrichten.
    """
    warnings: list[str] = []
    current_checksums = collect_files()
    stored_data = load_integrity()

    if stored_data is None:
        # Keine INTEGRITY.json vorhanden → erstelle neue
        save_integrity(current_checksums)
        warnings.append(
            "INTEGRITY.json wurde neu erstellt. Initialisierung abgeschlossen."
        )
        return False, warnings

    stored_checksums: dict[str, str] = stored_data.get("checksums", {})

    # Prüfe auf fehlende oder geänderte Dateien
    all_files = set(stored_checksums.keys()) | set(current_checksums.keys())
    is_valid = True

    for filepath in sorted(all_files):
        stored_hash = stored_checksums.get(filepath, "")
        current_hash = current_checksums.get(filepath, "")

        if not stored_hash and not current_hash:
            continue
        if not stored_hash:
            warnings.append(f"[NEUE DATEI] {filepath} wurde hinzugefügt.")
            is_valid = False
        elif not current_hash:
            warnings.append(f"[GEÄNDERT] {filepath} existiert nicht mehr.")
            is_valid = False
        elif stored_hash != current_hash:
            warnings.append(
                f"[MODIFIZIERT] {filepath} wurde verändert!\n"
                f"  Erwartet: {stored_hash[:16]}...\n"
                f"  Aktuell:  {current_hash[:16]}..."
            )
            is_valid = False

    # Prüfe auf gelöschte Dateien aus der gespeicherten Liste
    for filepath in sorted(stored_checksums.keys()):
        if filepath not in current_checksums:
            warnings.append(f"[GELÖSCHT] {filepath} wurde entfernt!")
            is_valid = False

    return is_valid, warnings


def generate_integrity_report() -> str:
    """Generiert einen vollständigen Integritätsbericht."""
    checksums = collect_files()
    save_integrity(checksums)
    return f"INTEGRITY.json generiert mit {len(checksums)} Dateien."


def run_gui_check(parent: tk.Widget | None = None) -> bool:
    """
    GUI-Integritätsprüfung für den App-Start.
    Zeigt eine Warnung an, wenn Dateien modifiziert wurden.

    Args:
        parent: Eltern-Widget für Tk-Dialogfenster.

    Returns:
        True wenn die Integrität geprüft und intakt ist, False bei Problemen.
    """
    is_valid, warnings = verify_integrity()

    if not is_valid:
        if parent:
            try:
                # Versuche eine tkinter-Warnung zu zeigen
                root = tk.Toplevel(parent) if isinstance(parent, tk.Widget) else parent
                root.withdraw()
                msg = "⚠️ INTEGRITÄTSWARNUNG ⚠️\n\n"
                msg += "Einige Dateien der Hotdesk-Anwendung wurden verändert!\n\n"
                msg += "Details:\n" + "\n".join(f"• {w}" for w in warnings[:10])
                msg += "\n\nDie Anwendung wird möglicherweise nicht korrekt funktionieren.\n"
                msg += "Bitte überprüfen Sie die Dateien und kontaktieren Sie den Administrator."
                tk.messagebox.showwarning("Sicherheitswarnung", msg, parent=parent)
                root.destroy()
            except Exception:
                # Falls GUI nicht verfügbar, nur Konsolenausgabe
                for warning in warnings:
                    print(f"[INTEGRITY WARNING] {warning}")
        else:
            for warning in warnings:
                print(f"[INTEGRITY WARNING] {warning}")

        return False
    else:
        # Alles intakt - INTEGRITY.json ggf. aktualisieren
        current_checksums = collect_files()
        stored_data = load_integrity()
        if stored_data and stored_data.get("checksums") != current_checksums:
            save_integrity(current_checksums)

        return True


def main() -> None:
    """Hauptfunktion für den Aufruf von der Kommandozeile."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SHA-256 Integritätsprüfung für Hotdesk"
    )
    parser.add_argument(
        "--generate", action="store_true",
        help="Erstellt INTEGRITY.json neu"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Prüft die Integrität aller Dateien"
    )
    parser.add_argument(
        "--update", action="store_true",
        help="Aktualisiert INTEGRITY.json mit aktuellen Prüfsummen"
    )

    args = parser.parse_args()

    if args.generate:
        result = generate_integrity_report()
        print(result)
    elif args.verify:
        is_valid, warnings = verify_integrity()
        if is_valid:
            print("✅ Alle Dateien sind intakt und unverändert.")
        else:
            print("❌ Integritätsprüfung fehlgeschlagen!")
            for warning in warnings:
                print(f"  {warning}")
        sys.exit(0 if is_valid else 1)
    elif args.update or not (args.generate or args.verify):
        # Standard: generieren und aktualisieren
        result = generate_integrity_report()
        print(result)
        is_valid, warnings = verify_integrity()
        if is_valid:
            print("✅ Integritätsprüfung bestanden.")
        else:
            for warning in warnings:
                print(f"[WARN] {warning}")


if __name__ == "__main__":
    main()
