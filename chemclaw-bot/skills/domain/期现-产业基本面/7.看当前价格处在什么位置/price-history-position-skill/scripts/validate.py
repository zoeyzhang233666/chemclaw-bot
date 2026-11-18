# -*- coding: utf-8 -*-
"""数据一致性与合理性校验：把 build/data.json 与原始观测、公开事实三方交叉核对。"""
import json
import sys
import datetime

FAIL = []
WARN = []


def chk(cond, msg):
    if not cond:
        FAIL.append(msg)


def warn(cond, msg):
    if not cond:
        WARN.append(msg)


D = json.load(open("build/data.json", encoding="utf-8"))
RAW = json.load(open("raw/ppi_observations.json", encoding="utf-8"))
A = D["analysis"]
S1 = D["series"]["S1"]["data"]
S2 = D["series"]["S2"]["data"]
S3 = D["series"]["S3"]["data"]
M = D["meta"]

lines = []
lines.append("== 基本 ==")
lines.append("asof=%s  S1=%d  S2=%d  S3=%d" % (M["asof"], len(S1), len(S2), len(S3)))
chk(len(S1) > 300, "S1 观测数过少：%d" % len(S1))
chk(len(S3) > 300, "S3 观测数过少：%d" % len(S3))

# 1 与原始观测条数一致
raw_h = [r for r in RAW["huadong"].values() if r["heavy_lo"] is not None]
lines.append("原始华东重质观测=%d  数据集=%d" % (len(raw_h), len(S1)))
chk(abs(len(raw_h) - len(S1)) <= 2, "华东重质观测数与原始不一致")

# 2 一致性：当前值 = 序列末值 = 窗口末值
a1 = A["S1_mid"]
last = S1[-1]
lines.append("末条 %s = %.2f  分析 last_value=%.2f  last_date=%s" %
             (last["date"], last["mid"], a1["last_value"], a1["last_date"]))
chk(abs(last["mid"] - a1["last_value"]) < 1e-6, "last_value 与序列末值不符")
chk(last["date"] == a1["last_date"], "last_date 与序列末日不符")

# 3 经验分位必须落在 [0,100]，且与手算一致
for w, v in a1["windows"].items():
    if not v.get("available"):
        continue
    sub = [x for x in S1 if (datetime.date.fromisoformat(a1["last_date"]) -
                             datetime.timedelta(days=int(w))) <
           datetime.date.fromisoformat(x["date"]) <= datetime.date.fromisoformat(a1["last_date"])]
    vals = [x["mid"] for x in sub]
    x = a1["last_value"]
    exp_incl = sum(1 for t in vals if t <= x) / len(vals) * 100
    exp_mid = (sum(1 for t in vals if t < x) + 0.5 * sum(1 for t in vals if t == x)) / len(vals) * 100
    got = v["percentile"]
    ok = abs(exp_incl - got["percentile_inclusive_pct"]) < 0.02 and abs(exp_mid - got["percentile_midrank_pct"]) < 0.02
    lines.append("  %ss: n=%d incl=%.2f(exp %.2f) mid=%.2f(exp %.2f) %s" %
                 (w, len(vals), got["percentile_inclusive_pct"], exp_incl,
                  got["percentile_midrank_pct"], exp_mid, "OK" if ok else "MISMATCH"))
    chk(ok, "窗口 %s 的分位与手算不一致" % w)
    chk(len(vals) == v["n_obs"], "窗口 %s 样本数不一致 (%d vs %d)" % (w, len(vals), v["n_obs"]))
    chk(0 <= got["percentile_inclusive_pct"] <= 100, "分位越界")
    # 区间位置 ≠ 分位：确认两者是不同数
    rp = v["range_position_pct"]
    st = v["stats"]
    exp_rp = (x - st["min"]) / (st["max"] - st["min"]) * 100 if st["max"] > st["min"] else None
    if exp_rp is not None:
        chk(abs(exp_rp - rp) < 0.02, "窗口 %s 区间位置计算不符" % w)

# 4 统计量复算
for w in ("365", "1095"):
    v = a1["windows"][w]
    sub = [x["mid"] for x in S1 if (datetime.date.fromisoformat(a1["last_date"]) -
                                    datetime.timedelta(days=int(w))) <
           datetime.date.fromisoformat(x["date"]) <= datetime.date.fromisoformat(a1["last_date"])]
    st = v["stats"]
    chk(abs(min(sub) - st["min"]) < 1e-6, "窗口 %s min 不符" % w)
    chk(abs(max(sub) - st["max"]) < 1e-6, "窗口 %s max 不符" % w)
    chk(abs(sum(sub) / len(sub) - st["mean"]) < 0.01, "窗口 %s mean 不符" % w)
    ss = sorted(sub)
    med = ss[len(ss) // 2] if len(ss) % 2 else (ss[len(ss) // 2 - 1] + ss[len(ss) // 2]) / 2
    chk(abs(med - st["median"]) < 0.01, "窗口 %s median 不符" % w)
    lines.append("  %ss stats min=%.2f max=%.2f mean=%.2f med=%.2f OK" % (w, st["min"], st["max"], st["mean"], st["median"]))

# 5 外部事实交叉校验：2026-07-28 华东重碱应为 1180-1250
row = [x for x in S1 if x["date"] == "2026-07-28"]
if row:
    lines.append("2026-07-28 华东重碱 %s-%s" % (row[0]["lo"], row[0]["hi"]))
    chk(row[0]["lo"] == 1180 and row[0]["hi"] == 1250, "2026-07-28 重碱区间与原文不符")

# 6 缺口/异常结构
lines.append("缺口段=%d  单日缺失=%d  水平异常=%d  跳变=%d" %
             (a1["gaps"]["run_count"], a1["gaps"]["single_missing"],
              len(a1["anomalies"]["level"]), len(a1["anomalies"]["jump"])))
chk(a1["gaps"]["run_count"] >= 0, "缺口结构异常")
for x in a1["anomalies"]["jump"]:
    for f in x["flags"]:
        if f["rule"] == "jump":
            chk(abs(f["pct"]) >= 3.0, "跳变阈值未生效")

# 7 序列单调日期 & 无重复
for nm, s in (("S1", S1), ("S2", S2), ("S3", S3)):
    ds = [x["date"] for x in s]
    chk(ds == sorted(ds), "%s 未按日期升序" % nm)
    chk(len(ds) == len(set(ds)), "%s 存在重复日期" % nm)
    chk(all(x.get("url") for x in s), "%s 存在缺来源链接的观测" % nm)

# 8 无插值与模拟价的痕迹：相邻两天数值相同是允许的（报价未变），
#   但不允许出现"凭空多出来的日期"——每个日期都必须能在原始文章里找到
raw_dates = {r["data_date"] for r in RAW["huadong"].values()}
for x in S1:
    chk(x["date"] in raw_dates, "S1 出现原始观测中不存在的日期：%s" % x["date"])

lines.append("")
lines.append("FAIL=%d WARN=%d" % (len(FAIL), len(WARN)))
for f in FAIL:
    lines.append("  [FAIL] " + f)
for w in WARN:
    lines.append("  [WARN] " + w)
open("raw/qa_validate.txt", "w", encoding="utf-8").write("\n".join(lines))
print("FAIL", len(FAIL), "WARN", len(WARN))
