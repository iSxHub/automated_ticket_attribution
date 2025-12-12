from __future__ import annotations
from pathlib import Path
from typing import Protocol, Sequence
from app.domain.helpdesk import HelpdeskRequest


class ReportExporterPort(Protocol):
    def export(self, requests: Sequence[HelpdeskRequest]) -> Path:
        """Persist a report and return its path."""
        ...