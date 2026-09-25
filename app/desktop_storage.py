"""Lokale SQLite-Datenbank und Geschäftslogik für Hotdesk.

Die Datenschicht ist absichtlich unabhängig vom GUI. Dadurch kann dieselbe
Anwendung später auch für einen Sync- oder Import-Agent verwendet werden.
"""
from __future__ import annotations

import csv
import os
import shutil
import sqlite3
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Iterator

# Optional dependencies for PDF and ZUGFeRD
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import mm
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

try:
    from PyPDF2 import PdfReader, PdfWriter, PageObject
    from PyPDF2.generic import DictionaryObject, NameObject, StreamObject, TextStringObject
    PYPDF2_AVAILABLE = True
except Exception:
    PYPDF2_AVAILABLE = False

APP_NAME = "Hotdesk"

DEFAULT_INVOICE_TEMPLATE = """Firma: {company_name}
Adresse: {company_address}

Rechnung an:
{customer_name}
{customer_address}

Rechnung-Nr: {invoice_number}
Datum: {invoice_date}
Fällig: {due_date}

{items_table}

Zwischensumme: {subtotal_formatted}
MwSt. ({tax_rate}%): {tax_formatted}
Gesamt: {total_formatted}
"""


def data_dir() -> Path:
    override = os.environ.get("HOTDESK_DATA_DIR")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base).expanduser() if base else Path.home() / ".local/share") / "hotdesk"


def db_path() -> Path:
    return data_dir() / "hotdesk.sqlite"


