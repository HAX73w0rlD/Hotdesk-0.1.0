"""Hotdesk – lokale Desktop-Buchhaltung mit eigener GUI."""
from __future__ import annotations

import os
import sys
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk, Menu

from .desktop_storage import APP_NAME, Database, euro, money, today, DEFAULT_INVOICE_TEMPLATE


BG = "#f4f7f5"
SIDEBAR = "#14251e"
SIDEBAR_MUTED = "#a5b9ad"
TEXT = "#17221b"
MUTED = "#68746b"
LINE = "#dbe5dd"
CARD = "#ffffff"
GREEN = "#216044"
LIME = "#b8ef6b"
DANGER = "#b33f3f"
AMBER = "#ad6b00"


class HotdeskApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} · Rechnungen, Kunden, Übersicht")
        self.geometry("1440x900")
        self.minsize(1120, 700)
        self.configure(bg=BG)
        self.db = Database()
        # Trial logic: 14-day limit
        install_date_str = self.db.setting("install_date", "")
        if not install_date_str:
            # First run: set install date to today
            self.db.save_settings({"install_date": date.today().isoformat()})
            install_date = date.today()
        else:
            try:
                install_date = date.fromisoformat(install_date_str)
            except ValueError:
                # Corrupt date, reset
                install_date = date.today()
                self.db.save_settings({"install_date": install_date.isoformat()})
        if (date.today() - install_date).days > 14:
            # Trial expired: show message and self-delete
            from tkinter import messagebox
            messagebox.showerror(
                "Testversion abgelaufen",
                "Die 14‑tägige Testversion von Hotdesk ist abgelaufen.\n"
                "Die Anwendung wird nun geschlossen und gelöscht."
            )
            try:
                import os
                os.unlink(sys.argv[0])
            except Exception:
                pass
            self.destroy()
            return
        self.current = "dashboard"
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Bereit")
        self._configure_styles()
        self._build_shell()
        self.show_dashboard()
        self.bind("<Control-n>", lambda _event: self.open_customer_dialog())
        self.bind("<Control-i>", lambda _event: self.open_invoice_dialog())
        self.bind("<F1>", lambda _event: self.show_help())
        self.bind("<F5>", lambda _event: self.refresh_current())
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("DejaVu Sans", 10))
        style.configure("Card.TLabel", background=CARD, foreground=TEXT, font=("DejaVu Sans", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("DejaVu Sans", 9))
        style.configure("MutedCard.TLabel", background=CARD, foreground=MUTED, font=("DejaVu Sans", 9))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("DejaVu Sans", 26, "bold"))
        style.configure("Section.TLabel", background=BG, foreground=TEXT, font=("DejaVu Sans", 15, "bold"))
        style.configure("CardTitle.TLabel", background=CARD, foreground=MUTED, font=("DejaVu Sans", 9))
        style.configure("CardValue.TLabel", background=CARD, foreground=TEXT, font=("DejaVu Sans", 19, "bold"))
        style.configure("TButton", padding=(12, 8), font=("DejaVu Sans", 9, "bold"))
        style.configure("Primary.TButton", background=GREEN, foreground="white", borderwidth=0, padding=(14, 9))
        style.map("Primary.TButton", background=[("active", "#174b35")])
        style.configure("Danger.TButton", background="#fff0ee", foreground=DANGER)
        style.configure("Line.TFrame", background=LINE)
        style.configure("Accent.TFrame", background=LIME)
        style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT, rowheight=34, font=("DejaVu Sans", 9), borderwidth=0)
        style.configure("Treeview.Heading", background="#edf3ee", foreground=MUTED, font=("DejaVu Sans", 8, "bold"), relief="flat", padding=(7, 8))
        style.map("Treeview", background=[("selected", "#dcefe0")], foreground=[("selected", TEXT)])
        style.configure("TEntry", padding=8, fieldbackground="white")
        style.configure("TCombobox", padding=7, fieldbackground="white")
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(13, 8), font=("DejaVu Sans", 9, "bold"))
        style.configure("Vertical.TScrollbar", background="#d4dfd6", troughcolor=BG, borderwidth=0)

    def _build_shell(self) -> None:
        self.sidebar = tk.Frame(self, bg=SIDEBAR, width=235)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        logo = tk.Frame(self.sidebar, bg=SIDEBAR)
        logo.pack(fill="x", padx=24, pady=(28, 42))
        tk.Label(logo, text="K", bg=LIME, fg=SIDEBAR, font=("DejaVu Sans", 18, "bold"), width=3, height=1).pack(side="left", ipady=5)
        tk.Label(logo, text=APP_NAME, bg=SIDEBAR, fg="white", font=("DejaVu Sans", 19, "bold")).pack(side="left", padx=(10, 0))
        self.nav_buttons: dict[str, tk.Button] = {}
        for key, label, icon in [("dashboard", "Übersicht", "◈"), ("customers", "Kunden", "◎"), ("invoices", "Rechnungen", "▤"), ("products", "Produkte", "◇"), ("reports", "Berichte", "▥"), ("settings", "Einstellungen", "⚙")]:
            button = tk.Button(self.sidebar, text=f"  {icon}   {label}", anchor="w", relief="flat", bd=0, padx=22, pady=12, bg=SIDEBAR, fg="white", activebackground="#264b3a", activeforeground="white", font=("DejaVu Sans", 10, "bold"), command=lambda value=key: self.navigate(value), cursor="hand2")
            button.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[key] = button
        footer = tk.Frame(self.sidebar, bg=SIDEBAR)
        footer.pack(side="bottom", fill="x", padx=22, pady=22)
        tk.Label(footer, text="Lokal · SQLite · keine Cloud-Pflicht", bg=SIDEBAR, fg=SIDEBAR_MUTED, font=("DejaVu Sans", 8), wraplength=185, justify="left").pack()
        tk.Label(footer, text="F1  Hilfe     F5  Aktualisieren", bg=SIDEBAR, fg="#6e8a7a", font=("DejaVu Sans", 8)).pack(pady=(14, 0))
        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)
        self.topbar = tk.Frame(self.content, bg=BG, height=68)
        self.topbar.pack(fill="x", padx=32, pady=(20, 0))
        self.topbar.pack_propagate(False)
        self.title_label = tk.Label(self.topbar, text="Übersicht", bg=BG, fg=TEXT, anchor="w", font=("DejaVu Sans", 18, "bold"))
        self.title_label.pack(side="left")
        search = ttk.Entry(self.topbar, textvariable=self.search_var, width=28)
        search.pack(side="right", padx=(10, 0), ipady=3)
        search.bind("<Return>", lambda _event: self.refresh_current())
        tk.Label(self.topbar, text="⌕", bg=BG, fg=MUTED, font=("DejaVu Sans", 18)).pack(side="right", padx=(0, 6))
        ttk.Button(self.topbar, text="+ Rechnung", style="Primary.TButton", command=self.open_invoice_dialog).pack(side="right")
        self.body = tk.Frame(self.content, bg=BG)
        self.body.pack(fill="both", expand=True, padx=32, pady=(12, 28))
        self.status = tk.Label(self.content, textvariable=self.status_var, bg=BG, fg=MUTED, anchor="w", font=("DejaVu Sans", 8), padx=32, pady=0)
        self.status.pack(fill="x")

    def navigate(self, page: str) -> None:
        self.current = page
        for key, button in self.nav_buttons.items():
            button.configure(bg="#264b3a" if key == page else SIDEBAR)
        getattr(self, f"show_{page}")()

    def clear_body(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def set_title(self, title: str, subtitle: str = "") -> None:
        self.title_label.configure(text=title)
        if subtitle:
            self.title_label.configure(text=f"{title}  ·  {subtitle}")

    def status_message(self, message: str) -> None:
        self.status_var.set(message)
        self.after(4000, lambda: self.status_var.set("Bereit"))

    def refresh_current(self) -> None:
        self.navigate(self.current)

    def _page_header(self, title: str, subtitle: str, action: str | None = None, command=None) -> None:
        header = tk.Frame(self.body, bg=BG)
        header.pack(fill="x", pady=(4, 20))
        left = tk.Frame(header, bg=BG)
        left.pack(side="left")
        ttk.Label(left, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text=subtitle, style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        if action:
            ttk.Button(header, text=action, style="Primary.TButton", command=command).pack(side="right", anchor="n")

    def _empty(self, parent: tk.Widget, title: str, subtitle: str, action: str | None = None, command=None) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=28)
        card.pack(fill="both", expand=True, pady=20)
        ttk.Label(card, text=title, style="Section.TLabel").pack(anchor="w")
        ttk.Label(card, text=subtitle, style="MutedCard.TLabel", wraplength=620, justify="left").pack(anchor="w", pady=(8, 16))
        if action:
            ttk.Button(card, text=action, style="Primary.TButton", command=command).pack(anchor="w")

    def show_dashboard(self) -> None:
        self.set_title("Guten Morgen", "Ihre Geschäftszahlen auf einen Blick")
        self.clear_body()
        data = self.db.dashboard()
        stats = [("Offener Betrag", euro(int(data["open"])), GREEN), ("Überfällig", euro(int(data["overdue"])), DANGER), ("Rechnungen", str(data["invoices"]), TEXT), ("Kunden", str(data["customers"]), TEXT)]
        cards = tk.Frame(self.body, bg=BG)
        cards.pack(fill="x")
        for index, (label, value, color) in enumerate(stats):
            card = tk.Frame(cards, bg=CARD, highlightbackground=LINE, highlightthickness=1, padx=20, pady=18)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 8, 0))
            cards.grid_columnconfigure(index, weight=1)
            tk.Label(card, text=label.upper(), bg=CARD, fg=MUTED, font=("DejaVu Sans", 8, "bold")).pack(anchor="w")
            tk.Label(card, text=value, bg=CARD, fg=color, font=("DejaVu Sans", 19, "bold")).pack(anchor="w", pady=(8, 0))
        lower = tk.Frame(self.body, bg=BG)
        lower.pack(fill="both", expand=True, pady=(18, 0))
        lower.grid_columnconfigure(0, weight=3)
        lower.grid_columnconfigure(1, weight=2)
        lower.grid_rowconfigure(0, weight=1)
        recent = tk.Frame(lower, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        recent.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        tk.Label(recent, text="Letzte Rechnungen", bg=CARD, fg=TEXT, font=("DejaVu Sans", 14, "bold")).pack(anchor="w", padx=20, pady=(18, 10))
        if data["recent"]:
            self._tree(recent, [("invoice_number", "Nummer", 150), ("customer_name", "Kunde", 240), ("invoice_date", "Datum", 100), ("status", "Status", 100), ("total_cents", "Gesamt", 130)], data["recent"], height=7)
        else:
            tk.Label(recent, text="Noch keine Rechnungen. Legen Sie Ihre erste Rechnung an.", bg=CARD, fg=MUTED, font=("DejaVu Sans", 9)).pack(anchor="w", padx=20, pady=25)
        quick = tk.Frame(lower, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        quick.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        tk.Label(quick, text="Schnellaktionen", bg=CARD, fg=TEXT, font=("DejaVu Sans", 14, "bold")).pack(anchor="w", padx=20, pady=(18, 10))
        for text, cmd in [("Neue Rechnung", self.open_invoice_dialog), ("Kunde anlegen", self.open_customer_dialog), ("Backup erstellen", self.create_backup)]:
            button = tk.Button(quick, text=text, command=cmd, anchor="w", relief="flat", bd=0, bg="#eef5ef", fg=GREEN, activebackground="#dfeee2", font=("DejaVu Sans", 10, "bold"), padx=16, pady=12, cursor="hand2")
            button.pack(fill="x", padx=20, pady=5)
        tk.Label(quick, text=f"Aktive Produkte: {data['products']}", bg=CARD, fg=MUTED, font=("DejaVu Sans", 8)).pack(anchor="w", padx=20, pady=(15, 18))

    def _tree(self, parent: tk.Widget, columns: list[tuple[str, str, int]], rows: Iterable, height: int = 12) -> ttk.Treeview:
        holder = ttk.Frame(parent, style="Card.TFrame")
        holder.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        tree = ttk.Treeview(holder, columns=[c[0] for c in columns], show="headings", height=height)
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="w")
        for row in rows:
            values = []
            for key, _, _ in columns:
                value = row[key]
                values.append(euro(int(value)) if key.endswith("_cents") else value)
            tree.insert("", "end", values=values, iid=str(row["id"]) if "id" in row.keys() else None)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    def show_customers(self) -> None:
        self.set_title("Kunden", "Kontakte, Debitoren und Stammdaten")
        self.clear_body()
        self._page_header("Kunden", "Alle Kunden an einem Ort", "+ Kunde anlegen", self.open_customer_dialog)
        card = tk.Frame(self.body, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        card.pack(fill="both", expand=True)
        self._tree(card, [("customer_number", "Nummer", 120), ("name", "Name", 190), ("company", "Firma", 220), ("email", "E-Mail", 250), ("phone", "Telefon", 150), ("city", "Ort", 150)], self.db.customers(self.search_var.get()))
        self.status_message(f"{len(self.db.customers(self.search_var.get()))} Kunden geladen")

    def show_products(self) -> None:
        self.set_title("Produkte", "Leistungen und Preise")
        self.clear_body()
        self._page_header("Produkte & Leistungen", "Wiederverwendbare Positionen für schnelle Rechnungen", "+ Produkt anlegen", self.open_product_dialog)
        card = tk.Frame(self.body, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        card.pack(fill="both", expand=True)
        self._tree(card, [("sku", "SKU", 120), ("name", "Name", 270), ("description", "Beschreibung", 330), ("unit", "Einheit", 100), ("net_price_cents", "Netto", 140), ("tax_rate", "Steuer", 100)], self.db.products(self.search_var.get()))

    def show_invoices(self) -> None:
        self.set_title("Rechnungen", "Offene Posten und Zahlungsstatus")
        self.clear_body()
        self.db.refresh_overdue()
        self._page_header("Rechnungen", "Erstellen, verfolgen und bezahlen", "+ Rechnung erstellen", self.open_invoice_dialog)
        card = tk.Frame(self.body, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        card.pack(fill="both", expand=True)
        rows = self.db.invoices(self.search_var.get())
        tree = self._tree(card, [("invoice_number", "Nummer", 140), ("customer_name", "Kunde", 220), ("invoice_date", "Datum", 110), ("due_date", "Fällig", 110), ("status", "Status", 110), ("total_cents", "Gesamt", 130), ("paid_cents", "Bezahlt", 130)], rows)
        self.status_message(f"{len(rows)} Rechnungen geladen · Suche: {self.search_var.get() or 'alle'}")
        # Context menu
        menu = Menu(tree, tearoff=0)
        menu.add_command(label="Rechnung bearbeiten", command=lambda: self._edit_selected_invoice(tree))
        menu.add_command(label="Rechnung duplizieren", command=lambda: self._duplicate_selected_invoice(tree))
        menu.add_command(label="Rechnung löschen", command=lambda: self._delete_selected_invoice(tree))
        menu.add_separator()
        menu.add_command(label="Status ändern", command=lambda: self._change_status_selected_invoice(tree))
        menu.add_separator()
        menu.add_command(label="Als Text exportieren", command=lambda: self._export_invoice_as_text(tree))
        tree.bind("<Button-3>", lambda event: self._show_context_menu(event, menu))

    def _get_selected_invoice_id(self, tree: ttk.Treeview) -> int | None:
        selected = tree.selection()
        if not selected:
            return None
        item = tree.item(selected[0])
        vals = item["values"]
        if not vals:
            return None
        invoice_number = vals[0]  # first column
        row = self.db.connection.execute("SELECT id FROM invoices WHERE invoice_number=?", (invoice_number,)).fetchone()
        return row["id"] if row else None

    def _delete_selected_invoice(self, tree: ttk.Treeview) -> None:
        invoice_id = self._get_selected_invoice_id(tree)
        if invoice_id is None:
            messagebox.showwarning("Keine Auswahl", "Bitte zuerst eine Rechnung auswählen.", parent=tree)
            return
        if not messagebox.askyesno("Rechnung löschen", "Möchten Sie die ausgewählte Rechnung wirklich löschen?", parent=tree):
            return
        try:
            self.db.connection.execute("DELETE FROM invoices WHERE id=?", (invoice_id,))
            self.db.connection.commit()
            self.refresh_current()
            self.status_message("Rechnung gelöscht.")
        except Exception as e:
            messagebox.showerror("Fehler beim Löschen", str(e), parent=tree)

    def _change_status_selected_invoice(self, tree: ttk.Treeview) -> None:
        invoice_id = self._get_selected_invoice_id(tree)
        if invoice_id is None:
            messagebox.showwarning("Keine Auswahl", "Bitte zuerst eine Rechnung auswählen.", parent=tree)
            return
        # Simple dialog with combobox
        dialog = tk.Toplevel(tree)
        dialog.title("Status ändern")
        dialog.transient(tree)
        dialog.grab_set()
        ttk.Label(dialog, text="Neuen Status wählen:").pack(padx=10, pady=10)
        status_var = tk.StringVar(value=self.db.invoice(invoice_id)["status"] if self.db.invoice(invoice_id) else "offen")
        combo = ttk.Combobox(dialog, textvariable=status_var, values=["offen", "überfällig", "bezahlt", "entwurf", "storniert", "gesendet"], state="readonly")
        combo.pack(padx=10, pady=5)
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Abbrechen", command=dialog.destroy).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="OK", command=lambda: self._apply_status_change(dialog, status_var.get(), invoice_id, tree)).pack(side="right", padx=5)

    def _apply_status_change(self, dialog: tk.Toplevel, status: str, invoice_id: int, tree: ttk.Treeview) -> None:
        try:
            self.db.set_invoice_status(invoice_id, status)
            dialog.destroy()
            self.refresh_current()
            self.status_message(f"Status auf {status} geändert.")
        except Exception as e:
            messagebox.showerror("Fehler", str(e), parent=dialog)

    def _export_invoice_as_text(self, tree: ttk.Treeview) -> None:
        invoice_id = self._get_selected_invoice_id(tree)
        if invoice_id is None:
            messagebox.showwarning("Keine Auswahl", "Bitte zuerst eine Rechnung auswählen.", parent=tree)
            return
        invoice = self.db.invoice(invoice_id)
        if not invoice:
            messagebox.showerror("Fehler", "Rechnung nicht gefunden.", parent=tree)
            return
        items = self.db.invoice_items(invoice_id)
        # Build items table string
        lines = []
        for it in items:
            lines.append(f"{it['description']} | {it['quantity']} {it['unit']} | {self.db.fmt_currency(it['unit_price_cents'])} | {self.db.fmt_currency(it['line_total_cents'])}")
        items_table = "\n".join(lines) if lines else "-"
        # Get template
        template = self.db.get_invoice_template()
        # Prepare replacements
        replacements = {
            "company_name": self.db.setting("company_name", ""),
            "company_address": self.db.setting("company_address", ""),
            "customer_name": invoice["customer_name"],
            "customer_address": (f"{invoice['address']} {invoice['postal_code']} {invoice['city']} {invoice['country']}").strip(),
            "invoice_number": invoice["invoice_number"],
            "invoice_date": invoice["invoice_date"],
            "due_date": invoice["due_date"],
            "items_table": items_table,
            "subtotal_formatted": self.db.fmt_currency(invoice["subtotal_cents"]),
            "tax_rate": str(invoice["tax_cents"] * 100 / invoice["subtotal_cents"]) if invoice["subtotal_cents"] else "0",
            "tax_formatted": self.db.fmt_currency(invoice["tax_cents"]),
            "total_formatted": self.db.fmt_currency(invoice["total_cents"]),
        }
        try:
            text = template.format(**replacements)
        except KeyError as e:
            messagebox.showerror("Vorlagenfehler", f"Platzhalter {e} nicht in Vorlage gefunden.", parent=tree)
            return
        messagebox.showinfo("Rechnungsvorschau", text, parent=tree)

    def show_reports(self) -> None:
        self.set_title("Berichte", "Verständliche Zahlen für Ihre Entscheidungen")
        self.clear_body()
        self._page_header("Berichte", "Eine kompakte operative Sicht auf Ihr Geschäft")
        data = self.db.dashboard()
        card = tk.Frame(self.body, bg=CARD, highlightbackground=LINE, highlightthickness=1, padx=24, pady=22)
        card.pack(fill="both", expand=True)
        rows = [("Rechnungen gesamt", str(data["invoices"])), ("Gesamtwert aller Rechnungen", euro(int(data["total"]))), ("Offener Betrag", euro(int(data["open"]))), ("Überfällig", euro(int(data["overdue"]))), ("Kunden", str(data["customers"])), ("Aktive Produkte", str(data["products"]))]
        for label, value in rows:
            line = tk.Frame(card, bg=CARD)
            line.pack(fill="x", pady=9)
            tk.Label(line, text=label, bg=CARD, fg=MUTED, font=("DejaVu Sans", 10)).pack(side="left")
            tk.Label(line, text=value, bg=CARD, fg=TEXT, font=("DejaVu Sans", 11, "bold")).pack(side="right")
            tk.Frame(card, bg=LINE, height=1).pack(fill="x")

    def show_settings(self) -> None:
        self.set_title("Einstellungen", "Unternehmen, Zahlen und Sicherungen")
        self.clear_body()
        self._page_header("Einstellungen", "Alles bleibt lokal auf diesem Rechner")
        card = tk.Frame(self.body, bg=CARD, highlightbackground=LINE, highlightthickness=1, padx=25, pady=22)
        card.pack(fill="both", expand=True)
        values = self.db.settings()
        fields = [("company_name", "Firmenname"), ("company_address", "Adresse"), ("company_email", "E-Mail"), ("company_phone", "Telefon"), ("invoice_prefix", "Rechnungspräfix"), ("payment_terms_days", "Zahlungsziel in Tagen"), ("datev_client", "DATEV-Mandant"), ("datev_consultant", "DATEV-Berater"), ("datev_firm", "DATEV-Kanzlei"), ("datev_receivable_account", "DATEV Forderungs Konto"), ("datev_bank_account", "DATEV Bankkonto"), ("invoice_template", "Rechnungsvorlage")]
        self.setting_vars: dict[str, tk.StringVar] = {}
        for key, label in fields:
            if key == "invoice_template":
                # Text widget for multi-line editing
                tk.Label(card, text=label, bg=CARD, fg=MUTED, width=24, anchor="w", font=("DejaVu Sans", 9)).pack(anchor="w", pady=(2,0))
                text = tk.Text(card, height=6, width=50, wrap="word")
                text.insert("1.0", values.get(key, DEFAULT_INVOICE_TEMPLATE))
                text.pack(fill="x", pady=2)
                self.setting_vars[key] = text
                continue
            variable = tk.StringVar(value=values.get(key, ""))
            self.setting_vars[key] = variable
            line = tk.Frame(card, bg=CARD)
            line.pack(fill="x", pady=5)
            tk.Label(line, text=label, bg=CARD, fg=MUTED, width=24, anchor="w", font=("DejaVu Sans", 9)).pack(side="left")
            ttk.Entry(line, textvariable=variable).pack(side="left", fill="x", expand=True)
        # DATEV aktiv Checkbox
        enabled_var = tk.StringVar(value=values.get("datev_enabled", "0"))
        self.setting_vars["datev_enabled"] = enabled_var
        chk_frame = tk.Frame(card, bg=CARD)
        chk_frame.pack(fill="x", pady=5)
        ttk.Checkbutton(chk_frame, text="DATEV aktiv", variable=enabled_var, onvalue="1", offvalue="0").pack(side="left")
        actions = tk.Frame(card, bg=CARD)
        actions.pack(fill="x", pady=(25, 0))
        ttk.Button(actions, text="Einstellungen speichern", style="Primary.TButton", command=self.save_settings).pack(side="left")
        ttk.Button(actions, text="Backup erstellen", command=self.create_backup).pack(side="left", padx=8)
        ttk.Button(actions, text="PCAS-Import", command=self.open_pcas_import).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="DATEV-Export", command=self.export_datev).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="DATANORM-Import", command=self.open_datanorm_import).pack(side="left", padx=(8, 0))

    def save_settings(self) -> None:
        settings = {}
        for key, widget in self.setting_vars.items():
            if isinstance(widget, tk.Text):
                value = widget.get("1.0", "end-1c").strip()
            else:
                value = widget.get().strip()
            settings[key] = value
        self.db.save_settings(settings)
        self.status_message("Einstellungen gespeichert.")

    def create_backup(self) -> None:
        destination = filedialog.asksaveasfilename(title="Backup speichern", defaultextension=".sqlite", initialfile=f"hotdesk-backup-{date.today().isoformat()}.sqlite", filetypes=[("SQLite-Backup", "*.sqlite")])
        if destination:
            self.db.backup(Path(destination))
            self.status_message(f"Backup gespeichert: {destination}")

    def open_pcas_import(self) -> None:
        dialog, frame = self._dialog_shell("PCAS-Dateien importieren", 650, 410)
        ttk.Label(frame, text="PCAS-Dateien importieren", style="Section.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Unterstützt werden die dokumentierten PCAS-Standard-Line-Exporte 'Kunden.txt' (Debitoren) und 'RAImport1' (Rechnungsausgänge).", style="MutedCard.TLabel", wraplength=570, justify="left").pack(anchor="w", pady=(5, 15))
        kind = tk.StringVar(value="Kunden.txt / Debitoren")
        ttk.Label(frame, text="Dateityp", style="Card.TLabel").pack(anchor="w")
        ttk.Combobox(frame, textvariable=kind, values=("Kunden.txt / Debitoren", "RAImport1 / Rechnungen"), state="readonly").pack(fill="x", pady=(5, 14))
        ttk.Label(frame, text="Hinweis: Vor dem ersten Import wird empfohlen, ein Hotdesk-Backup anzulegen. Bestehende Nummern werden nicht dupliziert.", style="MutedCard.TLabel", wraplength=570, justify="left").pack(anchor="w", pady=(0, 14))
        buttons = ttk.Frame(frame, style="Card.TFrame")
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="right", padx=(8, 0))
        def choose_and_import() -> None:
            selected_kind = kind.get()
            if selected_kind.startswith("Kunden"):
                path = filedialog.askopenfilename(title="PCAS Kunden.txt wählen", filetypes=[("PCAS/Text", "*.txt *.TXT *.csv *.CSV"), ("Alle Dateien", "*.*")])
                if not path: return
                result = self.db.import_pcas_customers(Path(path))
            else:
                path = filedialog.askopenfilename(title="PCAS RAImport1 wählen", filetypes=[("PCAS/Text", "RAImport1 *.txt *.TXT"), ("Alle Dateien", "*.*")])
                if not path: return
                result = self.db.import_pcas_invoices(Path(path))
            dialog.destroy()
            self.refresh_current()
            self.status_message(f"PCAS-Import: {result['imported']} neu, {result.get('updated', 0)} aktualisiert, {result.get('skipped', 0)} übersprungen.")
            messagebox.showinfo("PCAS-Import abgeschlossen", f"Neu importiert: {result['imported']}\nAktualisiert: {result.get('updated', 0)}\nÜbersprungen: {result.get('skipped', 0)}\n\nDie importierten Daten wurden in den Audit-Log geschrieben.")
        ttk.Button(buttons, text="Datei wählen und importieren", style="Primary.TButton", command=choose_and_import).pack(side="right")

    def export_datev(self) -> None:
        destination = filedialog.asksaveasfilename(title="DATEV-CSV exportieren", defaultextension=".csv", initialfile=f"hotdesk-datev-{date.today().isoformat()}.csv", filetypes=[("CSV", "*.csv")])
        if destination:
            self.db.export_datev_csv("buchungsstapel", Path(destination))
            self.status_message(f"DATEV-Datei gespeichert: {destination}")

    def open_datanorm_import(self) -> None:
        dialog, frame = self._dialog_shell("DATANORM-Import", 650, 410)
        ttk.Label(frame, text="DATANORM-Produktstammdaten importieren", style="Section.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Unterstützt werden DATANORM-Dateien im Semikolon-separierten Format (V5).", style="MutedCard.TLabel", wraplength=570, justify="left").pack(anchor="w", pady=(5, 15))
        ttk.Label(frame, text="Hinweis: Vor dem Import wird empfohlen, ein Hotdesk-Backup anzulegen.", style="MutedCard.TLabel", wraplength=570, justify="left").pack(anchor="w", pady=(0, 14))
        buttons = ttk.Frame(frame, style="Card.TFrame")
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="right", padx=(8, 0))
        def choose_and_import() -> None:
            path = filedialog.askopenfilename(title="DATANORM-Datei wählen", filetypes=[("DATANORM/Text", "*.txt *.TXT *.csv *.CSV"), ("Alle Dateien", "*.*")])
            if not path: return
            result = self.db.import_datanorm_products(Path(path))
            dialog.destroy()
            self.refresh_current()
            self.status_message(f"DATANORM-Import: {result['imported']} neu, {result['updated']} aktualisiert, {result['deleted']} gelöscht, {result['skipped']} übersprungen.")
            messagebox.showinfo("DATANORM-Import abgeschlossen", f"Neu importiert: {result['imported']}\nAktualisiert: {result['updated']}\nGelöscht: {result['deleted']}\nÜbersprungen: {result['skipped']}\n\nDie importierten Daten wurden in den Audit-Log geschrieben.")
        ttk.Button(buttons, text="Datei wählen und importieren", style="Primary.TButton", command=choose_and_import).pack(side="right")

    def _dialog_shell(self, title: str, width: int = 700, height: int = 580) -> tuple[tk.Toplevel, tk.Frame]:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry(f"{width}x{height}")
        dialog.minsize(width, height)
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        frame = ttk.Frame(dialog, style="Card.TFrame", padding=24)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        return dialog, frame

    def open_customer_dialog(self, customer_id: int | None = None) -> None:
        existing = self.db.customer(customer_id) if customer_id else None
        dialog, frame = self._dialog_shell("Kunde bearbeiten" if existing else "Neuer Kunde")
        ttk.Label(frame, text="Kunde bearbeiten" if existing else "Neuer Kunde", style="Section.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Stammdaten für Angebote, Rechnungen und DATEV.", style="MutedCard.TLabel").pack(anchor="w", pady=(4, 14))
        variables: dict[str, tk.StringVar] = {}
        fields = [("name", "Name *"), ("company", "Firma"), ("email", "E-Mail"), ("phone", "Telefon"), ("address", "Straße"), ("postal_code", "PLZ"), ("city", "Ort"), ("country", "Land"), ("tax_number", "Steuernummer"), ("notes", "Notiz")]
        for key, label in fields:
            variable = tk.StringVar(value=existing[key] if existing else "")
            variables[key] = variable
            line = ttk.Frame(frame, style="Card.TFrame")
            line.pack(fill="x", pady=4)
            ttk.Label(line, text=label, width=18, style="Card.TLabel").pack(side="left")
            ttk.Entry(line, textvariable=variable).pack(side="left", fill="x", expand=True)
        buttons = ttk.Frame(frame, style="Card.TFrame")
        buttons.pack(fill="x", pady=(18, 0))
        ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Speichern", style="Primary.TButton", command=lambda: self.save_customer(dialog, variables, customer_id)).pack(side="right")

    def save_customer(self, dialog: tk.Toplevel, variables: dict[str, tk.StringVar], customer_id: int | None) -> None:
        try:
            self.db.save_customer({key: var.get() for key, var in variables.items()}, customer_id)
            dialog.destroy()
            self.refresh_current()
            self.status_message("Kunde gespeichert.")
        except (ValueError, Exception) as error:
            messagebox.showerror("Kunde konnte nicht gespeichert werden", str(error), parent=dialog)

    def open_product_dialog(self, product_id: int | None = None) -> None:
        existing = self.db.product(product_id) if product_id else None
        dialog, frame = self._dialog_shell("Produkt bearbeiten" if existing else "Neues Produkt", 620, 440)
        ttk.Label(frame, text="Produkt bearbeiten" if existing else "Neues Produkt", style="Section.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Positionen werden in Rechnungen als Snapshot gespeichert.", style="MutedCard.TLabel").pack(anchor="w", pady=(4, 14))
        variables: dict[str, tk.Variable] = {}
        fields = [("name", "Name *"), ("sku", "SKU"), ("description", "Beschreibung"), ("unit", "Einheit"), ("net_price", "Nettopreis"), ("tax_rate", "Steuersatz %")]
        for key, label in fields:
            if key == "net_price":
                value = str(existing["net_price_cents"] / 100) if existing and key == "net_price" else ""
            else:
                value = existing[key] if existing else ""
            variable = tk.StringVar(value=value)
            variables[key] = variable
            line = ttk.Frame(frame, style="Card.TFrame")
            line.pack(fill="x", pady=5)
            ttk.Label(line, text=label, width=18, style="Card.TLabel").pack(side="left")
            ttk.Entry(line, textvariable=variable).pack(side="left", fill="x", expand=True)
        # Aktiv-Checkbox
        active_var = tk.BooleanVar(value=bool(existing["active"]) if existing else True)
        variables["active"] = active_var
        chk = ttk.Checkbutton(frame, text="Aktiv", variable=active_var)
        chk.pack(anchor="w", pady=(10, 0))
        buttons = ttk.Frame(frame, style="Card.TFrame")
        buttons.pack(fill="x", pady=(18, 0))
        ttk.Button(buttons, text="Abbrechen", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Speichern", style="Primary.TButton", command=lambda: self.save_product(dialog, variables, product_id)).pack(side="right")

    def save_product(self, dialog: tk.Toplevel, variables: dict[str, tk.StringVar], product_id: int | None) -> None:
        try:
            self.db.save_product({key: var.get() for key, var in variables.items()}, product_id)
            dialog.destroy()
            self.refresh_current()
            self.status_message("Produkt gespeichert.")
        except Exception as error:
            messagebox.showerror("Produkt konnte nicht gespeichert werden", str(error), parent=dialog)

    def open_invoice_dialog(self) -> None:
        customers = self.db.customers()
        products = self.db.products()
        if not customers:
            messagebox.showinfo("Kunde fehlt", "Legen Sie zuerst einen Kunden an.")
            return
        dialog, frame = self._dialog_shell("Neue Rechnung", 850, 650)
        ttk.Label(frame, text="Neue Rechnung", style="Section.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Positionen erfassen, Steuern prüfen, Rechnung anlegen.", style="MutedCard.TLabel").pack(anchor="w", pady=(4, 12))
        top = ttk.Frame(frame, style="Card.TFrame")
        top.pack(fill="x")
        customer_var = tk.StringVar(value=customers[0]["name"])
        date_var = tk.StringVar(value=today())
        try:
            days = int(self.db.setting("payment_terms_days", "14"))
        except ValueError:
            days = 14
        due_var = tk.StringVar(value=(date.today() + timedelta(days=days)).isoformat())
        notes_var = tk.StringVar()
        for label, variable in [("Kunde", customer_var), ("Rechnungsdatum", date_var), ("Fällig", due_var)]:
            ttk.Label(top, text=label, style="Card.TLabel").pack(side="left", padx=(0, 7))
            if label == "Kunde":
                box = ttk.Combobox(top, textvariable=customer_var, values=[f"{row['name']} · {row['company']}" for row in customers], state="readonly", width=35)
            else:
                box = ttk.Entry(top, textvariable=variable, width=14)
            box.pack(side="left", padx=(0, 15))
        ttk.Label(top, text="Notiz", style="Card.TLabel").pack(side="left", padx=(0, 7))
        ttk.Entry(top, textvariable=notes_var).pack(side="left", fill="x", expand=True)
        items_frame = ttk.Frame(frame, style="Card.TFrame")
        items_frame.pack(fill="both", expand=True, pady=(15, 8))
        item_tree = ttk.Treeview(items_frame, columns=("desc", "qty", "unit", "price", "tax", "total"), show="headings", height=7)
        for key, label, width in [("desc", "Beschreibung", 330), ("qty", "Menge", 70), ("unit", "Einheit", 90), ("price", "Netto", 100), ("tax", "Steuer", 80), ("total", "Gesamt", 110)]: item_tree.heading(key, text=label); item_tree.column(key, width=width)
        item_tree.pack(side="left", fill="both", expand=True)
        item_values: list[dict] = []
        add = ttk.Frame(frame, style="Card.TFrame")
        add.pack(fill="x", pady=4)
        desc = ttk.Combobox(add, values=[row["name"] for row in products], width=33)
        desc.pack(side="left", padx=(0, 5))
        qty = ttk.Entry(add, width=7); qty.insert(0, "1"); qty.pack(side="left", padx=5)
        unit = ttk.Entry(add, width=8); unit.insert(0, "Stk."); unit.pack(side="left", padx=5)
        price = ttk.Entry(add, width=12); price.insert(0, "0,00"); price.pack(side="left", padx=5)
        tax = ttk.Entry(add, width=8); tax.insert(0, "19"); tax.pack(side="left", padx=5)
        def add_item() -> None:
            text = desc.get().strip()
            if not text: return
            quantity = qty.get().strip(); rate = tax.get().strip(); price_value = money(price.get())
            try:
                q = float(quantity.replace(",", ".")); r = float(rate.replace(",", "."))
                if q <= 0 or not 0 <= r <= 100: raise ValueError
            except ValueError:
                messagebox.showerror("Ungültige Position", "Menge oder Steuersatz ist ungültig.", parent=dialog); return
            sub = int(round(q * price_value)); tax_value = int(round(sub * r / 100)); total = sub + tax_value
            item_values.append({"description": text, "quantity": q, "unit": unit.get().strip() or "Stk.", "unit_price": price_value, "tax_rate": r})
            item_tree.insert("", "end", values=(text, quantity, unit.get(), euro(price_value), f"{rate:g} %", euro(total)))
            desc.delete(0, "end"); qty.delete(0, "end"); qty.insert(0, "1"); price.delete(0, "end"); price.insert(0, "0,00")
        ttk.Button(add, text="+ Position", command=add_item).pack(side="left", padx=(7, 0))
        desc.bind("<Return>", lambda _event: add_item())
        bottom = ttk.Frame(frame, style="Card.TFrame")
        bottom.pack(fill="x", pady=(12, 0))
        ttk.Label(bottom, text="Der Rechnungsbetrag wird beim Speichern serverseitig aus den Positionen berechnet.", style="MutedCard.TLabel").pack(side="left")
        ttk.Button(bottom, text="Abbrechen", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(bottom, text="Rechnung anlegen", style="Primary.TButton", command=lambda: self.save_invoice(dialog, customer_var, date_var, due_var, notes_var, item_values)).pack(side="right")
        if products:
            first = products[0]; desc.insert(0, "first" if False else first["name"]); price.delete(0, "end"); price.insert(0, f"{first['net_price_cents'] / 100:.2f}".replace(".", ",")); tax.delete(0, "end"); tax.insert(0, str(first["tax_rate"]))

    def save_invoice(self, dialog: tk.Toplevel, customer_var: tk.StringVar, date_var: tk.StringVar, due_var: tk.StringVar, notes: tk.StringVar, items: list[dict]) -> None:
        customers = self.db.customers()
        selected = next((row for row in customers if f"{row['name']} · {row['company']}" == customer_var.get()), customers[0])
        try:
            invoice_id = self.db.create_invoice(int(selected["id"]), date_var.get().strip(), due_var.get().strip(), notes.get().strip(), items)
            dialog.destroy()
            self.show_invoices()
            self.open_invoice_details(invoice_id)
            self.status_message("Rechnung angelegt.")
        except Exception as error:
            messagebox.showerror("Rechnung konnte nicht angelegt werden", str(error), parent=dialog)

    def open_invoice_details(self, invoice_id: int) -> None:
        invoice = self.db.invoice(invoice_id)
        if not invoice: return
        dialog, frame = self._dialog_shell(f"Rechnung {invoice['invoice_number']}", 720, 610)
        ttk.Label(frame, text=invoice["invoice_number"], style="Section.TLabel").pack(anchor="w")
        ttk.Label(frame, text=f"{invoice['customer_name']} · Rechnungsdatum {invoice['invoice_date']} · fällig {invoice['due_date']}", style="MutedCard.TLabel").pack(anchor="w", pady=(4, 14))
        card = ttk.Frame(frame, style="Card.TFrame")
        card.pack(fill="both", expand=True)
        tree = ttk.Treeview(card, columns=("description", "quantity", "unit_price_cents", "line_total_cents"), show="headings", height=8)
        for key, label, width in [("description", "Position", 350), ("quantity", "Menge", 80), ("unit_price_cents", "Netto", 120), ("line_total_cents", "Gesamt", 120)]: tree.heading(key, text=label); tree.column(key, width=width)
        for item in self.db.invoice_items(invoice_id): tree.insert("", "end", values=(item["description"], item["quantity"], euro(int(item["unit_price_cents"])), euro(int(item["line_total_cents"]))))
        tree.pack(fill="both", expand=True)
        totals = tk.Frame(frame, bg=CARD); totals.pack(fill="x", pady=(12, 0))
        for label, value in [("Netto", euro(int(invoice["subtotal_cents"]))), ("Steuer", euro(int(invoice["tax_cents"]))), ("Gesamt", euro(int(invoice["total_cents"]))), ("Bezahlt", euro(int(invoice["paid_cents"])))]: 
            line = tk.Frame(totals, bg=CARD); line.pack(fill="x", pady=2); tk.Label(line, text=label, bg=CARD, fg=MUTED).pack(side="left"); tk.Label(line, text=value, bg=CARD, fg=TEXT, font=("DejaVu Sans", 9, "bold")).pack(side="right")
        actions = ttk.Frame(frame, style="Card.TFrame"); actions.pack(fill="x", pady=(15, 0))
        ttk.Button(actions, text="Schließen", command=dialog.destroy).pack(side="right")
        if int(invoice["paid_cents"]) < int(invoice["total_cents"]) and invoice["status"] not in ("entwurf", "storniert"):
            ttk.Button(actions, text="Zahlung erfassen", style="Primary.TButton", command=lambda: self.open_payment_dialog(invoice_id, dialog)).pack(side="right", padx=(0, 8))

    def open_payment_dialog(self, invoice_id: int, parent: tk.Toplevel) -> None:
        dialog, frame = self._dialog_shell("Zahlung erfassen", 450, 300)
        ttk.Label(frame, text="Zahlung erfassen", style="Section.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Die Zahlung wird direkt auf die offene Rechnung gebucht.", style="MutedCard.TLabel").pack(anchor="w", pady=(4, 14))
        amount = tk.StringVar(); method = tk.StringVar(value="bank"); reference = tk.StringVar()
        ttk.Label(frame, text="Betrag *", style="Card.TLabel").pack(anchor="w"); ttk.Entry(frame, textvariable=amount).pack(fill="x", pady=5)
        ttk.Label(frame, text="Methode", style="Card.TLabel").pack(anchor="w", pady=(5, 0)); ttk.Combobox(frame, textvariable=method, values=("bank", "cash", "card", "paypal"), state="readonly").pack(fill="x", pady=5)
        ttk.Label(frame, text="Referenz", style="Card.TLabel").pack(anchor="w", pady=(5, 0)); ttk.Entry(frame, textvariable=reference).pack(fill="x", pady=5)
        def save():
            try:
                self.db.record_payment(invoice_id, money(amount.get()), method.get(), reference.get())
                dialog.destroy(); parent.destroy(); self.refresh_current(); self.status_message("Zahlung gespeichert.")
            except Exception as error: messagebox.showerror("Zahlung fehlgeschlagen", str(error), parent=dialog)
        ttk.Button(frame, text="Zahlung speichern", style="Primary.TButton", command=save).pack(anchor="e", pady=(15, 0))

    def show_help(self) -> None:
        messagebox.showinfo(
            "Hilfe",
            "Hotdesk ist eine eigenständige Desktop-Anwendung zur Verwaltung von Kunden, Produkten, Rechnungen und Zahlungen.\n\n"
            "Tastenkürzel:\n"
            "Ctrl+N: Neuer Kunde\n"
            "Ctrl+I: Neue Rechnung\n"
            "F1: Diese Hilfe\n"
            "F5: Aktuelle Ansicht aktualisieren\n"
            "\n"
            "Daten werden lokal unter ~/.local/share/hotdesk/ gespeichert.\n"
            "Backups können über das Menü erstellt werden.",
            parent=self,
        )

    def close(self) -> None:
        self.db.close()
        self.destroy()


def main() -> None:
    app = HotdeskApp()
    app.mainloop()


if __name__ == "__main__":
    main()
