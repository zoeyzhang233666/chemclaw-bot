"""
calc_trade.py — 把 fetch_trade.py 的 raw 结果先"算出来给人看"，再决定写进 case JSON。

为什么要有这一步：贸易数据最容易出错的是口径（CIF/FOB、净重缺失、单位是 kg、伙伴 999 未知），
把口径算清楚再抄进 case JSON，比事后在报告里纠错便宜。

用法
----
  python calc_trade.py raw/comtrade_360_283620.json --years 2020-2025
  python calc_trade.py raw/comtrade_360_283620.json --years 2020-2025 --json trade_facts.json

输出（stdout 与 --json 文件同内容）
  imports     逐年金额 / 数量 / 单位价值 / 同比
  partners    每年来源国前 8 位、份额、单位价值
  exports     目标国出口（判断其是否为再出口国）
  exporter    出口国对目标国出口 与 其对世界出口（可选）
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

NAMES = {0: "世界合计 World", 842: "美国 USA", 156: "中国 China", 699: "印度 India", 792: "土耳其 Türkiye",
         784: "阿联酋 UAE", 100: "保加利亚 Bulgaria", 616: "波兰 Poland", 586: "巴基斯坦 Pakistan",
         490: "中国台湾 Other Asia, nes", 70: "波黑 Bosnia and Herzegovina", 276: "德国 Germany",
         458: "马来西亚 Malaysia", 392: "日本 Japan", 56: "比利时 Belgium", 643: "俄罗斯 Russia",
         826: "英国 UK", 528: "荷兰 Netherlands", 410: "韩国 Korea", 380: "意大利 Italy", 724: "西班牙 Spain",
         36: "澳大利亚 Australia", 764: "泰国 Thailand", 704: "越南 Viet Nam", 608: "菲律宾 Philippines",
         504: "摩洛哥 Morocco", 404: "肯尼亚 Kenya", 642: "罗马尼亚 Romania", 348: "匈牙利 Hungary",
         203: "捷克 Czechia", 757: "瑞士 Switzerland", 40: "奥地利 Austria", 250: "法国 France",
         752: "瑞典 Sweden", 246: "芬兰 Finland", 578: "挪威 Norway", 208: "丹麦 Denmark",
         360: "印度尼西亚 Indonesia", 364: "伊朗 Iran", 566: "尼日利亚 Nigeria", 554: "新西兰 New Zealand",
         144: "斯里兰卡 Sri Lanka", 384: "科特迪瓦 Côte d'Ivoire", 430: "利比里亚 Liberia",
         999: "其他/未知 Others", 899: "其他/未知 Others"}


def parse_years(s):
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


def pick(rows, code):
    for r in rows:
        if r.get("partnerCode") == code:
            return r
    return None


def analyze(raw, years, exporter=156):
    meta = raw.get("meta") or {}
    res = {"product": meta.get("product"), "reporter": meta.get("reporter"),
           "value_basis": "CIF (imports) / FOB (exports)", "unit": "USD and tonnes",
           "imports": [], "exports": [], "partners": {}, "exporter_rows": [], "warnings": []}
    for y in years:
        rows = C.jget(raw, "IDN", "M", y, default=[]) or []
        tot = pick(rows, 0)
        if not tot:
            res["warnings"].append("%s 年无进口合计行（未报送或该年无贸易）" % y)
            continue
        qty = tot.get("netWgt")
        if not qty:
            res["warnings"].append("%s 年进口净重未报送/为 0：数量留缺口，不做推算" % y)
            qty = None
        val = tot.get("primaryValue")
        res["imports"].append({"year": y, "value_usd": val, "qty_t": round(qty / 1000.0, 1) if qty else None,
                               "unit_usd_t": round(val / (qty / 1000.0), 1) if (qty and val) else None})
        parts = sorted([r for r in rows if r.get("partnerCode") != 0], key=lambda r: -(r.get("primaryValue") or 0))
        res["partners"][y] = [{
            "rank": i, "code": p["partnerCode"], "name": NAMES.get(p["partnerCode"], "ISO %s" % p["partnerCode"]),
            "value_usd": p.get("primaryValue"),
            "qty_t": round(p["netWgt"] / 1000.0, 1) if p.get("netWgt") else None,
            "share_value_pct": round(p["primaryValue"] / val * 100, 1) if (val and p.get("primaryValue")) else None,
            "unit_usd_t": round(p["primaryValue"] / (p["netWgt"] / 1000.0), 1) if (p.get("netWgt") and p.get("primaryValue")) else None,
        } for i, p in enumerate(parts[:8], start=1)]

        xrows = C.jget(raw, "IDN", "X", y, default=[]) or []
        xt = pick(xrows, 0)
        dests = [r for r in xrows if r["partnerCode"] != 0]
        if xt:
            res["exports"].append({"year": y, "value_usd": xt.get("primaryValue"),
                                   "qty_t": round(xt["netWgt"] / 1000.0, 1) if xt.get("netWgt") else None,
                                   "top_dest": NAMES.get(max(dests, key=lambda r: r.get("primaryValue") or 0)["partnerCode"], "—")
                                   if dests else None})

        erows = C.jget(raw, "CHN_X", y, default=[]) or []
        e_world, e_part = pick(erows, 0), pick(erows, int(meta.get("reporter") or 0))
        if e_part:
            res["exporter_rows"].append({"year": y, "exporter": exporter, "to_reporter_usd": e_part.get("primaryValue"),
                                         "to_reporter_t": round(e_part["netWgt"] / 1000.0, 1) if e_part.get("netWgt") else None,
                                         "to_world_usd": e_world.get("primaryValue") if e_world else None})

    imps = res["imports"]
    res["cagr"] = {}
    if len(imps) >= 2:
        y0, y1 = imps[0]["year"], imps[-1]["year"]
        res["cagr"]["value_pct"] = round(C.cagr(imps[0]["value_usd"], imps[-1]["value_usd"], y1 - y0), 1)
        res["cagr"]["qty_pct"] = (round(C.cagr(imps[0]["qty_t"], imps[-1]["qty_t"], y1 - y0), 1)
                                  if imps[0]["qty_t"] and imps[-1]["qty_t"] else None)
    return res


def main():
    ap = argparse.ArgumentParser(description="raw 贸易数据 → 逐年/伙伴/出口事实（供人工核对后写入 case JSON）")
    ap.add_argument("raw")
    ap.add_argument("--years", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    raw = C.load_json(a.raw)
    if a.years:
        years = parse_years(a.years)
    else:
        years = sorted(int(y) for y in (C.jget(raw, "IDN", "M", default={}) or {}).keys())
    res = analyze(raw, years)
    if a.json:
        C.save_json(res, a.json)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
