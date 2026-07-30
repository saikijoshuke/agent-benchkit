"""report.py — 把调研结果导出为 Markdown / PDF。

PDF 中文需要 CJK 字体（fpdf2 默认不含）。若系统找不到 CJK TTF，则回退为 .md
并给出提示——这是已知限制（原项目 tmp_font_check 系列即在解决此问题）。
"""
from __future__ import annotations

import os
import shutil
from typing import List

from .schema import AgentResult, Source

_CJK_FONT_HINTS = (
    "msyh.ttc", "msyh.ttf",            # 微软雅黑
    "simhei.ttf", "simsun.ttc",        # 黑体 / 宋体
    "NotoSansCJK-Regular.ttc",
    "NotoSansSC-Regular.otf",
    "SourceHanSansSC-Regular.otf",
    "wqy-zenhei.ttc", "wqy-microhei.ttc",
)


def _find_cjk_font() -> str | None:
    roots = [r"C:\Windows\Fonts", "/usr/share/fonts", "/System/Library/Fonts",
             os.path.expanduser("~/.fonts")]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dp, _, fns in os.walk(root):
            for fn in fns:
                low = fn.lower()
                if low.endswith((".ttf", ".ttc", ".otf")) and any(h in low for h in _CJK_FONT_HINTS):
                    return os.path.join(dp, fn)
    return None


def to_markdown(res: AgentResult) -> str:
    lines = [f"# 调研报告：{res.topic}", "",
             f"- 架构：{res.arch}　耗时：{res.elapsed}s　Tokens：{res.tokens}　成本：${res.cost:.4f}",
             f"- 引用真实性 cite_acc：{res.cite_acc}　编造引用数：{res.citations_fabricated}　幻觉率：{res.hallucination_rate}",
             ""]
    lines.append("## 正文")
    lines.append(res.clean_report or res.report)
    lines.append("")
    lines.append("## 检索来源")
    for s in res.sources:
        lines.append(f"[{s.idx}] 《{s.title}》 ({s.source_type}) — {s.url}")
    return "\n".join(lines)


def export_report(res: AgentResult, path: str) -> str:
    """导出报告。path 以 .pdf 结尾时尝试 PDF，否则 Markdown。返回最终文件路径。"""
    if path.endswith(".pdf"):
        font = _find_cjk_font()
        if not font:
            md_path = path[:-4] + ".md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(to_markdown(res))
            return md_path + "  (无 CJK 字体，已回退为 Markdown；安装中文字体后可导出 PDF)"
        try:
            from fpdf import FPDF

            pdf = FPDF()
            pdf.add_page()
            pdf.add_font("CJK", "", font)
            pdf.set_font("CJK", size=11)
            pdf.multi_cell(0, 6, to_markdown(res))
            pdf.output(path)
            return path
        except Exception as e:
            md_path = path[:-4] + ".md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(to_markdown(res))
            return md_path + f"  (PDF 导出失败：{e}；已回退为 Markdown)"
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_markdown(res))
    return path
