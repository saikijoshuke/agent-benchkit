"""cli.py — 命令行入口.

用法：
  python app/cli.py --topic "大语言模型在游戏设计中的应用"
  python app/cli.py --topic "..." --arch v2 --output report.pdf
  python app/cli.py --eval --arch v3 --max-q 60        # 跑评测
  python app/cli.py --eval --max-q 5 --arch v4 --reflect
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.agent import ResearchAgent
from src.agent_v2 import ResearchAgentV2
from src.agent_v3 import ResearchAgentV3
from src.agent_v4 import ResearchAgentV4
from src.evaluator import run_eval
from src.report import export_report

ARCH_MAP = {
    "v1": ResearchAgent,
    "v2": ResearchAgentV2,
    "v3": ResearchAgentV3,
    "v4": ResearchAgentV4,
}


def load_agent(arch: str, verbose: bool):
    return ARCH_MAP[arch](verbose=verbose)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Agent BenchKit — 调研 Agent 评测框架")
    p.add_argument("--topic", "-t", default=None, help="研究主题")
    p.add_argument("--arch", "-a", default="v1", choices=list(ARCH_MAP.keys()))
    p.add_argument("--max-results", "-n", type=int, default=None)
    p.add_argument("--eval", action="store_true", help="跑评测模式（否则单主题调研）")
    p.add_argument("--max-q", type=int, default=None, help="评测题数（默认全量/前5）")
    p.add_argument("--benchmark", default=None, help="自定义测试集路径")
    p.add_argument("--reflect", action="store_true", help="开启 v4 反思循环")
    p.add_argument("--no-credibility", action="store_true")
    p.add_argument("--parallel-workers", type=int, default=None)
    p.add_argument("--no-verify-urls", action="store_true")
    p.add_argument("--output", "-o", default=None, help="导出报告路径(.md/.pdf)")
    p.add_argument("--json", default=None, help="评测结果 JSON 输出路径")
    p.add_argument("--verbose", "-v", action="store_true")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    # 应用命令行开关
    if args.max_results:
        settings.TAVILY_MAX_RESULTS = args.max_results
    if args.reflect:
        settings.ENABLE_REFLECTION = True
    if args.no_credibility:
        settings.ENABLE_CREDIBILITY = False
    if args.parallel_workers:
        settings.PARALLEL_WORKERS = args.parallel_workers
    if args.no_verify_urls:
        settings.VERIFY_URL_REACHABLE = False

    try:
        settings.validate()
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    # 占位符 / 明显无效 Key 快速拦截（避免联网后才报 401 让人摸不着头脑）
    key_problems = settings.check_keys()
    if key_problems:
        print("[ERROR] 检测到 API Key 异常：")
        for p in key_problems:
            print(f"  - {p}")
        print("请打开 .env 文件填入真实 Key：")
        print("  DEEPSEEK_API_KEY=sk-xxxx   （https://platform.deepseek.com）")
        print("  TAVILY_API_KEY=tvly-xxxx   （https://tavily.com,backend=tavily 时）")
        print("  SERPAPI_API_KEY=xxxx       （https://serpapi.com,backend=serpapi 时）")
        sys.exit(1)

    if args.eval:
        arch = args.arch
        print(f"\n=== 评测 arch={arch} max_q={args.max_q or 'all'} ===")
        agent = load_agent(arch, args.verbose)
        out = run_eval(agent.run, max_q=args.max_q, benchmark_path=args.benchmark, verbose=True)
        m = out["metrics"]
        print("\n" + "=" * 60)
        print(f"  评测结果 ({arch})  n={m['n']}")
        print("=" * 60)
        print(f"  事实准确率 fact_acc : {m['fact_acc']}")
        print(f"  引用真实性 cite_acc : {m['cite_acc']}  (编造引用合计 {m['fabricated_total']})")
        print(f"  幻觉率   hall_rate : {m['hall_rate']}")
        print(f"  覆盖率   coverage  : {m['coverage']}")
        print(f"  平均耗时 avg_time  : {m['avg_time']}s   平均tokens: {m['avg_tokens']}")
        if args.json:
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print(f"\nSaved: {args.json}")
        return

    topic = args.topic or input("输入研究主题: ").strip()
    if not topic:
        print("[ERROR] 主题不能为空")
        sys.exit(1)

    agent = load_agent(args.arch, args.verbose)
    res = agent.run(topic)
    print("\n" + "=" * 70)
    print(f"[结果] arch={res.arch}  cite_acc={res.cite_acc}  hall_rate={res.hallucination_rate}"
          f"  fabricated={res.citations_fabricated}  time={res.elapsed}s")
    print("=" * 70)
    print(res.clean_report or res.report)
    print("\n--- 检索来源 ---")
    for s in res.sources:
        print(f"[{s.idx}] 《{s.title}》 ({s.source_type}) {s.url}")

    if args.output:
        final = export_report(res, args.output)
        print(f"\n导出: {final}")


if __name__ == "__main__":
    main()
