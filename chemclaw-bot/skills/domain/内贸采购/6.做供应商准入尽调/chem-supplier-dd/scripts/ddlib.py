"""ddlib — 供应商准入尽调底稿的公共渲染工具（仅依赖标准库）。

数据契约见 references/data-contract.md，可运行的完整示例见 examples/soda-ash/data.json。
HTML 与 XLSX 两个渲染器共用本模块的状态口径与文案格式化。
"""
import datetime
import html
import re

DEFAULT_STATUS = {
    "ok": {"label": "已核实", "color": "green", "desc": "有公开文件直接支撑"},
    "pub": {"label": "公开可查", "color": "blue", "desc": "公开渠道可查，非一手披露"},
    "none": {"label": "无公开信息", "color": "gray", "desc": "公开渠道未取得，不等于不存在"},
    "todo": {"label": "待核验", "color": "amber", "desc": "须供应商材料或现场确认"},
    "risk": {"label": "风险", "color": "red", "desc": "已识别的负面事实"},
}

LEVEL_TAG = {"high": "high", "mid": "mid", "low": "low"}
LEVEL_TEXT = {"high": "高风险", "mid": "中风险", "low": "低风险"}
STRENGTH_TEXT = {"strong": "强", "mid": "中", "weak": "弱"}
STRENGTH_X = {"weak": 1, "mid": 2, "strong": 3}
IMPACT_Y = {"high": 1, "mid": 2, "low": 3}

TAG_TONE = {
    "expired": "exp", "exp": "exp", "red": "exp",
    "soon": "soon", "amber": "soon",
    "valid": "ok", "ok": "ok", "green": "ok",
}
PRIORITY_CLASS = {"高": "h", "中": "m", "低": "l"}


def esc(value):
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def frag(text):
    """段落：用空行分段，其余内联 HTML（<b>、<span class="muted">）原样保留。"""
    if not text:
        return ""
    parts = [p.strip() for p in str(text).split("\n\n") if p.strip()]
    if len(parts) <= 1:
        return "".join(parts)
    return "".join(parts[:1]) + "".join(f"<p>{p}</p>" for p in parts[1:])


