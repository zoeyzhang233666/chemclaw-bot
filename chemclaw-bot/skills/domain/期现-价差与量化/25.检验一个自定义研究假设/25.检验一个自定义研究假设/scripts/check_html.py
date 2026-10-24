# -*- coding: utf-8 -*-
"""check_html.py — 交付前对单文件 HTML 做结构与内容自检。

检查项
  * 没有外部依赖（无 http(s):// css/js/img 引用），保证离线可打开
  * 标签页数量、每个 tab 的 id 与 nav 按钮一一对应
  * 关键结论/警示是否真的出现在页面上（样本不足、模拟标记、局限）
  * 真实轨道里是否混入了模拟数据标记的统计（防止串轨）
  * 未闭合的 <section>/<table> 粗检
"""
import argparse
import re
import sys

REQUIRED = [
    ("样本不足", "真实轨道必须明确写出样本不足"),
    ("SIMULATED", "模拟数据必须有显式标记"),
    ("未来函数", "必须出现前视偏差相关章节"),
    ("BH", "必须出现多重检验校正"),
    ("回源核验", "必须披露库存来源核验"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    a = ap.parse_args()
    s = open(a.html, encoding="utf-8").read()
    problems, oks = [], []

    ext = re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', s)
    if ext:
        problems.append(f"存在外部外链依赖 {len(ext)} 处：{ext[:3]}")
    else:
        oks.append("无外部资源依赖（离线可用）")

    tabs = re.findall(r'<section class="tab" id="([^"]+)"', s)
    navs = re.findall(r'<button data-t="([^"]+)"', s)
    if tabs != navs:
        problems.append(f"tab 与 nav 不匹配：{tabs} vs {navs}")
    else:
        oks.append(f"{len(tabs)} 个标签页 id 全部对应")

    for kw, why in REQUIRED:
        if kw in s:
            oks.append(f"包含关键内容「{kw}」（{why}）")
        else:
            problems.append(f"缺少「{kw}」（{why}）")

    for tag in ("section", "table", "div"):
        o = len(re.findall(rf"<{tag}[\s>]", s))
        c = len(re.findall(rf"</{tag}>", s))
        if o != c:
            problems.append(f"<{tag}> 开合不匹配：{o} 开 / {c} 闭")
    if not any(p.startswith("<") for p in problems):
        oks.append("主要容器标签开合平衡")

    # 串轨检查：模拟统计表是否出现在真实统计 section
    m = re.search(r'<section class="tab" id="t5">(.*?)</section>\s*<section', s, re.S)
    if m and "SIMULATED" in m.group(1):
        problems.append("真实统计页混入 SIMULATED 内容")
    else:
        oks.append("真实统计页未混入模拟内容")

    print(f"HTML: {a.html}  {len(s)/1024:.1f} KB")
    for o in oks:
        print("  PASS", o)
    for p in problems:
        print("  FAIL", p)
    print("RESULT:", "OK" if not problems else f"{len(problems)} PROBLEM(S)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
