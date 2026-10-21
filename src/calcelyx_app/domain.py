"""Core business objects and calculations for Calcelyx.

The module deliberately has no UI or persistence dependencies.  Dimensions are
expressed in metres and all prices are net PLN amounts unless stated otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4


ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")
MONEY_QUANTUM = Decimal("0.01")
QUANTITY_QUANTUM = Decimal("0.0001")


def to_decimal(value: Decimal | int | float | str) -> Decimal:
    """Convert input to Decimal without inheriting binary float artefacts."""

    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round_money(value: Decimal | int | float | str) -> Decimal:
    return to_decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def round_quantity(value: Decimal | int | float | str) -> Decimal:
    return to_decimal(value).quantize(QUANTITY_QUANTUM, rounding=ROUND_HALF_UP)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


Point = tuple[Decimal, Decimal]


def _normalise_points(
    points: Iterable[Sequence[Decimal | int | float | str]],
) -> list[Point]:
    result: list[Point] = []
    for point in points:
        if len(point) != 2:
            raise ValueError("Each point must contain exactly two coordinates")
        result.append((to_decimal(point[0]), to_decimal(point[1])))
    return result


def polygon_area(points: Sequence[Sequence[Decimal | int | float | str]]) -> Decimal:
    """Return the absolute area of a simple polygon using the shoelace formula."""

    normalised = _normalise_points(points)
    if len(normalised) < 3:
        return ZERO
    twice_area = ZERO
    for index, (x1, y1) in enumerate(normalised):
        x2, y2 = normalised[(index + 1) % len(normalised)]
        twice_area += x1 * y2 - x2 * y1
    return abs(twice_area) / Decimal("2")


def polygon_perimeter(
    points: Sequence[Sequence[Decimal | int | float | str]],
) -> Decimal:
    """Return polygon perimeter.  Coordinates are expected in metres."""

    normalised = _normalise_points(points)
    if len(normalised) < 2:
        return ZERO
    result = ZERO
    for index, (x1, y1) in enumerate(normalised):
        x2, y2 = normalised[(index + 1) % len(normalised)]
        # Decimal.sqrt keeps geometry deterministic and avoids float round trips.
        result += ((x2 - x1) ** 2 + (y2 - y1) ** 2).sqrt()
    return result


@dataclass(slots=True)
class Opening:
    width: Decimal
    height: Decimal
    kind: str = "door"
    name: str = ""

    def __post_init__(self) -> None:
        self.width = to_decimal(self.width)
        self.height = to_decimal(self.height)
        if self.width < ZERO or self.height < ZERO:
            raise ValueError("Opening dimensions cannot be negative")

    @property
    def area(self) -> Decimal:
        return self.width * self.height

    @property
    def subtract_from_baseboard(self) -> bool:
        return self.kind.casefold() in {"door", "doors", "drzwi"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": _decimal_text(self.width),
            "height": _decimal_text(self.height),
            "kind": self.kind,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Opening":
        return cls(
            width=data["width"],
            height=data["height"],
            kind=str(data.get("kind", "door")),
            name=str(data.get("name", "")),
        )


@dataclass(slots=True)
class Room:
    name: str
    points: list[Point]
    height: Decimal = Decimal("2.60")
    openings: list[Opening] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        self.points = _normalise_points(self.points)
        self.height = to_decimal(self.height)
        if self.height <= ZERO:
            raise ValueError("Room height must be positive")

    @property
    def floor_area(self) -> Decimal:
        return polygon_area(self.points)

    @property
    def ceiling_area(self) -> Decimal:
        return self.floor_area

    @property
    def perimeter(self) -> Decimal:
        return polygon_perimeter(self.points)

    @property
    def walls_gross_area(self) -> Decimal:
        return self.perimeter * self.height

    @property
    def walls_net_area(self) -> Decimal:
        return max(ZERO, self.walls_gross_area - sum((item.area for item in self.openings), ZERO))

    @property
    def baseboard_length(self) -> Decimal:
        door_width = sum(
            (item.width for item in self.openings if item.subtract_from_baseboard), ZERO
        )
        return max(ZERO, self.perimeter - door_width)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "points": [[_decimal_text(x), _decimal_text(y)] for x, y in self.points],
            "height": _decimal_text(self.height),
            "openings": [item.to_dict() for item in self.openings],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Room":
        return cls(
            id=str(data.get("id") or uuid4()),
            name=str(data["name"]),
            points=list(data.get("points", [])),
            height=data.get("height", "2.60"),
            openings=[Opening.from_dict(item) for item in data.get("openings", [])],
        )


@dataclass(slots=True)
class Project:
    name: str
    customer_name: str = ""
    rooms: list[Room] = field(default_factory=list)
    notes: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "customer_name": self.customer_name,
            "notes": self.notes,
            "rooms": [room.to_dict() for room in self.rooms],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Project":
        return cls(
            id=str(data.get("id") or uuid4()),
            name=str(data["name"]),
            customer_name=str(data.get("customer_name", "")),
            notes=str(data.get("notes", "")),
            rooms=[Room.from_dict(item) for item in data.get("rooms", [])],
        )


@dataclass(slots=True)
class PriceItem:
    code: str
    name: str
    unit: str
    labor_price: Decimal = ZERO
    material_price: Decimal = ZERO
    vat_percent: Decimal = Decimal("8")
    minimum_net: Decimal = ZERO
    category: str = ""

    def __post_init__(self) -> None:
        self.labor_price = to_decimal(self.labor_price)
        self.material_price = to_decimal(self.material_price)
        self.vat_percent = to_decimal(self.vat_percent)
        self.minimum_net = to_decimal(self.minimum_net)
        if not self.code.strip():
            raise ValueError("Price item code is required")
        if any(value < ZERO for value in (self.labor_price, self.material_price, self.minimum_net)):
            raise ValueError("Prices cannot be negative")
        if self.vat_percent < ZERO:
            raise ValueError("VAT cannot be negative")

    @property
    def unit_net(self) -> Decimal:
        return self.labor_price + self.material_price

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "unit": self.unit,
            "labor_price": _decimal_text(self.labor_price),
            "material_price": _decimal_text(self.material_price),
            "vat_percent": _decimal_text(self.vat_percent),
            "minimum_net": _decimal_text(self.minimum_net),
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PriceItem":
        return cls(**dict(data))


@dataclass(slots=True)
class EstimateLine:
    price_item: PriceItem
    quantity: Decimal
    waste_percent: Decimal = ZERO
    layers: Decimal = Decimal("1")
    difficulty_multiplier: Decimal = Decimal("1")
    description: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        self.quantity = to_decimal(self.quantity)
        self.waste_percent = to_decimal(self.waste_percent)
        self.layers = to_decimal(self.layers)
        self.difficulty_multiplier = to_decimal(self.difficulty_multiplier)
        if self.quantity < ZERO or self.waste_percent < ZERO:
            raise ValueError("Quantity and waste cannot be negative")
        if self.layers <= ZERO or self.difficulty_multiplier <= ZERO:
            raise ValueError("Layers and difficulty multiplier must be positive")

    @property
    def billable_quantity(self) -> Decimal:
        return self.quantity * (Decimal("1") + self.waste_percent / ONE_HUNDRED) * self.layers

    @property
    def calculated_net(self) -> Decimal:
        labor = self.quantity * self.layers * self.price_item.labor_price
        material = self.billable_quantity * self.price_item.material_price
        return (labor + material) * self.difficulty_multiplier

    @property
    def net_amount(self) -> Decimal:
        return round_money(max(self.calculated_net, self.price_item.minimum_net))

    @property
    def vat_amount(self) -> Decimal:
        return round_money(self.net_amount * self.price_item.vat_percent / ONE_HUNDRED)

    @property
    def gross_amount(self) -> Decimal:
        return self.net_amount + self.vat_amount

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "price_item": self.price_item.to_dict(),
            "quantity": _decimal_text(self.quantity),
            "waste_percent": _decimal_text(self.waste_percent),
            "layers": _decimal_text(self.layers),
            "difficulty_multiplier": _decimal_text(self.difficulty_multiplier),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EstimateLine":
        return cls(
            id=str(data.get("id") or uuid4()),
            price_item=PriceItem.from_dict(data["price_item"]),
            quantity=data["quantity"],
            waste_percent=data.get("waste_percent", "0"),
            layers=data.get("layers", "1"),
            difficulty_multiplier=data.get("difficulty_multiplier", "1"),
            description=str(data.get("description", "")),
        )


@dataclass(frozen=True, slots=True)
class EstimateSummary:
    lines_net: Decimal
    travel_net: Decimal
    subtotal_net: Decimal
    markup_net: Decimal
    discount_net: Decimal
    net: Decimal
    vat: Decimal
    gross: Decimal


@dataclass(slots=True)
class Estimate:
    project_id: str
    lines: list[EstimateLine] = field(default_factory=list)
    title: str = "Wycena"
    discount_percent: Decimal = ZERO
    markup_percent: Decimal = ZERO
    travel_net: Decimal = ZERO
    travel_vat_percent: Decimal = Decimal("8")
    notes: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        self.discount_percent = to_decimal(self.discount_percent)
        self.markup_percent = to_decimal(self.markup_percent)
        self.travel_net = to_decimal(self.travel_net)
        self.travel_vat_percent = to_decimal(self.travel_vat_percent)
        if any(
            value < ZERO
            for value in (
                self.discount_percent,
                self.markup_percent,
                self.travel_net,
                self.travel_vat_percent,
            )
        ):
            raise ValueError("Estimate percentages and travel cost cannot be negative")
        if self.discount_percent > ONE_HUNDRED:
            raise ValueError("Discount cannot exceed 100%")

    def calculate_summary(self) -> EstimateSummary:
        lines_net = sum((line.net_amount for line in self.lines), ZERO)
        travel_net = round_money(self.travel_net)
        subtotal = lines_net + travel_net
        markup = round_money(subtotal * self.markup_percent / ONE_HUNDRED)
        before_discount = subtotal + markup
        discount = round_money(before_discount * self.discount_percent / ONE_HUNDRED)
        net = round_money(before_discount - discount)

        # Markup and discount are spread proportionally over all taxable items.
        factor = (
            (Decimal("1") + self.markup_percent / ONE_HUNDRED)
            * (Decimal("1") - self.discount_percent / ONE_HUNDRED)
        )
        lines_vat = sum(
            (
                line.net_amount
                * factor
                * line.price_item.vat_percent
                / ONE_HUNDRED
                for line in self.lines
            ),
            ZERO,
        )
        travel_vat = travel_net * factor * self.travel_vat_percent / ONE_HUNDRED
        vat = round_money(lines_vat + travel_vat)
        return EstimateSummary(
            lines_net=round_money(lines_net),
            travel_net=travel_net,
            subtotal_net=round_money(subtotal),
            markup_net=markup,
            discount_net=discount,
            net=net,
            vat=vat,
            gross=net + vat,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "discount_percent": _decimal_text(self.discount_percent),
            "markup_percent": _decimal_text(self.markup_percent),
            "travel_net": _decimal_text(self.travel_net),
            "travel_vat_percent": _decimal_text(self.travel_vat_percent),
            "notes": self.notes,
            "lines": [line.to_dict() for line in self.lines],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Estimate":
        return cls(
            id=str(data.get("id") or uuid4()),
            project_id=str(data["project_id"]),
            title=str(data.get("title", "Wycena")),
            discount_percent=data.get("discount_percent", "0"),
            markup_percent=data.get("markup_percent", "0"),
            travel_net=data.get("travel_net", "0"),
            travel_vat_percent=data.get("travel_vat_percent", "8"),
            notes=str(data.get("notes", "")),
            lines=[EstimateLine.from_dict(item) for item in data.get("lines", [])],
        )
