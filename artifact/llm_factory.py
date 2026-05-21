from typing import Tuple
from urllib.parse import urlparse

from langchain_openai import ChatOpenAI
from openai import OpenAI


class LLMConfigError(RuntimeError):
    """Raised when the LLM configuration is invalid or unreachable."""


def _validate_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise LLMConfigError(
            f"Invalid BASE_URL '{base_url}'. Expected a full URL like http://localhost:8000/v1."
        )


def _validate_openai_compatible_endpoint(model: str, api_key: str, base_url: str) -> None:
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=10.0)
    try:
        available = [m.id for m in client.models.list().data]
    except Exception as exc:
        raise LLMConfigError(
            "Failed to connect to BASE_URL as an OpenAI-compatible endpoint. "
            "For local vLLM, make sure the server is running and reachable. "
            f"BASE_URL={base_url}. Original error: {exc}"
        ) from exc

    if available and model not in available:
        preview = ", ".join(available[:8])
        raise LLMConfigError(
            f"Model '{model}' was not found on the endpoint. Available models: {preview}"
        )


def create_llm_from_env(model: str, api_key: str, base_url: str | None) -> Tuple[ChatOpenAI, str]:
    """Builds a ChatOpenAI client for OpenAI or local OpenAI-compatible providers."""
    if not model:
        raise LLMConfigError("LLM_MODEL must be set.")

    if base_url:
        _validate_base_url(base_url)
        resolved_api_key = api_key or "local"
        _validate_openai_compatible_endpoint(model, resolved_api_key, base_url)
        llm = ChatOpenAI(
            model=model,
            temperature=0,
            api_key=resolved_api_key,
            base_url=base_url,
            timeout=600,      # 10 min — at 35 tok/sec, 2048 tokens = ~58s; only fires on vLLM stalls
            max_retries=1,    # allow one retry on transient errors, never loop
        )
        return llm, "openai-compatible"

    if not api_key:
        raise LLMConfigError(
            "API_KEY must be set when BASE_URL is not provided. "
            "For local vLLM, set BASE_URL and optionally API_KEY=local."
        )

    llm = ChatOpenAI(model=model, temperature=0, api_key=api_key, timeout=600, max_retries=1)
    return llm, "openai"
