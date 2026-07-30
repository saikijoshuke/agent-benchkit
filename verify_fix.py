"""verify_fix.py — 离线验证"引用造假"修复（无需 API Key）。

它直接驱动 citation_guard + evaluator 的确定性逻辑，证明：
1. 编造的 URL / 越界编号会被识别为 fabricated，并从清洗文本中剔除；
2. 只引用真实检索来源的干净报告 cite_acc=1.0、fabricated=0；
3. 原 README 中 cite_acc=0.000 的根因（模型自由编造 URL）在此管线中被堵死。

运行：python verify_fix.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.citation_guard import analyze_claims, analyze_report
from src.evaluator import _coverage_of
from src.schema import Source

# 模拟"真实检索到的来源"
SOURCES = [
    Source(idx=1, title="OpenAI 发布 Shap-E", url="https://openai.com/research/shap-e",
           content="Shap-E 是 OpenAI 提出的文本生成 3D 模型。", source_type="official"),
    Source(idx=2, title="AI Dungeon 与 GPT", url="https://aidungeon.io/about",
           content="AI Dungeon 早期基于 GPT-2 做交互式文字冒险。", source_type="media"),
    Source(idx=3, title="Stable Diffusion 权重", url="https://stability.ai/stable-diffusion",
           content="Stable Diffusion 由 Stability AI 发布开源权重。", source_type="official"),
]


def banner(t: str):
    print("\n" + "=" * 64)
    print(t)
    print("=" * 64)


def case_fabricated():
    banner("CASE 1 — 含编造引用的报告（模拟修复前的 v1 输出）")
    report = (
        "大模型在游戏里用途广泛[1]。AI Dungeon 基于 GPT-2[2]。"
        "此外，有研究指出某模型能让留存提升 300%[9]。"  # [9] 越界
        "另据 https://fake-news.example.com/proof 报道，图灵奖已颁给某游戏 AI 团队。"  # 编造 URL
    )
    cg = analyze_report(report, SOURCES, verify_reachable=False)
    cl = analyze_claims(report, cg)
    print("原始报告:\n ", report)
    print("\n清洗后报告:\n ", cg.clean_text)
    print(f"\ncite_acc={cg.cite_acc}  fabricated={cg.fabricated}  total={cg.total}")
    print(f"hall_rate={cl.hall_rate}  (无支撑论断={cl.ungrounded}, 诚实声明={cl.admitted})")
    assert cg.fabricated == 2, f"应识别 2 处编造引用，实际 {cg.fabricated}"
    assert cg.cite_acc < 1.0
    print("\n[PASS] 编造引用被识别并剔除 ✓")


def case_clean():
    banner("CASE 2 — 只引用真实来源的报告（修复后的目标态）")
    report = (
        "Shap-E 可文本生成 3D[1]。AI Dungeon 早期基于 GPT-2[2]。"
        "Stable Diffusion 提供开源权重[3]。关于其对留存的具体提升幅度（无检索依据）。"
    )
    cg = analyze_report(report, SOURCES, verify_reachable=False)
    cl = analyze_claims(report, cg)
    print("报告:\n ", report)
    print(f"\ncite_acc={cg.cite_acc}  fabricated={cg.fabricated}  total={cg.total}")
    print(f"hall_rate={cl.hall_rate}")
    assert cg.fabricated == 0
    assert cg.cite_acc == 1.0
    print("\n[PASS] 干净报告 cite_acc=1.0、fabricated=0 ✓")


def case_coverage():
    banner("CASE 3 — 覆盖度题要点命中")
    report = "大模型用于 NPC 对话的动态对话生成、情绪与性格建模、玩家行为自适应、多语言支持，并关注成本与延迟。"
    dims = ["动态对话生成", "情绪与性格建模", "玩家行为自适应", "多语言支持", "成本与延迟", "安全与内容审核"]
    cov = _coverage_of(report, dims)
    print(f"命中 {cov:.2f}  (期望 5/6 ≈ 0.83)")
    assert cov >= 0.8
    print("\n[PASS] 覆盖度计算正常 ✓")


def case_trap():
    banner("CASE 4 — 陷阱题：诚实承认未知（不应编造）")
    report = "关于该未公开的内部数据（无检索依据），无法核实其具体数值，故不给出结论。"
    cg = analyze_report(report, [], verify_reachable=False)
    admitted = any(k in report for k in ("无检索依据", "无法", "未知"))
    print(f"admitted={admitted}  fabricated={cg.fabricated}")
    assert admitted and cg.fabricated == 0
    print("\n[PASS] 陷阱题诚实通过 ✓")


if __name__ == "__main__":
    case_fabricated()
    case_clean()
    case_coverage()
    case_trap()
    banner("全部离线校验通过：引用造假修复管线工作正常")
    print("\n对比 README 旧指标（v1 cite_acc=0.000）→ 本管线可稳定达到 cite_acc=1.0（当报告只引用真实来源时）。")
