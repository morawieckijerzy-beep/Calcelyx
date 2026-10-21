from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tkinter as tk
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from uuid import uuid4

import customtkinter as ctk

from .database import Database
from .domain import Estimate, Project, Room
from .floorplan import FloorPlanCanvas
from .i18n import SUPPORTED_LANGUAGES, get_language, install_ui_localization, set_language, tr
from .pricelist import (
    ALLOWED_UNITS,
    PriceItem,
    PricelistValidationError,
    create_template_xlsx,
    import_pricelist_xlsx,
    item_to_dict,
    load_demo_items,
)
from .reporting import SUPPORTED_CURRENCIES, export_estimate_xlsx, export_offer_pdf, money, normalize_currency
from .theme import FONT_FAMILY, TYPOGRAPHY, configure_ttk_styles, ctk_color


install_ui_localization()

APP_NAME = "Calcelyx"
APP_VERSION = "1.0"
Q2 = Decimal("0.01")


def safe_filename_component(value: object, fallback: str = "Projekt") -> str:
    """Return a readable Windows-safe file-name fragment."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return (cleaned or fallback)[:80].rstrip(" .")


def project_archive_filename(state: dict) -> str:
    project = state.get("project", {})
    name = safe_filename_component(project.get("name"), "Projekt bez nazwy")
    client = safe_filename_component(project.get("client_name"), "")
    label = f"{name} - {client}" if client else name
    short_id = safe_filename_component(str(state.get("id", "projekt"))[:8], "projekt")
    return f"{label} [{short_id}].json"


def runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", runtime_root()))


def user_data_root() -> Path:
    """Keep data shared when a patched one-folder build sits next to Calcelyx."""
    root = runtime_root()
    if getattr(sys, "frozen", False) and root.name.casefold() != "calcelyx":
        canonical = root.parent / "Calcelyx"
        if (canonical / "Dane").exists():
            return canonical
    return root


def d(value: object, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value).replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def q(value: Decimal) -> Decimal:
    return value.quantize(Q2, rounding=ROUND_HALF_UP)


def display_number(value: object, digits: int = 2) -> str:
    rendered = f"{d(value):.{digits}f}"
    return rendered.replace(".", ",") if get_language() == "pl" else rendered


def parse_number(
    value: object,
    label: str,
    *,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
    integer: bool = False,
) -> Decimal:
    """Parse user input without silently replacing mistakes with zero."""
    text = str(value).strip().replace(" ", "").replace(",", ".")
    if not text:
        raise ValueError(f"Pole „{label}” jest wymagane.")
    try:
        result = Decimal(text)
    except (InvalidOperation, ValueError):
        raise ValueError(f"Pole „{label}” musi zawierać liczbę, np. 12,50.") from None
    if not result.is_finite():
        raise ValueError(f"Pole „{label}” musi zawierać skończoną liczbę.")
    if integer and result != result.to_integral_value():
        raise ValueError(f"Pole „{label}” musi zawierać liczbę całkowitą.")
    if minimum is not None and result < minimum:
        raise ValueError(f"Pole „{label}” nie może być mniejsze niż {display_number(minimum)}.")
    if maximum is not None and result > maximum:
        raise ValueError(f"Pole „{label}” nie może być większe niż {display_number(maximum)}.")
    return result


class AppState(dict):
    """Dictionary that preserves Tk's callable ``window.state()`` API."""

    def __init__(self, window: tk.Misc, initial: dict) -> None:
        super().__init__(initial)
        self._window = window

    def __call__(self, newstate: str | None = None) -> str:
        if newstate is None:
            return str(self._window.tk.call("wm", "state", self._window._w))
        return str(self._window.tk.call("wm", "state", self._window._w, newstate))


