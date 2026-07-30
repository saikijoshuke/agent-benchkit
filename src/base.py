from __future__ import annotations

import time
from typing import List

from langchain_core.messages import BaseMessage

from src.config import settings
from .citation_guard import analyze_claims, analyze_report
from .cost_tracker import CostTracker
from .llm import count_tokens, get_llm
from .prompts import build_synth_messages
from .schema import AgentResult, Source


class BaseResearchAgent:
    arch = "base"

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.tracker = CostTracker()
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    # ---------- 检索 ----------
    def retrieve(self, query: str, max_results: int | None = None) -> List[Source]:
        from .tools import search
        return search(query, max_results)

    # ---------- 受控 LLM 调用（记录成本）----------
    def _call(self, messages: List[BaseMessage], temperature: float | None = None) -> str:
        llm = get_llm(temperature) if temperature is not None else self.llm
        resp = llm.invoke(messages)
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        # token 统计（优先 usage_metadata，否则估算）
        inp = out = 0
        um = getattr(resp, "usage_metadata", None)
        if um:
            inp = getattr(um, "input_tokens", 0) or 0
            out = getattr(um, "output_tokens", 0) or 0
        else:
            inp = count_tokens("\n".join(m.content for m in messages if isinstance(m.content, str)))
            out = count_tokens(text)
        self.tracker.add(inp, out)
        return text

    # ---------- 合成（受约束）----------
    def synthesize(self, topic: str, sources: List[Source]) -> str:
        return self._call(build_synth_messages(topic, sources))

    # ---------- 引用校验 + 清洗 ----------
    def guard(self, report: str, sources: List[Source]) -> dict:
        cguard = analyze_report(
            report, sources,
            verify_reachable=settings.VERIFY_URL_REACHABLE,
            timeout=settings.REQUEST_TIMEOUT,
        )
        claims = analyze_claims(report, cguard)
        return {
            "clean_report": cguard.clean_text,
            "cite_acc": cguard.cite_acc,
            "fabricated": cguard.fabricated,
            "citations_total": cguard.total,
            "hall_rate": claims.hall_rate,
        }

    # ---------- 子类实现：如何组织检索合成 ----------
    def research(self, topic: str) -> dict:
        """返回报告和来源列表。"""
        sources = self.retrieve(topic)
        report = self.synthesize(topic, sources)
        return {"report": report, "sources": sources}

    # ---------- 统一入口 ----------
    def run(self, topic: str) -> AgentResult:
        t0 = time.time()
        try:
            out = self.research(topic)
            report = out.get("report", "")
            sources = out.get("sources", [])
            g = self.guard(report, sources)
            res = AgentResult(
                topic=topic,
                arch=self.arch,
                report=report,
                clean_report=g["clean_report"],
                sources=sources,
                citations_total=g["citations_total"],
                citations_fabricated=g["fabricated"],
                cite_acc=g["cite_acc"],
                hallucination_rate=g["hall_rate"],
                elapsed=round(time.time() - t0, 2),
                tokens=self.tracker.total_tokens,
                cost=round(self.tracker.cost_usd, 5),
                ok=True,
            )
        except Exception as e:
            # 三层降级：任何异常都返回诚实结果，而不是崩溃
            res = AgentResult(
                topic=topic,
                arch=self.arch,
                report=f"（调研执行失败：{e}）",
                clean_report=f"（调研执行失败：{e}）",
                elapsed=round(time.time() - t0, 2),
                tokens=self.tracker.total_tokens,
                ok=False,
                notes=[f"error: {e}"],
            )
        return res