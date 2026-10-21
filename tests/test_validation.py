from decimal import Decimal

import pytest

import calcelyx_app.app as app_module
from calcelyx_app.app import parse_number, project_archive_filename, safe_filename_component


def test_parse_number_accepts_polish_decimal_separator() -> None:
    assert parse_number("12,50", "Cena", minimum=Decimal("0")) == Decimal("12.50")


@pytest.mark.parametrize("value", ["", "abc", "NaN", "Infinity"])
def test_parse_number_rejects_missing_or_non_numeric_input(value: str) -> None:
    with pytest.raises(ValueError):
        parse_number(value, "Cena")


def test_parse_number_checks_ranges_and_integers() -> None:
    with pytest.raises(ValueError):
        parse_number("101", "Rabat", maximum=Decimal("100"))
    with pytest.raises(ValueError):
        parse_number("1,5", "Liczba wizyt", integer=True)


def test_project_filename_is_readable_and_windows_safe() -> None:
    state = {"id": "24bba72a-e0f1-4a31-8c6c-1f92b2a9b0bf", "project": {"name": "Remont: Mokotów", "client_name": "Jan/Kowalski"}}
    assert project_archive_filename(state) == "Remont_ Mokotów - Jan_Kowalski [24bba72a].json"
    assert safe_filename_component("  .  ", "Projekt") == "Projekt"


def test_patched_build_reuses_canonical_sibling_data(tmp_path, monkeypatch) -> None:
    patched = tmp_path / "Calcelyx_1.0_poprawiona"
    (tmp_path / "Calcelyx" / "Dane").mkdir(parents=True)
    patched.mkdir()
    monkeypatch.setattr(app_module, "runtime_root", lambda: patched)
    monkeypatch.setattr(app_module.sys, "frozen", True, raising=False)

    assert app_module.user_data_root() == tmp_path / "Calcelyx"
