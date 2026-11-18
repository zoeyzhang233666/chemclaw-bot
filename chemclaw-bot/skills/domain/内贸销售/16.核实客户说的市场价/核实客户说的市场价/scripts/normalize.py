#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""normalize.py — 价格口径换算与核验（命令行）。

只做**确定性换算**，每一步都打印出来；缺参数就报「无法直接折算」，绝不替你猜运费或税率。

用法示例：
  # 1) 含税/不含税互转（默认增值税 13%，可改）
  python scripts/normalize.py tax --price 1400 --from 不含税 --to 含税 --vat 0.13

  # 2) 出厂/送到互转（必须给运费，否则报无法折算）
  python scripts/normalize.py delivery --price 1400 --from 出厂 --to 送到 --freight 80

  # 3) 一条命令把客户价换到市场口径
  python scripts/normalize.py convert --price 1400 --tax 未注明 --delivery 未注明 \\
      --market-tax 含税 --market-delivery 送到 [--freight N] [--vat 0.13]

  # 4) 判定落在哪个区间（也支持用近3月价格带）
  python scripts/normalize.py classify --price 1400 --low 1050 --high 1200 [--band-min 1100 --band-max 1200]

所有命令输出 JSON（UTF-8），方便脚本再处理。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- tax
def cmd_tax(a):
    src, dst = C.norm_tax(a.src), C.norm_tax(a.dst)
    steps = []
    if src == "未注明" or dst == "未注明":
        return emit({
            "ok": False,
            "reason": "税费口径未注明，无法确定换算方向",
            "hint": "先问清客户价格是否含税；不确定时保留原值并标注口径风险",
            "price": a.price,
        })
    if src == dst:
        return emit({"ok": True, "value": a.price, "steps": [f"两侧均为{src}，无需换算"], "note": "数值不变"})
    vat = a.vat
    if src == "不含税" and dst == "含税":
        v = a.price * (1 + vat)
        steps.append(f"含税价 = 不含税价 × (1 + 税率) = {C.fmt_num(a.price)} × (1 + {vat}) = {C.fmt_num(v)}")
    elif src == "含税" and dst == "不含税":
        v = a.price / (1 + vat)
        steps.append(f"不含税价 = 含税价 ÷ (1 + 税率) = {C.fmt_num(a.price)} ÷ (1 + {vat}) = {C.fmt_num(v)}")
    else:
        return emit({"ok": False, "reason": f"不支持的换算：{src} → {dst}"})
    return emit({"ok": True, "value": round(v, 2), "steps": steps,
                 "note": f"按增值税 {vat*100:g}% 换算；如品种适用税率不同请用 --vat 指定"})


# ---------------------------------------------------------------- delivery
def cmd_delivery(a):
    src, dst = C.norm_delivery(a.src), C.norm_delivery(a.dst)
    if src == "未注明" or dst == "未注明":
        return emit({"ok": False, "reason": "交付口径未注明，无法确定是否含运费", "price": a.price})
    if src == dst:
        return emit({"ok": True, "value": a.price, "steps": [f"两侧均为{src}，无需换算"]})
    if a.freight is None:
        return emit({
            "ok": False,
            "reason": "无法直接折算：缺少运费",
            "detail": f"要把「{src}」换算成「{dst}」必须知道这段运距的运费，本工具不替你估计",
            "howto": "向物流/客户确认运费后，用 --freight 传入（元/吨）",
            "price": a.price,
        })
    if src == "出厂" and dst == "送到":
        v = a.price + a.freight
        step = f"送到价 = 出厂价 + 运费 = {C.fmt_num(a.price)} + {C.fmt_num(a.freight)} = {C.fmt_num(v)}"
    elif src == "送到" and dst == "出厂":
        v = a.price - a.freight
        step = f"出厂价 = 送到价 − 运费 = {C.fmt_num(a.price)} − {C.fmt_num(a.freight)} = {C.fmt_num(v)}"
    else:
        return emit({"ok": False, "reason": f"「{src}」与「{dst}」之间不能只靠运费换算，需要另取对应口径报价"})
    return emit({"ok": True, "value": round(v, 2), "steps": [step],
                 "note": "运费为已知值，未含资金占用/装卸等其它费用"})


