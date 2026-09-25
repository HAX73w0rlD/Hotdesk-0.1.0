# Sicherheit

## Melden von Sicherheitslücken

Bitte melden Sie Sicherheitslücken per E-Mail an den Maintainer anstelle über das öffentliche Issue-Tracker.

## Datenschutz

Hotdesk speichert alle Daten lokal in einer SQLite-Datenbank unter `~/.local/share/hotdesk/hotdesk.sqlite`. Es werden **keine Daten an externe Server gesendet**. Die AppImage enthält keine Telemetrie oder externen Verbindungen.

### Daten, die lokal gespeichert werden:
- Kundendaten
- Rechnungsdaten
- Produktinformationen
- Zahlungsdaten
- Audit-Log

### Datenschutz-Hinweis

Da alle Daten lokal auf dem Gerät gespeichert werden, liegt die vollständige Kontrolle beim Nutzer. Für Backups empfehlen wir regelmäßige Kopien des SQLite-Datenbank-Verzeichnisses.

## Sicherheitshinweise

- Die AppImage wird **nicht mit Internetverbindung** ausgeliefert
- Keine Telemetrie oder Analytics
- Keine externen API-Abhängigkeiten
- Alle Verschlüsselung und Zugriff erfolgt lokal
- Für produktiven Einsatz mit steuerlichen Daten: **rechtliche Prüfung erforderlich**
