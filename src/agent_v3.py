"""agent_v3.py — v3: 在 v2 并行架构之上叠加"可信度加权"。

来源按 official > media > blog > forum > other 排序并标注类型，合成时要求
高可信来源优先、关键结论不得仅依赖低可信来源。这直接对应 INTERVIEW 中
"v3 引用真实性显著高于 v1"的预期，并进一步压缩低质来源带来的幻觉。
"""
from __future__ import annotations

from .agent_v2 import ResearchAgentV2
from .prompts import CREDIBILITY_RUBRIC, SYSTEM_RESEARCH
from .schema import Source
from .tools import format_sources

_RANK = {"official": 0, "media": 1, "blog": 2, "forum": 3, "other": 4}


def _order_by_cred(sources: list[Source]) -> list[Source]:
    return sorted(sources, key=lambda s: (_RANK.get(s.source_type, 4), -s.score))


class ResearchAgentV3(ResearchAgentV2):
    arch = "v3"

    def synthesize(self, topic: str, sources: list[Source]) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage
        ordered = _order_by_cred(sources)
        ctx = format_sources(ordered) if ordered else "（本次未检索到任何来源）"
        msgs = [
            SystemMessage(content=SYSTEM_RESEARCH + "\n\n" + CREDIBILITY_RUBRIC),
            HumanMessage(content=(
                f"研究主题：{topic}\n\n可用的检索来源（已按可信度排序，只能引用这些编号）：\n{ctx}\n\n"
                "请基于上述来源撰写结构化研究报告。每条事实性论断后用 [N] 标注来源编号；"
                "来自 forum/other 的论断需标注其来源类型。无来源支撑请写「（无检索依据）」。"
                "不要输出来源列表以外的任何 URL。"
            )),
        ]
        return self._call(msgs)
