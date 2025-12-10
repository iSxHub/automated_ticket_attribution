from dataclasses import dataclass
import os
from dotenv import load_dotenv


load_dotenv()

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

def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required but not set")
    return value

def load_helpdesk_config() -> HelpdeskAPIConfig:
    url = _get_required_env("HELPDESK_API_URL")
    api_key = _get_required_env("HELPDESK_API_KEY")
    api_secret = _get_required_env("HELPDESK_API_SECRET")

    return HelpdeskAPIConfig(
        url=url,
        api_key=api_key,
        api_secret=api_secret,
    )

def load_service_catalog_config() -> ServiceCatalogConfig:
    url = _get_required_env("SERVICE_CATALOG_URL")

    return ServiceCatalogConfig(
        url=url,
    )

# LLM
@dataclass(frozen=True)
class LLMConfig:
    model_name: str
    api_key: str
    batch_size: int

def load_llm_config() -> LLMConfig:
    model_name = os.getenv("LLM_MODEL_NAME")
    api_key = _get_required_env("GEMINI_API_KEY")

    batch_size_str = os.getenv("LLM_BATCH_SIZE", "30")
    try:
        batch_size = int(batch_size_str)
    except ValueError as exc:
        raise RuntimeError("LLM_BATCH_SIZE must be an integer") from exc

    return LLMConfig(
        model_name=model_name,
        api_key=api_key,
        batch_size=batch_size,
    )

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

def load_email_config() -> EmailConfig:
    smtp_host = os.getenv("EMAIL_SMTP_HOST")
    smtp_port_str = os.getenv("EMAIL_SMTP_PORT")
    use_tls_str = os.getenv("EMAIL_USE_TLS")

    username = _get_required_env("EMAIL_USERNAME")
    password = _get_required_env("EMAIL_PASSWORD")

    if not username or not password:
        raise RuntimeError("EMAIL_USERNAME and EMAIL_PASSWORD must be set in the environment.")

    smtp_port = int(smtp_port_str)
    use_tls = use_tls_str.lower() in ("1", "true", "yes", "y")

    sender = os.getenv("EMAIL_SENDER", username)
    recipient = os.getenv("EMAIL_RECIPIENT")
    candidate_name = os.getenv("CANDIDATE_NAME")

    return EmailConfig(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        use_tls=use_tls,
        username=username,
        password=password,
        sender=sender,
        recipient=recipient,
        candidate_name=candidate_name,
    )
# db
@dataclass(frozen=True)
class ReportLogConfig:
    db_path: str

def load_report_log_config() -> ReportLogConfig:
    db_path = os.getenv("REPORT_LOG_DB_PATH")
    return ReportLogConfig(db_path=db_path)