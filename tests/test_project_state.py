from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

import calcelyx_app.app as app_module
from calcelyx_app.pricelist import PriceItem
from calcelyx_app.project_state import (
    ProjectFileError,
    build_domain_project,
    calculate_line_net,
    format_exact_number,
    line_min_charge,
    normalize_loaded_state,
    obsolete_project_files,
    parse_price_items,
    project_file_for_opened_path,
    quarantine_file,
)


DEFAULTS = {
    "id": "default-id",
    "project": {"name": "Nowa", "number": "1", "client_name": "", "address": ""},
    "rooms": [],
    "floorplan": {},
    "lines": [],
    "travel": {"rate": 0, "parking": 0},
    "pricelist": [],
}
PRICE = {
    "code": "MY-1",
    "category": "C",
    "name": "N",
    "unit": "m2",
    "labor_net": 10.0,
    "material_net": 5.0,
    "vat_rate": 8.0,
    "waste_pct": 0.0,
    "min_charge": 200.0,
    "active": True,
}


def _write_project(path: Path, project_id: str) -> Path:
    path.write_text(json.dumps({"id": project_id}), encoding="utf-8")
    return path


@pytest.mark.parametrize("hostile_name", ["../victim.json", "../../victim.json", "..\\victim.json", "C:\\victim.json"])
def test_relative_escape_never_selected_for_deletion(tmp_path: Path, hostile_name: str) -> None:
    projects = tmp_path / "data" / "Projekty"
    projects.mkdir(parents=True)
    _write_project(tmp_path / "data" / "victim.json", "p1")
    _write_project(tmp_path / "victim.json", "p1")

    assert obsolete_project_files(projects, [hostile_name], "p1", projects / "keep.json") == []


def test_absolute_path_never_selected_for_deletion(tmp_path: Path) -> None:
    projects = tmp_path / "Projekty"
    projects.mkdir()
    victim = _write_project(tmp_path / "victim.json", "p1")

    assert obsolete_project_files(projects, [str(victim)], "p1", projects / "keep.json") == []


def test_only_files_of_the_same_project_are_obsolete(tmp_path: Path) -> None:
    projects = tmp_path / "Projekty"
    projects.mkdir()
    own = _write_project(projects / "old name.json", "p1")
    other_client = _write_project(projects / "other client.json", "p2")
    (projects / "notes.json").write_text("not json", encoding="utf-8")
    keep = _write_project(projects / "keep.json", "p1")

    names = [own.name, other_client.name, "notes.json", keep.name, "missing.json", ""]

    assert obsolete_project_files(projects, names, "p1", keep) == [own]


def test_opened_file_name_comes_from_its_real_location(tmp_path: Path) -> None:
    projects = tmp_path / "Projekty"
    projects.mkdir()

    assert project_file_for_opened_path(projects / "a.json", projects) == "a.json"
    assert project_file_for_opened_path(tmp_path / "a.json", projects) is None


def test_partial_state_gets_nested_defaults_without_mutating_inputs() -> None:
    loaded = {"id": "p1", "project": {"name": "Stary"}, "travel": {"rate": "1"}}

    state = normalize_loaded_state(loaded, DEFAULTS)

    assert state["project"] == {"name": "Stary", "number": "1", "client_name": "", "address": ""}
    assert state["travel"] == {"rate": "1", "parking": 0}
    assert state["rooms"] == [] and state["lines"] == []
    assert DEFAULTS["project"]["name"] == "Nowa"
    assert "number" not in loaded["project"]


@pytest.mark.parametrize(
    "loaded",
    [
        [],
        "text",
        {"project": []},
        {"travel": "x"},
        {"rooms": {}},
        {"rooms": ["x"]},
        {"rooms": [{"height": "2"}]},
        {"lines": "x"},
        {"lines": [1]},
        {"pricelist": {}},
        {"floorplan": []},
    ],
)
def test_malformed_state_is_rejected(loaded: object) -> None:
    with pytest.raises(ProjectFileError):
        normalize_loaded_state(loaded, DEFAULTS)


def test_rooms_and_lines_get_the_fields_pages_index_directly() -> None:
    state = normalize_loaded_state({"rooms": [{"name": "Salon"}], "lines": [{"name": "X"}]}, DEFAULTS)

    assert state["rooms"][0]["floor_area"] == "0"
    assert state["lines"][0]["id"]
    assert state["lines"][0]["net"] == "0"


@pytest.mark.parametrize("project_id", ["../../evil", "a/b", "a\\b", "", None, 5])
def test_unsafe_project_id_is_replaced(project_id: object) -> None:
    state = normalize_loaded_state({"id": project_id}, DEFAULTS)

    assert state["id"] == "default-id"


