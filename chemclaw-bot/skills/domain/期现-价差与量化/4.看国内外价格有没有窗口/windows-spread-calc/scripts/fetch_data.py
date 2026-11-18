# -*- coding: utf-8 -*-
"""数据抓取（可选，需联网；依赖 requests，缺失时自动退化为 urllib）。

本脚本只负责"把公开可得的原始数据落到 raw/ 目录"，不做任何口径判断。
口径判断在 core.py / assemble.py，缺口揭示在 validate.py。

用法：
    python scripts/fetch_data.py --futures EG0 --out raw/eg0_daily.json
    python scripts/fetch_data.py --fx 2025-10-01:2026-10-20 --out raw/usdcny.json
    python scripts/fetch_data.py --futures EG0 --fx 2025-10-01:2026-10-20 --out-dir raw

数据源（公开接口、免 key）：
  * 期货日线：新浪财经 InnerFuturesNewService.getDailyKLine（主连 EG0 等）
  * 汇率：Frankfurter（欧洲央行 ECB 每日参考汇率）
  * 人民币中间价：CFETS chinamoney ccpr.json（当日快照）

不抓的部分：海运费、保险费、关税、国内现货价 —— 多为付费源或需逐条核验，
请在 research.json 里手工登记并写清 source；取不到就写 gaps，不要估算。
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wio  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def http_get(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def get_json(url, timeout=40):
    txt = http_get(url, timeout)
    i = txt.find("{")
    return json.loads(txt[i:] if i > 0 else txt)


def fetch_futures(symbol):
    url = ("https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_x=/"
           "InnerFuturesNewService.getDailyKLine?symbol=" + symbol)
    t = http_get(url)
    i = t.find("[{")
    if i < 0:
        return {"symbol": symbol, "source": "sina", "source_url": url, "rows": []}
    arr = json.loads(t[i:t.rindex("]") + 1])
    out = []
    for x in arr:
        try:
            out.append({"date": x["d"], "open": float(x["o"]), "high": float(x["h"]),
                        "low": float(x["l"]), "close": float(x["c"]), "volume": float(x["v"])})
        except (KeyError, ValueError):
            continue
    return {"symbol": symbol,
            "source": "新浪财经 InnerFuturesNewService.getDailyKLine（主连日线）",
            "source_url": url,
            "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
            "rows": out}


def fetch_fx(start, end):
    url = "https://api.frankfurter.app/%s..%s?from=USD&to=CNY" % (start, end)
    d = get_json(url)
    rows = [{"date": k, "usdcny": v["CNY"]} for k, v in sorted(d.get("rates", {}).items())]
    return {"pair": "USD/CNY", "source": "Frankfurter / 欧洲央行 ECB 每日参考汇率",
            "source_url": url,
            "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
            "note": "ECB 参考汇率只覆盖工作日，不含周末与欧洲节假日；是参考汇率而非银行间即期成交价",
            "rows": rows}


def fetch_pboc():
    url = "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json"
    d = get_json(url)
    usd = None
    for row in d.get("records", []):
        if (row.get("vrtEName") or "").upper() == "USD/CNY":
            usd = {"mid": float(row.get("price")), "date": d.get("data", {}).get("lastDate")}
            break
    return {"source": "中国外汇交易中心 CFETS 人民币汇率中间价", "source_url": url,
            "fetched_at": dt.datetime.now().isoformat(timespec="seconds"), "usd_cny": usd}


def save(obj, path):
    wio.dump_json(obj, path)
    wio.ok("%s（%d 行）" % (path, len(obj.get("rows", []))))


def main():
    ap = argparse.ArgumentParser(description="抓取公开原始数据到 raw/")
    ap.add_argument("--futures", default=None, help="期货主连代码，如 EG0 / MA0 / SA0")
    ap.add_argument("--fx", default=None, help="汇率区间 START:END，如 2025-10-01:2026-10-20")
    ap.add_argument("--pboc", action="store_true", help="抓当日人民币中间价快照")
    ap.add_argument("--out", default=None, help="单文件输出路径（只抓一项时使用）")
    ap.add_argument("--out-dir", default="raw")
    args = ap.parse_args()
    if not (args.futures or args.fx or args.pboc):
        wio.die("至少要指定 --futures / --fx / --pboc 之一")
    if args.out:
        if args.futures:
            save(fetch_futures(args.futures), args.out)
        elif args.fx:
            a, b = args.fx.split(":")
            save(fetch_fx(a, b), args.out)
        else:
            save(fetch_pboc(), args.out)
        return
    os.makedirs(args.out_dir, exist_ok=True)
    if args.futures:
        save(fetch_futures(args.futures), os.path.join(args.out_dir, args.futures.lower() + "_daily.json"))
    if args.fx:
        a, b = args.fx.split(":")
        save(fetch_fx(a, b), os.path.join(args.out_dir, "usdcny.json"))
    if args.pboc:
        try:
            save(fetch_pboc(), os.path.join(args.out_dir, "pboc_ccpr.json"))
        except Exception as e:
            wio.warn("中间价快照抓取失败：%s" % e)


if __name__ == "__main__":
    main()
