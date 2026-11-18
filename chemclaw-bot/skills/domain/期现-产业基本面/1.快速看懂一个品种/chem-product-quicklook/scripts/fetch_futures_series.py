"""拉取郑商所甲醇(MA0)主连日线：新浪 InnerFuturesNewService，保存为 build_anchors.py 可读格式"""
import json, re, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0", "Referer": "https://finance.sina.com.cn"}
URL = "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/InnerFuturesNewService.getDailyKLine?symbol=MA0"
raw = urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=25).read().decode("utf-8", "replace")
m = re.search(r"\[.*\]", raw, re.S)
rows = json.loads(m.group(0))
out = []
for r in rows:
    out.append({"d": r["d"], "o": float(r["o"]), "h": float(r["h"]), "l": float(r["l"]),
                "c": float(r["c"]), "v": float(r["v"]), "oi": float(r["p"]) if r.get("p") else None,
                "settle": float(r["s"]) if r.get("s") else None})
out.sort(key=lambda x: x["d"])
doc = {"symbol": "MA0", "exchange": "郑州商品交易所", "unit": "元/吨",
       "note": "主连（连续合约拼接）；合约价不含税，含交易所交割相关成本",
       "count": len(out), "first": out[0]["d"], "last": out[-1]["d"], "rows": out}
json.dump(doc, open("raw/MA0_daily_sina.json", "w", encoding="utf-8"), ensure_ascii=False)
print("rows", len(out), out[0]["d"], "→", out[-1]["d"], "last close", out[-1]["c"], "settle", out[-1]["settle"])
