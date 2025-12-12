from __future__ import annotations
from pathlib import Path
from typing import Sequence
from app.application.errors import ReportGenerationError
from app.application.ports.report_exporter_port import ReportExporterPort
from app.domain.helpdesk import HelpdeskRequest
from app.infrastructure.build_excel import ExcelReportError
from app.infrastructure.save_excel import save_excel


class ExcelReportExporter(ReportExporterPort):
    def export(self, requests: Sequence[HelpdeskRequest]) -> Path:
        try:
            excel_path_str = save_excel(list(requests))
        except ExcelReportError as exc:
            raise ReportGenerationError(str(exc)) from exc

        return Path(excel_path_str).resolve()