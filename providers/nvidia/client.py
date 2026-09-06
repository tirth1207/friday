from langchain_nvidia_ai_endpoints import ChatNVIDIA

from .config import settings


DEFAULT_HOSTED_MODEL = "nvidia/nemotron-3-super-120b-a12b"


def _is_hosted() -> bool:
    return settings.base_url.rstrip("/").startswith("https://integrate.api.nvidia.com")


def get_model(require_tools: bool = False):
    """Create the NVIDIA model used by FRIDAY.

    Hosted NVIDIA inference is pinned to the documented Nemotron 3 Super model instead
    of probing the model catalog on every process startup. This prevents an old model
    name in .env from breaking tool calling and removes the extra catalog request.
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
    )
