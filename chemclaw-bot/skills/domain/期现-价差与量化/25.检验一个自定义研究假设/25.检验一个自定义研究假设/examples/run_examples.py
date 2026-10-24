# -*- coding: utf-8 -*-
"""run_examples.py — 三个示范假设的一键复现说明与参数定义。

为什么三个案例都只给"设计 + 复现方式"而不是预跑好的结果：
本 Skill 的铁律是「结论必须来自真实、可核验、经确认的数据」。纯碱厂库、尿素出口的
公开周度/月度数据这次没有拿到可逐条核验的完整序列，因此它们的状态是
「设计已就绪、数据待接入」，绝不预填一份看起来很像真的结果。

用法：
  python run_examples.py --list                 # 列出全部案例与其状态
  python run_examples.py --example soda_ash --show-design    # 打印该案例的研究设计
  python run_examples.py --example soda_ash --write build/design_soda_ash.json
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

EXAMPLES = {
    "methanol": {
        "name": "甲醇港口库存连降两周 → 基差走强",
        "status": "COMPLETED — 真实数据 228 周，结论：样本不足（主口径 10 个信号），修订口径亦无正向证据",
        "hypothesis": "甲醇港口库存连续两周下降时，随后两周基差更容易走强",
        "product": "甲醇（郑商所 MA）",
        "x": "中国甲醇样本港口库存（万吨，周度，隆众口径）",
        "y": "Δbasis_10 = 基差(T0+10交易日) − 基差(T0)，basis = 100ppi 现货 − 近月期货",
        "signal": "DOWN2：ΔI<0 且 ΔI₋₁<0（严格符号）",
        "control": "非 DOWN2 的其它周（状态转变去重）",
        "window": "10 个交易日（≈2 周）；敏感性 5 日",
        "entry": "报告日 14:00–15:00 的 60 分钟 bar；缺 bar 用当日收盘代理",
        "data": "data/port_inventory_weekly.csv（228 周，逐条回源核验）+ data/100ppi_sf.csv（1119 日）",
    },
    "soda_ash": {
        "name": "纯碱厂库连续累库两周 → 基差走弱",
        "status": "DESIGN_READY — 设计已冻结，等待可核验的纯碱厂库周度序列",
        "hypothesis": "纯碱生产企业库存连续两周上升时，随后一个月纯碱基差更容易走弱",
        "product": "纯碱（郑商所 SA）",
        "x": "纯碱生产企业库存（万吨，周度，隆众/卓创口径）",
        "y": "Δbasis_20 = 基差(T0+20交易日) − 基差(T0)（重碱华东现货 − SA 主力）",
        "signal": "UP2：ΔI>0 且 ΔI₋₁>0",
        "control": "非 UP2 周；需按库存分位带等价过滤",
        "window": "20 个交易日（≈1 个月）；敏感性 10 日",
        "entry": "报告日收盘（若无法确认发布时点，一律用次日开盘/收盘）",
        "data": "待接入：纯碱厂库周度（预期 2019 年起）+ SA 主力日线 + 重碱华东现货",
        "caution": "纯碱厂库与交易所仓单/交割逻辑强相关，且 2023 年后有巨量新增产能，"
                   "样本内存在结构断点，必须分段检验。",
    },
    "urea_export": {
        "name": "尿素出口量环比大增 → 国内基差走强",
        "status": "DESIGN_READY — 设计已冻结，等待海关月度出口数据",
        "hypothesis": "尿素月度出口量环比大增后，随后一个月国内尿素基差更容易走强",
        "product": "尿素（郑商所 UR）",
        "x": "尿素月度出口量（万吨，海关总署）",
        "y": "Δbasis_20 = 基差(T0+20) − 基差(T0)（小颗粒主产区现货 − UR 主力）",
        "signal": "出口量环比增幅 ≥ 30%（需预先固定阈值）",
        "control": "环比增幅 < 30% 的月份",
        "window": "20 个交易日",
        "entry": "海关数据发布日（通常次月 20 日前后）的收盘",
        "data": "待接入：海关月度出口 + UR 日线 + 主产区现货",
        "caution": "月度数据只有 12×N 个观测，N 年也只有几十个；出口政策（法检、配额）是外生冲击，"
                   "适合做事件研究而非均值差检验。",
    },
}


def design_for(key):
    e = EXAMPLES[key]
    return {
        "schema_version": "1.1",
        "example": key,
        "raw_text": e["hypothesis"],
        "approved": False,
        "approval_state": "PENDING_USER_CONFIRMATION",
        "product": {"name": e["product"]},
        "variables": {"X": {"name": e["x"]}, "Y_main": {"name": e["y"]}},
        "signal": {"rule": e["signal"]},
        "control": {"rule": e["control"]},
        "horizon": {"main_sessions": int(e["window"].split()[0])},
        "entry_rule": {"main_desc": e["entry"]},
        "data": {"note": e["data"]},
        "caution": e.get("caution", ""),
        "status": e["status"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--example", default=None, choices=list(EXAMPLES))
    ap.add_argument("--show-design", action="store_true")
    ap.add_argument("--write", default=None)
    a = ap.parse_args()
    if a.list or not a.example:
        for k, e in EXAMPLES.items():
            print(f"[{k}] {e['name']}\n    状态：{e['status']}\n    X：{e['x']}\n    Y：{e['y']}\n")
        return
    d = design_for(a.example)
    if a.show_design:
        print(json.dumps(d, ensure_ascii=False, indent=1))
    if a.write:
        os.makedirs(os.path.dirname(a.write) or ".", exist_ok=True)
        json.dump(d, open(a.write, "w", encoding="utf-8-sig"), ensure_ascii=False, indent=1)
        print("->", a.write)


if __name__ == "__main__":
    main()
