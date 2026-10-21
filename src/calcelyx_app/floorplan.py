from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import messagebox, simpledialog
from typing import Callable
from uuid import uuid4

from PIL import Image, ImageEnhance, ImageTk


Point = tuple[float, float]


@dataclass(slots=True)
class Outline:
    """A persistent polygon drawn in background/world coordinates."""

    id: str = field(default_factory=lambda: uuid4().hex)
    name: str = "Pomieszczenie"
    kind: str = "room"  # ``main`` for the optional apartment outline
    points: list[Point] = field(default_factory=list)
    closed: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "points": [list(point) for point in self.points],
            "closed": self.closed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Outline":
        kind = str(data.get("kind", "room"))
        if kind not in {"main", "room"}:
            kind = "room"
        return cls(
            id=str(data.get("id") or uuid4().hex),
            name=str(data.get("name") or ("Obrys lokalu" if kind == "main" else "Pomieszczenie")),
            kind=kind,
            points=[(float(x), float(y)) for x, y in data.get("points", [])],
            closed=bool(data.get("closed", False)),
        )

    def area_pixels2(self) -> float:
        if len(self.points) < 3:
            return 0.0
        return abs(sum(
            x1 * self.points[(index + 1) % len(self.points)][1]
            - self.points[(index + 1) % len(self.points)][0] * y1
            for index, (x1, y1) in enumerate(self.points)
        )) / 2

    def perimeter_pixels(self) -> float:
        if len(self.points) < 2:
            return 0.0
        segments = list(zip(self.points, self.points[1:]))
        if self.closed:
            segments.append((self.points[-1], self.points[0]))
        return sum(math.dist(a, b) for a, b in segments)

    def can_close_at(self, point: Point, tolerance: float) -> bool:
        """Whether a click should close this outline without adding a point."""
        return len(self.points) >= 3 and math.dist(point, self.points[0]) <= tolerance

    def has_self_intersection(self) -> bool:
        if len(self.points) < 4:
            return False

        def orientation(a: Point, b: Point, c: Point) -> float:
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        segments = list(zip(self.points, self.points[1:] + [self.points[0]]))
        for i, (a, b) in enumerate(segments):
            for j, (c, d) in enumerate(segments):
                if j <= i + 1 or (i == 0 and j == len(segments) - 1):
                    continue
                if orientation(a, b, c) * orientation(a, b, d) < 0 and orientation(c, d, a) * orientation(c, d, b) < 0:
                    return True
        return False


