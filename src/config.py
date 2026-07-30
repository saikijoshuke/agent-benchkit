# config.py
"""应用配置模块，集中管理环境变量与全局开关。

所有"是否开启某能力"的开关都集中在这里，方便在不改业务代码的情况下做消融实验
（这正是 README / INTERVIEW 中"靠数字说话"思想在工程上的落地）。
"""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ---- LLM ----
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_BASE: str = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # ---- 检索后端 ----
    # 可选值：serpapi | tavily。决定 search() 实际调用哪家搜索服务。
    SEARCH_BACKEND: str = os.getenv("SEARCH_BACKEND", "serpapi").lower()
    # Tavily 凭据（backend=tavily 时必填）
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    TAVILY_MAX_RESULTS: int = int(os.getenv("TAVILY_MAX_RESULTS", "8"))
    # SerpAPI 凭据（backend=serpapi 时必填）
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")
    SERPAPI_ENGINE: str = os.getenv("SERPAPI_ENGINE", "google")   # google | bing | baidu | duckduckgo 等
    SERPAPI_MAX_RESULTS: int = int(os.getenv("SERPAPI_MAX_RESULTS", "8"))

    @classmethod
    def search_max_results(cls) -> int:
        return cls.TAVILY_MAX_RESULTS if cls.SEARCH_BACKEND == "tavily" else cls.SERPAPI_MAX_RESULTS

    # ---- 抗幻觉 / 抗引用造假 核心开关 ----
    # 是否要求模型只引用检索来源的编号（[1][2]），从根本上杜绝编造 URL
    GROUNDED_CITATION: bool = os.getenv("GROUNDED_CITATION", "1") in ("1", "true", "True", "yes")
    # 生成后是否再用 CitationGuard 二次校验并裁剪编造引用
    POST_VERIFY_CITATIONS: bool = os.getenv("POST_VERIFY_CITATIONS", "1") in ("1", "true", "True", "yes")
    # 是否对引用 URL 做真实可达性探测（需联网；关闭则只做"是否在检索结果内"的判定）
    VERIFY_URL_REACHABLE: bool = os.getenv("VERIFY_URL_REACHABLE", "0") in ("1", "true", "True", "yes")
    # 事实合成温度（越低越稳）
    SYNTH_TEMPERATURE: float = float(os.getenv("SYNTH_TEMPERATURE", "0.1"))
    # 规划（拆子问题）温度
    PLAN_TEMPERATURE: float = float(os.getenv("PLAN_TEMPERATURE", "0.2"))

    # ---- 架构开关 ----
    ENABLE_PARALLEL: bool = os.getenv("ENABLE_PARALLEL", "1") in ("1", "true", "True", "yes")
    PARALLEL_WORKERS: int = int(os.getenv("PARALLEL_WORKERS", "5"))
    ENABLE_CREDIBILITY: bool = os.getenv("ENABLE_CREDIBILITY", "1") in ("1", "true", "True", "yes")
    ENABLE_REFLECTION: bool = os.getenv("ENABLE_REFLECTION", "0") in ("1", "true", "True", "yes")
    REFLECTION_ROUNDS: int = int(os.getenv("REFLECTION_ROUNDS", "1"))

    # ---- 缓存 / 成本 ----
    CACHE_DIR: str = os.getenv("CACHE_DIR", os.path.join(os.path.dirname(__file__), "cache"))
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "1") in ("1", "true", "True", "yes")

    # ---- 链路追踪（可选）----
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # ---- 检索超时 ----
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "15"))

    @classmethod
    def validate(cls, require_keys: bool = True) -> None:
        missing = []
        if require_keys:
            if not cls.DEEPSEEK_API_KEY:
                missing.append("DEEPSEEK_API_KEY")
            if cls.SEARCH_BACKEND == "tavily":
                if not cls.TAVILY_API_KEY:
                    missing.append("TAVILY_API_KEY")
            elif cls.SEARCH_BACKEND == "serpapi":
                if not cls.SERPAPI_API_KEY:
                    missing.append("SERPAPI_API_KEY")
            else:
                missing.append(f"SEARCH_BACKEND 取值非法: {cls.SEARCH_BACKEND}（应为 serpapi 或 tavily）")
        if missing:
            raise ValueError(f"missing env: {missing}. copy .env.example to .env")

    @classmethod
    def check_keys(cls) -> list[str]:
        """检测明显是占位符 / 无效的 Key，返回问题列表（空=看起来正常）。

        注意：这只能识别形如 your_xxx_here / sk-xxxx / 全 xxx 的明显占位符，
        无法判断 Key 是否真的在服务商侧有效。真 Key 的鉴权结果以实际调用为准。
        """
        problems: list[str] = []
        placeholders = ("your_", "_here", "xxx", "changeme", "todo", "placeholder", "api_key")
        # 只检查当前后端需要的 Key，避免 serpapi 模式下被"TAVILY_API_KEY 为空"误拦
        checks = {"DEEPSEEK_API_KEY": cls.DEEPSEEK_API_KEY}
        if cls.SEARCH_BACKEND == "tavily":
            checks["TAVILY_API_KEY"] = cls.TAVILY_API_KEY
        elif cls.SEARCH_BACKEND == "serpapi":
            checks["SERPAPI_API_KEY"] = cls.SERPAPI_API_KEY
        else:  # 后端取值非法：两个都查，提示更全
            checks["TAVILY_API_KEY"] = cls.TAVILY_API_KEY
            checks["SERPAPI_API_KEY"] = cls.SERPAPI_API_KEY
        for name, val in checks.items():
            if not val:
                problems.append(f"{name} 为空")
                continue
            low = val.strip().lower()
            if any(tok in low for tok in placeholders):
                problems.append(f"{name} 仍是占位符（{val.strip()[:6]}…），请填入真实 Key")
                continue
            if low.startswith("sk-") and len(val.strip()) < 20:
                problems.append(f"{name} 长度异常（{len(val.strip())} 字符），可能不是完整 Key")
        return problems

    @classmethod
    def as_dict(cls) -> dict:
        return {k: v for k, v in cls.__dict__.items() if not k.startswith("__") and not callable(v)}


settings = Settings()
