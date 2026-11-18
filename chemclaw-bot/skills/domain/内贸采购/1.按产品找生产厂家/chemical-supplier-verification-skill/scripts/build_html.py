#!/usr/bin/env python3
"""Build a self-contained HTML report from a chemical supplier project.json.

Usage:
    python scripts/build_html.py path/to/project.json --out path/to/output.html
"""
from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

E = html.escape

REGION_MAP = {
    "华东": {"上海", "江苏", "浙江", "安徽", "福建", "江西", "山东"},
    "华北": {"北京", "天津", "河北", "山西", "内蒙古"},
    "华中": {"河南", "湖北", "湖南"},
    "华南": {"广东", "广西", "海南"},
    "西南": {"重庆", "四川", "贵州", "云南", "西藏"},
    "西北": {"陕西", "甘肃", "青海", "宁夏", "新疆"},
    "东北": {"辽宁", "吉林", "黑龙江"},
}
PROVINCE_TO_REGION = {p: r for r, ps in REGION_MAP.items() for p in ps}
PALETTE = ["#0f766e", "#d97706", "#14263b", "#2563eb", "#7c3aed", "#b42318", "#0d9488", "#8b97a7"]


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fmt(v, digits=0) -> str:
    if v is None or v == "":
        return "未披露"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{v:,.{digits}f}"
    return str(v)


def tier_for(score: float, tiers: list[dict]) -> str:
    for t in sorted(tiers, key=lambda x: x.get("min", 0), reverse=True):
        if score >= t.get("min", 0):
            return t.get("label", "")
    return ""


def calc_composite(c: dict, w: dict) -> float:
    return round(
        c.get("certainty", 0) * w.get("certainty", 0)
        + c.get("spec_score", 0) * w.get("spec", 0)
        + c.get("scale_score", 0) * w.get("scale", 0)
        + c.get("distance_score", 0) * w.get("distance", 0),
        1,
    )


def region_of(province: str) -> str:
    return PROVINCE_TO_REGION.get(province, "其他")


def compute(d: dict) -> dict:
    M = d["meta"]
    C = d["companies"]
    W = d["scoring"]["weights"]
    tiers = d["scoring"]["tiers"]
    for c in C:
        if c.get("composite") is None:
            c["composite"] = calc_composite(c, W)
        if not c.get("tier"):
            c["tier"] = tier_for(c["composite"], tiers)
        if c.get("spec_open") is None:
            c["spec_open"] = sum(1 for r in c.get("spec_rows", []) if r.get("status") == "部分公开")
        if not c.get("nearest_plant") and c.get("plants"):
            c["nearest_plant"] = c["plants"][0].get("name", "")
        if c.get("nearest_city") is None:
            nearest = next((p for p in c.get("plants", []) if p.get("name") == c.get("nearest_plant")), (c.get("plants") or [{}])[0])
            c["nearest_city"] = nearest.get("city", "")
        if c.get("spec_gaps") is None:
            c["spec_gaps"] = [r.get("label", "") for r in c.get("spec_rows", []) if r.get("status") != "部分公开"]
        if c.get("full_name") is None:
            c["full_name"] = c.get("full", "")
    C.sort(key=lambda c: (c.get("rank") or 999, -(c.get("composite") or 0)))
    plants = [(c, p) for c in C for p in c.get("plants", [])]
    capacity_total = sum(c.get("capacity", 0) for c in C)
    provinces = {p.get("province", "") for _, p in plants if p.get("province")}
    province_tot = Counter()
    process_tot = Counter()
    region_tot = Counter()
    region_provs: dict[str, set[str]] = {}
    for _, p in plants:
        prov = p.get("province", "")
        if prov:
            province_tot[prov] += p.get("capacity", 0)
            reg = region_of(prov)
            region_tot[reg] += p.get("capacity", 0)
            region_provs.setdefault(reg, set()).add(prov)
        process_tot[p.get("process", "未分类")] += p.get("capacity", 0)
    return {
        "companies": C,
        "plants": plants,
        "capacity_total": capacity_total,
        "provinces": provinces,
        "province_tot": sorted(province_tot.items(), key=lambda x: -x[1]),
        "process_tot": sorted(process_tot.items(), key=lambda x: -x[1]),
        "region_tot": sorted(region_tot.items(), key=lambda x: -x[1]),
        "region_provs": region_provs,
        "tiers": Counter(c.get("tier", "") for c in C),
    }


