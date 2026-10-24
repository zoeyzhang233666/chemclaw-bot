#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_dataset.py —— chain-data.json 数据契约校验（生成 HTML 之前运行）

它只做一件事：把「不允许出现的数据错误」拦在画图之前。规则来自价格类研究的硬约束：

  1. 必须有数据日（YYYY-MM-DD）与价格单位；缺单位不得画价格图。
  2. 有价环节（role=material）必须带至少一条原始报价记录，图上数字必须能在记录里找到。
  3. 缺值不当零：「0」视为非法价格（除非显式写成 missing）。
  4. 无货/无报价必须显式标记，不能写成 0 或空白。
  5. 下游应用环节（role=application）不得填价格，且必须在 gaps 里登记。
  6. 连线两端必须存在，不允许自环。
  7. 原始记录里的占位地区（如「地区」「——」）不得当真实地区使用。

用法
  python validate_dataset.py chain-data.json
退出码 0 = 通过（可能有警告）；1 = 存在错误。
"""

import json
import re
import sys

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")
PLACEHOLDER_REGION = {"地区", "—", "——", "-", "", "未知", "未提供"}
MISSING_WORDS = ("无货", "暂无", "缺货", "无报盘", "未提供", "无价格", "停报", "无报价", "暂缺")
ZERO_RE = re.compile(r"^[0０](?:\.0+)?$")

errors = []
warnings = []
infos = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def info(msg):
    infos.append(msg)


def check_rows(kind, owner, rows, meta_unit):
    """校验一组报价行；返回价格字符串集合。"""
    prices = set()
    seen = {}
    if not isinstance(rows, list) or not rows:
        err("%s [%s]：没有任何原始报价记录（有价环节必须逐条给出来源记录）" % (kind, owner))
        return prices
    for i, r in enumerate(rows):
        where = "%s [%s] 第 %d 行" % (kind, owner, i + 1)
        if not isinstance(r, dict):
            err("%s：不是对象" % where)
            continue
        price = str(r.get("price", "")).strip()
        if not price:
            err("%s：price 为空。缺值请留空并写明原因，不要用 0 代替" % where)
            continue
        prices.add(price)
        if ZERO_RE.match(price) and not r.get("missing"):
            err("%s：price=%s 形同缺值当零。要么给真实价格，要么标 \"missing\": true 并写清原因"
                % (where, price))
        if any(w in price for w in MISSING_WORDS) and not r.get("missing"):
            warn("%s：price=「%s」看起来是无报价状态，建议补 \"missing\": true，避免被当成价格参与比较"
                 % (where, price))
        unit = r.get("unit")
        if unit and meta_unit and unit != meta_unit:
            err("%s：行单位「%s」与 meta.unit「%s」不一致；不同单位不可混在一张图里"
                % (where, unit, meta_unit))
        region = str(r.get("region", "")).strip()
        if region in PLACEHOLDER_REGION:
            warn("%s：region=「%s」是占位值，展示时应写「未标注 / 未细分地区」，不得当作真实地区"
                 % (where, region))
        date = r.get("date")
        if date and not DATE_RE.match(str(date)):
            err("%s：date「%s」不是 YYYY-MM-DD" % (where, date))
        if not r.get("source"):
            warn("%s：没有 source，报告里无法说明数字从哪来" % where)
        key = (region, str(r.get("spec", "")), price, str(date or ""))
        if key in seen:
            warn("%s：与第 %d 行完全重复（同地区/同规格/同价/同日），建议去重或注明多来源同值"
                 % (where, seen[key]))
        else:
            seen[key] = i + 1
    return prices


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("meta") or {}
    unit = meta.get("unit", "")
    date = meta.get("data_date", "")
    if not meta.get("title"):
        err("meta.title 缺失")
    if not date:
        err("meta.data_date 缺失：没有数据日就无法说明「最新价」是哪一天")
    elif not DATE_RE.match(str(date)):
        err("meta.data_date「%s」不是 YYYY-MM-DD" % date)
    if not unit:
        err("meta.unit 缺失：缺单位不得画价格图")
    if not (meta.get("sources") or []):
        err("meta.sources 为空：必须说明价格来源")
    if not meta.get("headline"):
        warn("meta.headline 缺失：建议写一句核心结论")

    stages = data.get("stages") or []
    if not stages:
        err("stages 为空")
    stage_keys = [s.get("key") for s in stages]
    if len(stage_keys) != len(set(stage_keys)):
        err("stages.key 有重复")
    for s in stages:
        if not s.get("label"):
            warn("stage「%s」没有 label" % s.get("key"))

    nodes = data.get("nodes") or []
    if not nodes:
        err("nodes 为空")
    ids = [n.get("id") for n in nodes]
    if len(ids) != len(set(ids)):
        err("nodes.id 有重复：%s" % [i for i in ids if ids.count(i) > 1])
    gap_scopes = " ".join(str(g.get("scope", "")) for g in data.get("gaps") or [])
    all_prices = set()

    for n in nodes:
        nid = str(n.get("id", ""))
        where = "node [%s]" % nid
        if not ID_RE.match(nid):
            err("%s：id 只允许字母数字下划线短横（1-40 位）" % where)
        if n.get("stage") not in stage_keys:
            err("%s：stage「%s」不在 stages 中" % (where, n.get("stage")))
        role = n.get("role", "material")
        if role not in ("material", "application"):
            err("%s：role「%s」非法（material / application）" % (where, role))
        if not n.get("name"):
            err("%s：缺 name" % where)

        if role == "material":
            price = str(n.get("price", "")).strip()
            if not price:
                err("%s：有价环节缺 price" % where)
            elif ZERO_RE.match(price):
                err("%s：price=0 形同缺值当零" % where)
            if not (n.get("unit") or unit):
                err("%s：既没有节点单位也没有 meta.unit" % where)
            if not n.get("basis"):
                warn("%s：缺 basis（地区/规格/提货方式口径），图上数字容易被误读" % where)
            prices = check_rows("报价行", nid, n.get("rows"), unit)
            all_prices |= prices
            if price and prices and price not in prices:
                warn("%s：图上标注价「%s」不在本环节原始记录中，请确认它是某条记录的代表值并写明挑选规则"
                     % (where, price))
            if n.get("gap_label"):
                warn("%s：material 环节不需要 gap_label" % where)
        else:
            if str(n.get("price", "")).strip():
                err("%s：下游应用环节不得直接标价格（本次是否取到价须由原始记录支撑）" % where)
            if n.get("rows"):
                err("%s：application 环节不应带报价行" % where)
            if not n.get("gap_label"):
                warn("%s：application 环节建议写 gap_label 说明为什么没有价格" % where)
            short = n.get("short") or []
            if not (1 <= len(short) <= 3):
                warn("%s：short 建议 1–3 行短句（当前 %d 行）" % (where, len(short)))
            name = str(n.get("name", ""))
            if gap_scopes and name and name not in gap_scopes:
                bare = re.sub(r"[（(][^）)]*[）)]", "", name)
                tokens = [t for t in re.split(r"[／/、,，\s]+", bare) if t]
                if not any(t and t in gap_scopes for t in tokens):
                    warn("%s：「%s」在 gaps 中没有对应条目，缺口清单可能漏登记" % (where, name))

    for lk in data.get("links") or []:
        if lk.get("from") not in ids:
            err("link from「%s」不存在" % lk.get("from"))
        if lk.get("to") not in ids:
            err("link to「%s」不存在" % lk.get("to"))
        if lk.get("from") == lk.get("to"):
            err("link 自环：%s" % lk.get("from"))
        if not lk.get("label"):
            warn("link [%s→%s] 没有 label，读者无法判断这是什么关系"
                 % (lk.get("from"), lk.get("to")))
        if lk.get("kind") not in (None, "solid", "dashed"):
            warn("link [%s→%s] kind 非法，应为 solid/dashed" % (lk.get("from"), lk.get("to")))

    for t in data.get("tables") or []:
        if not t.get("title"):
            err("tables 中有一组缺 title")
        check_rows("附加明细", t.get("title", "?"), t.get("rows"), unit)
        if not t.get("note"):
            warn("附加明细「%s」没有 note：口径说明很重要" % t.get("title"))

    for g in data.get("gaps") or []:
        if not g.get("scope"):
            err("gaps 中有条目缺 scope")
        if not g.get("reason"):
            warn("gaps「%s」缺 reason" % g.get("scope"))
        if not g.get("evidence"):
            info("gaps「%s」没有 evidence：建议附上「观测数为 0」之类原始依据" % g.get("scope"))

    # 输出
    print("数据集校验：%s" % path)
    print("  有价环节 %d 个 · 应用环节 %d 个 · 原始报价行 %d 条 · 验证到的价格字符串 %d 个"
          % (sum(1 for n in nodes if n.get("role", "material") == "material"),
             sum(1 for n in nodes if n.get("role") == "application"),
             sum(len(n.get("rows") or []) for n in nodes) +
             sum(len(t.get("rows") or []) for t in data.get("tables") or []),
             len(all_prices)))
    for m in infos:
        print("  [提示] %s" % m)
    for m in warnings:
        print("  [警告] %s" % m)
    for m in errors:
        print("  [错误] %s" % m)
    if errors:
        print("结果：不通过（%d 错误 / %d 警告）" % (len(errors), len(warnings)))
        return 1
    print("结果：通过（0 错误 / %d 警告）" % len(warnings))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
