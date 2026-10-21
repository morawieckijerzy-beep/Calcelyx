"""Wspólny motyw interfejsu aplikacji Calcelyx.

Modul nie wymaga biblioteki CustomTkinter. Kolory w ``CTK_COLORS`` maja
format ``(jasny, ciemny)`` akceptowany przez CustomTkinter, a funkcja
``configure_ttk_styles`` konfiguruje natywne widzety ``tkinter.ttk``.
"""

from __future__ import annotations

from typing import Final, Literal, Mapping
import tkinter as tk
from tkinter import ttk


AppearanceMode = Literal["light", "dark"]

FONT_FAMILY: Final = "Segoe UI"
MONOSPACE_FONT_FAMILY: Final = "Cascadia Mono"

SPACING: Final[Mapping[str, int]] = {
    "xxs": 2,
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "2xl": 32,
    "3xl": 48,
}

RADII: Final[Mapping[str, int]] = {
    "sm": 4,
    "md": 8,
    "lg": 12,
}

TYPOGRAPHY: Final[Mapping[str, tuple[str, int, str]]] = {
    "display": (FONT_FAMILY, 28, "bold"),
    "title": (FONT_FAMILY, 22, "bold"),
    "heading": (FONT_FAMILY, 16, "bold"),
    "body": (FONT_FAMILY, 12, "normal"),
    "body_strong": (FONT_FAMILY, 12, "bold"),
    "caption": (FONT_FAMILY, 10, "normal"),
    "button": (FONT_FAMILY, 11, "bold"),
}

# Neutralne powierzchnie i niebieski akcent nawiazuja do jezyka Fluent,
# zachowujac niezalezna identyfikacje aplikacji.
LIGHT_COLORS: Final[Mapping[str, str]] = {
    "background": "#F5F7FA",
    "surface": "#FFFFFF",
    "surface_alt": "#EEF2F6",
    "surface_hover": "#E6EDF5",
    "border": "#D1D9E3",
    "border_strong": "#AAB6C5",
    "text": "#182230",
    "text_muted": "#566476",
    "text_disabled": "#8995A5",
    "accent": "#2563EB",
    "accent_hover": "#1D4ED8",
    "accent_pressed": "#1E40AF",
    "accent_text": "#FFFFFF",
    "selection": "#DCE8FF",
    "focus": "#60A5FA",
    "success": "#16803A",
    "success_surface": "#E8F6EC",
    "warning": "#9A6700",
    "warning_surface": "#FFF4CE",
    "error": "#C42B1C",
    "error_surface": "#FDEBEC",
    "info": "#0F6CBD",
    "info_surface": "#E5F1FB",
}

DARK_COLORS: Final[Mapping[str, str]] = {
    "background": "#111827",
    "surface": "#1B2432",
    "surface_alt": "#243044",
    "surface_hover": "#2D3A4E",
    "border": "#3B485C",
    "border_strong": "#66748A",
    "text": "#F4F7FB",
    "text_muted": "#B4BFCE",
    "text_disabled": "#7B8798",
    "accent": "#60A5FA",
    "accent_hover": "#7DB5FA",
    "accent_pressed": "#93C5FD",
    "accent_text": "#0B1220",
    "selection": "#244A79",
    "focus": "#93C5FD",
    "success": "#54C77A",
    "success_surface": "#173D28",
    "warning": "#F3C64E",
    "warning_surface": "#453817",
    "error": "#FF8A80",
    "error_surface": "#4B2326",
    "info": "#75BDF2",
    "info_surface": "#193B54",
}

# Gotowe wartosci fg_color/hover_color dla CustomTkinter.
CTK_COLORS: Final[Mapping[str, tuple[str, str]]] = {
    name: (LIGHT_COLORS[name], DARK_COLORS[name]) for name in LIGHT_COLORS
}


def colors(mode: AppearanceMode = "light") -> Mapping[str, str]:
    """Zwraca palete dla jawnie wybranego trybu wygladu."""

    return DARK_COLORS if mode == "dark" else LIGHT_COLORS


def ctk_color(name: str) -> tuple[str, str]:
    """Zwraca pare ``(light, dark)`` do uzycia w CustomTkinter.

    ``KeyError`` dla nieznanej nazwy jest zamierzony: literowka w tokenie
    motywu powinna byc wykryta podczas tworzenia interfejsu.
    """

    return CTK_COLORS[name]


def _detect_mode(root: tk.Misc) -> AppearanceMode:
    """Rozpoznaje tryb CustomTkinter bez twardej zaleznosci od biblioteki."""

    get_mode = getattr(root, "_get_appearance_mode", None)
    if callable(get_mode):
        try:
            value = str(get_mode()).lower()
            if value in {"dark", "1"}:
                return "dark"
        except (tk.TclError, TypeError):
            pass
    return "light"


