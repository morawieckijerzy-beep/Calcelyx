from __future__ import annotations

from pathlib import Path

import calcelyx_app.app as app_module
from calcelyx_app.reporting import export_offer_pdf


def test_all_pages_and_pdf_underlay(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(app_module, "runtime_root", lambda: tmp_path)
    app = app_module.App()
    try:
        for page in ("investment", "plan", "estimate", "prices", "settings", "start"):
            app.show_page(page)
            app.update()

        sample_pdf = export_offer_pdf(
            tmp_path / "sample.pdf",
            {"company_name": "Test", "number": "1", "date": "2026-10-21"},
            [],
        )
        app.show_page("plan")
        assert app.floor_canvas is not None
        app.floor_canvas.load_pdf(sample_pdf)
        background_size = app.floor_canvas._background_original.size
        app.floor_canvas.points = [(100, 100), (300, 100), (300, 250), (100, 250)]
        app.floor_canvas.meters_per_pixel = 0.02
        app.floor_canvas.closed = True
        assert round(app.floor_canvas.area_m2, 2) == 12.0
        assert round(app.floor_canvas.perimeter_m, 2) == 14.0
        area_before = app.floor_canvas.area_m2
        app.floor_canvas._zoom_at(250, 200, 1.5)
        app.floor_canvas.view_offset = [130, -45]
        assert app.floor_canvas.area_m2 == area_before
        app.floor_canvas._record_undo()
        app.floor_canvas.points.append((120, 120))
        app.floor_canvas.undo()
        assert len(app.floor_canvas.points) == 4
        app.floor_canvas.redo()
        assert len(app.floor_canvas.points) == 5
        app.geometry("1200x780")
        app.update()
        app.floor_canvas.redraw()
        assert app.floor_canvas._background_original.size == background_size
        room_outline_id = app.floor_canvas.start_new_outline("Salon", kind="room")
        app._refresh_outline_selector()
        assert app.floor_canvas.active_outline_id == room_outline_id
        assert len(app.floor_canvas.outlines) == 2
        app.state["project"]["name"] = "Remont Mokotów"
        app.state["project"]["client_name"] = "Jan Kowalski"
        app._save_state(quiet=True)
        assert (tmp_path / "Dane" / "projekt_biezacy.json").exists()
        assert (tmp_path / "Dane" / "calcelyx.sqlite3").exists()
        project_files = list((tmp_path / "Dane" / "Projekty").glob("*.json"))
        assert len(project_files) == 1
        assert project_files[0].name.startswith("Remont Mokotów - Jan Kowalski [")
        assert project_files[0].name != f"{app.state['id']}.json"
    finally:
        app.destroy()

