# -*- coding: utf-8 -*-
"""selftest.py — 用合成数据验证核心算法（离线可跑，不需要任何网络）

验证项：
  1. 交易日历对齐：非交易日顺延到首个交易日
  2. 换月复权：换月日收益 == 旧合约真实涨跌（这是我们复权正确性的判据）
  3. 事件窗口收益：手工算例与函数一致
  4. 市场模型 AR：构造已知 beta 的数据，看是否复原
  5. 去重与重叠检测
  6. 缺失窗口不产生伪造数值

运行：python scripts/selftest.py
"""
from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")

import core  # noqa: E402
import eventstudy as es  # noqa: E402
import build_prices as bp  # noqa: E402

FAILS = []
OKS = []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name)
    print(("  [OK]   " if cond else "  [FAIL] ") + name + (f"  {detail}" if detail else ""))


def t1_trading_day():
    print("\n① 交易日对齐")
    days = ["2026-06-11", "2026-06-12", "2026-06-15", "2026-06-16", "2026-06-17"]
    cal = es.TradingCalendar(days)
    check("交易日原样返回", cal.next_on_or_after("2026-06-15") == "2026-06-15")
    check("周六顺延到周一", cal.next_on_or_after("2026-06-13") == "2026-06-15",
          f"2026-06-13(周六)->{cal.next_on_or_after('2026-06-13')}")
    check("周日顺延到周一", cal.next_on_or_after("2026-06-14") == "2026-06-15")
    check("超出日历返回 None", cal.next_on_or_after("2026-07-01") is None)


def t2_roll_adjust():
    print("\n② 换月复权（核心正确性判据）")
    # 判据（panama 后向复权）：
    #   (1) 段内（同一合约）相邻日收益 == 原始收益
    #   (2) 换月日跳空 == 0（换月价差被消除，不当作涨跌）
    #   (3) 最新一天价格 == 真实成交价（不做缩放）
    def mk(pairs):
        return [{"date": f"d{i}", "contract": c, "close": p} for i, (c, p) in enumerate(pairs)]

    def run(pairs, label):
        out = bp.add_adjusted(mk(pairs))
        adj = [r["adj_close"] for r in out]
        ok_all = True
        for i in range(1, len(adj)):
            raw = pairs[i][1] / pairs[i - 1][1] - 1
            got = adj[i] / adj[i - 1] - 1
            is_roll = pairs[i][0] != pairs[i - 1][0]
            ok = (abs(got) < 1e-9) if is_roll else (abs(raw - got) < 1e-9)
            ok_all = ok_all and ok
        last_ok = abs(adj[-1] - pairs[-1][1]) < 1e-9
        return adj, ok_all and last_ok

    a, ok = run([("OLD", 100.0), ("OLD", 110.0), ("NEW", 90.0)], "single")
    check("单次换月：段内真实 + 跳空归零 + 最新价真实", ok, f"adj={[round(x,2) for x in a]}")
    check("单次换月：跳空确实为 0", abs(a[2] / a[1] - 1) < 1e-9, f"{((a[2]/a[1]-1)*100):.2f}%")
    check("单次换月：段内收益保持 +10%", abs((a[1] / a[0] - 1) - 0.10) < 1e-9,
          f"{((a[1]/a[0]-1)*100):.2f}%")

    a2, ok2 = run([("A", 100.0), ("A", 120.0), ("B", 60.0), ("B", 66.0), ("C", 30.0)], "multi")
    check("多段换月：段内真实 + 跳空归零 + 最新价真实", ok2, f"adj={[round(x,2) for x in a2]}")
    check("多段换月：A 段内 +20%", abs((a2[1] / a2[0] - 1) - 0.20) < 1e-9)
    check("多段换月：B 段内 +10%", abs((a2[3] / a2[2] - 1) - 0.10) < 1e-9)
    check("多段换月：两个换月日跳空均为 0",
          abs(a2[2] / a2[1] - 1) < 1e-9 and abs(a2[4] / a2[3] - 1) < 1e-9)

    a3, ok3 = run([("A", 100.0), ("B", 50.0)], "two-day")
    check("只跨一天的两行：跳空归零", ok3, f"adj={[round(x,2) for x in a3]}")