class FloorPlanCanvas(tk.Canvas):
    """Offline 2D editor sharing one transform between plan and measurements."""

    MIN_ZOOM = 0.08
    MAX_ZOOM = 8.0
    CLOSE_SNAP_PX = 14.0

    def __init__(self, master: tk.Misc, on_change: Callable[[], None] | None = None, on_mode_change: Callable[[str], None] | None = None, **kwargs):
        super().__init__(master, background="#F8FAFC", highlightthickness=0, takefocus=True, **kwargs)
        self.on_change = on_change
        self.on_mode_change = on_mode_change
        first = Outline(name="Obrys lokalu", kind="main")
        self.outlines: list[Outline] = [first]
        self.active_outline_id: str = first.id
        self.meters_per_pixel = 0.02
        self._background_original: Image.Image | None = None
        self._background_photo: ImageTk.PhotoImage | None = None
        self._background_opacity = 0.42
        self._calibration_points: list[tuple[float, float]] = []
        self._mode = "draw"
        self.view_scale = 1.0
        self.view_offset = [20.0, 20.0]
        self._pan_anchor: tuple[float, float] | None = None
        self._pan_origin: tuple[float, float] | None = None
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self.bind("<Button-1>", self._click)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Double-Button-1>", self._double_click)
        self.bind("<Button-2>", self._start_middle_pan)
        self.bind("<B2-Motion>", self._middle_pan)
        self.bind("<ButtonRelease-2>", self._release)
        self.bind("<Control-MouseWheel>", self._wheel_zoom)
        self.bind("<Control-Button-4>", lambda e: self._zoom_at(e.x, e.y, 1.12))
        self.bind("<Control-Button-5>", lambda e: self._zoom_at(e.x, e.y, 1 / 1.12))
        self.bind("<Control-z>", lambda _e: self.undo())
        self.bind("<Control-y>", lambda _e: self.redo())
        self.bind("<Control-Shift-Z>", lambda _e: self.redo())
        self.bind("<Configure>", lambda _e: self.redraw())

    @property
    def active_outline(self) -> Outline:
        for outline in self.outlines:
            if outline.id == self.active_outline_id:
                return outline
        if not self.outlines:
            outline = Outline(name="Pomieszczenie", kind="room")
            self.outlines.append(outline)
            self.active_outline_id = outline.id
            return outline
        self.active_outline_id = self.outlines[0].id
        return self.outlines[0]

    # Compatibility with the original single-outline API. Mutable access such as
    # ``canvas.points.append(...)`` continues to target the selected outline.
    @property
    def points(self) -> list[Point]:
        return self.active_outline.points

    @points.setter
    def points(self, value: list[Point]) -> None:
        self.active_outline.points = value

    @property
    def closed(self) -> bool:
        return self.active_outline.closed

    @closed.setter
    def closed(self, value: bool) -> None:
        self.active_outline.closed = bool(value)

    def _snapshot(self) -> dict:
        return {
            "outlines": [outline.to_dict() for outline in self.outlines],
            "active_outline_id": self.active_outline_id,
            "meters_per_pixel": self.meters_per_pixel,
        }

    def _apply_snapshot(self, snapshot: dict) -> None:
        self.outlines = [Outline.from_dict(data) for data in snapshot["outlines"]]
        self.active_outline_id = str(snapshot.get("active_outline_id", ""))
        self.meters_per_pixel = float(snapshot.get("meters_per_pixel", self.meters_per_pixel))
        # Normalize a stale selection without creating a second outline.
        if self.outlines and not any(item.id == self.active_outline_id for item in self.outlines):
            self.active_outline_id = self.outlines[0].id

    def _record_undo(self) -> None:
        self._undo_stack.append(self._snapshot())
        self._undo_stack = self._undo_stack[-100:]
        self._redo_stack.clear()

    def start_new_outline(self, name: str | None = None, kind: str = "room") -> str:
        """Create, select and return the id of a new persistent outline.

        There may be only one ``main`` outline. Calling this with ``kind='main'``
        selects the existing main outline when one is already present.
        """
        if kind not in {"main", "room"}:
            raise ValueError("kind musi mieć wartość 'main' albo 'room'")
        if kind == "main":
            existing = next((item for item in self.outlines if item.kind == "main"), None)
            if existing:
                self.select_outline(existing.id)
                return existing.id
        self._record_undo()
        default_number = 1 + sum(item.kind == "room" for item in self.outlines)
        outline = Outline(name=name or ("Obrys lokalu" if kind == "main" else f"Pomieszczenie {default_number}"), kind=kind)
        self.outlines.append(outline)
        self.active_outline_id = outline.id
        self.redraw()
        self._changed()
        return outline.id

    def select_outline(self, outline_id: str) -> None:
        if not any(item.id == outline_id for item in self.outlines):
            raise KeyError(f"Nie znaleziono obrysu: {outline_id}")
        self.active_outline_id = outline_id
        self.redraw()
        self._changed()

    def rename_outline(self, outline_id: str, name: str) -> None:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Nazwa obrysu nie może być pusta")
        outline = next((item for item in self.outlines if item.id == outline_id), None)
        if outline is None:
            raise KeyError(f"Nie znaleziono obrysu: {outline_id}")
        if outline.name == normalized:
            return
        self._record_undo()
        outline.name = normalized
        self.redraw()
        self._changed()

    def delete_outline(self, outline_id: str | None = None) -> None:
        target = outline_id or self.active_outline_id
        if not any(item.id == target for item in self.outlines):
            return
        self._record_undo()
        self.outlines = [item for item in self.outlines if item.id != target]
        if not self.outlines:
            self.outlines.append(Outline(name="Pomieszczenie 1", kind="room"))
        self.active_outline_id = self.outlines[0].id
        self.redraw()
        self._changed()

    def _world(self, x: float, y: float) -> tuple[float, float]:
        return ((x - self.view_offset[0]) / self.view_scale, (y - self.view_offset[1]) / self.view_scale)

    def _screen(self, x: float, y: float) -> tuple[float, float]:
        return (x * self.view_scale + self.view_offset[0], y * self.view_scale + self.view_offset[1])

    def set_mode(self, mode: str) -> None:
        if mode not in {"draw", "calibrate", "pan"}:
            raise ValueError(f"Nieobsługiwany tryb: {mode}")
        self._mode = mode
        self.configure(cursor="fleur" if mode == "pan" else "crosshair")
        if self.on_mode_change:
            self.on_mode_change(mode)

    @property
    def mode(self) -> str:
        return self._mode

    def clear_outline(self, *, confirm: bool = True) -> None:
        if not self.points:
            return
        if confirm and not messagebox.askyesno("Wyczyść obrys", "Usunąć cały obrys? Możesz go przywrócić skrótem Ctrl+Z.", parent=self):
            return
        self._record_undo()
        self.points.clear()
        self.closed = False
        self.redraw()
        self._changed()

    def undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self._snapshot())
        self._apply_snapshot(self._undo_stack.pop())
        self.redraw()
        self._changed()

    def redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self._snapshot())
        self._apply_snapshot(self._redo_stack.pop())
        self.redraw()
        self._changed()

    def close_outline(self) -> None:
        if len(self.points) < 3:
            messagebox.showwarning("Obrys", "Dodaj co najmniej trzy punkty.", parent=self)
            return
        if not self.closed:
            self._record_undo()
            self.closed = True
            self.redraw()
            self._changed()

    def load_pdf(self, path: str | Path, page_index: int = 0) -> int:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(path))
        page_count = len(pdf)
        if not 0 <= page_index < page_count:
            pdf.close()
            raise ValueError("Nieprawidłowy numer strony PDF")
        page = pdf[page_index]
        bitmap = page.render(scale=2.0)
        self._background_original = bitmap.to_pil().convert("RGB")
        page.close()
        pdf.close()
        self.fit_background()
        return page_count

    def load_image(self, path: str | Path) -> None:
        with Image.open(path) as source:
            self._background_original = source.convert("RGB")
        self.fit_background()

    def fit_background(self) -> None:
        if not self._background_original:
            return
        self.update_idletasks()
        width, height = max(200, self.winfo_width() - 40), max(200, self.winfo_height() - 40)
        image_width, image_height = self._background_original.size
        self.view_scale = max(self.MIN_ZOOM, min(width / image_width, height / image_height, self.MAX_ZOOM))
        self.view_offset = [(self.winfo_width() - image_width * self.view_scale) / 2, (self.winfo_height() - image_height * self.view_scale) / 2]
        self.redraw()

    def set_opacity(self, value: float) -> None:
        self._background_opacity = max(0.08, min(1.0, float(value)))
        self.redraw()

    def start_calibration(self) -> None:
        if not self._background_original:
            messagebox.showwarning("Kalibracja", "Najpierw otwórz PDF lub obraz rzutu.", parent=self)
            return
        self._calibration_points.clear()
        self.set_mode("calibrate")
        messagebox.showinfo("Kalibracja skali", "Kliknij kolejno dwa końce znanego wymiaru na rzucie.", parent=self)

    def _click(self, event: tk.Event) -> None:
        self.focus_set()
        if self._mode == "pan":
            self._pan_anchor, self._pan_origin = (float(event.x), float(event.y)), tuple(self.view_offset)
            return
        point = self._world(float(event.x), float(event.y))
        if self._mode == "calibrate":
            self._calibration_points.append(point)
            if len(self._calibration_points) == 2:
                pixels = math.dist(*self._calibration_points)
                # Pokaż oba punkty i linię odniesienia również wtedy, gdy
                # modalne okno oczekuje na podanie rzeczywistej długości.
                self.redraw()
                self.update_idletasks()
                real = simpledialog.askfloat("Znany wymiar", "Rzeczywista odległość [m]:", minvalue=0.01, parent=self)
                if real and pixels:
                    self._record_undo()
                    self.meters_per_pixel = real / pixels
                    messagebox.showinfo("Skala ustawiona", f"1 px = {self.meters_per_pixel:.5f} m", parent=self)
                    self._changed()
                self.set_mode("draw")
                self._calibration_points.clear()
            self.redraw()
            return
        if self._mode != "draw" or self.closed:
            return
        # Closing never appends an approximate second copy of the first point.
        # The closing edge is represented geometrically as last -> points[0].
        if self.active_outline.can_close_at(point, self.CLOSE_SNAP_PX / self.view_scale):
            self.close_outline()
            return
        if self.points:
            x0, y0 = self.points[-1]
            snap = 10 / self.view_scale
            if abs(point[0] - x0) < snap:
                point = (x0, point[1])
            elif abs(point[1] - y0) < snap:
                point = (point[0], y0)
        self._record_undo()
        self.points.append(point)
        self.redraw()
        self._changed()

    def _drag(self, event: tk.Event) -> None:
        if self._mode == "pan" and self._pan_anchor and self._pan_origin:
            self.view_offset = [self._pan_origin[0] + event.x - self._pan_anchor[0], self._pan_origin[1] + event.y - self._pan_anchor[1]]
            self.redraw()

    def _start_middle_pan(self, event: tk.Event) -> None:
        self._pan_anchor, self._pan_origin = (float(event.x), float(event.y)), tuple(self.view_offset)

    def _middle_pan(self, event: tk.Event) -> None:
        if self._pan_anchor and self._pan_origin:
            self.view_offset = [self._pan_origin[0] + event.x - self._pan_anchor[0], self._pan_origin[1] + event.y - self._pan_anchor[1]]
            self.redraw()

    def _release(self, _event: tk.Event) -> None:
        self._pan_anchor = self._pan_origin = None

    def _wheel_zoom(self, event: tk.Event) -> str:
        self._zoom_at(event.x, event.y, 1.12 if event.delta > 0 else 1 / 1.12)
        return "break"

    def _zoom_at(self, x: float, y: float, factor: float) -> None:
        old_scale = self.view_scale
        new_scale = max(self.MIN_ZOOM, min(self.MAX_ZOOM, old_scale * factor))
        if new_scale == old_scale:
            return
        world_x, world_y = self._world(x, y)
        self.view_scale = new_scale
        self.view_offset = [x - world_x * new_scale, y - world_y * new_scale]
        self.redraw()
        self._changed()

    def _double_click(self, _event: tk.Event) -> None:
        if self._mode == "draw" and len(self.points) >= 3 and not self.closed:
            self.undo()  # suppress the extra point generated by Tk
            self.close_outline()

    def _changed(self) -> None:
        if self.on_change:
            self.on_change()

    @property
    def area_m2(self) -> float:
        return self.active_outline.area_pixels2() * self.meters_per_pixel**2

    @property
    def perimeter_m(self) -> float:
        return self.active_outline.perimeter_pixels() * self.meters_per_pixel

    @property
    def has_self_intersection(self) -> bool:
        return self.active_outline.has_self_intersection()

    def outline_area_m2(self, outline_id: str) -> float:
        outline = next(item for item in self.outlines if item.id == outline_id)
        return outline.area_pixels2() * self.meters_per_pixel**2

    def outline_perimeter_m(self, outline_id: str) -> float:
        outline = next(item for item in self.outlines if item.id == outline_id)
        return outline.perimeter_pixels() * self.meters_per_pixel

    def serialize(self) -> dict:
        return {
            "schema_version": 2,
            "outlines": [outline.to_dict() for outline in self.outlines],
            "active_outline_id": self.active_outline_id,
            "meters_per_pixel": self.meters_per_pixel,
            "view_scale": self.view_scale,
            "view_offset": list(self.view_offset),
        }

    def restore(self, data: dict) -> None:
        if "outlines" in data:
            self.outlines = [Outline.from_dict(item) for item in data.get("outlines", [])]
            if not self.outlines:
                self.outlines = [Outline(name="Pomieszczenie 1", kind="room")]
            self.active_outline_id = str(data.get("active_outline_id") or self.outlines[0].id)
            if not any(item.id == self.active_outline_id for item in self.outlines):
                self.active_outline_id = self.outlines[0].id
        else:
            # Transparent migration of projects saved by the single-outline API.
            legacy = Outline(
                name="Obrys lokalu",
                kind="main",
                points=[(float(x), float(y)) for x, y in data.get("points", [])],
                closed=bool(data.get("closed", False)),
            )
            self.outlines = [legacy]
            self.active_outline_id = legacy.id
        self.meters_per_pixel = float(data.get("meters_per_pixel", 0.02))
        self.view_scale = float(data.get("view_scale", 1.0))
        offset = data.get("view_offset", [20, 20])
        self.view_offset = [float(offset[0]), float(offset[1])]
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width, height = max(1, self.winfo_width()), max(1, self.winfo_height())
        step = max(12, int(25 * self.view_scale))
        for x in range(int(self.view_offset[0]) % step, width, step):
            self.create_line(x, 0, x, height, fill="#E9EEF5")
        for y in range(int(self.view_offset[1]) % step, height, step):
            self.create_line(0, y, width, y, fill="#E9EEF5")
        if self._background_original:
            source = self._background_original
            size = (max(1, int(source.width * self.view_scale)), max(1, int(source.height * self.view_scale)))
            image = ImageEnhance.Contrast(source.resize(size, Image.Resampling.LANCZOS)).enhance(0.88)
            alpha = Image.new("L", image.size, int(self._background_opacity * 255))
            rgba = image.convert("RGBA")
            rgba.putalpha(alpha)
            self._background_photo = ImageTk.PhotoImage(rgba)
            self.create_image(*self.view_offset, image=self._background_photo, anchor="nw")
        # Inactive outlines are drawn first and remain visible while another room
        # is being edited. All use the same world transform and calibration.
        ordered = sorted(self.outlines, key=lambda item: item.id == self.active_outline_id)
        for outline in ordered:
            if not outline.points:
                continue
            active = outline.id == self.active_outline_id
            color = "#2563EB" if active else ("#0F766E" if outline.kind == "main" else "#64748B")
            fill = "#DBEAFE" if active else ("#CCFBF1" if outline.kind == "main" else "#E2E8F0")
            width_px = 4 if active else 2
            shown = [self._screen(*point) for point in outline.points]
            flat = [value for point in shown for value in point]
            if outline.closed and len(shown) >= 3:
                self.create_polygon(*flat, outline=color, fill=fill, stipple="gray25", width=width_px)
            elif len(shown) >= 2:
                self.create_line(*flat, fill=color, width=width_px, capstyle="round", joinstyle="round")
            if active:
                for index, (x, y) in enumerate(shown, 1):
                    self.create_oval(x - 6, y - 6, x + 6, y + 6, fill="white", outline=color, width=3)
                    self.create_text(x + 12, y - 12, text=str(index), fill="#172033", font=("Segoe UI", 9, "bold"))
                segments = zip(outline.points, outline.points[1:] + ([outline.points[0]] if outline.closed else []))
                for a, b in segments:
                    sa, sb = self._screen(*a), self._screen(*b)
                    self.create_text(
                        (sa[0] + sb[0]) / 2,
                        (sa[1] + sb[1]) / 2 - 11,
                        text=f"{math.dist(a, b) * self.meters_per_pixel:.2f} m",
                        fill="#172033",
                        font=("Segoe UI", 9, "bold"),
                    )
            anchor_x, anchor_y = shown[0]
            self.create_text(anchor_x, anchor_y + 18, anchor="n", text=outline.name, fill=color, font=("Segoe UI", 9, "bold"))
        for point in self._calibration_points:
            x, y = self._screen(*point)
            self.create_oval(x - 7, y - 7, x + 7, y + 7, fill="#F97316", outline="white", width=2)
        if len(self._calibration_points) == 2:
            a, b = (self._screen(*point) for point in self._calibration_points)
            self.create_line(*a, *b, fill="#F97316", width=3, dash=(8, 4))
        self.create_text(width - 12, height - 12, anchor="se", text=f"Zoom {self.view_scale * 100:.0f}%", fill="#64748B", font=("Segoe UI", 9))
