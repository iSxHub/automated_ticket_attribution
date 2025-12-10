from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ReportLogRecord:
    filename: str
    created_at: datetime

class ReportLogError(RuntimeError):
    """Raised when the report log cannot be accessed."""

class SQLiteReportLog:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reports (
                        filename TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise ReportLogError("Failed to initialize report log database") from exc

    def get_record(self, path: Path) -> Optional[ReportLogRecord]:
        filename = path.name

        try:
            conn = sqlite3.connect(self._db_path)
            try:
                cur = conn.execute(
                    "SELECT created_at FROM reports WHERE filename = ?",
                    (filename,),
                )
                row = cur.fetchone()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise ReportLogError("Failed to read from report log database") from exc

        if row is None:
            return None

        created_at_str: str = row[0]
        created_at = datetime.fromisoformat(created_at_str)

        return ReportLogRecord(filename=filename, created_at=created_at)

    def mark_sent(self, path: Path, created_at: Optional[datetime] = None) -> None:
        if created_at is None:
            created_at = datetime.now()

        filename = path.name

        try:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO reports (filename, created_at)
                    VALUES (?, ?)
                    """,
                    (filename, created_at.isoformat(timespec="seconds")),
                )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise ReportLogError("Failed to write to report log database") from exc