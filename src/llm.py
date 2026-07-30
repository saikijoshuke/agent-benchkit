from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from src.config import settings


def get_llm(temperature: float | None = None) -> BaseChatModel:
    from langchain_deepseek import ChatDeepSeek

    return ChatDeepSeek(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_API_BASE,
        temperature=(settings.SYNTH_TEMPERATURE if temperature is None else temperature),
    )


def count_tokens(text: str) -> int:
    """粗略 token 估算（中文按字、英文按词），仅用于成本展示"""
    if not text:
        return 0
    import re
    en = len(re.findall(r"[A-Za-z0-9]+", text))
    zh = len(re.findall(r"[一-鿿]", text))
    return en + zh