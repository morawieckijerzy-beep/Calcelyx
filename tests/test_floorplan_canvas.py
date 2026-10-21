from __future__ import annotations

from types import SimpleNamespace

import pytest

from calcelyx_app.floorplan import FloorPlanCanvas, Outline


def _headless_canvas() -> FloorPlanCanvas:
    """Build only the stateful part of Canvas; no display server is required."""
    canvas = FloorPlanCanvas.__new__(FloorPlanCanvas)
    main = Outline(id="main", name="Obrys lokalu", kind="main")
    canvas.outlines = [main]
    canvas.active_outline_id = main.id
    canvas.meters_per_pixel = 0.1
    canvas.view_scale = 1.0
    canvas.view_offset = [20.0, 20.0]
    canvas._undo_stack = []
    canvas._redo_stack = []
    canvas._mode = "draw"
    canvas.on_change = None
    canvas.redraw = lambda: None
    canvas.focus_set = lambda: None
    return canvas


def test_outline_geometry_uses_exact_closing_segment() -> None:
    outline = Outline(points=[(0, 0), (30, 0), (30, 40)], closed=True)

    assert outline.area_pixels2() == 600
    assert outline.perimeter_pixels() == 120
    assert outline.points == [(0, 0), (30, 0), (30, 40)]


def test_click_near_first_point_closes_without_appending_nearby_point() -> None:
    canvas = _headless_canvas()
    canvas.points = [(0, 0), (100, 0), (100, 100)]
    canvas._world = lambda _x, _y: (5.0, 4.0)

    canvas._click(SimpleNamespace(x=5, y=4))

    assert canvas.closed is True
    assert canvas.points == [(0, 0), (100, 0), (100, 100)]
    assert canvas.perimeter_m == pytest.approx((100 + 100 + 100 * 2**0.5) * 0.1)


def test_multiple_outlines_round_trip_with_shared_transform() -> None:
    canvas = _headless_canvas()
    canvas.points = [(0, 0), (100, 0), (100, 80), (0, 80)]
    canvas.closed = True
    room_id = canvas.start_new_outline("Kuchnia")
    canvas.points = [(10, 10), (50, 10), (50, 40), (10, 40)]
    canvas.closed = True
    canvas.view_scale = 2.5
    canvas.view_offset = [-13.0, 44.0]
    canvas.meters_per_pixel = 0.02

    payload = canvas.serialize()
    restored = _headless_canvas()
    restored.restore(payload)

    assert payload["schema_version"] == 2
    assert len(restored.outlines) == 2
    assert restored.active_outline_id == room_id
    assert restored.active_outline.name == "Kuchnia"
    assert restored.points == [(10.0, 10.0), (50.0, 10.0), (50.0, 40.0), (10.0, 40.0)]
    assert restored.view_scale == 2.5
    assert restored.view_offset == [-13.0, 44.0]
    assert restored.meters_per_pixel == 0.02


def test_restore_accepts_legacy_single_outline_payload() -> None:
    canvas = _headless_canvas()
    canvas.restore({
        "points": [[0, 0], [10, 0], [10, 10]],
        "closed": True,
        "meters_per_pixel": 0.5,
        "view_scale": 1.2,
        "view_offset": [3, 4],
    })

    assert len(canvas.outlines) == 1
    assert canvas.active_outline.kind == "main"
    assert canvas.points == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    assert canvas.closed is True


def test_undo_redo_restores_entire_outline_collection() -> None:
    canvas = _headless_canvas()
    canvas.points = [(0, 0), (10, 0), (10, 10)]

    room_id = canvas.start_new_outline("Łazienka")
    assert len(canvas.outlines) == 2
    assert canvas.active_outline_id == room_id

    canvas.undo()
    assert len(canvas.outlines) == 1
    assert canvas.points == [(0, 0), (10, 0), (10, 10)]

    canvas.redo()
    assert len(canvas.outlines) == 2
    assert canvas.active_outline_id == room_id


def test_only_one_main_outline_is_created() -> None:
    canvas = _headless_canvas()
    existing_id = canvas.active_outline_id

    returned_id = canvas.start_new_outline(kind="main")

    assert returned_id == existing_id
    assert len(canvas.outlines) == 1
