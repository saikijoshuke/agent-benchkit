"""agent_v4.py — v4: 在 v3 之上叠加"反思循环"（默认关闭，需显式开启）。

反思循环：草稿生成后，让审稿模型找出"没有 [N] 引用支撑"的论断与编造 URL；
若存在无支撑论断，则针对这些论断做补充检索（或显式标注「无检索依据」）后重新合成。
对应 INTERVIEW：反思循环代价高，只在需要极致严谨时开启（ENABLE_REFLECTION=1）。
"""
from __future__ import annotations

from .agent_v2 import _dedup_merge
from .agent_v3 import ResearchAgentV3
from .config import settings
from .prompts import build_reflect_messages
from .utils import extract_json


class ResearchAgentV4(ResearchAgentV3):
    arch = "v4"

    def _reflect(self, report: str, sources) -> dict:
        raw = self._call(build_reflect_messages(report, sources))
        data = extract_json(raw) or {}
        if not isinstance(data, dict):
            return {"ungrounded": [], "has_fabricated_url": False}
        return {
            "ungrounded": data.get("ungrounded", []) or [],
            "has_fabricated_url": bool(data.get("has_fabricated_url", False)),
        }

    def research(self, topic: str) -> dict:
        # 复用 v2 的并行检索 + v3 的可信度合成得到草稿
        queries = self.plan(topic)
        sources = self.parallel_search(queries)
        if not sources:
            raise RuntimeError(
                "所有子问题的检索均失败（来源为空）。常见原因：Tavily 网络/TLS 连接失败"
                "（代理或区域限制）、API Key 无效，或返回 0 条结果。"
            )
        try:
            report = self.synthesize(topic, sources)
        except Exception as e:
            report = self._fallback_report(topic, sources, str(e))
            return {"report": report, "sources": sources}

        if not settings.ENABLE_REFLECTION:
            return {"report": report, "sources": sources}

        # 反思：找出无支撑论断
        try:
            review = self._reflect(report, sources)
        except Exception:
            return {"report": report, "sources": sources}
        ungrounded = [u for u in review.get("ungrounded", []) if u]
        if not ungrounded and not review.get("has_fabricated_url"):
            return {"report": report, "sources": sources}

        # 针对无支撑论断补充检索（并入来源，重新编号）
        extra = []
        for claim in ungrounded[:3]:
            extra.append(self.retrieve(claim, max_results=3))
        if extra:
            sources = _dedup_merge([sources] + extra)
        # 重新合成，并强制把无法支撑的论断改写为「无检索依据」
        try:
            report2 = self.synthesize(
                topic + "\n\n补充要求：对仍无来源支撑的论断，直接写「（无检索依据）」，不要编造。",
                sources,
            )
        except Exception as e:
            report2 = self._fallback_report(topic, sources, str(e))
        return {"report": report2, "sources": sources}
