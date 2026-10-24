# -*- coding: utf-8 -*-
"""研究母本 research.json 自检。

用法：
    python scripts/validate.py examples/01-meg-cfr-china-huadong/research.json

检查项（任一 error 即判为"这次交付不能用"）：
  1. 结构与必填字段；
  2. 口径六要素：品种 / 规格 / 地区 / 币种 / 税基 / 日期（每个价格节点都要有）；
  3. 贸易术语合法性 + 重复计费（术语已含的费用又单列）；
  4. 税费率区间、汇率合理性；
  5. 历史序列的取值方式标注（actual / monthly_avg / assumed_base / gap），
     以及"用当前运费冒充历史运费"的硬性拦截；
  6. 禁用表述（套利利润 / 交易指令 / 方向判断）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
import wio  # noqa: E402

PRICE_NODES = [
    ("overseas", "海外报价"),
    ("domestic", "国内现货"),
    ("compare_quote", "对比期海外报价"),
    ("compare_dom", "对比期国内现货"),
]


def check_price_node(errors, warns, node_key, label, node, need_currency=False):
    """六要素校验。国内价默认人民币，币种可省略（缺省即 CNY），但仍会提示一次。"""
    if not node:
        return
    need = [("price", "数值"), ("spec", "规格"), ("region", "地区"),
            ("tax", "税基"), ("date", "日期"), ("source", "来源")]
    if need_currency:
        need.insert(3, ("currency", "币种"))
    for k, cn in need:
        if node.get(k) in (None, ""):
            errors.append((node_key, "%s 缺少口径要素：%s" % (label, cn)))
    if not need_currency and not node.get("currency"):
        node["currency"] = "CNY"   # 国内价一律人民币，隐式补齐并留痕
        warns.append((node_key, "%s 未写币种，按人民币 CNY 处理" % label))
    if node.get("date") and not wio.parse_iso(node["date"]):
        errors.append((node_key, "%s 日期不合法：%s" % (label, node.get("date"))))
    lo, hi = core.parse_range(node.get("price_range") or node.get("price"))
    if lo is not None and hi is not None and lo > hi:
        errors.append((node_key, "%s 报价区间下沿大于上沿" % label))
    if node.get("conf") not in (None, "高", "中", "低"):
        warns.append((node_key, "%s conf 建议用 高/中/低 三档" % label))


def main(path):
    res = wio.load_json(path)
    errors, warns = wio.check_research(res)

    for key, label in PRICE_NODES:
        check_price_node(errors, warns, key, label, res.get(key),
                         need_currency=(key in ("overseas", "compare_quote")))

    cp = res.get("cost_params", {})
    ov = res.get("overseas") or {}
    # 海外报价的数值活在 overseas.price 上，cost_params 只放费用与税率，故用合并后的探针
    probe = dict(cp)
    probe["term"] = core.norm_term(ov.get("term"))
    probe["price_quote"] = core.mid(*core.parse_range(ov.get("price_range") or ov.get("price")))
    probe["currency"] = ov.get("currency") or "USD"
    probe["dom_quote"] = core.mid(*core.parse_range((res.get("domestic") or {}).get("price")))
    for issue in core.check_terms(probe):
        errors.append(("cost_params", issue["msg"]))
    for issue in core.check_config(probe):
        (errors if issue["level"] == "error" else warns).append(("cost_params", issue["msg"]))

    dom = res.get("domestic") or {}
    if dom.get("tax") not in ("含税", "不含税", "未税"):
        errors.append(("domestic", "国内现货 tax 必须写 含税 / 不含税"))

    # 历史序列：汇率与运费都要标清来源，且必须能自证不是"用今天冒充过去"
    fx_series = {}
    fxh = res.get("fx_history")
    if isinstance(fxh, dict):
        for k, v in fxh.items():
            fxv = v.get("value") if isinstance(v, dict) else v
            if core.fnum(fxv) is not None:
                fx_series[str(k)[:10]] = core.fnum(fxv)
    elif isinstance(fxh, list):
        for r in fxh:
            if isinstance(r, dict):
                fxv = r.get("value", r.get("usdcny", r.get("v")))
                if r.get("date") and core.fnum(fxv) is not None:
                    fx_series[str(r["date"])[:10]] = core.fnum(fxv)
    hist = res.get("history") or []
    if hist:
        allowed = {"actual", "monthly_avg", "assumed_base", "gap"}
        max_stale = int((res.get("series_sources") or {}).get("fx_max_stale_days") or 7)
        for i, h in enumerate(hist):
            tag = h.get("frt_source")
            if tag not in allowed:
                errors.append(("history", "第 %d 条（%s）的运费来源标注不合法：%s"
                               % (i + 1, h.get("date"), tag)))
            if tag == "assumed_base" and not h.get("note"):
                errors.append(("history", "第 %d 条用基准日运费替代历史值，必须在 note 里写明理由"
                               % (i + 1)))
            for k in ("ov_usd", "dom_cny"):
                if h.get(k) in (None, ""):
                    errors.append(("history", "第 %d 条（%s）缺少 %s" % (i + 1, h.get("date"), k)))
            # 汇率：允许行内直给，否则必须能在 fx_history 里按新鲜度取到
            fxv = core.fnum(h.get("fx"))
            if fxv is None:
                got, d = core.series_prev(fx_series, h.get("date") or "", max_stale)
                if got is None:
                    errors.append(("history",
                                   "第 %d 条（%s）既无行内 fx，也取不到 %d 天内的历史汇率："
                                   "按规则不得插值，请补数据或标 gap" % (i + 1, h.get("date"), max_stale)))
                h["fx"] = got
                h["fx_source"] = "actual"
                h["fx_date"] = d
            else:
                h.setdefault("fx_source", "actual")
            if h.get("fx_source") not in ("actual", "gap"):
                errors.append(("history", "第 %d 条（%s）的汇率来源必须标 actual 或 gap"
                               % (i + 1, h.get("date"))))
        dates = [wio.parse_iso(h.get("date")) for h in hist if h.get("date")]
        if any(a is None for a in dates):
            errors.append(("history", "存在非法日期"))
        else:
            for a, b in zip(dates, dates[1:]):
                if b <= a:
                    errors.append(("history", "日期必须严格递增：%s -> %s" % (a, b)))
        frts = [core.fnum(h.get("frt_usd")) for h in hist if h.get("frt_source") == "actual"]
        if len(frts) >= 3 and len(set(frts)) == 1:
            errors.append(("history", "有 3 条以上被标为 actual 的海运费完全相同，"
                                      "疑似用当前运费冒充历史值，请改为 monthly_avg 或 assumed_base"))

    for word in wio.BANNED_WORDS:
        hits = [t for _loc, t in wio.find_text_all(res, word)]
        if hits and not wio.is_negated_texts(hits, word):
            errors.append(("wording", "出现禁用表述「%s」（%s）" % (word, wio.find_text_all(res, word)[0][0])))

    for i, g in enumerate(res.get("gaps", [])):
        if not g.get("severity"):
            warns.append(("gaps", "第 %d 条缺口没有严重度" % (i + 1)))

    return wio.report((errors, warns), "validate: %s" % os.path.basename(path))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        wio.die("用法: python scripts/validate.py <research.json>")
    sys.exit(1 if main(sys.argv[1]) else 0)
