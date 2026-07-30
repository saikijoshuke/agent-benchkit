"""agent.py — v1: ReAct 基线。

单一检索 + 受约束合成。作为对照基线，重点验证"只引用检索来源"这一约束本身
就能把 cite_acc 从 0 拉到接近 1。
"""
from __future__ import annotations

from .base import BaseResearchAgent


class ResearchAgent(BaseResearchAgent):
    arch = "v1"

    def research(self, topic: str) -> dict:
        sources = self.retrieve(topic)
        report = self.synthesize(topic, sources)
        return {"report": report, "sources": sources}
