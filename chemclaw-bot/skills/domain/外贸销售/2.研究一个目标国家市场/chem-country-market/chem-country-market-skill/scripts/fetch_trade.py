"""
fetch_trade.py — 从公开、免密钥的 UN Comtrade 拉取某国某 HS6 产品的进出口与某出口国对目标国的出口。

用法
----
  python fetch_trade.py --reporter 360 --product 283620 --years 2020-2025
  python fetch_trade.py --reporter 360 --product 283620 --years 2020-2025 \
                        --exporter 156 --out raw/
  python fetch_trade.py --reporter IDN --product "soda ash" --years 5     # 先试 --lookup 找 HS 码

输出
----
  raw/comtrade_<reporter>_<product>.json
    {
      "meta": {...},
      "IDN": {"M": {"2020": [ {partnerCode, primaryValue, netWgt, ...} ]}, "X": {...}},
      "CHN_X": {"2020": [...]}
    }
  该结构与 examples 中的 raw 完全一致，可直接作为 case JSON 的取数底座。

说明
----
* 使用的是 Comtrade 免费公开 API（preview 端点），无需 API key；频率受服务器限流，
  脚本内置重试与 0.6 s 间隔，5 年 × 2 流 + 出口国约 20 次请求，通常 1–3 分钟。
* 只取 partner2Code=0 的“全部运输方式合计”行，避免重复计数。
* 数量取 netWgt（kg）。某些国家某些年份不报送净重（返回 0 或 null）——本工具**不会**用金额反推数量。
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

API = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
UA = "Mozilla/5.0 (compatible; chem-country-market/1.0; public-research)"
M49 = {"IDN": 360, "CHN": 156, "IND": 699, "THA": 764, "VNM": 704, "MYS": 458, "USA": 842,
       "TUR": 792, "BRA": 76, "RUS": 643, "JPN": 392, "KOR": 410, "DEU": 276, "GBR": 826,
       "AUS": 36, "PHL": 608, "PAK": 586, "EGY": 818, "SAU": 682, "NGA": 566, "MEX": 484,
       "SAF": 710, "ZAF": 710}


def parse_years(s):
    if "-" in s and ":" not in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    if ":" in s:
        a, b = s.split(":")
        return list(range(int(a), int(b) + 1))
    n = int(s)
    if n < 100:  # "5" means last 5 complete years
        this = time.localtime().tm_year
        return list(range(this - n, this))
    return [n]


def get_json(url, retries=4, pause=0.6):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode())
        except Exception as ex:  # noqa: BLE001 - network errors vary
            print("  [retry %d] %s" % (i + 1, ex), file=sys.stderr)
            time.sleep(pause * (i + 2) * 2)
    return None


def clean(rows):
    best = {}
    for r in rows or []:
        if r.get("partner2Code") not in (0, None):
            continue
        k = r.get("partnerCode")
        if k not in best or (best[k].get("isAggregate") and not r.get("isAggregate")):
            best[k] = r
    keep = ("partnerCode", "primaryValue", "cifvalue", "fobvalue", "netWgt", "qty", "qtyUnitAbbr",
            "isNetWgtEstimated", "altQty", "isAggregate")
    return [{k: r.get(k) for k in keep} for r in best.values()]


def fetch(reporter, product, years, flows=("M", "X")):
    out = {}
    for y in years:
        for f in flows:
            url = "%s?reporterCode=%s&period=%s&partnerCode=&cmdCode=%s&flowCode=%s" % (API, reporter, y, product, f)
            d = get_json(url)
            rows = clean((d or {}).get("data"))
            out.setdefault(str(y), {})[f] = rows
            tot = [r for r in rows if r["partnerCode"] == 0]
            print("  %s %s  rows=%-3d total=%s" % (y, f, len(rows),
                                                   (tot[0].get("primaryValue"), tot[0].get("netWgt")) if tot else "—"))
            time.sleep(0.6)
    return out


def lookup(product_kw):
    """Find HS6 codes whose description contains the keyword (Comtrade reference endpoint)."""
    url = "https://comtradeapi.un.org/files/v1/app/reference/H6.json"
    d = get_json(url, retries=2)
    if not d:
        return []
    hit = []
    for r in d.get("results", []):
        desc = (r.get("text") or "").lower()
        if product_kw.lower() in desc:
            hit.append((r.get("id"), r.get("text")))
    return hit[:30]


def main():
    ap = argparse.ArgumentParser(description="UN Comtrade 公开 API 贸易数据拉取（免 key）")
    ap.add_argument("--reporter", required=True, help="报告国 M49 数字码或 ISO3（如 360 / IDN）")
    ap.add_argument("--product", required=True, help="HS6 编码（如 283620）；或用 --lookup 先查")
    ap.add_argument("--years", default="5", help="2020-2025 / 2020:2025 / 5（最近 5 个完整年）")
    ap.add_argument("--exporter", default=None, help="额外拉取某出口国对该国的出口（如 156=中国）")
    ap.add_argument("--lookup", action="store_true", help="按描述关键词查 HS6，不拉贸易数据")
    ap.add_argument("--out", default="raw", help="输出目录")
    a = ap.parse_args()

    if a.lookup:
        hits = lookup(a.product)
        if not hits:
            print("未找到匹配的产品描述；请换关键词（英文）")
        for code, text in hits:
            print(code, text)
        return

    rep = a.reporter.upper()
    rep = str(M49.get(rep, rep))
    exp = a.exporter
    if exp:
        exp = str(M49.get(exp.upper(), exp))

    years = parse_years(a.years)
    print("拉取 reporter=%s product=%s years=%s" % (rep, a.product, years))
    data = fetch(rep, a.product, years)
    res = {"IDN": {"M": {}, "X": {}}, "CHN_X": {}, "meta": {
        "source": "UN Comtrade public API v1 (preview), annual, HS",
        "endpoint": API + "?reporterCode={rep}&period={year}&partnerCode=&cmdCode={product}&flowCode={flow}",
        "reporter": rep, "product": a.product, "years": years,
        "value_basis_imports": "CIF USD", "value_basis_exports": "FOB USD",
        "weight_basis": "netWgt kg (unreported years stay null/0 — not estimated)",
    }}
    for y, flows in data.items():
        for f, rows in flows.items():
            res["IDN"][f][y] = rows
    if exp:
        print("拉取出口国 %s 对 %s 的出口" % (exp, rep))
        ex = fetch(exp, a.product, years, flows=("X",))
        for y, flows in ex.items():
            res["CHN_X"][y] = flows["X"]
        res["meta"]["exporter"] = exp

    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, "comtrade_%s_%s.json" % (rep, a.product))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    print("已写出", path)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
