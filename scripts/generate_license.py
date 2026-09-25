"""Lizenzschlüssel-Generator für Hotdesk.

Generiert Lizenzschlüssel für verschiedene Lizenztypen.
Erstellt sowohl einfache Text- als auch verschlüsselte Lizenzdateien.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

HOTDESK_DIR = Path.home() / ".hotdesk"
PROJECT_LICENSE_DIR = Path(__file__).resolve().parent.parent / ".hotdesk"
LICENSE_FILE = HOTDESK_DIR / "license.key"
ENCRYPTED_LICENSE_FILE = HOTDESK_DIR / "license.enc"
LICENSE_INFO_FILE = HOTDESK_DIR / "license_info.json"

SECRET_SALT = "hotdesk-secret-salt-2024"

VERIFY_SALT = "hotdesk-secret-salt-2024"

LICENSE_TYPES = {
    "trial": {"name": "Testversion", "days": 14},
    "basic": {"name": "Basic", "days": 365},
    "pro": {"name": "Professional", "days": 0},  # Unbegrenzt
    "enterprise": {"name": "Enterprise", "days": 0},
}


def generate_key() -> str:
    """Generiert einen zufälligen Lizenzschlüssel."""
    return f"HD-{secrets.token_hex(16).upper()}"


def compute_license_hash(license_type: str, key: str, timestamp: str) -> str:
    """Berechnet den Hash für die Lizenz."""
    return hashlib.sha256(
        f"{license_type}:{key}:{timestamp}:{SECRET_SALT}".encode()
    ).hexdigest()[:32]


def generate_license(
    license_type: str = "trial",
    customer_name: str = "Unknown",
    customer_email: str = "",
    days: int | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Generiert einen Lizenzschlüssel.

    Args:
        license_type: Typ der Lizenz (trial, basic, pro, enterprise).
        customer_name: Name des Kunden.
        customer_email: E-Mail des Kunden.
        days: Anzahl der Tage (nur für zeitlich begrenzte Lizenzen).
        output_dir: Verzeichnis für die Ausgabe-Dateien.

    Returns:
        Dictionary mit den Lizenzinformationen.
    """
    if license_type not in LICENSE_TYPES:
        raise ValueError(
            f"Ungültiger Lizenztyp: {license_type}. "
            f"Verfügbare Typen: {list(LICENSE_TYPES.keys())}"
        )

    if days is None:
        days = LICENSE_TYPES[license_type]["days"]

    timestamp = datetime.now().isoformat()

    if days > 0:
        expiry_date = (datetime.now() + timedelta(days=days)).isoformat()
    else:
        expiry_date = "unlimited"

    license_key = generate_key()
    license_hash = compute_license_hash(license_type, license_key, timestamp)

    license_data: dict[str, Any] = {
        "version": "1.0",
        "license_type": license_type,
        "license_name": LICENSE_TYPES[license_type]["name"],
        "key": license_key,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "timestamp": timestamp,
        "expiry_date": expiry_date,
        "hash": license_hash,
        "features": _get_features(license_type),
        "generated_at": datetime.now().isoformat(),
    }

    # Speichere die Lizenzdatei
    target_dir = output_dir or HOTDESK_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    # Text-Lizenzdatei
    license_text = _format_license_text(license_data)
    license_path = target_dir / "license.key"
    with open(license_path, "w", encoding="utf-8") as f:
        f.write(license_text)

    # JSON-Lizenzdatei (für einfache Parsing)
    license_json_path = target_dir / "license.json"
    with open(license_json_path, "w", encoding="utf-8") as f:
        json.dump(license_data, f, indent=2)

    # Verschlüsselte Lizenzdatei
    encrypted_path = target_dir / "license.enc"
    _save_encrypted_license(license_data, encrypted_path)

    # Lizenz-Info-Datei
    info_data = {
        "license_type": license_type,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "expiry_date": expiry_date,
        "generated_at": datetime.now().isoformat(),
        "key_id": hashlib.sha256(license_key.encode()).hexdigest()[:16],
    }
    info_path = target_dir / "license_info.json"
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info_data, f, indent=2)

    # Projektverzeichnis-Lizenzdatei erstellen
    project_license_path = PROJECT_LICENSE_DIR / "license.key"
    if not project_license_path.exists():
        PROJECT_LICENSE_DIR.mkdir(parents=True, exist_ok=True)
        with open(project_license_path, "w", encoding="utf-8") as f:
            f.write(license_text)

    print(f"✅ Lizenz erfolgreich generiert!")
    print(f"   Typ: {LICENSE_TYPES[license_type]['name']}")
    print(f"   Schlüssel: {license_key}")
    print(f"   Kunde: {customer_name} <{customer_email}>")
    print(f"   Gültig bis: {expiry_date}")
    print(f"   Hash: {license_hash}")
    print(f"")
    print(f"   Dateien erstellt:")
    print(f"   - {license_path}")
    print(f"   - {license_json_path}")
    print(f"   - {encrypted_path}")
    print(f"   - {info_path}")

    return license_data


