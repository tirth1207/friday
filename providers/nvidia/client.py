from functools import lru_cache

from langchain_nvidia_ai_endpoints import ChatNVIDIA

from .config import settings


DEFAULT_TOOL_MODEL = "nvidia/nemotron-3-super-120b-a12b"


@lru_cache(maxsize=1)
def _hosted_tool_model() -> str:
    """Resolve a provider-known tool-capable hosted model once per process.

    Custom/local NIM deployments are left untouched because their model catalog is
    deployment-specific. For NVIDIA hosted endpoints, prefer a model LangChain
    explicitly reports as supporting tools when the configured model is unknown or
    not tool-capable.
    """
    configured = settings.model.strip()
    if not settings.base_url.startswith("https://integrate.api.nvidia.com"):
        return configured

    try:
        models = ChatNVIDIA.get_available_models()
        for model in models:
            if getattr(model, "id", None) == configured and getattr(model, "supports_tools", False):
                return configured
        for model in models:
            if getattr(model, "supports_tools", False):
                return str(model.id)
    except Exception as error:
        print(f"[NVIDIA] Could not resolve hosted tool-capable model: {error}")

    return DEFAULT_TOOL_MODEL


def get_model(require_tools: bool = False):
    model_name = _hosted_tool_model() if require_tools else settings.model
    return ChatNVIDIA(
        model=model_name,
        api_key=settings.api_key,
        base_url=settings.base_url,
        temperature=0.2,
    )
