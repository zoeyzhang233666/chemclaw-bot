# -*- coding: utf-8 -*-
"""把解析出的原始观测 -> 分析数据集（含统计、分位、季节性、异常、缺口、口径变更）。

输出 build/data.json，供 build_html.py / build_xlsx.py 共用，保证 HTML 与 Excel 同源同数。

核心口径（全部来自 raw/ppi_observations.json，无一处插值/模拟）：
  S1 华东·重质纯碱·主流市场区间（低端/高端/中值）  2024-07 起
  S2 华东·轻质纯碱·主流市场区间                     全窗口
  S3 全国·重质纯碱·生意社基准价（单点）             全窗口
三者是三条独立序列，各自标注口径，绝不拼接。
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import price_stats as PS

RAW = "raw/ppi_observations.json"
OUT = "build/data.json"

D = json.load(open(RAW, encoding="utf-8"))


def rows_of(bucket):
    return sorted(D[bucket].values(), key=lambda r: r["data_date"])


hd = rows_of("huadong")
bh = rows_of("bench_h")
bl = rows_of("bench_l")


def build(bucket, pick, label):
    """pick(rec) -> (低端, 高端) 或 None"""
    rows = []
    for r in rows_of(bucket):
        p = pick(r)
        if not p or p[0] is None:
            continue
        lo, hi = p
        rows.append({"date": r["data_date"], "lo": float(lo), "hi": float(hi),
                     "mid": round((float(lo) + float(hi)) / 2.0, 2),
                     "url": r.get("url"), "basis": r.get("basis"), "unit": r.get("unit")})
    seen = {}
    for x in rows:
        seen[x["date"]] = x
    return sorted(seen.values(), key=lambda x: x["date"])


def build_bench(bucket):
    rows = []
    for r in rows_of(bucket):
        rows.append({"date": r["data_date"], "value": float(r["value"]),
                     "url": r.get("url"), "unit": r.get("unit")})
    seen = {}
    for x in rows:
        seen[x["date"]] = x
    return sorted(seen.values(), key=lambda x: x["date"])


S1 = build("huadong", lambda r: (r["heavy_lo"], r["heavy_hi"]), "华东重质")
S2 = build("huadong", lambda r: (r["light_lo"], r["light_hi"]), "华东轻质")
S3 = build_bench("bench_h")

# ---------------------------------------------------------------- 基准日
asof = datetime.date.fromisoformat(max(x["date"] for x in S1))
ASOF = asof


def series_of(rows, key):
    out, _, _ = PS.clean_series([{"date": r["date"], "value": r[key]} for r in rows])
    return out


def analyse(rows, key, asof, windows=(30, 90, 365, 1095, 1826)):
    ser = series_of(rows, key)
    if not ser:
        return None
    # 各序列的「最新可靠报价」以该序列自身的末条为准，但不得晚于报告基准日；
    # 窗口也统一以这个参考日回看，保证 分位/区间位置/涨跌 三者互相自洽。
    ref = max([d for d, _ in ser if d <= asof] or [ser[0][0]])
    ref_value = dict(ser)[ref]
    ser = [(d, v) for d, v in ser if d <= ref]
    last_date, last_value = ref, ref_value
    res = {
        "series_n": len(ser),
        "first_date": ser[0][0].isoformat(),
        "last_date": last_date.isoformat(),
        "last_value": round(last_value, 2),
        "stale_days": (asof - last_date).days,
        "windows": {},
        "volatility": {},
        "anomalies": {},
        "gaps": PS.find_gaps(ser, asof, ser[0][0]),
        "mdd": None,
    }
    for w in windows:
        sub = PS.window_slice(ser, ref, w)
        vals = [v for _, v in sub]
        if not vals:
            res["windows"][str(w)] = {"available": False, "reason": "窗口内无有效观测"}
            continue
        d = PS.describe(vals)
        pct = PS.empirical_percentile(vals, last_value) if len(vals) >= PS.MIN_OBS else None
        res["windows"][str(w)] = {
            "available": len(vals) >= PS.MIN_OBS,
            "n_obs": len(vals),
            "from": sub[0][0].isoformat(), "to": sub[-1][0].isoformat(),
            "stats": d,
            "percentile": pct,
            "range_position_pct": PS.ranged_position(vals, last_value),
            "change": PS.change_metrics(ser, ref, w),
            "insufficient_sample": len(vals) < PS.MIN_OBS,
        }
    for w in (30, 90, 365):
        res["volatility"][str(w)] = PS.volatility_metrics(ser, ref, w)
    res["anomalies"] = {
        "level": [a for a in PS.detect_anomalies(ser) if any(f["rule"] != "jump" for f in a["flags"])],
        "jump": [a for a in PS.detect_anomalies(ser) if any(f["rule"] == "jump" for f in a["flags"])],
    }
    res["mdd"] = PS.max_drawdown(ser)
    res["seasonality"] = PS.seasonality(ser)
    res["_series"] = [{"date": d.isoformat(), "value": round(v, 2)} for d, v in ser]
    return res


DATA = {
    "meta": {
        "product": "纯碱",
        "spec": "重质纯碱（≥99.2%，GB/T 210-2022 优等品口径）",
        "region": "华东",
        "asof": ASOF.isoformat(),
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "unit": "元/吨",
        "tax": "含税（增值税13%）",
        "delivery": "主流市场报价 / 实单商谈（非严格出厂或送到）",
        "source": "生意社（100ppi.com）华东地区纯碱市场日评 + 生意社基准价",
        "source_url": "https://www.100ppi.com/news/list--12-1.html",
    },
    "series": {
        "S1": {"name": "华东·重质纯碱·主流市场区间中值", "role": "主口径",
               "note": "华东地区重质纯碱「主流市场报价区间」的中值；区间低端/高端各自单列计算，不做加权。",
               "data": S1},
        "S2": {"name": "华东·轻质纯碱·主流市场区间中值", "role": "辅助口径（跨期可比性对照）",
               "note": "华东轻质纯碱报价区间中值。2024-07 之前华东日评实际只披露轻质价，故其历史更长，但不能替代重碱。",
               "data": S2},
        "S3": {"name": "全国·重质纯碱·生意社基准价", "role": "辅助口径（全国基准，非华东）",
               "note": "生意社基准价，样本为全国范围，口径与华东区域报价不同，不可互换、不可拼接。",
               "data": S3},
    },
    "analysis": {
        "S1_mid": analyse(S1, "mid", ASOF),
        "S1_lo": analyse(S1, "lo", ASOF),
        "S1_hi": analyse(S1, "hi", ASOF),
        "S2_mid": analyse(S2, "mid", ASOF),
        "S3_value": analyse(S3, "value", ASOF),
    },
}

# ---------------------------------------------------------------- 口径变更
chg = []
for k, lab, key in (("S1", "华东重质纯碱", "heavy_lo"), ("S2", "华东轻质纯碱", "light_lo")):
    cov = {}
    for r in hd:
        m = r["data_date"][:7]
        c = cov.setdefault(m, [0, 0])
        c[0] += 1
        if r[key] is not None:
            c[1] += 1
    full = [m for m, c in sorted(cov.items()) if c[1] == c[0]]
    part = [m for m, c in sorted(cov.items()) if 0 < c[1] < c[0]]
    zero = [m for m, c in sorted(cov.items()) if c[1] == 0]
    chg.append({"series": k, "label": lab,
                "months_total": len(cov),
                "months_full": len(full), "months_partial": len(part), "months_zero": len(zero),
                "first_full_month": full[0] if full else None,
                "last_zero_month": zero[-1] if zero else None,
                "coverage": [{"month": m, "total": c[0], "with_value": c[1]} for m, c in sorted(cov.items())]})
DATA["coverage_change"] = chg

# ---------------------------------------------------------------- 口径与备注
_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
_ev = os.path.join(_DATA, "events.json")
DATA["events"] = json.load(open(_ev, encoding="utf-8"))["events"] if os.path.exists(_ev) else []

DATA["caveats"] = [
    {"level": "bad", "title": "口径断点（最重要，直接影响 3 年/5 年分位的解读）：",
     "body": "生意社「华东地区纯碱」日评在 <b>2024 年 7 月之前只披露轻质纯碱或不区分规格的「纯碱主流报价」</b>，"
             "重质纯碱价格<b>根本没有公开日度记录</b>。本报告的 3 年/5 年重质分位，实际样本是 "
             "<b>2024-07-17 起的 358 条</b>，不是「完整 3 年」。<br>"
             "对客户必须这么说：<i>「三年分位」这个数是拿真实观测算的，但能算三年分位的品种只有最近两年多的记录，"
             "再往前没有公开的重碱日度价。</i> 用轻质序列去冒充重碱、或用全国基准价去冒充华东价，都是错的。"},
    {"level": "info", "title": "三条序列不可互换：",
     "body": "S1 华东·重质（主口径）、S2 华东·轻质（同区域不同规格）、S3 全国·重质·生意社基准价"
             "（同规格不同区域）。三者各自独立计算分位，<b>不做拼接、不做换算、不做对齐</b>。"
             "S2 与 S3 只用于回答「华东这个价到底是华东特有，还是全国同步」这类问题。"},
    {"level": "info", "title": "价格性质：",
     "body": "华东日评给的是<b>主流市场报价区间</b>（如 1180-1250 元/吨），并注明「实单以商谈为主」。"
             "本报告用<b>区间中值</b>做主序列，区间上下沿各自单独计算（Excel 表 03 保留 lo/hi/mid 三列）。"
             "中值是报价区间的中点，<b>不是成交价</b>。"},
    {"level": "", "title": "含税与交付：",
     "body": "生意社华东纯碱报价为<b>含税（13% 增值税）</b>、<b>出厂/主流市场报价</b>口径，"
             "不等于下游玻璃厂的到厂价；跨区调货、账期、品牌升贴水均未包含在内。"},
    {"level": "", "title": "交易日历：",
     "body": "该序列只在工作日发布，周末与法定节假日无报价。因此<b>缺口按工作日统计</b>，"
             "单日缺失多为节假日或当日未发布日评；这些位置一律留空，<b>不做前值填充</b>——"
             "填充会人为压低波动率、把分位算偏。"},
    {"level": "", "title": "分位口径说明：",
     "body": "报告同时给出「经验分位（含并列）」与「经验分位（中位秩）」，并单独列出「区间位置」。"
             "现货价格是锯齿状的，大量日期取值完全相同（报价未变），"
             "此时三种算法会出现明显差异（例如当前价恰为窗口最低点：含并列分位 0.72%、"
             "区间位置 0.0%）。<b>三个数都对，含义不同，不能混用</b>。"},
]

DATA["sources"] = [
    {"name": "生意社（100ppi.com）纯碱频道 · 商品动态",
     "used_for": "全部价格观测的原始出处（华东日评 %d 篇 + 基准价 %d 篇）"
                 % (len(hd), len(bh)),
     "url": "https://soda.100ppi.com/news/list--12-1.html"},
    {"name": "生意社 华东地区纯碱市场日评（逐篇）",
     "used_for": "S1 华东重质 / S2 华东轻质 的区间低-高-中值，每行均可点开原文核对",
     "url": "https://www.100ppi.com/news/detail-20260728-5990717.html"},
    {"name": "生意社 重质纯碱基准价（逐日）",
     "used_for": "S3 全国重质基准价序列",
     "url": "https://www.100ppi.com/rawmex/detail-737.html"},
    {"name": "东方汇金期货晨会纪要（2025-09-08）",
     "used_for": "第三方同日口径交叉校验（华东重碱 1260-1320 元/吨，库存 182.21 万吨）",
     "url": "https://www.dfhjqh.com/news/1316.html"},
]


json.dump(DATA, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok", OUT, "S1", len(S1), "S2", len(S2), "S3", len(S3))
