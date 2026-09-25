"""Lizenzschlüssel-Validierung für Hotdesk.

Prüft auf eine Lizenzdatei im Verzeichnis .hotdesk/.
Wenn keine gültige Lizenz vorhanden ist, wird eine Trial-Nachricht angezeigt.
Die Lizenzprüfung erfolgt bei jedem Start der Anwendung.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Lizenzdatei-Pfade
HOTDESK_DIR = Path.home() / ".hotdesk"
LICENSE_FILE = HOTDESK_DIR / "license.key"
ENCRYPTED_LICENSE_FILE = HOTDESK_DIR / "license.enc"
LICENSE_INFO_FILE = HOTDESK_DIR / "license_info.json"

# Pfad im Projektverzeichnis (für Entwicklungsumgebung)
PROJECT_LICENSE_FILE = Path(__file__).resolve().parent.parent / ".hotdesk" / "license.key"

# Trial-Konfiguration
TRIAL_DAYS = 14
TRIAL_INSTALLED_KEY = "hotdesk_trial_install_date"

# Lizenz-Typen
LICENSE_TYPES = {
    "trial": {"name": "Testversion", "days": TRIAL_DAYS},
    "basic": {"name": "Basic", "days": 365},
    "pro": {"name": "Professional", "days": 0},  # Unbegrenzt
    "enterprise": {"name": "Enterprise", "days": 0},
}


class LicenseStatus:
    """Enum-ähnliche Klasse für Lizenzstatus."""
    VALID = "valid"
    TRIAL = "trial"
    EXPIRED = "expired"
    INVALID = "invalid"
    MISSING = "missing"
    CORRUPTED = "corrupted"


class LicenseChecker:
    """Prüft und verwaltet die Lizenzvalidierung."""

    def __init__(self) -> None:
        self.license_data: dict[str, Any] | None = None
        self.status: str = LicenseStatus.MISSING
        self.message: str = ""
        self.trial_remaining_days: int = 0

    def check_license(self) -> dict[str, Any]:
        """
        Hauptmethode zur Lizenzprüfung.

        Prüft in dieser Reihenfolge:
        1. Projekt-Lizenzdatei (.hotdesk/license.key)
        2. Benutzer-Lizenzdatei (~/.hotdesk/license.key)
        3. Verschlüsselte Lizenzdatei
        4. Trial-Status

        Returns:
            Dictionary mit Lizenzstatus und Details.
        """
        # Prüfe die Lizenzdateien
        license_path = self._find_license_file()

        if license_path and license_path.exists():
            result = self._validate_license_file(license_path)
            if result:
                return result

        # Prüfe verschlüsselte Lizenz
        result = self._check_encrypted_license()
        if result:
            return result

        # Prüfe Trial-Status
        return self._check_trial_status()

    def _find_license_file(self) -> Path | None:
        """Findet die Lizenzdatei im Projekt- oder Benutzerverzeichnis."""
        # Prüfe Projektverzeichnis zuerst
        if PROJECT_LICENSE_FILE.exists():
            return PROJECT_LICENSE_FILE
        # Prüfe Benutzerverzeichnis
        if LICENSE_FILE.exists():
            return LICENSE_FILE
        return None

    def _validate_license_file(self, path: Path) -> dict[str, Any] | None:
        """Validiert eine Lizenzdatei."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read().strip()

            # Prüfe ob es JSON oder einfacher Text ist
            if raw.startswith("{"):
                data = json.loads(raw)
            else:
                # Einfacher Text-Format: HOTDESK-LICENSE:<key>:<timestamp>:<hash>
                data = self._parse_license_text(raw)
                if data is None:
                    return None

            if not self._verify_license_hash(data):
                self.status = LicenseStatus.INVALID
                self.message = "Lizenzschlüssel ist ungültig (Hash-Fehler)."
                return self._get_result()

            # Prüfe Ablaufdatum
            expiry = data.get("expiry_date")
            if expiry and not self._check_expiry(expiry):
                self.status = LicenseStatus.EXPIRED
                self.message = f"Lizenz ist abgelaufen am {expiry}."
                return self._get_result()

            self.license_data = data
            self.status = LicenseStatus.VALID
            self.message = f"Lizenz gültig: {data.get('type', 'unknown')}"
            return self._get_result()

        except (json.JSONDecodeError, ValueError, IOError) as exc:
            self.status = LicenseStatus.CORRUPTED
            self.message = f"Lizenzdatei ist beschädigt: {exc}"
            return self._get_result()

    def _parse_license_text(self, raw: str) -> dict[str, Any] | None:
        """Parst eine einfache Text-Lizenzdatei."""
        # Nur die erste Zeile parsen: HOTDESK-LICENSE:type:key:timestamp:hash
        first_line = raw.strip().split("\n")[0]
        # Hash ist die letzte 32-Zeichen-Hex-Zeichenkette, verwende rsplit
        parts = first_line.rsplit(":", 1)
        if len(parts) != 2 or not parts[1].strip().isalnum() or len(parts[1].strip()) != 32:
            return None
        hash_part = parts[1].strip()
        rest = parts[0]
        # Teile den Rest in die ersten 3 Elemente auf
        subparts = rest.split(":", 3)
        if len(subparts) != 4 or subparts[0] != "HOTDESK-LICENSE":
            return None
        return {
            "type": subparts[1].strip(),
            "key": subparts[2].strip(),
            "timestamp": subparts[3].strip(),
            "hash": hash_part,
        }

    def _verify_license_hash(self, data: dict[str, Any]) -> bool:
        """Verifiziert den Hash der Lizenzdaten."""
        key = data.get("key", "")
        license_type = data.get("type", "trial")
        timestamp = data.get("timestamp", "")
        salt = "hotdesk-secret-salt-2024"
        expected_hash = hashlib.sha256(
            f"{license_type}:{key}:{timestamp}:{salt}".encode()
        ).hexdigest()

        return data.get("hash") == expected_hash[:32]

    def _check_expiry(self, expiry_str: str) -> bool:
        """Prüft ob die Lizenz noch nicht abgelaufen ist."""
        try:
            expiry_date = datetime.fromisoformat(expiry_str)
            return datetime.now() <= expiry_date
        except (ValueError, TypeError):
            return True  # Wenn das Datum nicht parsebar ist, gilt als nicht abgelaufen

    def _check_encrypted_license(self) -> dict[str, Any] | None:
        """Prüft eine verschlüsselte Lizenzdatei."""
        if not ENCRYPTED_LICENSE_FILE.exists():
            return None

        try:
            with open(ENCRYPTED_LICENSE_FILE, "rb") as f:
                encrypted_data = f.read()

            # Einfache Entschlüsselung (Base64 + XOR als Basis)
            # Für Produktion sollte eine richtige Verschlüsselung verwendet werden
            try:
                import base64
                decoded = base64.b64decode(encrypted_data)
                # Einfacher XOR-Decrypt (nur für Demo-Zwecke)
                decrypted = bytes(b ^ 0x42 for b in decoded)
                data = json.loads(decrypted.decode("utf-8"))

                if self._verify_license_hash(data):
                    self.license_data = data
                    self.status = LicenseStatus.VALID
                    return self._get_result()
            except Exception:
                pass
        except IOError:
            pass
        except IOError:
            pass

        return None

    def _check_trial_status(self) -> dict[str, Any]:
        """Prüft den Trial-Status der Anwendung."""
        install_date_str = ""

        # Prüfe die Installationsdatums-Datei
        try:
            # Versuche zuerst die SQLite-Datenbank zu lesen
            db_path = Path.home() / ".local/share/hotdesk/hotdesk.sqlite"
            if db_path.exists():
                import sqlite3
                conn = sqlite3.connect(str(db_path))
                row = conn.execute(
                    "SELECT value FROM settings WHERE key = ?", (TRIAL_INSTALLED_KEY,)
                ).fetchone()
                conn.close()
                if row:
                    install_date_str = row[0]
        except Exception:
            pass

        if not install_date_str:
            # Prüfe in der Projektumgebung
            install_date_str = os.environ.get("HOTDESK_INSTALL_DATE", "")

        if install_date_str:
            try:
                install_date = datetime.fromisoformat(install_date_str)
                days_passed = (datetime.now() - install_date).days
                self.trial_remaining_days = max(0, TRIAL_DAYS - days_passed)

                if days_passed <= TRIAL_DAYS:
                    self.status = LicenseStatus.TRIAL
                    self.message = (
                        f"Testversion aktiv. Noch {self.trial_remaining_days} Tage übrig."
                    )
                else:
                    self.status = LicenseStatus.EXPIRED
                    self.message = (
                        f"Testversion abgelaufen. Die 14-Tage-Testversion ist beendet."
                    )
            except ValueError:
                self.status = LicenseStatus.MISSING
                self.message = "Installationsdatum ist ungültig."
        else:
            self.status = LicenseStatus.TRIAL
            self.trial_remaining_days = TRIAL_DAYS
            self.message = f"Testversion gestartet. {TRIAL_DAYS} Tage kostenlos verfügbar."

        return self._get_result()

    def _get_result(self) -> dict[str, Any]:
        """Gibt das Ergebnis als Dictionary zurück."""
        return {
            "status": self.status,
            "valid": self.status in (LicenseStatus.VALID,),
            "message": self.message,
            "license_type": self.license_data.get("type", "trial") if self.license_data else "trial",
            "trial_remaining_days": self.trial_remaining_days,
            "timestamp": datetime.now().isoformat(),
        }

    def should_block_launch(self) -> bool:
        """
        Prüft ob der App-Start blockiert werden sollte.

        Returns:
            True wenn die App sich selbst sperren sollte.
        """
        return self.status in (LicenseStatus.EXPIRED,)

    def get_trial_message(self) -> str:
        """Gibt die Trial-Nachricht für die GUI zurück."""
        if self.status == LicenseStatus.TRIAL:
            return (
                f"ℹ️ Testversion von Hotdesk\n\n"
                f"Sie nutzen die Testversion. Noch {self.trial_remaining_days} Tage übrig.\n"
                f"Bitte erwerben Sie eine Lizenz, um die volle Funktionalität zu nutzen.\n\n"
                f"Kontaktieren Sie: sales@hotdesk.local"
            )
        elif self.status == LicenseStatus.EXPIRED:
            return (
                f"⚠️ Testversion abgelaufen\n\n"
                f"Die 14-Tage-Testversion von Hotdesk ist abgelaufen.\n"
                f"Bitte erwerben Sie eine Lizenz, um die Anwendung weiter zu nutzen.\n\n"
                f"Kontaktieren Sie: sales@hotdesk.local"
            )
        elif self.status == LicenseStatus.VALID:
            return (
                f"✅ Lizenz gültig\n\n"
                f"Lizenztyp: {self.license_data.get('type', 'unknown')}\n"
                f"Die Anwendung ist voll funktionsfähig."
            )
        else:
            return self.message


