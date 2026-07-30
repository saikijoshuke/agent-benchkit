# Agent BenchKit · 可量产的调研 Agent 系统

[![Version](https://img.shields.io/badge/Version-2.0.0-blue)](VERSION)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

> **当前版本：v2.0.0** — 重建为可量产的调研 Agent 系统，包含抗引用造假管线、v1–v4 四套可消融对比架构、60 题基准与端到端评测。

Agent BenchKit 把"调研 Agent 到底好不好"变成**可量化、可复现、可比较**的实验结果：
用不同 Agent 架构完成主题调研，自动计算 5 项指标，并用一套**抗引用造假管线**把
"模型编造 URL / 编造事实"从根上堵死。

---

## 一、本轮修复了什么（你遇到的两个核心问题）

你发布的旧版本在 60 题评测里暴露了两个致命问题（见旧 README 的对比表）：

| 问题 | 旧版表现 | 根因 | 本版修复 |
|------|----------|------|----------|
| **引用造假** | 所有版本 `cite_acc = 0.000` | LLM 自由生成 URL，没有任何约束 | 生成端只许引用检索来源编号 `[N]`；生成后再用 `CitationGuard` 二次校验并裁剪编造引用 |
| **v2/v3/v4 并行架构崩溃** | `fact_acc = 0.000`、`hall_rate = 1.000` | 并行检索分支异常/超时后返回空报告 | v2 用 `asyncio + ThreadPoolExecutor` 真正并行检索子问题，异常走三层降级，绝不返回空壳 |

> 离线验证（`python verify_fix.py`，**无需 API Key**）已证明：含编造 URL 的报告会被识别并剔除，
> 只引用真实来源的报告 `cite_acc = 1.000`、`fabricated = 0`。

---

## 二、项目差异化亮点（为什么不是又一个 RAG demo）

1. **生成即约束 + 生成后审计的双重抗造假**
   不只靠 prompt 提醒，而是把"引用"变成"只能指向已检索内容编号"的硬约束，并由独立的
   `CitationGuard` 做审计级校验（含可选的真实 URL 可达性探测）。这是把"引用真实性"做成
   **可量化指标**而非口头承诺。

2. **四种架构同台对比，且可消融**
   ReAct(v1) / Plan-Execute 并行(v2) / 可信度加权(v3) / 反思循环(v4) 共用同一套管线，
   通过 `config.py` 的开关做消融实验——直接回答"并行有没有用、反思值不值"。

3. **诚实优先的评测设计**
   60 题覆盖 **事实 / 覆盖度 / 陷阱** 三类：陷阱题专门考察"不知道时会不会承认"，
   编造引用直接判 hallucination，鼓励"说不知道"而非"编一个"。

4. **生产级工程化**
   检索缓存、token/成本追踪、异常三层降级、CLI + Gradio Web 双入口、可选 Langfuse 链路追踪、
   结构化输出（Pydantic）、报告导出（Markdown/PDF）。

5. **靠数字说话的闭环**
   `python run_compare.py --max-q 60` 一键产出可复现的对比表与 JSON，方便发版前回归。

---

## 三、四种架构

| 版本 | 策略 | 解决的问题 | 默认 |
|------|------|-----------|------|
| **v1** | ReAct：单路检索 + 受约束合成 | 基线对照 | ✅ |
| **v2** | Plan-and-Execute：**并行**检索多个子问题 | 覆盖度 + 耗时（并行纯收益） | ✅ |
| **v3** | v2 + **可信度加权**（official>media>blog>forum） | 低质来源带来的幻觉 | ✅ |
| **v4** | v3 + **反思循环**（找无支撑论断→补检索/标注） | 极致严谨场景 | 默认关闭（`ENABLE_REFLECTION=1`） |

> 设计取舍（见 INTERVIEW.md）：v2 性价比最高（覆盖 ~70% 场景）；v4 反思循环代价高，
> 只在需要极致严谨时开启。

---

## 四、抗引用造假管线（核心）

```
检索(Tavily) ──► 来源编号 [1..k]
                     │
                     ▼
LLM 合成（只允许写 [N]，禁止造 URL）
                     │
                     ▼
CitationGuard.analyze_report()
  · 把报告中每个 [N] / 裸 URL 与真实来源对齐
  · 不在检索结果中 ⇒ 判定 fabricated，从文本剔除
  · 可选：对引用 URL 做 HTTP 可达性探测
                     │
                     ▼
清洗后报告 + {cite_acc, fabricated, hall_rate}
```

幻觉率定义：`hall_rate = (无支撑论断 + 编造引用) / (有效论断 + 总引用)`，
诚实声明（"无检索依据/不确定"等）不计入分母。

---

## 五、评测指标

| 指标 | 含义 |
|------|------|
| `fact_acc` | 事实准确率（事实题用 LLM 裁判，可选；否则用"引用真实+低幻觉"代理；陷阱题考察诚实度） |
| `cite_acc` | 引用真实性 = 真实且可达的引用 / 全部引用 |
| `hall_rate` | 幻觉率 |
| `coverage` | 覆盖度题命中要点维度比例 |
| `avg_time` | 单题平均耗时 |

---

## 六、快速开始

```bash
git clone <你的仓库地址> && cd agent-benchkit
pip install -r requirements.txt
cp .env.example .env        # 填入 DEEPSEEK_API_KEY / TAVILY_API_KEY
```

```bash
# 单主题调研（v1）
python app/cli.py --topic "大语言模型在游戏设计中的应用"

# 指定架构 + 导出报告
python app/cli.py --topic "..." --arch v2 --output report.pdf

# 跑评测（全量 60 题）
python run_compare.py --max-q 60

# 单架构评测 + 结果落盘
python run_eval.py --arch v3 --max-q 60 --json results/v3.json

# Web UI
python run_web.py            # http://127.0.0.1:7860
```

**离线校验抗造假修复（无需 Key）：**
```bash
python verify_fix.py
```

---

## 七、项目结构

```
agent-benchkit/
  app/
    cli.py          # 命令行入口
    web.py          # Gradio Web 界面
  src/
    agent.py        # v1 ReAct
    agent_v2.py     # v2 Plan-Execute 并行
    agent_v3.py     # v3 可信度加权
    agent_v4.py     # v4 反思循环
    base.py         # 共享基类（检索/LLM/校验/汇总）
    citation_guard.py  # 抗引用造假核心（可离线测试）
    tools.py        # Tavily 检索 + 来源分类 + URL 探测
    prompts.py      # 受约束 Prompt 模板
    schema.py       # Pydantic 结构化类型
    llm.py          # LLM 工厂
    cost_tracker.py # token/成本追踪 + 检索缓存
    evaluator.py    # 5 指标自动评测
    report.py       # 报告导出（Markdown/PDF）
    utils.py        # JSON 抽取等工具
  testsets/
    benchmark_v1.json   # 60 题（事实20 / 覆盖20 / 陷阱20）
    _gen_benchmark.py   # 基准生成器（便于扩展规模）
  results/             # 评测对比 JSON
  config.py            # 配置与功能开关
  run.py / run_compare.py / run_eval.py / run_web.py
  requirements.txt
  .env.example
  verify_fix.py        # 离线抗造假验证
```

---

## 八、已知限制 / 后续

- PDF 中文导出依赖系统 CJK 字体；缺失时自动回退为 Markdown（原项目 `tmp_font_check` 系列即在解决此问题）。
- URL 可达性探测用 `requests` 扫静态页，SPA 抓不到；生产级可换 Playwright（`VERIFY_URL_REACHABLE=1`）。
- `fact_acc` 的事实题默认用代理指标，开启 `FACT_JUDGE=1` 可做 LLM 裁判（更准但更贵）。
- 下一步：引入 MMLU / HotpotQA 等公开数据集交叉验证，扩大测试集，优化 Web 展示。

## 许可证

MIT。欢迎 Issue / PR。
