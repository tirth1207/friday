from langchain_nvidia_ai_endpoints import ChatNVIDIA

from .config import settings


def get_model():
    return ChatNVIDIA(
        model=settings.model,
        api_key=settings.api_key,
        base_url=settings.base_url,
        temperature=0.2,
    )