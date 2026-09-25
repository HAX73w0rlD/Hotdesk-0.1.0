"""Verschlüsselte Konfigurationsdatei für sensible Hotdesk-Daten.

Dieses Modul bietet Funktionen zum Verschlüsseln und Entschlüsseln
sensibler Konfigurationsdaten wie API-Schlüssel, Passwörter und
andere geheime Informationen.

Für Produktionsumgebungen sollte AES-256-GCM statt XOR-Verschlüsselung
verwendet werden. Diese Implementierung dient als Basis.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any

# Verschlüsselungs-Konfiguration
ENCRYPTION_SALT = b"hotdesk-encryption-salt-2024"
CONFIG_DIR = Path.home() / ".config" / "hotdesk"
ENCRYPTED_CONFIG_FILE = CONFIG_DIR / "config.enc"
CONFIG_KEY_FILE = CONFIG_DIR / ".config_key"

# Simple XOR-Verschlüsselung (für Demo)
# In Produktion: cryptography.fernet oder PyCryptodome verwenden


def _derive_key(password: str) -> bytes:
    """Leitet einen Verschlüsselungsschlüssel aus einem Passwort ab."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        ENCRYPTION_SALT,
        100_000,
        dklen=32,
    )


def _xor_encrypt(data: bytes, key: bytes) -> bytes:
    """Verschlüsselt Daten mit XOR."""
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _xor_decrypt(data: bytes, key: bytes) -> bytes:
    """Entschlüsselt Daten mit XOR (identisch mit XOR)."""
    return _xor_encrypt(data, key)


def encrypt_config(config_data: dict[str, Any], password: str | None = None) -> str:
    """
    Verschlüsselt eine Konfigurations-Dictionary.

    Args:
        config_data: Das zu verschlüsselnde Konfigurations-Dictionary.
        password: Passwort für die Verschlüsselung. Wenn None, wird ein
                  zufälliges Passwort generiert.

    Returns:
        Base64-kodierter verschlüsselter String.
    """
    if password is None:
        password = secrets.token_hex(32)

    key = _derive_key(password)
    json_data = json.dumps(config_data, indent=2, sort_keys=True).encode("utf-8")
    encrypted = _xor_encrypt(json_data, key)
    encoded = base64.b64encode(encrypted).decode("utf-8")

    return encoded


def decrypt_config(encrypted_data: str, password: str) -> dict[str, Any]:
    """
    Entschlüsselt eine verschlüsselte Konfiguration.

    Args:
        encrypted_data: Base64-kodierter verschlüsselter String.
        password: Passwort für die Entschlüsselung.

    Returns:
        Das entschlüsselte Konfigurations-Dictionary.
    """
    key = _derive_key(password)
    encrypted = base64.b64decode(encrypted_data)
    decrypted = _xor_decrypt(encrypted, key)
    return json.loads(decrypted.decode("utf-8"))


class SecureConfig:
    """Sichere Konfigurationsverwaltung mit verschlüsselter Speicherung."""

    def __init__(self) -> None:
        self.config_dir = CONFIG_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._config: dict[str, Any] = {}
        self._encryption_password: str | None = None

    def load(self, config_file: Path | None = None) -> bool:
        """
        Lädt die verschlüsselte Konfiguration.

        Args:
            config_file: Pfad zur verschlüsselten Konfigurationsdatei.

        Returns:
            True wenn erfolgreich geladen.
        """
        file_path = config_file or ENCRYPTED_CONFIG_FILE
        if not file_path.exists():
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                encrypted_data = f.read()

            # Versuche mit gespeichertem Passwort zu entschlüsseln
            key_file = CONFIG_KEY_FILE
            if key_file.exists():
                with open(key_file, "r", encoding="utf-8") as kf:
                    self._encryption_password = kf.read().strip()
                self._config = decrypt_config(encrypted_data, self._encryption_password)
                return True
        except Exception as exc:
            print(f"[SECURE_CONFIG] Fehler beim Laden: {exc}")

        return False

    def save(self, config_data: dict[str, Any], password: str) -> None:
        """
        Speichert die Konfiguration verschlüsselt.

        Args:
            config_data: Zu speichernde Konfiguration.
            password: Verschlüsselungs-Passwort.
        """
        self._encryption_password = password
        encrypted = encrypt_config(config_data, password)

        # Speichere verschlüsselte Konfiguration
        with open(ENCRYPTED_CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(encrypted)

        # Speichere das Passwort separat (in Produktion: Hardware-Safe oder Keychain)
        with open(CONFIG_KEY_FILE, "w", encoding="utf-8") as f:
            f.write(password)
        os.chmod(str(CONFIG_KEY_FILE), 0o600)

        self._config = config_data.copy()

    def get(self, key: str, default: Any = None) -> Any:
        """Gibt einen Konfigurationswert zurück."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Setzt einen Konfigurationswert."""
        self._config[key] = value

    def get_all(self) -> dict[str, Any]:
        """Gibt alle Konfigurationswerte zurück."""
        return self._config.copy()

    def has_sensitive_data(self) -> bool:
        """Prüft ob die Konfiguration sensible Daten enthält."""
        sensitive_keys = {"api_key", "password", "secret", "token", "encryption_key"}
        return any(k in self._config for k in sensitive_keys)


def create_default_secure_config() -> dict[str, Any]:
    """Erstellt eine Standard-verschlüsselte Konfiguration."""
    return {
        "security": {
            "enable_integrity_check": True,
            "enable_license_check": True,
            "enable_encrypted_config": True,
            "max_failed_checks": 3,
            "log_suspicious_activity": True,
        },
        "encryption": {
            "algorithm": "xor-aes256",
            "key_derivation": "pbkdf2-sha256",
            "iterations": 100000,
        },
        "anti_tampering": {
            "check_on_startup": True,
            "block_on_tampering": True,
            "alert_on_modification": True,
        },
    }


def main() -> None:
    """Hauptfunktion."""
    import argparse

    parser = argparse.ArgumentParser(description="Verschlüsselte Konfiguration für Hotdesk")
    parser.add_argument("--init", action="store_true", help="Initialisiert die verschlüsselte Konfiguration")
    parser.add_argument("--load", action="store_true", help="Lädt die verschlüsselte Konfiguration")
    parser.add_argument("--get", metavar="KEY", help="Gibt einen Wert zurück")
    parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="Setzt einen Wert")
    parser.add_argument("--password", default="", help="Verschlüsselungs-Passwort")

    args = parser.parse_args()

    config = SecureConfig()

    if args.init:
        default_config = create_default_secure_config()
        if args.password:
            config.save(default_config, args.password)
            print("✅ Verschlüsselte Konfiguration initialisiert.")
        else:
            print("❌ Bitte ein Passwort mit --password angeben.")
    elif args.load:
        if config.load():
            if args.get:
                print(config.get(args.get))
            else:
                print(json.dumps(config.get_all(), indent=2))
        else:
            print("❌ Konfiguration konnte nicht geladen werden.")
    elif args.set:
        key, value = args.set
        config.set(key, value)
        if args.password:
            config.save(config.get_all(), args.password)
            print(f"✅ Wert '{key}' gesetzt.")

    if args.init and not args.password:
        # Erstelle Standardkonfiguration mit zufälligem Passwort
        password = secrets.token_hex(16)
        default_config = create_default_secure_config()
        config.save(default_config, password)
        print(f"✅ Standardkonfiguration erstellt.")
        print(f"   Passwort: {password}")
        print(f"   Speichere dieses Passwort sicher!")


if __name__ == "__main__":
    main()
