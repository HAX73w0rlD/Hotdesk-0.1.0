# Hotdesk v0.1.1

**Hotdesk** ist eine lokale Desktop-Anwendung für Kunden, Rechnungen, Produkte und Zahlungen. Die Oberfläche ist eine eigenständige Python/Tk-GUI – keine Browser-Oberfläche und kein PHP.

## Funktionen

- Dashboard mit offenen, überfälligen und Gesamtbeträgen
- Kundenverwaltung mit Debitoren- und Kontaktdaten
- Produkte und Leistungen mit Netto-Preis und Steuersatz
- Rechnungen mit Positionen, Fälligkeit und Zahlungsstatus
- Teilzahlungen und vollständige Zahlungen
- Automatische Überfälligkeitserkennung
- SQLite-Datenbank mit WAL und Audit-Log
- PCAS-Import für `Kunden.txt` (Debitoren) und `RAImport1` (Rechnungsausgänge) mit detaillierten Fehlermeldungen
- DATEV-CSV-Export (Debitoren, Konten und Buchungsstapel)
- Lokale Backups mit und ohne Zeitstempel
- **JSON-Export** aller Daten mit SHA-256-Prüfsumme
- **Automatisches Backup mit Zeitstempel**
- Verbesserte Treeview-Ansicht mit optimalen Spaltenbreiten
- Splash-Screen beim Start
- Über-Dialog (F12) mit Versionsinfo und Prüfsumme
- Deutsche Oberfläche und Tastaturkürzel

## Sicherheit

Hotdesk implementiert einen **5-Schicht-Sicherheitsmechanismus**:

1. **GPG-Signatur** – Die AppImage-Datei ist mit RSA-4096 (SHA512) signiert
2. **SHA-256 Prüfsummen** – Alle Dateien in `INTEGRITY.json` gespeichert und bei Start geprüft
3. **Lizenzprüfung** – Validierung von Trial-, Basic-, Pro- und Enterprise-Lizenzen
4. **Anti-Tampering** – AppImage-Hash wird bei jedem Start geprüft; Modifikation = sofortiger Stopp
5. **Verschlüsselte Konfiguration** – PBKDF2-HMAC-SHA256 (100.000 Iterationen) für sensible Daten

Alle Sicherheitsmaßnahmen sind in `SECURITY.md` dokumentiert.

## Download

