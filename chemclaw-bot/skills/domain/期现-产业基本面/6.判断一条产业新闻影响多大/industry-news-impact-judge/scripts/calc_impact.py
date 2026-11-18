#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calc_impact.py — 产业新闻影响量计算器

用途：把「装置产能 Q / 天数 d / 开工率 r / 波及系数 k」四要素代入统一公式，
     输出理论产量影响、产能占比、覆盖全国产量天数，并给出 d×r 敏感矩阵。

设计原则（与 SKILL.md 一致）：
  * 缺 Q -> 拒绝计算
  * 缺 d -> 拒绝计算（不得自拟天数）
  * r / k 必须是显式假设，结果中强制回显假设

用法：
  python calc_impact.py --capacity 1200000 --days 30 --rate 0.8895 --k 0.125
  python calc_impact.py --capacity 1200000 --matrix-days 7,10,15,20,30 --matrix-rates 0.68,0.7295,0.8895
  python calc_impact.py --capacity 1200000 --national-capacity 106300000 --regional-capacity 37205000 --days 30

作者：期现-产业基本面 / 6.判断一条产业新闻影响多大
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional


# ---------------------------------------------------------------- 基础公式
def daily_capacity(capacity_tpa: float) -> float:
    """F1 日均产能 D = Q / 365"""
    return capacity_tpa / 365.0


def impact_loss(capacity_tpa: float, days: float, rate: float, k: float = 1.0) -> float:
    """F2 理论产量影响 L = Q × (d/365) × r × k"""
    return capacity_tpa * (days / 365.0) * rate * k


def ratio(part: float, whole: float) -> float:
    """F3 占比"""
    if not whole:
        raise ValueError("分母为 0")
    return part / whole


def coverage_days(loss_t: float, national_output_tpa: float) -> float:
    """F4 相当于全国多少天的产量"""
    daily = national_output_tpa / 365.0
    return loss_t / daily if daily else float("nan")


# ---------------------------------------------------------------- 解析
def _parse_list(text: Optional[str]) -> Optional[list[float]]:
    if not text:
        return None
    return [float(x) for x in text.replace("，", ",").split(",") if x.strip()]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="产业新闻影响量计算器（产能占比 / 理论产量影响 / 敏感性矩阵）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--capacity", type=float, required=True, help="装置设计产能 Q，吨/年（必填，必须有出处）")
    p.add_argument("--days", type=float, help="受影响天数 d（必填用于单点测算；缺省则不做单点测算）")
    p.add_argument("--rate", type=float, default=None, help="假设开工率 r（0~1），缺省用 --actual-output 推算")
    p.add_argument("--k", type=float, default=1.0, help="波及系数 k（0~1），默认 1.0 表示全厂")
    p.add_argument("--actual-output", type=float, default=None,
                   help="近三年平均实际产量（吨/年），提供则用产量率替代 design×rate")
    p.add_argument("--national-capacity", type=float, help="全国有效产能，吨/年（用于占比）")
    p.add_argument("--regional-capacity", type=float, help="区域有效产能，吨/年（用于占比）")
    p.add_argument("--national-output", type=float, help="全国年产量，吨/年（用于覆盖天数）")
    p.add_argument("--matrix-days", type=str, help="敏感矩阵天数列表，如 7,10,15,20,30")
    p.add_argument("--matrix-rates", type=str, help="敏感矩阵开工率列表，如 0.68,0.7295,0.8895")
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    return p


