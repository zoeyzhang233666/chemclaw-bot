"""
check_html.py — 交付前的 HTML 静态 + 结构校验（不需要浏览器）。

检查：占位符残留、内联 ECharts、数据块可被 JSON 解析、九大板块元素是否齐全、
来源 id 与正文引用一致、禁用词、缺口区块存在、URL 是否为 http(s)。

  python check_html.py out/xxx.html
返回码非 0 = 不可交付。
"""
import argparse
import json
import os
import re
import sys

REQUIRED_IDS = ["title", "kpiGrid", "chartTrade", "chartPie", "chartPartners", "tradeTable", "partnerTable",
                "chinaTable", "exportTable", "localSupply", "consumerGrid", "downstreamGrid",
                "tariffTable", "ntmList", "relTimeline", "gapGrid", "verifyTable", "srcList", "mapTable",
                "drawer", "dlg", "handoffGrid"]
SECTIONS = ["sec-overview", "sec-trade", "sec-supply", "sec-downstream", "sec-policy", "sec-gaps", "sec-sources"]
BANNED = ["__DATA__", "__TITLE__", "__ECHARTS__", "[object Object]", "锟斤拷"]
# NaN / undefined / null are legitimate in our own guards (isNaN, ==null) — checked as visible text below
PREDICTIVE = ["预计将", "必将", "一定会", "毫无疑问", "保证可以", "肯定能"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--min-cn", type=int, default=0, help="正文最少中文字数（防空白报告）")
    a = ap.parse_args()
    h = open(a.html, encoding="utf-8").read()
    errs, warns, info = [], [], []

    size = os.path.getsize(a.html) / 1048576.0
    info.append("文件 %.2f MB" % size)
    if "__ECHARTS__" in h:
        errs.append("ECharts 未内联：图表在离线环境会全部空白")
    elif "echarts" not in h:
        errs.append("未找到 echarts 脚本")
    info.append("ECharts 内联 %s" % ("是" if "__ECHARTS__" not in h and "echarts" in h else "否"))

    # only audit our own code: strip the vendored library and the data block
    body = h
    blocks = re.findall(r"<script>(.*?)</script>", h, re.S)
    if len(blocks) >= 2:
        body = h.replace(blocks[0], "")          # vendor library (minified, contains NaN/undefined legitimately)
        m0 = re.search(r"const D = (\{.*?\});\nconst \$ =", blocks[-1], re.S)
        if m0:
            body = body.replace(m0.group(1), "")  # JSON data (checked separately below)
    for bad in BANNED:
        if bad in body:
            i = body.find(bad)
            errs.append("残留占位/异常文本 %r：…%s…" % (bad, body[max(0, i - 50):i + 50].replace("\n", " ")))

    # 'NaN' / 'undefined' / 'null' are legitimate inside our own number guards (isNaN, ==null);
    # only flag them where they leak into VISIBLE text: between two HTML tags.
    for t in ("NaN", "undefined", "null"):
        hits = re.findall(r">\s*[^<>{}]{0,40}\b%s\b[^<>{}]{0,40}\s*<" % t, body)
        real = [x for x in hits if "isNaN" not in x and "==" not in x and "||" not in x]
        if real:
            errs.append("页面中出现可见的异常文本 %r：%s" % (t, real[:2]))

    m = re.search(r"const D = (\{.*?\});\nconst \$ =", h, re.S)
    if not m:
        errs.append("找不到内联数据块 const D = {...}")
        data = None
    else:
        try:
            data = json.loads(m.group(1))
        except Exception as ex:  # noqa: BLE001
            errs.append("内联数据块不是合法 JSON：%s" % ex)
            data = None
        if data:
            info.append("数据块可解析：sources=%d gaps=%d kpi=%d" % (
                len(data["case"]["sources"]), len(data["case"]["gaps"]), len(data["index"]["kpi"])))
            if not data["index"]["imports"]:
                errs.append("进口数据为空")
            if not data["case"]["gaps"]:
                errs.append("缺口清单为空：本技能的核心价值之一就是明确写出不知道什么")

    for rid in REQUIRED_IDS:
        if ('id="%s"' % rid) not in h:
            errs.append("缺少必需元素 #%s" % rid)
    for sid in SECTIONS:
        if ('id="%s"' % sid) not in h:
            errs.append("缺少板块 section#%s" % sid)

    cn = len(re.findall(r"[\u4e00-\u9fa5]", h))
    info.append("页面中文字符 %d" % cn)
    if cn < (a.min_cn or 3000):
        errs.append("中文内容过少（%d），可能是空模板" % cn)

    for w in PREDICTIVE:
        if w in h:
            errs.append("出现预测性表述 %r：结论必须可追溯、不做预测" % w)

    urls = re.findall(r'href="(http[^"]+)"', h)
    bad_urls = [u for u in urls if not re.match(r"^https?://", u)]
    if bad_urls:
        warns.append("非 http(s) 链接：%s" % bad_urls[:3])

    if data:
        src = {s["id"] for s in data["case"]["sources"]}
        used = set(re.findall(r'"s-[a-z0-9-]+"', json.dumps(data["case"], ensure_ascii=False)))
        used = {u.strip('"') for u in used}
        missing = used - src
        if missing:
            errs.append("正文引用了未登记的来源 id：%s" % ", ".join(sorted(missing)))
        unused = src - used
        if unused:
            # 'comtrade' is consumed by build_index rather than cited inside case fields
            unused = {u for u in unused if u != "comtrade"}
        if unused:
            warns.append("登记了但未被任何字段引用的来源：%s" % ", ".join(sorted(unused)))
        info.append("来源 %d 个，其中被引用 %d 个" % (len(src), len(used & src)))

    print("\n".join(info))
    for w in warns:
        print("WARN ", w)
    for e in errs:
        print("ERROR", e)
    print("—" * 50)
    print("%d error / %d warning%s" % (len(errs), len(warns), "" if not errs else "  → 不可交付"))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
