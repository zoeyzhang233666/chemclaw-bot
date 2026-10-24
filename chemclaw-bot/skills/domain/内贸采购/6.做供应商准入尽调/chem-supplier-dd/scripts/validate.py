# -*- coding: utf-8 -*-
"""validate.py — 渲染前的数据契约自检。

    python validate.py <data.json>

检查项：
  1. 必填字段（meta / sections / evidence）
  2. 证据引用是否都能解析（evid 必须指向 evidence[].id）
  3. 状态词是否在允许集合内
  4. 风险条目字段是否完整
  5. 资质到期日是否能解析
  6. 正文是否出现“预测履约/交付概率”式表述（合规红线）
  7. 内联 HTML 标签是否成对

退出码：0 = 通过（可能带警告）；1 = 有 FAIL。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ddlib as L  # noqa: E402

REQUIRED_META = ["doc_no", "title", "target", "product", "as_of", "author", "reviewer"]
STATUS_OK = set(L.DEFAULT_STATUS)
RISK_FIELDS = ["id", "dim", "level", "strength", "title", "fact", "impact", "action"]

# 只允许出现在否定语境里的词（合规红线）
PREDICT_WORDS = ["履约概率", "交付概率", "违约概率", "预计交付率", "中标概率"]
NEGATIONS = ("不预测", "不给出", "不评估", "不代表", "不等于", "不构成", "不是", "并非", "无", "非", "不得")

fails, warns = [], []


def fail(msg):
    fails.append(msg)


def warn(msg):
    warns.append(msg)


def strip_html(text):
    return re.sub(r"<[^>]+>", "", str(text))


def check_html_balance(text, where):
    for tag in ("b", "i", "span", "p", "div"):
        opens = len(re.findall(rf"<{tag}(\s[^>]*)?>", text))
        closes = len(re.findall(rf"</{tag}>", text))
        if opens != closes:
            warn(f"{where}: <{tag}> 开闭不配对（{opens}/{closes}）")


def walk_blocks(data):
    for sec in data.get("sections", []):
        for b in sec.get("blocks", []):
            yield sec, b
            for card in b.get("cards", []) or []:
                yield sec, card


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    data = json.load(open(sys.argv[1], encoding="utf-8"))

    meta = data.get("meta", {})
    for k in REQUIRED_META:
        if not meta.get(k):
            fail(f"meta.{k} 缺失")
    if meta.get("as_of") and not L.parse_date(meta.get("as_of")):
        fail(f"meta.as_of 无法解析为日期：{meta.get('as_of')}")

    evid = {e.get("id") for e in data.get("evidence", []) if e.get("id")}
    if not evid:
        fail("evidence 为空：底稿至少需要 1 份一手证据")
    for e in data.get("evidence", []):
        if not str(e.get("url", "")).startswith("http"):
            warn(f"evidence {e.get('id')} 的 url 不是 http(s) 链接，原文将无法跳转")

    sections = data.get("sections", [])
    if len(sections) < 5:
        fail(f"只有 {len(sections)} 个模块，底稿结构不完整（建议 9–12 个）")
    ids = [s.get("id") for s in sections]
    if len(set(ids)) != len(ids):
        fail("section id 有重复")
    for s in sections:
        if not s.get("title"):
            fail(f"section {s.get('id')} 缺 title")
        if not s.get("blocks"):
            warn(f"section {s.get('id')} 没有任何区块")

    # 证据引用
    for sec, b in walk_blocks(data):
        for it in b.get("items", []) or []:
            ref = it.get("evid")
            if not ref:
                continue
            refs = ref if isinstance(ref, list) else re.split(r"[/、,，\s]+", str(ref))
            for one in refs:
                one = str(one).strip()
                if one and one not in ("todo", "无") and one not in evid:
                    fail(f"{sec.get('id')} 引用了不存在的证据 {one}")
        rows = b.get("rows") or []
        for row in rows:
            for cell in row if isinstance(row, list) else []:
                if isinstance(cell, str) and re.fullmatch(r"E\d{2}(/E\d{2})*", cell):
                    for one in cell.split("/"):
                        if one not in evid:
                            fail(f"{sec.get('id')} 表格引用了不存在的证据 {one}")
        if b.get("type") == "certs":
            for c in b.get("items", []):
                if not L.parse_date(c.get("end")):
                    warn(f"资质 {c.get('name')} 的到期日无法解析：{c.get('end')}")

    for c in data.get("certificates", []):
        if not L.parse_date(c.get("end")):
            warn(f"资质 {c.get('name')} 的到期日无法解析：{c.get('end')}")
        if not c.get("relevance"):
            warn(f"资质 {c.get('name')} 未标注相关性（core / related / irrelevant）")
        elif c.get("relevance") not in ("core", "related", "irrelevant"):
            fail(f"资质 {c.get('name')} 相关性取值非法：{c.get('relevance')}")

    # 状态词
    for sec, b in walk_blocks(data):
        for it in b.get("items", []) or []:
            st = it.get("state")
            if st and st not in STATUS_OK:
                fail(f"{sec.get('id')} 出现未知状态 '{st}'，允许：{sorted(STATUS_OK)}")

    # 风险
    risks = []
    for sec, b in walk_blocks(data):
        if b.get("type") == "risks":
            risks.extend(b.get("items", []))
    for r in risks:
        for f in RISK_FIELDS:
            if not r.get(f):
                fail(f"风险 {r.get('id')} 缺字段 {f}")
        if r.get("level") not in ("high", "mid", "low"):
            fail(f"风险 {r.get('id')} 等级必须是 high/mid/low")
        if r.get("strength") not in ("strong", "mid", "weak"):
            fail(f"风险 {r.get('id')} 证据强度必须是 strong/mid/weak")
        if not r.get("evid"):
            fail(f"风险 {r.get('id')} 没有绑定证据 ID")
        if not r.get("impact_level"):
            warn(f"风险 {r.get('id')} 未给 impact_level，矩阵将默认放在“中”")
    if not risks:
        warn("没有任何风险条目：供应商尽调几乎不可能零风险，请复核是否漏查")

    # 清单
    for sec, b in walk_blocks(data):
        if b.get("type") == "checklist":
            if not b.get("items"):
                warn(f"{sec.get('id')} 的清单为空")
            for it in b.get("items", []):
                if not it.get("code") or not it.get("name"):
                    fail(f"{sec.get('id')} 清单条目缺 code 或 name：{it}")
                if it.get("priority") not in ("高", "中", "低"):
                    warn(f"{it.get('code')} 优先级建议用 高/中/低")

    # 合规红线：预测性表述
    texts = []

    def collect(obj):
        if isinstance(obj, str):
            texts.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                collect(v)
        elif isinstance(obj, list):
            for v in obj:
                collect(v)

    collect(data.get("sections", []))
    collect(meta)
    for t in texts:
        for w in PREDICT_WORDS:
            for m in re.finditer(w, t):
                left = t[max(0, m.start() - 24):m.start()]
                if not any(n in left for n in NEGATIONS):
                    fail(f"出现未加否定的预测性表述“{w}”：…{t[max(0, m.start()-20):m.start()+20]}…")

    for t in texts:
        if "<" in t and ">" in t:
            check_html_balance(t, "正文")

    print(f"data: {sys.argv[1]}")
    print(f"模块 {len(sections)} · 证据 {len(evid)} · 风险 {len(risks)} · "
          f"资质 {len(data.get('certificates', []))}")
    for m in warns:
        print("  WARN ", m)
    for m in fails:
        print("  FAIL ", m)
    if fails:
        print(f"\n未通过：{len(fails)} 项 FAIL / {len(warns)} 项 WARN")
        return 1
    print(f"\n通过：0 项 FAIL / {len(warns)} 项 WARN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
