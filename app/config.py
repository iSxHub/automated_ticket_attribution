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
    delay_between_batches: float = 2.0
    temperature: float = 0.0
    top_p: float = 1.0
    top_k: int = 1

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
    codebase_url: str
    email_title: str

# db
@dataclass(frozen=True)
class ReportLogConfig:
    db_path: str