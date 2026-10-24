# -*- coding: utf-8 -*-
"""内外价差 Skill —— 公共 IO 与校验工具（只依赖标准库）。

约定：
  * 输入统一是 JSON（research.json / data.json），不引入数据库、不联网；
  * 控制台统一 UTF-8 输出，避免 Windows GBK 控制台把中文打成乱码；
  * 所有检查器返回 (errors, warns)，由调用方决定退出码。
"""
import io
import json
import os
import sys
import datetime as dt

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)


# ------------------------------------------------------------------ 日志
def ok(msg):
    print("[ OK  ] " + msg)


def warn(msg):
    print("[WARN ] " + msg)


def err(msg):
    print("[FAIL] " + msg)


def die(msg, code=2):
    print("[FATAL] " + msg, file=sys.stderr)
    sys.exit(code)


# ------------------------------------------------------------------ IO
def load_json(path):
    with io.open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def dump_json(obj, path):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def read_text(path):
    with io.open(path, encoding="utf-8-sig") as f:
        return f.read()


def write_text(path, text):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def list_files(root, exts=None):
    out = []
    for base, _dirs, files in os.walk(root):
        for fn in files:
            if exts and os.path.splitext(fn)[1].lower() not in exts:
                continue
            out.append(os.path.join(base, fn))
    return sorted(out)


# ------------------------------------------------------------------ 日期
def parse_iso(s):
    """接受 2026-10-19 / 2026/10/19 / 20261019 / 2026年10月19日。"""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y年%m月%d日"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return dt.datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def is_business_day(d):
    return d.weekday() < 5


def next_business_day(d):
    d = d + dt.timedelta(days=1)
    while not is_business_day(d):
        d = d + dt.timedelta(days=1)
    return d


def days_between(a, b):
    da, db = parse_iso(a), parse_iso(b)
    if not da or not db:
        return None
    return (db - da).days


# ------------------------------------------------------------------ 数字
def num(v, default=None):
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def fmt(n, d=0):
    if n is None:
        return "—"
    return format(float(n), ",." + str(d) + "f")


def fmt_trim(n, maxd=2):
    if n is None:
        return "—"
    f = float(n)
    for d in range(maxd + 1):
        if abs(round(f, d) - f) < 1e-9:
            return format(round(f, d), ",." + str(d) + "f")
    return format(round(f, maxd), ",." + str(maxd) + "f")


def pct(n, d=2):
    if n is None:
        return "—"
    return ("+" if n > 0 else "") + ("%." + str(d) + "f%%") % n


# ------------------------------------------------------------------ data.json 结构
REQUIRED_TOP = [
    "meta",          # 品种、规格、口径、基准日、贸易术语包含项
    "params",        # 基准参数（与 HTML 交互面板、Excel 输入表一一对应）
    "cost",          # 基准成本四层
    "domestic",      # 国内可比价
    "gaps_table",    # 四口径价差
    "attribution",   # 本期 vs 对比期 归因
    "series",        # 历史序列
    "sensitivity",   # 敏感性
    "waterfall",     # 成本瀑布
    "scenarios",     # 场景对比（术语切换 / 市场隐含）
    "sources",       # 数据来源
    "gaps",          # 数据缺口
    "formulas",      # 公式清单
    "disclaimers",   # 边界声明
]

BANNED_WORDS = [
    "建议买入", "建议卖出", "抄底", "建仓", "止损", "必赚", "稳赚",
    "套利利润", "无风险套利", "买入指令", "卖出指令", "采购建议", "交易指令",
    "何时开仓", "该不该买", "该不该卖",
]


