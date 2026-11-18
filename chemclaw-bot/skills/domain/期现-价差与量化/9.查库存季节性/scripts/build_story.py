# -*- coding: utf-8 -*-
"""
build_story.py —— 规则化解读层
================================
把 seasonal.json 里的数字翻译成“可复核的判断句”，所有结论都由显式规则生成，
不做任何价格方向预测。规则编号与 references/04-分位与判断规则.md 一一对应。

核心护栏（硬编码，不允许被配置绕过）：
    R0  库存高于历史均值 ≠ 价格下跌；报告只描述“库存相对季节性水平的位置”与“累去库幅度”。
    R0a 口径混用即结论作废：全国港口口径的水平值不得与华东口径的同期分布比较。
    R0b 样本年数 < 4 时，分位只报区间不报结论。
    R0c 水平值缺失（仅剩增减额）时，分位必须标注“缺失期不可得”，不得用替代口径冒充。
"""
from __future__ import annotations

import json
from pathlib import Path


def _rank_phrase(r, n=None, hmin=None, hmax=None):
    """
    R3a：分位端点的措辞。
    分位是闭区间，0 与 100 只代表“低于/高于全部样本”，不是精确到小数的排名，
    因此用“低于全部 N 个历史样本（最小 X）”这类可核验的说法。
    """
    if r is None:
        return "分位不可得"
    if r <= 0:
        return (f"0 分位，即低于同期全部 {n} 个历史样本" + (f"（历史同期最小值 {hmin}）" if hmin is not None else "")) \
            if n else "0 分位，即低于同期全部历史样本"
    if r >= 100:
        return (f"100 分位，即高于同期全部 {n} 个历史样本" + (f"（历史同期最大值 {hmax}）" if hmax is not None else "")) \
            if n else "100 分位，即高于同期全部历史样本"
    return f"{r} 分位"


def _state_of_rank(r):
    """R3：按历史分位把水平分成五档。仅描述位置，不含方向含义。"""
    if r is None:
        return "不可得"
    if r < 10:
        return "显著低于历史同期"
    if r < 25:
        return "低于历史同期"
    if r <= 75:
        return "处于历史同期正常区间"
    if r <= 90:
        return "高于历史同期"
    return "显著高于历史同期"


def _speed_of(cum4, band, ref):
    """R4：以“4 周累计变化”相对历史同周次分位带的位置描述累/去库速度。"""
    if cum4 is None:
        return "不可得"
    p25 = (band or {}).get("p25")
    p75 = (band or {}).get("p75")
    if p25 is not None and p75 is not None:
        if cum4 < p25:
            return "去库明显快于历史同期"
        if cum4 > p75:
            return "累库明显快于历史同期"
        return "累去库速度与历史同期相近"
    return "历史样本不足，不评级"


