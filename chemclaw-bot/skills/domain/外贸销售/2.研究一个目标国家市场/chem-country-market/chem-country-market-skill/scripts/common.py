"""Shared library for chem-country-market (国别市场研究).

Pure standard library.  Used by validate.py / calc_trade.py / build_html.py / build_xlsx.py /
check_html.py / check_xlsx.py / selftest.py.

Conventions
-----------
* case JSON  = the single human-maintained source of truth (see references/data-contract.md)
* data.json  = derived, rebuilt on every run (never edit by hand)
* All money in USD unless a field name says otherwise; quantities in tonnes (t).
* Nothing here invents a number: missing values stay None and are reported as gaps.
"""
import json
import os
import re

SCHEMA_VERSION = "1.0"

# --------------------------------------------------------------------------- evidence classes
KINDS = {
    "official": ("官方统计", "官方 / 国际组织直接公布的贸易或海关统计"),
    "regulation": ("官方政策", "法规、税则、公告、政府指南原文"),
    "company": ("企业公开资料", "上市公司年报、企业官网、新闻稿"),
    "media": ("媒体报道", "对官方或企业表态的报道，二手"),
    "trade_assoc": ("协会 / 行业机构", "行业协会、产业联盟发布"),
    "market_research": ("市场机构估算", "付费或半付费研究机构，方法与明细通常不公开"),
    "estimate": ("估算", "由已有数据按明确公式推算，必须写明输入"),
    "unnamed": ("未核实行业描述", "一般性产业判断，未落到具体企业或数据"),
}
KIND_ORDER = list(KINDS)

# --------------------------------------------------------------------------- scale helpers
UNITS = [("万", 1e4), ("亿", 1e8), ("十万", 1e5), ("百万", 1e6), ("千万", 1e7)]
AMOUNT_UNITS = {"usd": 1.0, "万美元": 1e4, "万美元≈": 1e4, "亿美元": 1e8, "千美元": 1e3,
                "idr": 1.0, "亿印尼盾": 1e8, "万亿印尼盾": 1e12}
WEIGHT_UNITS = {"t": 1.0, "吨": 1.0, "kt": 1e3, "千吨": 1e3, "万吨": 1e4, "mt": 1.0, "公斤": 1e-3}


def usd_t(value_usd, qty_t):
    """Unit value USD/t from a value/quantity pair; None if any side is missing/zero."""
    try:
        if value_usd is None or qty_t in (None, 0):
            return None
        return float(value_usd) / float(qty_t)
    except (TypeError, ValueError):
        return None


def pct(a, b):
    if a is None or b in (None, 0):
        return None
    try:
        return (float(a) / float(b) - 1.0) * 100.0
    except (TypeError, ValueError):
        return None


def share(a, b):
    if a is None or b in (None, 0):
        return None
    try:
        return float(a) / float(b) * 100.0
    except (TypeError, ValueError):
        return None


def cagr(first, last, years):
    if first in (None, 0) or last is None or years <= 0 or first < 0:
        return None
    try:
        return ((float(last) / float(first)) ** (1.0 / years) - 1.0) * 100.0
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def hist_position(series, value):
    """Percentile rank of value inside a numeric series (0-100). None if <2 usable points."""
    vals = sorted(float(v) for v in series if v is not None)
    if value is None or len(vals) < 2:
        return None
    below = sum(1 for v in vals if v < value)
    return below / (len(vals) - 1) * 100.0


# --------------------------------------------------------------------------- io helpers
def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def jget(obj, *path, default=None):
    """Nested get that tolerates both int and str keys (JSON year keys are usually strings)."""
    cur = obj
    for p in path:
        if isinstance(cur, dict):
            if p in cur:
                cur = cur[p]
                continue
            if str(p) in cur:
                cur = cur[str(p)]
                continue
            if isinstance(p, int) and str(p) in cur:
                cur = cur[str(p)]
                continue
            return default
        return default
    return cur


