# 运行 / 测试 / 发布指南（v2.0.0）

本文件给你在 `research-agent-v2.0` 目录下完成**本地运行 → 测试验证 → 后续更新发布**的完整步骤。
所有命令都在项目根目录执行（即本文件所在目录）。

> 当前代码已全部离线验证（语法 + 抗造假管线 + 评测器）。**真实联调需要你自备两个 API Key**，
> 因为本环境没有 Key，无法替你跑真实 LLM/搜索调用。

---

## 0. 目录位置
```
C:\Users\wuqi\research-agent-v2.0
```
已 `git init` 并打首个基线提交（`v2.0.0`）。

---

## 1. 环境准备（一次性）

```bash
# 1) Python 3.10+（建议用本机已装版本）
python --version

# 2) 创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\activate          # Windows
#   source .venv/bin/activate    # macOS/Linux

# 3) 安装依赖
pip install -r requirements.txt

# 4) 配置 API Key（必需，真实联调用）
cp .env.example .env
#   然后编辑 .env，填入：
#   DEEPSEEK_API_KEY=sk-xxxx        # 默认 LLM（见 config.py）
#   TAVILY_API_KEY=tvly-xxxx        # 搜索工具（见 src/tools.py）
```

> 若不想用 DeepSeek，可在 `.env` 改 `MODEL_NAME` / `OPENAI_API_KEY` 等（见 `config.py` 顶部）。

---

## 2. 运行步骤（Run）

### 2.1 单次调研（最快验证）
```bash
python app/cli.py --topic "大语言模型在游戏设计中的应用" --arch v2
```
参数说明：
- `--arch`：`v1`（ReAct）| `v2`（Plan-Execute 并行，默认）| `v3`（可信度加权）| `v4`（反思循环，需极致严谨时开）
- `--max-results`：每路检索条数（默认见 `config.py`）
- `--verbose`：打印计划 / 子问题 / 来源
- 输出会写到 `results/<arch>_xxx.md`

### 2.2 四种架构对比（核心可量产卖点）
```bash
python run_compare.py --max-q 60
```
- 跑 60 题基准，输出四架构对比表 + `results/compare_<时间戳>.json`
- 用 `--max-q` 缩小题量做快速冒烟（如 `--max-q 6`）

### 2.3 端到端评测（只看指标）
```bash
python run_eval.py --arch v2 --max-q 60
```
- 计算 5 项指标：`fact_acc / cite_acc / hall_rate / coverage / avg_time`
- 详细逻辑见 `src/evaluator.py`

### 2.4 Web UI（可视化，可选）
```bash
python app/web.py
# 打开终端里的 http://127.0.0.1:7860
```

---

## 3. 测试步骤（Test）

### 3.1 离线验证（无需任何 Key，必跑）
```bash
python verify_fix.py
```
**预期：全部 [PASS]**
- 含编造 URL 的报告被识别（fabricated>0，清洗后 cite_acc<1）
- 只引用真实来源的报告 cite_acc=1.0、fabricated=0
- 覆盖度计算正常、陷阱题诚实承认未知
> 这是证明"引用造假已修复"的硬证据，**每次改了 `src/citation_guard.py` 或 `src/evaluator.py` 后必跑**。

### 3.2 快速冒烟（有 Key 后）
```bash
python app/cli.py --topic "Shap-E 是什么" --arch v2 --verbose
```
检查：
- 报告里 `[1][2]` 都能在文末"来源"区找到对应条目；
- 没有任何 `http(s)://` 直接出现在正文（URL 只能在来源区）；
- 末尾打印 `cite_acc` / `fabricated` 指标。

### 3.3 全量回归（发布前必跑）
```bash
python run_compare.py --max-q 60
```
对照上一次发布的 `results/compare_*.json`，重点看：
- `cite_acc` 是否 ≥ 0.95（回归口径，如发现掉落说明改动破坏了抗造假）；
- `hall_rate` 是否下降；
- `coverage` 是否提升或持平。

### 3.4 改动检查清单（每次提交前）
- [ ] `python verify_fix.py` 全绿
- [ ] 改了引用/评测逻辑 → 跑 3.1
- [ ] 改了 agent 逻辑 → 跑 3.2（至少 v2）
- [ ] `python -m py_compile src/*.py app/*.py` 无报错
- [ ] 更新 `CHANGELOG.md` 对应条目

---

## 4. 后续更新发布步骤（Release）

```bash
# 1) 提交改动
git add -A
git commit -m "feat: ..."

# 2) 升版本号（三选一改多大）
#    补丁 2.0.0 → 2.0.1 / 小版本 2.0.0 → 2.1.0 / 大版本 → 3.0.0
#    编辑 VERSION 文件，并同步 README 顶部 Version badge

# 3) 补 CHANGELOG.md（Fix / Feat / 已知缺口）

# 4) 打 tag 并推送（首次需先连远程）
git tag v2.0.1
git remote add origin git@github.com:saikijoshuke/<repo>.git   # 仅首次
git push origin main --tags

# 5) 在 GitHub 用 tag 创建 Release，正文贴 CHANGELOG 对应条目
```

---

## 5. 常见问题（Troubleshooting）

| 现象 | 原因 | 处理 |
|------|------|------|
| `KeyError: DEEPSEEK_API_KEY` | 没配 Key | 复制 `.env.example`→`.env` 并填值 |
| 报告里出现裸 URL | 抗造假被绕过 | 先跑 `verify_fix.py`，再查 `prompts.py` 的引用约束是否被改 |
| v2 很慢 | 并行检索被限流 | 调大 `config.py` 的 `PARALLEL_WORKERS`（注意 API 配额） |
| `cite_acc` 偏低 | 模型引用了来源区没有的编号 | 检查 `base.py` 的合成 prompt 与 `citation_guard.py` 映射逻辑 |
| `hall_rate` 偏高 | 大量论断无来源 | 开 v4 反思，或调高 `MAX_SEARCH_ROUNDS` |

---

## 6. 与旧仓库合并提示
如果你 GitHub 旧仓库里有历史 `src/` 实现，请先 `git remote add old <旧仓库>` 拉取 `diff`，
按下列映射合并（新结构保持兼容）：
- 旧 `v2/v3/v4` 实现 → 对应 `src/agent_v2.py` / `agent_v3.py` / `agent_v4.py`
- 旧评测 → `src/evaluator.py`
- 入口 → `app/cli.py`（兼容旧 `run_compare.py` 的 `ARCH_MAP`）
