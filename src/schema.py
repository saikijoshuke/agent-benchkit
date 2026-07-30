"""schema.py — 结构化数据类型定义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Source(BaseModel):
    """一条检索来源。idx 为 1-based 编号，供报告以 [idx] 引用。"""
    idx: int
    title: str = ""
    url: str = ""
    content: str = ""
    score: float = 0.0
    source_type: str = "other"   # official | media | blog | forum | other

    def snippet(self, n: int = 600) -> str:
        return (self.content or "").strip().replace("\n", " ")[:n]


class PlanStep(BaseModel):
    sub_question: str
    intent: str = ""


class AgentResult(BaseModel):
    """单个 Agent 对某主题的产出。"""
    topic: str
    arch: str
    report: str = ""                 # 原始报告（可能含编造引用）
    clean_report: str = ""           # 经 CitationGuard 清洗后的报告
    sources: List[Source] = field(default_factory=list)
    citations_total: int = 0
    citations_fabricated: int = 0
    cite_acc: float = 0.0
    hallucination_rate: float = 0.0
    coverage: float = 0.0
    elapsed: float = 0.0
    tokens: int = 0
    cost: float = 0.0
    notes: List[str] = field(default_factory=list)
    ok: bool = True


class BenchmarkItem(BaseModel):
    id: str
    type: str                        # fact | coverage | trap
    question: str
    dimensions: List[str] = field(default_factory=list)   # coverage 类题的要点维度
    expect_admit: bool = False       # trap 类题：期望承认未知/不足


class Metrics(BaseModel):
    fact_acc: float = 0.0
    cite_acc: float = 0.0
    hall_rate: float = 0.0
    coverage: float = 0.0
    avg_time: float = 0.0
    avg_tokens: int = 0
    n: int = 0
    fabricated_total: int = 0