def kpi_html(d: dict, x: dict) -> str:
    M = d["meta"]
    spec_count = len(d["specs"])
    counts = Counter(e.get("level", "") for c in x["companies"] for e in c.get("evidence", []))
    priority = d["scoring"]["tiers"][0] if d["scoring"]["tiers"] else {"min": 84, "label": "优先"}
    items = [
        (str(len(x["companies"])), "生产厂家", "有装置/产能/产量证据，不是经营范围"),
        (str(len(x["plants"])), "生产基地", f"覆盖 {len(x['provinces'])} 个省级产区，多基地分列"),
        (fmt(x["capacity_total"]), f"样本产能（{M.get('capacity_unit', '万吨/年')}）", M.get("sample_note", "")),
        (str(x["tiers"].get(priority["label"], 0)), priority["label"], f"综合 ≥{priority['min']}；主供/备供见 09"),
        ("0", "公开批次 COA", f"{spec_count} 项指标无一家公开连续批次数据"),
        (str(sum(counts.values())), "条生产证据", f"A{counts.get('直接-A', 0)} / B{counts.get('直接-B', 0)} / C{counts.get('间接-C', 0)}，每条可回溯"),
    ]
    return "\n".join(
        f'<div class="kpi"><div class="n">{E(n)}</div><div class="l">{E(l)}</div><div class="s">{E(s)}</div></div>'
        for n, l, s in items
    )


def hero_card(d: dict) -> str:
    M = d["meta"]
    R = d["rfq"]
    lines = []
    for i in range(0, min(6, len(d["specs"])), 2):
        a = d["specs"][i]
        if i + 1 < len(d["specs"]):
            b = d["specs"][i + 1]
            lines.append(
                f'<div class="spec-line"><span>{E(a.get("label", ""))} / {E(b.get("label", ""))}</span>'
                f'<b>{E(a.get("requirement", ""))} / {E(b.get("requirement", ""))}</b></div>'
            )
        else:
            lines.append(
                f'<div class="spec-line"><span>{E(a.get("label", ""))}</span>'
                f'<b>{E(a.get("requirement", ""))}</b></div>'
            )
    cas = " · ".join(x for x in [f"CAS {M.get('cas')}" if M.get("cas") else "", f"HS {M.get('hs')}" if M.get("hs") else "", M.get("standard", "")] if x)
    return f'''
          <div class="hero-card-head"><span>RFQ SNAPSHOT</span><b>示例需求</b></div>
          <div class="hero-q">
            <p class="product">{E(M.get("product", ""))}<br>{E(M.get("application", ""))}</p>
            <div class="cas">{E(cas)}</div>
            {"".join(lines)}
            <div class="spec-line"><span>收货地</span><b>{E(M.get("destination", ""))}</b></div>
            <div class="big"><strong>{fmt(R.get("qty_month"), 0)}</strong><span>{E(M.get("quantity_unit", "吨"))} / 月 · {fmt(R.get("qty_year"), 0)} {E(M.get("quantity_unit", "吨"))} / 年</span></div>
          </div>'''


def hero_chips(d: dict, x: dict) -> str:
    return "\n".join([
        f'<span class="pill"><i></i>{len(x["companies"])} 家生产厂家</span>',
        f'<span class="pill"><i></i>{len(x["plants"])} 个基地</span>',
        '<span class="pill amber"><i></i>0 家公开批次 COA</span>',
        f'<span class="pill red"><i></i>{len(d.get("traders", []))} 个贸易/流通样本</span>',
        '<span class="pill"><i></i>每条数据可回溯</span>',
    ])


