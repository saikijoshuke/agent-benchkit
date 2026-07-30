# 仓库重命名迁移指南

## 推荐新名称

| 新名称 | 侧重 |
|--------|------|
| `agent-eval-framework` | 评测框架（推荐） |
| `llm-research-bench` | 评测基准 |
| `plan-execute-agent` | 架构本身 |

## 迁移步骤

### 本地迁移

```bash
# 重命名文件夹
mv agent-benchkit agent-eval-framework
cd agent-eval-framework

# 更新所有文件中的 import 路径引用（如果有）
grep -rl "agent-benchkit" . --include="*.py" --include="*.md" 2>/dev/null
# 手动检查上面命令输出的文件中是否引用了旧路径
```

### GitHub 远程迁移

```bash
# 1. 在 GitHub 网页端创建一个新仓库
#    https://github.com/new
#    仓库名填新名称（如 agent-eval-framework）
#    不要勾 Initialize with README

# 2. 更新 remote 地址
git remote set-url origin https://github.com/saikijoshuke/agent-eval-framework.git

# 3. 推送到新仓库
git push -u origin master
```

### 注意
- 旧仓库不删除，两个仓库共存一段时间
- 更新 README 中的仓库链接
- 如果发布了 PyPI 包，确保 `pyproject.toml` 中的 URL 也更新