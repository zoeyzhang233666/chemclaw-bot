"""Assemble the interactive HTML review report.

Usage:
    python build_report.py <contract_parsed.json> <data_meta.json> <issues-*.json, ...> --out report.html

Reads templates report.css / report.js from the same directory as this script
(or --template-dir).
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

KIND_CLASS = {
    "h1": "b-art",
    "annex-title": "b-annex",
    "h2": "b-clause",
    "p": "b-p",
    "exec-line": "b-p exec-line",
    "exec-col": "b-p exec-col",
}


def esc(s: str) -> str:
    return (
        str(s if s is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def load_issues(paths: list[str]) -> list[dict]:
    issues: list[dict] = []
    for p in paths:
        data = json.load(io.open(p, encoding="utf-8"))
        issues.extend(data.get("issues", []))
    seen = set()
    for i in issues:
        if i["id"] in seen:
            raise SystemExit(f"duplicate issue id {i['id']}")
        seen.add(i["id"])
    issues.sort(key=lambda i: i.get("seq", 999))
    return issues


def render_blocks(blocks: list[dict]) -> str:
    out: list[str] = []
    for b in blocks:
        kind = b["kind"]
        bid = b["id"]
        if kind == "table":
            rows = b["rows"]
            head = rows[0]
            body = rows[1:]
            th = "".join(f"<th>{esc(c)}</th>" for c in head)
            trs = "".join(
                "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in body
            )
            out.append(
                f'<table class="c-table" data-bid="{esc(bid)}"><thead><tr>{th}</tr></thead>'
                f"<tbody>{trs}</tbody></table>"
            )
            continue
        if kind == "exec-col":
            lines = b.get("lines", [])
            inner = "".join(
                f'<div class="xl" data-bid="{esc(ln["id"])}">{esc(ln["text"])}</div>'
                for ln in lines
            )
            out.append(f'<div class="b-p exec-col" data-bid="{esc(bid)}">{inner}</div>')
            continue
        cls = KIND_CLASS.get(kind, "b-p")
        out.append(f'<div class="{cls}" data-bid="{esc(bid)}">{esc(b["text"])}</div>')
    return "\n".join(out)


def build(parsed: dict, meta: dict, issues: list[dict], template_dir: Path) -> str:
    css = (template_dir / "report.css").read_text(encoding="utf-8")
    js = (template_dir / "report.js").read_text(encoding="utf-8")

    counts = {"high": 0, "medium": 0, "low": 0}
    for i in issues:
        counts[i["severity"]] = counts.get(i["severity"], 0) + 1
    total = len(issues)
    missing_n = sum(1 for i in issues if i["category"] == "missing")

    payload = {
        "meta": meta,
        "categories": meta_categories(meta, issues),
        "severities": SEVERITIES,
        "issues": issues,
    }

    meta_rows = "".join(
        f"<tr><td>{esc(m['k'])}</td><td>{esc(m['v'])}</td></tr>" for m in parsed["meta"]
    )

    body = render_blocks(parsed["blocks"])

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(meta['review_title'])} — {esc(meta['contract_no'])}</title>
<meta name="description" content="{esc(meta['review_title'])} · 模拟合同 · 业务风险提醒，不构成法律意见">
<style>
{css}
</style>
</head>
<body>

<header class="topbar">
  <div class="topbar-inner">
    <div class="brand">
      <h1>{esc(meta['review_title'])}</h1>
      <span class="sub">{esc(meta['product_cn'])} · 中国出口 → 印度尼西亚 · {esc(meta['trade_term'])}</span>
    </div>
    <span class="sim-badge"><span class="dot"></span>模拟合同 SIMULATED</span>
    <div class="spacer"></div>
    <div class="kpi-strip">
      <div class="kpi high"><div class="n">{counts.get('high', 0)}</div><div class="l">高风险</div></div>
      <div class="kpi medium"><div class="n">{counts.get('medium', 0)}</div><div class="l">中风险</div></div>
      <div class="kpi low"><div class="n">{counts.get('low', 0)}</div><div class="l">低风险</div></div>
      <div class="kpi"><div class="n">{total}</div><div class="l">问题项</div></div>
    </div>
    <button class="btn" id="btn-split">双栏审阅</button>
    <button class="btn" id="btn-overview">总览</button>
    <button class="btn primary" id="btn-export">导出审阅清单</button>
    <button class="btn" id="btn-help">说明</button>
  </div>
</header>

<div class="filterbar" id="filterbar">
  <span class="filter-label">主题</span>
  <div id="chips" style="display:flex;gap:6px;flex-wrap:wrap"></div>
  <div class="vdiv"></div>
  <span class="filter-label">等级</span>
  <div id="sevchips" style="display:flex;gap:6px;flex-wrap:wrap"></div>
  <div class="vdiv"></div>
  <select id="statusfilter" class="searchbox" style="width:auto"></select>
  <div class="spacer"></div>
  <input id="search" class="searchbox" type="search" placeholder="搜索条款 / 关键词  ( / )">
  <button class="btn" id="btn-print" style="background:#fff;color:#4a5568;border-color:#e2e6ee">打印</button>
  <button class="btn" id="btn-export-json" style="background:#fff;color:#4a5568;border-color:#e2e6ee">导出状态</button>
</div>

<main id="view-split" class="split">
  <section class="pane pane-left">
    <div class="paper">
      <div class="contract-banner">{esc(parsed['banner'])}</div>
      <h2 class="contract-title">{esc(parsed['title'])}</h2>
      <p class="contract-subtitle">{esc(parsed['subtitle'])}</p>
      <table class="meta-table">{meta_rows}</table>
{body}
    </div>
  </section>

  <section class="pane pane-right">
    <div class="rp-head">
      <h2>风险提示与确认事项</h2>
      <span class="hint">点击条目定位原文 · 点击左侧橙色标记回看风险</span>
      <span class="rp-count" id="rp-count"></span>
    </div>
    <div id="cards"></div>
  </section>
</main>

<main id="view-overview" class="overview">
  <div class="ov-note">
    <strong>本报告为业务风险提醒，不构成法律意见。</strong>
    报告仅基于所提供合同文本及其附件作出，未核验交易对手资信、货物实际品质或印尼监管现状。
    所有法律适用结论（尤其涉及印尼法的部分）均须由具备中国法与印度尼西亚法执业资格的律师复核后方可用于谈判或争议处理。
  </div>
  <div class="ov-grid">
    <div class="ov-card"><h3>交易概况 / Parties &amp; Terms</h3><div id="ov-meta"></div></div>
    <div class="ov-card"><h3>风险等级分布</h3><div id="ov-sev"></div>
      <h3 style="margin-top:16px">按主题分布</h3><div id="ov-cat"></div></div>
    <div class="ov-card"><h3>使用说明</h3>
      <p style="font-size:12.6px;line-height:1.8;color:#374151;margin:0">
      1. <b>点击条款编号</b>可跳转到双栏视图中的对应条目。<br>
      2. <b>定位原文</b>按钮会高亮左侧合同对应段落。<br>
      3. 每条均可填写<b>负责人、处理状态与备注</b>，数据保存在本机浏览器。<br>
      4. <b>导出审阅清单</b>生成 CSV，可直接用 Excel 打开，作为与法务沟通的底稿。<br>
      5. 顶部筛选可按<b>主题、等级、处理状态</b>过滤；按 <b>/</b> 快速搜索。</p></div>
  </div>
  <div class="ov-card"><h3>问题清单总览</h3>
    <div class="table-wrap"><table class="mini-table" id="ov-table"></table></div>
  </div>
  <div class="disclaimer" style="margin-top:16px">
    <b>免责声明：</b>{esc(meta['disclaimer'])}
  </div>
</main>

<div class="modal-mask" id="modal-mask">
  <div class="modal">
    <div class="modal-head"><h3>使用说明与边界</h3></div>
    <div class="modal-body">
      <h4>这份报告是什么</h4>
      <p>把一份外贸销售/采购合同拆成“条款位置 → 风险说明 → 商务后果 → 待确认事项”的可核查清单，
      供外贸业务人员与法务沟通使用。每条风险都锚定到合同原文的具体条款，可点击定位。</p>
      <h4>这份报告不是什么</h4>
      <p>不是法律意见书。报告不替代律师对合同效力的判断，不对任何法律适用作出确定性结论，
      也未核验交易对手资信、货物实测品质或目的国监管现状。涉及印尼法的事项一律标注为待印尼律师确认。</p>
      <h4>操作</h4>
      <ul style="margin:0;padding-left:18px;line-height:1.9">
        <li><b>双栏审阅</b>：左原文、右风险；点击右侧“定位原文↓”高亮左侧条款。</li>
        <li><b>主题筛选</b>：付款 / 交付 / 质量 / 索赔 / 合规 / 争议解决 / 条款缺失。</li>
        <li><b>负责人 / 状态 / 备注</b>：自动保存在本机 localStorage，可“导出状态”备份。</li>
        <li><b>导出审阅清单</b>：CSV 文件，含原文引用与确认事项，供法务会签。</li>
      </ul>
      <h4>本样例的免责提示</h4>
      <div class="code">{esc(meta['disclaimer'])}</div>
    </div>
    <div class="modal-foot"><button class="btn-dark" id="modal-close">知道了</button></div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
window.__REVIEW__ = {json.dumps(payload, ensure_ascii=False)};
</script>
<script>
{js}
</script>
</body>
</html>
"""
    return html