def spec_table_rows(d: dict) -> str:
    out = []
    for s in d["specs"]:
        out.append(
            f'<tr><td><b>{E(s.get("label", ""))}</b></td><td>{E(s.get("requirement", ""))}</td>'
            f'<td>{E(s.get("unit", "—"))}</td><td>{E(s.get("method", "—"))}</td>'
            f'<td>{E(s.get("why", "—"))}</td></tr>'
        )
    return "\n".join(out)


def province_bars(d: dict, x: dict) -> str:
    if not x["province_tot"]:
        return '<div class="note-box">尚无可汇总的基地产能。</div>'
    maxv = max(v for _, v in x["province_tot"]) or 1
    out = []
    for name, v in x["province_tot"]:
        pct = round(v / maxv * 100, 1)
        out.append(
            f'<div class="prov-row" title="{E(name)}：{fmt(v)} {E(d["meta"].get("capacity_unit", ""))}">'
            f'<span class="nm">{E(name)}</span><span class="bar"><i style="width:{pct}%"></i></span>'
            f'<span class="vl">{fmt(v)}</span></div>'
        )
    return "\n".join(out)


def donut(d: dict, x: dict) -> tuple[str, str]:
    total = sum(v for _, v in x["process_tot"]) or 1
    segs, legend = [], []
    cum = 0.0
    for i, (name, v) in enumerate(x["process_tot"]):
        pct = v / total * 100
        color = PALETTE[i % len(PALETTE)]
        segs.append(f"{color} {cum:.2f}% {cum + pct:.2f}%")
        legend.append(
            f'<div class="dl"><i style="background:{color}"></i><span>{E(name)}</span>'
            f'<b>{fmt(v)} · {pct:.0f}%</b></div>'
        )
        cum += pct
    return "conic-gradient(" + ", ".join(segs) + ")", "\n".join(legend)


def corridor(d: dict, x: dict) -> str:
    if not x["region_tot"]:
        return '<div class="note-box">尚无区域产能可汇总。</div>'
    out = []
    for reg, v in x["region_tot"][:6]:
        provs = " / ".join(sorted(x["region_provs"].get(reg, set()))[:3])
        out.append(
            f'<div class="region-node"><div class="dot"></div><b>{E(reg)}</b>'
            f'<span>{E(provs)}</span><em>{fmt(v)} {E(d["meta"].get("capacity_unit", ""))}</em></div>'
        )
    return "\n".join(out)


def evidence_cards(d: dict, x: dict) -> str:
    counts = Counter(e.get("level", "") for c in x["companies"] for e in c.get("evidence", []))
    counts["仅工商-D"] = len(d.get("traders", []))
    desc = {
        "直接-A": "定期报告、政府项目、环评、公告。能直接证明装置/产能/产量，是本池的主证据。",
        "直接-B": "公司官网、IR、招聘主页中的产能与基地地址。需与 A 级来源交叉后才打 90+。",
        "间接-C": "新闻、行业统计、原料采购、招聘。只能做旁证；不能单独证明“在生产”。",
        "仅工商-D": "营业执照经营范围、店铺 SKU、代理宣称。单独标红，不进入厂家池。",
    }
    out = []
    for lv in ["直接-A", "直接-B", "间接-C", "仅工商-D"]:
        cls = {"直接-A": "a", "直接-B": "b", "间接-C": "c", "仅工商-D": "d"}[lv]
        out.append(
            f'<div class="ev-card"><span class="lv lv-{cls}">{E(lv)}</span>'
            f'<h4>{E(desc[lv].split("。")[0])}</h4><p>{E(desc[lv])}</p>'
            f'<div class="cnt">{counts.get(lv, 0)}</div></div>'
        )
    return "\n".join(out)


def traders(d: dict) -> str:
    out = []
    for t in d.get("traders", []):
        out.append(
            f'<article class="trader" title="{E(t.get("evidence", ""))}">'
            f'<div class="type">{E(t.get("type", ""))} · {E(t.get("region", ""))}</div>'
            f'<h4>{E(t.get("name", ""))}</h4><p>{E(t.get("why", ""))}</p>'
            f'<p style="color:var(--red);margin-top:6px"><b>{E(t.get("level", ""))}</b> · 不进入厂家池</p>'
            f'</article>'
        )
    return "\n".join(out)


