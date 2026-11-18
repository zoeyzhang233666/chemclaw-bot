# -*- coding: utf-8 -*-
"""build/data.json + templates -> 单文件离线交互式 HTML 报告。

用法：python build_html.py build/data.json --out "out/xxx.html"
产物：内联 ECharts、零外链、双击可开。
"""
import argparse
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "templates")
ASSETS = os.path.join(HERE, "assets")

WIN_LABEL = {"30": "30 天", "90": "3 个月", "365": "1 年", "1095": "3 年", "1826": "5 年"}
SER_KEY = {"S1_mid": "S1", "S2_mid": "S2", "S3_value": "S3"}


def e(s):
    return html.escape(str(s), quote=True)


def f2(v, d=2):
    if v is None or v == "":
        return "—"
    try:
        return ("%%.%df" % d) % float(v)
    except (TypeError, ValueError):
        return "—"


def pct_badge(v):
    if v is None:
        return '<span class="badge n">无数据</span>'
    v = float(v)
    if v <= 10:
        return '<span class="badge r">极低 %.1f%%</span>' % v
    if v <= 30:
        return '<span class="badge a">偏低 %.1f%%</span>' % v
    if v <= 70:
        return '<span class="badge n">中位 %.1f%%</span>' % v
    if v <= 90:
        return '<span class="badge a">偏高 %.1f%%</span>' % v
    return '<span class="badge g">高位 %.1f%%</span>' % v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    D = json.load(open(a.data, encoding="utf-8"))
    A = D["analysis"]
    M = D["meta"]
    S1 = A["S1_mid"]; S2 = A.get("S2_mid"); S3 = A.get("S3_value")

    # ---------------------------------------------------------- 首屏
    cur = S1["last_value"]
    rng = D["series"]["S1"]["data"]
    rng = [r for r in rng if r["date"] == S1["last_date"]]
    lo = rng[0]["lo"] if rng else None
    hi = rng[0]["hi"] if rng else None
    chg = S1["windows"].get("30", {}).get("change")

    if chg and chg.get("pct_change") is not None:
        cls = "dn" if chg["pct_change"] < 0 else ("up" if chg["pct_change"] > 0 else "flat")
        arrow = "▼" if chg["pct_change"] < 0 else ("▲" if chg["pct_change"] > 0 else "—")
        chg_html = ('<div class="chg %s">%s 近 30 天 %+.2f%% （%+.2f 元/吨）</div>'
                    % (cls, arrow, chg["pct_change"], chg["abs_change"]))
    else:
        chg_html = '<div class="chg flat">近 30 天样本不足，不做区间变动</div>'

    # KPI 四卡
    def pct_card(label, w, note):
        v = S1["windows"].get(w, {})
        if not v.get("available"):
            return ('<div class="kpi"><div class="t">%s</div><div class="v">—</div>'
                    '<div class="d">%s</div></div>' % (label, note or "有效观测不足，不计算分位"))
        p = v["percentile"]
        return ('<div class="kpi hot"><div class="t">%s</div>'
                '<div class="v">%.1f<i>%%</i></div>'
                '<div class="d">%s · n=%d · 中位秩 %.1f%%</div></div>'
                % (label, p["percentile_inclusive_pct"], pct_badge(p["percentile_inclusive_pct"]).split(">")[1].split("<")[0],
                   p["n"], p["percentile_midrank_pct"]))

    k = S1["windows"].get("1095", {})
    kst = k.get("stats") or {}
    kpis = "".join([
        pct_card("3 年经验分位", "1095", ""),
        pct_card("1 年经验分位", "365", ""),
        '<div class="kpi"><div class="t">3 年最高 / 最低</div><div class="v mono">%s<i>/ %s</i></div>'
        '<div class="d">窗口 %s 起，样本 n=%d</div></div>'
        % (f2(kst.get("max"), 0), f2(kst.get("min"), 0), k.get("from", "—"), k.get("n_obs", 0)),
        '<div class="kpi"><div class="t">3 年均值 / 中位数</div><div class="v mono">%s<i>/ %s</i></div>'
        '<div class="d">当前价相对中位 %s</div></div>'
        % (f2(kst.get("mean"), 0), f2(kst.get("median"), 0),
           ("%+.1f%%" % ((cur / kst["median"] - 1) * 100)) if kst.get("median") else "—"),
    ])

    tags = [
        e(M["spec"]), e(M["region"]), e(M["tax"]), e(M["delivery"]),
    ]
    extra_tag = ""
    if S1["windows"].get("1095", {}).get("stats"):
        extra_tag = '<span class="tag warn">3 年分位 %.1f%%</span>' % S1["windows"]["1095"]["percentile"]["percentile_inclusive_pct"]
    tags = "".join('<span class="tag">%s</span>' % t for t in tags) + extra_tag

    # ---------------------------------------------------------- 分位总览卡
    bar_rows = []
    for w in ("30", "90", "365", "1095", "1826"):
        v = S1["windows"].get(w, {})
        if not v.get("available"):
            bar_rows.append(
                '<tr><td>%s</td><td colspan="6" style="color:#6B7A8C">'
                '有效观测 %d 条，低于最小样本门槛（%d），<b>不计算分位</b>——不做外推</td></tr>'
                % (WIN_LABEL[w], v.get("n_obs", 0), 20))
            continue
        p = v["percentile"]
        bar_rows.append(
            '<tr><td><b>%s</b></td>'
            '<td class="num mono">%d</td>'
            '<td class="num mono">%s</td>'
            '<td class="num mono">%s</td>'
            '<td class="num mono">%s</td>'
            '<td>%s</td>'
            '<td class="num mono">%s</td></tr>'
            % (WIN_LABEL[w], v["n_obs"], f2(v["stats"]["min"], 0), f2(v["stats"]["max"], 0),
               f2(v["stats"]["median"], 0), pct_badge(p["percentile_inclusive_pct"]),
               f2(v["range_position_pct"], 1) + "%"))

    perc_card = ('<div class="tscroll">'
                 '<table><thead><tr><th>窗口</th><th class="num">有效观测</th><th class="num">最低</th>'
                 '<th class="num">最高</th><th class="num">中位数</th><th>经验分位（含并列）</th>'
                 '<th class="num">区间位置</th></tr></thead><tbody>%s</tbody></table></div>'
                 % "".join(bar_rows))

    # ---------------------------------------------------------- 分窗口统计总表（三条序列）
    def stat_table(key, label):
        a = A.get(key)
        if not a:
            return ('<tr><td colspan="11" style="color:#6B7A8C">%s：本次未取到可核验序列</td></tr>' % e(label))
        rows = []
        for w in ("30", "90", "365", "1095", "1826"):
            v = a["windows"].get(w, {})
            if not v.get("available"):
                rows.append('<tr><td>%s</td><td colspan="10" style="color:#6B7A8C">'
                            '有效观测 %d，不足门槛，不计算（不外推、不插值）</td></tr>'
                            % (WIN_LABEL[w], v.get("n_obs", 0)))
                continue
            st = v["stats"]; p = v["percentile"]; c = v["change"]
            rows.append(
                '<tr><td><b>%s</b></td><td class="num mono">%d</td>'
                '<td class="num mono">%s</td><td class="num mono">%s</td>'
                '<td class="num mono">%s</td><td class="num mono">%s</td>'
                '<td class="num mono">%s</td><td class="num mono">%s</td>'
                '<td class="num mono">%.2f%%</td><td class="num mono">%s</td>'
                '<td class="num mono">%s</td></tr>'
                % (WIN_LABEL[w], v["n_obs"], f2(st["min"], 0), f2(st["max"], 0),
                   f2(st["mean"], 0), f2(st["median"], 0),
                   f2(p["percentile_inclusive_pct"], 2), f2(p["percentile_midrank_pct"], 2),
                   p["pct_above"],
                   ("%+.2f%%" % c["pct_change"]) if c and c.get("pct_change") is not None else "—",
                   f2(v["range_position_pct"], 1) + "%"))
        return ('<tr class="grp"><td colspan="11" style="background:#EEF4FA;font-weight:700">'
                '%s　（%s 至 %s，共 %d 条真实观测）</td></tr>%s'
                % (e(label), a["first_date"], a["last_date"], a["series_n"], "".join(rows)))

    win_table = ('<table><thead><tr><th>窗口</th><th class="num">n</th><th class="num">最低</th>'
                 '<th class="num">最高</th><th class="num">均值</th><th class="num">中位数</th>'
                 '<th class="num">经验分位<br>含并列</th><th class="num">经验分位<br>中位秩</th>'
                 '<th class="num">高于现价<br>占比</th><th class="num">区间涨跌</th>'
                 '<th class="num">区间位置<br>(非分位)</th></tr></thead><tbody>%s</tbody></table>'
                 % "".join([
                     stat_table("S1_mid", "S1 华东·重质纯碱·主流市场区间中值（主口径）"),
                     stat_table("S2_mid", "S2 华东·轻质纯碱·主流市场区间中值（辅助口径）"),
                     stat_table("S3_value", "S3 全国·重质纯碱·生意社基准价（辅助口径）"),
                 ]))

    # ---------------------------------------------------------- 季节性表
    se = (S1.get("seasonality") or {})
    monthly = se.get("monthly") or []
    yrs = sorted({r["year"] for r in monthly})
    mons = list(range(1, 13))
    cell = {}
    for r in monthly:
        cell[(r["year"], r["month"])] = r
    head = "<th>年份</th>" + "".join('<th class="num">%d月</th>' % m for m in mons)
    body = []
    for y in yrs:
        tds = ['<td><b>%d</b></td>' % y]
        for m in mons:
            r = cell.get((y, m))
            if not r:
                tds.append('<td class="num" style="color:#C6D0DA">—</td>')
            else:
                tds.append('<td class="num mono" title="n=%d">%s</td>' % (r["n"], f2(r["mean"], 0)))
        body.append("<tr>%s</tr>" % "".join(tds))
    season_table = ('<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
                    % (head, "".join(body)))
    season_note = ('<div class="note info">「—」＝该年该月<b>没有</b>有效观测，不是 0，也不做填补。'
                   '单元格为当月所有真实报价的中值均值；悬浮可见观测条数。</div>')

    # ---------------------------------------------------------- 波动卡
    vol = S1.get("volatility") or {}
    vcards = []
    lbl = {"30": "近 30 天", "90": "近 3 个月", "365": "近 1 年"}
    for w in ("30", "90", "365"):
        v = vol.get(w)
        if not v:
            vcards.append('<div class="kpi"><div class="t">%s年化波动率</div><div class="v">—</div>'
                          '<div class="d">有效观测不足</div></div>' % lbl[w])
            continue
        vcards.append(
            '<div class="kpi"><div class="t">%s · 年化波动率</div>'
            '<div class="v">%.2f<i>%%</i></div>'
            '<div class="d">日均绝对变动 %.3f%% · 最大单日 %.2f%% · ≥1%% 天数占比 %.1f%%</div></div>'
            % (lbl[w], v["ann_vol_pct"], v["mean_abs_daily_pct"] or 0,
               v["max_abs_daily_pct"] or 0, v["pct_days_ge_1pct"] or 0))
    mdd = S1.get("mdd")
    if mdd:
        vcards.append(
            '<div class="kpi"><div class="t">最大回撤（全样本）</div>'
            '<div class="v">%.2f<i>%%</i></div>'
            '<div class="d">%s → %s</div></div>'
            % (mdd["mdd_pct"], mdd["peak_date"], mdd["trough_date"]))
    vol_cards = '<div class="grid3">%s</div>' % "".join(vcards)

    # ---------------------------------------------------------- 异常列表
    an = S1.get("anomalies") or {}
    lvl = an.get("level") or []
    jmp = an.get("jump") or []

    # 水平异常常连续多日同值，逐日罗列会刷屏：按「价格相同的连续段」合并成区间
    runs = []
    for x in lvl:
        if runs and runs[-1]["value"] == x["value"]:
            runs[-1]["to"] = x["date"]
            runs[-1]["n"] += 1
        else:
            runs.append({"from": x["date"], "to": x["date"], "n": 1, "value": x["value"],
                         "flags": x["flags"]})
    items = []
    for r in runs[-18:]:
        fs = []
        for f in r["flags"]:
            if f["rule"] == "level_mad":
                fs.append("水平偏离稳健 z=%.2f" % f["score"])
            elif f["rule"] == "iqr_fence":
                fs.append("越 IQR 栅栏")
        span = r["from"] if r["from"] == r["to"] else "%s → %s" % (r["from"], r["to"])
        items.append('<div class="ev"><div class="dt">%s</div>'
                     '<div class="bd"><div class="h">水平异常 · 连续 %d 个报价日</div>'
                     '<div class="x">%s</div></div>'
                     '<div class="v">%s</div></div>'
                     % (span, r["n"], "；".join(fs), f2(r["value"], 0)))
    for x in jmp[-30:]:
        for f in x["flags"]:
            if f["rule"] == "jump":
                items.append('<div class="ev"><div class="dt">%s</div>'
                             '<div class="bd"><div class="h">单日跳变 %+.2f%%</div>'
                             '<div class="x">前值 %s（%s）</div></div>'
                             '<div class="v">%s</div></div>'
                             % (x["date"], f["pct"], f2(f["from_value"], 0), f["from_date"], f2(x["value"], 0)))
    anomaly_list = "".join(reversed(items)) or '<div style="color:#6B7A8C">未识别出异常观测。</div>'

    # ---------------------------------------------------------- 事件（可核验）
    ev = D.get("events") or []
    ev_items = []
    for x in ev:
        ev_items.append(
            '<div class="ev"><div class="dt">%s</div><div class="bd">'
            '<div class="h">%s</div><div class="x">%s</div>'
            '<div class="src">来源：%s</div></div></div>'
            % (e(x.get("date", "")), e(x.get("title", "")), e(x.get("detail", "")),
               '<a href="%s" target="_blank">%s</a>' % (e(x.get("url", "#")), e(x.get("source", "—")))))
    event_list = "".join(ev_items) or '<div style="color:#6B7A8C">本次未附可核验事件。</div>'

    # ---------------------------------------------------------- 口径卡
    cav = D.get("caveats") or []
    cav_html = "".join(
        '<div class="note %s"><b>%s</b>%s</div>' % (c.get("level", ""), e(c.get("title", "")), c.get("body", ""))
        for c in cav)
    gaps = S1.get("gaps") or {}
    runs = gaps.get("runs") or []
    gap_items = "".join('<tr><td class="mono">%s</td><td class="mono">%s</td>'
                        '<td class="num mono">%d</td></tr>'
                        % (r["from"], r["to"], r["workdays"]) for r in runs[:24])
    gap_html = ('<div class="note info"><b>数据缺口：</b>序列共识别出 <b>%d</b> 个连续缺口段'
                '（连续 ≥3 个工作日无报价），另有 <b>%d</b> 个单日缺失（多为法定假日）。'
                '缺口一律留空，<b>不插值、不模拟补价</b>。</div>' % (gaps.get("run_count", 0), gaps.get("single_missing", 0)))
    if runs:
        gap_html += ('<details><summary>展开缺口明细（前 24 段）</summary><div class="dc">'
                     '<table><thead><tr><th>起</th><th>止</th><th class="num">缺失工作日</th></tr></thead>'
                     '<tbody>%s</tbody></table></div></details>' % gap_items)

    # 口径变更表
    cov_html = ""
    for c in D.get("coverage_change") or []:
        if c["series"] != "S1":
            continue
        cov_html = (
            '<div class="note bad"><b>口径变更（影响可比性）：</b>生意社「%s」日评在 '
            '<b>%s 之前完全不披露该规格价格</b>（%d 个月中仅 %d 个月有该品种报价，%d 个月为 0 覆盖），'
            '<b>%s 起转为持续披露</b>。因此基于该序列的 3 年/5 年窗口实际只有 '
            '<b>%s 至 %s</b> 的观测，5 年窗口与 3 年窗口样本完全相同——'
            '这不是"5 年数据齐全"，而是<b>该口径只有这么长的历史</b>。</div>'
            % (e(c["label"]), c["first_full_month"], c["months_total"], c["months_full"],
               c["months_zero"], c["first_full_month"], S1["first_date"], S1["last_date"]))
    caveat_card = '<div class="card pad">%s%s%s</div>' % (cov_html, cav_html, gap_html)

    # ---------------------------------------------------------- 来源表
    srcs = D.get("sources") or []
    src_rows = "".join(
        '<tr><td>%s</td><td>%s</td><td class="src"><a href="%s" target="_blank">%s</a></td></tr>'
        % (e(s.get("name", "")), e(s.get("used_for", "")), e(s.get("url", "#")), e(s.get("url", "")))
        for s in srcs)
    source_table = ('<div class="tscroll"><table>'
                    '<thead><tr><th>来源</th><th>用于</th><th>链接</th></tr></thead>'
                    '<tbody>%s</tbody></table></div>' % src_rows)

    footer = ('报告生成于 %s ｜ 数据基准日 <b>%s</b> ｜ 全部价格均为真实可核验观测，'
              '无插值、无模拟、不含未来价格预测。<br>'
              '分钟级复核：任一价格均可在「来源」列点开当日报价原文核对。'
              % (e(M["generated_at"]), e(M["asof"])))

    # ---------------------------------------------------------- 组装
    tpl = open(os.path.join(TPL, "report.html"), encoding="utf-8").read()
    appjs = open(os.path.join(TPL, "app.js"), encoding="utf-8").read()
    echarts = open(os.path.join(ASSETS, "echarts.min.js"), encoding="utf-8").read()

    payload = {
        "meta": M,
        "series": {k: {"name": v["name"], "note": v.get("note", ""), "data": v["data"]}
                   for k, v in D["series"].items()},
        "analysis": {k: {"series_n": v["series_n"], "first_date": v["first_date"],
                         "last_date": v["last_date"], "last_value": v["last_value"],
                         "windows": v["windows"], "volatility": v["volatility"],
                         "anomalies": v["anomalies"], "seasonality": v["seasonality"],
                         "gaps": v["gaps"], "mdd": v["mdd"]}
                     for k, v in A.items() if v},
    }

    out = tpl
    for key, val in [
        ("__TITLE__", "华东重质纯碱 · 现货价格历史位置分析"),
        ("__SUBLINE__", '<b>%s</b> ｜ 基准日 <b>%s</b> ｜ 当前 <b>%s 元/吨</b> ｜ 3 年经验分位 <b>%s</b>'
         % (e(M["region"]), e(M["asof"]), f2(cur, 0),
            f2(S1["windows"].get("1095", {}).get("percentile", {}).get("percentile_inclusive_pct"), 1) + "%"
            if S1["windows"].get("1095", {}).get("available") else "样本不足")),
        ("__TAGS__", tags),
        ("__ASOF__", e(M["asof"])),
        ("__PRICE__", f2(cur, 2)),
        ("__CHG__", chg_html),
        ("__SPEC__", e(M["spec"])),
        ("__REGION__", e(M["region"])),
        ("__TAX__", e(M["tax"] + " / " + M["delivery"])),
        ("__DATA_DATE__", e(S1["last_date"])),
        ("__SOURCE__", e(M["source"])),
        ("__RANGE__", ("%s – %s" % (f2(lo, 0), f2(hi, 0))) if lo else "—"),
        ("__KPIS__", kpis),
        ("__PERCENTILE_CARD__", perc_card),
        ("__WINDOW_TABLE__", win_table),
        ("__SEASON_TABLE__", season_note + '<div class="tscroll">'
         '<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
         % (head, "".join(body))),
        ("__VOL_CARDS__", vol_cards),
        ("__ANOMALY_LIST__", anomaly_list),
        ("__EVENT_LIST__", event_list),
        ("__CAVEAT_CARD__", caveat_card),
        ("__SOURCE_TABLE__", source_table),
        ("__FOOTER__", footer),
        ("__ECHARTS__", echarts),
        ("__DATA_JSON__", json.dumps(payload, ensure_ascii=False)),
        ("__APP_JS__", appjs),
    ]:
        out = out.replace(key, val)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(out)
    print("ok", a.out, "%.2f MB" % (len(out.encode("utf-8")) / 1048576))


if __name__ == "__main__":
    main()
