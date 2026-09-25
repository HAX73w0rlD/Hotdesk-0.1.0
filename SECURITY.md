# Hotdesk Sicherheitsdokumentation

## Übersicht

Diese Dokumentation beschreibt alle in der Hotdesk Desktop-Anwendung implementierten Sicherheitsmaßnahmen zum Schutz vor unbefugter Kopie, Modifikation und Manipulation.

---

## 1. SHA-256 Prüfsummen-Verifikation

### Beschreibung
Alle Python-Quelldateien, Konfigurationsdateien und die AppImage-Datei werden mit SHA-256-Prüfsummen gesichert. Die Prüfsummen werden in der Datei `INTEGRITY.json` gespeichert.

### Funktionsweise
- **`scripts/check_integrity.py`** berechnet die SHA-256-Prüfsumme aller geschützten Dateien
- Bei jedem App-Start wird die Integrität automatisch geprüft
- Bei Modifikation wird eine Warnung angezeigt
- Die INTEGRITY.json wird automatisch mit aktuellen Prüfsummen aktualisiert

### Geschützte Dateien
- `app/*.py` – Alle Python-Quelldateien der Anwendung
- `app/config/*.py` – Konfigurationsdateien
- `hotdesk/*.py` – Hauptmodul
- `packaging/appimage/*` – AppImage-Verpackungsdateien
- `Hotdesk-0.1.0-x86_64.AppImage` – Die AppImage-Datei selbst
- `pyproject.toml`, `README.md` – Projektdateien

### Nutzung
```bash
# Prüfsummen generieren
python3 scripts/check_integrity.py --generate

# Integrität prüfen
python3 scripts/check_integrity.py --verify

# Prüfsummen aktualisieren
python3 scripts/check_integrity.py --update
```

---

## 2. GPG-Signatur für AppImage

### Beschreibung
Die AppImage-Datei wird mit einer GPG-Signatur gesichert. Dies stellt die Authentizität und Unversehrtheit der verteilten Datei sicher.

### Funktionsweise
- **`scripts/sign_appimage.sh`** erstellt eine GPG-Detached-Signatur
- RSA-4096 Schlüssel mit SHA512-Hash-Algorithmus
- Es werden sowohl binäre (.sig) als auch ASCII-kodierende (.asc) Signaturen erstellt
- Die Signatur-Informationen werden in `signature_info.json` gespeichert

### Verifizierung
```bash
# AppImage signieren
./scripts/sign_appimage.sh

# Signatur verifizieren
./scripts/sign_appimage.sh --verify

# GPG-Informationen anzeigen
./scripts/sign_appimage.sh --gpg-info
```

### Signaturprüfung mit verify.sh
```bash
./scripts/verify.sh
```
Die Verifizierung prüft:
1. Existenz der AppImage-Datei
2. GPG-Signatur (binär und ASCII)
3. SHA-256-Prüfsumme gegen Signature-Info
4. INTEGRITY.json Integrität
5. Lizenzdatei-Existenz
6. Python-Syntaxprüfung

---

## 3. Lizenzschlüssel-Validierung

### Beschreibung
Die Anwendung prüft bei jedem Start eine Lizenzdatei. Ohne gültige Lizenz wird eine Trial-Nachricht angezeigt. Es gibt vier Lizenztypen.

### Lizenztypen
| Typ | Tage | Features |
|-----|------|----------|
| **Trial** | 14 Tage | Grundfunktionen |
| **Basic** | 365 Tage | PDF-Export, Backup |
| **Pro** | Unbegrenzt | DATEV, PCAS-Import, DATANORM |
| **Enterprise** | Unbegrenzt | Alle Features, Support, API |

### Funktionsweise
- **`scripts/license_check.py`** prüft die Lizenzdateien
- Lizenzdateien werden gesucht in:
  - Projektverzeichnis: `.hotdesk/license.key`
  - Benutzerverzeichnis: `~/.hotdesk/license.key`
  - Verschlüsselte Lizenz: `~/.hotdesk/license.enc`
- Trial-Status wird über das Installationsdatum in der SQLite-Datenbank verfolgt
- Bei Ablauf der Trial-Version wird die Anwendung blockiert

### Lizenzgenerierung
```bash
# Testversion generieren
python3 scripts/generate_license.py --generate --type trial

# Professionelle Lizenz generieren
python3 scripts/generate_license.py --generate --type pro --customer "Max Mustermann" --email max@example.com

# Alle Lizenzen auflisten
python3 scripts/generate_license.py --list

# Lizenz widerrufen
python3 scripts/generate_license.py --revoke HD-ABCD1234EF567890
```

### Lizenzdatei-Struktur
- `license.key` – Einfache Text-Lizenzdatei
- `license.json` – JSON-Lizenzdatei für Parsing
- `license.enc` – Verschlüsselte Lizenzdatei (Base64 + XOR)
- `license_info.json` – Metadaten über die Lizenz

---

## 4. Anti-Tampering Schutz

### Beschreibung
Die AppImage-Datei selbst wird bei jedem Start auf Integrität geprüft. Wird eine Modifikation erkannt, sperrt sich die Anwendung selbst.

