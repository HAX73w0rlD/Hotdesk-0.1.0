# Hotdesk v0.1.1 – Projektabschluss und Sicherheits-Updates

## Hinzugefügt

- **INTEGRITY.json** – SHA-256-Prüfsummendatei für alle Python-Quelldateien, Konfigurationen und die AppImage-Datei. Automatische Integritätsprüfung bei jedem App-Start.
- **Skripterweiterung** –
  - `scripts/check_integrity.py` – Neue Integritätsprüfung mit `--generate`, `--verify`, `--update` Optionen
  - `scripts/sign_appimage.sh` – GPG-Detached-Signatur-Erstellung für AppImage-Dateien (RSA-4096, SHA512)
  - `scripts/verify.sh` – Vollständige Verifizierung: Signatur, SHA-256, INTEGRITY.json, Lizenzdatei, Python-Syntax
  - `scripts/license_check.py` – Lizenzprüfung bei jedem Start (Trial/Pro/Enterprise Lizenztypen)
  - `scripts/generate_license.py` – Lizenzgenerierung für alle Typen (Trial, Pro, Enterprise)
  - `scripts/install-hotdesk.sh` – Installationsskript für die Hotdesk-Anwendung
  - `scripts/verify-integrity.sh` – Unabhängige Integritätsprüfung der AppImage
- **Lizenzdatei-Validierung** – Unterstützung von `.key`, `.json`, `.enc` und verschlüsselten Konfigurationsdateien
- **Anti-Tampering-Schutz** – Die AppImage prüft bei jedem Start ihren eigenen Hash gegen gespeicherten Wert
- **Verschlüsselte Konfiguration** – `app/config/encrypted_config.py` mit PBKDF2-HMAC-SHA256 (100.000 Iterationen)
- **.gitignore** – Entfernung von `*.AppImage` aus der Ignoreliste, damit die AppImage im Git verfolgt wird
- **INTEGRITY.json** – Enthält nun Prüfsummen für 42 Dateien inklusive aller neuen Skripte und Konfigurationen

## Geändert

- **README.md** – Erweiterte Dokumentation mit allen neuen Features, Installationsanweisungen und Sicherheitsmaßnahmen
- **SECURITY.md** – Ausführliche Dokumentation aller 5 Sicherheitsschichten (Signatur, Prüfsummen, Lizenz, Anti-Tampering, verschlüsselte Config)
- **app/desktop_app.py** – Integration von Splash-Screen, Über-Dialog (F12) und verbessertem Startverhalten
- **app/desktop_storage.py** – Anti-Tampering-Mechanismus: Hash-Vergleich der AppImage bei jedem Start, sofortiges Beenden bei Modifikation
- **INTEGRITY.json** – Automatisch aktualisiert bei jedem Start bei Dateiänderungen

## Behebt

- Fehlende GPG-Signatur-Prüfung in vorigen Versionen
- AppImage wurde fälschlicherweise aus .gitignore entfernt
- Fehlende Integritätsprüfung bei App-Start

---

*Format basiert auf [Keep a Changelog](https://keepachangelang.com/de/)*