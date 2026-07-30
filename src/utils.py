"""utils.py — 小工具：从 LLM 输出里稳健地抽取 JSON。"""
from __future__ import annotations

import json
import re


def extract_json(text: str):
    """从可能带 ```json 围栏或多余文字的输出中提取第一个 JSON 对象/数组。"""
    if text is None:
        return None
    # 优先尝试整段解析
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    # 去围栏
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass
    # 找第一个 { 或 [ 到匹配的末尾
    for opener, closer in (("{", "}"), ("[", "]")):
        i = text.find(opener)
        if i == -1:
            continue
        depth = 0
        for j in range(i, len(text)):
            if text[j] == opener:
                depth += 1
            elif text[j] == closer:
                depth -= 1
                if depth == 0:
                    frag = text[i:j + 1]
                    try:
                        return json.loads(frag)
                    except Exception:
                        break
    return None