SEVERITIES = [
    {"key": "high", "label": "高风险", "color": "#dc2626"},
    {"key": "medium", "label": "中风险", "color": "#d97706"},
    {"key": "low", "label": "低风险", "color": "#059669"},
]

CAT_ORDER = ["payment", "delivery", "quality", "claim", "compliance", "dispute", "missing"]
CAT_LABEL = {
    "payment": ("付款", "Payment", "#2563eb"),
    "delivery": ("交付与运输", "Delivery & Transport", "#0891b2"),
    "quality": ("质量与检验", "Quality & Inspection", "#7c3aed"),
    "claim": ("索赔与责任", "Claims & Liability", "#c2410c"),
    "compliance": ("合规与单证", "Compliance & Documents", "#b45309"),
    "dispute": ("争议解决与效力", "Dispute & Validity", "#be123c"),
    "missing": ("条款缺失", "Missing Clause", "#475569"),
}


def meta_categories(meta: dict, issues: list[dict]) -> list[dict]:
    present = {i["category"] for i in issues}
    out = []
    for key in CAT_ORDER:
        if key not in present:
            continue
        cn, en, color = CAT_LABEL[key]
        out.append({"key": key, "label": cn, "label_en": en, "color": color})
    return out


def _default_template_dir() -> Path:
    """Find report.css / report.js whether the skill is zipped flat or in a folder.

    Search order:
      1. <skill root>/templates            (packaged layout: scripts/ + templates/)
      2. <scripts dir>/template            (legacy layout)
      3. <skill root>/template
    """
    candidates = [
        HERE.parent / "templates",
        HERE / "template",
        HERE.parent / "template",
    ]
    for c in candidates:
        if (c / "report.css").is_file() and (c / "report.js").is_file():
            return c
    raise SystemExit(
        "could not locate report.css / report.js. Looked in:\n  "
        + "\n  ".join(str(c) for c in candidates)
        + "\nPass --template-dir explicitly if they live elsewhere."
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("parsed")
    ap.add_argument("meta")
    ap.add_argument("issues", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--template-dir", default=None,
                    help="directory holding report.css and report.js (auto-detected)")
    args = ap.parse_args()

    parsed = json.load(io.open(args.parsed, encoding="utf-8"))
    meta = json.load(io.open(args.meta, encoding="utf-8"))["meta"]
    issues = load_issues(args.issues)

    template_dir = Path(args.template_dir) if args.template_dir else _default_template_dir()
    html = build(parsed, meta, issues, template_dir)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"wrote {args.out} ({len(html):,} chars, {len(issues)} issues, templates from {template_dir})")


if __name__ == "__main__":
    main()
