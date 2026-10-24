# -*- coding: utf-8 -*-
"""
统一研究样本构建（甲醇港口库存周度变化 × 甲醇期货周度收益率）
数据源：
  A 指标：隆众资讯「中国甲醇样本港口库存周数据统计」101 期，含精确发布时间（毫秒时间戳）
  B 指标：郑商所甲醇主连（MA0）日线收盘价
"""
import json, math, datetime, os, statistics as st

W = str(__import__('pathlib').Path.cwd())
OUT = W + r"\leadlag-methanol\build"
os.makedirs(OUT, exist_ok=True)
TZ8 = datetime.timezone(datetime.timedelta(hours=8))


def local_dt(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, TZ8)


# ---------- 1) 库存原始记录 ----------
raw = json.load(open(W + r"\_ll_fetch\port_inv_raw.json", encoding="utf-8"))
inv = []
for it in raw:
    c = it["contentWithOutHtmlTag"]
    stat = it["title"].split("(")[-1].replace("）", "").replace(")", "")
    stat = datetime.date(int(stat[:4]), int(stat[4:6]), int(stat[6:8]))
    total = float(c.split("港口库存总量在")[1].split("万吨")[0])
    chg_txt = c.split("较上一期数据")[1][:12]
    inv.append({"stat": stat, "pub": local_dt(it["publishTime"]), "total": total,
                "url": it["url"], "title": it["title"], "content": c})
inv.sort(key=lambda r: r["stat"])
for i, r in enumerate(inv):
    r["woi"] = r["total"]  # placeholder

# 库存级数据检查
# 华东/华南拆分
import re
for r in inv:
    c = r["content"]
    me = re.search(r"华东地区(\S{2,4})，库存(增加|减少)([\d.]+)万吨", c)
    ms = re.search(r"华南地区(\S{2,4})，库存(增加|减少)([\d.]+)万吨", c)
    r["east_chg"] = float(me.group(3)) * (1 if me.group(2) == "增加" else -1) if me else None
    r["south_chg"] = float(ms.group(3)) * (1 if ms.group(2) == "增加" else -1) if ms else None
    r["east_dir"] = me.group(1) if me else ""
    r["south_dir"] = ms.group(1) if ms else ""

# ---------- 2) 期货日线 ----------
fut = json.load(open(W + r"\methanol-attrib\raw\MA0_daily.json", encoding="utf-8"))
fut = sorted(fut, key=lambda x: x["date"])
fdates = [x["date"] for x in fut]
fclose = {x["date"]: float(x["close"]) for x in fut}
fsettle = {x["date"]: float(x.get("settle") or x["close"]) for x in fut}
fvol = {x["date"]: float(x.get("volume") or 0) for x in fut}


def prev_trading_day(d):  # 严格早于 d 的最后一个交易日
    import bisect
    i = bisect.bisect_left(fdates, d.isoformat())
    return fdates[i - 1] if i > 0 else None


def on_or_before(d):  # <= d 的最后交易日
    import bisect
    i = bisect.bisect_right(fdates, d.isoformat())
    return fdates[i - 1] if i > 0 else None


# ---------- 3) 报告期与可获取时点 ----------
# 库存：统计日=发布日（14:00 前后，盘中），披露日 d 当天 11:30 期货收盘价是该周唯一“在披露前已定格”的价格
for i, r in enumerate(inv):
    r["pub_date"] = r["pub"].date()
    r["pub_hm"] = r["pub"].strftime("%H:%M")
    assert r["pub_date"] == r["stat"], (r["stat"], r["pub_date"])
    r["P_prev"] = fclose[prev_trading_day(r["stat"])]      # 披露前最后收盘（11:30 定格）
    r["P_pub"] = fclose[on_or_before(r["stat"])]            # 披露当日收盘
    r["stat_last_td"] = prev_trading_day(r["stat"])         # 报告期最后交易日
    r["ret"] = math.log(r["P_pub"] / r["P_prev"])           # 披露日当日收益率（对数）
    r["ret_simple"] = r["P_pub"] / r["P_prev"] - 1

# 周度收益：市场观察者从“上一披露后”到“本次披露前”可见的收益（严格可得）
for i, r in enumerate(inv):
    if i == 0:
        r["ret_avail"] = None
    else:
        p0 = inv[i - 1]["P_pub"]
        r["ret_avail"] = r["P_pub"] / p0 - 1               # 简单收益，可加性更好
    r["lret_avail"] = (r["P_pub"] / inv[i - 1]["P_pub"]) if i > 0 else None

# 库存变化
for i, r in enumerate(inv):
    if i == 0:
        r["dI"] = None; r["dI_pct"] = None; r["dI_float"] = None
    else:
        r["dI"] = r["total"] - inv[i - 1]["total"]
        r["dI_pct"] = r["dI"] / inv[i - 1]["total"] * 100.0
        r["zI"] = None
# 浮动比例：vs 最新75%历史窗口分位
for i, r in enumerate(inv):
    if i >= 3:
        lo, hi = min(x["total"] for x in inv[max(0, i - 52):i]), max(x["total"] for x in inv[max(0, i - 52):i])
        r["dI_float"] = (r["total"] - lo) / (hi - lo) if hi > lo else None
    else:
        r["dI_float"] = None

# Lag 定义：
#   Lag = +k (k>=0)：A(库存) 在第 t 期先公布，B(收益) 取第 t+k 期  -> A 领先 B k 周
#   Lag = -k：B 取第 t-k 期 -> 实际上 A 滞后于 B k 周（检查 B 是否先行）
def pair(series_a, series_b, lag):
    """返回 [(t, a[t], b[t+lag])]"""
    out = []
    n = len(series_a)
    for t in range(n):
        j = t + lag
        if 0 <= j < n:
            a, b = series_a[t], series_b[j]
            if a is None or b is None:
                continue
            out.append((t, a, b))
    return out


series = {
    "dI": [r["dI"] for r in inv],
    "dI_pct": [r["dI_pct"] for r in inv],
    "dI_float": [r["dI_float"] for r in inv],
    "ret": [r["ret"] for r in inv],
    "ret_avail": [r.get("ret_avail") for r in inv],
    "ret01": [],   # 披露日收益 = 披露前到披露后，即 [P_prev -> P_pub]
}
# 由 P_t 与 P_{t-1} 计算的周收益（观察者视角，严格可用）
for i, r in enumerate(inv):
    series["ret01"].append(r["ret_avail"])

meta = {
    "n": len(inv),
    "start": inv[0]["stat"].isoformat(),
    "end": inv[-1]["stat"].isoformat(),
    "inv_min": min(r["total"] for r in inv),
    "inv_max": max(r["total"] for r in inv),
    "fut_start": fdates[0] if fdates[0] >= "2024" else fdates[0],
}
print(json.dumps(meta, ensure_ascii=False))

out = []
for r in inv:
    out.append({k: (v.isoformat() if isinstance(v, (datetime.date, datetime.datetime)) else v)
                for k, v in r.items() if k not in ("content",)})
json.dump({"rows": out, "meta": meta}, open(OUT + r"\sample.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved", OUT + r"\sample.json", "rows", len(out))
print(out[0])
print(out[1])
