# Beitragen zu Hotdesk

Vielen Dank für Ihr Interesse an Hotdesk! Wir freuen uns über Beiträge.

## Richtlinien

### Voraussetzungen
- Python 3.11 oder höher
- Git
- pyInstaller (für AppImage-Builds)

### Entwicklungsablauf
1. Fork das Repository
2. Erstelle einen Feature-Branch (`git checkout -b feature/NeueFunktion`)
3. Implementiere deine Änderungen
4. Führe Tests aus
5. Erstelle einen Commit (`git commit -m 'Neue Funktion hinzufügen'`)
6. Push zum Branch (`git push origin feature/NeueFunktion`)
7. Öffne einen Pull Request

### Code-Standards
- Python-Code nach PEP 8
- Deutsche Kommentierung
- Typhints verwenden (Python 3.11+)
- SQLite-Datenbank-Operationen in `app/desktop_storage.py` belassen
- GUI-Änderungen in `app/desktop_app.py`

### Pull Request Checks
- Alle bestehenden Funktionen müssen weiterhin funktionieren
- Keine neuen Abhängigkeiten ohne Diskussion
- AppImage muss weiterhin gebaut werden können
- Dateigröße der AppImage sollte unter 50 MB bleiben

## Reporting von Bugs

Bitte nutze das [Issue-Tracker](https://github.com/HAX73w0rlD/Hotdesk-0.1.0/issues) und gib folgende Informationen an:
- Betriebssystem und Version
- Python-Version
- Schritte zur Reproduktion
- Erwartetes vs. tatsächliches Verhalten
- Eventuelle Fehlermeldungen

## Feature Requests

Bitte eröffne ein Issue mit dem Label `enhancement` und beschreibe:
- Was das Feature lösen soll
- Warum es notwendig ist
- Vorschlag für die Implementierung

## Fragen?

Eröffne ein Issue oder kontaktiere **HAX73w0rlD** direkt.