def configure_ttk_styles(root: tk.Misc) -> ttk.Style:
    """Konfiguruje spójne style ttk i zwraca obiekt :class:`ttk.Style`.

    Funkcje nalezy wywolac po utworzeniu glownego okna. Dla ``CTk`` tryb
    jasny/ciemny jest rozpoznawany automatycznie. Po zmianie trybu w trakcie
    pracy funkcje mozna wywolac ponownie.
    """

    palette = colors(_detect_mode(root))
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        # Nie kazda dystrybucja Tk udostepnia motyw clam.
        pass

    root.option_add("*Font", (FONT_FAMILY, 11))
    root.option_add("*selectBackground", palette["selection"])
    root.option_add("*selectForeground", palette["text"])

    style.configure("TFrame", background=palette["background"])
    style.configure("Surface.TFrame", background=palette["surface"])
    style.configure("Card.TFrame", background=palette["surface"], relief="flat")

    style.configure(
        "TLabel",
        background=palette["background"],
        foreground=palette["text"],
        font=TYPOGRAPHY["body"],
    )
    style.configure(
        "Surface.TLabel",
        background=palette["surface"],
        foreground=palette["text"],
        font=TYPOGRAPHY["body"],
    )
    style.configure("Title.TLabel", font=TYPOGRAPHY["title"])
    style.configure("Heading.TLabel", font=TYPOGRAPHY["heading"])
    style.configure(
        "Muted.TLabel",
        foreground=palette["text_muted"],
        font=TYPOGRAPHY["caption"],
    )
    for semantic in ("success", "warning", "error", "info"):
        style.configure(
            f"{semantic.title()}.TLabel",
            foreground=palette[semantic],
            font=TYPOGRAPHY["body_strong"],
        )

    button_base = {
        "font": TYPOGRAPHY["button"],
        "padding": (SPACING["lg"], SPACING["sm"]),
        "borderwidth": 0,
        "focuscolor": palette["focus"],
    }
    style.configure(
        "TButton",
        **button_base,
        background=palette["surface_alt"],
        foreground=palette["text"],
    )
    style.map(
        "TButton",
        background=[("pressed", palette["border"]), ("active", palette["surface_hover"])],
        foreground=[("disabled", palette["text_disabled"])],
    )
    style.configure(
        "Primary.TButton",
        **button_base,
        background=palette["accent"],
        foreground=palette["accent_text"],
    )
    style.map(
        "Primary.TButton",
        background=[
            ("pressed", palette["accent_pressed"]),
            ("active", palette["accent_hover"]),
            ("disabled", palette["border"]),
        ],
        foreground=[("disabled", palette["text_disabled"])],
    )
    style.configure(
        "Danger.TButton",
        **button_base,
        background=palette["error"],
        foreground="#FFFFFF",
    )
    style.map("Danger.TButton", background=[("active", palette["error_surface"])])

    field_options = {
        "fieldbackground": palette["surface"],
        "foreground": palette["text"],
        "bordercolor": palette["border"],
        "lightcolor": palette["border"],
        "darkcolor": palette["border"],
        "insertcolor": palette["text"],
        "padding": SPACING["sm"],
    }
    style.configure("TEntry", **field_options)
    style.configure("TCombobox", **field_options, arrowsize=16)
    for widget_style in ("TEntry", "TCombobox"):
        style.map(
            widget_style,
            bordercolor=[("focus", palette["focus"]), ("invalid", palette["error"])],
            fieldbackground=[("disabled", palette["surface_alt"])],
            foreground=[("disabled", palette["text_disabled"])],
        )

    style.configure(
        "Treeview",
        background=palette["surface"],
        fieldbackground=palette["surface"],
        foreground=palette["text"],
        bordercolor=palette["border"],
        rowheight=32,
        font=TYPOGRAPHY["body"],
    )
    style.configure(
        "Treeview.Heading",
        background=palette["surface_alt"],
        foreground=palette["text"],
        font=TYPOGRAPHY["body_strong"],
        padding=(SPACING["sm"], SPACING["sm"]),
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", palette["selection"])],
        foreground=[("selected", palette["text"])],
    )
    style.map("Treeview.Heading", background=[("active", palette["surface_hover"])])

    style.configure("TNotebook", background=palette["background"], borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=palette["surface_alt"],
        foreground=palette["text_muted"],
        font=TYPOGRAPHY["body_strong"],
        padding=(SPACING["lg"], SPACING["sm"]),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", palette["surface"]), ("active", palette["surface_hover"])],
        foreground=[("selected", palette["accent"])],
    )
    style.configure("TSeparator", background=palette["border"])
    style.configure(
        "TCheckbutton",
        background=palette["background"],
        foreground=palette["text"],
        font=TYPOGRAPHY["body"],
    )
    style.map("TCheckbutton", foreground=[("disabled", palette["text_disabled"])])

    return style


__all__ = [
    "CTK_COLORS",
    "DARK_COLORS",
    "FONT_FAMILY",
    "LIGHT_COLORS",
    "MONOSPACE_FONT_FAMILY",
    "RADII",
    "SPACING",
    "TYPOGRAPHY",
    "colors",
    "configure_ttk_styles",
    "ctk_color",
]
