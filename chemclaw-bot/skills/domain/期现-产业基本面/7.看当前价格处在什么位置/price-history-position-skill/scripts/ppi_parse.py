# -*- coding: utf-8 -*-
"""生意社(100ppi) 纯碱文章解析：华东区域日评 + 全国基准价。

两类文章都能解析成「日期 + 数值/区间 + 口径」的结构化记录：

A. 华东地区纯碱行情（区域现货日评）
   「7月1日华东地区纯碱报价，轻质纯碱主流市场在1070-1560元/吨左右；
     重质纯碱主流市场在1180-1300元/吨左右，实单以商谈为主。」
   → 华东 · 重质纯碱 · 主流市场区间(低-高) · 含税出厂 · 元/吨 · 数据日期

B. 生意社基准价（全国基准，非区域）
   「8月24日生意社重质纯碱基准价为1090.00元/吨」
   → 全国基准价 · 重质纯碱 · 单点 · 元/吨

注意：B 是「全国基准价」，其样本构成与 A 的「华东主流市场区间」不同，
两者不可互相替代，也不可拼成一条序列。报告必须分列并标注口径差异。
"""
import re

CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
          "十": 10, "十一": 11, "十二": 12}
UNIT = "元/吨"


def _clean_text(html):
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&gt;", ">").replace("&lt;", "<")
    lines = [x.strip() for x in t.split("\n") if x.strip()]
    return lines


def _body(lines):
    """取正文段：从『生意社x月x日讯』之后到『【大宗商品公式定价原理】』之前。"""
    start = 0
    for i, l in enumerate(lines):
        if re.search(r"生意社\s*\d{1,2}月\d{1,2}日讯", l):
            start = i
            break
    end = len(lines)
    for i in range(start, len(lines)):
        if "【大宗商品公式定价原理】" in lines[i] or "定价公式" in lines[i]:
            end = i
            break
    return lines[start:end]


def parse_date_from_text(text):
    m = re.search(r"(\d{4})\s*[年\-/]\s*(\d{1,2})\s*[月\-/]\s*(\d{1,2})", text)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.search(r"(\d{1,2})月(\d{1,2})日", text)
    if m:
        return None, int(m.group(1)), int(m.group(2))
    return None


def parse_huadong(html, pub_date):
    """解析华东地区纯碱行情文章。返回 dict 或 None。"""
    lines = _clean_text(html)
    body = _body(lines)
    joined = " ".join(body)
    if "华东" not in joined:
        return None

    title = None
    for l in lines:
        if "华东地区纯碱" in l and len(l) < 90:
            title = l
            break

    pm = parse_date_from_text(joined)
    if pm:
        y, m, d = pm
        data_date = "%04d-%02d-%02d" % (y or int(str(pub_date)[:4]), m, d)
    else:
        data_date = "%s-%s-%s" % (pub_date[:4], pub_date[4:6], pub_date[6:8])

    def grab(label):
        # 「重质纯碱主流市场在1180-1300元/吨左右」
        pat = label + r"[^。；;]{0,40}?(\d{3,5})\s*[-~—–至]\s*(\d{3,5})\s*元/吨"
        m = re.search(pat, joined)
        if m:
            return int(m.group(1)), int(m.group(2))
        pat2 = label + r"[^。；;]{0,40}?(\d{3,5})\s*元/吨"
        m = re.search(pat2, joined)
        if m:
            return int(m.group(1)), int(m.group(1))
        return None

    hd = grab("重质纯碱")
    lt = grab("轻质纯碱")

    # 调价句：必须绑定到品种，否则会把「轻质下调70」错记到重质头上。
    # 「7月27日价格下调50元/吨」通常紧跟在该品种区间之后，两品种的调价各取各的。
    def grab_adj(label):
        seg = re.search(label + r"主流市场[^。；;]{0,60}", joined)
        if not seg:
            return None
        m = re.search(r"(?:价格)?(上调|下调|上涨|下跌)\s*(\d{1,4})\s*元/吨", seg.group(0))
        if not m:
            return None
        return {"dir": m.group(1), "amount": int(m.group(2))}

    adj_heavy = grab_adj("重质纯碱")
    adj_light = grab_adj("轻质纯碱")
    adj = adj_heavy or adj_light

    # 规格与交付方式：华东日评通常写「主流市场」「实单以商谈为主」
    basis = "主流市场报价"
    if "出厂" in joined:
        basis = "出厂价"
    elif "送到" in joined:
        basis = "送到价"
    elif "承兑" in joined:
        basis = "承兑价"
    if "实单以商谈为主" in joined:
        basis += "（实单商谈）"

    return {
        "data_date": data_date,
        "pub_date": "%s-%s-%s" % (pub_date[:4], pub_date[4:6], pub_date[6:8]),
        "title": title,
        "heavy_lo": hd[0] if hd else None,
        "heavy_hi": hd[1] if hd else None,
        "light_lo": lt[0] if lt else None,
        "light_hi": lt[1] if lt else None,
        "adjust": adj,
        "adjust_heavy": adj_heavy,
        "adjust_light": adj_light,
        "basis": basis,
        "unit": UNIT,
        "snippet": joined[:260],
    }


def parse_benchmark(html, pub_date, kind):
    """解析「x月x日生意社重质/轻质纯碱基准价为YYYY.YY元/吨」。"""
    lines = _clean_text(html)
    joined = " ".join(lines)
    who = "重质" if kind == "bench_h" else "轻质"
    m = re.search(who + r"纯碱基准价为\s*([\d.]+)\s*元/吨", joined)
    if not m:
        return None
    val = float(m.group(1))
    pm = parse_date_from_text(joined)
    if pm:
        y, mo, d = pm
        data_date = "%04d-%02d-%02d" % (y or int(str(pub_date)[:4]), mo, d)
    else:
        data_date = "%s-%s-%s" % (pub_date[:4], pub_date[4:6], pub_date[6:8])
    return {"data_date": data_date, "pub_date": "%s-%s-%s" % (pub_date[:4], pub_date[4:6], pub_date[6:8]),
            "kind": who, "value": val, "unit": UNIT}