def test_price_with_unknown_field_is_kept() -> None:
    items, rejected = parse_price_items([{**PRICE, "future_field": 1}])

    assert [item.code for item in items] == ["MY-1"]
    assert rejected == []


def test_invalid_price_is_reported_not_dropped_silently() -> None:
    bad = {"code": "NO-FIELDS"}

    items, rejected = parse_price_items([PRICE, bad, "x"])

    assert [item.code for item in items] == ["MY-1"]
    assert rejected == [bad, "x"]


def test_load_state_keeps_custom_prices_and_saves_rejected_ones(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(app_module.messagebox, "showwarning", lambda _title, text, **_kw: warnings.append(text))
    state_path = tmp_path / "projekt_biezacy.json"
    state_path.write_text(json.dumps({"id": "x", "pricelist": [PRICE, {"code": "BAD"}]}), encoding="utf-8")
    fake = SimpleNamespace(state_path=state_path, state={"language": "en"}, prices=[], language="en")
    fake._default_state = lambda: dict(DEFAULTS)
    fake._bundled_demo_prices = lambda _language: pytest.fail("demo prices must not replace custom ones")

    app_module.App._load_state(fake)

    assert [item.code for item in fake.prices] == ["MY-1"]
    assert len(warnings) == 1
    recovered = list(tmp_path.glob("cennik_odzyskany_*.json"))
    assert len(recovered) == 1
    assert json.loads(recovered[0].read_text(encoding="utf-8")) == [{"code": "BAD"}]


def test_load_state_sets_aside_unreadable_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module.messagebox, "showwarning", lambda *_a, **_kw: None)
    state_path = tmp_path / "projekt_biezacy.json"
    state_path.write_text("{broken", encoding="utf-8")
    fake = SimpleNamespace(state_path=state_path, state={"language": "en"}, prices=[], language="en")
    fake._default_state = lambda: dict(DEFAULTS)
    fake._bundled_demo_prices = lambda _language: []

    app_module.App._load_state(fake)

    copies = list(tmp_path.glob("projekt_biezacy.json.unreadable-*"))
    assert len(copies) == 1
    assert copies[0].read_text(encoding="utf-8") == "{broken"


def test_quarantine_does_not_overwrite_previous_copy(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("one", encoding="utf-8")

    first = quarantine_file(path)
    second = quarantine_file(path)

    assert first != second
    assert first.read_text(encoding="utf-8") == "one"


def _open_project_fake(tmp_path: Path, show_page: object) -> SimpleNamespace:
    previous_state = {"id": "current", "project": {"name": "Bieżący"}}
    previous_prices = [PriceItem(**PRICE)]
    fake = SimpleNamespace(
        state=previous_state,
        prices=previous_prices,
        language="en",
        projects_dir=tmp_path / "Projekty",
        _dirty=False,
        _last_deleted_rooms=[{"name": "stary"}],
        _last_deleted_lines=[{"id": "stary"}],
        _last_deleted_prices=[PriceItem(**PRICE)],
        show_page=show_page,
    )
    fake.projects_dir.mkdir(exist_ok=True)
    fake._save_state = lambda quiet=False: None
    fake._default_state = lambda: dict(DEFAULTS)
    fake._clear_undo_buffers = lambda: app_module.App._clear_undo_buffers(fake)
    fake.mark_dirty = lambda: setattr(fake, "_dirty", True)
    return fake


def _choose_file(monkeypatch: pytest.MonkeyPatch, path: Path) -> list[str]:
    errors: list[str] = []
    monkeypatch.setattr(app_module.filedialog, "askopenfilename", lambda **_kw: str(path))
    monkeypatch.setattr(app_module.messagebox, "showerror", lambda _title, text, **_kw: errors.append(text))
    return errors


@pytest.mark.parametrize(
    "content",
    ["{broken", json.dumps({"rooms": "x"}), json.dumps({"pricelist": [{"code": "BAD"}]})],
)
def test_failed_open_leaves_current_project_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str) -> None:
    source = tmp_path / "bad.json"
    source.write_text(content, encoding="utf-8")
    errors = _choose_file(monkeypatch, source)
    fake = _open_project_fake(tmp_path, lambda _page: None)
    state, prices = fake.state, fake.prices

    app_module.App._open_project(fake)

    assert fake.state is state and fake.prices is prices
    assert fake._dirty is False
    assert len(errors) == 1
    assert fake._last_deleted_lines == [{"id": "stary"}]


