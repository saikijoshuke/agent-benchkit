"""prompts.py — 全部 Prompt 模板。

关键约束（直接针对 cite_acc=0 的引用造假问题）：
- 只允许用 [n] 引用"下方提供的来源编号"，严禁凭空生成 URL；
- 任何无法被来源支撑的论断必须显式标注「（无检索依据）」；
- 这把"引用"从"模型自由发挥"变成"只能指向已检索内容"，从生成端堵死编造。
"""
from __future__ import annotations

from .schema import Source, PlanStep
from .tools import format_sources

SYSTEM_RESEARCH = """你是一个严谨的研究助理。规则（务必遵守）：
1. 只能使用下方「来源[N]」中的内容进行作答，引用时必须写成 [N]（N 为来源编号）。
2. 严禁编造任何 URL、论文编号、统计数字或人名；若来源中没有对应信息，写「（无检索依据）」。
3. 用中文、结构化（分点 / 小节）输出；先给结论，再给证据。
4. 当不同来源冲突时，优先采用 official / media 类高可信来源，并说明分歧。
5. 诚实优先于完整：信息不足就如实说明，不要合理化猜测。"""

USER_SYNTH = """研究主题：{topic}

可用的检索来源（只能引用这些编号）：
{context}

请基于上述来源撰写结构化研究报告。每一条事实性论断后都用 [N] 标注其来源编号。
若某论断无来源支撑，请写「（无检索依据）」。不要输出来源列表以外的任何 URL。"""


def build_synth_messages(topic: str, sources: list[Source]):
    from langchain_core.messages import HumanMessage, SystemMessage
    ctx = format_sources(sources) if sources else "（本次未检索到任何来源）"
    return [
        SystemMessage(content=SYSTEM_RESEARCH),
        HumanMessage(content=USER_SYNTH.format(topic=topic, context=ctx)),
    ]


PLAN_SYSTEM = """你是一个研究规划器。把一个宽泛的研究主题拆成 3-5 个互斥且完备的子问题，
覆盖：定义/背景、核心能力/技术、应用场景、案例/数据、风险/争议、未来趋势。只输出 JSON。"""
PLAN_USER = """研究主题：{topic}
请输出 JSON：{{"steps": [{{"sub_question": "...", "intent": "..."}}]}}，3-5 个。"""


def build_plan_messages(topic: str):
    from langchain_core.messages import HumanMessage, SystemMessage
    return [
        SystemMessage(content=PLAN_SYSTEM),
        HumanMessage(content=PLAN_USER.format(topic=topic)),
    ]


SYNTH_SYSTEM = SYSTEM_RESEARCH

REFLECT_SYSTEM = """你是审稿人。检查下面这份报告里有没有"没有 [N] 引用支撑"的事实性论断。
只输出 JSON：{{"ungrounded": ["论断1", ...], "has_fabricated_url": true/false}}。
若全部论断都有引用支撑且未发现编造 URL，输出 {{"ungrounded": [], "has_fabricated_url": false}}。"""

REFLECT_USER = """报告：
{report}

可用来源编号：{idxs}"""


def build_reflect_messages(report: str, sources: list[Source]):
    from langchain_core.messages import HumanMessage, SystemMessage
    idxs = ", ".join(str(s.idx) for s in sources) or "无"
    return [
        SystemMessage(content=REFLECT_SYSTEM),
        HumanMessage(content=REFLECT_USER.format(report=report, idxs=idxs)),
    ]


CREDIBILITY_RUBRIC = (
    "来源可信度加权规则（v3）：official(官方/文档) > media(权威媒体) > blog(技术博客) > "
    "forum(论坛/社区) > other。合成时高可信来源优先；来自 forum/other 的论断需标注其来源类型，"
    "关键结论不应仅依赖低可信来源。"
)