def conflicts(d: dict) -> str:
    out = []
    for c in d.get("conflicts", []):
        impact = f'<p><b>影响：</b>{E(c.get("impact", ""))}</p>' if c.get("impact") else ""
        out.append(
            f'<article class="conflict"><h4>{E(c.get("topic", ""))}</h4>'
            f'<div class="pair"><span>A：{E(c.get("a", ""))}</span><span>B：{E(c.get("b", ""))}</span></div>'
            f'<p><b>处理：</b>{E(c.get("resolution", ""))}</p>{impact}</article>'
        )
    return "\n".join(out)


def gaps(d: dict) -> str:
    out = []
    for g in d.get("gaps", []):
        cls = "p0" if g.get("priority") == "P0" else ""
        out.append(
            f'<tr><td class="{cls}">{E(g.get("priority", ""))}</td><td><b>{E(g.get("gap", ""))}</b></td>'
            f'<td>{E(g.get("impact", ""))}</td><td>{E(g.get("verify", ""))}</td></tr>'
        )
    return "\n".join(out)


def actions(d: dict) -> str:
    return "\n".join(
        f'<div class="action-item"><div class="ph">{E(a.get("phase", ""))}</div>'
        f'<div><b>{E(a.get("action", ""))}</b><span>{E(a.get("detail", ""))}</span></div></div>'
        for a in d.get("actions", [])
    )


def sources(d: dict) -> str:
    out = []
    for s in d.get("sources", []):
        grade_cls = {"A": "teal", "B": "blue", "C": "amber", "D": "red"}.get(s.get("grade", ""), "amber")
        url = s.get("url", "")
        link = f'<a href="{E(url)}" target="_blank" rel="noopener">{E(url)}</a>' if url else "—"
        out.append(
            f'<tr><td><b>{E(s.get("id", ""))}</b></td><td>{E(s.get("org", ""))}</td>'
            f'<td title="{E(s.get("used", ""))}">{E(s.get("title", ""))}</td>'
            f'<td>{E(s.get("date", ""))}</td><td><span class="badge {grade_cls}">{E(s.get("grade", ""))}</span></td>'
            f'<td>{link}</td></tr>'
        )
    return "\n".join(out)


def weight_rows(d: dict) -> str:
    W = d["scoring"]["weights"]
    labels = [("certainty", "生产确定性"), ("spec", "规格匹配"), ("scale", "规模"), ("distance", "距离")]
    out = []
    for key, label in labels:
        v = W.get(key, 0)
        out.append(
            f'<div class="weight-row"><span>{E(label)}</span>'
            f'<div class="bar"><i style="width:{v * 100:.0f}%"></i></div><b>{v:.0%}</b></div>'
        )
    return "\n".join(out)


