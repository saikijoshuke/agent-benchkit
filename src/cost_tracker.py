"""cost_tracker.py — token / 成本追踪（按 DeepSeek 公开价目粗略估算）。"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class CostTracker:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # DeepSeek-chat 公开价（美元 / 1M tokens），仅作展示用
    PRICE_IN = 0.14
    PRICE_OUT = 0.28

    def add(self, inp: int, out: int) -> None:
        with self._lock:
            self.input_tokens += inp
            self.output_tokens += out
            self.calls += 1

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float:
        return self.input_tokens / 1_000_000 * self.PRICE_IN + self.output_tokens / 1_000_000 * self.PRICE_OUT

    def reset(self) -> None:
        with self._lock:
            self.input_tokens = self.output_tokens = self.calls = 0