def test_open_rolls_back_when_the_page_cannot_render(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "ok.json"
    source.write_text(json.dumps({"id": "other"}), encoding="utf-8")
    errors = _choose_file(monkeypatch, source)
    rendered: list[str] = []

    def show_page(page: str) -> None:
        rendered.append(str(fake.state["id"]))
        if fake.state["id"] == "other":
            raise KeyError("name")

    fake = _open_project_fake(tmp_path, show_page)

    app_module.App._open_project(fake)

    assert fake.state["id"] == "current"
    assert rendered == ["other", "current"]
    assert len(errors) == 1


def test_open_ignores_project_file_from_json_and_clears_undo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "outside.json"
    source.write_text(json.dumps({"id": "other", "_project_file": "../../victim.txt"}), encoding="utf-8")
    _choose_file(monkeypatch, source)
    fake = _open_project_fake(tmp_path, lambda _page: None)

    app_module.App._open_project(fake)

    assert fake.state["id"] == "other"
    assert "_project_file" not in fake.state
    assert fake._last_deleted_rooms == [] and fake._last_deleted_lines == [] and fake._last_deleted_prices == []


def test_new_project_clears_undo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *_a, **_kw: True)
    fake = _open_project_fake(tmp_path, lambda _page: None)

    app_module.App._new_project(fake)

    assert fake._last_deleted_rooms == [] and fake._last_deleted_lines == [] and fake._last_deleted_prices == []


def test_line_net_applies_minimum_charge() -> None:
    assert calculate_line_net(Decimal("1"), Decimal("10"), Decimal("5"), Decimal("0"), Decimal("1"), Decimal("200")) == Decimal("200")
    assert calculate_line_net(Decimal("100"), Decimal("10"), Decimal("5"), Decimal("10"), Decimal("2"), Decimal("200")) == Decimal("3100.0")


def test_line_min_charge_prefers_line_then_price_list() -> None:
    prices = [PriceItem(**PRICE)]

    assert line_min_charge({"min_charge": "50", "code": "MY-1"}, prices) == Decimal("50")
    assert line_min_charge({"code": "MY-1"}, prices) == Decimal("200.0")
    assert line_min_charge({"code": "GONE"}, prices) == Decimal("0")


@pytest.mark.parametrize(
    ("value", "language", "expected"),
    [
        ("1.2345", "en", "1.2345"),
        ("1.2345", "pl", "1,2345"),
        ("12.50", "en", "12.5"),
        (23.0, "en", "23"),
        ("100", "en", "100"),
        ("1E+2", "en", "100"),
        ("0.0001", "en", "0.0001"),
        ("NaN", "en", "0"),
        (None, "en", "0"),
    ],
)
def test_editor_number_keeps_full_precision(value: object, language: str, expected: str) -> None:
    assert format_exact_number(value, language) == expected


def test_domain_project_keeps_room_identity_openings_and_full_state() -> None:
    state = {
        "id": "p1",
        "project": {"name": "P", "client_name": "K"},
        "travel": {"rate": "1"},
        "floorplan": {"points": []},
        "lines": [{"id": "l1", "net": "10"}],
        "rooms": [
            {"id": "r1", "name": "Salon", "length": "5", "width": "4", "height": "2.5", "opening_area": "3"},
            {"id": "r2", "name": "Bad", "height": "-1"},
        ],
    }

    first = build_domain_project(state)
    second = build_domain_project(state)

    assert [room.id for room in first.rooms] == ["r1"]
    assert [room.id for room in second.rooms] == ["r1"]
    assert sum(opening.area for opening in first.rooms[0].openings) == Decimal("3")
    stored = json.loads(first.notes)
    assert [room["id"] for room in stored["rooms"]] == ["r1", "r2"]
    assert stored["lines"] == state["lines"]
    assert stored["floorplan"] == state["floorplan"]


def test_ui_and_pdf_totals_match_on_half_cent_values() -> None:
    from calcelyx_app.reporting import calculate_totals

    for net, markup in (("1250.50", "5"), ("0.50", "1"), ("333.30", "2.5")):
        lines = [{"net": net, "vat_rate": 8, "included": True}]
        fake = SimpleNamespace(state={"lines": lines, "project": {"markup_pct": markup, "discount_pct": "0"}})
        assert app_module.App._calculate_totals(fake) == calculate_totals(lines, Decimal("0"), Decimal(markup))

    half_cent = calculate_totals([{"net": "1250.50", "vat_rate": 8}], Decimal("0"), Decimal("5"))
    assert half_cent["markup"] == Decimal("62.53")