def build(d: dict, out: Path) -> Path:
    M = d["meta"]
    R = d["rfq"]
    x = compute(d)
    templates = Path(__file__).resolve().parent.parent / "templates"
    tpl = (templates / "report.html").read_text(encoding="utf-8")
    css = (templates / "style.css").read_text(encoding="utf-8")
    js = (templates / "app.js").read_text(encoding="utf-8")

    cap_unit = M.get("capacity_unit", "万吨/年")
    qty_unit = M.get("quantity_unit", "吨")
    spec_count = len(d["specs"])
    base = M.get("output_basename") or f"{M.get('product_short', '产品')}生产厂家核验池_{M.get('destination_short', '')}_{M.get('as_of', '')[:7].replace('-', '')}"
    excel_name = (out.with_suffix(".xlsx").name if out else base + ".xlsx")
    donut_style, donut_legend = donut(d, x)
    W = d["scoring"]["weights"]
    weights_summary = f"确定性{W.get('certainty', 0):.0%} + 规格{W.get('spec', 0):.0%} + 规模{W.get('scale', 0):.0%} + 距离{W.get('distance', 0):.0%}"
    weights_long = f"生产确定性 × {W.get('certainty', 0):.0%} + 规格匹配 × {W.get('spec', 0):.0%} + 规模 × {W.get('scale', 0):.0%} + 距离 × {W.get('distance', 0):.0%}"
    first_open = max((c.get("spec_open", 0) for c in x["companies"]), default=0)
    priority = d["scoring"]["tiers"][0] if d["scoring"]["tiers"] else {"min": 84, "label": "优先"}
    lede = M.get("lede") or (
        f"以“{R.get('title', '')}”为示例，把 {len(x['companies'])} 家生产厂家、{len(x['plants'])} 个基地、"
        f"{fmt(x['capacity_total'])} {cap_unit} 样本产能放进同一张核验表：先证明“真的在生产”，再比规格、规模和距离。"
        f"贸易商、代理与仅工商信息单独标红，不混入厂家池。"
    )
    rfq_desc = M.get("rfq_desc") or (
        f"产品、规格、数量、收货地四项决定“谁能供”。本页按 {spec_count} 项指标逐项对照；上传规格书只做辅助识别，"
        f"最终以人工确认为准。"
    )
    region_opts = "".join(
        f"<option>{E(v)}</option>" for v in [
            R.get("region_pref", "本地/邻近区域优先"),
            "仅本省/邻省",
            "不限地区，按到厂价",
        ]
    )
    corridor_html = corridor(d, x)
    data = dict(d)
    data["companies"] = x["companies"]
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    theme = M.get("theme") or {}
    brand_css = (
        "\n/* brand theme */\n:root{\n"
        f"  --brand-accent:{theme.get('accent', '#0f766e')};\n"
        f"  --brand-accent-2:{theme.get('accent_2', '#14b8a6')};\n"
        f"  --brand-accent-soft:{theme.get('accent_soft', '#e6f4f1')};\n"
        f"  --brand-ink:{theme.get('ink', '#0b1726')};\n"
        f"  --brand-serif:{theme.get('serif', 'Source Han Serif SC, Noto Serif SC, Songti SC, SimSun, serif')};\n"
        "}\n"
        ".brand-mark svg path{stroke:var(--brand-accent-2)}\n"
        ".hero h1 em,.section-title em{color:var(--brand-accent)}\n"
        ".pill i{background:var(--brand-accent-2)}\n"
        ".tier.t1{background:var(--brand-accent)!important}\n"
        ".btn-primary{background:var(--brand-accent)!important;border-color:var(--brand-accent)!important}\n"
        ".prov-row .bar i{background:linear-gradient(90deg,var(--brand-accent),var(--brand-accent-2))}\n"
        ".kpi .n{color:var(--brand-accent)}\n"
    )
    repl = {
        "__META_DESCRIPTION__": f"{M.get('title', '')}：按产品找生产厂家，区分生产厂家/贸易商，展示直接证据、间接证据与规格匹配缺口。",
        "__TITLE__": M.get("title", "生产厂家核验池"),
        "__BRAND__": M.get("brand", "化工品核验"),
        "__BRAND_SUB__": "CHEMICAL PRODUCER VERIFICATION",
        "__ASOF__": M.get("as_of", ""),
        "__EXCEL_FILENAME__": excel_name,
        "__PRODUCT_SHORT__": M.get("product_short", "产品"),
        "__LEDE__": lede,
        "__HERO_CHIPS__": hero_chips(d, x),
        "__HERO_CARD__": hero_card(d),
        "__KPI_HTML__": kpi_html(d, x),
        "__RFQ_DESC__": rfq_desc,
        "__QTY_MONTH_FMT__": fmt(R.get("qty_month"), 0),
        "__QTY_UNIT__": qty_unit,
        "__QTY_MONTH__": str(R.get("qty_month", "")),
        "__RFQ_PRODUCT_VALUE__": R.get("product", M.get("product", "")),
        "__DESTINATION__": R.get("destination", M.get("destination", "")),
        "__RFQ_REGION_OPTIONS__": region_opts,
        "__SPEC_COUNT__": str(spec_count),
        "__SPEC_TABLE_ROWS__": spec_table_rows(d),
        "__PROVINCE_TITLE__": "产能分布：按生产基地所在省汇总",
        "__PROVINCE_DESC__": f"按生产基地所在省汇总，单位：{cap_unit}；样本 {fmt(x['capacity_total'])} {cap_unit}。样本覆盖不等于市场份额。",
        "__PROVINCE_BARS__": province_bars(d, x),
        "__PROCESS_TITLE__": "工艺/路线结构：不同路线，不同成本与杂质",
        "__PROCESS_DESC__": "工艺影响成本、杂质控制与副产物；不是“越新越好”，要看下游规格与稳定性。",
        "__DONUT_STYLE__": donut_style,
        "__DONUT_LEGEND__": donut_legend,
        "__CAPACITY_FMT__": fmt(x["capacity_total"]),
        "__CAP_UNIT__": cap_unit,
        "__CORRIDOR__": corridor_html,
        "__DEST_SHORT__": M.get("destination_short", "收货地"),
        "__SPEC_OPEN_EXAMPLE__": str(first_open),
        "__POOL_COUNT__": str(len(x["companies"])),
        "__PLANT_COUNT__": str(len(x["plants"])),
        "__WEIGHT_SUMMARY__": weights_summary,
        "__WEIGHT_SUMMARY_LONG__": weights_long,
        "__WEIGHT_ROWS__": weight_rows(d),
        "__SENSITIVITY__": d.get("sensitivity", "若把距离权重提高 10–15 个百分点，近距企业会上升；若把规模权重提高，大厂会上升。当前权重适合“先保供、再优化成本”的场景。"),
        "__EVIDENCE_COUNT__": str(sum(len(c.get("evidence", [])) for c in x["companies"])),
        "__EVIDENCE_CARDS__": evidence_cards(d, x),
        "__TRADER_COUNT__": str(len(d.get("traders", []))),
        "__TRADERS__": traders(d),
        "__GAP_COUNT__": str(len(d.get("gaps", []))),
        "__GAP_ROWS__": gaps(d),
        "__CONFLICTS__": conflicts(d),
        "__ACTIONS__": actions(d),
        "__ACTION_INTRO__": d.get("action_intro", "先把“谁在生产”变成“谁能稳定供、什么价、什么账期”。建议主供 1 家 + 备供 2 家，先小批量试单，再签年度框架。"),
        "__SOURCE_COUNT__": str(len(d.get("sources", []))),
        "__SOURCES__": sources(d),
        "__FOOTER_TITLE__": f"{M.get('brand', '')} · {M.get('title', '')}",
        "__FOOTER_META__": f"示例需求：{R.get('title', '')} · 收货地{M.get('destination', '')} · 数据截止 {M.get('as_of', '')}",
        "__DISCLAIMER__": M.get("disclaimer", "本页用于采购初筛，不替代现场审核、样品检测与商务尽调。产能≠产量，标准≠批次合格，直线距离≠运费。未披露的数据以“未披露/未核验”标注，不做猜测填充。"),
        "__DATA__": data_json,
        "__BRAND_CSS__": brand_css,
    }
    for key, val in repl.items():
        tpl = tpl.replace(key, str(val))
    tpl = tpl.replace("__BRAND_CSS__", brand_css)
    tpl = tpl.replace("/*__CSS__*/", css)
    tpl = tpl.replace("/*__JS__*/", js)
    if "__" in tpl:
        leftovers = sorted(set(__import__("re").findall(r"__[A-Z_]+__", tpl)))
        if leftovers:
            print("WARN leftover placeholders:", leftovers[:10])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(tpl, encoding="utf-8", newline="\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Build HTML from project.json")
    ap.add_argument("project", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    d = load(args.project)
    out = build(d, args.out)
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