def t3_window_returns():
    print("\n③ 事件窗口收益")
    tmp = tempfile.mkdtemp()
    days = [f"2026-01-{d:02d}" for d in range(1, 32)]
    rows = [{"date": d, "close": str(100 + i), "adj_close": str(100 + i),
             "contract": "T", "volume": "9999", "oi": "9999"} for i, d in enumerate(days)]
    p = os.path.join(tmp, "prices.csv")
    core.write_csv(p, rows)
    panel = es.PricePanel(core.read_csv(p), "date", "close")
    d0, d5 = days[0], days[5]
    expect = (105.0 / 100.0 - 1) * 100
    got = panel.ret(d0, d5)
    check("t+5 收益与手工算例一致", abs(got - expect) < 1e-9, f"{got:.4f} vs {expect:.4f}")
    check("越界窗口返回 None 而不是编数", panel.ret(d0, "2026-03-01") is None)


def t4_market_model():
    print("\n④ 市场模型（β 复原）")
    # 构造：R_i = 1.5 * R_m + 0.2 + 噪音(0)，用 20 个观测
    rm = [(i % 5) * 0.4 - 0.8 for i in range(20)]
    ri = [1.5 * x + 0.2 for x in rm]
    beta, alpha = es.ols_beta_alpha(list(zip(rm, ri)))
    n = len(ri)
    check("beta 复原为 1.5", abs(beta - 1.5) < 1e-6, f"beta={beta:.6f}")
    check("alpha 复原为 0.2", abs(alpha - 0.2) < 1e-6, f"alpha={alpha:.6f}")
    check("估计样本数正确", n == 20, f"n={n}")


def t5_dedup_overlap():
    print("\n⑤ 去重与重叠检测")
    evs = [
        core.Event(event_id="A", first_market_date="2026-06-15", product="甲醇",
                   company="伊朗Kimiya", capacity_wt=165.0,
                   source_title="甲醇装置停车检修消息", unit_name="Kimiya 165万吨"),
        core.Event(event_id="B", first_market_date="2026-06-16", product="甲醇",
                   company="伊朗Kimiya", capacity_wt=165.0,
                   source_title="甲醇装置停车检修消息", unit_name="Kimiya 165万吨"),
        core.Event(event_id="C", first_market_date="2026-08-01", product="甲醇",
                   company="神华榆林", capacity_wt=60.0,
                   source_title="乙二醇装置检修消息", unit_name="神华榆林一期"),
    ]
    dups = core.find_duplicates(evs)
    groups = [set(g["group"]) for g in dups]
    check("识别出 A/B 为疑似重复", any({"A", "B"} <= g for g in groups), f"groups={groups}")
    check("不把 C 与 A 误判为重复", not any("C" in g and "A" in g for g in groups))
    spans = [("A", 0, 25, "2026-01-01"), ("B", 1, 26, "2026-01-02"), ("C", 60, 85, "2026-03-01")]
    res = core.overlap_pairs(spans)
    blk = res[0] if isinstance(res, list) and res and isinstance(res[0], dict) else {}
    pairs = blk.get("overlap_pairs", [])
    ids = {(p.get("a"), p.get("b")) for p in pairs}
    check("检测到 A-B 窗口重叠", ("A", "B") in ids, f"pairs={ids}")
    check("C 与 A/B 不重叠", not any("C" in x for x in ids if x) and not any("C" in i.values() for i in pairs))
    kept = blk.get("kept_in_dedup_subsample", [])
    check("去重叠子样本保留 A 与 C、排除 B", set(kept) == {"A", "C"}, f"kept={kept}")


def t6_no_fabrication():
    print("\n⑥ 缺失不伪造")
    tmp = tempfile.mkdtemp()
    rows = [{"date": "2026-01-05", "close": "100", "adj_close": "100"},
            {"date": "2026-01-06", "close": "101", "adj_close": "101"}]
    p = os.path.join(tmp, "p.csv")
    core.write_csv(p, rows)
    panel = es.PricePanel(core.read_csv(p), "date", "close")
    check("超出序列末端返回 None", panel.ret("2026-01-05", "2026-01-30") is None)
    check("Close 取不到返回 None", panel.close("2026-02-01") is None)


def main():
    print("=" * 60)
    print("装置停车事件研究 — 算法自检")
    print("=" * 60)
    t1_trading_day()
    t2_roll_adjust()
    t3_window_returns()
    t4_market_model()
    t5_dedup_overlap()
    t6_no_fabrication()
    print("\n" + "=" * 60)
    print(f"通过 {len(OKS)} 项，失败 {len(FAILS)} 项")
    if FAILS:
        for f in FAILS:
            print("  FAIL:", f)
        print("=" * 60)
        return 1
    print("全部通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
