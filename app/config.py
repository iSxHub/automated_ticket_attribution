from dataclasses import dataclass
import os
from dotenv import load_dotenv


load_dotenv()

@dataclass(frozen=True)
class HelpdeskAPIConfig:
    url: str
    api_key: str
    api_secret: str
    timeout_seconds: float = 10.0

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

# Gemini
@dataclass(frozen=True)
class LLMConfig:
    model_name: str
    api_key: str

def load_llm_config() -> LLMConfig:
    model_name = os.getenv("LLM_MODEL_NAME", "gemini-2.0-flash-lite")
    api_key = _get_required_env("GEMINI_API_KEY")

    return LLMConfig(
        model_name=model_name,
        api_key=api_key,
    )