class App(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1460x900")
        self.minsize(1180, 760)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        try:
            self.iconbitmap(str(bundle_root() / "assets" / "app.ico"))
        except Exception:
            pass
        configure_ttk_styles(self)

        storage_root = user_data_root()
        self.data_dir = storage_root / "Dane"
        self.export_dir = storage_root / "Eksporty"
        self.backup_dir = storage_root / "Kopie_zapasowe"
        self.projects_dir = self.data_dir / "Projekty"
        for directory in (self.data_dir, self.export_dir, self.backup_dir, self.projects_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self.state_path = self.data_dir / "projekt_biezacy.json"
        legacy_database = self.data_dir / "tomek_wyceny.sqlite3"
        database_path = self.data_dir / "calcelyx.sqlite3"
        if legacy_database.exists() and not database_path.exists():
            shutil.copy2(legacy_database, database_path)
        self.db = Database(database_path)
        self._dirty = False
        self.current_page = "start"
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self.floor_canvas: FloorPlanCanvas | None = None
        self._last_deleted_rooms: list[dict] = []
        self._last_deleted_lines: list[dict] = []
        self._last_deleted_prices: list[PriceItem] = []

        self.language = "en"
        set_language(self.language)
        self.state = AppState(self, self._default_state())
        self.prices: list[PriceItem] = []
        self._load_state()
        self.language = str(self.state.get("language", "en"))
        set_language(self.language)

        self._build_interface()
        self.bind_all("<Control-z>", self._global_undo)
        self.bind_all("<Control-y>", self._global_redo)
        self.bind_all("<Control-Shift-Z>", self._global_redo)

    def _build_interface(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.nav_buttons = {}
        self._build_sidebar()
        self.main = ctk.CTkFrame(self, fg_color=ctk_color("background"), corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)
        self._build_topbar()
        self.content = ctk.CTkFrame(self.main, fg_color="transparent", corner_radius=0)
        self.content.grid(row=1, column=0, sticky="nsew", padx=26, pady=(6, 24))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self.show_page(self.current_page)

    @staticmethod
    def _default_state() -> dict:
        return {
            "id": str(uuid4()),
            "language": get_language(),
            "project": {
                "name": tr("Nowa wycena"),
                "number": f"{tr('OF/')}{date.today().year}/001",
                "date": date.today().isoformat(),
                "currency": "PLN",
                "client_name": "",
                "client_phone": "",
                "client_email": "",
                "address": "",
                "valid_days": 14,
                "markup_pct": 0,
                "discount_pct": 0,
                "company_name": tr("Twoja Firma Wykończeniowa"),
                "company_details": tr("Uzupełnij dane firmy w Ustawieniach"),
                "assumptions": tr("Wycena została przygotowana na podstawie podanych wymiarów. Prace ukryte i niemożliwe do oceny przed rozpoczęciem robót wymagają osobnego uzgodnienia."),
            },
            "rooms": [],
            "floorplan": {},
            "lines": [],
            "travel": {"one_way_km": 0, "visits": 0, "rate": 0, "free_km": 0, "parking": 0, "round_trip": True, "included": False},
            "pricelist": [],
        }

    def _load_state(self) -> None:
        if self.state_path.exists():
            try:
                loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
                defaults = self._default_state()
                defaults.update(loaded)
                defaults["project"].update(loaded.get("project", {}))
                defaults["travel"].update(loaded.get("travel", {}))
                self.state = AppState(self, defaults)
            except Exception as exc:
                messagebox.showwarning("Odzyskiwanie danych", f"Nie udało się odczytać ostatniego projektu:\n{exc}")
        self.language = str(self.state.get("language", "en"))
        set_language(self.language)
        raw_prices = self.state.get("pricelist") or []
        if raw_prices:
            try:
                self.prices = [PriceItem(**item) for item in raw_prices]
            except Exception:
                self.prices = []
        if not self.prices:
            try:
                self.prices = self._bundled_demo_prices(self.language)
            except Exception:
                self.prices = []

    @staticmethod
    def _bundled_demo_prices(language: str) -> list[PriceItem]:
        demo_name = "pricelist_example_en.json" if language == "en" else "cennik_przykladowy.json"
        demo_path = bundle_root() / "data" / demo_name
        return load_demo_items(demo_path if demo_path.exists() else None)

    def _switch_demo_pricelist_language(self, language: str) -> None:
        """Swap only an untouched bundled catalogue; never rewrite custom content."""
        current = [item_to_dict(item) for item in self.prices]
        try:
            known_demos = [
                [item_to_dict(item) for item in self._bundled_demo_prices(code)]
                for code in SUPPORTED_LANGUAGES
            ]
            if current in known_demos:
                self.prices = self._bundled_demo_prices(language)
        except Exception:
            return

    def _save_state(self, quiet: bool = False) -> None:
        if self.floor_canvas:
            self.state["floorplan"] = self.floor_canvas.serialize()
        self.state["pricelist"] = [item_to_dict(item) for item in self.prices]
        previous_project_file = self.state.get("_project_file")
        friendly_name = project_archive_filename(self.state)
        self.state["_project_file"] = friendly_name
        temp = self.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, self.state_path)
        project_copy = self.projects_dir / friendly_name
        project_copy.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        obsolete_names = {str(previous_project_file or ""), f"{self.state['id']}.json"}
        for obsolete_name in obsolete_names:
            obsolete = self.projects_dir / obsolete_name
            if obsolete_name and obsolete != project_copy and obsolete.exists() and obsolete.is_file():
                obsolete.unlink()
        project = self._domain_project()
        self.db.save_project(project)
        self._dirty = False
        self.status_var.set(f"{tr('Zapisano lokalnie • ')}{datetime.now().strftime('%H:%M')}")
        if not quiet:
            self._toast("Projekt został zapisany.")

    def _domain_project(self) -> Project:
        rooms: list[Room] = []
        for item in self.state["rooms"]:
            length, width = d(item.get("length")), d(item.get("width"))
            points = item.get("points") or [["0", "0"], [str(length), "0"], [str(length), str(width)], ["0", str(width)]]
            try:
                rooms.append(Room(name=item["name"], points=points, height=item.get("height", "2.6")))
            except Exception:
                continue
        return Project(
            id=self.state["id"],
            name=self.state["project"].get("name") or "Nowa wycena",
            customer_name=self.state["project"].get("client_name", ""),
            notes=json.dumps({"project": self.state["project"], "travel": self.state["travel"]}, ensure_ascii=False),
            rooms=rooms,
        )

    def mark_dirty(self) -> None:
        self._dirty = True
        if hasattr(self, "status_var"):
            self.status_var.set(tr("Niezapisane zmiany"))

    def _money(self, value: object) -> str:
        return money(value, self.language, self.state["project"].get("currency", "PLN"))

    def _global_undo(self, _event: tk.Event | None = None) -> str | None:
        if self.current_page == "plan" and self.floor_canvas:
            self.floor_canvas.undo()
            return "break"
        return None

    def _global_redo(self, _event: tk.Event | None = None) -> str | None:
        if self.current_page == "plan" and self.floor_canvas:
            self.floor_canvas.redo()
            return "break"
        return None

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=238, corner_radius=0, fg_color=ctk_color("surface"))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        logo = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo.pack(fill="x", padx=22, pady=(24, 25))
        ctk.CTkLabel(logo, text="CX", width=42, height=42, corner_radius=10, fg_color=ctk_color("accent"), text_color="white", font=(FONT_FAMILY, 15, "bold")).pack(side="left")
        text = ctk.CTkFrame(logo, fg_color="transparent")
        text.pack(side="left", padx=11)
        ctk.CTkLabel(text, text="Calcelyx", font=(FONT_FAMILY, 16, "bold"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(text, text="wersja 1.0 • offline", font=(FONT_FAMILY, 10), text_color=ctk_color("text_muted"), anchor="w").pack(anchor="w")

        items = [
            ("start", "⌂", "Pulpit"),
            ("investment", "▤", "Inwestycja"),
            ("plan", "⌑", "Rzut i obmiary"),
            ("estimate", "Σ", "Kosztorys"),
            ("prices", "▦", "Cennik"),
            ("settings", "⚙", "Ustawienia"),
        ]
        for key, icon, label in items:
            button = ctk.CTkButton(
                sidebar, text=f"{icon}    {tr(label)}", anchor="w", height=44, corner_radius=8,
                fg_color="transparent", hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"),
                font=(FONT_FAMILY, 12), command=lambda page=key: self.show_page(page),
            )
            button.pack(fill="x", padx=14, pady=2)
            self.nav_buttons[key] = button

    def _build_topbar(self) -> None:
        top = ctk.CTkFrame(self.main, height=72, corner_radius=0, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=26, pady=(8, 0))
        top.grid_columnconfigure(1, weight=1)
        self.page_title = ctk.CTkLabel(top, text="Pulpit", font=TYPOGRAPHY["title"], anchor="w")
        self.page_title.grid(row=0, column=0, sticky="w")
        self.status_var = tk.StringVar(value=tr("Dane przechowywane lokalnie"))
        ctk.CTkLabel(top, textvariable=self.status_var, font=TYPOGRAPHY["caption"], text_color=ctk_color("text_muted")).grid(row=0, column=1, padx=18, sticky="e")
        ctk.CTkButton(top, text="Zapisz", width=105, height=38, corner_radius=8, command=self._save_state).grid(row=0, column=2, padx=(0, 8))
        ctk.CTkButton(top, text="Eksport PDF", width=125, height=38, corner_radius=8, fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=self.export_pdf).grid(row=0, column=3)

    def show_page(self, page: str) -> None:
        if self.floor_canvas and self.current_page == "plan":
            self.state["floorplan"] = self.floor_canvas.serialize()
        self.floor_canvas = None
        self.current_page = page
        for child in self.content.winfo_children():
            child.destroy()
        for key, button in self.nav_buttons.items():
            button.configure(fg_color=ctk_color("selection") if key == page else "transparent", text_color=ctk_color("accent") if key == page else ctk_color("text"))
        builders = {
            "start": ("Pulpit", self._page_dashboard),
            "investment": ("Inwestycja", self._page_investment),
            "plan": ("Rzut i obmiary", self._page_plan),
            "estimate": ("Kosztorys", self._page_estimate),
            "prices": ("Cennik robót", self._page_prices),
            "settings": ("Ustawienia", self._page_settings),
        }
        title, builder = builders[page]
        self.page_title.configure(text=title)
        builder()

    def _scroll_page(self) -> ctk.CTkScrollableFrame:
        page = ctk.CTkScrollableFrame(self.content, fg_color="transparent", corner_radius=0)
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_columnconfigure(0, weight=1)
        return page

    def _card(self, parent: tk.Misc, title: str | None = None) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=ctk_color("surface"), corner_radius=12, border_width=1, border_color=ctk_color("border"))
        if title:
            ctk.CTkLabel(frame, text=title, font=TYPOGRAPHY["heading"], anchor="w").pack(fill="x", padx=20, pady=(17, 10))
        return frame

    def _metric_card(self, parent: tk.Misc, label: str, value: str, caption: str, column: int) -> None:
        card = self._card(parent)
        card.grid(row=0, column=column, padx=(0 if column == 0 else 7, 0 if column == 3 else 7), sticky="ew")
        ctk.CTkLabel(card, text=str(tr(label)).upper(), font=(FONT_FAMILY, 10, "bold"), text_color=ctk_color("text_muted")).pack(anchor="w", padx=18, pady=(16, 5))
        ctk.CTkLabel(card, text=value, font=(FONT_FAMILY, 23, "bold")).pack(anchor="w", padx=18)
        ctk.CTkLabel(card, text=caption, font=TYPOGRAPHY["caption"], text_color=ctk_color("text_muted")).pack(anchor="w", padx=18, pady=(4, 16))

    def _page_dashboard(self) -> None:
        page = self._scroll_page()
        hero = ctk.CTkFrame(page, fg_color="#172033", corner_radius=14)
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        left = ctk.CTkFrame(hero, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=27, pady=24)
        ctk.CTkLabel(left, text="Dobra wycena zaczyna się od dobrego obmiaru.", font=(FONT_FAMILY, 22, "bold"), text_color="white", anchor="w").pack(anchor="w")
        ctk.CTkLabel(left, text="Rzut, cennik, kosztorys i gotowa oferta — lokalnie, bez chmury.", font=(FONT_FAMILY, 12), text_color="#CBD5E1", anchor="w").pack(anchor="w", pady=(6, 16))
        ctk.CTkButton(left, text="Kontynuuj wycenę", width=150, height=39, command=lambda: self.show_page("investment")).pack(anchor="w")
        actions = ctk.CTkFrame(left, fg_color="transparent")
        actions.pack(anchor="w", pady=(9, 0))
        ctk.CTkButton(actions, text="Nowy projekt", width=118, height=34, fg_color="#334155", hover_color="#475569", command=self._new_project).pack(side="left")
        ctk.CTkButton(actions, text="Otwórz projekt", width=125, height=34, fg_color="#334155", hover_color="#475569", command=self._open_project).pack(side="left", padx=8)

        metrics = ctk.CTkFrame(page, fg_color="transparent")
        metrics.grid(row=1, column=0, sticky="ew")
        for i in range(4):
            metrics.grid_columnconfigure(i, weight=1)
        totals = self._calculate_totals()
        self._metric_card(metrics, "Pomieszczenia", str(len(self.state["rooms"])), "w bieżącym projekcie", 0)
        self._metric_card(metrics, "Powierzchnia", f"{display_number(sum(d(r.get('floor_area', 0)) for r in self.state['rooms']), 1)} m²", "łączna podłoga", 1)
        self._metric_card(metrics, "Pozycje", str(len(self.state["lines"])), "w kosztorysie", 2)
        self._metric_card(metrics, "Wartość brutto", self._money(totals["gross"]), "bieżąca wersja", 3)

        grid = ctk.CTkFrame(page, fg_color="transparent")
        grid.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        grid.grid_columnconfigure((0, 1), weight=1)
        project_card = self._card(grid, "Bieżąca wycena")
        project_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        p = self.state["project"]
        for label, value in (("Nazwa", p["name"]), ("Numer", p["number"]), ("Klient", p["client_name"] or "Nie podano"), ("Adres", p["address"] or "Nie podano")):
            row = ctk.CTkFrame(project_card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=6)
            ctk.CTkLabel(row, text=label, width=90, anchor="w", text_color=ctk_color("text_muted")).pack(side="left")
            ctk.CTkLabel(row, text=value, anchor="w", font=(FONT_FAMILY, 11, "bold")).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(project_card, text="Edytuj dane inwestycji", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=lambda: self.show_page("investment")).pack(anchor="w", padx=20, pady=(12, 20))

        checklist = self._card(grid, "Gotowość oferty")
        checklist.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        checks = [
            (bool(p["client_name"]), "Dane klienta"),
            (bool(self.state["rooms"]), "Pomieszczenia i obmiary"),
            (bool(self.state["lines"]), "Pozycje kosztorysu"),
            (bool(p["company_name"]), "Dane wykonawcy"),
        ]
        for ok, label in checks:
            ctk.CTkLabel(checklist, text=f"{'●' if ok else '○'}  {tr(label)}", text_color=ctk_color("success") if ok else ctk_color("text_muted"), font=(FONT_FAMILY, 11, "bold" if ok else "normal"), anchor="w").pack(fill="x", padx=20, pady=7)

    def _field(self, parent: tk.Misc, label: str, key: str, row: int, column: int, width: int = 250) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, font=(FONT_FAMILY, 10, "bold"), text_color=ctk_color("text_muted"), anchor="w").grid(row=row * 2, column=column, sticky="ew", padx=8, pady=(7, 3))
        entry = ctk.CTkEntry(parent, height=38, width=width, corner_radius=7)
        entry.insert(0, str(self.state["project"].get(key, "")))
        entry.grid(row=row * 2 + 1, column=column, sticky="ew", padx=8, pady=(0, 7))
        entry.bind("<KeyRelease>", lambda _e, e=entry, k=key: self._set_project(k, e.get()))
        if key in {"markup_pct", "discount_pct", "valid_days"}:
            entry.bind("<FocusOut>", lambda _e, e=entry, k=key, l=label: self._validate_project_number(e, k, l))
        return entry

    def _validate_project_number(self, entry: ctk.CTkEntry, key: str, label: str) -> None:
        rules = {
            "markup_pct": (Decimal("0"), Decimal("1000"), False),
            "discount_pct": (Decimal("0"), Decimal("100"), False),
            "valid_days": (Decimal("1"), Decimal("3650"), True),
        }
        minimum, maximum, integer = rules[key]
        try:
            value = parse_number(entry.get(), label, minimum=minimum, maximum=maximum, integer=integer)
        except ValueError as exc:
            messagebox.showwarning("Nieprawidłowa wartość", str(exc), parent=self)
            entry.delete(0, "end")
            entry.insert(0, str(self._default_state()["project"][key]))
            self.state["project"][key] = self._default_state()["project"][key]
            return
        self.state["project"][key] = str(value)

    def _set_project(self, key: str, value: object) -> None:
        self.state["project"][key] = value
        self.mark_dirty()

    def _page_investment(self) -> None:
        page = self._scroll_page()
        form = self._card(page, "Dane projektu i klienta")
        form.grid(row=0, column=0, sticky="ew")
        body = ctk.CTkFrame(form, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=(0, 16))
        for i in range(3):
            body.grid_columnconfigure(i, weight=1)
        fields = [("Nazwa projektu", "name"), ("Numer oferty", "number"), ("Data", "date"), ("Klient", "client_name"), ("Telefon", "client_phone"), ("E-mail", "client_email"), ("Adres inwestycji", "address")]
        for idx, (label, key) in enumerate(fields):
            self._field(body, label, key, idx // 3, idx % 3)

        room_card = self._card(page, "Pomieszczenia")
        room_card.grid(row=1, column=0, sticky="ew", pady=(18, 0))
        controls = ctk.CTkFrame(room_card, fg_color="transparent")
        controls.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkButton(controls, text="＋ Dodaj pomieszczenie ręcznie", width=220, command=self._open_room_editor).pack(side="left")
        ctk.CTkButton(controls, text="Otwórz rzut — skaluj, przesuń i wykonaj obmiar", width=310, fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=lambda: self.show_page("plan")).pack(side="left", padx=8)
        ctk.CTkLabel(controls, text="Kliknij dwukrotnie wiersz, aby edytować wymiary, drzwi i okna.", text_color=ctk_color("text_muted")).pack(side="right")

        tree = ttk.Treeview(room_card, columns=("name", "floor", "walls", "ceiling", "baseboard", "windows", "height"), show="headings", height=9)
        for col, label, width in (("name", "Pomieszczenie", 210), ("floor", "Podłoga", 105), ("walls", "Ściany netto", 115), ("ceiling", "Sufit", 100), ("baseboard", "Listwy", 100), ("windows", "Okna: dł. / pole", 145), ("height", "Wysokość", 90)):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w" if col == "name" else "e")
        for room in self.state["rooms"]:
            window_summary = f"{display_number(room.get('window_width', 0))} m / {display_number(room.get('window_area', 0))} m²"
            tree.insert("", "end", iid=room["id"], values=(room["name"], f"{display_number(room['floor_area'])} m²", f"{display_number(room['walls_net'])} m²", f"{display_number(room['floor_area'])} m²", f"{display_number(room['baseboard'])} mb", window_summary, f"{display_number(room['height'])} m"))
        tree.pack(fill="x", padx=20, pady=(0, 8))
        tree.bind("<Double-1>", lambda _e: self._edit_room(tree))
        actions = ctk.CTkFrame(room_card, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(0, 18))
        ctk.CTkButton(actions, text="Przywróć ostatnio usunięte", width=190, fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), state="normal" if self._last_deleted_rooms else "disabled", command=self._restore_rooms).pack(side="left")
        ctk.CTkButton(actions, text="Edytuj zaznaczone", width=160, fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=lambda: self._edit_room(tree)).pack(side="right", padx=(8, 0))
        ctk.CTkButton(actions, text="Usuń zaznaczone", width=145, fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("error"), command=lambda: self._remove_room(tree)).pack(side="right")

    def _edit_room(self, tree: ttk.Treeview) -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Pomieszczenia", "Najpierw zaznacz pomieszczenie.", parent=self)
            return
        room = next((item for item in self.state["rooms"] if item["id"] == selected[0]), None)
        if room:
            self._open_room_editor(room)

    def _open_room_editor(self, room: dict | None = None) -> None:
        window = ctk.CTkToplevel(self)
        window.title("Edytuj pomieszczenie" if room else "Dodaj pomieszczenie")
        window.geometry("720x680")
        window.transient(self)
        window.grab_set()
        window.bind("<Escape>", lambda _e: window.destroy())
        ctk.CTkLabel(window, text="Edytuj pomieszczenie" if room else "Nowe pomieszczenie", font=TYPOGRAPHY["title"]).pack(anchor="w", padx=26, pady=(22, 4))
        ctk.CTkLabel(window, text="Dla prostokąta podaj długość i szerokość. Dla obrysu z rzutu możesz skorygować bezpośrednio pole i obwód.", wraplength=660, justify="left", text_color=ctk_color("text_muted")).pack(anchor="w", padx=26, pady=(0, 12))
        defaults = room or {}
        values = {
            "name": defaults.get("name", ""),
            "length": defaults.get("length", ""),
            "width": defaults.get("width", ""),
            "height": defaults.get("height", "2.60"),
            "floor_area": defaults.get("floor_area", ""),
            "perimeter": defaults.get("perimeter", ""),
            "door_width": defaults.get("door_width", "0"),
            "door_area": defaults.get("door_area", defaults.get("opening_area", "0")),
            "window_width": defaults.get("window_width", "0"),
            "window_area": defaults.get("window_area", "0"),
        }
        entries: dict[str, ctk.CTkEntry] = {}
        fields = (
            ("name", "Nazwa pomieszczenia"), ("length", "Długość pomieszczenia [m] — opcjonalnie"),
            ("width", "Szerokość pomieszczenia [m] — opcjonalnie"), ("height", "Wysokość [m]"),
            ("floor_area", "Powierzchnia podłogi/sufitu [m²]"), ("perimeter", "Obwód ścian [m]"),
            ("door_width", "Łączna szerokość drzwi [m]"), ("door_area", "Łączna powierzchnia drzwi [m²]"),
            ("window_width", "Łączna długość/szerokość okien [m]"), ("window_area", "Łączna powierzchnia okien [m²]"),
        )
        for key, label in fields:
            row = ctk.CTkFrame(window, fg_color="transparent")
            row.pack(fill="x", padx=26, pady=3)
            ctk.CTkLabel(row, text=label, width=370, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=285)
            value = values[key]
            entry.insert(0, str(value).replace(".", ",") if key != "name" else str(value))
            entry.pack(side="right")
            entries[key] = entry

        def save() -> None:
            name = entries["name"].get().strip()
            if not name:
                messagebox.showwarning("Pomieszczenie", "Podaj nazwę pomieszczenia.", parent=window)
                return
            try:
                height = parse_number(entries["height"].get(), "Wysokość", minimum=Decimal("0.1"), maximum=Decimal("20"))
                length_text, width_text = entries["length"].get().strip(), entries["width"].get().strip()
                if bool(length_text) != bool(width_text):
                    raise ValueError("Podaj jednocześnie długość i szerokość albo pozostaw oba pola puste.")
                if length_text:
                    length = parse_number(length_text, "Długość", minimum=Decimal("0.01"), maximum=Decimal("1000"))
                    width = parse_number(width_text, "Szerokość", minimum=Decimal("0.01"), maximum=Decimal("1000"))
                    floor_area, perimeter = length * width, 2 * (length + width)
                else:
                    length = width = None
                    floor_area = parse_number(entries["floor_area"].get(), "Powierzchnia podłogi", minimum=Decimal("0.01"), maximum=Decimal("1000000"))
                    perimeter = parse_number(entries["perimeter"].get(), "Obwód ścian", minimum=Decimal("0.01"), maximum=Decimal("100000"))
                door_width = parse_number(entries["door_width"].get() or "0", "Szerokość drzwi", minimum=Decimal("0"), maximum=perimeter)
                door_area = parse_number(entries["door_area"].get() or "0", "Powierzchnia drzwi", minimum=Decimal("0"))
                window_width = parse_number(entries["window_width"].get() or "0", "Długość okien", minimum=Decimal("0"), maximum=perimeter)
                window_area = parse_number(entries["window_area"].get() or "0", "Powierzchnia okien", minimum=Decimal("0"))
                if door_area + window_area >= perimeter * height:
                    raise ValueError("Łączna powierzchnia drzwi i okien musi być mniejsza od powierzchni ścian brutto.")
            except ValueError as exc:
                messagebox.showwarning("Nieprawidłowe dane pomieszczenia", str(exc), parent=window)
                return
            room_id = room["id"] if room else str(uuid4())
            old_name = room.get("name") if room else None
            updated = dict(room or {})
            updated.update({
                "id": room_id, "name": name, "length": "" if length is None else str(length), "width": "" if width is None else str(width),
                "height": str(height), "floor_area": str(q(floor_area)), "perimeter": str(q(perimeter)),
                "door_width": str(door_width), "door_area": str(door_area), "window_width": str(window_width), "window_area": str(window_area),
                "opening_area": str(q(door_area + window_area)), "walls_net": str(q(perimeter * height - door_area - window_area)),
                "baseboard": str(q(max(Decimal("0"), perimeter - door_width))),
            })
            existing = next((index for index, item in enumerate(self.state["rooms"]) if item["id"] == room_id), None)
            if existing is None:
                self.state["rooms"].append(updated)
            else:
                self.state["rooms"][existing] = updated
            if old_name and old_name != name:
                for line in self.state["lines"]:
                    if line.get("room") == old_name:
                        line["room"] = name
                floorplan = self.state.get("floorplan", {})
                mapping = self.state.get("floorplan_room_ids", {})
                linked_outline_ids = {outline_id for outline_id, linked_room_id in mapping.items() if linked_room_id == room_id}
                for outline in floorplan.get("outlines", []):
                    if outline.get("id") in linked_outline_ids:
                        outline["name"] = name
            self.mark_dirty()
            window.destroy()
            self.show_page("investment")
            self._toast(f"Zapisano pomieszczenie „{name}”.")

        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.pack(fill="x", padx=26, pady=18)
        ctk.CTkButton(buttons, text="Anuluj", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=window.destroy).pack(side="left")
        ctk.CTkButton(buttons, text="Zapisz pomieszczenie", command=save).pack(side="right")
        entries["name"].focus_set()

    def _add_rect_room(self, name: ctk.CTkEntry, length: ctk.CTkEntry, width: ctk.CTkEntry, height: ctk.CTkEntry, door: ctk.CTkEntry, openings: ctk.CTkEntry) -> None:
        n = name.get().strip()
        if not n:
            messagebox.showwarning("Pomieszczenie", "Podaj nazwę pomieszczenia.", parent=self)
            return
        try:
            l = parse_number(length.get(), "Długość", minimum=Decimal("0.01"), maximum=Decimal("1000"))
            w = parse_number(width.get(), "Szerokość", minimum=Decimal("0.01"), maximum=Decimal("1000"))
            h = parse_number(height.get(), "Wysokość", minimum=Decimal("0.1"), maximum=Decimal("20"))
            dw = parse_number(door.get() or "0", "Łączna szerokość drzwi", minimum=Decimal("0"), maximum=2 * (l + w))
            opening_area = parse_number(openings.get(), "Powierzchnia drzwi i okien", minimum=Decimal("0")) if openings.get().strip() else dw * Decimal("2.05")
        except ValueError as exc:
            messagebox.showwarning("Nieprawidłowe dane pomieszczenia", str(exc), parent=self)
            return
        perimeter = 2 * (l + w)
        if opening_area > perimeter * h:
            messagebox.showwarning("Nieprawidłowe otwory", "Powierzchnia drzwi i okien nie może być większa niż powierzchnia ścian brutto.", parent=self)
            return
        self.state["rooms"].append({"id": str(uuid4()), "name": n, "length": str(l), "width": str(w), "height": str(h), "door_width": str(dw), "opening_area": str(opening_area), "floor_area": str(q(l * w)), "perimeter": str(q(perimeter)), "walls_net": str(q(max(Decimal("0"), perimeter * h - opening_area))), "baseboard": str(q(max(Decimal("0"), perimeter - dw)))})
        self.mark_dirty()
        self.show_page("investment")

    def _remove_room(self, tree: ttk.Treeview) -> None:
        selected = tree.selection()
        if not selected:
            return
        dependent = [line for line in self.state["lines"] if line.get("room") in {room["name"] for room in self.state["rooms"] if room["id"] in selected}]
        note = f"\n\nPowiązane pozycje kosztorysu: {len(dependent)}. Pozostaną w kosztorysie jako „Bez przypisania”." if dependent else ""
        if not messagebox.askyesno("Usuń pomieszczenie", f"Usunąć {len(selected)} zaznaczone pomieszczenie(a)?{note}", parent=self):
            return
        removed_names = {room["name"] for room in self.state["rooms"] if room["id"] in selected}
        self._last_deleted_rooms = [room for room in self.state["rooms"] if room["id"] in selected]
        self.state["rooms"] = [room for room in self.state["rooms"] if room["id"] not in selected]
        for line in self.state["lines"]:
            if line.get("room") in removed_names:
                line["room"] = ""
        self.mark_dirty()
        self.show_page("investment")

    def _restore_rooms(self) -> None:
        if not self._last_deleted_rooms:
            return
        self.state["rooms"].extend(self._last_deleted_rooms)
        count = len(self._last_deleted_rooms)
        self._last_deleted_rooms = []
        self.mark_dirty()
        self.show_page("investment")
        self._toast(f"Przywrócono pomieszczenia: {count}.")

    def _page_plan(self) -> None:
        outer = ctk.CTkFrame(self.content, fg_color="transparent")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(1, weight=1)
        panel = self._card(outer, "Narzędzia")
        panel.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        panel.configure(width=245)
        project_name = self.state["project"].get("name") or "Nowa inwestycja"
        ctk.CTkLabel(panel, text=f"{tr('INWESTYCJA')}\n{project_name}", justify="left", wraplength=205, font=(FONT_FAMILY, 11, "bold"), text_color=ctk_color("accent")).pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkLabel(panel, text="1. Otwórz i skalibruj rzut\n2. Narysuj obrys główny\n3. Twórz osobne obrysy pomieszczeń\n4. Kliknij punkt 1, aby zamknąć dokładnie\n\nCtrl+rolka: zoom • środkowy: przesuń\nCtrl+Z / Ctrl+Y: cofnij / ponów", justify="left", wraplength=210, text_color=ctk_color("text_muted"), font=TYPOGRAPHY["caption"]).pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkButton(panel, text="Otwórz PDF / obraz", command=self._load_plan_background).pack(fill="x", padx=18, pady=4)
        ctk.CTkLabel(panel, text="AKTYWNY OBRYS", font=(FONT_FAMILY, 9, "bold"), text_color=ctk_color("text_muted")).pack(anchor="w", padx=18, pady=(8, 2))
        self._outline_label_to_id: dict[str, str] = {}
        self.outline_selector = ctk.CTkComboBox(panel, values=["Obrys główny"], command=self._select_plan_outline)
        self.outline_selector.pack(fill="x", padx=18, pady=(0, 4))
        outline_row = ctk.CTkFrame(panel, fg_color="transparent")
        outline_row.pack(fill="x", padx=18, pady=2)
        ctk.CTkButton(outline_row, text="＋ Główny", width=98, fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=lambda: self._new_plan_outline("main")).pack(side="left")
        ctk.CTkButton(outline_row, text="＋ Pokój", width=98, command=lambda: self._new_plan_outline("room")).pack(side="right")
        ctk.CTkButton(panel, text="Usuń aktywny obrys", height=28, fg_color="transparent", hover_color="#FEE2E2", text_color=ctk_color("error"), command=self._delete_plan_outline).pack(fill="x", padx=18, pady=(0, 4))
        mode_row = ctk.CTkFrame(panel, fg_color="transparent")
        mode_row.pack(fill="x", padx=18, pady=4)
        self.plan_draw_button = ctk.CTkButton(mode_row, text="✎ Rysuj", width=98, command=lambda: self._set_plan_mode("draw"))
        self.plan_draw_button.pack(side="left")
        self.plan_pan_button = ctk.CTkButton(mode_row, text="✥ Przesuń", width=98, fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=lambda: self._set_plan_mode("pan"))
        self.plan_pan_button.pack(side="right")
        ctk.CTkButton(panel, text="Dopasuj stronę", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=lambda: self.floor_canvas and self.floor_canvas.fit_background()).pack(fill="x", padx=18, pady=4)
        ctk.CTkButton(panel, text="Kalibruj skalę", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=lambda: self.floor_canvas and self.floor_canvas.start_calibration()).pack(fill="x", padx=18, pady=4)
        ctk.CTkButton(panel, text="Zamknij obrys", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=lambda: self.floor_canvas and self.floor_canvas.close_outline()).pack(fill="x", padx=18, pady=4)
        history = ctk.CTkFrame(panel, fg_color="transparent")
        history.pack(fill="x", padx=18, pady=4)
        ctk.CTkButton(history, text="↶ Cofnij", width=98, fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=lambda: self.floor_canvas and self.floor_canvas.undo()).pack(side="left")
        ctk.CTkButton(history, text="↷ Ponów", width=98, fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=lambda: self.floor_canvas and self.floor_canvas.redo()).pack(side="right")
        ctk.CTkButton(panel, text="Wyczyść obrys", fg_color="transparent", border_width=1, border_color=ctk_color("border"), text_color=ctk_color("error"), command=lambda: self.floor_canvas and self.floor_canvas.clear_outline()).pack(fill="x", padx=18, pady=4)
        ctk.CTkLabel(panel, text="Przezroczystość podkładu", font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", padx=18, pady=(9, 3))
        ctk.CTkSlider(panel, from_=0.1, to=0.9, number_of_steps=16, command=lambda value: self.floor_canvas and self.floor_canvas.set_opacity(value)).pack(fill="x", padx=18)
        self.plan_stats = ctk.CTkLabel(panel, text=f"{tr('Pole: ')}{display_number(0)} m²\n{tr('Obwód: ')}{display_number(0)} m", justify="left", font=(FONT_FAMILY, 15, "bold"))
        self.plan_stats.pack(anchor="w", padx=18, pady=(12, 6))
        self.plan_add_room_button = ctk.CTkButton(panel, text="Zapisz jako pomieszczenie", command=self._add_room_from_plan)
        self.plan_add_room_button.pack(fill="x", padx=18, pady=(4, 14))

        canvas_holder = self._card(outer)
        canvas_holder.grid(row=0, column=1, sticky="nsew")
        self.floor_canvas = FloorPlanCanvas(canvas_holder, on_change=self._plan_changed, on_mode_change=self._show_plan_mode)
        self.floor_canvas.pack(fill="both", expand=True, padx=1, pady=1)
        background = self.state.get("floorplan_background")
        background_path = self._resolve_attachment(background)
        if background_path and background_path.exists():
            try:
                if background_path.suffix.lower() == ".pdf":
                    self.floor_canvas.load_pdf(background_path, int(self.state.get("floorplan_page", 0)))
                else:
                    self.floor_canvas.load_image(background_path)
            except Exception:
                pass
        # Wczytanie podkładu automatycznie dopasowuje go do płótna. Stan
        # widoku musi więc zostać odtworzony później, aby zachować zoom i
        # przesunięcie ustawione przez użytkownika przy poprzednim zapisie.
        if self.state.get("floorplan"):
            self.floor_canvas.restore(self.state["floorplan"])
            self._plan_changed()
        self._refresh_outline_selector()

    def _refresh_outline_selector(self) -> None:
        if not self.floor_canvas or not hasattr(self, "outline_selector"):
            return
        labels: list[str] = []
        mapping: dict[str, str] = {}
        room_number = 0
        active_label = ""
        for outline in self.floor_canvas.outlines:
            if outline.kind == "main":
                label = f"Główny — {outline.name}"
            else:
                room_number += 1
                label = f"Pokój {room_number} — {outline.name}"
            labels.append(label)
            mapping[label] = outline.id
            if outline.id == self.floor_canvas.active_outline_id:
                active_label = label
        self._outline_label_to_id = mapping
        self.outline_selector.configure(values=labels or ["Brak obrysów"])
        self.outline_selector.set(active_label or (labels[0] if labels else "Brak obrysów"))

    def _select_plan_outline(self, label: str) -> None:
        if not self.floor_canvas:
            return
        outline_id = self._outline_label_to_id.get(label)
        if outline_id:
            self.floor_canvas.select_outline(outline_id)
            self._set_plan_mode("draw")

    def _new_plan_outline(self, kind: str) -> None:
        if not self.floor_canvas:
            return
        if kind == "room":
            dialog = ctk.CTkInputDialog(text="Nazwa pomieszczenia, np. Salon:", title="Nowy obrys pomieszczenia")
            name = (dialog.get_input() or "").strip()
            if not name:
                return
        else:
            name = "Obrys główny lokalu"
        outline_id = self.floor_canvas.start_new_outline(name, kind=kind)
        self.floor_canvas.select_outline(outline_id)
        self._set_plan_mode("draw")
        self._refresh_outline_selector()
        self._toast("Wybrano obrys główny." if kind == "main" else f"Utworzono obrys pomieszczenia „{name}”.")

    def _delete_plan_outline(self) -> None:
        if not self.floor_canvas:
            return
        outline = self.floor_canvas.active_outline
        mapping = self.state.setdefault("floorplan_room_ids", {})
        linked_room_id = mapping.get(outline.id)
        note = " Powiązane pomieszczenie i jego pomiary również zostaną usunięte." if linked_room_id else ""
        if not messagebox.askyesno("Usuń obrys", f"Usunąć obrys „{outline.name}”?{note}", parent=self):
            return
        removed_room_names = {room["name"] for room in self.state["rooms"] if room["id"] == linked_room_id}
        if linked_room_id:
            self.state["rooms"] = [room for room in self.state["rooms"] if room["id"] != linked_room_id]
            mapping.pop(outline.id, None)
            for line in self.state["lines"]:
                if line.get("room") in removed_room_names:
                    line["room"] = ""
        self.floor_canvas.delete_outline(outline.id)
        self._refresh_outline_selector()
        self.mark_dirty()

    def _set_plan_mode(self, mode: str) -> None:
        if not self.floor_canvas:
            return
        self.floor_canvas.set_mode(mode)

    def _show_plan_mode(self, mode: str) -> None:
        active, inactive = ctk_color("accent"), ctk_color("surface_alt")
        self.plan_draw_button.configure(
            fg_color=active if mode == "draw" else inactive,
            text_color="white" if mode == "draw" else ctk_color("text"),
        )
        self.plan_pan_button.configure(
            fg_color=active if mode == "pan" else inactive,
            text_color="white" if mode == "pan" else ctk_color("text"),
        )

    def _resolve_attachment(self, stored: object) -> Path | None:
        if not stored:
            return None
        path = Path(str(stored))
        if path.is_absolute() and path.exists():
            return path
        return self.data_dir / path

    def _load_plan_background(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Wybierz rzut", filetypes=[("PDF lub obraz", "*.pdf *.png *.jpg *.jpeg *.bmp"), ("PDF", "*.pdf"), ("Obrazy", "*.png *.jpg *.jpeg *.bmp")])
        if not path or not self.floor_canvas:
            return
        try:
            page_index = 0
            if Path(path).stat().st_size > 100 * 1024 * 1024:
                raise ValueError("Plik jest większy niż 100 MB. Zmniejsz PDF przed wczytaniem.")
            if Path(path).suffix.lower() == ".pdf":
                import pypdfium2 as pdfium
                probe = pdfium.PdfDocument(path)
                page_count = len(probe)
                probe.close()
                if page_count > 1:
                    selected = simpledialog.askinteger("Strona PDF", f"Dokument ma {page_count} stron. Podaj numer strony do odrysowania:", minvalue=1, maxvalue=page_count, initialvalue=1, parent=self)
                    if selected is None:
                        return
                    page_index = selected - 1
                self.floor_canvas.load_pdf(path, page_index)
            else:
                self.floor_canvas.load_image(path)
            attachments = self.data_dir / "Zalaczniki"
            attachments.mkdir(exist_ok=True)
            source_path = Path(path)
            target = attachments / f"{source_path.stem}_{uuid4().hex[:8]}{source_path.suffix.lower()}"
            if Path(path).resolve() != target.resolve():
                shutil.copy2(path, target)
            self.state["floorplan_background"] = str(target.relative_to(self.data_dir))
            self.state["floorplan_page"] = page_index
            self.mark_dirty()
        except Exception as exc:
            messagebox.showerror("Podkład", f"Nie udało się otworzyć pliku:\n{exc}", parent=self)

    def _plan_changed(self) -> None:
        if not self.floor_canvas:
            return
        outline = self.floor_canvas.active_outline
        if self.floor_canvas.closed:
            stats = f"{outline.name}\n{tr('Pole: ')}{display_number(self.floor_canvas.area_m2)} m²\n{tr('Obwód: ')}{display_number(self.floor_canvas.perimeter_m)} m"
        else:
            stats = f"{outline.name}\n{tr('Pole podglądowe: ')}{display_number(self.floor_canvas.area_m2)} m²\n{tr('Otwarty obrys: ')}{display_number(self.floor_canvas.perimeter_m)} m\n{tr('Kliknij punkt 1, aby zamknąć')}"
        self.plan_stats.configure(text=stats)
        if hasattr(self, "plan_add_room_button"):
            can_save_room = outline.kind == "room" and outline.closed
            self.plan_add_room_button.configure(state="normal" if can_save_room else "disabled")
        self.mark_dirty()

    def _add_room_from_plan(self) -> None:
        if not self.floor_canvas or not self.floor_canvas.closed:
            messagebox.showwarning("Obrys", "Najpierw zamknij obrys pomieszczenia.", parent=self)
            return
        outline = self.floor_canvas.active_outline
        if outline.kind != "room":
            messagebox.showwarning("Obrys główny", "Obrys główny opisuje cały lokal. Utwórz osobny obrys pokoju przyciskiem „+ Pokój”.", parent=self)
            return
        if self.floor_canvas.has_self_intersection or self.floor_canvas.area_m2 <= 0:
            messagebox.showwarning("Nieprawidłowy obrys", "Obrys przecina sam siebie albo ma zerowe pole. Popraw punkty przed zapisaniem pomieszczenia.", parent=self)
            return
        name = simpledialog.askstring("Zapisz pomieszczenie", "Nazwa pomieszczenia:", initialvalue=outline.name, parent=self)
        if not name:
            return
        height_dialog = ctk.CTkInputDialog(text="Wysokość w metrach:", title="Wysokość")
        try:
            height = parse_number(height_dialog.get_input(), "Wysokość", minimum=Decimal("0.1"), maximum=Decimal("20"))
        except ValueError as exc:
            messagebox.showwarning("Nieprawidłowa wysokość", str(exc), parent=self)
            return
        area = d(self.floor_canvas.area_m2)
        perimeter = d(self.floor_canvas.perimeter_m)
        mapping = self.state.setdefault("floorplan_room_ids", {})
        room_id = mapping.get(outline.id) or str(uuid4())
        old_room = next((room for room in self.state["rooms"] if room["id"] == room_id), None)
        old_name = old_room.get("name") if old_room else None
        room_data = {"id": room_id, "name": name, "height": str(height), "door_width": "0", "floor_area": str(q(area)), "perimeter": str(q(perimeter)), "walls_net": str(q(perimeter * height)), "baseboard": str(q(perimeter)), "points": [[str(q(d(x) * d(self.floor_canvas.meters_per_pixel))), str(q(d(y) * d(self.floor_canvas.meters_per_pixel)))] for x, y in self.floor_canvas.points]}
        existing = next((i for i, room in enumerate(self.state["rooms"]) if room["id"] == room_id), None)
        if existing is None:
            self.state["rooms"].append(room_data)
        else:
            self.state["rooms"][existing] = room_data
        mapping[outline.id] = room_id
        self.floor_canvas.rename_outline(outline.id, name)
        if old_name and old_name != name:
            for line in self.state["lines"]:
                if line.get("room") == old_name:
                    line["room"] = name
        self._refresh_outline_selector()
        self.mark_dirty()
        self._toast(f"Zapisano pomieszczenie „{name}”.")

    def _page_estimate(self) -> None:
        outer = ctk.CTkFrame(self.content, fg_color="transparent")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.grid_rowconfigure(2, weight=1)
        outer.grid_columnconfigure(0, weight=1)
        room_summary = self._card(outer, "Rozkład pomieszczeń projektu")
        room_summary.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        if self.state["rooms"]:
            room_parts = [f"{room['name']}  {display_number(room.get('floor_area', 0))} m²" for room in self.state["rooms"]]
            total_area = sum((d(room.get("floor_area", 0)) for room in self.state["rooms"]), Decimal("0"))
            summary_text = "   •   ".join(room_parts) + f"     |     RAZEM  {display_number(total_area)} m²"
        else:
            summary_text = "Brak pomieszczeń. Dodaj je w widoku Inwestycja lub Rzut i obmiary."
        ctk.CTkLabel(room_summary, text=summary_text, justify="left", anchor="w", wraplength=1450, font=(FONT_FAMILY, 12, "bold"), text_color=ctk_color("text")).pack(fill="x", padx=20, pady=(0, 14))
        toolbar = ctk.CTkFrame(outer, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        ctk.CTkButton(toolbar, text="＋ Dodaj z cennika", command=self._open_add_line).pack(side="left")
        ctk.CTkButton(toolbar, text="Edytuj zaznaczoną", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=lambda: self._edit_estimate_line(tree)).pack(side="left", padx=8)
        ctk.CTkButton(toolbar, text="Przypisz pomieszczenie", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=lambda: self._assign_lines_to_room(tree)).pack(side="left")
        ctk.CTkButton(toolbar, text="Usuń zaznaczone", fg_color=ctk_color("surface_alt"), hover_color="#FEE2E2", text_color=ctk_color("error"), command=lambda: self._remove_line(tree)).pack(side="left", padx=8)
        ctk.CTkButton(toolbar, text="Dodaj dojazd", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=self._open_travel).pack(side="left", padx=8)
        ctk.CTkButton(toolbar, text="Eksport Excel", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=self.export_xlsx).pack(side="left")
        ctk.CTkButton(toolbar, text="Utwórz rewizję", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=self._create_revision).pack(side="left", padx=8)
        ctk.CTkButton(toolbar, text="Historia rewizji", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=self._show_revisions).pack(side="left")

        card = self._card(outer)
        card.grid(row=2, column=0, sticky="nsew")
        card.grid_rowconfigure(0, weight=1)
        card.grid_columnconfigure(0, weight=1)
        columns = ("room", "name", "qty", "unit", "labor", "material", "net", "vat", "included")
        tree = ttk.Treeview(card, columns=columns, show="headings")
        specs = [("room", "Pomieszczenie", 125), ("name", "Praca / materiał", 250), ("qty", "Ilość", 75), ("unit", "Jednostka", 75), ("labor", "Robocizna", 95), ("material", "Materiał", 95), ("net", "Wartość", 105), ("vat", "VAT", 55), ("included", "Zakres", 70)]
        for col, label, width in specs:
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w" if col in {"room", "name"} else "e")
        for line in self.state["lines"]:
            tree.insert("", "end", iid=line["id"], values=(line.get("room", "") or "Bez przypisania", line["name"], display_number(line["quantity"]), line["unit"], self._money(line.get("labor_net", line.get("unit_price", 0))), self._money(line.get("material_net", 0)), self._money(line["net"]), f"{display_number(line.get('vat_rate', 23), 0)}%", "W cenie" if line.get("included", True) else "Opcja"))
        tree.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        scrollbar = ttk.Scrollbar(card, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)
        tree.bind("<Double-1>", lambda _e: self._edit_estimate_line(tree))
        tree.bind("<Delete>", lambda _e: self._remove_line(tree))
        footer = ctk.CTkFrame(outer, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        ctk.CTkButton(footer, text="Usuń zaznaczone", width=145, fg_color="transparent", border_width=1, border_color=ctk_color("border"), text_color=ctk_color("error"), command=lambda: self._remove_line(tree)).pack(side="left")
        ctk.CTkButton(footer, text="Przywróć usunięte", width=150, state="normal" if self._last_deleted_lines else "disabled", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=self._restore_lines).pack(side="left", padx=8)
        totals = self._calculate_totals()
        summary = self._card(footer)
        summary.pack(side="right")
        ctk.CTkLabel(summary, text=f"{tr('Netto')}  {self._money(totals['net'])}", font=(FONT_FAMILY, 11), text_color=ctk_color("text_muted")).pack(side="left", padx=(18, 10), pady=13)
        ctk.CTkLabel(summary, text=f"VAT  {self._money(totals['vat'])}", font=(FONT_FAMILY, 11), text_color=ctk_color("text_muted")).pack(side="left", padx=10)
        ctk.CTkLabel(summary, text=f"{tr('Brutto')}  {self._money(totals['gross'])}", font=(FONT_FAMILY, 15, "bold"), text_color=ctk_color("accent")).pack(side="left", padx=(10, 18))

    def _open_add_line(self) -> None:
        if not self.prices:
            messagebox.showwarning("Cennik", "Cennik jest pusty. Najpierw zaimportuj lub utwórz cennik.", parent=self)
            return
        window = ctk.CTkToplevel(self)
        window.title("Dodaj pozycję")
        window.geometry("980x650")
        window.transient(self)
        window.grab_set()
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(window, text="Dodaj pozycję z cennika", font=TYPOGRAPHY["title"]).grid(row=0, column=0, sticky="w", padx=24, pady=(22, 12))
        search_var = tk.StringVar()
        search = ctk.CTkEntry(window, textvariable=search_var, placeholder_text="Szukaj po nazwie, kodzie lub kategorii…", height=38)
        search.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))
        tree = ttk.Treeview(window, columns=("code", "category", "name", "unit", "labor", "material"), show="headings")
        for col, label, width in (("code", "Kod", 105), ("category", "Kategoria", 150), ("name", "Nazwa", 300), ("unit", "J.m.", 70), ("labor", "Robocizna", 105), ("material", "Materiał", 105)):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w" if col in {"code", "category", "name"} else "e")
        tree.grid(row=2, column=0, sticky="nsew", padx=24)

        def populate(*_args: object) -> None:
            tree.delete(*tree.get_children())
            needle = search_var.get().casefold()
            for item in self.prices:
                if item.active and (not needle or needle in f"{item.code} {item.category} {item.name}".casefold()):
                    tree.insert("", "end", iid=item.code, values=(item.code, item.category, item.name, item.unit, self._money(item.labor_net), self._money(item.material_net)))

        search_var.trace_add("write", populate)
        populate()
        options = ctk.CTkFrame(window, fg_color="transparent")
        options.grid(row=3, column=0, sticky="ew", padx=24, pady=15)
        room_values = ["Bez przypisania"] + [r["name"] for r in self.state["rooms"]]
        room = ctk.CTkComboBox(options, values=room_values, width=185)
        room.set(room_values[0])
        room.pack(side="left", padx=(0, 8))
        source = ctk.CTkComboBox(options, values=["Własna ilość", "Podłoga", "Ściany", "Sufit", "Listwy"], width=145)
        source.set("Własna ilość")
        source.pack(side="left", padx=4)
        quantity = ctk.CTkEntry(options, placeholder_text="Ilość", width=95)
        quantity.insert(0, "1")
        quantity.pack(side="left", padx=4)
        waste = ctk.CTkEntry(options, placeholder_text="Odpad %", width=95)
        waste.pack(side="left", padx=4)
        difficulty = ctk.CTkEntry(options, placeholder_text="Trudność", width=95)
        difficulty.insert(0, "1,00")
        difficulty.pack(side="left", padx=4)

        def update_quantity(*_args: object) -> None:
            selected_room = next((r for r in self.state["rooms"] if r["name"] == room.get()), None)
            mapping = {"Podłoga": "floor_area", "Ściany": "walls_net", "Sufit": "floor_area", "Listwy": "baseboard"}
            if selected_room and source.get() in mapping:
                quantity.delete(0, "end")
                quantity.insert(0, display_number(selected_room[mapping[source.get()]]))
        room.configure(command=lambda _v: update_quantity())
        source.configure(command=lambda _v: update_quantity())

        def add() -> None:
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("Pozycja", "Wybierz pozycję z tabeli.", parent=window)
                return
            item = next(x for x in self.prices if x.code == selection[0])
            try:
                qty = parse_number(quantity.get(), "Ilość", minimum=Decimal("0.0001"), maximum=Decimal("10000000"))
                waste_pct = parse_number(waste.get() or item.waste_pct, "Odpad", minimum=Decimal("0"), maximum=Decimal("100"))
                diff = parse_number(difficulty.get(), "Mnożnik trudności", minimum=Decimal("0.01"), maximum=Decimal("100"))
            except ValueError as exc:
                messagebox.showwarning("Nieprawidłowe dane pozycji", str(exc), parent=window)
                return
            labor_price, material_price = d(item.labor_net), d(item.material_net)
            unit_price = labor_price + material_price
            labor_total = qty * labor_price * diff
            material_total = qty * (Decimal("1") + waste_pct / 100) * material_price * diff
            total = max(d(item.min_charge), labor_total + material_total)
            formula = f"robocizna: {display_number(qty)} {item.unit} × {self._money(labor_price)}; materiał: {display_number(qty)} {item.unit} × {self._money(material_price)}"
            if waste_pct:
                formula += f" + {display_number(waste_pct)}% odpadu materiałowego"
            if diff != 1:
                formula += f" × trudność {display_number(diff)}"
            self.state["lines"].append({"id": str(uuid4()), "code": item.code, "room": "" if room.get() == "Bez przypisania" else room.get(), "name": item.name, "quantity": str(qty), "unit": item.unit, "labor_net": str(q(d(item.labor_net))), "material_net": str(q(d(item.material_net))), "unit_price": str(q(unit_price)), "waste_pct": str(waste_pct), "difficulty": str(diff), "net": str(q(total)), "vat_rate": item.vat_rate, "included": True, "formula": formula})
            self.mark_dirty()
            window.destroy()
            self.show_page("estimate")
        ctk.CTkButton(options, text="Dodaj do kosztorysu", width=175, command=add).pack(side="right")

    def _remove_line(self, tree: ttk.Treeview) -> None:
        selected = set(tree.selection())
        if not selected:
            messagebox.showinfo("Kosztorys", "Najpierw zaznacz pozycję do usunięcia.", parent=self)
            return
        if not messagebox.askyesno("Usuń pozycje", f"Usunąć {len(selected)} zaznaczone pozycje kosztorysu?", parent=self):
            return
        self._last_deleted_lines = [line for line in self.state["lines"] if line["id"] in selected]
        self.state["lines"] = [line for line in self.state["lines"] if line["id"] not in selected]
        self.mark_dirty()
        self.show_page("estimate")

    def _restore_lines(self) -> None:
        if self._last_deleted_lines:
            self.state["lines"].extend(self._last_deleted_lines)
            self._last_deleted_lines = []
            self.mark_dirty()
            self.show_page("estimate")

    def _assign_lines_to_room(self, tree: ttk.Treeview) -> None:
        selected = set(tree.selection())
        if not selected:
            messagebox.showinfo("Kosztorys", "Najpierw zaznacz jedną lub kilka pozycji.", parent=self)
            return
        room_values = ["Bez przypisania"] + [room["name"] for room in self.state["rooms"]]
        window = ctk.CTkToplevel(self)
        window.title("Przypisz pomieszczenie")
        window.geometry("470x230")
        window.transient(self)
        window.grab_set()
        window.bind("<Escape>", lambda _e: window.destroy())
        ctk.CTkLabel(window, text=f"{tr('Przypisz')} {len(selected)} {tr('zaznaczone pozycje')}", font=TYPOGRAPHY["title"]).pack(anchor="w", padx=24, pady=(24, 8))
        ctk.CTkLabel(window, text="Wybierz pomieszczenie albo usuń przypisanie.", text_color=ctk_color("text_muted")).pack(anchor="w", padx=24, pady=(0, 12))
        room = ctk.CTkComboBox(window, values=room_values, width=420)
        room.set(room_values[0])
        room.pack(fill="x", padx=24)

        def assign() -> None:
            target = "" if room.get() == "Bez przypisania" else room.get()
            for line in self.state["lines"]:
                if line["id"] in selected:
                    line["room"] = target
            self.mark_dirty()
            window.destroy()
            self.show_page("estimate")
            self._toast(f"Przypisano pozycje: {len(selected)}.")

        ctk.CTkButton(window, text="Zapisz przypisanie", command=assign).pack(fill="x", padx=24, pady=20)

    def _edit_estimate_line(self, tree: ttk.Treeview) -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Kosztorys", "Najpierw zaznacz pozycję.", parent=self)
            return
        line = next((row for row in self.state["lines"] if row["id"] == selected[0]), None)
        if not line or line.get("code") == "DOJAZD":
            messagebox.showinfo("Kosztorys", "Dojazd edytuj przyciskiem „Dodaj dojazd”.", parent=self)
            return
        window = ctk.CTkToplevel(self)
        window.title("Edytuj pozycję kosztorysu")
        window.geometry("560x510")
        window.transient(self)
        window.grab_set()
        room_values = ["Bez przypisania"] + [room["name"] for room in self.state["rooms"]]
        room_row = ctk.CTkFrame(window, fg_color="transparent")
        room_row.pack(fill="x", padx=24, pady=(18, 5))
        ctk.CTkLabel(room_row, text="Pomieszczenie", width=285, anchor="w").pack(side="left")
        room_choice = ctk.CTkComboBox(room_row, values=room_values, width=190)
        current_room = line.get("room", "") or "Bez przypisania"
        room_choice.set(current_room if current_room in room_values else "Bez przypisania")
        room_choice.pack(side="right")
        fields: dict[str, ctk.CTkEntry] = {}
        for key, label, value in (("quantity", "Ilość", line.get("quantity", 1)), ("labor_net", "Robocizna netto / jednostkę", line.get("labor_net", line.get("unit_price", 0))), ("material_net", "Materiał netto / jednostkę", line.get("material_net", 0)), ("waste_pct", "Odpad [%]", line.get("waste_pct", 0)), ("difficulty", "Mnożnik trudności", line.get("difficulty", 1)), ("vat_rate", "VAT [%]", line.get("vat_rate", 23))):
            row = ctk.CTkFrame(window, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=5)
            ctk.CTkLabel(row, text=label, width=285, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=190)
            entry.insert(0, display_number(value))
            entry.pack(side="right")
            fields[key] = entry
        included = tk.BooleanVar(value=line.get("included", True))
        ctk.CTkCheckBox(window, text="Uwzględnij w sumie oferty", variable=included).pack(anchor="w", padx=24, pady=10)

        def save() -> None:
            try:
                qty = parse_number(fields["quantity"].get(), "Ilość", minimum=Decimal("0.0001"))
                labor = parse_number(fields["labor_net"].get(), "Robocizna", minimum=Decimal("0"))
                material = parse_number(fields["material_net"].get(), "Materiał", minimum=Decimal("0"))
                waste = parse_number(fields["waste_pct"].get(), "Odpad", minimum=Decimal("0"), maximum=Decimal("100"))
                difficulty = parse_number(fields["difficulty"].get(), "Mnożnik trudności", minimum=Decimal("0.01"), maximum=Decimal("100"))
                vat = parse_number(fields["vat_rate"].get(), "VAT", minimum=Decimal("0"), maximum=Decimal("100"))
            except ValueError as exc:
                messagebox.showwarning("Nieprawidłowe dane", str(exc), parent=window)
                return
            unit_price = labor + material
            total = (qty * labor + qty * (Decimal("1") + waste / 100) * material) * difficulty
            selected_room = "" if room_choice.get() == "Bez przypisania" else room_choice.get()
            line.update(room=selected_room, quantity=str(qty), labor_net=str(q(labor)), material_net=str(q(material)), unit_price=str(q(unit_price)), waste_pct=str(waste), difficulty=str(difficulty), vat_rate=float(vat), included=included.get(), net=str(q(total)), formula=f"robocizna: {display_number(qty)} × {self._money(labor)}; materiał: {display_number(qty)} × {self._money(material)} + {display_number(waste)}% odpadu; trudność × {display_number(difficulty)}")
            self.mark_dirty()
            window.destroy()
            self.show_page("estimate")

        ctk.CTkButton(window, text="Zapisz zmiany", command=save).pack(fill="x", padx=24, pady=20)

    def _open_travel(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("Koszt dojazdu")
        window.geometry("560x525")
        window.transient(self)
        window.grab_set()
        ctk.CTkLabel(window, text="Dojazd — dane ręczne", font=TYPOGRAPHY["title"]).pack(anchor="w", padx=24, pady=(22, 5))
        ctk.CTkLabel(window, text="Moduł działa całkowicie offline. Podaj rzeczywisty dystans i liczbę wizyt.", text_color=ctk_color("text_muted"), wraplength=500, justify="left").pack(anchor="w", padx=24, pady=(0, 15))
        values: dict[str, ctk.CTkEntry] = {}
        labels = [("one_way_km", "Dystans w jedną stronę [km]"), ("visits", "Liczba wizyt [całkowita]"), ("rate", "Stawka netto za 1 km"), ("free_km", "Bezpłatny dystans na jedną trasę [km]"), ("parking", "Parking i opłaty dla całego projektu")]
        for key, label in labels:
            row = ctk.CTkFrame(window, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=5)
            ctk.CTkLabel(row, text=label, width=285, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=190)
            entry.insert(0, display_number(self.state["travel"].get(key, 0)))
            entry.pack(side="right")
            values[key] = entry
        round_var = tk.BooleanVar(value=bool(self.state["travel"].get("round_trip", True)))
        included_var = tk.BooleanVar(value=bool(self.state["travel"].get("included", False)))
        ctk.CTkCheckBox(window, text="Licz trasę w obie strony", variable=round_var).pack(anchor="w", padx=24, pady=(12, 4))
        ctk.CTkCheckBox(window, text="Dodaj koszt do kosztorysu", variable=included_var).pack(anchor="w", padx=24, pady=4)

        def save() -> None:
            try:
                parsed = {
                    "one_way_km": parse_number(values["one_way_km"].get(), "Dystans", minimum=Decimal("0"), maximum=Decimal("100000")),
                    "visits": parse_number(values["visits"].get(), "Liczba wizyt", minimum=Decimal("0"), maximum=Decimal("100000"), integer=True),
                    "rate": parse_number(values["rate"].get(), "Stawka za kilometr", minimum=Decimal("0"), maximum=Decimal("100000")),
                    "free_km": parse_number(values["free_km"].get(), "Bezpłatny dystans", minimum=Decimal("0"), maximum=Decimal("100000")),
                    "parking": parse_number(values["parking"].get(), "Parking i opłaty", minimum=Decimal("0"), maximum=Decimal("100000000")),
                }
            except ValueError as exc:
                messagebox.showwarning("Nieprawidłowe dane dojazdu", str(exc), parent=window)
                return
            for key, value in parsed.items():
                self.state["travel"][key] = str(value)
            self.state["travel"]["round_trip"] = round_var.get()
            self.state["travel"]["included"] = included_var.get()
            self._sync_travel_line()
            self.mark_dirty()
            window.destroy()
            self.show_page("estimate")
        ctk.CTkButton(window, text="Zapisz koszt dojazdu", command=save).pack(fill="x", padx=24, pady=22)

    def _sync_travel_line(self) -> None:
        self.state["lines"] = [line for line in self.state["lines"] if line.get("code") != "DOJAZD"]
        travel = self.state["travel"]
        if not travel.get("included"):
            return
        multiplier = Decimal("2") if travel.get("round_trip") else Decimal("1")
        paid_km = max(Decimal("0"), d(travel["one_way_km"]) - d(travel["free_km"])) * multiplier
        all_km = paid_km * d(travel["visits"])
        total = all_km * d(travel["rate"]) + d(travel["parking"])
        self.state["lines"].append({"id": str(uuid4()), "code": "DOJAZD", "room": "Inwestycja", "name": "Dojazdy, parking i opłaty", "quantity": str(q(all_km)), "unit": "km", "unit_price": str(q(d(travel["rate"]))), "net": str(q(total)), "vat_rate": 23, "included": True, "formula": f"{display_number(all_km)} km × {self._money(travel['rate'])} + opłaty {self._money(travel['parking'])}"})

    def _calculate_totals(self) -> dict[str, Decimal]:
        included = [line for line in self.state["lines"] if line.get("included", True)]
        base = sum((d(line.get("net")) for line in included), Decimal("0"))
        markup = q(base * d(self.state["project"].get("markup_pct")) / 100)
        discount = q((base + markup) * d(self.state["project"].get("discount_pct")) / 100)
        net = q(base + markup - discount)
        factor = (Decimal("1") + d(self.state["project"].get("markup_pct")) / 100) * (Decimal("1") - d(self.state["project"].get("discount_pct")) / 100)
        vat = q(sum((d(line.get("net")) * d(line.get("vat_rate", 23)) / 100 for line in included), Decimal("0")) * factor)
        return {"base": q(base), "markup": markup, "discount": discount, "net": net, "vat": vat, "gross": net + vat}

    def _page_prices(self) -> None:
        outer = ctk.CTkFrame(self.content, fg_color="transparent")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)
        toolbar = ctk.CTkFrame(outer, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ctk.CTkButton(toolbar, text="＋ Dodaj usługę", command=lambda: self._open_price_editor()).pack(side="left")
        ctk.CTkButton(toolbar, text="Edytuj zaznaczoną", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=lambda: self._edit_price(tree)).pack(side="left", padx=8)
        ctk.CTkButton(toolbar, text="Importuj Excel", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=self._import_prices).pack(side="left")
        ctk.CTkButton(toolbar, text="Eksportuj do Excela", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=self._export_prices).pack(side="left", padx=8)
        ctk.CTkLabel(toolbar, text=f"{len(self.prices)} pozycji • kliknij dwukrotnie, aby edytować cenę", text_color=ctk_color("text_muted")).pack(side="right")
        card = self._card(outer)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_rowconfigure(0, weight=1)
        card.grid_columnconfigure(0, weight=1)
        tree = ttk.Treeview(card, columns=("code", "category", "name", "unit", "labor", "material", "vat", "waste"), show="headings")
        for col, label, width in (("code", "Kod", 105), ("category", "Kategoria", 145), ("name", "Nazwa", 300), ("unit", "J.m.", 65), ("labor", "Robocizna", 105), ("material", "Materiał", 105), ("vat", "VAT", 65), ("waste", "Odpad", 75)):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w" if col in {"code", "category", "name"} else "e")
        for item in self.prices:
            tree.insert("", "end", iid=item.code, values=(item.code, item.category, item.name, item.unit, self._money(item.labor_net), self._money(item.material_net), f"{display_number(item.vat_rate, 0)}%", f"{display_number(item.waste_pct, 0)}%"))
        tree.grid(row=0, column=0, sticky="nsew")
        tree.bind("<Double-1>", lambda _e: self._edit_price(tree))
        scrollbar = ttk.Scrollbar(card, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)
        actions = ctk.CTkFrame(outer, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ctk.CTkButton(actions, text="Przywróć usuniętą", width=150, state="normal" if self._last_deleted_prices else "disabled", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=self._restore_price).pack(side="left")
        ctk.CTkButton(actions, text="Usuń zaznaczoną", width=150, fg_color="transparent", border_width=1, border_color=ctk_color("border"), text_color=ctk_color("error"), command=lambda: self._remove_price(tree)).pack(side="right")

    def _edit_price(self, tree: ttk.Treeview) -> None:
        selected = tree.selection()
        if not selected:
            return
        item = next(item for item in self.prices if item.code == selected[0])
        self._open_price_editor(item)

    def _open_price_editor(self, item: PriceItem | None = None) -> None:
        window = ctk.CTkToplevel(self)
        window.title("Edytuj usługę" if item else "Dodaj usługę")
        window.geometry("620x690")
        window.transient(self)
        window.grab_set()
        window.bind("<Escape>", lambda _e: window.destroy())
        ctk.CTkLabel(window, text="Edytuj usługę i ceny" if item else "Nowa usługa w cenniku", font=TYPOGRAPHY["title"]).pack(anchor="w", padx=24, pady=(22, 6))
        ctk.CTkLabel(window, text="Kwoty podawaj netto. Przecinek i kropka są akceptowane.", text_color=ctk_color("text_muted")).pack(anchor="w", padx=24, pady=(0, 12))
        entries: dict[str, ctk.CTkEntry] = {}
        values = {
            "code": item.code if item else "",
            "category": item.category if item else "",
            "name": item.name if item else "",
            "unit": item.unit if item else "m²",
            "labor_net": item.labor_net if item else 0,
            "material_net": item.material_net if item else 0,
            "vat_rate": item.vat_rate if item else 23,
            "waste_pct": item.waste_pct if item else 0,
            "min_charge": item.min_charge if item else 0,
            "notes": item.notes if item else "",
        }
        fields = (("code", "Kod (A-Z, 0-9, _ lub -)"), ("category", "Kategoria"), ("name", "Nazwa usługi"), ("unit", "Jednostka (np. m², mb, szt.)"), ("labor_net", "Robocizna netto"), ("material_net", "Materiał netto"), ("vat_rate", "VAT [%]"), ("waste_pct", "Domyślny odpad [%]"), ("min_charge", "Minimalna wartość netto"), ("notes", "Notatki"))
        for key, label in fields:
            row = ctk.CTkFrame(window, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=3)
            ctk.CTkLabel(row, text=label, width=270, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=285)
            value = values[key]
            entry.insert(0, display_number(value) if key in {"labor_net", "material_net", "vat_rate", "waste_pct", "min_charge"} else str(value))
            entry.pack(side="right")
            entries[key] = entry
        active_var = tk.BooleanVar(value=item.active if item else True)
        ctk.CTkCheckBox(window, text="Usługa aktywna i widoczna przy dodawaniu do kosztorysu", variable=active_var).pack(anchor="w", padx=24, pady=(10, 4))
        def save() -> None:
            code = entries["code"].get().strip().upper()
            category, name, unit = entries["category"].get().strip(), entries["name"].get().strip(), entries["unit"].get().strip()
            if not code or len(code) < 2 or len(code) > 40 or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in code):
                messagebox.showwarning("Nieprawidłowy kod", "Kod musi mieć 2–40 znaków i może zawierać tylko A-Z, 0-9, _ oraz -.", parent=window)
                return
            if any(existing.code == code and existing is not item for existing in self.prices):
                messagebox.showwarning("Duplikat kodu", f"Kod „{code}” już istnieje w cenniku.", parent=window)
                return
            if not category or not name or not unit:
                messagebox.showwarning("Brak wymaganych danych", "Uzupełnij kategorię, nazwę i jednostkę.", parent=window)
                return
            if unit not in ALLOWED_UNITS:
                messagebox.showwarning("Nieprawidłowa jednostka", "Dozwolone jednostki: " + ", ".join(sorted(ALLOWED_UNITS)), parent=window)
                return
            try:
                labor = parse_number(entries["labor_net"].get(), "Robocizna netto", minimum=Decimal("0"), maximum=Decimal("10000000"))
                material = parse_number(entries["material_net"].get(), "Materiał netto", minimum=Decimal("0"), maximum=Decimal("10000000"))
                vat = parse_number(entries["vat_rate"].get(), "VAT", minimum=Decimal("0"), maximum=Decimal("100"))
                waste = parse_number(entries["waste_pct"].get(), "Odpad", minimum=Decimal("0"), maximum=Decimal("100"))
                minimum = parse_number(entries["min_charge"].get(), "Minimalna wartość", minimum=Decimal("0"), maximum=Decimal("100000000"))
            except ValueError as exc:
                messagebox.showwarning("Nieprawidłowe dane", str(exc), parent=window)
                return
            replacement = PriceItem(code=code, category=category, name=name, unit=unit, labor_net=float(labor), material_net=float(material), vat_rate=float(vat), waste_pct=float(waste), min_charge=float(minimum), active=active_var.get(), notes=entries["notes"].get().strip())
            if item:
                index = next(i for i, existing in enumerate(self.prices) if existing is item)
                self.prices[index] = replacement
            else:
                self.prices.append(replacement)
            self.mark_dirty()
            window.destroy()
            self.show_page("prices")
        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.pack(fill="x", padx=24, pady=20)
        ctk.CTkButton(buttons, text="Anuluj", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=window.destroy).pack(side="left")
        ctk.CTkButton(buttons, text="Zapisz usługę", command=save).pack(side="right")
        entries["code"].focus_set()

    def _remove_price(self, tree: ttk.Treeview) -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Cennik", "Najpierw zaznacz usługę w tabeli.", parent=self)
            return
        if not messagebox.askyesno("Usuń usługę", f"Usunąć usługę {selected[0]} z cennika? Istniejące pozycje kosztorysu pozostaną bez zmian.", parent=self):
            return
        self._last_deleted_prices = [item for item in self.prices if item.code == selected[0]]
        self.prices = [item for item in self.prices if item.code != selected[0]]
        self.mark_dirty()
        self.show_page("prices")

    def _restore_price(self) -> None:
        if self._last_deleted_prices:
            self.prices.extend(self._last_deleted_prices)
            self._last_deleted_prices = []
            self.mark_dirty()
            self.show_page("prices")

    def _import_prices(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Importuj cennik", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        try:
            result = import_pricelist_xlsx(path)
            if not messagebox.askyesno("Import cennika", f"Poprawnie odczytano {len(result.items)} pozycji.\n\nZastąpić obecny cennik?", parent=self):
                return
            self.prices = result.items
            self.mark_dirty()
            self._save_state(quiet=True)
            self.show_page("prices")
            self._toast("Zaimportowano nową wersję cennika.")
        except PricelistValidationError as exc:
            messagebox.showerror("Błędy w cenniku", str(exc)[:4000], parent=self)
        except Exception as exc:
            messagebox.showerror("Import cennika", f"Nie udało się odczytać pliku:\n{exc}", parent=self)

    def _export_prices(self) -> None:
        initial = self.export_dir / ("Price_list_editable.xlsx" if self.language == "en" else "Cennik_do_edycji.xlsx")
        path = filedialog.asksaveasfilename(parent=self, title="Zapisz cennik", initialfile=initial.name, initialdir=str(initial.parent), defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            create_template_xlsx(path, self.prices, {"pricelist_name": "My price list" if self.language == "en" else "Mój cennik", "version": date.today().isoformat(), "currency": self.state["project"].get("currency", "PLN")}, language=self.language)
            self._toast("Cennik Excel został zapisany.")

    def _page_settings(self) -> None:
        page = self._scroll_page()
        language_card = self._card(page, "Język aplikacji")
        language_card.grid(row=0, column=0, sticky="ew")
        language_body = ctk.CTkFrame(language_card, fg_color="transparent")
        language_body.pack(fill="x", padx=20, pady=(0, 18))
        ctk.CTkLabel(
            language_body,
            text="Wybierz język interfejsu i dokumentów eksportowanych.",
            text_color=ctk_color("text_muted"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        language_box = ctk.CTkComboBox(
            language_body,
            values=list(SUPPORTED_LANGUAGES.values()),
            width=170,
            state="readonly",
            command=self._change_language,
        )
        language_box.set(SUPPORTED_LANGUAGES.get(self.language, "English"))
        language_box.pack(side="right")

        company = self._card(page, "Dane wykonawcy")
        company.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        body = ctk.CTkFrame(company, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=(0, 16))
        body.grid_columnconfigure((0, 1), weight=1)
        self._field(body, "Nazwa firmy", "company_name", 0, 0)
        self._field(body, "Dane kontaktowe / NIP", "company_details", 0, 1)

        finance = self._card(page, "Reguły oferty")
        finance.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        fbody = ctk.CTkFrame(finance, fg_color="transparent")
        fbody.pack(fill="x", padx=12, pady=(0, 16))
        fbody.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self._field(fbody, "Narzut od kosztu [%]", "markup_pct", 0, 0)
        self._field(fbody, "Rabat po naliczeniu narzutu [%]", "discount_pct", 0, 1)
        self._field(fbody, "Ważność oferty [dni]", "valid_days", 0, 2)
        currency_cell = ctk.CTkFrame(fbody, fg_color="transparent")
        currency_cell.grid(row=0, column=3, rowspan=2, sticky="nsew", padx=8, pady=(7, 7))
        ctk.CTkLabel(currency_cell, text="Waluta wyceny", font=(FONT_FAMILY, 10, "bold"), text_color=ctk_color("text_muted"), anchor="w").pack(fill="x", pady=(0, 3))
        currency_box = ctk.CTkComboBox(currency_cell, values=list(SUPPORTED_CURRENCIES), state="readonly", command=self._change_currency)
        currency_box.set(normalize_currency(self.state["project"].get("currency")))
        currency_box.pack(fill="x")

        notes = self._card(page, "Domyślne założenia i wyłączenia")
        notes.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        textbox = ctk.CTkTextbox(notes, height=165, font=(FONT_FAMILY, 11), wrap="word")
        textbox.insert("1.0", self.state["project"].get("assumptions", ""))
        textbox.pack(fill="x", padx=20, pady=(0, 10))
        def save_notes() -> None:
            self.state["project"]["assumptions"] = textbox.get("1.0", "end").strip()
            self.mark_dirty()
            self._save_state()
        ctk.CTkButton(notes, text="Zapisz ustawienia", command=save_notes).pack(anchor="e", padx=20, pady=(0, 18))

        backup = self._card(page, "Kopie zapasowe")
        backup.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        ctk.CTkLabel(backup, text="Baza oraz bieżący projekt są zapisywane lokalnie. Utwórz dodatkową kopię przed większą zmianą cennika.", text_color=ctk_color("text_muted"), anchor="w").pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkButton(backup, text="Utwórz kopię teraz", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=self._backup).pack(anchor="w", padx=20, pady=(0, 18))
        ctk.CTkButton(backup, text="Przywróć kopię…", fg_color=ctk_color("surface_alt"), hover_color=ctk_color("surface_hover"), text_color=ctk_color("text"), command=self._restore_backup).pack(anchor="w", padx=20, pady=(0, 18))

    def _change_language(self, display_name: str) -> None:
        language = next((code for code, name in SUPPORTED_LANGUAGES.items() if name == display_name), "en")
        if language == self.language:
            return
        if self.floor_canvas:
            self.state["floorplan"] = self.floor_canvas.serialize()
        self._switch_demo_pricelist_language(language)
        self.language = language
        self.state["language"] = language
        set_language(language)
        self.mark_dirty()
        self._save_state(quiet=True)
        self.floor_canvas = None
        for child in self.winfo_children():
            child.destroy()
        self._build_interface()

    def _change_currency(self, currency: str) -> None:
        selected = normalize_currency(currency)
        previous = normalize_currency(self.state["project"].get("currency"))
        if selected == previous:
            return
        old_labels = {previous}
        if previous == "PLN":
            old_labels.add("zł")
        new_label = "zł" if selected == "PLN" and self.language == "pl" else selected
        for line in self.state.get("lines", []):
            formula = str(line.get("formula", ""))
            for old_label in old_labels:
                formula = re.sub(rf"(?<!\w){re.escape(old_label)}(?!\w)", new_label, formula)
            line["formula"] = formula
        self.state["project"]["currency"] = selected
        self.mark_dirty()
        self._save_state(quiet=True)
        self.show_page(self.current_page)

    def _backup(self) -> None:
        self._save_state(quiet=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = self.backup_dir / f"Kopia_{stamp}"
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.data_dir, folder / "Dane", dirs_exist_ok=True)
        self.db.backup(folder / "Dane" / "calcelyx.sqlite3")
        self._toast(f"Utworzono kopię: {folder.name}")

    def _restore_backup(self) -> None:
        folder = filedialog.askdirectory(parent=self, title="Wybierz folder kopii", initialdir=str(self.backup_dir))
        if not folder:
            return
        source = Path(folder) / "Dane"
        state_source = source / "projekt_biezacy.json"
        if not state_source.exists():
            messagebox.showerror("Przywracanie kopii", "Wybrany folder nie zawiera kompletnej kopii Calcelyx.", parent=self)
            return
        if not messagebox.askyesno("Przywróć kopię", "Bieżące dane zostaną najpierw zapisane, a następnie zastąpione zawartością kopii. Kontynuować?", parent=self):
            return
        self._save_state(quiet=True)
        safety = self.backup_dir / f"Przed_odtworzeniem_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copytree(self.data_dir, safety / "Dane", dirs_exist_ok=True)
        # Odtwarzamy dokładną migawkę. Kopia bezpieczeństwa powyżej pozwala
        # wrócić do danych sprzed tej operacji, także gdy zawierały nowsze pliki.
        for child in self.data_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        shutil.copytree(source, self.data_dir, dirs_exist_ok=True)
        self.state = AppState(self, self._default_state())
        self._load_state()
        self.show_page("start")
        self._toast("Kopia została przywrócona.")

    def _new_project(self) -> None:
        if not messagebox.askyesno("Nowy projekt", "Zapisać bieżący projekt i rozpocząć nowy?", parent=self):
            return
        self._save_state(quiet=True)
        current_prices = [item_to_dict(item) for item in self.prices]
        self.state = AppState(self, self._default_state())
        self.state["pricelist"] = current_prices
        self.mark_dirty()
        self.show_page("investment")

    def _open_project(self) -> None:
        self._save_state(quiet=True)
        path = filedialog.askopenfilename(parent=self, title="Otwórz projekt", initialdir=str(self.projects_dir), filetypes=[("Projekt Calcelyx", "*.json")])
        if not path:
            return
        try:
            loaded = json.loads(Path(path).read_text(encoding="utf-8"))
            loaded["language"] = self.language
            self.state = AppState(self, loaded)
            self.prices = [PriceItem(**item) for item in loaded.get("pricelist", [])] or self.prices
            self.mark_dirty()
            self.show_page("start")
        except Exception as exc:
            messagebox.showerror("Otwieranie projektu", f"Nie udało się otworzyć projektu:\n{exc}", parent=self)

    def export_pdf(self) -> None:
        issues = self._offer_validation_issues()
        if issues:
            messagebox.showwarning("Oferta nie jest kompletna", "Uzupełnij dane przed eksportem:\n\n• " + "\n• ".join(issues), parent=self)
            return
        totals = self._calculate_totals()
        p = self.state["project"]
        preview = f"Klient: {p.get('client_name')}\nAdres: {p.get('address')}\nPozycji w cenie: {sum(1 for row in self.state['lines'] if row.get('included', True))}\nNetto: {self._money(totals['net'])}\nVAT: {self._money(totals['vat'])}\nBrutto: {self._money(totals['gross'])}\nWażność: {p.get('valid_days')} dni\n\nUtworzyć ofertę PDF?"
        if not messagebox.askyesno("Podgląd oferty", preview, parent=self):
            return
        self._save_state(quiet=True)
        initial = f"{'Quote' if self.language == 'en' else 'Oferta'}_{p.get('number', 'estimate').replace('/', '-')}.pdf"
        path = filedialog.asksaveasfilename(parent=self, title="Eksportuj ofertę PDF", initialdir=str(self.export_dir), initialfile=initial, defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            export_offer_pdf(path, p, self.state["lines"], language=self.language)
            self._toast("Oferta PDF jest gotowa.")
            if messagebox.askyesno("Eksport zakończony", "Oferta została zapisana. Otworzyć ją teraz?", parent=self):
                os.startfile(path)
        except Exception as exc:
            messagebox.showerror("Eksport PDF", f"Nie udało się utworzyć oferty:\n{exc}", parent=self)

    def export_xlsx(self) -> None:
        p = self.state["project"]
        initial = f"{'Estimate' if self.language == 'en' else 'Kosztorys'}_{p.get('number', 'estimate').replace('/', '-')}.xlsx"
        path = filedialog.asksaveasfilename(parent=self, title="Eksportuj kosztorys", initialdir=str(self.export_dir), initialfile=initial, defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            try:
                export_estimate_xlsx(path, p, self.state["lines"], language=self.language)
                self._toast("Kosztorys Excel jest gotowy.")
            except Exception as exc:
                messagebox.showerror("Eksport Excel", f"Nie udało się utworzyć pliku:\n{exc}", parent=self)

    def _create_revision(self) -> None:
        issues = self._offer_validation_issues(require_address=False)
        if issues:
            messagebox.showwarning("Nie można utworzyć rewizji", "Uzupełnij:\n\n• " + "\n• ".join(issues), parent=self)
            return
        self._save_state(quiet=True)
        estimate = Estimate(project_id=self.state["id"], title=self.state["project"]["name"], markup_percent=d(self.state["project"].get("markup_pct")), discount_percent=d(self.state["project"].get("discount_pct")), notes=json.dumps(self.state["lines"], ensure_ascii=False))
        revision = self.db.create_estimate_revision(self.state["id"], estimate, "draft")
        self._toast(f"Utworzono rewizję {revision} kosztorysu.")

    def _show_revisions(self) -> None:
        revisions = self.db.list_estimate_revisions(self.state["id"])
        if not revisions:
            messagebox.showinfo("Historia rewizji", "Nie utworzono jeszcze żadnej rewizji.", parent=self)
            return
        window = ctk.CTkToplevel(self)
        window.title("Historia rewizji")
        window.geometry("760x440")
        window.transient(self)
        tree = ttk.Treeview(window, columns=("number", "date", "status", "items"), show="headings")
        for key, label, width in (("number", "Rewizja", 90), ("date", "Data", 190), ("status", "Status", 110), ("items", "Liczba pozycji", 130)):
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="center")
        for revision in revisions:
            try:
                lines = json.loads(revision.estimate.notes or "[]")
            except Exception:
                lines = []
            tree.insert("", "end", iid=str(revision.revision_number), values=(revision.revision_number, revision.created_at.replace("T", " ")[:19], revision.status, len(lines)))
        tree.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(window, text="Rewizje są niezmiennymi migawkami kosztorysu. Utwórz nową rewizję po każdej zmianie przekazanej klientowi.", wraplength=700, text_color=ctk_color("text_muted")).pack(padx=20, pady=(0, 18))

    def _offer_validation_issues(self, *, require_address: bool = True) -> list[str]:
        project = self.state["project"]
        checks = (("name", "nazwa inwestycji — ekran Inwestycja"), ("number", "numer oferty — ekran Inwestycja"), ("date", "data oferty — ekran Inwestycja"), ("client_name", "nazwa klienta — ekran Inwestycja"))
        issues = [label for key, label in checks if not str(project.get(key, "")).strip()]
        if require_address and not str(project.get("address", "")).strip():
            issues.append("adres inwestycji — ekran Inwestycja")
        if not any(line.get("included", True) for line in self.state["lines"]):
            issues.append("co najmniej jedna pozycja uwzględniona w kosztorysie")
        for key, label, minimum, maximum, integer in (("markup_pct", "narzut", Decimal("0"), Decimal("1000"), False), ("discount_pct", "rabat", Decimal("0"), Decimal("100"), False), ("valid_days", "ważność oferty", Decimal("1"), Decimal("3650"), True)):
            try:
                parse_number(project.get(key, ""), label, minimum=minimum, maximum=maximum, integer=integer)
            except ValueError as exc:
                issues.append(str(exc))
        return issues

    def _toast(self, text: str) -> None:
        toast = ctk.CTkFrame(self, fg_color="#172033", corner_radius=9)
        toast.place(relx=0.985, rely=0.965, anchor="se")
        ctk.CTkLabel(toast, text="✓  " + text, text_color="white", font=(FONT_FAMILY, 11, "bold")).pack(padx=18, pady=12)
        self.after(3200, toast.destroy)

    def _on_close(self) -> None:
        try:
            self._save_state(quiet=True)
        finally:
            self.destroy()


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

