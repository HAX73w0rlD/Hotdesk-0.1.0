# Hotdesk

## Beschreibung

**Hotdesk** ist eine lokale Desktop-Anwendung für die Verwaltung von Kunden, Rechnungen, Produkten und Zahlungen.

- **Sprache:** Python 3.11+
- **GUI:** Tkinter
- **Datenbank:** SQLite mit WAL-Modus
- **Formatierung:** AppImage für Linux x86_64

## Installation aus Quellcode

### Voraussetzungen
```bash
sudo apt-get install python3-tk python3-pyinstaller libfuse2t64 desktop-file-utils
python3 -m pip install --user pyinstaller
```

### Entwicklungsinstallation
```bash
cd hotdesk
pip install -e .
python -m hotdesk
```

### AppImage bauen
```bash
APPIMAGETOOL=/pfad/zu/appimagetool packaging-appimage/build-appimage.sh
```

## Projektstruktur

```
hotdesk/
├── app/
│   ├── __init__.py
│   ├── desktop_app.py       # Tkinter GUI Hauptanwendung
│   ├── desktop_storage.py   # SQLite-Datenbank-Logik
│   ├── config/
│   │   └── __init__.py      # Anwendungskonfiguration
│   └── models/              # Datenmodelle
├── hotdesk/
│   └── __init__.py         # Startpunkt
├── packaging-appimage/     # AppImage-Dateien
├── pyproject.toml          # Build-Konfiguration
└── README.md
```

## Module

### `app.desktop_app`
Die Hauptbenutzeroberfläche der Anwendung. Verantwortlich für:
- Dashboard-Darstellung
- Kundenverwaltung
- Rechnungserstellung und -verwaltung
- Produktverwaltung
- Import/Export-Funktionen

### `app.desktop_storage`
Datenbank-Speicher-Engine mit:
- SQLite-WAL-Unterstützung
- Audit-Log für alle Änderungen
- Automatische Datenbankmigration
- Backup-Funktionalität

### `app.config`
Zentrales Konfigurationsmodul mit:
- Pfadkonfiguration
- Datenbank-Verbindungseinstellungen
- Anwendungspräferenzen
- PCAS-Import-Parameter

## Abhängigkeiten

### Systemabhängigkeiten
- Python 3.11+
- python3-tk
- python3-pyinstaller
- libfuse2t64 (nur für AppImage)

### Python-Abhängigkeiten
Siehe `pyproject.toml` für eine vollständige Liste.

## Testen

```bash
# Tests ausführen
python -m pytest tests/

# Code-Qualität prüfen
python -m py_compile app/*.py
```

## Lizenz

Dieses Projekt ist unter der MIT License lizenziert. Siehe [LICENSE](LICENSE) für Details.

## Beitragen

Bitte siehe [CONTRIBUTING.md](CONTRIBUTING.md) für Beitragshinweise.

## Support

Für Support, Fragen und Bug-Reports bitte [Issues öffnen](https://github.com/HAX73w0rlD/Hotdesk-0.1.0/issues).
