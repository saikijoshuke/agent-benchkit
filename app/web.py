"""web.py — Gradio Web UI。

启动：python run_web.py  ->  http://127.0.0.1:7860
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.agent import ResearchAgent
from src.agent_v2 import ResearchAgentV2
from src.agent_v3 import ResearchAgentV3
from src.agent_v4 import ResearchAgentV4

ARCH_MAP = {
    "v1 (ReAct)": ResearchAgent,
    "v2 (Plan+并行)": ResearchAgentV2,
    "v3 (可信度加权)": ResearchAgentV3,
    "v4 (反思循环)": ResearchAgentV4,
}


def build_ui():
    import gradio as gr

    def run(topic, arch_name, max_results, reflect):
        if not topic or not topic.strip():
            return "请输入研究主题", ""
        settings.TAVILY_MAX_RESULTS = int(max_results or settings.TAVILY_MAX_RESULTS)
        settings.ENABLE_REFLECTION = bool(reflect)
        try:
            settings.validate()
        except ValueError as e:
            return f"[ERROR] {e}", ""
        agent = ARCH_MAP[arch_name](verbose=False)
        res = agent.run(topic.strip())
        report = res.clean_report or res.report
        meta = (f"架构={res.arch} | 引用真实性={res.cite_acc} | 编造引用={res.citations_fabricated} | "
                f"幻觉率={res.hallucination_rate} | 耗时={res.elapsed}s | tokens={res.tokens}")
        sources = "\n".join(f"[{s.idx}] 《{s.title}》 ({s.source_type}) {s.url}" for s in res.sources)
        return report, meta + "\n\n" + sources

    with gr.Blocks(title="Agent BenchKit") as demo:
        gr.Markdown("# Agent BenchKit — 调研 Agent（抗引用造假版）\n"
                    "只引用真实检索来源，生成后自动校验并裁剪编造引用。")
        with gr.Row():
            topic = gr.Textbox(label="研究主题", placeholder="例如：大语言模型在游戏设计中的应用", scale=4)
            arch = gr.Dropdown(list(ARCH_MAP.keys()), value="v1 (ReAct)", label="架构")
        with gr.Row():
            max_results = gr.Number(value=settings.TAVILY_MAX_RESULTS, label="检索条数", precision=0)
            reflect = gr.Checkbox(value=False, label="v4 反思循环")
            btn = gr.Button("开始调研", variant="primary")
        report = gr.Markdown(label="研究报告")
        sources = gr.Textbox(label="来源与指标", lines=10)
        btn.click(run, [topic, arch, max_results, reflect], [report, sources])
    return demo


def main():
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)


if __name__ == "__main__":
    main()
