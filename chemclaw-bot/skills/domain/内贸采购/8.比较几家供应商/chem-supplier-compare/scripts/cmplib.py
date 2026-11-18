# -*- coding: utf-8 -*-
"""cmplib — 化工供应商横向比较的公共模型与工具（仅依赖 Python 标准库）。

职责：
  1. 读入 data.json，做规范化（供应商、维度、证据、报价）；
  2. 计算"真正差异"：同一单元格里出现的差异标记 → 维度级差异说明；
  3. 提供 HTML / XLSX 两个渲染器共用的文案、颜色与单元格解析。

数据契约见 references/data-contract.md。
"""
import datetime
import html
import json
import re

# ---------------------------------------------------------------------------
# 证据标签：整个 skill 的证据体系只有这 5 类，任何一行内容都必须能归入其中一类
# ---------------------------------------------------------------------------
LABELS = {
    "V": {"cn": "已核实", "color": "green",
          "desc": "有一手文件直接支撑（上市公司公告/年报、环评公示、法院文书、政府许可公示）"},
    "S": {"cn": "企业自述", "color": "amber",
          "desc": "来自企业官网、宣传资料、行业会议发言，未经验证"},
    "M": {"cn": "媒体/第三方", "color": "blue",
          "desc": "主流媒体报道或第三方数据库，可参考但不等于核实"},
    "U": {"cn": "无法核实", "color": "gray",
          "desc": "公开渠道未取得，不等于不存在；须供应商提供材料或现场确认"},
    "X": {"cn": "风险事实", "color": "red",
          "desc": "已发生的负面事实（诉讼、处罚、事故、法律、经营异常等），附出处"},
}
LABEL_ORDER = ["V", "S", "M", "U", "X"]

LEVELS = {
    "high": {"cn": "高", "color": "red"},
    "mid": {"cn": "中", "color": "amber"},
    "low": {"cn": "低", "color": "green"},
    "none": {"cn": "无", "color": "gray"},
}

STATUS = {
    "confirmed": {"cn": "已确认", "color": "green"},
    "quoted": {"cn": "报价待核", "color": "blue"},
    "pending": {"cn": "待确认", "color": "amber"},
    "missing": {"cn": "未提供", "color": "gray"},
    "risk": {"cn": "有风险", "color": "red"},
}

PRODUCER = {
    "producer": {"cn": "生产厂家", "color": "green"},
    "doubt": {"cn": "厂家身份存疑", "color": "amber"},
    "trader": {"cn": "贸易/代理", "color": "blue"},
    "unknown": {"cn": "身份待核", "color": "gray"},
}

# 维度类型 → 中文名（用于 Excel 页签、HTML 分组）
DIM_KIND = {
    "producer": "厂家身份与核验",
    "location": "生产基地与运距",
    "capacity": "产能与生产规模",
    "match": "主营匹配度",
    "licence": "经营资质与许可",
    "risk": "经营与司法风险",
    "event": "近期负面事件",
    "terms": "商业条款",
    "custom": "自定义维度",
    "evidence": "证据完整度",
}

DEFAULT_DIMENSIONS = ["producer", "location", "capacity", "match", "licence", "risk", "event", "terms"]


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def esc(value):
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def frag(text):
    """富文本：空行分段；<b> <span class="muted"> <br> <a> 原样保留（写入前由作者负责安全）。"""
    if text is None:
        return ""
    parts = [p.strip() for p in str(text).split("\n\n") if p.strip()]
    if len(parts) <= 1:
        return (parts[0] if parts else "").replace("\n", "<br>")
    return parts[0].replace("\n", "<br>") + "".join(
        "<p>" + p.replace("\n", "<br>") + "</p>" for p in parts[1:])


