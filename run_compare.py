"""架构对比评测：跑全量测试集并生成对比表。
用法:
    python run_compare.py --max-q 60
    python run_compare.py --archs v1 v3 --max-q 10
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.evaluator import run_eval

ARCH_MAP = {
    "v1": ("src.agent", "ResearchAgent"),
    "v2": ("src.agent_v2", "ResearchAgentV2"),
    "v3": ("src.agent_v3", "ResearchAgentV3"),
    "v4": ("src.agent_v4", "ResearchAgentV4"),
}


def load_agent(arch: str):
    mod_path, cls_name = ARCH_MAP[arch]
    mod = importlib.import_module(mod_path)
    return getattr(mod, cls_name)(verbose=False)


def run_compare(archs=None, max_q=None, benchmark=None):
    if archs is None:
        archs = ["v1", "v2", "v3", "v4"]
    results = {}
    for arch in archs:
        print("\n" + "=" * 60)
        print("  Running:", arch)
        print("=" * 60)
        agent = load_agent(arch)
        summary = run_eval(agent.run, max_q=max_q, benchmark_path=benchmark, verbose=False)
        results[arch] = summary["metrics"]

    print("\n\n" + "=" * 72)
    print("  架构对比评测结果")
    print("=" * 72)
    h = "{:>6} | {:>9} | {:>9} | {:>8} | {:>8} | {:>9} | {:>8}".format(
        "版本", "事实准确", "引用真实", "幻觉率", "覆盖率", "耗时(s)", "tokens")
    print(h)
    print("-" * len(h))
    for arch in archs:
        r = results.get(arch, {})
        line = "{:>6} | {:>9} | {:>9} | {:>8} | {:>8} | {:>9} | {:>8}".format(
            arch, r.get("fact_acc", "?"), r.get("cite_acc", "?"),
            r.get("hall_rate", "?"), r.get("coverage", "?"),
            r.get("avg_time", "?"), r.get("avg_tokens", "?"))
        print(line)

    out = {"time": time.strftime("%Y-%m-%d %H:%M"), "max_q": max_q,
           "fabricated_total": {a: results[a].get("fabricated_total", 0) for a in archs},
           "results": results}
    os.makedirs("results", exist_ok=True)
    p = os.path.join("results", "compare_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\nSaved:", p)
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--archs", nargs="+", default=["v1", "v2", "v3", "v4"])
    p.add_argument("--max-q", type=int, default=None)
    p.add_argument("--benchmark", default=None)
    a = p.parse_args()
    run_compare(archs=a.archs, max_q=a.max_q, benchmark=a.benchmark)
