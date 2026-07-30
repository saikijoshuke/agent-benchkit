"""一键运行评测（默认全量 60 题）。"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.evaluator import run_eval
from src.agent import ResearchAgent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arch", default="v1", choices=["v1", "v2", "v3", "v4"])
    p.add_argument("--max-q", type=int, default=None)
    p.add_argument("--benchmark", default=None)
    p.add_argument("--json", default=None)
    a = p.parse_args()

    if a.arch == "v1":
        agent = ResearchAgent(verbose=False)
    elif a.arch == "v2":
        from src.agent_v2 import ResearchAgentV2 as A
        agent = A(verbose=False)
    elif a.arch == "v3":
        from src.agent_v3 import ResearchAgentV3 as A
        agent = A(verbose=False)
    else:
        from src.agent_v4 import ResearchAgentV4 as A
        agent = A(verbose=False)

    out = run_eval(agent.run, max_q=a.max_q, benchmark_path=a.benchmark, verbose=True)
    m = out["metrics"]
    print("\n指标:", m)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            import json as _j
            _j.dump(out, f, ensure_ascii=False, indent=2)
        print("Saved:", a.json)


if __name__ == "__main__":
    main()
