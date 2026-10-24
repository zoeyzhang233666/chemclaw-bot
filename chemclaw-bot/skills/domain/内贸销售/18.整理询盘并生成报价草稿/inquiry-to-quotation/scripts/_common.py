# -*- coding: utf-8 -*-
"""询盘 → 报价草稿：共用契约与渲染（single source of truth）。

extract.py / build_quote.py / build_workbench.py / selfcheck.py 全部从这里取字段定义，
改字段只改这个文件，避免四处漂移。

三个不可谈判的约定写死在代码里：
1) 本模块从不产生单价。price 只接受"用户确认过的值"，空值就是空值。
2) 缺失字段一律 status=missing + value=""，不允许用行业惯例或假设顶替 must 字段。
3) assume 字段的默认值带 assumed_by 标记，渲染时必须显式写出"我方假设/待客户确认"。
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

# ---------------------------------------------------------------- 字段契约

BUCKET_LABEL = {"must": "必须补充后才能报价", "assume": "可先按假设准备"}

STATUS_LABEL = {
    "extracted": "已提取",
    "missing": "缺",
    "assumed": "我方假设",
    "tbc": "待客户确认",
    "user": "待你填写",
}

# (key, label, bucket, side, unit, hint, assume_default)
FIELD_SPEC: list[tuple[str, str, str, str, str, str, str | None]] = [
    ("product", "产品名称", "must", "customer", "", "重质纯碱 / 轻质纯碱 / SBS / 钛白粉…", None),
    ("grade", "规格 / 牌号", "must", "customer", "", "纯度、杂质、粒度、白度、熔指等内控指标", None),
    ("quantity", "数量", "must", "customer", "吨", "必须分清试单量 / 月用量 / 年用量", None),
    ("place", "交货地点", "must", "customer", "", "省市 + 厂区或仓库；“你们送过来”不算", None),
    ("customer", "客户名称", "must", "customer", "", "报价单抬头的开票主体全称", None),
    ("packaging", "包装", "assume", "customer", "", "吨包 / 25kg 袋 / 槽车 / 散装", "1000kg 吨包，栈板+缠膜"),
    ("delivery_date", "交期", "assume", "customer", "", "到厂日期，或款到后工作日", "款到后 5~7 个工作日到厂"),
    ("payment", "付款条件", "assume", "customer", "", "款到发货 / 月结 30 天 / 预付比例", "款到发货（电汇）"),
    ("incoterm", "运输方式", "assume", "customer", "", "汽运整车 / 铁路 / 水运 / 槽车", "汽运整车"),
    ("validity", "报价有效期", "assume", "user", "天", "默认 7 天；大宗随行就市可缩到 3 天", "7"),
]

FIELD_KEYS = [f[0] for f in FIELD_SPEC]
FIELD_LABEL = {f[0]: f[1] for f in FIELD_SPEC}
FIELD_BUCKET = {f[0]: f[2] for f in FIELD_SPEC}

# 用户侧口径（不可从询盘单向"提取"，必须由用户确认后生效）
GATE_SPEC = [
    ("tax_mode", "税费口径"),
    ("freight_mode", "运费口径"),
]

TAX_OPTIONS = [
    "含税（13% 增值税专用发票）",
    "含税（9% 增值税专用发票）",
    "含税（3% / 普票）",
    "不含税（税额另计）",
]

FREIGHT_OPTIONS = [
    "到厂价（含运费）",
    "出厂价（不含运费）",
    "送到站（含运费至指定站）",
]

CURRENCY_LABEL = "CNY"

# ---------------------------------------------------------------- 文档骨架


def today() -> str:
    return _dt.date.today().isoformat()


def _field_row(key: str) -> dict:
    for k, label, bucket, side, unit, hint, default in FIELD_SPEC:
        if k != key:
            continue
        return {
            "key": k,
            "label": label,
            "bucket": bucket,
            "bucket_label": BUCKET_LABEL[bucket],
            "side": side,
            "unit": unit,
            "hint": hint,
            "value": "",
            "status": "assumed" if bucket == "assume" else "missing",
            "confidence": "",
            "source": "",
            "note": "",
            "assume_default": default or "",
        }
    raise KeyError(key)


def new_doc(customer: str = "", inquiry_no: str = "", as_of: str = "") -> dict:
    """空文档：所有 must 字段都是 missing，assume 字段带默认假设但 status=assumed。"""
    fields = {}
    for key in FIELD_KEYS:
        row = _field_row(key)
        fields[key] = row
    return {
        "meta": {
            "inquiry_no": inquiry_no or auto_inquiry_no(),
            "as_of": as_of or today(),
            "customer": customer,
            "currency": CURRENCY_LABEL,
            "unit": "吨",
            "sources": [],
        },
        "fields": fields,
        "gate": {
            "tax_mode": {"value": "", "status": "user"},
            "freight_mode": {"value": "", "status": "user"},
        },
        "price": {
            "unit_price": None,
            "quote_quantity": None,
            "quote_quantity_unit": "吨",
            "validity_days": 7,
            "company": "",
            "contact": "",
            "quote_no": "",
            "ack": "",
            "confirmed_at": "",
            "currency": CURRENCY_LABEL,
        },
        "notes": [],
        "unreadable": [],
    }


def auto_inquiry_no(prefix: str = "INQ") -> str:
    return f"{prefix}-{_dt.date.today():%Y%m%d}-01"


# ---------------------------------------------------------------- 闸门判定


def must_rows(doc: dict) -> list[dict]:
    return [doc["fields"][k] for k in FIELD_KEYS if FIELD_BUCKET[k] == "must"]


def assume_rows(doc: dict) -> list[dict]:
    return [doc["fields"][k] for k in FIELD_KEYS if FIELD_BUCKET[k] == "assume"]


def _row_ready(row: dict) -> bool:
    """must 字段算不算"有了"。空值、待客户确认、我方假设都不算。"""
    if not str(row.get("value", "")).strip():
        return False
    return row.get("status") not in {"missing", "tbc"}


def blockers(doc: dict) -> list[str]:
    """返回阻塞"生成报价草稿"的全部原因（人话，可直接显示给用户）。"""
    out: list[str] = []
    for row in must_rows(doc):
        if not _row_ready(row):
            if not str(row.get("value", "")).strip():
                out.append(f"缺：{row['label']}")
            else:
                out.append(f"待确认：{row['label']}（当前标记为{STATUS_LABEL.get(row['status'], row['status'])}）")
    for key, label in GATE_SPEC:
        if not str(doc["gate"].get(key, {}).get("value", "")).strip():
            out.append(f"待你选择：{label}")
    price = doc.get("price", {})
    if not _positive(price.get("unit_price")):
        out.append("待你填写：确认单价")
    if not _positive(price.get("quote_quantity")):
        out.append("待你填写：报价数量")
    if not str(price.get("ack", "")).strip():
        out.append("待你勾选：确认该单价为我方销售价格")
    return out


def _positive(v) -> bool:
    try:
        return float(v) > 0
    except (TypeError, ValueError):
        return False


def price_ready(doc: dict) -> bool:
    return not blockers(doc)


# ---------------------------------------------------------------- 渲染


def money(v, digits: int = 2) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return ""
    return f"{x:,.{digits}f}"


def total(price: dict) -> dict:
    qty = float(price.get("quote_quantity") or 0)
    unit = float(price.get("unit_price") or 0)
    amount = qty * unit
    tax_mode = (price.get("tax_mode") or "").strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", tax_mode)
    rate = float(m.group(1)) / 100 if m else 0.0
    taxed = "不含税" not in tax_mode
    if taxed:
        net = amount / (1 + rate) if rate else amount
        tax = amount - net
    else:
        net = amount
        tax = amount * rate
    return {
        "qty": qty,
        "unit_price": unit,
        "amount": amount,
        "net": net,
        "tax": tax,
        "rate": rate,
        "taxed": taxed,
    }


def _value(row: dict) -> str:
    v = str(row.get("value", "")).strip()
    return v or "待客户确认"


def _tag(row: dict) -> str:
    st = row.get("status", "")
    if st == "assumed":
        return "（我方假设 · 待客户确认）"
    if st == "tbc":
        return "（待客户确认）"
    return ""


def _effective(row: dict) -> str:
    """assume 字段没填值时用默认假设。"""
    v = str(row.get("value", "")).strip()
    if v:
        return v
    return str(row.get("assume_default", "")).strip()


def build_context(doc: dict) -> dict:
    """把文档摊平成渲染用的上下文。"""
    price = dict(doc.get("price", {}))
    price["tax_mode"] = doc["gate"]["tax_mode"].get("value", "")
    price["freight_mode"] = doc["gate"]["freight_mode"].get("value", "")
    tot = total(price)
    f = doc["fields"]
    meta = doc["meta"]

    validity_days = price.get("validity_days") or 7
    try:
        validity_days = int(validity_days)
    except (TypeError, ValueError):
        validity_days = 7
    valid_until = ""
    try:
        valid_until = (_dt.date.fromisoformat(meta["as_of"]) + _dt.timedelta(days=validity_days)).isoformat()
    except (KeyError, ValueError):
        valid_until = ""

    pending = []
    for key in FIELD_KEYS:
        if key == "validity":
            continue
        row = f[key]
        if row.get("status") in {"missing", "tbc"} or not str(row.get("value", "")).strip():
            if FIELD_BUCKET[key] == "assume":
                pending.append(f"{row['label']}：按我方假设「{_effective(row)}」，请客户确认")
            else:
                pending.append(f"{row['label']}：待客户确认（询盘中未给出）")
    pending.append(f"报价有效期：本报价按 {validity_days} 天执行，请客户确认是否足够")
    pending.extend(doc.get("unreadable", []))

    return {
        "meta": meta,
        "fields": f,
        "gate": doc["gate"],
        "price": price,
        "totals": tot,
        "valid_days": validity_days,
        "valid_until": valid_until,
        "pending": pending,
        "product": _value(f["product"]),
        "grade": _value(f["grade"]),
        "quantity": _value(f["quantity"]),
        "place": _value(f["place"]),
        "customer": str(meta.get("customer") or _value(f["customer"])),
        "customer_contact": str(meta.get("customer_contact") or ""),
        "packaging": _effective(f["packaging"]) + _tag(f["packaging"]),
        "delivery_date": _effective(f["delivery_date"]) + _tag(f["delivery_date"]),
        "payment": _effective(f["payment"]) + _tag(f["payment"]),
        "incoterm": _effective(f["incoterm"]) + _tag(f["incoterm"]),
        "tax_mode": price["tax_mode"] or "待你确认",
        "freight_mode": price["freight_mode"] or "待你确认",
        "company": price.get("company") or "（我方公司抬头待填写）",
        "quote_no": price.get("quote_no") or auto_quote_no(meta.get("inquiry_no", "")),
        "quote_date": meta.get("as_of", ""),
    }


def auto_quote_no(inquiry_no: str = "") -> str:
    """INQ-20261020-01 → QT-20261020-01；认不出日期就退回当天。"""
    digits = re.sub(r"\D", "", inquiry_no or "")
    if len(digits) >= 8:
        date, tail = digits[:8], (digits[8:] or "01")
        return f"QT-{date}-{tail}"
    return f"QT-{_dt.date.today():%Y%m%d}-01"


def render_quote_md(doc: dict, template: str | None = None) -> str:
    """渲染 Markdown 报价草稿。单价只可能来自 doc['price']['unit_price']。"""
    if not price_ready(doc):
        raise ValueError("价格或口径未确认，拒绝渲染报价草稿：" + "；".join(blockers(doc)))
    ctx = build_context(doc)
    if template:
        return _render_template(template, ctx)

    p, t = ctx["price"], ctx["totals"]
    unit_price = money(p["unit_price"])
    tax_note = "含税单价" if t["taxed"] else "不含税单价"

    lines: list[str] = []
    A = lines.append
    if "演示" in str(p.get("ack", "")):
        A("> **DEMO 演示文件**：本报价使用演示输入价，仅用于展示版式；"
          "不是系统建议价、不是市场报价、不是成交价。正式报价请清空后填入销售确认价。")
        A("")
    A("# 报 价 单（草稿 · 待我方审阅后发出）")
    A("")
    A(f"- 报价单号：{ctx['quote_no']}")
    A(f"- 报价日期：{ctx['quote_date']}　　有效期至：{ctx['valid_until']}（{ctx['valid_days']} 天）")
    A(f"- 致：{ctx['customer']}" + (f"（{ctx['customer_contact']}）" if ctx["customer_contact"] else ""))
    A(f"- 我方：{ctx['company']}")
    A("")
    A("## 一、商品明细")
    A("")
    A("| 序号 | 产品 | 规格 / 牌号 | 数量 | 单位 | 单价（元） | 金额（元） | 备注 |")
    A("| --- | --- | --- | --- | --- | --- | --- | --- |")
    A(
        "| 1 | {p} | {g} | {q} | {u} | {up}（{tn}） | {amt}（{tn}） | 见条款二 |".format(
            p=ctx["product"],
            g=ctx["grade"],
            q=money(t["qty"], 0) if float(t["qty"]).is_integer() else money(t["qty"]),
            u=p.get("quote_quantity_unit") or doc["meta"].get("unit", "吨"),
            up=unit_price,
            tn=tax_note,
            amt=money(t["amount"]),
        )
    )
    A("")
    A(f"> 数量口径：{ctx['quantity']}。本次报价按 **{money(t['qty'])} 吨** 计算；"
      "正式合同以双方书面确认的数量为准，价格按本合同单价执行。")
    A("")
    A("## 二、价格与口径")
    A("")
    A(f"- **税费口径**：{ctx['tax_mode']}")
    A(f"- **运费口径**：{ctx['freight_mode']}")
    if t["taxed"]:
        A(f"- 价税构成：不含税金额 {money(t['net'])} 元 + 税额 {money(t['tax'])} 元"
          f"（税率 {t['rate']*100:.0f}%）= 价税合计 **{money(t['amount'])} 元**")
    else:
        A(f"- 价税构成：不含税金额 {money(t['net'])} 元；按 {t['rate']*100:.0f}% 计税额 {money(t['tax'])} 元，"
          f"价税合计 **{money(t['amount'] + t['tax'])} 元**")
    A("")
    A("## 三、交付条件")
    A("")
    A(f"- 交货地点：{ctx['place']}")
    A(f"- 运输方式：{ctx['incoterm']}")
    A(f"- 交期：{ctx['delivery_date']}")
    A(f"- 包装：{ctx['packaging']}")
    A("")
    A("## 四、付款条件")
    A("")
    A(f"- {ctx['payment']}")
    A("")
    A("## 五、质量与验收")
    A("")
    A(f"- 质量指标：按 {ctx['grade']} 执行，随货提供批批 COA。")
    A("- 验收：到货后按双方确认的指标验收；异议应在收货后 7 个工作日内书面提出。")
    A("")
    A("## 六、报价有效期")
    A("")
    A(f"- 本报价自 {ctx['quote_date']} 起 **{ctx['valid_days']} 天**内有效（至 {ctx['valid_until']}）。")
    A("- 逾期未确认的，价格与交期需重新确认；原材料大幅波动时我方有权提前书面通知调整。")
    A("")
    A("## 七、待客户确认事项")
    A("")
    if ctx["pending"]:
        for item in ctx["pending"]:
            A(f"- {item}")
    else:
        A("- 无")
    A("")
    A("## 八、备注")
    A("")
    A("- 本报价为草稿，未经我方销售负责人确认不得对外发送。")
    A("- 单价与口径由我方业务人员填写并确认；系统未生成、未推荐、未调整任何商业价格。")
    A("")
    A("---")
    A("")
    A(f"生成说明：单价 {unit_price} 元/{p.get('quote_quantity_unit') or '吨'} "
      f"由{'我方业务人员' if p.get('ack') else '（未确认）'}于 "
      f"{p.get('confirmed_at') or _dt.date.today().isoformat()} 确认；"
      "本文件为可审阅草稿，非最终对外报价。")
    return "\n".join(lines) + "\n"


def _render_template(template: str, ctx: dict) -> str:
    """公司模板占位符替换：未知占位符原样保留，方便用户自己发现漏改。"""
    flat = {
        "quote_no": ctx["quote_no"],
        "quote_date": ctx["quote_date"],
        "valid_until": ctx["valid_until"],
        "valid_days": str(ctx["valid_days"]),
        "customer": ctx["customer"],
        "customer_contact": ctx["customer_contact"],
        "company": ctx["company"],
        "product": ctx["product"],
        "grade": ctx["grade"],
        "quantity": ctx["quantity"],
        "qty": money(ctx["totals"]["qty"]),
        "qty_unit": ctx["price"].get("quote_quantity_unit") or "吨",
        "unit_price": money(ctx["price"]["unit_price"]),
        "amount": money(ctx["totals"]["amount"]),
        "net": money(ctx["totals"]["net"]),
        "tax": money(ctx["totals"]["tax"]),
        "tax_rate": f"{ctx['totals']['rate']*100:.0f}%",
        "tax_mode": ctx["tax_mode"],
        "freight_mode": ctx["freight_mode"],
        "place": ctx["place"],
        "packaging": ctx["packaging"],
        "delivery_date": ctx["delivery_date"],
        "payment": ctx["payment"],
        "incoterm": ctx["incoterm"],
        "pending": "\n".join(f"- {x}" for x in ctx["pending"]) or "- 无",
    }
    out = template
    for k, v in flat.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


# ---------------------------------------------------------------- IO


def load_doc(path: str | Path) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return normalize(doc)


def normalize(doc: dict) -> dict:
    """补齐缺字段，保证渲染不会 KeyError。"""
    base = new_doc()
    base["meta"].update({k: v for k, v in (doc.get("meta") or {}).items() if v is not None})
    for key in FIELD_KEYS:
        if key in (doc.get("fields") or {}):
            row = dict(base["fields"][key])
            row.update(doc["fields"][key])
            row["bucket"] = FIELD_BUCKET[key]
            row["bucket_label"] = BUCKET_LABEL[FIELD_BUCKET[key]]
            row["label"] = FIELD_LABEL[key]
            base["fields"][key] = row
    for key, _label in GATE_SPEC:
        if key in (doc.get("gate") or {}):
            base["gate"][key].update(doc["gate"][key])
    base["price"].update(doc.get("price") or {})
    base["notes"] = list(doc.get("notes") or base["notes"])
    base["unreadable"] = list(doc.get("unreadable") or base["unreadable"])
    return base


def save_doc(doc: dict, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(normalize(doc), ensure_ascii=False, indent=1), encoding="utf-8")
