import sys
import unittest
from decimal import Decimal
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calcelyx_app.domain import (  # noqa: E402
    Estimate,
    EstimateLine,
    Opening,
    PriceItem,
    Project,
    Room,
    polygon_area,
    polygon_perimeter,
    round_money,
)


class GeometryTests(unittest.TestCase):
    def test_rectangle_area_and_perimeter(self) -> None:
        points = [(0, 0), (4, 0), (4, 3), (0, 3)]
        self.assertEqual(polygon_area(points), Decimal("12"))
        self.assertEqual(polygon_area(list(reversed(points))), Decimal("12"))
        self.assertEqual(polygon_perimeter(points), Decimal("14"))

    def test_room_measurements_with_openings(self) -> None:
        room = Room(
            "Salon",
            [(0, 0), (4, 0), (4, 3), (0, 3)],
            height="2.5",
            openings=[
                Opening("0.9", "2", "door"),
                Opening("1.5", "1.2", "window"),
            ],
        )
        self.assertEqual(room.floor_area, Decimal("12"))
        self.assertEqual(room.ceiling_area, Decimal("12"))
        self.assertEqual(room.walls_gross_area, Decimal("35.0"))
        self.assertEqual(room.walls_net_area, Decimal("31.40"))
        self.assertEqual(room.baseboard_length, Decimal("13.1"))


class EstimateTests(unittest.TestCase):
    def test_line_applies_waste_layers_difficulty_and_minimum(self) -> None:
        item = PriceItem("MAL", "Malowanie", "m2", "10", "5", "8")
        line = EstimateLine(item, "10", waste_percent="10", layers="2", difficulty_multiplier="1.2")
        self.assertEqual(line.billable_quantity, Decimal("22.0"))
        self.assertEqual(line.net_amount, Decimal("372.00"))
        self.assertEqual(line.vat_amount, Decimal("29.76"))

        minimum = EstimateLine(
            PriceItem("MIN", "Drobna praca", "szt", "10", minimum_net="100"),
            "1",
        )
        self.assertEqual(minimum.net_amount, Decimal("100.00"))

    def test_summary_includes_travel_markup_discount_and_mixed_vat(self) -> None:
        line = EstimateLine(PriceItem("A", "Praca", "m2", "100", vat_percent="8"), "1")
        estimate = Estimate(
            "project-1",
            [line],
            markup_percent="10",
            discount_percent="10",
            travel_net="20",
            travel_vat_percent="23",
        )
        summary = estimate.calculate_summary()
        self.assertEqual(summary.lines_net, Decimal("100.00"))
        self.assertEqual(summary.subtotal_net, Decimal("120.00"))
        self.assertEqual(summary.markup_net, Decimal("12.00"))
        self.assertEqual(summary.discount_net, Decimal("13.20"))
        self.assertEqual(summary.net, Decimal("118.80"))
        self.assertEqual(summary.vat, Decimal("12.47"))
        self.assertEqual(summary.gross, Decimal("131.27"))

    def test_half_up_rounding_and_round_trip(self) -> None:
        self.assertEqual(round_money("1.005"), Decimal("1.01"))
        project = Project("Dom", rooms=[Room("Pokój", [(0, 0), (2, 0), (2, 2)])])
        self.assertEqual(Project.from_dict(project.to_dict()), project)


if __name__ == "__main__":
    unittest.main()
