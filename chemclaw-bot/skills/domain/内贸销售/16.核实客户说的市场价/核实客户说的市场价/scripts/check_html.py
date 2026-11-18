#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_html.py — 交付前静态 + 渲染自检（不依赖第三方包）。

检查项：
  1. 占位符是否残留
  2. 是否存在外链（外链 script/link/img、@import url）
  3. ECharts 是否内联
  4. 正文禁用词（预测 / 承诺 / 报价建议类）
  5. 渲染（本机有 Chrome/Edge 时）：无 JS 报错、无失败横幅、KPI 与结论文案正确、图表 canvas 真的画出来
  6. 渲染后数字与 data.json 一致

用法：
  python scripts/check_html.py out/xxx.html build/data.json
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

BANNED = [
    "建议报价", "销售建议价", "底价", "可以降到", "让利", "打折", "包您", "保证采购",
    "预计上涨", "预计下跌", "看涨", "看跌", "抄底", "底部已现", "肯定会", "包准",
]


def find_browser():
    for c in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if os.path.exists(c):
            return c
    for n in ("chrome", "chromium", "google-chrome", "msedge"):
        e = shutil.which(n)
        if e:
            return e
    return None


def strip_html(s):
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
         .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    return re.sub(r"\s+", " ", s)


def grab(dom, el_id):
    m = re.search(r'id="' + re.escape(el_id) + r'"[^>]*>(.*?)(?=</div>|</span>|</td>|<div id=)', dom, re.S)
    return strip_html(m.group(1)) if m else ""


def grab_raw(dom, el_id):
    """保留标签的原始片段，用来检查「单位是否真的是 <small> 元素」。"""
    m = re.search(r'id="' + re.escape(el_id) + r'"[^>]*>(.*?)(?=</div>|</span>|</td>|<div id=)', dom, re.S)
    return m.group(1) if m else ""