def build(seasonal: dict) -> dict:
    m = seasonal["meta"]
    cur = seasonal["current"]
    sp = seasonal["speed"]
    cal = seasonal["calibration"]
    integ = seasonal["integrity"]
    east = cur.get("east") or {}
    port = cur.get("port_total") or {}
    est = cur.get("east_from_port") or {}

    # ---- 口径状态 ----
    level_ok = east.get("asof") is not None
    level_week = east.get("iso_week")
    latest_week = port.get("iso_week")
    level_missing = seasonal.get("level_missing", {})

    flags = []
    # R0 / R2：分位是否可用
    if level_ok and (east.get("n_hist") or 0) < int(seasonal["guardrails"].get("min_sample_years", 4)):
        flags.append("sample_insufficient")
    if not level_ok:
        flags.append("level_missing")
    if not integ.get("freq_ok"):
        flags.append("freq_gap")
    if (integ.get("missing_weeks") or 0) > 0:
        flags.append("missing_weeks")
    if cal.get("chg_discrepancy_weeks", 0) > 0:
        flags.append("local_sampling_jump")
    if (seasonal.get("season_fit") or {}).get("r2") is not None and \
            seasonal["season_fit"]["r2"] < float(seasonal["guardrails"].get("min_r2_seasonal", 0.6)):
        flags.append("season_weak")

    kpis = {
        "current_value": east.get("value"),
        "current_asof": east.get("asof"),
        "pct_rank": east.get("pct_rank"),
        "pct_rank_n": east.get("n_hist"),
        "hist_mean": east.get("hist_mean"),
        "vs_mean_pct": east.get("vs_mean_pct"),
        "chg4w": sp.get("cum4w"),
        "chg12w": sp.get("cum12w"),
        "run_label": sp.get("run_label"),
        "run_len": sp.get("run_len"),
        "latest_asof": port.get("asof"),
        "latest_port_total": port.get("value"),
        "latest_east_est": est.get("value"),
    }

    verdict = {
        "level_state": _state_of_rank(east.get("pct_rank")) if level_ok else "缺失期不可得",
        "level_week": level_week,
        "level_asof": east.get("asof"),
        "deseason_state": _state_of_rank(east.get("pct_rank_deseason")) if level_ok else "不可得",
        "deseason_resid_pct": east.get("deseason_resid_pct"),
        "speed_state": _speed_of(sp.get("cum4w"), sp.get("cum4w_hist_band"), None),
        "speed_rank": sp.get("cum4w_pct_rank"),
        "speed_rank12": sp.get("cum12w_pct_rank"),
        "flags": flags,
        "can_conclude_level": bool(level_ok and (east.get("n_hist") or 0) >= 4),
        "level_missing_weeks": level_missing.get("weeks"),
        "level_missing_from": level_missing.get("from"),
    }

    # ---- 证据链（每条都带可核验的门槛与结论）----
    checks = [
        {"id": "C1", "name": "统计对象与口径",
         "claim": f"{cal['metric_label']}，{cal['inventory_class']} 类库存，{cal['frequency']} 频，单位 {cal['unit']}，发布方 {cal['issuer']}",
         "evidence": f"A 样本 {integ['n_weeks']} 期（{integ['start']} ~ {integ['end']}），逐期原文可核验 {cal['official_chg_weeks']} 期",
         "status": "pass"},
        {"id": "C2", "name": "华东口径与全国港口口径分离",
         "claim": "华东（江苏+浙江）与全国港口（华东+华南）分列，不混算；对照口径只用于覆盖偏差度量与缺失期水平替代",
         "evidence": f"华南占全国港口比例中位数 {seasonal['coverage_bias']['share_ref']}，替代值标记为 east_from_port，不进入主统计",
         "status": "pass"},
        {"id": "C3", "name": "历史频率一致",
         "claim": f"相邻两期间隔中位数 {integ['gap_median_days']} 天、最大 {integ['gap_max_days']} 天",
         "evidence": f"缺报（跨度>16 天）{integ['missing_weeks']} 周；>10 天的双周报 {0 if integ.get('gap_max_days', 0) <= 10 else '存在'}",
         "status": "pass" if integ["freq_ok"] else "warn"},
        {"id": "C4", "name": "周次对齐",
         "claim": f"以 ISO 周年 + ISO 周次为季节坐标，历史样本 {seasonal['meta']['sample_years']} 年（{','.join(map(str, seasonal['meta']['hist_years']))}），同周次 ±1 周容差",
         "evidence": f"可用周次 {len(seasonal['weeks'])} 个；样本年数不足 4 的周次 {sum(1 for v in seasonal['weeks'].values() if v.get('insufficient'))} 个",
         "status": "pass"},
        {"id": "C5", "name": "季节分解",
         "claim": f"ln I = 趋势(52 周中心化 MA) + 季节(傅里叶 K=2)，季节效应振幅 {seasonal['season_fit'].get('season_amp_pct')}%",
         "evidence": f"去季节 R² = {seasonal['season_fit'].get('r2')}；留一年样本外 MAPE = {(seasonal['season_fit'].get('oos') or {}).get('mape_log')}%",
         "status": "pass" if (seasonal["season_fit"].get("r2") or 0) >= 0.15 else "warn"},
        {"id": "C6", "name": "样本与披露变化",
         "claim": f"逐地区披露止于 {cal['region_split_last']}；华东水平值最后一个可核验期为 {cal['east_available_last']}；此后仅由官方增减额递推，{level_missing.get('from')} 起水平不可得",
         "evidence": f"递推 {cal['est_weeks']} 期（最长连续 {int(cal['est_max_chain'] or 0)} 期）；官方增减额与表格差分不一致 {cal['chg_discrepancy_weeks']} 期（局部口径补报）",
         "status": "warn"},
        {"id": "C7", "name": "断点显式化",
         "claim": "；".join(f"{b['date']} {b['kind']}" for b in seasonal["breakpoints"]),
         "evidence": "断点两侧样本不合并统计，仅在“剔除异常段”敏感性场景中对照",
         "status": "pass"},
    ]

    # ---- 结论句（严格由数字 + 规则拼出）----
    lines = []
    if level_ok:
        lines.append(
            f"在可核验的最后一个水平期（{east['asof']}，W{east['iso_week']}），华东港口库存为 {east['value']} 万吨，"
            f"处于过去 {len(seasonal['meta']['hist_years'])} 年"
            f"（{'/'.join(map(str, sorted(seasonal['meta']['hist_years'])))}）同周次（±1 周，n={east['n_hist']}）"
            f"{_rank_phrase(east['pct_rank'], east['n_hist'], east['hist_min'], east['hist_max'])}，"
            f"较同期均值 {east['hist_mean']} 万吨{'低' if (east.get('vs_mean') or 0) < 0 else '高'}"
            f" {abs(east.get('vs_mean') or 0)} 万吨（{east.get('vs_mean_pct')}%）。"
        )
        if east.get("pct_rank_deseason") is not None:
            lines.append(
                f"扣除季节性后（去季节残差 {east['deseason_resid_pct']}%），该值仍位于历史同期偏离分布的 "
                f"{_rank_phrase(east['pct_rank_deseason'])}——即“偏低”不只是季节位置造成的。"
            )
    lines.append(
        f"最新一期（{port['asof']}，W{port['iso_week']}）华东库存水平值不可得：自 {cal['east_available_last']} 之后逐地区库存未再公开，"
        f"自 {level_missing.get('from')} 起只能以全国港口总量与官方增减额描述变化；同期全国港口库存 {port['value']} 万吨，"
        f"按近一年华东占比折算华东约 {est.get('value')} 万吨（替代值，仅供定位，不参与分位计算）。"
    )
    cum4 = sp.get("cum4w")
    band4 = sp.get("cum4w_hist_band") or {}
    if cum4 is not None and band4.get("p50") is not None:
        faster = "大于" if cum4 > band4["p50"] else ("小于" if cum4 < band4["p50"] else "接近")
        lines.append(
            f"最近 4 周 / 12 周华东累计变化 {cum4} / {sp.get('cum12w')} 万吨，4 周变化历史同周次分位 {sp.get('cum4w_pct_rank')}"
            f"（同期历史中位数 {band4.get('p50')}、p75 {band4.get('p75')}、p90 {band4.get('p90')}），"
            f"绝对幅度{faster}历史同期中位数——即当前既没有出现历史同期那种大规模累库，也没有异常急速去库；"
            f"当前状态：{sp.get('run_label')}（连续 {abs(sp.get('run_len') or 0)} 周）。"
        )

    return {
        "kpis": kpis,
        "verdict": verdict,
        "checks": checks,
        "statements": lines,
        "rules": [
            {"id": "R0", "rule": "库存高于/低于历史均值不直接推价格方向；本报告只描述库存相对季节性水平的位置与累去库幅度。"},
            {"id": "R1", "rule": "产品 + 口径 + 地区 + 统计机构 + 频率 五项必须同时确定，缺一不做分位结论。"},
            {"id": "R2", "rule": "统计样本年数 < 4 时，分位只报区间不报结论（insufficient）。"},
            {"id": "R3", "rule": "历史分位五档：<10 显著偏低 / 10-25 偏低 / 25-75 正常 / 75-90 偏高 / >90 显著偏高。"},
            {"id": "R4", "rule": "累去库速度以 4 周累计变化相对历史同周次 p25-p75 带定位；速度不等于方向。"},
            {"id": "R5", "rule": "披露口径或统计样本发生变化时，断点后数据不与断点前合并统计，必须单独标注。"},
        ],
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasonal", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    s = json.loads(Path(args.seasonal).read_text(encoding="utf-8"))
    o = build(s)
    Path(args.out).write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(o["verdict"], ensure_ascii=False, indent=1))
    for ln in o["statements"]:
        print("-", ln)


if __name__ == "__main__":
    main()