# ---------------------------------------------------------------- 主流程
def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    warnings: list[str] = []

    # --- 参数校验
    if args.capacity <= 0:
        print("[拒绝计算] 装置产能必须 > 0", file=sys.stderr)
        return 2

    rate = args.rate
    if rate is None:
        if args.actual_output:
            rate = args.actual_output / args.capacity
            warnings.append(
                f"未提供 --rate，改用产量率 r = {args.actual_output:,.0f} / {args.capacity:,.0f} = {rate:.4f}"
            )
        else:
            warnings.append("未提供 --rate 与 --actual-output，假设 r = 0.85（仅示意，禁止用于正式结论）")
            rate = 0.85
    if not 0 < rate <= 1.2:
        print(f"[拒绝计算] 开工率 r={rate} 不合理（应 0<r<=1.2）", file=sys.stderr)
        return 2
    if not 0 < args.k <= 1.0:
        print(f"[拒绝计算] 波及系数 k={args.k} 不合理（应 0<k<=1）", file=sys.stderr)
        return 2

    D = daily_capacity(args.capacity)
    base_output = args.actual_output if args.actual_output else args.capacity * rate
    D_actual = base_output / 365.0

    result: dict = {
        "inputs": {
            "Q_capacity_tpa": args.capacity,
            "d_days": args.days,
            "r_rate": round(rate, 6),
            "k": args.k,
            "actual_output_3y_avg_tpa": args.actual_output,
        },
        "assumptions_note": "r 与 k 均为假设参数，须在报告中显式披露；d 必须有出处",
        "daily_capacity_tpd_design": round(D, 2),
        "daily_capacity_tpd_actual_basis": round(D_actual, 2),
        "warnings": warnings,
    }

    # --- 单点测算
    if args.days is None:
        warnings.append("未提供 --days，跳过单点影响量测算（按规则不得自拟天数）")
        result["loss_t"] = None
    else:
        if args.days <= 0:
            print("[拒绝计算] 天数必须 > 0", file=sys.stderr)
            return 2
        loss = impact_loss(args.capacity, args.days, rate, args.k)
        result["loss_t"] = round(loss, 0)
        result["loss_formula"] = (
            f"L = Q x (d/365) x r x k = {args.capacity:,.0f} x ({args.days}/365) "
            f"x {rate:.4f} x {args.k} = {loss:,.0f} 吨"
        )
        if args.national_output:
            cd = coverage_days(loss, args.national_output)
            result["coverage_days_national"] = round(cd, 4)

    # --- 占比
    if args.national_capacity:
        result["ratio_national_pct"] = round(ratio(args.capacity, args.national_capacity) * 100, 4)
    if args.regional_capacity:
        result["ratio_regional_pct"] = round(ratio(args.capacity, args.regional_capacity) * 100, 4)
    if args.national_output:
        result["ratio_national_monthly_output_pct"] = round(
            ratio(args.capacity, args.national_output / 12) * 100, 4
        )

    # --- 敏感矩阵
    mdays = _parse_list(args.matrix_days)
    mrates = _parse_list(args.matrix_rates)
    if mdays and mrates:
        matrix = {}
        for r in mrates:
            matrix[f"{r}"] = {f"{d}": round(impact_loss(args.capacity, d, r, args.k), 0) for d in mdays}
        result["sensitivity_matrix"] = {
            "unit": "吨",
            "k": args.k,
            "rows_by_rate": matrix,
            "cols_days": mdays,
        }

    # --- 输出
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=" * 68)
        print("产业新闻影响量测算（仅规模，不含价格判断）")
        print("=" * 68)
        print(f"装置设计产能 Q        : {args.capacity:,.0f} 吨/年")
        print(f"日均产能 D = Q/365     : {D:,.2f} 吨/日")
        print(f"假设开工率 r           : {rate:.4f}")
        print(f"波及系数 k             : {args.k}")
        if args.days is not None:
            print(f"受影响天数 d           : {args.days} 天")
            print(f"理论产量影响 L         : {result['loss_t']:,.0f} 吨")
            print(f"公式                   : {result['loss_formula']}")
        if "coverage_days_national" in result:
            print(f"相当于全国产量         : {result['coverage_days_national']:.3f} 天")
        if "ratio_national_pct" in result:
            print(f"占全国产能             : {result['ratio_national_pct']:.4f} %")
        if "ratio_regional_pct" in result:
            print(f"占区域产能             : {result['ratio_regional_pct']:.4f} %")
        if "sensitivity_matrix" in result:
            sm = result["sensitivity_matrix"]
            print("\n敏感矩阵（单位：吨）")
            head = "  r \\ d " + "".join(f"{d:>12}" for d in sm["cols_days"])
            print(head)
            for r, row in sm["rows_by_rate"].items():
                line = f"{r:>8} " + "".join(f"{v:>12,.0f}" for v in (row[str(d)] for d in sm["cols_days"]))
                print(line)
        for w in warnings:
            print(f"\n[提示] {w}")
        print("\n[声明] 本工具只计算规模，不推断价格方向；所有 r / k / d 必须由使用者提供依据。")
        print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
