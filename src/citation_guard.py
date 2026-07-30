"""citation_guard.py — 抗引用造假的核心模块（可离线测试，不依赖任何 API）。

设计目标（对应 README/INTERVIEW 中暴露的 cite_acc=0.000 问题）：
1. 生成前约束：模型只允许引用检索来源的编号 [1][2]…，从根上杜绝"凭空造 URL"。
2. 生成后校验（本模块）：
   - 把报告中出现的每个 [n] / 裸 URL 与"真实检索到的来源"对齐；
   - 不在检索结果中的引用 => 判定为"编造引用(fabricated)"；
   - 可选地对引用 URL 做真实可达性探测（HTTP 2xx/3xx）。
3. 产出可用于评分与清洗的结果：
   - cite_acc      = 真实且可达的引用 / 全部引用
   - fabricated    = 编造引用数
   - clean_text    = 已裁剪编造引用的干净报告

该模块不调用 LLM，因此可在没有 API Key 的情况下做单元测试与回归验证。
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Iterable, List, Optional
from urllib.parse import urlsplit

import requests

from .schema import Source

_INDEX_RE = re.compile(r"\[(\d+)\]")
_URL_RE = re.compile(r"https?://[^\s）)，。；:：'\"\]]+", re.IGNORECASE)


def normalize_url(u: str) -> str:
    """小写、去尾斜杠、去 fragment，用于宽松匹配。"""
    if not u:
        return ""
    u = u.strip().lower()
    u = u.split("#", 1)[0]
    u = u.rstrip("/")
    return u


def _url_prefix_match(url: str, source_urls: set) -> bool:
    n = normalize_url(url)
    if not n:
        return False
    if n in source_urls:
        return True
    # 容忍追踪参数：source 是前缀，或引用是前缀
    for s in source_urls:
        if n.startswith(s) or s.startswith(n):
            return True
    return False


@dataclass
class Citation:
    marker: str               # 报告中出现的原始片段，如 "[3]" 或 "https://..."
    kind: str                 # "index" | "url"
    source_idx: Optional[int] = None   # 命中到的来源编号（1-based）
    url: Optional[str] = None
    grounded: bool = False    # 是否能在检索来源中找到
    reachable: Optional[bool] = None   # 是否真实可达（仅当开启探测）


@dataclass
class CitationReport:
    citations: List[Citation] = field(default_factory=list)
    total: int = 0
    grounded: int = 0
    reachable: int = 0
    fabricated: int = 0
    clean_text: str = ""
    cite_acc: float = 0.0          # grounded (且可选 reachable) / total
    fabricated_rate: float = 0.0

    @property
    def source_urls(self) -> List[str]:
        return [c.url for c in self.citations if c.url]


def _url_reachable(url: str, timeout: int = 15) -> bool:
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AgentBenchKit/1.0)"
        })
        if r.status_code >= 400:
            # HEAD 可能被拒，回退 GET 探一下
            r = requests.get(url, timeout=timeout, allow_redirects=True, stream=True,
                             headers={"User-Agent": "Mozilla/5.0 (compatible; AgentBenchKit/1.0)"})
            return r.status_code < 400
        return r.status_code < 400
    except Exception:
        return False


def analyze_report(
    text: str,
    sources: Iterable[Source],
    verify_reachable: bool = False,
    timeout: int = 15,
) -> CitationReport:
    """分析一份报告，产出引用校验结果与清洗后的文本。

    Args:
        text: 模型生成的报告（含 [n] 编号引用或裸 URL）。
        sources: 真实检索到的来源列表（Source 含 idx / url）。
        verify_reachable: 是否对引用 URL 做真实可达性探测。
        timeout: 探测超时（秒）。
    """
    src_list = list(sources)
    by_idx = {s.idx: s for s in src_list}
    src_norm = {normalize_url(s.url) for s in src_list if s.url}

    citations: List[Citation] = []
    clean = text

    # 1) 编号引用 [n]
    for m in _INDEX_RE.finditer(text):
        n = int(m.group(1))
        src = by_idx.get(n)
        if src is not None:
            grounded = True
            url = src.url
        else:
            grounded = False
            url = None
        cit = Citation(marker=m.group(0), kind="index", source_idx=n if src else None,
                       url=url, grounded=grounded)
        if verify_reachable and url:
            cit.reachable = _url_reachable(url, timeout)
        citations.append(cit)
        if not grounded:
            # 清洗：删除编造的 [n]
            clean = clean.replace(m.group(0), "", 1)

    # 2) 裸 URL（排除已作为 [n] 来源出现的）
    seen_urls = set()
    for m in _URL_RE.finditer(clean):
        url = m.group(0)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        grounded = _url_prefix_match(url, src_norm)
        cit = Citation(marker=url, kind="url", url=url, grounded=grounded)
        if verify_reachable and grounded:
            cit.reachable = _url_reachable(url, timeout)
        citations.append(cit)
        if not grounded:
            clean = clean.replace(url, "[引用缺失]", 1)

    total = len(citations)
    grounded_n = sum(1 for c in citations if c.grounded)
    reachable_n = sum(1 for c in citations if c.grounded and (c.reachable in (True, None) or not verify_reachable))
    fabricated_n = sum(1 for c in citations if not c.grounded)

    if verify_reachable:
        cite_acc = (grounded_n and sum(1 for c in citations if c.grounded and c.reachable) or 0) / total if total else 1.0
    else:
        cite_acc = (grounded_n / total) if total else 1.0

    # 若没有任何引用，视为满分（诚实的"无依据"比编造强），但 fabricated_rate=0
    if total == 0:
        cite_acc = 1.0

    return CitationReport(
        citations=citations,
        total=total,
        grounded=grounded_n,
        reachable=reachable_n,
        fabricated=fabricated_n,
        clean_text=clean,
        cite_acc=round(cite_acc, 3),
        fabricated_rate=round(fabricated_n / total, 3) if total else 0.0,
    )


# ---------- 论断级幻觉分析（供 Agent 与 Evaluator 共用）----------

_ADMIT = ("无检索依据", "缺乏", "不足", "无法", "不确定", "未知", "尚不清楚",
          "暂无", "没有找到", "未检索到", "未能检索", "尚无定论")
_SENT_SPLIT = re.compile(r"[。！？\n]+")


@dataclass
class ClaimReport:
    total: int = 0            # 有效论断数（已剔除诚实声明）
    grounded: int = 0         # 有真实引用支撑的论断
    admitted: int = 0         # 诚实声明（不计入分母）
    ungrounded: int = 0       # 既无支撑、又非诚实声明的论断
    hall_rate: float = 0.0


def analyze_claims(text: str, citation_report: CitationReport) -> ClaimReport:
    """把报告拆成论断，判断每条是否有真实引用支撑。

    hall_rate = (无支撑论断 + 编造引用) / (有效论断 + 总引用)
    诚实声明（"无检索依据/不确定"等）不计入分母，鼓励诚实而非编造。
    """
    grounded_markers = {c.marker for c in citation_report.citations if c.grounded}
    lines = [ln.strip() for ln in _SENT_SPLIT.split(text) if ln.strip()]
    total = grounded_n = admitted_n = 0
    for ln in lines:
        if ln.startswith("#") or ln.startswith("- ") or ln.startswith("* "):
            # 列表项仍可能是论断，但标题行跳过
            if ln.startswith("#"):
                continue
        has_grounded = any(m in ln for m in grounded_markers)
        if not has_grounded:
            for c in citation_report.citations:
                if c.grounded and c.kind == "url" and c.url and c.url in ln:
                    has_grounded = True
                    break
        if any(k in ln for k in _ADMIT):
            admitted_n += 1
            continue
        total += 1
        if has_grounded:
            grounded_n += 1
    ungrounded = total - grounded_n
    eff = total + citation_report.total
    hall = (ungrounded + citation_report.fabricated) / eff if eff else 0.0
    return ClaimReport(total=total, grounded=grounded_n, admitted=admitted_n,
                       ungrounded=ungrounded, hall_rate=round(hall, 3))