### Funktionsweise in `app/desktop_storage.py`
- Bei Initialisierung der `Database`-Klasse wird ein Integritäts-Check durchgeführt
- Der SHA-256-Hash der AppImage-Datei wird mit dem gespeicherten Wert verglichen
- Bei Abweichung wird die Anwendung sofort beendet
- Alle Integritätsprüfungen werden im Audit-Log protokolliert

### Selbstschutz-Mechanismus
```
AppStart → Integritätsprüfung → Prüfe AppImage-Hash → Prüfe Lizenz → Prüfe INTEGRITY.json
     ↓                              ↓                       ↓              ↓
  Erlaubt                        Blockiert              Blockiert        Blockiert
```

### Verschlüsselte Konfiguration
- **`app/config/encrypted_config.py`** bietet verschlüsselte Speicherung sensibler Daten
- Verwendung von PBKDF2-HMAC-SHA256 mit 100.000 Iterationen
- Konfigurationsdatei unter `~/.config/hotdesk/config.enc`
- Schlüsseldatei unter `~/.config/hotdesk/.config_key` (Berechtigung: 600)
- Sensible Daten werden vor dem Speichern verschlüsselt

---

## 5. Sicherheitsarchitektur

### Verteidigungsstrategie (Defense in Depth)

```
┌─────────────────────────────────────────────┐
│           SCHICHT 1: AppImage-Signatur       │
│         (GPG-Detached-Signatur)              │
│         Verifiziert Authentizität            │
├─────────────────────────────────────────────┤
│           SCHICHT 2: SHA-256 Prüfsummen      │
│         (INTEGRITY.json)                     │
│         Verifiziert Datei-Integrität         │
├─────────────────────────────────────────────┤
│           SCHICHT 3: Lizenzprüfung           │
│         (license_check.py)                   │
│         Verifiziert Berechtigung             │
├─────────────────────────────────────────────┤
│           SCHICHT 4: Anti-Tampering          │
│         (desktop_storage.py)                 │
│         Blockiert modifizierte AppImage      │
├─────────────────────────────────────────────┤
│           SCHICHT 5: Verschlüsselte Config   │
│         (encrypted_config.py)                │
│         Schützt sensible Daten               │
└─────────────────────────────────────────────┘
```

### Audit-Logging
Alle Sicherheitsrelevante Ereignisse werden im SQLite-Audit-Log protokolliert:
- Integritätsprüfungen
- Lizenzänderungen
- Modifikationsversuche
- Konfigurationsänderungen

---

## 6. Dateireferenzen

| Datei | Beschreibung |
|-------|-------------|
| `INTEGRITY.json` | SHA-256 Prüfsummen aller geschützten Dateien |
| `scripts/check_integrity.py` | Integritätsprüfung |
| `scripts/sign_appimage.sh` | GPG-Signatur-Erstellung |
| `scripts/verify.sh` | Vollständige Verifizierung |
| `scripts/license_check.py` | Lizenzprüfung |
| `scripts/generate_license.py` | Lizenzgenerierung |
| `app/config/encrypted_config.py` | Verschlüsselte Konfiguration |
| `.hotdesk/` | Lizenz- und Sicherheitsdateien |
| `~/.config/hotdesk/` | Verschlüsselte Konfigurationsdateien |
| `~/.hotdesk/license.key` | Lizenzschlüssel-Datei |
| `~/.hotdesk/license.enc` | Verschlüsselte Lizenzdatei |

---

## 7. Wartung und Aktualisierung

### Prüfsummen aktualisieren
Wenn Dateien geändert werden müssen, wird die INTEGRITY.json automatisch aktualisiert:
```bash
python3 scripts/check_integrity.py --generate
```

### GPG-Schlüssel rotieren
Für die Sicherheit empfiehlt sich eine regelmäßige Rotation:
```bash
# Neuen Schlüssel erstellen und AppImage neu signieren
./scripts/sign_appimage.sh
```

### Lizenz-Überprüfung
Regelmäßige Überprüfung der Lizenzdateien:
```bash
python3 scripts/license_check.py --status
```

---

## 8. Einschränkungen und Hinweise

### Hinweise
- Die XOR-Verschlüsselung in `encrypted_config.py` und der Lizenzdateien dient als Basis
- Für Produktionsumgebungen wird AES-256-GCM empfohlen (z.B. `cryptography`-Bibliothek)
- Die GPG-Signatur sollte mit einem sicheren Schlüssel erstellt werden
- Passwörter und Schlüssel sollten sicher gespeichert werden
- Die Trial-Prüfung basiert auf dem Systemdatum; Systemuhr-Manipulation kann die Prüfung umgehen

### Empfohlene Verbesserungen für Produktion
1. Ersetzen Sie XOR-Verschlüsselung durch AES-256-GCM
2. Verwenden Sie Hardware-Sicherheitsschlüssel (HSM/Keychain)
3. Implementieren Sie OTA-Integritätsprüfung
4. Fügen Sie Code-Obfuscation hinzu
5. Implementieren Sie Telemetrie für Sicherheitswarnungen

---

*Letzte Aktualisierung: 2026-09-25*
*Hotdesk Version 0.1.0*
*Sicherheitsmaßnahmen: SHA-256, GPG-Signatur, Lizenzprüfung, Anti-Tampering, Verschlüsselte Konfiguration*