def _split(s):
    """把带空格的字符串拆成若干片段，避免内联元素造成的伪空格不匹配。"""
    return [p for p in re.split(r"\s+", s or "") if p]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("data_json", nargs="?")
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()

    # 读取 HTML：刚生成的报告偶尔仍被上一个无头浏览器句柄占着，重试几次再放弃
    import time as _time
    h, last_err = None, None
    for _ in range(12):
        try:
            with open(a.html, "r", encoding="utf-8") as f:
                h = f.read()
            break
        except PermissionError as e:      # 文件被占用（Windows 上常见于残留浏览器进程）
            last_err = e
            _time.sleep(0.5)
    if h is None:
        print(f"== check_html: {os.path.basename(a.html)}")
        print(f"   [FAIL] 无法读取文件（可能被另一个进程占用）：{last_err}")
        return 1
    data = C.load_json(a.data_json) if a.data_json else None
    fails, warns = [], []

    # 1 占位符
    left = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", h)))
    if left:
        fails.append(f"残留占位符：{left}")

    # 2 外链
    ext = re.findall(r'<(?:script|link|img|iframe)[^>]+(?:src|href)\s*=\s*["\'](?:https?:)?//', h, re.I)
    if ext:
        fails.append(f"发现 {len(ext)} 处外部资源引用（应为零外链）")
    if re.search(r"@import\s+url\(", h, re.I):
        fails.append("发现 @import 外链样式")

    # 3 ECharts
    if "registerTheme" not in h or len(re.findall(r"echarts", h)) < 5:
        fails.append("ECharts 未内联")

    # 4 禁用词（去掉脚本/样式后扫正文；渲染后再扫一次动态文本）
    body = strip_html(h)
    hit = sorted({w for w in BANNED if w in body})
    if hit:
        fails.append(f"静态正文出现禁用词：{hit}")

    # 5/6 渲染
    rendered = False
    if not a.no_render:
        br = find_browser()
        if not br:
            warns.append("未找到 Chrome/Edge，跳过渲染检查（静态检查仍执行）")
        else:
            tmp = tempfile.mkdtemp(prefix="chk_")
            local = os.path.join(tmp, "p.html")
            shutil.copyfile(a.html, local)
            url = "file:///" + local.replace("\\", "/")
            try:
                # 加 --disable-extensions/--no-first-run，并在结束后确保进程退出，
                # 否则残留的 chrome 会占着临时文件句柄，导致后续读取 PermissionError。
                p = subprocess.run([br, "--headless", "--disable-gpu", "--no-sandbox",
                                    "--no-first-run", "--disable-extensions",
                                    "--virtual-time-budget=9000", "--dump-dom", url],
                                   capture_output=True, timeout=180)
                dom = p.stdout.decode("utf-8", "replace")
                if len(dom) < 20000:
                    fails.append(f"渲染 DOM 过短（{len(dom)}），页面可能未加载")
                else:
                    rendered = True
                    ban = re.search(r'<div id="ssrBanner">\s*<div class="err">(.*?)</div>', dom, re.S)
                    if ban:
                        fails.append(f"页面报出脚本错误：{strip_html(ban.group(1))[:160]}")
                    canv = len(re.findall(r"<canvas", dom))
                    dyn = strip_html(re.sub(r"<script.*?</script>", " ", dom, flags=re.S | re.I))
                    # 降级模式（没有可用市场区间）：图表位置必须显示明确的缺口说明，
                    # 而不是画一张假图，也不能空着。
                    degraded = bool(data) and (data.get("market", {}).get("low") is None
                                               and data.get("market", {}).get("high") is None)
                    if degraded:
                        if canv > 0:
                            fails.append(f"降级案例不应绘制图表，但出现了 {canv} 个 canvas（可能在画假数据）")
                        for cid in ("bandChart", "trendChart", "regionChart"):
                            blk = grab(dom, cid)
                            if not blk or "无法" not in blk and "无历史" not in blk and "无区域" not in blk:
                                fails.append(f"降级案例图区「{cid}」未显示缺口说明")
                        if "无法验证" not in dyn:
                            fails.append("降级案例未出现「无法验证」字样，可能给出了不该有的结论")
                        warns.append("降级案例：无市场区间，已校验「缺口说明 + 无法验证」，未要求 canvas")
                    else:
                        if canv < 3:
                            fails.append(f"图表 canvas 只有 {canv} 个（至少应有 3：价格带/走势/区域）")
                    hit2 = sorted({w for w in BANNED if w in dyn})
                    if hit2:
                        fails.append(f"渲染后正文出现禁用词：{hit2}")
                    if data:
                        m, c = data["market"], data["comparison"]
                        cust = data["customer"].get("stated_price")
                        need = _split(strip_html(grab(dom, "fSrc"))) + _split(data["meta"].get("product", ""))
                        if m.get("low") is not None:
                            need.append(f"{m['low']:,.0f}")
                        if m.get("high") is not None:
                            need.append(f"{m['high']:,.0f}")
                        if cust is not None:
                            need.append(f"{cust:,.0f}")
                        if c.get("pos") != "undecidable":
                            need.append(f"{c['delta_to_dot']:+,.0f}")
                        need.append(data["verdict"]["label"])
                        for t in need:
                            if t and t not in dom:
                                fails.append(f"渲染后未出现：{t}")
                        # KPI 文本应含单位（单位现在是独立 <small> 元素）
                        # 降级案例（无市场区间）显示「—」，此时不需要单位
                        k3 = grab(dom, "k3")
                        if k3.strip() not in ("—", "", "样本不足") and "元/吨" not in k3:
                            fails.append("首屏 KPI「当日市场参考区间」未显示元/吨")
                        # 反向检查：标签不能被当成文字露出来（历史 bug：+275 <small>元/吨</small>）
                        for kid in ("k1", "k2", "k3", "k4"):
                            kv = grab(dom, kid)
                            if "<small" in kv or "</small" in kv:
                                fails.append(f"KPI {kid} 把 HTML 标签当文字显示了：{kv[:70]}")
                        if "&lt;small&gt;" in dom:
                            fails.append("页面出现被转义的 &lt;small&gt; 文本")
                        # 有数字的 KPI 必须真的有 <small> 元素（而不是纯文本单位）
                        for kid in ("k1", "k3", "k4"):
                            raw = grab_raw(dom, kid)
                            plain = grab(dom, kid).strip()
                            if plain and plain not in ("—", "样本不足", "无法直接折算"):
                                if "<small" not in raw:
                                    fails.append(f"KPI {kid} 缺少 <small> 单位元素：{plain[:60]}")
            except subprocess.TimeoutExpired:
                fails.append("渲染超时")
            except Exception as e:  # noqa: BLE001
                warns.append(f"渲染检查异常：{e}")
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

    print(f"== check_html: {os.path.basename(a.html)} ({os.path.getsize(a.html)/1024:.0f} KB)")
    for w in warns:
        print(f"   [warn] {w}")
    for f_ in fails:
        print(f"   [FAIL] {f_}")
    if not fails:
        print(f"   PASS  渲染={'是' if rendered else '跳过'}  图表 canvas≥3  禁用词=0  外链=0  占位符=0")
        return 0
    print(f"   共 {len(fails)} 项失败")
    return 1


if __name__ == "__main__":
    sys.exit(main())
