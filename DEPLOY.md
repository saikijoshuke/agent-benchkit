# Hugging Face Spaces 部署指南

## 步骤

1. 访问 https://huggingface.co/new-space
2. Space Name 填：`agent-eval-framework`
3. License 选 MIT
4. Space SDK 选 Gradio
5. Space Hardware 选 CPU free
6. 点 Create Space

7. 在 Settings → Repository Secret 中添加环境变量：
   - `DEEPSEEK_API_KEY` = 你的 DeepSeek Key
   - `TAVILY_API_KEY` = 你的 Tavily Key
   - `DEEPSEEK_API_BASE` = https://api.deepseek.com/v1

8. 本地推送到 Space：

```bash
git remote add space https://huggingface.co/spaces/你的用户名/agent-eval-framework
git push space master
```

9. 在 Space Settings 中配置限流（可选）：
   - 在 app/web.py 中添加 gradio 的 queue 配置
   - 或者用 Cloudflare 做反向代理限流

## 限流配置

在 web.py 的 demo.launch() 中添加：

```python
demo.queue(default_concurrency_limit=1)
demo.launch(server_name='0.0.0.0', server_port=7860, share=False)
```

如果每个 IP 限制 5 次/小时，可以在 app/web.py 中加一个简单的内存计数器。