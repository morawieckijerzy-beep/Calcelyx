"""Tk-free rules for loading, saving and pricing project state."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import fields
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from .domain import Opening, Project, Room
from .pricelist import PriceItem


ROOM_DEFAULTS = {"height": "2.6", "floor_area": "0", "perimeter": "0", "walls_net": "0", "baseboard": "0"}
LINE_DEFAULTS = {
    "code": "",
    "room": "",
    "name": "",
    "quantity": "0",
    "unit": "",
    "unit_price": "0",
    "net": "0",
    "vat_rate": 23,
    "included": True,
    "formula": "",
}
_PRICE_FIELD_NAMES = frozenset(field.name for field in fields(PriceItem))
_UNSAFE_NAME_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class ProjectFileError(ValueError):
    """The project data has a structure the application cannot use."""


def d(value: object, default: str = "0") -> Decimal:
    """Parse a stored or typed number, using ``default`` when it is invalid."""
    try:
        result = Decimal(str(value).replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)
    return result if result.is_finite() else Decimal(default)


def is_safe_project_filename(name: object) -> bool:
    """Return whether ``name`` is one plain JSON file name, on any platform."""
    if not isinstance(name, str) or not name.endswith(".json"):
        return False
    return not _UNSAFE_NAME_CHARACTERS.search(name) and name.strip(" .") == name and name != ".json"


def obsolete_project_files(projects_dir: Path, names: Iterable[object], project_id: str, keep: Path) -> list[Path]:
    """Select earlier copies of this project that may be deleted.

    Names come from project JSON, which may be hand-edited or hostile, so a file
    qualifies only if it sits directly in ``projects_dir`` and records the same
    project id.
    """
    obsolete: list[Path] = []
    for name in dict.fromkeys(names):
        if not is_safe_project_filename(name):
            continue
        candidate = projects_dir / str(name)
        if candidate != keep and _is_copy_of_project(candidate, project_id):
            obsolete.append(candidate)
    return obsolete


def project_file_for_opened_path(path: Path, projects_dir: Path) -> str | None:
    """Return the archive name of an opened file, or None if it is outside the archive."""
    if path.resolve().parent != projects_dir.resolve():
        return None
    return path.name if is_safe_project_filename(path.name) else None


def normalize_loaded_state(loaded: object, defaults: dict) -> dict:
    """Build a complete state from loaded JSON without changing either input.

    Raises:
        ProjectFileError: The data's structure cannot be used by the application.
    """
    if not isinstance(loaded, dict):
        raise ProjectFileError("Plik projektu nie zawiera obiektu JSON.")
    state = {**defaults, **loaded}
    for key in ("project", "travel"):
        section = _require_type(loaded.get(key, {}), dict, key)
        state[key] = {**defaults[key], **section}
    state["floorplan"] = _require_type(state["floorplan"], dict, "floorplan")
    state["pricelist"] = _require_type(state["pricelist"], list, "pricelist")
    state["rooms"] = [_normalize_room(room) for room in _require_type(state["rooms"], list, "rooms")]
    state["lines"] = [_normalize_line(line) for line in _require_type(state["lines"], list, "lines")]
    if not is_safe_project_filename(f"{state.get('id')}.json") or not isinstance(state.get("id"), str):
        state["id"] = defaults["id"]
    return state


def read_project_file(path: Path, defaults: dict, language: str, projects_dir: Path) -> tuple[dict, list[PriceItem]]:
    """Read and validate a project chosen by the user, without touching the open one.

    Raises:
        OSError: The file cannot be read.
        ValueError: The content is not valid JSON or not a usable project.
    """
    state = normalize_loaded_state(json.loads(path.read_text(encoding="utf-8")), defaults)
    prices, rejected_prices = parse_price_items(state["pricelist"])
    if rejected_prices:
        raise ProjectFileError(f"Nieprawidłowe pozycje cennika: {len(rejected_prices)}.")
    state["language"] = language
    # Only the file's real location is trusted; this name decides what later saves delete.
    state.pop("_project_file", None)
    project_file = project_file_for_opened_path(path, projects_dir)
    if project_file:
        state["_project_file"] = project_file
    return state, prices


def parse_price_items(raw_items: Iterable[object]) -> tuple[list[PriceItem], list[object]]:
    """Split stored prices into usable items and rejected raw entries.

    Unknown keys are ignored so a file saved by a newer version keeps its prices.
    """
    items: list[PriceItem] = []
    rejected: list[object] = []
    for raw_item in raw_items:
        try:
            items.append(PriceItem(**{key: value for key, value in raw_item.items() if key in _PRICE_FIELD_NAMES}))
        except (AttributeError, TypeError):
            rejected.append(raw_item)
    return items, rejected


def save_rejected_prices(directory: Path, rejected: list[object]) -> Path:
    """Write rejected price entries to a new recovery file and return its path."""
    path = _unused_path(directory, "cennik_odzyskany_", ".json")
    path.write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def quarantine_file(path: Path) -> Path:
    """Copy an unreadable file aside, so the next save cannot destroy it."""
    copy = _unused_path(path.parent, f"{path.name}.unreadable-", "")
    shutil.copy2(path, copy)
    return copy


def calculate_line_net(
    quantity: Decimal,
    labor_net: Decimal,
    material_net: Decimal,
    waste_pct: Decimal,
    difficulty: Decimal,
    min_charge: Decimal,
) -> Decimal:
    """Return an estimate line's net value, never below its minimum charge."""
    labor_total = quantity * labor_net * difficulty
    material_total = quantity * (Decimal("1") + waste_pct / 100) * material_net * difficulty
    return max(min_charge, labor_total + material_total)