def check_license_gui(parent: tk.Widget | None = None) -> bool:
    """
    GUI-Lizenzprüfung für den App-Start.

    Args:
        parent: Eltern-Widget für Tk-Dialogfenster.

    Returns:
        True wenn die Lizenz gültig ist, False bei Problemen.
    """
    checker = LicenseChecker()
    result = checker.check_license()

    if result["valid"]:
        return True

    if checker.should_block_launch():
        # Lizenz abgelaufen - zeige Fehlermeldung
        if parent:
            try:
                import tkinter as tk
                root = tk.Toplevel(parent) if isinstance(parent, tk.Widget) else parent
                root.withdraw()
                tk.messagebox.showerror(
                    "Lizenz abgelaufen",
                    checker.get_trial_message() +
                    "\n\nDie Anwendung wird nun geschlossen."
                )
                root.destroy()
            except Exception:
                print(checker.get_trial_message())
        else:
            print(checker.get_trial_message())
        return False

    # Trial- oder ungültige Lizenz - zeige Warnung
    if parent:
        try:
            import tkinter as tk
            root = tk.Toplevel(parent) if isinstance(parent, tk.Widget) else parent
            root.withdraw()
            tk.messagebox.showwarning(
                "Lizenz",
                checker.get_trial_message()
            )
            root.destroy()
        except Exception:
            print(checker.get_trial_message())
    else:
        print(checker.get_trial_message())

    return True


def main() -> None:
    """Hauptfunktion für den Aufruf von der Kommandozeile."""
    import argparse
    import tkinter as tk

    parser = argparse.ArgumentParser(
        description="Lizenzprüfung für Hotdesk"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Zeigt den aktuellen Lizenzstatus"
    )
    parser.add_argument(
        "--gui", action="store_true",
        help="Führt GUI-Lizenzprüfung durch"
    )

    args = parser.parse_args()

    checker = LicenseChecker()

    if args.gui:
        root = tk.Tk()
        root.withdraw()
        result = check_license_gui(root)
        root.destroy()
        sys.exit(0 if result else 1)
    else:
        result = checker.check_license()
        print(json.dumps(result, indent=2))
        if args.status:
            print(f"\nLizenzstatus: {result['status']}")
            print(f"Nachricht: {result['message']}")

        sys.exit(0 if result["valid"] or result["status"] == "trial" else 1)


if __name__ == "__main__":
    main()
