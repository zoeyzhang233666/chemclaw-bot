# -*- coding: utf-8 -*-
"""
extract_fundamentals.py — 从生意社 PP 分析评论文章中抽取基本面数值序列

抽取字段（均为原文明确写出的数值，不做任何推算）
------------------------------------------------
  inventory  : 库存（万吨）      "库存位置继续下滑致不足49万吨"
  operating  : 行业开工率（%）    "前半月总体开工率接近70%"
  downstream : 下游开工率（%）    "月底下游负荷45%左右"
  spot_lasi  : PP拉丝基准价      "生意社PP拉丝基准价报盘价格9933.33元/吨"
  weekly_out : 周均产量（万吨）   "当前周均产量不足70万吨"

每条记录带 source_url / pub_date / quote，便于审计。
"""
import csv
import glob
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS = os.path.join(BASE, "data", "raw", "news")
OUT = os.path.join(BASE, "data", "raw", "pp_fundamentals.csv")

# --- 数值中文与阿拉伯数字互转 ---
CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def cn2num(s):
    if not s:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return float(s)
    if s in CN_NUM:
        return float(CN_NUM[s])
    if s.startswith("十"):
        return float(10 + CN_NUM.get(s[1:], 0))
    return None


PATTERNS = [
    # (字段, 正则, 单位, 说明)
    ("inventory", r"库存[^。]{0,40}?(?:不足|降至|降至约|至|达到|为|报)?\s*(\d{1,3}(?:\.\d+)?)\s*万吨", "万吨", "库存"),
    ("operating", r"(?:行业|装置|总体|平均)?开工率[^。]{0,25}?(\d{1,2}(?:\.\d+)?)\s*%", "%", "开工率"),
    ("downstream", r"下游[^。]{0,15}?(?:负荷|开工率)[^。]{0,15}?(\d{1,2}(?:\.\d+)?)\s*%", "%", "下游负荷"),
    ("spot_lasi", r"PP拉丝基准价[^。]{0,20}?(\d{4,5}(?:\.\d+)?)\s*元/吨", "元/吨", "拉丝基准价"),
    ("weekly_out", r"周均产量[^。]{0,15}?(\d{1,3}(?:\.\d+)?)\s*万吨", "万吨", "周均产量"),
]


def clean_body(txt):
    t = re.sub(r"<[^>]+>", " ", txt)
    t = re.sub(r"\s+", " ", t)
    return t


def main():
    rows = []
    files = sorted(glob.glob(os.path.join(NEWS, "*.txt")))
    print("files", len(files))
    for fn in files:
        raw = open(fn, encoding="utf-8", errors="ignore").read()
        head = {}
        for line in raw.split("\n")[:3]:
            if ":" in line:
                k, v = line.split(":", 1)
                head[k.strip()] = v.strip()
        pub = head.get("DATE", "")
        url = head.get("URL", "")
        title = head.get("TITLE", "")
        body = clean_body(raw)
        for field, pat, unit, label in PATTERNS:
            for m in re.finditer(pat, body):
                try:
                    v = float(m.group(1))
                except Exception:
                    continue
                # 合理性过滤
                if field == "inventory" and not (10 <= v <= 300):
                    continue
                if field in ("operating", "downstream") and not (30 <= v <= 100):
                    continue
                if field == "spot_lasi" and not (4000 <= v <= 20000):
                    continue
                if field == "weekly_out" and not (20 <= v <= 150):
                    continue
                rows.append({
                    "pub_date": pub, "field": field, "value": v, "unit": unit,
                    "quote": body[max(0, m.start() - 30):m.end() + 20].strip(),
                    "title": title, "source_url": url,
                })
    # 同日同字段取第一条
    seen = {}
    for r in rows:
        k = (r["pub_date"], r["field"])
        if k not in seen:
            seen[k] = r
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["pub_date", "field", "value", "unit", "quote", "title", "source_url"])
        w.writeheader()
        for k in sorted(seen):
            w.writerow(seen[k])
    print("records", len(seen), "->", OUT)
    from collections import Counter
    print(Counter(r["field"] for r in seen.values()))


if __name__ == "__main__":
    main()