def line_min_charge(line: dict, prices: Iterable[PriceItem]) -> Decimal:
    """Return a line's minimum charge; lines saved before it was stored use the price list."""
    if "min_charge" in line:
        return d(line["min_charge"])
    price = next((item for item in prices if item.code == line.get("code")), None)
    return d(price.min_charge) if price else Decimal("0")


def format_exact_number(value: object, language: str) -> str:
    """Format a number for editing with every significant digit kept."""
    text = format(d(value).normalize(), "f")
    return text.replace(".", ",") if language == "pl" else text


def build_domain_project(state: dict) -> Project:
    """Build the database copy of a project.

    Rooms the domain model cannot represent are left out of ``rooms``, but the
    complete rooms, lines and floor plan are always kept in ``notes``.
    """
    return Project(
        id=state["id"],
        name=state["project"].get("name") or "Nowa wycena",
        customer_name=state["project"].get("client_name", ""),
        notes=json.dumps(
            {key: state.get(key) for key in ("project", "travel", "rooms", "lines", "floorplan")},
            ensure_ascii=False,
        ),
        rooms=[room for room in map(_domain_room, state["rooms"]) if room is not None],
    )


def _is_copy_of_project(path: Path, project_id: str) -> bool:
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(stored, dict) and stored.get("id") == project_id


def _require_type(value: object, expected: type, label: str):
    if not isinstance(value, expected):
        raise ProjectFileError(f"Nieprawidłowa sekcja projektu: {label}.")
    return value


def _normalize_room(room: object) -> dict:
    room = _require_type(room, dict, "rooms")
    if not isinstance(room.get("name"), str):
        raise ProjectFileError("Pomieszczenie w pliku projektu nie ma nazwy.")
    return {**ROOM_DEFAULTS, "id": str(uuid4()), **room}


def _normalize_line(line: object) -> dict:
    return {**LINE_DEFAULTS, "id": str(uuid4()), **_require_type(line, dict, "lines")}


def _domain_room(item: dict) -> Room | None:
    length, width = d(item.get("length")), d(item.get("width"))
    points = item.get("points") or [["0", "0"], [str(length), "0"], [str(length), str(width)], ["0", str(width)]]
    opening_area = d(item.get("opening_area"))
    # The UI stores one summed opening area, so it maps to a single opening of that area.
    openings = [Opening(width=opening_area, height=Decimal("1"), kind="opening")] if opening_area > 0 else []
    try:
        return Room(
            name=item["name"],
            points=points,
            height=item.get("height", "2.6"),
            openings=openings,
            id=str(item.get("id") or uuid4()),
        )
    except (ArithmeticError, KeyError, TypeError, ValueError):
        return None


def _unused_path(directory: Path, prefix: str, suffix: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = directory / f"{prefix}{stamp}{suffix}"
    attempt = 1
    while path.exists():
        path = directory / f"{prefix}{stamp}_{attempt}{suffix}"
        attempt += 1
    return path
