"""Application configuration loaded from hardcoded credentials."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel

from app.config.credentials import CREDENTIALS

class Settings(BaseModel):
    """Strongly-typed settings required by the application."""

    azure_search_service_endpoint: str
    azure_search_admin_key: str
    azure_search_index_name: str
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment_name: str
    azure_openai_api_version: str
    azure_openai_embedding_deployment_name: str
    azure_form_recognizer_endpoint: str = ""
    azure_form_recognizer_key: str = ""
    embedding_dimensions: int
    azure_search_use_semantic: bool = True
    azure_search_auto_create_index: bool = True
    minimum_relevance_score: float = 0.7
    enable_streaming: bool = True
    allowed_origins: List[str] = ["*"]


def _parse_bool(value: Optional[str], default: bool = True) -> bool:
    """Parse boolean-like environment values with a default fallback."""

    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_float(value: Optional[str], default: float) -> float:
    """Parse float environment values with a default fallback."""

    if value is None or not value.strip():
        return default
    return float(value)


def _parse_int(value: Optional[str], default: int) -> int:
    """Parse integer environment values with a default fallback."""

    if value is None or not value.strip():
        return default
    return int(value)


def _parse_allowed_origins(value: Optional[str]) -> List[str]:
    """Parse comma-separated CORS origins."""

    if value is None or not value.strip():
        return ["*"]

    origins = [item.strip() for item in value.split(",") if item.strip()]
    return origins or ["*"]


def _read_value(key: str, default: str = "") -> str:
    """Read a value from hardcoded credentials with a default fallback."""

    value = CREDENTIALS.get(key)
    if value is None:
        return default
    return str(value)


def _read_config() -> Dict[str, object]:
    """Read required configuration values from hardcoded credentials."""

    return {
        "azure_search_service_endpoint": _read_value("AZURE_SEARCH_SERVICE_ENDPOINT"),
        "azure_search_admin_key": _read_value("AZURE_SEARCH_ADMIN_KEY"),
        "azure_search_index_name": _read_value("AZURE_SEARCH_INDEX_NAME"),
        "azure_openai_endpoint": _read_value("AZURE_OPENAI_ENDPOINT"),
        "azure_openai_api_key": _read_value("AZURE_OPENAI_API_KEY"),
        "azure_openai_deployment_name": _read_value("AZURE_OPENAI_DEPLOYMENT_NAME"),
        "azure_openai_api_version": _read_value("AZURE_OPENAI_API_VERSION"),
        "azure_openai_embedding_deployment_name": _read_value(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"
        ),
        "azure_form_recognizer_endpoint": _read_value("AZURE_FORM_RECOGNIZER_ENDPOINT"),
        "azure_form_recognizer_key": _read_value("AZURE_FORM_RECOGNIZER_KEY"),
        "embedding_dimensions": _parse_int(_read_value("EMBEDDING_DIMENSIONS"), 1536),
        "azure_search_use_semantic": _parse_bool(
            _read_value("AZURE_SEARCH_USE_SEMANTIC"), default=True
        ),
        "azure_search_auto_create_index": _parse_bool(
            _read_value("AZURE_SEARCH_AUTO_CREATE_INDEX"), default=True
        ),
        "minimum_relevance_score": _parse_float(
            _read_value("MINIMUM_RELEVANCE_SCORE"), 0.7
        ),
        "enable_streaming": _parse_bool(_read_value("ENABLE_STREAMING"), default=True),
        "allowed_origins": _parse_allowed_origins(_read_value("ALLOWED_ORIGINS")),
    }


def get_settings() -> Settings:
    """Build a Settings object from hardcoded credentials."""

    values = _read_config()
    required_keys: List[str] = [
        "azure_search_service_endpoint",
        "azure_search_admin_key",
        "azure_search_index_name",
        "azure_openai_endpoint",
        "azure_openai_api_key",
        "azure_openai_deployment_name",
        "azure_openai_api_version",
        "azure_openai_embedding_deployment_name",
    ]
    missing = [key for key in required_keys if not values.get(key)]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"Missing required hardcoded credentials: {missing_list}")
    return Settings(**values)


# Instantiate settings once for reuse across the app.
settings = get_settings()
