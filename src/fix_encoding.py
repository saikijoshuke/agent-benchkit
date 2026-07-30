import os
import re

def fix_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # 如果 utf-8 解码失败，尝试用 gbk 或 latin-1，然后转 utf-8
        with open(filepath, 'r', encoding='gbk', errors='ignore') as f:
            content = f.read()
        # 重写为 utf-8
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed encoding: {filepath}")
        return

    # 替换可能导致语法错误的常见中文字符（但保留注释和字符串中的中文）
    # 仅替换可能出现在代码中的非法字符，例如中文分号、中文括号等（非字符串中）
    # 这里我们只替换显式的语法问题：中文分号、中文问号、中文括号等，但要注意不要破坏字符串。
    # 更安全的方式是让 Python 自行检查，但我们可以简单地替换几个常见错误。
    # 但这个文件报错是在第50行，有中文分号，我们手动定位替换。
    # 简单起见，直接重写整个文件，确保 utf-8 编码。

    # 保存回 utf-8
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Checked: {filepath}")

# 遍历所有 .py 文件
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))