def save_json(obj, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


class CaseError(Exception):
    pass


def need(obj, key, where, errors):
    if not isinstance(obj, dict) or obj.get(key) in (None, "", [], {}):
        errors.append("%s 缺少必填字段 `%s`" % (where, key))
        return None
    return obj.get(key)


# --------------------------------------------------------------------------- trade helpers
def import_rows(trade):
    return sorted(trade.get("imports") or [], key=lambda r: r.get("year", 0))


def value_series(trade):
    return [(r["year"], r.get("value_usd")) for r in import_rows(trade)]


def qty_series(trade):
    return [(r["year"], r.get("qty_t")) for r in import_rows(trade)]


def imports_with_notes(trade):
    """Annotate each import row with coverage flags used by the UI and the Excel."""
    rows = import_rows(trade)
    out = []
    for i, r in enumerate(rows):
        prev = rows[i - 1] if i else None
        out.append(dict(
            r,
            yoy_value=pct(r.get("value_usd"), (prev or {}).get("value_usd")),
            yoy_qty=pct(r.get("qty_t"), (prev or {}).get("qty_t")),
            unit_usd_t=usd_t(r.get("value_usd"), r.get("qty_t")),
            qty_status="已报送" if r.get("qty_t") is not None else "未报送",
        ))
    return out


def partner_rows(partners, year):
    return sorted((partners or {}).get(str(year)) or [], key=lambda p: p.get("rank", 999))


def struct_year_candidates(case):
    """Years for which a full structure (partners) exists."""
    base = case.get("meta", {}).get("research_year")
    years = sorted(int(y) for y in (case.get("trade", {}).get("partners") or {}).keys())
    for y in [base, base - 1 if base else None, base - 2 if base else None]:
        if y in years:
            return y
    return years[-1] if years else base


def china_rows(trade):
    rows = sorted(trade.get("china_exports") or [], key=lambda r: r.get("year", 0))
    out = []
    for i, r in enumerate(rows):
        prev = rows[i - 1] if i else None
        out.append(dict(
            r,
            unit_usd_t=usd_t(r.get("to_idn_usd"), r.get("to_idn_t")),
            yoy_value=pct(r.get("to_idn_usd"), (prev or {}).get("to_idn_usd")),
            share_of_idn_imports=None,   # filled by build_index
            share_of_china_world=share(r.get("to_idn_usd"), r.get("to_world_usd")),
        ))
    return out


def tariff_summary(policy):
    rows = (policy or {}).get("tariffs") or []
    known = [t for t in rows if isinstance(t.get("rate_pct"), (int, float))]
    if not known:
        return None
    return known


# --------------------------------------------------------------------------- validation
def validate_case(case):
    """Structural + semantic checks. Returns (errors, warnings)."""
    e, w = [], []
    meta = case.get("meta") or {}
    need(meta, "title", "meta", e)
    need(meta, "research_year", "meta", e)
    subj = need(meta, "subject", "meta", e) or {}
    need(subj, "product_cn", "meta.subject", e)
    need(subj, "hs_code", "meta.subject", e)
    cty = need(meta, "country", "meta", e) or {}
    need(cty, "name_cn", "meta.country", e)
    if not (meta.get("trade_source") or {}).get("name"):
        w.append("meta.trade_source.name 为空：报告首屏将无法说明贸易数据来源")
    y = meta.get("research_year")
    if isinstance(y, int) and not (1990 <= y <= 2100):
        e.append("meta.research_year 不合理：%s" % y)

    trade = case.get("trade") or {}
    imps = import_rows(trade)
    if len(imps) < 2:
        e.append("trade.imports 至少需要 2 个年度（用于增长与分位）")
    years = [r.get("year") for r in imps]
    if years != sorted(years) or len(set(years)) != len(years):
        e.append("trade.imports 年度重复或乱序：%s" % years)
    if years:
        win = meta.get("window") or 5
        if len(years) < win:
            w.append("trade.imports 只有 %d 年，少于声明的窗口 %d 年" % (len(years), win))
        for r in imps:
            typed = r.get("read_mode") == "screenshot"
            if r.get("value_usd") is None:
                e.append("%s 年进口金额缺失" % r.get("year"))
            elif not typed and r["value_usd"] > 1e12:
                e.append("%s 年进口金额量级异常（$%.0f），检查是否漏乘单位" % (r.get("year"), r["value_usd"]))
            if r.get("qty_t") is not None and r["qty_t"] < 0:
                e.append("%s 年进口数量为负" % r.get("year"))
            if r.get("source") and r.get("view_kind") not in KINDS and r.get("view_kind") is not None:
                w.append("%s 年 source=%s 未在已知来源 id 中" % (r.get("year"), r.get("source")))

    partners = trade.get("partners") or {}
    all_imps = {str(r.get("year")): r for r in (trade.get("imports_history") or [])}
    all_imps.update({str(r.get("year")): r for r in imps})
    for yk, rows in partners.items():
        tot = (all_imps.get(str(yk)) or {}).get("value_usd")
        if tot is None:
            w.append("trade.partners 有 %s 年明细但 trade.imports 无该年合计" % yk)
            continue
        s = sum((p.get("value_usd") or 0) for p in rows)
        if tot and s > tot * 1.02:
            e.append("%s 年前几位伙伴合计 %.0f 超过进口合计 %.0f" % (yk, s, tot))
        for p in rows:
            if p.get("value_usd") is None:
                w.append("%s 年伙伴 %s 金额缺失" % (yk, p.get("name")))
        if not rows:
            w.append("%s 年伙伴明细为空" % yk)

    for r in trade.get("china_exports") or []:
        if r.get("to_idn_usd") and r.get("to_idn_t") and not (1 < r["to_idn_usd"] / r["to_idn_t"] < 100000):
            w.append("%s 年中国对印尼单位价值异常：%.0f USD/t" % (r.get("year"), r["to_idn_usd"] / r["to_idn_t"]))
        if r.get("to_world_usd") and r.get("to_idn_usd") and r["to_idn_usd"] > r["to_world_usd"]:
            e.append("%s 年中国对印尼出口超过对世界出口" % r.get("year"))

    for block in ("industries", "downstream", "competition", "policy", "reports", "sources", "gaps", "verify_actions"):
        if not case.get(block):
            w.append("区块 `%s` 为空：报告中该区将显示“未取得”" % block)

    src_ids = {s.get("id") for s in (case.get("sources") or [])}
    gaps = case.get("gaps") or []
    for g in gaps:
        for f in ("id", "item", "why", "how_to_close"):
            if not g.get(f):
                e.append("gaps.%s 缺少 %s" % (g.get("id"), f))

    # every evidence reference must resolve
    refs = collect_refs(case)
    missing = sorted({r for r in refs if r not in src_ids})
    if missing:
        e.append("以下来源 id 被引用但未在 sources 中登记：%s" % ", ".join(missing))

    # every source must state a tier
    for s in case.get("sources") or []:
        if not s.get("id") or not s.get("url") or not s.get("title"):
            e.append("sources 条目缺少 id/url/title：%s" % s)
        if s.get("tier") not in (1, 2, 3, 4):
            w.append("来源 %s 未标注可信等级 tier(1-4)" % s.get("id"))

    # local production: capacity must be sourced or explicitly null
    for lp in (case.get("industries") or {}).get("local_production") or []:
        if lp.get("capacity_t") is None and not lp.get("capacity_basis"):
            w.append("本地产能 %s 未给 capacity_basis（说明为何无产能数字）" % lp.get("name"))
        if lp.get("capacity_t") is not None and not (lp.get("sources") or []):
            e.append("本地产能 %s 给出数字但未标注来源" % lp.get("name"))

    # tariffs: a rate must be official-ish, otherwise leave null
    for t in (case.get("policy") or {}).get("tariffs") or []:
        if t.get("rate_pct") is not None and t.get("status") not in ("fact", "official"):
            w.append("税率 %s 给出数值但状态为 %s，报告中会标注“待核实”" % (t.get("id"), t.get("status")))

    # forbidden phrasing: predictions masquerading as facts
    banned = [r"预计将增长", r"必将", r"一定会", r"肯定能", r"保证可以", r"必然上涨", r"毫无疑问"]
    text = json.dumps(case, ensure_ascii=False)
    for pat in banned:
        if re.search(pat, text):
            e.append("出现未授权表述：%s（结论必须可追溯，不做预测性断言）" % pat)

    return e, w


def collect_refs(case):
    """Collect every source id referenced anywhere in the case JSON."""
    out = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("source", "sources") and isinstance(v, str):
                    out.append(v)
                elif k in ("source", "sources") and isinstance(v, list):
                    out.extend([x for x in v if isinstance(x, str)])
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(case)
    return out


# --------------------------------------------------------------------------- derived index
def build_index(case):
    """All derived numbers in one place. The only function allowed to compute rates/shares."""
    meta = case["meta"]
    trade = case.get("trade") or {}
    imps = imports_with_notes(trade)
    imps_history = [dict(r, yoy_value=None, yoy_qty=None,
                         unit_usd_t=usd_t(r.get("value_usd"), r.get("qty_t")),
                         qty_status="已报送" if r.get("qty_t") is not None else "未报送")
                    for r in sorted(trade.get("imports_history") or [], key=lambda r: r.get("year", 0))]
    win = int(meta.get("window") or 5)
    window_rows = imps[-win:] if len(imps) >= win else imps
    first, last = (window_rows[0], window_rows[-1]) if len(window_rows) >= 2 else (None, None)

    values = [r.get("value_usd") for r in imps]
    qtys = [r.get("qty_t") for r in imps]
    units = [r.get("unit_usd_t") for r in imps]

    latest = imps[-1] if imps else None
    index = {
        "research_year": meta.get("research_year"),
        "window": win,
        "imports": imps,
        "imports_history": imps_history,
        "imports_window": window_rows,
        "years_span": [first["year"], last["year"]] if first and last else [None, None],
        "cagr_value": cagr(first.get("value_usd"), last.get("value_usd"), last["year"] - first["year"]) if first and last else None,
        "cagr_qty": cagr(first.get("qty_t"), last.get("qty_t"), last["year"] - first["year"]) if first and last else None,
        "yoy_value_latest": latest.get("yoy_value") if latest else None,
        "yoy_qty_latest": latest.get("yoy_qty") if latest else None,
        "peak_value": max((v for v in values if v is not None), default=None),
        "peak_value_year": (max((r for r in imps if r.get("value_usd") is not None),
                                key=lambda r: r["value_usd"])["year"]
                            if any(v is not None for v in values) else None),
        "qty_hist_position": hist_position(qtys, latest.get("qty_t") if latest else None),
        "unit_usd_t_latest": latest.get("unit_usd_t") if latest else None,
        "unit_series": [(r["year"], r.get("unit_usd_t")) for r in imps],
        "qty_missing_years": [r["year"] for r in imps if r.get("qty_t") is None],
    }

    # partner structure per year
    partners = trade.get("partners") or {}
    totals_by_year = {str(r.get("year")): r for r in imps_history}
    totals_by_year.update({str(r.get("year")): r for r in imps})
    pstruct = {}
    for yk, rows in partners.items():
        tot = totals_by_year.get(str(yk))
        base = (tot or {}).get("value_usd")
        baseq = (tot or {}).get("qty_t")
        enriched = []
        for p in sorted(rows, key=lambda p: p.get("rank", 999)):
            enriched.append(dict(
                p,
                share_value=share(p.get("value_usd"), base),
                share_qty=share(p.get("qty_t"), baseq),
                unit_usd_t=usd_t(p.get("value_usd"), p.get("qty_t")),
            ))
        pstruct[yk] = {"rows": enriched, "total_value_usd": base, "total_qty_t": baseq}
    index["partner_structure"] = pstruct
    cty_year = struct_year_candidates(case)
    cs = pstruct.get(str(cty_year)) or {"rows": []}
    index["structure_year"] = cty_year
    index["structure_rows"] = cs["rows"]
    index["structure_total_value_usd"] = cs.get("total_value_usd")
    index["china_latest_share"] = next((r.get("share_value") for r in cs["rows"] if "China" in (r.get("name") or "")), None)
    index["china_latest_rank"] = next((r.get("rank") for r in cs["rows"] if "China" in (r.get("name") or "")), None)
    index["top_supplier"] = cs["rows"][0] if cs["rows"] else None
    index["top_supplier_share"] = cs["rows"][0].get("share_value") if cs["rows"] else None
    index["partner_count"] = sum(1 for r in (trade.get("imports") or []) if False) or None

    # China exports
    chn = china_rows(trade)
    idn_by_year = {r["year"]: r for r in imps}
    for r in chn:
        r["share_of_idn_imports"] = share(r.get("to_idn_usd"), (idn_by_year.get(r.get("year")) or {}).get("value_usd"))
    index["china_exports"] = chn
    if chn:
        c0, c1 = chn[0], chn[-1]
        index["china_cagr"] = cagr(c0.get("to_idn_usd"), c1.get("to_idn_usd"), c1["year"] - c0["year"])
        index["china_last"] = c1

    # local supply (only what the case states)
    index["local_supply"] = trade.get("local_supply") or []
    index["consumption_reference"] = trade.get("consumption_reference") or []

    # re-export indicator: target country's own exports vs imports of the same HS6
    exp_rows = sorted(trade.get("exports") or [], key=lambda r: r.get("year", 0))
    by_year = {r["year"]: r for r in imps}
    for r in exp_rows:
        r["pct_of_imports_value"] = share(r.get("value_usd"), (by_year.get(r.get("year")) or {}).get("value_usd"))
    index["exports"] = exp_rows
    index["reexport_ratio_latest"] = (exp_rows[-1].get("pct_of_imports_value") if exp_rows else None)

    # sourcing concentration (HHI of value shares in the structure year)
    sh = [max(r.get("share_value") or 0, 0) for r in cs["rows"]]
    index["hhi_top"] = sum((s / 100.0) ** 2 for s in sh) * 10000 if sh else None
    index["gap_count"] = len(case.get("gaps") or [])
    index["verify_count"] = len(case.get("verify_actions") or [])
    index["source_count"] = len(case.get("sources") or [])

    index["kpi"] = kpi_cards(index, case)
    return index


def kpi_cards(index, case):
    """Six headline cards. Each carries its evidence label and source id (or None=缺口)."""
    imps = index["imports"]
    latest = imps[-1] if imps else {}
    qty_txt = ("%.0f 万吨" % (latest["qty_t"] / 1e4)) if latest.get("qty_t") else "未报送"
    cards = [
        {"key": "value", "label": "%s 年进口金额" % latest.get("year", "最新"),
         "value": ("%.2f 亿美元" % (latest["value_usd"] / 1e8)) if latest.get("value_usd") else "—",
         "sub": "CIF · HS %s · %d 个伙伴国" % (case["meta"]["subject"]["hs_code"], len(index["structure_rows"])),
         "kind": "official", "source": "comtrade", "tone": "blue"},
        {"key": "yoy", "label": "%s 年金额同比" % latest.get("year", ""),
         "value": ("%+.1f%%" % latest["yoy_value"]) if latest.get("yoy_value") is not None else "—",
         "sub": "%d–%d 年金额 CAGR %s" % (index["years_span"][0] or 0, index["years_span"][1] or 0,
                                         ("%.1f%%" % index["cagr_value"]) if index["cagr_value"] is not None else "—"),
         "kind": "official", "source": "comtrade",
         "tone": "red" if (latest.get("yoy_value") or 0) > 0 else "green"},
        {"key": "qty", "label": "%s 年进口数量" % latest.get("year", ""),
         "value": qty_txt,
         "sub": "数量 CAGR %s · 缺口年份 %s" % (
             ("%.1f%%" % index["cagr_qty"]) if index["cagr_qty"] is not None else "—",
             "、".join(str(y) for y in index["qty_missing_years"]) or "无"),
         "kind": "official" if latest.get("qty_t") else "gap", "source": "comtrade",
         "tone": "amber" if not latest.get("qty_t") else "blue"},
        {"key": "china", "label": "中国份额（%s）" % index["structure_year"],
         "value": ("%.1f%%" % index["china_latest_share"]) if index["china_latest_share"] is not None else "—",
         "sub": "排名第 %s · 中国对印尼出口 %s" % (
             index["china_latest_rank"] or "—",
             ("%.0f 万美元" % ((index.get("china_last") or {}).get("to_idn_usd", 0) / 1e4))
             if (index.get("china_last") or {}).get("to_idn_usd") else "缺口"),
         "kind": "official", "source": "comtrade", "tone": "violet"},
        {"key": "top", "label": "第一大来源国",
         "value": (index["top_supplier"] or {}).get("name", "—").split(" ")[0],
         "sub": "份额 %.1f%% · 单位价值 %s" % (
             index["top_supplier_share"] or 0,
             ("$%.0f/t" % (index["top_supplier"] or {}).get("unit_usd_t", 0))
             if (index["top_supplier"] or {}).get("unit_usd_t") else "—"),
         "kind": "official", "source": "comtrade", "tone": "cyan"},
        {"key": "supply", "label": "本地规模化产能",
         "value": local_supply_headline(case) or "0（在运）",
         "sub": "在建/中试项目 %d 个 · 见「本地产能与下游」" % len(
             (case.get("industries") or {}).get("local_production") or []),
         "kind": "official", "source": ((case.get("industries") or {}).get("local_production") or [{}])[0].get("sources", [None])[0]
         if (case.get("industries") or {}).get("local_production") else None,
         "tone": "amber"},
    ]
    return cards


def local_supply_headline(case):
    lps = (case.get("industries") or {}).get("local_production") or []
    cap = [p["capacity_t"] / 1e4 for p in lps if isinstance(p.get("capacity_t"), (int, float))]
    if not cap:
        return None
    return "在建 %.1f 万吨/年" % sum(cap)


# --------------------------------------------------------------------------- text helpers
def fmt(n, d=0):
    if n is None or (isinstance(n, float) and n != n):
        return "—"
    try:
        return ("{:,.%df}" % d).format(float(n))
    except (TypeError, ValueError):
        return str(n)


def fmt_money_usd(v, decimals=2):
    if v is None:
        return "—"
    return "%s 亿美元" % fmt(v / 1e8, decimals)


def fmt_t(t):
    if t is None:
        return "—"
    return "%s 万吨" % fmt(t / 1e4, 1)


def fmt_pct(v, d=1, sign=True):
    if v is None:
        return "—"
    return ("%+.*f%%" if sign else "%.*f%%") % (d, v)


def kind_label(k):
    return KINDS.get(k, (k or "未标注", ""))[0]


def nco_report_links(case):
    """Hand-off targets for the next skills in the 外贸销售 chain."""
    c = case["meta"]["country"]
    s = case["meta"]["subject"]
    return [
        {"name": "3. 找海外候选买家", "hint": "带着本品类、目标口岸、客户类型（玻璃 / 洗涤剂 / 分销商）与已核实企业清单继续",
         "payload": {"country": c["name_cn"], "product": s["product_cn"], "hs_code": s["hs_code"],
                     "seed_companies": [x.get("name") for x in ((case.get("industries") or {}).get("consumers") or [])]}},
        {"name": "6. 查产品出口要求", "hint": "带入 HS 编码与目标国，核查进口许可、标签、认证与出口国要求",
         "payload": {"country": c["name_cn"], "hs_code": s["hs_code"]}},
        {"name": "1. 看产品适合卖到哪些国家", "hint": "把本国的中国份额、增速与集中度作为比较维度喂回选国模型",
         "payload": {"country": c["name_cn"], "hs_code": s["hs_code"]}},
    ]