def _get_features(license_type: str) -> list[str]:
    """Gibt die Features für den Lizenztyp zurück."""
    features_map: dict[str, list[str]] = {
        "trial": ["basic_features"],
        "basic": ["basic_features", "pdf_export", "backup"],
        "pro": ["basic_features", "pdf_export", "backup", "datev", "pcas_import", "datanorm"],
        "enterprise": ["all_features", "priority_support", "custom_branding", "api_access"],
    }
    return features_map.get(license_type, ["basic_features"])


def _format_license_text(data: dict[str, Any]) -> str:
    """Formatiert die Lizenz als Textdatei."""
    return (
        f"HOTDESK-LICENSE:{data['license_type']}:{data['key']}:{data['timestamp']}:{data['hash']}\n"
        f"Customer: {data['customer_name']}\n"
        f"Email: {data['customer_email']}\n"
        f"Type: {data['license_name']}\n"
        f"Expiry: {data['expiry_date']}\n"
        f"Version: {data['version']}\n"
    )


def _save_encrypted_license(data: dict[str, Any], output_path: Path) -> None:
    """Speichert die Lizenz verschlüsselt."""
    try:
        import base64
        # Einfache XOR-Verschlüsselung (für Produktion AES verwenden)
        json_bytes = json.dumps(data, indent=2).encode("utf-8")
        encrypted = bytes(b ^ 0x42 for b in json_bytes)
        encoded = base64.b64encode(encrypted)
        with open(output_path, "wb") as f:
            f.write(encoded)
    except Exception:
        import base64
        # Fallback: einfache Base64-Kodierung
        encoded = base64.b64encode(json.dumps(data, indent=2).encode("utf-8"))
        with open(output_path, "wb") as f:
            f.write(encoded)


def revoke_license(license_key: str, output_dir: Path | None = None) -> bool:
    """
    Widerruft einen Lizenzschlüssel.

    Args:
        license_key: Der zu widerrufende Lizenzschlüssel.
        output_dir: Verzeichnis für die Widerrufs-Datei.

    Returns:
        True wenn der Lizenzschlüssel erfolgreich widerrufen wurde.
    """
    target_dir = output_dir or HOTDESK_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    # Erstelle Widerrufs-Datei
    revocation_data = {
        "revoked_key": license_key,
        "revoked_at": datetime.now().isoformat(),
        "reason": "manual_revocation",
    }
    revocation_path = target_dir / "license_revoked.key"
    with open(revocation_path, "w", encoding="utf-8") as f:
        json.dump(revocation_data, f, indent=2)

    # Lösche die aktiven Lizenzdateien
    for f in [LICENSE_FILE, HOTDESK_DIR / "license.json", HOTDESK_DIR / "license.enc"]:
        if f.exists():
            f.unlink()

    # Erstelle eine ungültige Lizenzdatei
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        f.write(f"HOTDESK-LICENSE:revoked:{license_key}:{datetime.now().isoformat()}:00000000000000000000000000000000\n")

    print(f"✅ Lizenzschlüssel {license_key} wurde widerrufen.")
    return True


def list_licenses() -> None:
    """Listet alle vorhandenen Lizenzdateien auf."""
    for license_path in [LICENSE_FILE, HOTDESK_DIR / "license.json", HOTDESK_DIR / "license.enc"]:
        if license_path.exists():
            print(f"📄 {license_path}")
            try:
                content = license_path.read_text(encoding="utf-8")
                if license_path.suffix == ".json":
                    print(json.dumps(json.loads(content), indent=2))
                else:
                    print(content[:200])
            except Exception:
                pass
        else:
            print(f"❌ {license_path} (nicht vorhanden)")


def main() -> None:
    """Hauptfunktion für den Aufruf von der Kommandozeile."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Lizenzschlüssel-Generator für Hotdesk"
    )
    parser.add_argument(
        "--generate", action="store_true",
        help="Generiert eine neue Lizenz"
    )
    parser.add_argument(
        "--type", default="trial",
        choices=list(LICENSE_TYPES.keys()),
        help="Lizenztyp (standard: trial)"
    )
    parser.add_argument(
        "--customer", default="Unknown",
        help="Kundenname"
    )
    parser.add_argument(
        "--email", default="",
        help="Kunden-E-Mail"
    )
    parser.add_argument(
        "--days", type=int, default=None,
        help="Anzahl der Tage (nur für zeitlich begrenzte Lizenzen)"
    )
    parser.add_argument(
        "--revoke", metavar="KEY",
        help="Widerruft einen Lizenzschlüssel"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Listet alle Lizenzen auf"
    )
    parser.add_argument(
        "--dir", type=Path, default=None,
        help="Ausgabeverzeichnis"
    )

    args = parser.parse_args()

    HOTDESK_DIR.mkdir(parents=True, exist_ok=True)

    if args.revoke:
        revoke_license(args.revoke, args.dir)
    elif args.list:
        list_licenses()
    elif args.generate:
        generate_license(
            license_type=args.type,
            customer_name=args.customer,
            customer_email=args.email,
            days=args.days,
            output_dir=args.dir,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
