#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_wits.py —— 从 World Bank WITS / UN Comtrade 抓取某国某 HS6 的出口分国别数据

用法：
    python fetch_wits.py <ISO3> <HS6> <起始年> <结束年> [输出.csv]
示例：
    python fetch_wits.py SAU 290531 2021 2025 wits_sau_290531.csv

输出 CSV 列：year, partner, value_usd_thousand, qty_kg
并在末尾打印各年 World 合计与对中国（China）数量，便于快速核对。

注意：
    - WITS 页面结构可能变化，如解析为 0 行，请检查 <tr>/<td> 结构；
    - 数量单位为 kg，货值单位为千美元；
    - 请遵守 World Bank 使用条款，控制请求频率（每次请求间隔 1 秒以上）。
"""
import sys, re, csv, time, html as H, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

def url(iso3, year, hs6, flow="Exports"):
    return (f"https://wits.worldbank.org/trade/comtrade/en/country/{iso3}/year/{year}"
            f"/tradeflow/{flow}/partner/ALL/product/{hs6}")

def fetch(iso3, hs6, y0, y1, flow="Exports"):
    rows = []
    for yr in range(y0, y1 + 1):
        try:
            req = urllib.request.Request(url(iso3, yr, hs6, flow), headers=UA)
            doc = urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "ignore")
        except Exception as e:
            print(f"[WARN] {yr} 抓取失败: {e}", file=sys.stderr)
            continue
        n = 0
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", doc, re.S):
            cells = [H.unescape(re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ").strip()
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            # 9 列：Reporter | Flow | ProductCode | Description | Year | Partner | Value | Qty | Unit
            if len(cells) >= 9 and cells[4].isdigit():
                try:
                    val = float(cells[6].replace(",", ""))
                    qty = float(cells[7].replace(",", ""))
                except ValueError:
                    continue
                rows.append([int(cells[4]), re.sub(r"\s+", " ", cells[5]), val, qty])
                n += 1
        m = re.search(r"was \$([\d,\.]+)K\s+and quantity ([\d,\.]+)Kg", doc)
        chk = f"(页面摘要: ${m.group(1)}K / {m.group(2)}Kg)" if m else ""
        print(f"[OK] {iso3} {yr} HS{hs6} 解析 {n} 行 {chk}", file=sys.stderr)
        time.sleep(1.2)
    return rows

def main():
    if len(sys.argv) < 5:
        print(__doc__); sys.exit(2)
    iso3, hs6, y0, y1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    out = sys.argv[5] if len(sys.argv) > 5 else f"wits_{iso3}_{hs6}.csv"
    rows = fetch(iso3, hs6, y0, y1)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["year", "partner", "value_usd_thousand", "qty_kg"])
        w.writerows(rows)
    print(f"[OK] 已写入 {out}，共 {len(rows)} 条", file=sys.stderr)
    print("\n年份  总量(kt)  对华(kt)  世界货值(百万美元)")
    for yr in range(y0, y1 + 1):
        sub = [r for r in rows if r[0] == yr]
        wld = [r for r in sub if r[1] == "World"]
        chn = [r for r in sub if r[1] == "China"]
        if wld:
            print(f"{yr}  {wld[0][3]/1e6:9.0f}  {chn[0][3]/1e6 if chn else 0:9.0f}  {wld[0][2]/1e3:12.0f}")

if __name__ == "__main__":
    main()