# ---------------------------------------------------------------- convert
def cmd_convert(a):
    steps, warn = [], []
    v = a.price
    ct, mt = C.norm_tax(a.tax), C.norm_tax(a.market_tax)
    cd, md = C.norm_delivery(a.delivery), C.norm_delivery(a.market_delivery)

    # 1 税基
    if ct == "未注明":
        warn.append("客户未说明含税/不含税，按市场税基直接比较（不加税、不减税）")
    elif ct != mt:
        if ct == "不含税" and mt == "含税":
            v = v * (1 + a.vat); steps.append(f"税基：不含税→含税，× (1+{a.vat}) → {C.fmt_num(v)}")
        elif ct == "含税" and mt == "不含税":
            v = v / (1 + a.vat); steps.append(f"税基：含税→不含税，÷ (1+{a.vat}) → {C.fmt_num(v)}")
    else:
        steps.append(f"税基：两侧均为{ct}，不换算")

    # 2 交付
    if cd == "未注明":
        warn.append("客户未说明出厂/送到，按市场交付口径直接比较")
    elif cd != md:
        if a.freight is None:
            return emit({"ok": False, "reason": "无法直接折算：缺少运费",
                         "detail": f"客户为「{cd}」，市场为「{md}」，必须知道运费才能比较",
                         "steps": steps, "warnings": warn,
                         "partial_value": round(v, 2)})
        if cd == "出厂" and md == "送到":
            v = v + a.freight; steps.append(f"交付：出厂→送到，+ 运费 {C.fmt_num(a.freight)} → {C.fmt_num(v)}")
        elif cd == "送到" and md == "出厂":
            v = v - a.freight; steps.append(f"交付：送到→出厂，− 运费 {C.fmt_num(a.freight)} → {C.fmt_num(v)}")
        else:
            return emit({"ok": False, "reason": f"「{cd}」与「{md}」不能只用运费换算",
                         "steps": steps, "warnings": warn})
    else:
        steps.append(f"交付：两侧均为{cd}，不换算")

    if C.norm_payment(a.payment) == "承兑" and C.norm_payment(a.market_payment) == "现金":
        warn.append("客户为承兑、市场为现金：承兑有贴现成本，未计入，需另问贴现率后再比")

    return emit({"ok": True, "value": round(v, 2), "steps": steps, "warnings": warn,
                 "basis": {"tax": mt, "delivery": md}})


# ---------------------------------------------------------------- classify
def cmd_classify(a):
    res = C.compare_to_range(a.price, a.low, a.high,
                             band_min=a.band_min, band_max=a.band_max)
    out = {"ok": True, **res}
    out["rule"] = ("①在区间内→接近市场参考区间；②区间外、距最近端点 ≤ 半宽→略高/略低；"
                   "③区间外、距最近端点 > 半宽→明显偏高/偏低；④无区间→无法判定。"
                   "「半宽」=(上沿−下沿)/2，取自报价自身宽度，不用固定百分比阈值。")
    if a.band_min is not None and a.band_max is not None:
        out["band_note"] = ("与近3月价格带交叉核对：客户价既超出当日区间、又超出近3月价格带时，"
                            "「明显」的判断更稳；若落在历史带内，应写明可能是不同日期的价格。")
    emit(out)


def main():
    ap = argparse.ArgumentParser(description="价格口径换算与判定")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("tax", help="含税/不含税互转")
    p.add_argument("--price", type=float, required=True)
    p.add_argument("--from", dest="src", required=True)
    p.add_argument("--to", dest="dst", required=True)
    p.add_argument("--vat", type=float, default=C.DEFAULT_VAT)
    p.set_defaults(func=cmd_tax)

    p = sub.add_parser("delivery", help="出厂/送到互转（需运费）")
    p.add_argument("--price", type=float, required=True)
    p.add_argument("--from", dest="src", required=True)
    p.add_argument("--to", dest="dst", required=True)
    p.add_argument("--freight", type=float, default=None)
    p.set_defaults(func=cmd_delivery)

    p = sub.add_parser("convert", help="把客户价换到市场口径")
    p.add_argument("--price", type=float, required=True)
    p.add_argument("--tax", default="未注明")
    p.add_argument("--delivery", default="未注明")
    p.add_argument("--payment", default="未注明")
    p.add_argument("--market-tax", default="含税")
    p.add_argument("--market-delivery", default="送到")
    p.add_argument("--market-payment", default="现金")
    p.add_argument("--freight", type=float, default=None)
    p.add_argument("--vat", type=float, default=C.DEFAULT_VAT)
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("classify", help="判定相对市场区间的位置")
    p.add_argument("--price", type=float, required=True)
    p.add_argument("--low", type=float, required=True)
    p.add_argument("--high", type=float, required=True)
    p.add_argument("--band-min", type=float, default=None)
    p.add_argument("--band-max", type=float, default=None)
    p.set_defaults(func=cmd_classify)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
