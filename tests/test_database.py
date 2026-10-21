import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calcelyx_app.database import Database, ImmutableRevisionError  # noqa: E402
from calcelyx_app.domain import Estimate, EstimateLine, PriceItem, Project, Room  # noqa: E402


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = Database(self.root / "data.sqlite3")
        self.project = Project(
            "Mieszkanie",
            customer_name="Jan Kowalski",
            rooms=[Room("Salon", [(0, 0), (5, 0), (5, 4), (0, 4)])],
        )
        self.database.save_project(self.project)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_project_snapshot_round_trip_and_update(self) -> None:
        loaded = self.database.load_project(self.project.id)
        self.assertEqual(loaded, self.project)
        assert loaded is not None
        loaded.name = "Nowa nazwa"
        self.database.save_project(loaded)
        self.assertEqual(self.database.load_project(self.project.id).name, "Nowa nazwa")
        self.assertEqual(len(self.database.list_projects()), 1)

    def test_revisions_are_numbered_and_locked_after_sending(self) -> None:
        estimate = Estimate(
            self.project.id,
            [EstimateLine(PriceItem("MAL", "Malowanie", "m2", "25"), "40")],
        )
        first = self.database.create_estimate_revision(self.project.id, estimate)
        second = self.database.create_estimate_revision(self.project.id, estimate)
        self.assertEqual((first, second), (1, 2))

        estimate.notes = "zmiana robocza"
        self.database.update_estimate_revision(self.project.id, first, estimate, status="sent")
        estimate.notes = "niedozwolona zmiana"
        with self.assertRaises(ImmutableRevisionError):
            self.database.update_estimate_revision(self.project.id, first, estimate)

        stored = self.database.load_estimate_revision(self.project.id, first)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.status, "sent")
        self.assertEqual(stored.estimate.notes, "zmiana robocza")
        self.database.set_revision_status(self.project.id, first, "accepted")
        self.assertEqual(
            self.database.load_estimate_revision(self.project.id, first).status,
            "accepted",
        )

    def test_backup_is_readable(self) -> None:
        backup_path = self.database.backup(self.root / "backup" / "copy.sqlite3")
        backup = Database(backup_path)
        self.assertEqual(backup.load_project(self.project.id), self.project)


if __name__ == "__main__":
    unittest.main()
