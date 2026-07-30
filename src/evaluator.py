"""evaluator.py — 自动化评测框架（5 项指标）。

指标定义（与 README 对齐，且可在无 API Key 的情况下确定性计算）：
- cite_acc   : 真实且可达的引用 / 全部引用（抗"引用造假"核心指标）
- hall_rate  : (无支撑论断 + 编造引用) / (有效论断 + 总引用)
- coverage   : 覆盖度题——报告命中的要点维度 / 期望维度
- fact_acc   : 事实题用 LLM 裁判（可选，FACT_JUDGE=1）；否则用"引用真实性+低幻觉"代理；
               陷阱题——诚实承认未知且未编造则记 1，否则 0
- avg_time   : 单题平均耗时（秒）

评测链路：测试集 -> Agent 逐题执行 -> 引用校验 + 要点匹配 + 幻觉检测 -> 指标。
"""
from __future__ import annotations

import json
import os
import time
from typing import Callable, List

from src.config import settings
from .citation_guard import analyze_claims, analyze_report
from .schema import AgentResult, BenchmarkItem, Metrics, Source

_ADMIT = ("无检索依据", "缺乏", "不足", "无法", "不确定", "未知", "尚不清楚",
          "暂无", "没有找到", "未检索到", "未能检索", "尚无定论", "（无检索依据）")


def load_benchmark(path: str | None = None) -> List[BenchmarkItem]:
    path = path or os.path.join(os.path.dirname(__file__), "..", "testsets", "benchmark_v1.json")
    path = os.path.abspath(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", data) if isinstance(data, dict) else data
    return [BenchmarkItem(**it) for it in items]


def _coverage_of(report: str, dims: List[str]) -> float:
    if not dims:
        return 1.0
    hit = 0
    for d in dims:
        # 维度可能是短语，命中其子串或前 4 个字即可
        key = d[:4] if len(d) >= 4 else d
        if key and key in report:
            hit += 1
    return hit / len(dims)


def _admitted(report: str) -> bool:
    return any(k in report for k in _ADMIT)


def _judge_factuality(question: str, report: str, sources: List[Source]) -> float:
    """可选 LLM 裁判：1=充分且无明显事实错误，0=严重缺失/错误。需 FACT_JUDGE=1。"""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from .llm import get_llm
        llm = get_llm(temperature=0.0)
        src_ctx = "\n".join(f"[{s.idx}] {s.title}" for s in sources[:8])
        msgs = [
            SystemMessage(content="你是严谨的事实评测员。只输出一个 0 到 1 之间的小数，"
                                   "表示报告对问题的回答充分且无事实硬伤的程度。不要解释。"),
            HumanMessage(content=f"问题：{question}\n可用来源：{src_ctx}\n报告：{report}\n分数："),
        ]
        out = llm.invoke(msgs).content
        import re
        m = re.search(r"0(\.\d+)?|1(\.0+)?", str(out))
        return float(m.group(0)) if m else 0.5
    except Exception:
        return 0.5


def run_eval(
    agent_run: Callable[[str], AgentResult | dict],
    max_q: int = 5,
    benchmark_path: str | None = None,
    verbose: bool = True,
) -> dict:
    """对某个 Agent 跑评测，返回 {metrics, records}。"""
    items = load_benchmark(benchmark_path)
    if max_q and max_q < len(items):
        items = items[:max_q]

    cite_accs, halls, covs, facts, times, toks = [], [], [], [], [], []
    records = []
    enable_judge = os.getenv("FACT_JUDGE", "0") in ("1", "true", "True")

    for it in items:
        t0 = time.time()
        res = agent_run(it.question)
        if isinstance(res, dict) and not isinstance(res, AgentResult):
            res = AgentResult(**{k: res.get(k) for k in AgentResult.model_fields}, ok=True) if "topic" in res else AgentResult(topic=it.question, report=str(res))
        elapsed = getattr(res, "elapsed", round(time.time() - t0, 2))
        # 独立审计：对"原始报告"做引用校验（而非 agent 已清洗过的版本），
        # 这样才能真实暴露编造引用；clean_report 仅作展示。
        report = getattr(res, "report", "") or getattr(res, "clean_report", "")
        sources = getattr(res, "sources", []) or []

        cg = analyze_report(report, sources, verify_reachable=settings.VERIFY_URL_REACHABLE,
                            timeout=settings.REQUEST_TIMEOUT)
        cl = analyze_claims(report, cg)
        cite_i = cg.cite_acc
        hall_i = cl.hall_rate

        if it.type == "coverage":
            cov_i = _coverage_of(report, it.dimensions)
            covs.append(cov_i)
            fact_i = cov_i
        elif it.type == "trap":
            admitted = _admitted(report)
            fact_i = 1.0 if (admitted and cg.fabricated == 0) else 0.0
            cov_i = None
        else:  # fact
            if enable_judge:
                fact_i = _judge_factuality(it.question, report, sources)
            else:
                fact_i = round(cite_i * 0.6 + (1 - hall_i) * 0.4, 3)
            cov_i = None

        cite_accs.append(cite_i)
        halls.append(hall_i)
        facts.append(fact_i)
        times.append(elapsed)
        toks.append(getattr(res, "tokens", 0) or 0)

        records.append({
            "id": it.id, "type": it.type, "question": it.question,
            "cite_acc": cite_i, "hall_rate": hall_i, "fact_acc": fact_i,
            "coverage": cov_i, "fabricated": cg.fabricated,
            "elapsed": elapsed, "ok": getattr(res, "ok", True),
        })
        if verbose:
            print(f"  [{it.id}/{it.type}] cite={cite_i:.2f} hall={hall_i:.2f} fact={fact_i:.2f}"
                  + (f" cov={cov_i:.2f}" if cov_i is not None else ""))

    metrics = Metrics(
        fact_acc=round(sum(facts) / len(facts), 3) if facts else 0.0,
        cite_acc=round(sum(cite_accs) / len(cite_accs), 3) if cite_accs else 0.0,
        hall_rate=round(sum(halls) / len(halls), 3) if halls else 0.0,
        coverage=round(sum(covs) / len(covs), 3) if covs else 0.0,
        avg_time=round(sum(times) / len(times), 2) if times else 0.0,
        avg_tokens=int(sum(toks) / len(toks)) if toks else 0,
        n=len(records),
        fabricated_total=sum(r["fabricated"] for r in records),
    )
    return {"metrics": metrics.model_dump(), "records": records}
