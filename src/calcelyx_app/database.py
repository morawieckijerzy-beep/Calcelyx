"""SQLite persistence for projects and immutable estimate revisions."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .domain import Estimate, Project


ALLOWED_STATUSES = frozenset({"draft", "sent", "accepted", "rejected"})
LOCKED_STATUSES = frozenset({"sent", "accepted"})


class RevisionNotFoundError(LookupError):
    pass


class ImmutableRevisionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EstimateRevision:
    project_id: str
    revision_number: int
    status: str
    estimate: Estimate
    created_at: str
    updated_at: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dump(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class Database:
    """Small repository facade owning short-lived SQLite connections."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Commit/rollback and, importantly on Windows, always close the handle."""

        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        schema = """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS estimate_revisions (
                project_id TEXT NOT NULL,
                revision_number INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('draft','sent','accepted','rejected')),
                snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (project_id, revision_number),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_estimate_revisions_project
            ON estimate_revisions(project_id, revision_number DESC);
        """
        with self._connection() as connection:
            connection.executescript(schema)

    def save_project(self, project: Project) -> None:
        now = _utc_now()
        snapshot = _json_dump(project.to_dict())
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO projects(id, name, snapshot_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    snapshot_json = excluded.snapshot_json,
                    updated_at = excluded.updated_at
                """,
                (project.id, project.name, snapshot, now, now),
            )

    def load_project(self, project_id: str) -> Project | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT snapshot_json FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        if row is None:
            return None
        return Project.from_dict(json.loads(row["snapshot_json"]))

    def list_projects(self) -> list[Project]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT snapshot_json FROM projects ORDER BY updated_at DESC, name"
            ).fetchall()
        return [Project.from_dict(json.loads(row["snapshot_json"])) for row in rows]

    def delete_project(self, project_id: str) -> bool:
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return cursor.rowcount > 0

    def create_estimate_revision(
        self, project_id: str, estimate: Estimate, status: str = "draft"
    ) -> int:
        self._validate_status(status)
        if estimate.project_id != project_id:
            raise ValueError("Estimate belongs to a different project")
        now = _utc_now()
        snapshot = _json_dump(estimate.to_dict())
        # BEGIN IMMEDIATE serialises revision number allocation across processes.
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project_exists = connection.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if project_exists is None:
                raise KeyError(f"Unknown project: {project_id}")
            next_revision = connection.execute(
                """
                SELECT COALESCE(MAX(revision_number), 0) + 1
                FROM estimate_revisions WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO estimate_revisions(
                    project_id, revision_number, status, snapshot_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (project_id, next_revision, status, snapshot, now, now),
            )
        return int(next_revision)

    def update_estimate_revision(
        self,
        project_id: str,
        revision_number: int,
        estimate: Estimate,
        *,
        status: str | None = None,
    ) -> None:
        """Update a draft snapshot; sent and accepted snapshots never change."""

        if estimate.project_id != project_id:
            raise ValueError("Estimate belongs to a different project")
        if status is not None:
            self._validate_status(status)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT status FROM estimate_revisions
                WHERE project_id = ? AND revision_number = ?
                """,
                (project_id, revision_number),
            ).fetchone()
            if row is None:
                raise RevisionNotFoundError((project_id, revision_number))
            if row["status"] in LOCKED_STATUSES:
                raise ImmutableRevisionError(
                    f"Revision {revision_number} is {row['status']} and cannot be edited"
                )
            new_status = status or row["status"]
            connection.execute(
                """
                UPDATE estimate_revisions
                SET status = ?, snapshot_json = ?, updated_at = ?
                WHERE project_id = ? AND revision_number = ?
                """,
                (
                    new_status,
                    _json_dump(estimate.to_dict()),
                    _utc_now(),
                    project_id,
                    revision_number,
                ),
            )

    def set_revision_status(
        self, project_id: str, revision_number: int, status: str
    ) -> None:
        """Change workflow status without modifying the immutable snapshot."""

        self._validate_status(status)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT status FROM estimate_revisions
                WHERE project_id = ? AND revision_number = ?
                """,
                (project_id, revision_number),
            ).fetchone()
            if row is None:
                raise RevisionNotFoundError((project_id, revision_number))
            current = row["status"]
            if current == "accepted" and status != "accepted":
                raise ImmutableRevisionError("An accepted revision has a terminal status")
            if current == "rejected" and status not in {"rejected", "draft"}:
                raise ValueError("A rejected revision must be returned to draft first")
            connection.execute(
                """
                UPDATE estimate_revisions SET status = ?, updated_at = ?
                WHERE project_id = ? AND revision_number = ?
                """,
                (status, _utc_now(), project_id, revision_number),
            )

    def load_estimate_revision(
        self, project_id: str, revision_number: int
    ) -> EstimateRevision | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM estimate_revisions
                WHERE project_id = ? AND revision_number = ?
                """,
                (project_id, revision_number),
            ).fetchone()
        return self._row_to_revision(row) if row is not None else None

    def list_estimate_revisions(self, project_id: str) -> list[EstimateRevision]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM estimate_revisions
                WHERE project_id = ? ORDER BY revision_number DESC
                """,
                (project_id,),
            ).fetchall()
        return [self._row_to_revision(row) for row in rows]

    def backup(self, target: str | Path) -> Path:
        target_path = Path(target)
        if target_path.resolve() == self.path.resolve():
            raise ValueError("Backup target must differ from the source database")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as source:
            destination = sqlite3.connect(target_path)
            try:
                source.backup(destination)
            finally:
                destination.close()
        return target_path

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported revision status: {status}")

    @staticmethod
    def _row_to_revision(row: sqlite3.Row) -> EstimateRevision:
        return EstimateRevision(
            project_id=row["project_id"],
            revision_number=int(row["revision_number"]),
            status=row["status"],
            estimate=Estimate.from_dict(json.loads(row["snapshot_json"])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


# Explicit alias for callers preferring repository terminology.
ProjectRepository = Database
