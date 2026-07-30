"""agent_v2.py — v2: 并行子问题检索 + 汇总合成。

相对 v1 单查询，v2 会先把主题拆成 3–6 个子问题并行检索，再统一合成报告。
这对应 INTERVIEW 里 "v2 覆盖率显著优于 v1" 的预期。
"""
from __future__ import annotations
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage
from src.tools import search
from src.config import settings
from src.base import BaseResearchAgent
from src.schema import Source

PLAN = "将主题拆分为3-6个子问题。只输出JSON: {\"sub_questions\":[\"q1\",\"q2\",...]}"
AGG = "基于以下搜索结果撰写报告。含来源URL.\n结果: {results}\n主题: {topic}"


class ResearchAgentV2(BaseResearchAgent):
    arch = "v2"

    def __init__(self, verbose: bool = False):
        super().__init__(verbose=verbose)
        self._v2_llm = ChatDeepSeek(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_API_BASE,
            temperature=0.3
        )
        self.executor = ThreadPoolExecutor(max_workers=settings.PARALLEL_WORKERS)

    # -------- v2 专用 LLM 封装（保留 v2 原有的温度/调用方式） --------
    def _v2_invoke(self, prompt: str) -> str:
        resp = self._v2_llm.invoke([HumanMessage(content=prompt)])
        return resp.content if isinstance(resp.content, str) else str(resp.content)

    # -------- 子问题规划 --------
    def plan(self, topic: str) -> list[str]:
        resp = self._v2_invoke(PLAN + "\n主题: " + topic)
        try:
            t = resp.strip().replace("```json", "").replace("```", "")
            qs = json.loads(t).get("sub_questions", [])
            print(f"  Plan: {len(qs)} sub-questions")
            return qs[:6]
        except Exception:
            return [topic]

    # 兼容别名：老代码里用的是 _plan
    _plan = plan

    # -------- 并行检索：对每个子问题检索，合并来源并重新编号 --------
    def parallel_search(self, questions: list[str], max_results_per_q: int = 5) -> list[Source]:
        merged: list[Source] = []
        seen_urls: set[str] = set()

        def _search_one(q):
            try:
                return search(q, max_results=max_results_per_q)
            except Exception as e:
                print(f"  [WARN] 检索失败「{q[:30]}…」: {e}")
                return []

        with self.executor as ex:
            futures = {ex.submit(_search_one, q): q for q in questions}
            for f in as_completed(futures):
                q = futures[f]
                sources = f.result()
                print(f"  Done: {q[:30]}...")
                for s in sources:
                    if s.url and s.url in seen_urls:
                        continue
                    if s.url:
                        seen_urls.add(s.url)
                    merged.append(s)
        # 重新编号 1-based
        for i, s in enumerate(merged, 1):
            s.idx = i
        return merged

    # 兼容别名：老代码里 _search_all 返回的是 dict 列表，这里提供同名薄封装供外部参考
    def _search_all(self, questions):
        """已废弃，保留名字避免外部引用报错。请使用 parallel_search()。"""
        return self.parallel_search(questions)

    # -------- 合成 --------
    def synthesize(self, topic: str, sources: list[Source]) -> str:
        # v2 原有的合成风格：把每个子问题的 Q/A 拼接后再让 LLM 汇总
        # 这里改成与 V1/V3 一致的风格：直接基于 sources 列表生成
        # 但为了保留 v2 行为特征，我们仍用 AGG 模板，将 sources 格式化传入
        blocks = []
        for i, s in enumerate(sources, 1):
            blocks.append(
                f"[{i}] {s.title}\n{s.content[:300]}\n来源: {s.url}"
            )
        ctx = "\n\n".join(blocks)[:3000]
        return self._v2_invoke(AGG.format(results=ctx, topic=topic))

    # 兼容别名
    def _aggregate(self, topic, results):
        return self.synthesize(topic, results)

    # -------- 降级报告：LLM 合成失败时，用检索结果拼接 --------
    def _fallback_report(self, topic: str, sources: list[Source], err_msg: str) -> str:
        """LLM 合成失败时的降级方案：直接拼接检索来源作为报告。"""
        print(f"  [WARN] LLM 合成失败（{err_msg}），降级为检索结果摘要")
        lines = [f"# {topic}\n",
                 f"> 注：LLM 合成失败（{err_msg}），以下为检索结果摘要。\n"]
        for i, s in enumerate(sources, 1):
            lines.append(f"## [{i}] {s.title}\n")
            lines.append(f"{s.snippet(400)}\n")
            lines.append(f"来源: {s.url}\n")
        return "\n".join(lines)

    # -------- research（供 BaseResearchAgent.run 调用） --------
    def research(self, topic: str) -> dict:
        print(f"\n[v2] {topic[:50]}...")
        qs = self.plan(topic)
        if not qs:
            return {"report": "[Error] 无法拆解子问题", "sources": []}
        print(f"  Searching {len(qs)} questions in parallel...")
        sources = self.parallel_search(qs)
        print(f"  Generating report...")
        try:
            report = self.synthesize(topic, sources)
        except Exception as e:
            report = self._fallback_report(topic, sources, str(e))
        return {"report": report, "sources": sources}

    # -------- 兼容老接口：原先 v2.run() 返回字符串，现在只在测试代码里调用 --------
    # 真正的 run() 由 BaseResearchAgent 提供，返回 AgentResult


def _dedup_merge(batches: list[list[Source]]) -> list[Source]:
    """合并多轮来源批次，按 URL 去重，重新编号 1-based。"""
    seen: set[str] = set()
    merged: list[Source] = []
    for batch in batches:
        for s in batch:
            if s.url and s.url in seen:
                continue
            if s.url:
                seen.add(s.url)
            merged.append(s)
    for i, s in enumerate(merged, 1):
        s.idx = i
    return merged