**Hotdesk-0.1.1-x86_64.AppImage** – [Herunterladen](https://github.com/HAX73w0rlD/Hotdesk-0.1.0/raw/main/Hotdesk-0.1.0-x86_64.AppImage)

Die Datei ist mit einer GPG-Detached-Signatur (`Hotdesk-0.1.0-x86_64.AppImage.sig` und `.asc`) gesichert.

Verifizierung:
```bash
./scripts/verify.sh
```

## Lokal starten

```bash
python3 hotdesk.py
```

Beim ersten Start entsteht automatisch:
```text
~/.local/share/hotdesk/hotdesk.sqlite
~/.local/share/hotdesk/hotdesk.log
```

## Standalone ohne System-Python

Die fertige AppImage enthält die Python-Laufzeit, Tcl/Tk, SQLite und alle für Hotdesk benötigten Python-Module. Auf dem Zielsystem müssen **weder Python noch PHP noch ein Webserver installiert sein**. Benötigt werden nur ein Linux-x86_64-System mit grafischer Oberfläche und – für den normalen AppImage-Mount – FUSE. Die AppImage ist kein statisch gelinktes Binary; sie benötigt weiterhin eine kompatible Linux-glibc-/X11-Basis.

```bash
sudo apt-get install python3-tk python3-pyinstaller libfuse2t64 desktop-file-utils
python3 -m pip install --user pyinstaller
APPIMAGETOOL=/pfad/zu/appimagetool packaging/appimage/build-appimage.sh
```

Die erzeugte Datei liegt danach unter:
```text
build/Hotdesk-0.1.0-x86_64.AppImage
```

Starten:
```bash
./build/Hotdesk-0.1.0-x86_64.AppImage
```

FUSE kann nicht automatisch aus der bereits laufenden AppImage heraus installiert werden, weil FUSE bereits zum Mounten benötigt wird. Der separate Helfer fragt nach einer Bestätigung:
```bash
./packaging/appimage/install-fuse.sh
```

Ohne FUSE kann der AppImage-Runtime-Fallback verwendet werden:
```bash
./build/Hotdesk-0.1.0-x86_64.AppImage --appimage-extract-and-run
```

## Daten und Sicherung

### Automatisches Backup mit Zeitstempel

Im Menü `Einstellungen` können Sie über **Backup mit Zeitstempel** ein automatisches SQLite-Backup mit Zeitstempel im Dateinamen erstellen. Die Datei wird im gewählten Verzeichnis unter `hotdesk_backup_YYYYMMDD_HHMMSS.sqlite` gespeichert.

### JSON-Export

Hotdesk unterstützt den Export aller Daten als JSON-Datei mit SHA-256-Prüfsumme. Über **JSON exportieren** im Menü `Einstellungen` werden alle Tabellen (Kunden, Produkte, Rechnungen, Positionen, Zahlungen, Audit-Log) als strukturierte JSON-Datei exportiert. Zusätzlich wird eine `.zip`-Datei mit der JSON-Datei und der Prüfsumme erstellt.

Die exportierten Daten enthalten:
- Alle Datensätze mit Metadaten (Export-Datum, Version)
- SHA-256-Prüfsumme zur Integritätsprüfung
- Begleitende `.sha256`-Datei

### PCAS-Import

Im Menü `Einstellungen` öffnen Sie `PCAS-Import`. Die Implementierung unterstützt die auf der PCAS-Schnittstellenseite dokumentierten Dateien:

- `Kunden.txt`: Debitoren-/Kundenstammdaten, Semikolon-getrennt, Felder gemäß PCAS-Schnittstellenbeschreibung
- `RAImport1`: Rechnungsausgangssätze im formatierten PCAS-Import, 153 Zeichen pro Satz

Die Dateien werden mit `UTF-8`, Windows-1252 oder Latin-1 gelesen. Vor dem Import sollten Sie ein Hotdesk-Backup erstellen. Der Import ist mit einem Audit-Eintrag versehen; doppelte Belegnummern werden nicht erneut angelegt. Nicht eindeutig erkennbare Datensätze werden übersprungen und in der GUI zusammengefasst.

Die aktuelle Umsetzung ist ein dokumentierter PCAS-Standard-Line-Import. Andere PCAS-Versionen, native `.mdb`/`.dbf`-Datenbanken und proprietäre Binärformate werden nicht automatisch verändert; dafür ist eine konkrete Datei/Feldprobe erforderlich.

Die Fehlermeldungen im neuen PCAS-Import zeigen nun detailliert an, welche Zeilen übersprungen wurden und warum (zu wenige Felder, leere Belegnummer, fehlender Kunde, ungültiger Betrag, Datumsfehler).

### Einstellungen und neue Features

Im Menü `Einstellungen` finden Sie die folgenden neuen Funktionen:

- **Backup erstellen**: Manuelles Backup mit Dateiauswahl
- **Backup mit Zeitstempel**: Automatisches Backup mit Zeitstempel im Verzeichnis
- **JSON exportieren**: Export aller Daten als JSON mit Prüfsumme

Die Einstellungen-Seite zeigt nun auch die Option **JSON exportieren** und **Backup mit Zeitstempel** neben den bestehenden Funktionen.

### Tastenkürzel

```
Ctrl+N: Neuer Kunde
Ctrl+I: Neue Rechnung
F1:   Hilfe
F5:   Aktuelle Ansicht aktualisieren
F12:  Über Hotdesk (Versionsinfo und Prüfsumme)
```

### Splash-Screen

Beim Start von Hotdesk wird ein Splash-Screen mit Fortschrittsbalken angezeigt, bis die Anwendung vollständig geladen ist.

### Über-Dialog

Drücken Sie **F12**, um den Über-Dialog zu öffnen. Dieser zeigt:
- Anwendungsname und Version
- Lizenzinformation
- Datenbank-Pfad und -Größe
- SHA-256-Prüfsumme der Datenbank

## Installation

### Python-Abhängigkeiten

```bash
python3 -m pip install --user reportlab PyPDF2
```

### Entwicklung

```bash
python3 -m py_compile app/*.py
python3 -m py_compile hotdesk/__init__.py
```

### Testing

```bash
python3 -m py_compile app/*.py
```

### Sicherheitsprüfung

```bash
# Integrität prüfen
python3 scripts/check_integrity.py --verify

# GPG-Signatur prüfen
./scripts/sign_appimage.sh --verify

# Vollständige Verifizierung
./scripts/verify.sh
```

## Lizenz

Hotdesk steht unter der [MIT License](LICENSE).

---

*Letzte Aktualisierung: 2026-09-25*
*Hotdesk v0.1.1 – Sicherheits-Updates und Projektabschluss*