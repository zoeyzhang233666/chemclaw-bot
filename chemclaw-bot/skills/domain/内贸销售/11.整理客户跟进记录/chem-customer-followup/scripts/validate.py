# -*- coding: utf-8 -*-
"""
validate.py — 交付前自检（不生成文件，只报告）

用法：
    python validate.py followup.json [--as-of 2026-10-19]

检查项：
  1. 结构完整性（时间线、分类合法性、阶段合法性）
  2. 出处完整性（四类事实是否都带 source）
  3. 停滞天数是否与时间线自洽（as_of − 最后客户回复）
  4. 承诺逾期是否与截止日自洽
  5. 纪律检查：AI 摘要是否独立存在、客户需求是否带置信度
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (
    validate, parse_as_of, compute_stall_days, promise_state,
    days_left, STAGE_NAMES,
)


def main():
    ap = argparse.ArgumentParser(description="客户跟进卡数据自检")
    ap.add_argument("input")
    ap.add_argument("--as-of", default=None, help="覆盖 meta.as_of_date")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8-sig") as f:
        data = json.load(f)

    as_of = parse_as_of(args.as_of or (data.get("meta") or {}).get("as_of_date"))
    print(f"as_of = {as_of.isoformat()}")

    errors, warnings = validate(data, as_of)

    days, last = compute_stall_days(data.get("timeline") or [], as_of)
    print("\n── 推导值 ──")
    if last:
        print(f"最后客户回复：{last.get('date')} {last.get('time','')}（{last.get('source','')}）")
    print(f"停滞天数（核算）：{days if days is not None else '—'}")
    stage = data.get("stage") or {}
    print(f"阶段：{stage.get('current','—')}　（合法值：{'/'.join(STAGE_NAMES)}）")

    exp = (data.get("meta") or {}).get("quote_expiry")
    if exp:
        d = days_left(exp, as_of)
        print(f"报价有效期：{exp}　剩余 {d} 天" if d is not None else f"报价有效期：{exp}")

    print("\n── 承诺状态（按截止日核算）──")
    for i, p in enumerate(data.get("promises") or [], 1):
        st, tone = promise_state(p, as_of)
        mark = "  << 逾期" if tone == "risk" else ""
        print(f"  #{i} due={str(p.get('due','—')):<12} → {st}{mark}")

    cnt = {}
    for r in data.get("timeline") or []:
        cnt[r.get("category", "?")] = cnt.get(r.get("category", "?"), 0) + 1
    print("\n── 分类计数 ──")
    print("  " + "　".join(f"{k}={v}" for k, v in cnt.items()))
    print(f"  合计 {sum(cnt.values())} 条")

    print("\n── 检查结果 ──")
    if not errors and not warnings:
        print("  [pass] 未发现问题")
    for e in errors:
        print(f"  [error] {e}")
    for w in warnings:
        print(f"  [warn ] {w}")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
