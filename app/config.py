from __future__ import annotations
from dataclasses import dataclass


# helpdesk
@dataclass(frozen=True)
class HelpdeskAPIConfig:
    url: str
    api_key: str
    api_secret: str
    timeout_seconds: float = 10.0

# service catalog
@dataclass(frozen=True)
class ServiceCatalogConfig:
    url: str
    timeout_seconds: float = 10.0

# LLM
@dataclass(frozen=True)
class LLMConfig:
    model_name: str
    api_key: str
    batch_size: int

# email
@dataclass
class EmailConfig:
    smtp_host: str
    smtp_port: int
    use_tls: bool
    username: str
    password: str
    sender: str
    recipient: str
    candidate_name: str

# db
@dataclass(frozen=True)
class ReportLogConfig:
    db_path: str