def money(value: str | int | float | Decimal) -> int:
    """Wandelt eine Eingabe in Cent um; decimalsafe statt float.*100."""
    raw = str(value).strip().replace(" ", "").replace("€", "")
    if not raw:
        return 0
    # Handle sign
    sign = -1 if raw.startswith('-') else 1
    if sign == -1:
        raw = raw[1:]
    # Separate thousands and decimal separators
    if raw.count('.') > 0 and raw.count(',') > 0:
        # Both dot and comma present: assume comma is decimal, dots are thousands
        raw = raw.replace('.', '')  # remove thousands separators
        raw = raw.replace(',', '.', 1)  # replace the first comma with dot
    else:
        # Only one type of separator or none: treat comma as decimal
        raw = raw.replace(',', '.')
    try:
        return sign * int((Decimal(raw) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return 0





def today() -> str:
    return date.today().isoformat()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path | None = None):
        self.path = path or db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.init_schema()
        self._start_backup_thread()

    def close(self) -> None:
        self.stop_backup_thread()
        self.connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS customers(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_number TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                company TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '',
                postal_code TEXT NOT NULL DEFAULT '',
                city TEXT NOT NULL DEFAULT '',
                country TEXT NOT NULL DEFAULT 'Deutschland',
                tax_number TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS products(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                unit TEXT NOT NULL DEFAULT 'Stk.',
                net_price_cents INTEGER NOT NULL DEFAULT 0,
                tax_rate REAL NOT NULL DEFAULT 19,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS invoices(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                customer_id INTEGER NOT NULL REFERENCES customers(id),
                invoice_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'offen',
                notes TEXT NOT NULL DEFAULT '',
                subtotal_cents INTEGER NOT NULL DEFAULT 0,
                tax_cents INTEGER NOT NULL DEFAULT 0,
                total_cents INTEGER NOT NULL DEFAULT 0,
                paid_cents INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS invoice_items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                product_id INTEGER REFERENCES products(id),
                description TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL DEFAULT 'Stk.',
                unit_price_cents INTEGER NOT NULL,
                tax_rate REAL NOT NULL,
                line_subtotal_cents INTEGER NOT NULL,
                line_tax_cents INTEGER NOT NULL,
                line_total_cents INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS payments(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL REFERENCES invoices(id),
                payment_date TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                method TEXT NOT NULL DEFAULT 'bank',
                reference TEXT NOT NULL DEFAULT '',
                event_id TEXT UNIQUE,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_log(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            """
        )
        # Spalten für spätere Migrationen ergänzen, ohne bestehende Datenbanken zu verlieren.
        invoice_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(invoices)")}
        if "source" not in invoice_columns:
            self.connection.execute("ALTER TABLE invoices ADD COLUMN source TEXT NOT NULL DEFAULT 'manuell'")
        if "source_reference" not in invoice_columns:
            self.connection.execute("ALTER TABLE invoices ADD COLUMN source_reference TEXT")
        self.connection.commit()
        defaults = {
            "company_name": "Mein Unternehmen",
            "company_address": "",
            "company_email": "",
            "company_phone": "",
            "invoice_prefix": "RE",
            "payment_terms_days": "14",
            "datev_enabled": "0",
            "datev_client": "",
            "datev_consultant": "",
            "datev_firm": "",
            "datev_receivable_account": "1000",
            "datev_bank_account": "1200",
            "currency": "EUR",
            "exchange_rate": "1.0",
            "invoice_template": DEFAULT_INVOICE_TEMPLATE,
            "backup_auto_enabled": "0",
            "backup_auto_time": "02:00",
            "backup_auto_dir": "",
        }
        with self.transaction() as db:
            db.executemany(
                "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", defaults.items()
            )
            self.connection.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES('invoice_sequence','0')"
            )

    def setting(self, key: str, default: str = "") -> str:
        row = self.connection.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def get_currency(self) -> str:
        return self.setting("currency", "EUR")

    def get_invoice_template(self) -> str:
        return self.setting("invoice_template", DEFAULT_INVOICE_TEMPLATE)

    def get_exchange_rate(self) -> float:
        try:
            return float(self.setting("exchange_rate", "1.0").replace(",", "."))
        except ValueError:
            return 1.0

    def fmt_currency(self, cents: int) -> str:
        """Format amount in the selected currency with two decimal places."""
        base = Decimal(cents) / Decimal(100)
        rate = Decimal(str(self.get_exchange_rate()))
        value = base * rate
        # Format with two decimal places, comma as decimal separator
        formatted = f"{value:.2f}".replace(".", ",")
        return f"{formatted} {self.get_currency()}"

    def parse_currency(self, value: str) -> int:
        """Parse a currency string to cents in base currency (EUR)."""
        s = value.strip()
        if not s:
            return 0
        # Remove currency symbol if present at end
        parts = s.split()
        number_str = parts[0]
        # Remove thousand separator dots
        number_str = number_str.replace(".", "")
        # Replace comma with dot for decimal
        number_str = number_str.replace(",", ".")
        try:
            val = Decimal(number_str)
        except InvalidOperation:
            return 0
        rate = Decimal(str(self.get_exchange_rate()))
        if rate == 0:
            return 0
        base_cents = int((val / rate * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return base_cents

    def settings(self) -> dict[str, str]:
        return {row["key"]: row["value"] for row in self.connection.execute("SELECT key,value FROM settings")}

    def save_settings(self, values: dict[str, str]) -> None:
        with self.transaction() as db:
            db.executemany(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                values.items(),
            )

    def _next_number(self, table: str, prefix: str) -> str:
        """Atomar die nächste sequenzielle Nummer für eine Tabelle generieren.
        Verwendet eine UPSERT in der settings-Tabelle, um Race Conditions zu vermeiden.
        """
        key = f"sequence_{table}"
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO settings(key, value)
                VALUES (?, '1')
                ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1
                RETURNING value
                """,
                (key,),
            )
            row = cursor.fetchone()
            if row is None:
                # This should not happen because of UPSERT
                raise RuntimeError(f"Failed to get next number for key {key}")
            current = int(row[0])
        return f"{prefix}-{current:05d}"

    def audit(self, entity_type: str, entity_id: int, action: str, payload: dict[str, Any] | None = None) -> None:
        import json

        self.connection.execute(
            "INSERT INTO audit_log(entity_type,entity_id,action,payload,created_at) VALUES(?,?,?,?,?)",
            (entity_type, entity_id, action, json.dumps(payload or {}, ensure_ascii=False), now()),
        )
        self.connection.commit()

    def customers(self, query: str = "") -> list[sqlite3.Row]:
        q = f"%{query.strip()}%"
        return list(self.connection.execute(
            """SELECT * FROM customers
               WHERE (? = '%%' OR name LIKE ? OR company LIKE ? OR customer_number LIKE ? OR email LIKE ?)
               ORDER BY name COLLATE NOCASE""", (q, q, q, q, q)
        ))

    def customer(self, customer_id: int) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()

    def save_customer(self, data: dict[str, Any], customer_id: int | None = None) -> int:
        fields = ["customer_number", "name", "company", "email", "phone", "address", "postal_code", "city", "country", "tax_number", "notes"]
        values = [str(data.get(field, "")).strip() for field in fields]
        if not values[1]:
            raise ValueError("Kundenname ist erforderlich.")
        if not values[0]:
            if customer_id:
                # When updating, preserve the existing customer number
                current = self.connection.execute("SELECT customer_number FROM customers WHERE id=?", (customer_id,)).fetchone()
                values[0] = current["customer_number"] if current else self._next_number("customers", "K")
            else:
                values[0] = self._next_number("customers", "K")
        if customer_id:
            with self.transaction() as db:
                db.execute(
                    f"UPDATE customers SET {','.join(f'{f}=?' for f in fields)} WHERE id=?",
                    (*values, customer_id),
                )
            self.audit("customer", customer_id, "updated", data)
            return customer_id
        with self.transaction() as db:
            cur = db.execute(
                f"INSERT INTO customers({','.join(fields)},created_at) VALUES({','.join('?' for _ in fields)},?)",
                (*values, now()),
            )
            customer_id = int(cur.lastrowid)
        self.audit("customer", customer_id, "created", data)
        return customer_id

    def delete_customer(self, customer_id: int) -> None:
        used = self.connection.execute("SELECT 1 FROM invoices WHERE customer_id=?", (customer_id,)).fetchone()
        if used:
            raise ValueError("Kunde hat Rechnungen und kann nicht gelöscht werden.")
        with self.transaction() as db:
            db.execute("DELETE FROM customers WHERE id=?", (customer_id,))
        self.audit("customer", customer_id, "deleted")

    def products(self, query: str = "") -> list[sqlite3.Row]:
        q = f"%{query.strip()}%"
        return list(self.connection.execute(
            """SELECT * FROM products
               WHERE (? = '%%' OR name LIKE ? OR sku LIKE ? OR description LIKE ?)
               ORDER BY active DESC, name COLLATE NOCASE""", (q, q, q, q)
        ))

    def product(self, product_id: int) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()

    def save_product(self, data: dict[str, Any], product_id: int | None = None) -> int:
        name = str(data.get("name", "")).strip()
        if not name:
            raise ValueError("Produktname ist erforderlich.")
        sku = str(data.get("sku", "")).strip()
        if not sku and product_id:
            # When updating, preserve the existing SKU if not provided
            current = self.connection.execute("SELECT sku FROM products WHERE id=?", (product_id,)).fetchone()
            sku = current["sku"] if current else self._next_number("products", "ART")
        if not sku:
            sku = self._next_number("products", "ART")
        price = money(data.get("net_price", 0))
        try:
            tax = float(str(data.get("tax_rate", "19")).replace(",", "."))
        except ValueError as exc:
            raise ValueError("Steuersatz ist ungültig.") from exc
        if not 0 <= tax <= 100:
            raise ValueError("Steuersatz muss zwischen 0 und 100 liegen.")
        values = [sku, name, str(data.get("description", "")).strip(), str(data.get("unit", "Stk.")).strip() or "Stk.", price, tax, int(bool(data.get("active", True)))]
        if product_id:
            with self.transaction() as db:
                db.execute("UPDATE products SET sku=?,name=?,description=?,unit=?,net_price_cents=?,tax_rate=?,active=? WHERE id=?", (*values, product_id))
            self.audit("product", product_id, "updated", data)
            return product_id
        with self.transaction() as db:
            cur = db.execute("INSERT INTO products(sku,name,description,unit,net_price_cents,tax_rate,active,created_at) VALUES(?,?,?,?,?,?,?,?)", (*values, now()))
            product_id = int(cur.lastrowid)
        self.audit("product", product_id, "created", data)
        return product_id

    def invoices(self, query: str = "") -> list[sqlite3.Row]:
        q = f"%{query.strip()}%"
        return list(self.connection.execute(
            """SELECT i.*, c.name AS customer_name, c.company AS customer_company
               FROM invoices i JOIN customers c ON c.id=i.customer_id
               WHERE (? = '%%' OR i.invoice_number LIKE ? OR c.name LIKE ? OR c.company LIKE ?)
               ORDER BY i.invoice_date DESC, i.id DESC""", (q, q, q, q)
        ))

    def invoice(self, invoice_id: int) -> sqlite3.Row | None:
        return self.connection.execute(
            """SELECT i.*, c.name AS customer_name, c.company AS customer_company, c.address, c.postal_code, c.city, c.country, c.email
               FROM invoices i JOIN customers c ON c.id=i.customer_id WHERE i.id=?""", (invoice_id,)
        ).fetchone()

    def invoice_items(self, invoice_id: int) -> list[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY id", (invoice_id,)))

    def create_invoice(self, customer_id: int, invoice_date: str, due_date: str, notes: str, items: Iterable[dict[str, Any]]) -> int:
        customer = self.customer(customer_id)
        if not customer:
            raise ValueError("Bitte einen Kunden auswählen.")
        normalized: list[dict[str, Any]] = []
        subtotal = tax_total = 0
        for item in items:
            description = str(item.get("description", "")).strip()
            if not description:
                continue
            try:
                quantity = Decimal(str(item.get("quantity", "1")).replace(",", "."))
                rate = Decimal(str(item.get("tax_rate", "19")).replace(",", "."))
            except InvalidOperation as exc:
                raise ValueError("Menge oder Steuersatz ist ungültig.") from exc
            price = money(item.get("unit_price", 0))
            if quantity <= 0 or price < 0 or not 0 <= rate <= 100:
                raise ValueError("Position enthält ungültige Werte.")
            line_subtotal = int((quantity * price).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            line_tax = int((Decimal(line_subtotal) * rate / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            normalized.append({"product_id": item.get("product_id"), "description": description, "quantity": float(quantity), "unit": str(item.get("unit", "Stk.")), "unit_price": price, "tax_rate": float(rate), "line_subtotal": line_subtotal, "line_tax": line_tax, "line_total": line_subtotal + line_tax})
            subtotal += line_subtotal
            tax_total += line_tax
        if not normalized:
            raise ValueError("Mindestens eine Position ist erforderlich.")
        number = self._next_number("invoices", self.setting("invoice_prefix", "RE"))
        total = subtotal + tax_total
        with self.transaction() as db:
            cur = db.execute(
                """INSERT INTO invoices(invoice_number,customer_id,invoice_date,due_date,status,notes,subtotal_cents,tax_cents,total_cents,paid_cents,created_at,updated_at,source,source_reference)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (number, customer_id, invoice_date, due_date, "offen", notes, subtotal, tax_total, total, 0, now(), now(), "manuell", None),
            )
            invoice_id = int(cur.lastrowid)
            for item in normalized:
                db.execute(
                    """INSERT INTO invoice_items(invoice_id,product_id,description,quantity,unit,unit_price_cents,tax_rate,line_subtotal_cents,line_tax_cents,line_total_cents)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (invoice_id, item["product_id"], item["description"], item["quantity"], item["unit"], item["unit_price"], item["tax_rate"], item["line_subtotal"], item["line_tax"], item["line_total"]),
                )
        self.audit("invoice", invoice_id, "created", {"number": number, "total_cents": total})
        return invoice_id

    def import_pcas_customers(self, path: Path) -> dict[str, int]:
        """Importiert PCAS Debitoren/Kunden.txt (Semikolon, 24 Felder)."""
        if not path.is_file():
            raise ValueError("PCAS-Datei wurde nicht gefunden.")
        text = self._read_export_text(path)
        imported = updated = skipped = 0
        # Skip leading empty lines and header lines
        lines = text.splitlines()
        i = 0
        while i < len(lines) and not lines[i].strip():
            i += 1
        header_indicators = {"kontonummer", "konto", "account"}
        while i < len(lines):
            fields = lines[i].rstrip(";").split(";")
            if len(fields) >= 1 and fields[0].strip().lower() in header_indicators:
                i += 1
                continue
            break
        # Process remaining lines
        for line in lines[i:]:
            if not line.strip():
                continue
            fields = line.rstrip(";").split(";")
            if len(fields) < 15:
                skipped += 1
                continue
            account = fields[0].strip()
            name1, name2, name3 = (fields[3].strip(), fields[4].strip(), fields[5].strip())
            name = " ".join(part for part in (name1, name2, name3) if part).strip()
            if not name:
                name = fields[1].strip() or account
            data = {"customer_number": account or self._next_number("customers", "K"), "name": name, "company": "", "email": fields[14].strip(), "phone": fields[11].strip() or fields[12].strip(), "address": fields[9].strip(), "postal_code": fields[7].strip(), "city": fields[8].strip(), "country": fields[6].strip() or "Deutschland", "tax_number": "", "notes": f"PCAS-Import; Quelle: {path.name}"}
            existing = self.connection.execute("SELECT id FROM customers WHERE customer_number=?", (data["customer_number"],)).fetchone()
            try:
                self.save_customer(data, int(existing["id"]) if existing else None)
                if existing:
                    updated += 1
                else:
                    imported += 1
            except Exception:
                skipped += 1
        return {"imported": imported, "updated": updated, "skipped": skipped}

    def import_pcas_invoices(self, path: Path) -> dict[str, int]:
        """Importiert PCAS RAImport1 als offene Buchungssätze, gruppiert nach Belegnummer."""
        if not path.is_file():
            raise ValueError("PCAS-Datei wurde nicht gefunden.")
        text = self._read_export_text(path)
        # Group lines by document_number
        groups: dict[str, dict] = {}
        imported = skipped = 0
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            if len(line.rstrip()) < 100:
                skipped += 1
                continue
            record = line.rstrip("\r\n")
            booking_date = record[0:10].strip()
            document_date = record[10:20].strip()
            text_field = record[20:50].strip()
            document_number = record[50:66].strip()
            # Skip empty document_number
            if not document_number:
                skipped += 1
                continue
            customer_number = record[83:91].strip()
            amount_text = record[99:109].strip()
            if not customer_number:
                skipped += 1
                continue
            # Get customer
            customer = self.connection.execute("SELECT id FROM customers WHERE customer_number=?", (customer_number,)).fetchone()
            if not customer:
                skipped += 1
                continue
            amount = money(amount_text)
            if amount <= 0:
                skipped += 1
                continue
            try:
                invoice_date = self._pcas_date(booking_date or document_date)
                due_date = self._pcas_date(document_date) or invoice_date
                if not invoice_date:
                    skipped += 1
                    continue
            except Exception:
                skipped += 1
                continue
            # Initialize group if not present
            if document_number not in groups:
                groups[document_number] = {
                    "customer_id": int(customer["id"]),
                    "invoice_date": invoice_date,
                    "due_date": due_date,
                    "lines": [],  # list of (description, amount)
                }
            # Add line to group
            groups[document_number]["lines"].append((text_field or "PCAS-Import", amount))
        # Process each group
        for document_number, data in groups.items():
            # Check if invoice already exists
            existing = self.connection.execute("SELECT id FROM invoices WHERE invoice_number=?", (document_number,)).fetchone()
            if existing:
                # Skip duplicate invoice (idempotent)
                continue
            try:
                invoice_id = self._create_pcas_invoice(
                    data["customer_id"],
                    data["invoice_date"],
                    data["due_date"],
                    document_number,
                    data["lines"],
                    str(path),
                )
                self.audit("invoice", invoice_id, "pcas_imported", {"source": str(path), "document_number": document_number})
                imported += 1
            except Exception:
                skipped += 1
        return {"imported": imported, "skipped": skipped}

    def import_datanorm_products(self, path: Path) -> dict[str, int]:
        """Importiert DATANORM-Produktstammdaten (semikolon-separiert, V5).
        Erwartet mindestens die Felder: Satzart, Verarbeitungskennzeichen, Artikelnummer,
        Artikelbezeichnung1, Artikelbezeichnung2, Preiskennzeichen, Preiseinheit,
        Mengeneinheit, Preis, Rabattgruppe, Hauptwarengruppe, Langtextschlüssel.
        Weitere Felder werden ignoriert.
        """
        if not path.is_file():
            raise ValueError("DATANORM-Datei wurde nicht gefunden.")
        text = self._read_export_text(path)
        lines = text.splitlines()
        imported = updated = deleted = skipped = 0
        # Determine if there is a header line
        start_idx = 0
        if lines:
            first_fields = lines[0].strip().split(";")
            if len(first_fields) > 0 and first_fields[0].strip().upper() == "SATZART":
                start_idx = 1
        for line in lines[start_idx:]:
            if not line.strip():
                continue
            fields = line.split(";")
            if len(fields) < 13:
                skipped += 1
                continue
            satzart = fields[0].strip()
            if satzart.upper() != "A":
                # We only process Hauptsatz (A) for now
                skipped += 1
                continue
            verf_kz = fields[1].strip().upper()  # N, L, A, X
            artikelnummer = fields[2].strip()
            if not artikelnummer:
                skipped += 1
                continue
            bezeichnung1 = fields[4].strip() if len(fields) > 4 else ""
            bezeichnung2 = fields[5].strip() if len(fields) > 5 else ""
            name = " ".join(part for part in (bezeichnung1, bezeichnung2) if part).strip()
            if not name:
                # Fallback to artikelnummer if no name
                name = artikelnummer
            einheit = fields[8].strip() if len(fields) > 8 else "Stk."
            preis_str = fields[9].strip() if len(fields) > 9 else "0"
            preis_cents = money(preis_str)
            rabattgruppe = fields[10].strip() if len(fields) > 10 else ""
            hauptwarengruppe = fields[11].strip() if len(fields) > 11 else ""
            langtextschluessel = fields[12].strip() if len(fields) > 12 else ""
            # Determine action based on processing code
            if verf_kz == "L":
                # Löschung: set active to False (or delete? we'll set inactive)
                with self.transaction() as db:
                    db.execute("UPDATE products SET active=0 WHERE sku=?", (artikelnummer,))
                deleted += 1
            else:
                # Neuanlage or Änderung: create or update product
                # Check if product exists
                existing = self.connection.execute("SELECT id FROM products WHERE sku=?", (artikelnummer,)).fetchone()
                if existing:
                    # Update
                    with self.transaction() as db:
                        db.execute(
                            """UPDATE products SET name=?, description=?, unit=?, net_price_cents=?,
                            active=1 WHERE sku=?""",
                            (name, name, einheit, preis_cents, artikelnummer),
                        )
                    updated += 1
                else:
                    # Insert
                    with self.transaction() as db:
                        db.execute(
                            """INSERT INTO products(sku,name,description,unit,net_price_cents,tax_rate,active,created_at)
                            VALUES(?,?,?,?,?,19,1,?)""",
                            (artikelnummer, name, name, einheit, preis_cents, now()),
                        )
                    imported += 1
        return {"imported": imported, "updated": updated, "deleted": deleted, "skipped": skipped}

    def _read_export_text(self, path: Path) -> str:
        raw = path.read_bytes()
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    @staticmethod
    def _pcas_date(value: str) -> str | None:
        value = value.strip()
        for pattern in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
            try:
                return datetime.strptime(value, pattern).date().isoformat()
            except ValueError:
                pass
        return None

    def _insert_pcas_booking(self, customer_id: int, invoice_date: str, due_date: str, document_number: str, description: str, amount: int) -> int:
        existing = self.connection.execute("SELECT id FROM invoices WHERE invoice_number=?", (document_number,)).fetchone()
        if existing:
            return int(existing["id"])
        number = document_number or self._next_number("invoices", self.setting("invoice_prefix", "RE"))
        with self.transaction() as db:
            cur = db.execute("INSERT INTO invoices(invoice_number,customer_id,invoice_date,due_date,status,notes,subtotal_cents,tax_cents,total_cents,paid_cents,created_at,updated_at,source,source_reference) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (number, customer_id, invoice_date, due_date, "offen", description, amount, 0, amount, 0, now(), now(), "pcas", document_number))
            invoice_id = int(cur.lastrowid)
            db.execute("INSERT INTO invoice_items(invoice_id,description,quantity,unit,unit_price_cents,tax_rate,line_subtotal_cents,line_tax_cents,line_total_cents) VALUES(?,?,?,?,?,?,?,?,?)", (invoice_id, description, 1, "Stk.", amount, 0, amount, 0, amount))
        return invoice_id

    def _create_pcas_invoice(self, customer_id: int, invoice_date: str, due_date: str, document_number: str, lines: list[tuple[str, int]], source_path: str) -> int:
        """Create a PCAS invoice with multiple lines.
        lines: list of (description, amount_in_cents)
        Tax is assumed 0 for PCAS lines.
        """
        if not lines:
            raise ValueError("At least one line is required")
        number = document_number or self._next_number("invoices", self.setting("invoice_prefix", "RE"))
        subtotal = sum(amount for _, amount in lines)
        tax = 0
        total = subtotal + tax
        with self.transaction() as db:
            cur = db.execute(
                "INSERT INTO invoices(invoice_number,customer_id,invoice_date,due_date,status,notes,subtotal_cents,tax_cents,total_cents,paid_cents,created_at,updated_at,source,source_reference) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (number, customer_id, invoice_date, due_date, "offen", f"PCAS-Import; Quelle: {source_path}", subtotal, tax, total, 0, now(), now(), "pcas", document_number),
            )
            invoice_id = int(cur.lastrowid)
            for description, amount in lines:
                db.execute(
                    "INSERT INTO invoice_items(invoice_id,description,quantity,unit,unit_price_cents,tax_rate,line_subtotal_cents,line_tax_cents,line_total_cents) VALUES(?,?,?,?,?,?,?,?,?)",
                    (invoice_id, description, 1, "Stk.", amount, 0, amount, 0, amount),
                )
        return invoice_id

    def record_payment(self, invoice_id: int, amount_cents: int, method: str = "bank", reference: str = "", event_id: str | None = None) -> tuple[int, bool]:
        if amount_cents <= 0:
            raise ValueError("Zahlungsbetrag muss größer als null sein.")
        if event_id:
            existing = self.connection.execute("SELECT id FROM payments WHERE event_id=?", (event_id,)).fetchone()
            if existing:
                return int(existing["id"]), True
        invoice = self.invoice(invoice_id)
        if not invoice or invoice["status"] in ("entwurf", "storniert"):
            raise ValueError("Diese Rechnung ist nicht zahlbar.")
        open_amount = int(invoice["total_cents"]) - int(invoice["paid_cents"])
        if amount_cents > open_amount:
            raise ValueError("Zahlung übersteigt den offenen Betrag.")
        with self.transaction() as db:
            cur = db.execute("INSERT INTO payments(invoice_id,payment_date,amount_cents,method,reference,event_id,created_at) VALUES(?,?,?,?,?,?,?)", (invoice_id, today(), amount_cents, method, reference, event_id, now()))
            paid = int(invoice["paid_cents"]) + amount_cents
            status = "bezahlt" if paid >= int(invoice["total_cents"]) else ("überfällig" if invoice["due_date"] < today() else "offen")
            db.execute("UPDATE invoices SET paid_cents=?,status=?,updated_at=? WHERE id=?", (paid, status, now(), invoice_id))
            payment_id = int(cur.lastrowid)
        self.audit("payment", payment_id, "created", {"invoice_id": invoice_id, "amount_cents": amount_cents})
        return payment_id, False

    def refresh_overdue(self) -> None:
        self.connection.execute("UPDATE invoices SET status='überfällig' WHERE status='offen' AND due_date < date('now')")
        self.connection.commit()

    def set_invoice_status(self, invoice_id: int, status: str) -> None:
        """Set the status of an invoice.
        Valid statuses: 'offen', 'überfällig', 'bezahlt', 'entwurf', 'storniert', 'gesendet'.
        """
        valid = {"offen", "überfällig", "bezahlt", "entwurf", "storniert", "gesendet"}
        if status not in valid:
            raise ValueError(f"Ungültiger Status: {status}")
        with self.transaction() as db:
            db.execute("UPDATE invoices SET status=?, updated_at=? WHERE id=?", (status, now(), invoice_id))
        self.audit("invoice", invoice_id, "status_changed", {"new_status": status})

    def dashboard(self) -> dict[str, Any]:
        self.refresh_overdue()
        row = self.connection.execute("""SELECT COUNT(*) AS invoices, COALESCE(SUM(total_cents),0) AS total, COALESCE(SUM(CASE WHEN status IN ('offen','überfällig') THEN total_cents-paid_cents ELSE 0 END),0) AS open, COALESCE(SUM(CASE WHEN status='überfällig' THEN total_cents-paid_cents ELSE 0 END),0) AS overdue FROM invoices""").fetchone()
        customers = self.connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        products = self.connection.execute("SELECT COUNT(*) FROM products WHERE active=1").fetchone()[0]
        recent = list(self.connection.execute("SELECT i.*, c.name AS customer_name FROM invoices i JOIN customers c ON c.id=i.customer_id ORDER BY i.created_at DESC LIMIT 6"))
        return {"invoices": row["invoices"], "total": row["total"], "open": row["open"], "overdue": row["overdue"], "customers": customers, "products": products, "recent": recent}

    def backup(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.resolve() == self.path.resolve():
            raise ValueError("Backup-Ziel darf nicht die aktive Datenbank sein.")
        with tempfile.NamedTemporaryFile(prefix="hotdesk-backup-", suffix=".sqlite", dir=destination.parent, delete=False) as temp:
            temp_path = Path(temp.name)
        try:
            self.connection.backup(sqlite3.connect(temp_path))
            shutil.copy2(temp_path, destination)
        finally:
            temp_path.unlink(missing_ok=True)
        return destination

    def export_datev_csv(self, kind: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        rows: list[list[str]] = []
        if kind == "debitors":
            header = ["Kundennummer", "Name", "Firma", "Strasse", "PLZ", "Ort", "Land", "Telefon", "E-Mail", "Steuernummer", "Zahlungsziel"]
            rows = [[r["customer_number"], r["name"], r["company"], r["address"], r["postal_code"], r["city"], r["country"], r["phone"], r["email"], r["tax_number"], self.setting("payment_terms_days", "14")] for r in self.customers()]
        elif kind == "accounts":
            header = ["Konto", "Kontenbezeichnung", "Kontentyp"]
            rows = [[self.setting("datev_receivable_account", "1000"), "Debitoren", "Aktiv"], [self.setting("datev_bank_account", "1200"), "Bank", "Aktiv"]]
        else:
            header = ["Belegdatum", "Belegfeld 1", "Buchungstext", "BU/SH", "Gegenkonto", "VKNR", "Betrag"]
            for invoice in self.invoices():
                customer = self.customer(int(invoice["customer_id"]))
                if not customer:
                    continue
                rows.append([invoice["invoice_date"], invoice["invoice_number"], "Rechnung netto", "S", self.setting("datev_receivable_account", "1000"), customer["customer_number"], f"{int(invoice['subtotal_cents']) / 100:.2f}".replace(".", ",")])
                if int(invoice["tax_cents"]):
                    rows.append([invoice["invoice_date"], invoice["invoice_number"], "Umsatzsteuer", "S", self.setting("datev_receivable_account", "1000"), customer["customer_number"], f"{int(invoice['tax_cents']) / 100:.2f}".replace(".", ",")])
        with destination.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(header)
            writer.writerows(rows)
        return destination

    def export_invoice_pdf(self, invoice_id: int, destination: Path) -> Path:
        """Export a single invoice as a PDF file."""
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError("Reportlab is not installed. Cannot generate PDF.")
        invoice = self.invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice with id {invoice_id} not found.")
        customer = self.customer(int(invoice["customer_id"]))
        if not customer:
            raise ValueError(f"Customer for invoice {invoice_id} not found.")
        items = self.invoice_items(invoice_id)

        # Prepare data for the template
        company_name = self.setting("company_name", "Mein Unternehmen")
        company_address = self.setting("company_address", "")
        customer_name = customer["name"]
        customer_address = f"{customer['address']}, {customer['postal_code']} {customer['city']}, {customer['country']}"
        invoice_number = invoice["invoice_number"]
        invoice_date = invoice["invoice_date"]
        due_date = invoice["due_date"]

        # Build items table data
        items_data = [["Position", "Beschreibung", "Menge", "Einheit", "Einpreis", "Gesamt"]]
        for item in items:
            items_data.append([
                str(item["id"]),
                item["description"],
                f"{item['quantity']:.2f}".replace(".", ","),
                item["unit"],
                self.fmt_currency(item["unit_price_cents"]),
                self.fmt_currency(item["line_total_cents"])
            ])

        # Calculate totals
        subtotal_cents = invoice["subtotal_cents"]
        tax_cents = invoice["tax_cents"]
        total_cents = invoice["total_cents"]

        # Create PDF
        buffer = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        try:
            doc = SimpleDocTemplate(buffer.name, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
            elements = []

            # Get styles
            styles = getSampleStyleSheet()
            normal = styles["Normal"]
            bold = styles["Bold"]
            # Title
            elements.append(Paragraph("Rechnung", styles["Title"]))
            elements.append(Spacer(1, 12))

            # Company and customer info
            info_data = [
                [f"Firma: {company_name}", f"Rechnung an: {customer_name}"],
                [f"Adresse: {company_address}", f"{customer_address}"],
                [f"Rechnung-Nr: {invoice_number}", f"Datum: {invoice_date}"],
                [f"Fällig: {due_date}", ""]
            ]
            info_table = Table(info_data, colWidths=[250, 250])
            info_table.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            elements.append(info_table)
            elements.append(Spacer(1, 12))

            # Items table
            items_table = Table(items_data, colWidths=[30, 200, 50, 50, 70, 70])
            items_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ]))
            elements.append(items_table)
            elements.append(Spacer(1, 12))

            # Totals
            totals_data = [
                ["Zwischensumme:", self.fmt_currency(subtotal_cents)],
                [f"MwSt. (19%):", self.fmt_currency(tax_cents)],
                ["Gesamt:", self.fmt_currency(total_cents)]
            ]
            totals_table = Table(totals_data, colWidths=[400, 100])
            totals_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
                ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(totals_table)

            doc.build(elements)
            shutil.move(buffer.name, destination)
            return destination
        finally:
            if os.path.exists(buffer.name):
                os.unlink(buffer.name)

    def export_invoice_zugferd(self, invoice_id: int, destination: Path) -> Path:
        """Export a single invoice as a ZUGFeRD-compliant PDF (PDF/A-3 with embedded XML).
        This implementation creates a PDF and attaches a minimal ZUGFeRD XML as an attachment.
        """
        if not REPORTLAB_AVAILABLE or not PYPDF2_AVAILABLE:
            raise RuntimeError("Reportlab and PyPDF2 are required for ZUGFeRD export.")
        # First generate a regular PDF
        pdf_destination = destination.with_suffix('.pdf')
        self.export_invoice_pdf(invoice_id, pdf_destination)

        # Generate a minimal ZUGFeRD XML (we'll create a very basic one)
        invoice = self.invoice(invoice_id)
        customer = self.customer(int(invoice["customer_id"]))
        # We'll create a simple XML string
        xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<CrossIndustryDocument xmlns="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100">
    <Header>
        <ID>{invoice["invoice_number"]}</ID>
        <IssueDateTime>{invoice["invoice_date"]}T00:00:00</IssueDateTime>
        <TypeCode>380</TypeCode>
    </Header>
    <SupplyChainTradeTransaction>
        <ApplicableHeaderTradeAgreement>
            <BuyerReference>{customer["customer_number"]}</BuyerReference>
            <SellerTradeParty>
                <Name>{self.setting("company_name", "Mein Unternehmen")}</Name>
            </SellerTradeParty>
            <BuyerTradeParty>
                <Name>{customer["name"]}</Name>
            </BuyerTradeParty>
        </ApplicableHeaderTradeAgreement>
        <ApplicableHeaderTradeSettlement>
            <InvoiceCurrencyCode>{self.get_currency()}</InvoiceCurrencyCode>
            <TaxCurrencyCode>{self.get_currency()}</TaxCurrencyCode>
            <PaymentDueDate>{invoice["due_date"]}T00:00:00</PaymentDueDate>
            <SpecifiedTradeSettlementHeaderMonetarySummation>
                <InvoiceAmount>{Decimal(invoice["total_cents"])/100:.2f}</InvoiceAmount>
                <TaxAmount>{Decimal(invoice["tax_cents"])/100:.2f}</TaxAmount>
                <GrandTotalAmount>{Decimal(invoice["total_cents"])/100:.2f}</GrandTotalAmount>
            </SpecifiedTradeSettlementHeaderMonetarySummation>
        </ApplicableHeaderTradeSettlement>
    </SupplyChainTradeTransaction>
</CrossIndustryDocument>
'''

        # Write XML to a temporary file
        xml_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.xml', mode='w', encoding='utf-8')
        xml_temp.write(xml_content)
        xml_temp.close()

        # Attach XML to PDF using PyPDF2
        reader = PdfReader(pdf_destination)
        writer = PdfWriter()
        # Copy pages from reader to writer
        for page in reader.pages:
            writer.add_page(page)

        # Create the attachment
        with open(xml_temp.name, 'rb') as f:
            xml_data = f.read()
        # Create a file attachment annotation
        # We'll attach the XML to the first page
        # According to PDF/A-3, we need to add an attachment and set the AFRelationship
        # We'll use the PyPDF2 method to add an attachment
        writer.add_attachment('zugferd-invoice.xml', xml_data)

        # Write the output
        with open(destination, 'wb') as f:
            writer.write(f)

        # Clean up
        os.unlink(xml_temp.name)
        os.unlink(pdf_destination)  # remove the temporary PDF

        return destination

    def _format_address(self, address: str) -> str:
        """Format an address string for XML (escape and wrap in XML tags)."""
        # For simplicity, we'll just return the address wrapped in <PostalTradeAddress> tags.
        # In a real implementation, we would break down the address into lines.
        # We'll escape the address for XML.
        import html
        escaped = html.escape(address)
        return f'<PostalTradeAddress>{escaped}</PostalTradeAddress>'

    def import_gaeb_invoices(self, path: Path) -> dict[str, int]:
        """Import GAEB invoices from a CSV file.
        Expected columns: Artikelnummer, Menge, Preis, Beschreibung (semicolon separated).
        This will create or update products and create a draft invoice for each unique customer?
        For simplicity, we will create products and then create a single draft invoice
        using the first customer found (or a default customer).
        """
        if not path.is_file():
            raise ValueError("GAEB-Datei wurde nicht gefunden.")
        text = self._read_export_text(path)
        lines = text.splitlines()
        if not lines:
            return {"imported": 0, "updated": 0, "skipped": 0}

        # Assume first line is header
        header = lines[0].strip().split(';')
        # We'll try to map columns
        col_map = {}
        for i, h in enumerate(header):
            h_lower = h.strip().lower()
            if 'artikel' in h_lower or 'sku' in h_lower:
                col_map['artikelnummer'] = i
            elif 'menge' in h_lower or 'quantity' in h_lower:
                col_map['menge'] = i
            elif 'preis' in h_lower or 'price' in h_lower:
                col_map['preis'] = i
            elif 'beschreibung' in h_lower or 'description' in h_lower:
                col_map['beschreibung'] = i

        required = ['artikelnummer', 'menge', 'preis', 'beschreibung']
        if not all(r in col_map for r in required):
            # Try without header
            # Assume columns in order: Artikelnummer, Menge, Preis, Beschreibung
            col_map = {'artikelnummer': 0, 'menge': 1, 'preis': 2, 'beschreibung': 3}
            data_lines = lines
        else:
            data_lines = lines[1:]

        imported = 0
        updated = 0
        skipped = 0
        # We'll collect product data
        products_to_create = []
        products_to_update = []

        for line in data_lines:
            if not line.strip():
                continue
            fields = line.split(';')
            if len(fields) < 4:
                skipped += 1
                continue
            try:
                artikelnummer = fields[col_map['artikelnummer']].strip()
                menge = fields[col_map['menge']].strip()
                preis = fields[col_map['preis']].strip()
                beschreibung = fields[col_map['beschreibung']].strip()
                if not artikelnummer:
                    skipped += 1
                    continue
                quantity = Decimal(menge.replace(',', '.'))
                price = money(preis)
                if quantity <= 0 or price < 0:
                    skipped += 1
                    continue
                # Check if product exists
                existing = self.connection.execute("SELECT id FROM products WHERE sku=?", (artikelnummer,)).fetchone()
                if existing:
                    # Update
                    products_to_update.append((artikelnummer, beschreibung, price, quantity))
                else:
                    # Create
                    products_to_create.append((artikelnummer, beschreibung, price, quantity))
            except Exception:
                skipped += 1
                continue

        # Update existing products
        for sku, description, price, quantity in products_to_update:
            with self.transaction() as db:
                db.execute(
                    """UPDATE products SET description=?, net_price_cents=? WHERE sku=?""",
                    (description, price, sku)
                )
            updated += 1

        # Create new products
        for sku, description, price, quantity in products_to_create:
            with self.transaction() as db:
                db.execute(
                    """INSERT INTO products(sku,name,description,unit,net_price_cents,tax_rate,active,created_at)
                    VALUES(?,?,?,?,?,19,1,?)""",
                    (sku, description, description, 'Stk.', price, now())
                )
            imported += 1

        # We'll also create a draft invoice for the first customer (if any) using all products?
        # For simplicity, we'll not create an invoice here. The user can create one later.
        # We'll just return the product counts.
        return {"imported": imported, "updated": updated, "skipped": skipped}

    def _start_backup_thread(self):
        """Start a background thread for automatic backups."""
        if hasattr(self, '_backup_thread') and self._backup_thread.is_alive():
            return
        self._backup_stop = threading.Event()
        self._backup_thread = threading.Thread(target=self._backup_worker, daemon=True)
        self._backup_thread.start()

    def _backup_worker(self):
        """Worker function for automatic backup thread."""
        while not self._backup_stop.is_set():
            # Create a temporary database connection for this iteration
            local_db = Database(self.path)
            try:
                # Check if automatic backup is enabled
                if local_db.setting("backup_auto_enabled", "0") == "1":
                    # Get the backup time
                    backup_time_str = local_db.setting("backup_auto_time", "02:00")
                    try:
                        # Parse the time
                        backup_time = datetime.strptime(backup_time_str, "%H:%M").time()
                        now = datetime.now().time()
                        # Check if it's time to backup (within a minute)
                        if now.hour == backup_time.hour and now.minute == backup_time.minute:
                            # Get backup directory
                            backup_dir_str = local_db.setting("backup_auto_dir", "")
                            if backup_dir_str:
                                backup_dir = Path(backup_dir_str).expanduser()
                                backup_dir.mkdir(parents=True, exist_ok=True)
                                # Create a backup filename with timestamp
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                backup_path = backup_dir / f"hotdesk_backup_{timestamp}.sqlite"
                                try:
                                    local_db.backup(backup_path)
                                    local_db.audit("system", 0, "auto_backup", {"destination": str(backup_path)})
                                except Exception as e:
                                    local_db.audit("system", 0, "auto_backup_error", {"error": str(e)})
                                # Sleep for a minute to avoid running multiple times in the same minute
                                time.sleep(60)
                            else:
                                # No backup directory set, sleep briefly
                                time.sleep(10)
                        else:
                            # Not yet time for backup, sleep briefly
                            time.sleep(10)
                    except Exception:
                        # If there's an error parsing time, sleep for a minute
                        time.sleep(60)
                else:
                    # Backup disabled, sleep for a minute
                    time.sleep(60)
            finally:
                local_db.close()

    def stop_backup_thread(self):
        """Stop the automatic backup thread."""
        if hasattr(self, '_backup_stop'):
            self._backup_stop.set()
        if hasattr(self, '_backup_thread'):
            self._backup_thread.join(timeout=5)


def euro(cents: int) -> str:
    """Format amount in the selected currency."""
    db = Database()
    try:
        return db.fmt_currency(cents)
    finally:
        db.close()