def parse_date(value, default=None):
    if not value:
        return default
    if isinstance(value, datetime.date):
        return value
    s = str(value).strip().replace("-", ".").replace("/", ".").replace("年", ".").replace("月", ".").replace("日", "")
    for fmt in ("%Y.%m.%d", "%Y.%m", "%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return default


def split_evidence(raw):
    """把证据单元格拆成 [(label, [evid...], note)]，允许一行有多个证据簇。

    语法：`V:E01,E02|...原文摘录`  或  `V|...摘录`（无证据 ID，仅标签）
    多个簇用 ` ;; ` 分隔。
    """
    if isinstance(raw, list):
        clusters = raw
    else:
        clusters = [c for c in re.split(r"\s*;;\s*", str(raw or "")) if c.strip()]
    out = []
    for c in clusters:
        c = c.strip()
        m = re.match(r"^([VS MUX])\s*[:：]?\s*([Ee]\d[\d,\s/、]*)?\s*\|?\s*(.*)$", c, re.S) or \
            re.match(r"^([VSMUX])\s*[:：]?\s*([Ee]\d[\d,\s/、]*)?\s*\|?\s*(.*)$", c, re.S)
        if not m:
            out.append(("U", [], c))
            continue
        label = m.group(1)
        ids = re.findall(r"[Ee]\d+", m.group(2) or "")
        note = (m.group(3) or "").strip()
        out.append((label, [i.upper().replace("E", "E") for i in ids], note))
    return out


def cell_labels(raw):
    return sorted({lb for lb, _, _ in split_evidence(raw)}, key=LABEL_ORDER.index)


def num(value, digits=None):
    """数字格式化：1234567 -> 1,234,567；带单位字符串原样返回。"""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value if value is not None else "")
    if digits is None:
        digits = 0 if abs(f - round(f)) < 1e-9 else 2
    return ("{:,.%df}" % digits).format(f)


