# -*- coding: utf-8 -*-
"""
sample.py — 案例数据自检
=========================
读出本目录的两个期货 CSV，检查：行数、日期范围、缺失、异常值、两者交集，
并把"可复现的基线数字"打印出来，供回归对照。

运行： python sample.py
"""
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")


def describe(path, price_col):
    df = pd.read_csv(path, parse_dates=["date"])
    s = df[price_col].dropna()
    print(f"\n{os.path.basename(path)}")
    print(f"  行数        : {len(df)}")
    print(f"  日期范围    : {df.date.min():%Y-%m-%d} → {df.date.max():%Y-%m-%d}")
    print(f"  价格缺失    : {df[price_col].isna().sum()}")
    print(f"  价格区间    : {s.min():.0f} ~ {s.max():.0f}")
    print(f"  零/负值     : {(s <= 0).sum()}")
    dup = df.date.duplicated().sum()
    print(f"  重复日期    : {dup}")
    return df


if __name__ == "__main__":
    a = describe(os.path.join(D, "pp.csv"), "c")
    b = describe(os.path.join(D, "lldpe.csv"), "c")
    m = (a[["date", "c"]].rename(columns={"c": "PP"})
         .merge(b[["date", "c"]].rename(columns={"c": "L"}), on="date", how="inner"))
    m = m[m.date >= pd.Timestamp("2023-10-20")]
    print("\n【近3年交集】")
    print(f"  共同交易日  : {len(m)}")
    print(f"  起点 / 终点 : {m.date.min():%Y-%m-%d} / {m.date.max():%Y-%m-%d}")
    print(f"  PP 首末     : {m.PP.iloc[0]:.0f} → {m.PP.iloc[-1]:.0f} "
          f"({(m.PP.iloc[-1]/m.PP.iloc[0]-1)*100:+.1f}%)")
    print(f"  L  首末     : {m.L.iloc[0]:.0f} → {m.L.iloc[-1]:.0f} "
          f"({(m.L.iloc[-1]/m.L.iloc[0]-1)*100:+.1f}%)")
    lvl = m.PP.corr(m.L)
    ret = m.PP.pct_change().corr(m.L.pct_change())
    print(f"  水平相关    : {lvl:.4f}")
    print(f"  收益率相关  : {ret:.4f}")
    print("\n  ⚠ 若水平相关明显低于收益率相关，说明图上的'平行'主要来自共同趋势，"
          "不能当作紧密联动的证据。")

    # 现货覆盖检查
    for f, col in (("spot_pp.csv", "PP拉丝_元吨"), ("spot_lldpe.csv", "LLDPE")):
        p = os.path.join(D, f)
        if os.path.exists(p):
            d = pd.read_csv(p, parse_dates=["date"])
            print(f"\n{os.path.basename(p)}: {len(d)} 行, "
                  f"{d.date.min():%Y-%m-%d} → {d.date.max():%Y-%m-%d}")
