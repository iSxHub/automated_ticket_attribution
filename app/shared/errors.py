from __future__ import annotations


class ServiceCatalogLoadError(RuntimeError):
    """Raised when Service Catalog cannot be loaded (HTTP/parse/shape/mapping)."""


class EmailSendError(RuntimeError):
    """Raised when sending report email fails."""


class ReportGenerationError(RuntimeError):
    """Raised when report export/generation fails."""