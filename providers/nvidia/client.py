from langchain_nvidia_ai_endpoints import ChatNVIDIA

from .config import settings


DEFAULT_HOSTED_MODEL = "nvidia/nemotron-3-super-120b-a12b"


def _is_hosted() -> bool:
    return settings.base_url.rstrip("/").startswith("https://integrate.api.nvidia.com")


def get_model(require_tools: bool = False):
    """Create the NVIDIA model used by FRIDAY.

    FRIDAY keeps model reasoning private: Nemotron's thinking mode is disabled for
    user-facing generations, while the UI receives explicit execution events for
    agent/tool progress. A larger generation budget also prevents long repository
    explanations from being cut off.
    """
    if _is_hosted() and not settings.api_key.strip():
        raise RuntimeError(
            "NVIDIA_API_KEY is missing or empty. Set NVIDIA_API_KEY in FRIDAY's .env before starting the server."
        )

    model_name = DEFAULT_HOSTED_MODEL if _is_hosted() else settings.model.strip()
    if not model_name:
        raise RuntimeError("NVIDIA_MODEL is empty for the configured custom NIM endpoint.")

    return ChatNVIDIA(
        model=model_name,
        api_key=settings.api_key,
        base_url=settings.base_url,
        temperature=0.2,
        max_completion_tokens=8192,
    ).with_thinking_mode(enabled=False)