def check_data(data):
    """校验 data.json（assemble 产物）。返回 (errors, warns)。"""
    errors, warns = [], []
    if not isinstance(data, dict):
        return [("结构", "data.json 根节点必须是对象")], []
    for k in REQUIRED_TOP:
        if k not in data:
            errors.append(("结构", "缺少顶层字段: " + k))
    if errors:
        return errors, warns

    meta = data["meta"]
    for k in ("product", "spec", "quote_basis", "quote_region", "dom_region", "dom_basis",
              "base_date", "window", "hs_code", "currency"):
        if not meta.get(k):
            errors.append(("meta", "缺少关键字段: " + k))
    if meta.get("base_date") and not parse_iso(meta["base_date"]):
        errors.append(("meta", "base_date 不是合法日期: %s" % meta["base_date"]))

    c = data["cost"]
    for k in ("cif", "landed_cash", "cash_out", "vat_credit", "net_cash", "unit_net"):
        if c.get(k) is None:
            errors.append(("cost", "成本字段缺失: " + k))
    if c.get("cif") is not None and c.get("net_cash") is not None:
        if c["net_cash"] > c["landed_cash"] + 1e-6:
            errors.append(("cost", "net_cash 不应大于 landed_cash（扣完可抵扣税后只会更小）"))
        lc = (c["cif"] + (c.get("discharge") or 0) + (c.get("duty") or 0) + (c.get("other_tax") or 0)
              + (c.get("vat") or 0) + (c.get("inland_dest") or 0) + (c.get("unload") or 0))
        if abs(lc - c["landed_cash"]) > 1e-3:
            errors.append(("cost", "landed_cash 与分项加总不一致：%.4f vs %.4f" % (lc, c["landed_cash"])))
        nc = c["landed_cash"] - c["vat_credit"]
        if abs(nc - c["net_cash"]) > 1e-3:
            errors.append(("cost", "net_cash != landed_cash - vat_credit：%.4f vs %.4f" % (nc, c["net_cash"])))

    p = data["params"]
    inc = meta.get("term_includes")
    if inc:
        pairs = {"freight": "ocean_freight", "insurance": "insurance_rate_pct",
                 "inland_origin": "inland_origin", "export_clear": "export_clear",
                 "discharge": "discharge_fee", "inland_dest": "inland_dest"}
        for flag, key in pairs.items():
            val = num(p.get(key), 0) or 0
            if inc.get(flag) and val > 0:
                errors.append(("params", "重复计费风险：术语已含 %s，但参数 %s=%s" % (flag, key, val)))

    ser = data.get("series", {})
    rows = ser.get("rows", [])
    for row in rows:
        if row.get("frt_source") is None:
            warns.append(("series", "序列行 %s 缺少 frt_source 标注" % row.get("date")))
            break
    if not rows:
        warns.append(("series", "历史序列为空，报告将只出单点"))

    if not data.get("sensitivity", {}).get("items"):
        warns.append(("sensitivity", "敏感性矩阵为空"))
    if not data.get("gaps"):
        warns.append(("gaps", "gaps 为空：按本 Skill 规则，没有缺口本身就是异常，至少应写 1 条"))

    for word in BANNED_WORDS:
        found = find_text(data, word)
        if found:
            errors.append(("wording", "data.json 出现禁用表述「%s」（位置：%s）" % (word, found)))
    return errors, warns


def find_text(obj, word, path="root"):
    hits = find_text_all(obj, word, path)
    return hits[0][0] if hits else None


def find_text_all(obj, word, path="root"):
    """返回 [(路径, 命中所在的整段文本)]，用于否定语境判断。"""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += find_text_all(v, word, path + "." + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += find_text_all(v, word, path + "[%d]" % i)
    elif isinstance(obj, str):
        if word in obj:
            out.append((path, obj))
    return out


NEGATORS = ("不", "勿", "禁", "无", "避免", "并非", "没有", "未", "拒绝", "not", "never")


def is_negated(obj, word, path="root"):
    """兼容旧签名：obj 为文本列表或文档根时都可用。"""
    if isinstance(obj, (str, bytes)):
        return is_negated_texts([obj], word)
    hits = [t for _loc, t in find_text_all(obj, word, path)]
    return is_negated_texts(hits, word)


def is_negated_texts(texts, word):
    """判断所有命中是否都处于否定语境（如「不给出任何建仓指令」）。

    规则：命中位置向前 24 字内出现否定词，视为写作上的免责表述，不判违规；
    但若紧接其后又出现「建议/立即/即刻」等动作词，则仍判为违规。
    """
    if not texts:
        return False
    for text in texts:
        i = 0
        while True:
            idx = text.find(word, i)
            if idx < 0:
                break
            i = idx + len(word)
            before = text[max(0, idx - 24):idx]
            after = text[idx + len(word): idx + len(word) + 8]
            negated = any(n in before for n in NEGATORS) and not any(s in after for s in ("建议", "立即", "即刻"))
            if not negated:
                return False
    return True


def check_research(res):
    """校验研究母本 research.json。返回 (errors, warns)。"""
    errors, warns = [], []
    for k in ("meta", "overseas", "domestic", "cost_params", "sources", "gaps"):
        if k not in res:
            errors.append(("结构", "research.json 缺少字段: " + k))
    if errors:
        return errors, warns
    m = res["meta"]
    for k in ("product", "spec", "quote_basis", "quote_region", "dom_region",
              "dom_basis", "base_date", "window", "hs_code", "currency"):
        if not m.get(k):
            errors.append(("meta", "缺少: " + k))
    o = res["overseas"]
    if o.get("price") in (None, ""):
        errors.append(("overseas", "海外报价 price 缺失"))
    if (o.get("term") or "").upper() not in ("EXW", "FCA", "FOB", "CFR", "CIF", "DAP"):
        errors.append(("overseas", "贸易术语 term 不合法: %s" % o.get("term")))
    if not o.get("source"):
        warns.append(("overseas", "海外报价没有写 source，无法回溯"))
    d = res["domestic"]
    for k in ("price", "tax", "term", "region", "spec"):
        if d.get(k) in (None, ""):
            errors.append(("domestic", "国内价格字段缺失: " + k))
    for i, g in enumerate(res.get("gaps", [])):
        for k in ("item", "impact", "fix"):
            if not g.get(k):
                errors.append(("gaps", "第 %d 条缺口缺少 %s" % (i + 1, k)))
    return errors, warns


def report(result, title):
    errors, warns = result
    print("=" * 64)
    print(title)
    print("=" * 64)
    for scope, msg in errors:
        err("[%s] %s" % (scope, msg))
    for scope, msg in warns:
        warn("[%s] %s" % (scope, msg))
    print("-" * 64)
    print("错误 %d 条 / 警告 %d 条" % (len(errors), len(warns)))
    return len(errors)
