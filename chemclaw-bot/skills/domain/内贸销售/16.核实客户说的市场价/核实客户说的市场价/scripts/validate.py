#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate.py — 校验 research.json 是否满足数据契约。

这份文件是「研究结果」与「渲染器」之间的契约。校验不过，就不该出报告，
因为缺一项口径，结论就可能错一个量级。

必填（缺失即失败）：
  meta.product / meta.region / meta.base_date / meta.spec
  customer.raw_text / customer.stated_price / customer.is_simulated
  spot[]  每条：date / spec / region / tax / delivery / low 或 high / source / url / conf
  history[] 每条：date / spec / region / tax / delivery / point / source
  calibers[] 每条：dim / customer / market / diff_flag
  questions[] 每条：q / priority / why
  gaps[] 每条：item / impact / fix
建议（缺失只警告）：
  facts / factors / regions / method_notes / comparison_modes / futures

额外规则：
  * 模拟客户消息必须带【模拟】字样，且 is_simulated=true
  * 客户所述价格不得被写进 spot（防止把客户数字当市场价）
  * 历史点日期不得晚于 base_date
  * 区间 low ≤ high

用法：
  python scripts/validate.py examples/01-xxx/research.json
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

TAX_OK = {"含税", "不含税", "未注明"}
DEL_OK = {"出厂", "送到", "库提", "未注明", "集港"}
PRI_OK = {"高", "中", "低"}
FLAG_OK = {"一致", "不一致", "信息缺失", "部分一致", "部分可比", "不可比"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("research_json")
    a = ap.parse_args()
    d = C.load_json(a.research_json)
    fail, warn = [], []
    name = os.path.basename(os.path.dirname(os.path.abspath(a.research_json)))

    def need(cond, msg):
        if not cond:
            fail.append(msg)

    def opt(cond, msg):
        if not cond:
            warn.append(msg)

    # ---- meta
    meta = d.get("meta") or {}
    for k in ("product", "region", "base_date", "spec"):
        need(meta.get(k), f"meta.{k} 缺失")
    base = meta.get("base_date") or ""

    # ---- customer
    cust = d.get("customer") or {}
    need(cust.get("raw_text"), "customer.raw_text 缺失")
    need(isinstance(cust.get("stated_price"), (int, float)), "customer.stated_price 必须是数字")
    need("is_simulated" in cust, "customer.is_simulated 缺失（必须显式声明是否模拟）")
    if cust.get("is_simulated"):
        need("模拟" in str(cust.get("raw_text", "")),
             "模拟客户消息的正文必须带「【模拟】」字样，避免被误当成真实行情")
        need(cust.get("simulation_disclaimer"), "模拟案例需要 customer.simulation_disclaimer 说明")
        raw = str(cust.get("raw_text", ""))
        num = str(int(cust.get("stated_price") or 0))
        need(num[:2] in raw.replace(",", ""), f"客户消息正文里应出现所述价格 {num}")

    # ---- spot
    spots = d.get("spot") or []
    need(len(spots) >= 1, "spot[] 为空：没有任何可比市场报价")
    for i, s in enumerate(spots):
        tag = f"spot[{i}]({s.get('id', '?')})"
        excluded = bool(s.get("exclude_reason"))
        for k in ("date", "spec", "region", "tax", "delivery", "source", "conf", "quote_type"):
            need(s.get(k), f"{tag}.{k} 缺失")
        need(s.get("low") is not None or s.get("high") is not None or s.get("point") is not None,
             f"{tag} 下沿/上沿/点价都为空")
        lo, hi = s.get("low"), s.get("high")
        if lo is not None and hi is not None:
            need(lo <= hi, f"{tag} low({lo}) > high({hi})")
        pt = s.get("point")
        if pt is not None:
            opt(str(s.get("point_note", "")).strip() != "" or (lo is not None and hi is not None),
                f"{tag} 是点价而非区间，建议用 point_note 说明「点价不可当区间用」")
        need(C.norm_tax(s.get("tax")) in TAX_OK, f"{tag}.tax 不规范：{s.get('tax')}")
        need(C.norm_delivery(s.get("delivery")) in DEL_OK, f"{tag}.delivery 不规范：{s.get('delivery')}")
        if s.get("date") and base:
            need(s["date"] <= base, f"{tag}.date {s['date']} 晚于基准日 {base}")
        # 被排除的条目（写在 exclude_reason 里的）本身就是「不合格样本」，
        # 没有 URL 是正常的——它存在的意义就是展示「这样的数据不能用」。
        if not excluded:
            need(str(s.get("url", "")).startswith("http"), f"{tag}.url 必须是可点击链接")
        # 防止把客户数字当市场价：只检查未被排除、会被当作主区间的条目
        if not excluded and cust.get("stated_price") is not None:
            cp = cust["stated_price"]
            vals = [v for v in (lo, hi, s.get("point")) if isinstance(v, (int, float))]
            if vals and all(abs(v - cp) < 1e-6 for v in vals):
                fail.append(f"{tag} 的价格与「客户所述价格」完全相同，疑似把客户说法当成了市场报价")

    # ---- 必须有一条 primary
    opt(any(s.get("primary") for s in spots), "没有标记 primary 的主报价条（建议指定一条同日同口径主报价）")

    # ---- history
    hist = d.get("history") or []
    opt(len(hist) >= 3, f"history[] 只有 {len(hist)} 个点，趋势与价格带可能不足")
    for i, h in enumerate(hist):
        tag = f"history[{i}]({h.get('date', '?')})"
        for k in ("date", "spec", "region", "tax", "delivery", "source"):
            need(h.get(k), f"{tag}.{k} 缺失")
        need(isinstance(h.get("point"), (int, float)), f"{tag}.point 必须是数字")
        lo, hi = h.get("low"), h.get("high")
        if lo is not None and hi is not None:
            need(lo <= hi, f"{tag} low > high")
            if isinstance(h.get("point"), (int, float)):
                opt(lo - 0.01 <= h["point"] <= hi + 0.01,
                    f"{tag}.point {h['point']} 不在区间 [{lo}, {hi}] 内，请核对是否取错点")
        if base:
            need(h["date"] <= base, f"{tag}.date 晚于基准日 {base}")
    if hist:
        dates = [h["date"] for h in hist]
        opt(dates == sorted(dates), "history[] 未按日期升序排列（图表与窗口计算依赖顺序）")

    # ---- calibers
    cal = d.get("calibers") or []
    opt(len(cal) >= 5, f"calibers[] 只有 {len(cal)} 个维度，建议覆盖规格/地区/税费/交付/数量/包装/账期/物流")
    for i, c in enumerate(cal):
        for k in ("dim", "customer", "market"):
            need(c.get(k), f"calibers[{i}].{k} 缺失")
        flag = c.get("diff_flag") or c.get("same")
        need(flag, f"calibers[{i}] 缺 diff_flag / same（是否一致）")
        need(flag in FLAG_OK or flag.startswith(tuple(FLAG_OK)),
             f"calibers[{i}] 一致性取值不规范：{flag}")
        # 「不一致（信息缺失）」这类写法要能从字面看出原因，以便渲染时高亮
        if "信息缺失" in flag and flag not in ("信息缺失",):
            opt(flag.startswith("信息缺失"),
                f"calibers[{i}] 若因客户未说明而无法判断，diff_flag 建议写成「信息缺失」，而不是「{flag}」")
        need(c.get("impact") and c.get("action"), f"calibers[{i}] 需要 impact 与 action（影响与动作）")

    # ---- questions
    qs = d.get("questions") or []
    opt(len(qs) >= 5, f"questions[] 只有 {len(qs)} 条，建议覆盖价格口径/来源/数量/账期/包装")
    for i, q in enumerate(qs):
        for k in ("q", "priority", "why"):
            need(q.get(k), f"questions[{i}].{k} 缺失")
        need(q.get("priority") in PRI_OK, f"questions[{i}].priority 不规范：{q.get('priority')}")
    opt(any(q.get("priority") == "高" for q in qs), "questions[] 没有「高」优先级问题")

    # ---- gaps
    gaps = d.get("gaps") or []
    opt(len(gaps) >= 1, "gaps[] 为空：真实研究几乎总有缺口，请显式写出")
    for i, g in enumerate(gaps):
        for k in ("item", "impact", "fix"):
            need(g.get(k), f"gaps[{i}].{k} 缺失")

    # ---- facts
    facts = d.get("facts") or []
    opt(len(facts) >= 3, f"facts[] 只有 {len(facts)} 条，沟通要点不足")
    for i, f in enumerate(facts):
        for k in ("text", "src", "date"):
            need(f.get(k), f"facts[{i}].{k} 缺失")

    # ---- regions
    for i, r_ in enumerate(d.get("regions") or []):
        for k in ("region", "low", "high", "date", "comparability"):
            need(r_.get(k) is not None, f"regions[{i}].{k} 缺失")

    # ---- 禁用表述：报告里不该出现「保证」「一定」「抄底」等承诺性词
    banned = ["保证", "一定能成交", "建议报底价", "最低成交价", "帮您拿下"]
    import json as _json
    blob = _json.dumps(d, ensure_ascii=False)
    for b in banned:
        need(b not in blob, f"研究数据里出现不该有的承诺性表述：「{b}」")

    print(f"== validate: {name}")
    for w in warn:
        print(f"   [warn] {w}")
    for f_ in fail:
        print(f"   [FAIL] {f_}")
    if not fail:
        print(f"   PASS  契约通过（spot {len(spots)} 条 / history {len(hist)} 点 / "
              f"calibers {len(cal)} 维 / questions {len(qs)} 条 / gaps {len(gaps)} 条）")
        return 0
    print(f"   共 {len(fail)} 项失败")
    return 1


if __name__ == "__main__":
    sys.exit(main())
