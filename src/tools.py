"""tools.py — 检索工具 + 来源可信度分类 + URL 可达性探测。"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import List

import requests

from src.config import settings
from .schema import Source

# 域名 -> 可信度类型（用于 v3 可信度加权）
_OFFICIAL_HINTS = ("official", "docs.", ".gov", ".edu", "github.io", "tensorflow", "pytorch", "openai.com", "deepseek.com", "anthropic.com")
_MEDIA_HINTS = ("news", "bloomberg", "reuters", "theverge", "techcrunch", "36kr", "ithome", "qq.com", "sina", "163.com", "zhihu-column")
_BLOG_HINTS = ("blog", "medium", "csdn", "cnblogs", "wordpress")
_FORUM_HINTS = ("forum", "reddit", "stackoverflow", "tieba", "v2ex", "zhihu.com", "quora")

_URL_HOST_RE = re.compile(r"https?://([^/]+)", re.IGNORECASE)


def _host(url: str) -> str:
    m = _URL_HOST_RE.match(url or "")
    return (m.group(1) if m else "").lower()


def classify_source(url: str, title: str = "") -> str:
    """官方 > 媒体 > 博客 > 论坛 > 其他。"""
    blob = f"{url} {title}".lower()
    if any(h in blob for h in _OFFICIAL_HINTS):
        return "official"
    if any(h in blob for h in _FORUM_HINTS):
        return "forum"
    if any(h in blob for h in _BLOG_HINTS):
        return "blog"
    if any(h in blob for h in _MEDIA_HINTS):
        return "media"
    return "other"


def _cache_path(query: str) -> str:
    os.makedirs(settings.CACHE_DIR, exist_ok=True)
    h = hashlib.sha1(query.strip().lower().encode("utf-8")).hexdigest()[:16]
    return os.path.join(settings.CACHE_DIR, f"search_{h}.json")


def search(query: str, max_results: int | None = None) -> List[Source]:
    """执行一次检索，返回带编号的来源列表。带本地缓存。

    实际后端由 settings.SEARCH_BACKEND 决定（serpapi | tavily）。
    任何网络/API 异常都会向上抛出，由调用方 _safe_retrieve 单路隔离，
    绝不会把错误信息当结果逐字符拆成假来源。
    """
    max_results = max_results or settings.search_max_results()
    cache_key = f"{settings.SEARCH_BACKEND}||{query}||{max_results}"
    if settings.ENABLE_CACHE:
        cp = _cache_path(cache_key)
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data:
                    return [Source(**d) for d in data]
            except Exception:
                pass

    backend = settings.SEARCH_BACKEND
    if backend == "tavily":
        sources = _search_tavily(query, max_results)
    elif backend == "serpapi":
        sources = _search_serpapi(query, max_results)
    else:
        raise RuntimeError(f"不支持的检索后端: {backend}（应为 serpapi 或 tavily）")

    if settings.ENABLE_CACHE:
        try:
            with open(cp, "w", encoding="utf-8") as f:
                json.dump([s.model_dump() for s in sources], f, ensure_ascii=False)
        except Exception:
            pass
    return sources


def _search_tavily(query: str, max_results: int) -> List[Source]:
    """Tavily 检索（官方 SDK，响应 {results:[...]}）。"""
    from tavily import TavilyClient

    client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    resp = client.search(
        query=query,
        max_results=max_results,
        search_depth="basic",
        include_images=False,
    )
    if not isinstance(resp, dict):
        raise RuntimeError(f"Tavily 返回非预期结构: {type(resp)} -> {str(resp)[:200]}")
    results = resp.get("results") or []
    if not isinstance(results, list):
        raise RuntimeError(f"Tavily results 字段非列表: {type(results)}")

    sources: List[Source] = []
    for i, r in enumerate(results, start=1):
        if not isinstance(r, dict):
            continue
        url = r.get("url") or ""
        title = r.get("title") or ""
        content = r.get("content") or ""
        try:
            score = float(r.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        sources.append(Source(
            idx=i, title=title, url=url, content=content,
            score=score, source_type=classify_source(url, title),
        ))
    if not sources:
        raise RuntimeError(f"Tavily 对「{query}」返回 0 条结果（resp keys={list(resp.keys())}）")
    return sources


def _search_serpapi(query: str, max_results: int) -> List[Source]:
    """SerpAPI 检索（Google/Bing 等，走 REST，无需额外依赖）。

    响应关键字段：organic_results / news_results，每项含
    title / link / snippet / position。无相关度分数时按排名推导
    score = 1/position，供 v3 可信度加权使用。
    """
    params = {
        "engine": settings.SERPAPI_ENGINE,
        "q": query,
        "num": max_results,
        "api_key": settings.SERPAPI_API_KEY,
        "hl": "zh-cn",
        "gl": "cn",
    }
    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params=params,
            timeout=settings.REQUEST_TIMEOUT,
        )
    except Exception as e:  # 网络 / TLS 异常统一向上抛，绝不吞成假来源
        raise RuntimeError(f"SerpAPI 请求失败: {e}") from e

    if resp.status_code != 200:
        try:
            err = resp.json().get("error", resp.text)
        except Exception:
            err = resp.text
        raise RuntimeError(f"SerpAPI HTTP {resp.status_code}: {err}")

    try:
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"SerpAPI 响应非 JSON: {e}") from e
    if not isinstance(data, dict):
        raise RuntimeError(f"SerpAPI 返回非预期结构: {type(data)} -> {str(data)[:200]}")

    results = data.get("organic_results") or data.get("news_results") or []
    if not isinstance(results, list):
        raise RuntimeError(f"SerpAPI results 字段非列表: {type(results)}")

    sources: List[Source] = []
    for i, r in enumerate(results, start=1):
        if not isinstance(r, dict):
            continue
        url = r.get("link") or r.get("url") or ""
        title = r.get("title") or ""
        content = r.get("snippet") or r.get("content") or ""
        position = r.get("position") or i
        try:
            score = round(1.0 / float(position), 4) if position else 0.0
        except (TypeError, ValueError):
            score = 0.0
        sources.append(Source(
            idx=i, title=title, url=url, content=content,
            score=score, source_type=classify_source(url, title),
        ))
    if not sources:
        raise RuntimeError(f"SerpAPI 对「{query}」返回 0 条结果（resp keys={list(data.keys())}）")
    return sources


def format_sources(sources: List[Source], snippet: int = 600) -> str:
    """把来源渲染成带编号的上下文，供 prompt 使用。"""
    lines = []
    for s in sources:
        lines.append(f"[{s.idx}] 《{s.title}》 ({s.source_type})\nURL: {s.url}\n摘要: {s.snippet(snippet)}")
    return "\n\n".join(lines)


def verify_url(url: str, timeout: int | None = None) -> bool:
    timeout = timeout or settings.REQUEST_TIMEOUT
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0 (compatible; AgentBenchKit/1.0)"})
        if r.status_code >= 400:
            r = requests.get(url, timeout=timeout, allow_redirects=True, stream=True,
                             headers={"User-Agent": "Mozilla/5.0 (compatible; AgentBenchKit/1.0)"})
            return r.status_code < 400
        return r.status_code < 400
    except Exception:
        return False
