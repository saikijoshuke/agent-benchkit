# Changelog

本文件用于跟踪版本迭代，便于后续更新发布。请在每个发布版本合并时追加条目。

## [2.0.0] - 2026-07-30

### 修复（Fix）
- **引用造假（cite_acc=0.000）**：新增 `src/citation_guard.py`，生成端只许引用检索来源编号 `[N]`，
  生成后二次审计并裁剪编造 URL；可选对 URL 做真实可达性探测。
- **v2/v3/v4 并行架构崩溃（fact_acc=0、hall_rate=1.0）**：v2 用 `asyncio + ThreadPoolExecutor`
  真正并行检索子问题（信号量限流、去重合并），全部架构继承 `base.py` 并带三层降级，绝不返回空壳。
- **评测无法暴露造假**：评测器改为对**原始报告**做独立引用审计（此前对"已清洗报告"重算导致编造永远看不见）。

### 新增（Feat）
- 四套可消融对比架构：v1 ReAct / v2 Plan-Execute 并行 / v3 可信度加权 / v4 反思循环。
- 降幻觉：合成温度 0.1 + 论断级引用绑定 + 反思补检索；诚实声明（"无检索依据"）不计入幻觉分母。
- 提覆盖：Plan 拆子问题多路检索 + 结构化维度抽取；覆盖度用要点命中率量化。
- 60 题基准（`testsets/benchmark_v1.json`）：20 事实 / 20 覆盖 / 20 陷阱，陷阱题断言"无检索依据"。
- CLI（`app/cli.py`）+ Web UI（`app/web.py`）+ 成本追踪（`src/cost_tracker.py`）+ 搜索缓存 + Langfuse 接入位。
- 离线验证脚本 `verify_fix.py`（无需 API Key 即可证明抗造假有效）。

### 已知缺口（Todo，待后续版本）
- 真实联调需自备 `DEEPSEEK_API_KEY` / `TAVILY_API_KEY`，本版逻辑已离线验证但未跑过真实 LLM 调用。
- 若 GitHub 旧仓库有历史 `src/` 实现，请 diff 合并（新结构保持 `run_compare.py` 的 `ARCH_MAP` 兼容）。
- `doc.md`（领域文章）与旧 `requirements.txt` 在原分享链接中为错误页，已重建。

## [1.x] - 早期原型
- 初版 v1 ReAct 调研原型与评测框架雏形（见旧 README 对比表：cite_acc=0、hall_rate=0.75、coverage=0.21）。