def cert_state(end, as_of):
    d = parse_date(end)
    if d is None or as_of is None:
        return "待核定", "soon"
    if d < as_of:
        return "已到期", "expired"
    days = (d - as_of).days
    if days <= 180:
        return "%d 天后到期" % days, "soon"
    return "有效", "valid"


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------
class Cmp:
    def __init__(self, data):
        self.d = data
        self.meta = data.get("meta", {})
        self.as_of = parse_date(self.meta.get("as_of"))
        self.ev = {e["id"].upper(): e for e in data.get("evidence", [])}
        self.suppliers = data.get("suppliers", [])
        self.dims = data.get("dimensions") or self._default_dims()
        self.warnings = []
        if len(self.suppliers) < 2:
            self.warnings.append("比较对象少于 2 家，横向比较无意义")
        if len(self.suppliers) > 5:
            self.warnings.append("比较对象超过 5 家，表格可读性会下降，建议分批比较")
        self.terms = data.get("terms") or self._default_terms()
        self.req = data.get("procurement", {})
        self.quotes = data.get("quotes") or {}
        self.intel = data.get("intel") or []
        self.intel_reach = data.get("intel_reach") or {}
        self.questions = data.get("questions") or {}
        self.findings = data.get("findings") or []
        self.actions = data.get("next_actions") or []
        self.ratings = data.get("ratings") or {}
        self._index()

    # ---------- 数据规范化 ----------
    def _default_dims(self):
        dims = []
        for i, k in enumerate(DEFAULT_DIMENSIONS):
            dims.append({"key": k, "type": k, "label": DIM_KIND[k], "weight": 1})
        return dims

    def _default_terms(self):
        keys = ["price", "tax", "freight", "package", "payment", "delivery", "moq", "validity"]
        cn = {"price": "含税单价", "tax": "含税口径", "freight": "运费承担", "package": "包装",
              "payment": "账期", "delivery": "交期", "moq": "最小起订量", "validity": "报价有效期"}
        return [{"key": k, "label": cn[k]} for k in keys]

    def _index(self):
        # 维度单元格：cells[dim_key][supplier_id] = {"v": 文本, "lvl": 分级, "ev": 证据}
        self.cells = {}
        self.labels = {}
        for dim in self.dims:
            k = dim["key"]
            self.cells[k] = {}
            for s in self.suppliers:
                raw = (s.get("dims") or {}).get(k) or {}
                if isinstance(raw, str):
                    raw = {"v": raw}
                self.cells[k][s["id"]] = {
                    "v": raw.get("v", ""),
                    "lvl": raw.get("lvl", ""),
                    "note": raw.get("note", ""),
                    "ev": raw.get("ev", ""),
                }
                lb = cell_labels(raw.get("ev", ""))
                if raw.get("lvl") == "high" and "X" not in lb:
                    lb = sorted(set(lb + ["X"]), key=LABEL_ORDER.index)
                self.labels[(k, s["id"])] = lb
        # 商业条款单元格
        self.term_cells = {}
        for t in self.terms:
            self.term_cells[t["key"]] = {}
            for s in self.suppliers:
                q = (s.get("quote") or {})
                raw = q.get(t["key"]) or {}
                if isinstance(raw, (int, float)):
                    raw = {"v": raw}
                if isinstance(raw, str):
                    raw = {"v": raw}
                st = raw.get("status") or ("pending" if not raw else "quoted")
                self.term_cells[t["key"]][s["id"]] = {
                    "v": raw.get("v", ""),
                    "status": st,
                    "unit": raw.get("unit", ""),
                    "note": raw.get("note", ""),
                    "ev": raw.get("ev", ""),
                }
        # 全量许可/资质
        self.certs = []
        for s in self.suppliers:
            for c in s.get("certs") or []:
                c = dict(c)
                c["sid"] = s["id"]
                self.certs.append(c)
        # 问题清单统一编号（若未给）
        self.q_all = []
        for s in self.suppliers:
            qs = self.questions.get(s["id"]) or []
            for i, q in enumerate(qs):
                q = dict(q)
                q["sid"] = s["id"]
                q.setdefault("no", "%s-Q%02d" % (s["id"], i + 1))
                q.setdefault("priority", "中")
                q.setdefault("dim", "")
                self.q_all.append(q)

    # ---------- 查询 ----------
    def supplier(self, sid):
        for s in self.suppliers:
            if s["id"] == sid:
                return s
        return {"id": sid, "name": sid, "short": sid}

    def sname(self, sid):
        s = self.supplier(sid)
        return s.get("short") or s.get("name") or sid

    def evchips(self, ids, chip="ev"):
        out = []
        for i in ids or []:
            i = str(i).upper()
            e = self.ev.get(i)
            if not e:
                out.append('<span class="ev evmiss" title="证据索引缺少 %s">%s</span>' % (esc(i), esc(i)))
                continue
            out.append('<a class="%s" href="%s" target="_blank" rel="noopener" '
                       'title="%s · %s">%s</a>' % (chip, esc(e.get("url", "#")), esc(e.get("name", "")),
                                                    esc(e.get("source", "")), esc(i)))
        return '<span class="evs">' + "".join(out) + "</span>" if out else ""

    # ---------- 差异分析 ----------
    def dim_diff(self, dim_key):
        """返回该维度下"真正不同"的点：值相同/标签相同即视为无差异。"""
        dim = next((d for d in self.dims if d["key"] == dim_key), None)
        type_ = dim.get("type") if dim else "custom"
        groups = {}
        for s in self.suppliers:
            c = self.cells[dim_key][s["id"]]
            sig = self._signature(type_, c, self.labels[(dim_key, s["id"])])
            groups.setdefault(sig, []).append(s["id"])
        if len(groups) <= 1:
            return {"differ": False, "values": [], "groups": [list(groups.values())[0]] if groups else []}
        vals = []
        for sig, sids in groups.items():
            c = self.cells[dim_key][sids[0]]
            vals.append({"sids": sids, "v": c["v"], "lvl": c["lvl"]})
        return {"differ": True, "values": vals, "groups": list(groups.values())}

    def _signature(self, type_, cell, labels):
        v = re.sub(r"<[^>]+>", "", str(cell.get("v", "")))
        v = re.sub(r"\s+", " ", v).strip()
        if type_ in ("risk", "event"):
            return "L:" + cell.get("lvl", "")
        if type_ == "licence":
            # 许可维度：以“公开可查的许可条数”为签名，0 条即无法核实
            n = len(re.findall(r"\d{4}", v))
            return "LIC:%d" % (0 if (n == 0 or "未取得" in v or "待索取" in v) else n)
        if type_ == "terms":
            return "T:" + str(cell.get("status", "pending"))
        if cell.get("lvl"):
            return "L:" + cell.get("lvl")
        if not v or v in ("—", "-", "待确认"):
            return "EMPTY"
        return "V:" + v

    def dimension_summary(self):
        rows = []
        for dim in self.dims:
            d = self.dim_diff(dim["key"])
            rows.append({"dim": dim, "differ": d["differ"], "groups": d.get("groups", [])})
        return rows

    def report_labels(self):
        """全报告的证据标签计数（含风险与事件）。"""
        cnt = {k: 0 for k in LABEL_ORDER}
        for (k, sid), lb in self.labels.items():
            for x in lb:
                cnt[x] += 1
        for q in self.term_cells.values():
            for c in q.values():
                if c.get("status") == "pending":
                    cnt["U"] += 1
        return cnt

    def evidence_count(self, sid):
        ids = set()
        for dim in self.dims:
            for i in re.findall(r"[Ee]\d+", str(self.cells[dim["key"]][sid].get("ev", ""))):
                ids.add(i.upper())
        s = self.supplier(sid)
        for i in re.findall(r"[Ee]\d+", json.dumps(s, ensure_ascii=False)):
            ids.add(i.upper())
        return len([i for i in ids if i in self.ev])

    def producer_of(self, sid):
        s = self.supplier(sid)
        return s.get("producer", "unknown")

    def day_gap(self):
        if not self.as_of:
            return None
        return (datetime.date.today() - self.as_of).days
