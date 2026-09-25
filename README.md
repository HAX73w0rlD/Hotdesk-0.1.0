<h1 align="center">
  <img src="packaging-appimage/hotdesk.svg" alt="Hotdesk" width="128" />
  <br/>
  Hotdesk
</h1>

<div align="center">

**Lokale Desktop-Anwendung für Kunden, Rechnungen, Produkte und Zahlungen**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-%3E%3D3.11-blue)
![Platform](https://img.shields.io/badge/Platform-Linux%20x86_64-lightgrey)
![AppImage](https://img.shields.io/badge/Bundle-AppImage-FF69B4)
[![Downloads](https://img.shields.io/github/downloads/HAX73w0rlD/Hotdesk-0.1.0/total)](https://github.com/HAX73w0rlD/Hotdesk-0.1.0/releases)

</div>

---

## ✨ Überblick

**Hotdesk** ist eine eigenständige Desktop-Anwendung für die Verwaltung von Kunden, Rechnungen, Produkten und Zahlungen. Die Benutzeroberfläche basiert auf **Python/Tkinter** – ohne Browser, ohne PHP, ohne Webserver.

Die fertige **AppImage** enthält die gesamte Python-Laufzeit, Tcl/Tk, SQLite und alle Abhängigkeiten. Auf dem Zielsystem sind **keine Installationen** erforderlich – nur ein Linux-x86_64-System mit grafischer Oberfläche und FUSE.

## 🚀 Schnellstart

### AppImage (empfohlen)
```bash
chmod +x Hotdesk-0.1.0-x86_64.AppImage
./Hotdesk-0.1.0-x86_64.AppImage
```

### Aus dem Quellcode
```bash
sudo apt-get install python3-tk python3-pyinstaller libfuse2t64 desktop-file-utils
python3 -m pip install --user pyinstaller
APPIMAGETOOL=/pfad/zu/appimagetool packaging-appimage/build-appimage.sh
./build/Hotdesk-0.1.0-x86_64.AppImage
```

### Ohne FUSE
```bash
./Hotdesk-0.1.0-x86_64.AppImage --appimage-extract-and-run
```

## 📋 Funktionen

- **Dashboard** mit offenen, überfälligen und Gesamtbeträgen
- **Kundenverwaltung** mit Debitoren- und Kontaktdaten
- **Produkte & Leistungen** mit Netto-Preis und Steuersatz
- **Rechnungsmanagement** mit Positionen, Fälligkeit und Zahlungsstatus
- **Teilzahlungen** und vollständige Zahlungen
- **Automatische Überfälligkeitserkennung**
- **SQLite-Datenbank** mit WAL und Audit-Log
- **PCAS-Import** für `Kunden.txt` (Debitoren) und `RAImport1` (Rechnungsausgänge)
- **DATEV-CSV-Export** (Debitoren, Konten, Buchungsstapel)
- **Lokale Backups**
- **Deutsche Oberfläche** mit Tastaturkürzeln

## 📁 Datenbank

Bei erstem Start wird automatisch eine SQLite-Datenbank erstellt:
```text
~/.local/share/hotdesk/hotdesk.sqlite
```

## 🖼️ Screenshots

*Hinweis: Screenshots werden in einer zukünftigen Version ergänzt.*

## 📦 Installation

### Voraussetzungen
- Linux x86_64 (glibc-kompatibel)
- Grafische Oberfläche (X11/Wayland)
- FUSE (für AppImage-Mount, optional mit `--appimage-extract-and-run`)

### PCAS-Import
Über `Einstellungen → PCAS-Import` werden folgende Dateien unterstützt:
- `Kunden.txt` – Debitoren-/Kundenstammdaten (semikolon-getrennt)
- `RAImport1` – Rechnungsausgangssätze (153 Zeichen pro Satz)

Die Dateien werden als UTF-8, Windows-1252 oder Latin-1 gelesen. Vor dem Import sollte ein Backup erstellt werden.

### DATEV-Export
Im Menü `Einstellungen → DATEV-Export` werden Debitoren-, Konten- und Buchungsstapel als CSV exportiert.

## 🏗️ Aufbau

```
hotdesk/
├── app/
│   ├── __init__.py
│   ├── desktop_app.py      # Hauptanwendung (Tkinter GUI)
│   ├── desktop_storage.py  # SQLite-Datenbank-Logik
│   ├── config/
│   │   └── __init__.py     # Anwendungskonfiguration
│   └── models/             # Datenmodelle
├── hotdesk/
│   └── __init__.py         # Startpunkt (Hauptmodul)
├── packaging-appimage/     # AppImage-Paketinrichtung
├── pyproject.toml          # Projektkonfiguration
├── README.md
└── LICENSE
```

## 🔧 Entwicklung

### Voraussetzungen
```bash
sudo apt-get install python3-tk python3-pyinstaller libfuse2t64 desktop-file-utils
python3 -m pip install --user pyinstaller
```

### AppImage bauen
```bash
APPIMAGETOOL=/pfad/zu/appimagetool packaging-appimage/build-appimage.sh
```

### Ausführen
```bash
./build/Hotdesk-0.1.0-x86_64.AppImage
```

### FUSE installieren (falls benötigt)
```bash
./packaging-appimage/install-fuse.sh
```

## 📄 Lizenz

Dieses Projekt steht unter der **MIT License**. Siehe [LICENSE](LICENSE) für Details.

## ⚠️ Haftungsausschluss

Diese Anwendung ist ein solider lokaler MVP. Für den Produktivbetrieb mit echten steuerlichen Exporten, Benutzerverwaltung, Audit-Freigaben, DATEV-Zertifizierung und XRechnung/ZUGFeRD ist eine **fachliche und rechtliche Prüfung** erforderlich.

## 📝 Änderungsprotokoll

### v0.1.0 (2026-09-25)
- Initiale Veröffentlichung
- Kundenverwaltung
- Rechnungsmanagement
- Produkte & Leistungen
- Dashboard
- PCAS-Import
- DATEV-CSV-Export
- SQLite-Datenbank mit WAL und Audit-Log
- AppImage-Build

## 🤝 Beitragen

Beiträge sind willkommen! Bitte beachten Sie die [Beitragrichtlinien](CONTRIBUTING.md).

## 📫 Kontakt

**HAX73w0rlD** – [GitHub](https://github.com/HAX73w0rlD)

## 🔗 Links

- [AppImage herunterladen](https://github.com/HAX73w0rlD/Hotdesk-0.1.0/releases)
- [Dokumentation](https://github.com/HAX73w0rlD/Hotdesk-0.1.0/wiki)
- [Issues](https://github.com/HAX73w0rlD/Hotdesk-0.1.0/issues)
- [Python-Projekt](https://github.com/HAX73w0rlD/Hotdesk-0.1.0)

---

<div align="center">

Made with ❤️ für lokale Buchhaltung

</div>
