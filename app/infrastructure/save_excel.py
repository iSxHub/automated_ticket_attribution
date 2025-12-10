from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path
from app.domain.helpdesk import HelpdeskRequest
from app.infrastructure.excel import build_excel, ExcelReportError


logger = logging.getLogger(__name__)

def save_excel(requests: list[HelpdeskRequest], output_path: str | None = None, filename_prefix: str = "",) -> str:
    try:
        excel_bytes = build_excel(requests)
    except ExcelReportError as exc:
        logger.error("Could not generate Excel report: %s", exc)
        return ""

    project_root = Path(__file__).resolve().parent.parent.parent

    if output_path is None:
        timestamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
        filename = f"{filename_prefix}classified_requests_{timestamp}.xlsx"
        path = project_root / "output" / filename
    else:
        path = Path(output_path)
        if not path.is_absolute():
            path = project_root / path

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(excel_bytes)

    logger.info("Excel report generated at %s", path.resolve())
    return str(path.resolve())