def parse_date(value, default=None):
    if not value:
        return default
    s = str(value).strip().replace("-", ".").replace("/", ".")
    for fmt in ("%Y.%m.%d", "%Y.%m", "%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return default


def cert_state(end, as_of):
    d = parse_date(end)
    if d is None or as_of is None:
        return "待核定", "soon"
    if d < as_of:
        return "已到期", "expired"
    days = (d - as_of).days
    if days <= 180:
        return f"{days} 天后到期", "soon"
    return "有效", "valid"


class Ctx:
    def __init__(self, data):
        self.d = data
        meta = data.get("meta", {})
        self.as_of = parse_date(meta.get("as_of"))
        self.status = {k: dict(v) for k, v in DEFAULT_STATUS.items()}
        for k, v in (data.get("status_defs") or {}).items():
            self.status.setdefault(k, {}).update(v)
        self.ev = {e["id"]: e for e in data.get("evidence", [])}
        self.risks = []
        for sec in data.get("sections", []):
            for b in sec.get("blocks", []):
                if b.get("type") == "risks":
                    self.risks.extend(b.get("items", []))

    # ---------------- 基础片段 ----------------
    def pill(self, key, label=None):
        st = self.status.get(key) or self.status["none"]
        return f'<span class="pill p-{st.get("color", "gray")}"><i></i>{esc(label or st.get("label", key))}</span>'

    def tag(self, value, tone):
        return f'<span class="tg tg-{TAG_TONE.get(tone, "ok")}">{esc(value)}</span>'

    def evchips(self, ids):
        if not ids:
            return ""
        if isinstance(ids, str):
            ids = [x for x in re.split(r"[/、,，\s]+", ids) if x]
        out = []
        for i in ids:
            i = str(i).strip()
            e = self.ev.get(i)
            if not e:
                continue
            out.append(f'<a class="ev" href="{esc(e.get("url", "#"))}" target="_blank" '
                       f'rel="noopener" title="{esc(e.get("name", ""))} · 点击打开原文">{esc(i)}</a>')
        return '<span class="evs">' + "".join(out) + "</span>" if out else ""


# ---------------- 复合组件（与原版底稿 DOM 完全一致） ----------------
def rows_html(ctx, items):
    out = []
    for it in items:
        st = it.get("state", "ok")
        note = f'<span class="sub">{esc(it["note"])}</span>' if it.get("note") else ""
        out.append(
            f'<div class="mrow" data-s="{esc(st)}"><div class="k">{esc(it.get("k"))}</div>'
            f'<div class="v">{frag(it.get("v"))}{note}</div>'
            f'<div class="s">{ctx.pill(st)}</div>'
            f'<div class="e">{ctx.evchips(it.get("evid"))}</div></div>')
    return '<div class="rows">' + "\n".join(out) + "</div>"


def score_html(items):
    out = []
    for it in items:
        c = {"ok": "", "amber": "a", "red": "r", "gray": "g"}.get(it.get("state", "ok"), "")
        val = it.get("value", 0)
        out.append(f'<div class="score"><span>{esc(it.get("name"))}</span>\n'
                   f'      <div class="bar"><i class="{c}" style="width:{val}%"></i></div>\n'
                   f'      <span class="v">{esc(val)}</span></div>')
    return "\n".join(out)


def risk_html(ctx, r):
    lv = r.get("level", "mid")
    chips = ctx.evchips(r.get("evid"))
    return f'''<div class="risk {lv}" data-s="risk">
      <div class="rh">
        <div class="rid">{esc(r.get("id"))}</div>
        <div><h3>{esc(r.get("title"))}</h3><div class="dm">{esc(r.get("dim"))} · 证据强度：{esc(STRENGTH_TEXT.get(r.get("strength"), r.get("strength", "中")))}</div></div>
        <div style="display:flex;gap:6px;align-items:center"><span class="lv lv-{lv}">{LEVEL_TEXT.get(lv, "中风险")}</span>{chips}</div>
      </div>
      <div class="rb">
        <div class="rblock"><div class="l">证据</div><div>{esc(r.get("fact"))}</div></div>
        <div class="rblock"><div class="l">采购影响</div><div>{esc(r.get("impact"))}</div></div>
        <div class="rblock hl"><div class="l">缓释动作</div><div>{esc(r.get("action"))}</div></div>
      </div></div>'''


def matrix_html(ctx, block):
    grid = {}
    for r in block.get("items") or ctx.risks:
        x = STRENGTH_X.get(r.get("strength"), 2)
        y = IMPACT_Y.get(r.get("impact_level") or r.get("impact") or "mid", 2)
        grid.setdefault((y, x), []).append(r)
    cells = []
    for y in (1, 2, 3):
        for x in (1, 2, 3):
            items = grid.get((y, x), [])
            tags = "".join(f'<span class="tag {i.get("level", "mid")}">{esc(i.get("id"))}</span>' for i in items)
            hl = " h" if (y == 1 and x == 3) else ""
            cells.append(f'<div class="cell{hl}">{tags}<span class="cn">{y}{x}</span></div>')
    left = block.get("ylabel", "采购影响（高 → 低）")
    axis = block.get("axis") or ["证据弱", "证据中", "证据强"]
    xl = "".join(f"<span>{esc(a)}</span>" for a in axis)
    return f'''<div class="mx">
      <div class="yl">{esc(left)}</div>
      <div><div class="grid">{''.join(cells)}</div>
      <div class="xl" style="margin-left:0">{xl}</div></div>
    </div>'''


def checklist_html(items, kind):
    out = []
    for it in items:
        code = it.get("code", "")
        pr = it.get("priority", "中")
        prc = PRIORITY_CLASS.get(pr, "m")
        pr_label = f"{pr}优先" if kind == "mat" else pr
        if kind == "mat":
            head = f'{esc(it.get("category", ""))} · ' if it.get("category") else ""
            out.append(f'''<label class="ci"><input type="checkbox">
              <div><div class="ct"><span class="cid">{esc(code)}</span> {esc(it.get("name"))}
              <span class="pr pr-{prc}">{pr_label}</span></div>
              <div class="cm">{head}{esc(it.get("note", ""))}</div></div></label>''')
        else:
            area = f'{esc(it.get("area"))} · ' if it.get("area") else ""
            out.append(f'''<label class="ci"><input type="checkbox">
              <div><div class="ct"><span class="cid">{esc(code)}</span> {area}{esc(it.get("name"))}
              <span class="pr pr-{prc}">{pr_label}</span></div>
              <div class="cm">{esc(it.get("note", ""))}</div></div></label>''')
    return "\n".join(out)


def evidence_html(ctx):
    out = []
    for e in ctx.d.get("evidence", []):
        out.append(f'''<div class="evi" id="ev-{esc(e["id"])}" data-s="ok">
          <div class="eid">{esc(e["id"])}</div>
          <div><b>{esc(e.get("name"))}</b><span class="muted"> · {esc(e.get("source", ""))} · {esc(e.get("note", ""))}</span>
            <a class="u" href="{esc(e.get("url", "#"))}" target="_blank" rel="noopener">{esc(e.get("url", ""))}</a></div>
          <div class="dt">{esc(e.get("date", ""))}</div></div>''')
    return "\n".join(out)


def table_html(ctx, columns, rows, tag_cols=None, pill_cols=None, evid_cols=None, row_class=None):
    tag_cols, pill_cols, evid_cols = tag_cols or {}, pill_cols or {}, evid_cols or []
    head = []
    for col in columns:
        cls = ""
        if col.get("align") == "r":
            cls = ' class="r"'
        elif col.get("align") == "c":
            cls = ' class="c"'
        style = f' style="width:{col["width"]}"' if col.get("width") else ""
        head.append(f'<th{cls}{style}>{esc(col.get("h", ""))}</th>')
    body = []
    for row in rows:
        cls_attr = ""
        if row_class is not None:
            rc = row_class(row) if callable(row_class) else ""
            if rc:
                cls_attr = f' class="{rc}"'
        tds = []
        for idx, cell in enumerate(row):
            col = columns[idx] if idx < len(columns) else {}
            a = col.get("align")
            c = ' class="r mono"' if a == "r" else (' class="c"' if a == "c" else "")
            if idx in tag_cols:
                tone = tag_cols[idx].get(str(cell), "ok")
                tds.append(f"<td{c}>{ctx.tag(cell, tone)}</td>")
            elif idx in pill_cols:
                tds.append(f"<td{c}>{ctx.pill(str(cell))}</td>")
            elif idx in evid_cols:
                tds.append(f"<td{c} class='c'>{ctx.evchips(cell)}</td>")
            else:
                tds.append(f"<td{c}>{esc(cell)}</td>")
        body.append(f"<tr{cls_attr}>" + "".join(tds) + "</tr>")
    return ('<div class="tblwrap"><table class="tbl"><thead><tr>' + "".join(head) +
            "</tr></thead><tbody>" + "\n".join(body) + "</tbody></table></div>")
