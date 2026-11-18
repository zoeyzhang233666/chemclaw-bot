# -*- coding: utf-8 -*-
"""batch_sourcing.actions — 由覆盖矩阵生成询价/资质核验清单、缺口清单、来源清单。"""
from __future__ import annotations


def _item_label(it):
    form = it.get("form") or ""
    return f"{it['name']}（{form}）" if form else it["name"]


def build_actions(project):
    calc = project["_calc"]
    items = {i["code"]: i for i in project["items"]}
    suppliers = {s["id"]: s for s in project["suppliers"]}
    actions, gaps, refs = [], [], []
    n = 0

    # ---------- 1) 按供应商打包的询价单
    for row in sorted(calc["supplier_rank"], key=lambda r: (-r["adv_current"], -r["current"])):
        sid = row["supplier_id"]
        s = suppliers[sid]
        lns = [l for l in project["links"] if l["supplier_id"] == sid and l["_deg"]["achievable"]]
        if not lns or row["achievable"] == 0:
            continue
        n += 1
        codes = [l["item_code"] for l in lns]
        acts = ["出具正式 RFQ（规格/数量/包装/交付点/账期/年用量）"]
        if any(l["coverage"] in ("partial_spec", "disclose") for l in lns):
            acts.append("对“待确认”项索取具体牌号 COA 与规格书，写清浓度/形态")
        if any("第" in (items[c].get("hazard") or "") for c in codes if c in items):
            acts.append("核验危险化学品生产/经营许可证范围、危险货物运输资质")
        if len(codes) > 1:
            acts.append("询问多料同框报价、合并发运与阶梯量价")
        if s["identity"] in ("S", "P", "G"):
            acts.append("确认签约主体（集团/子公司/销售公司）与授权书")
        actions.append({
            "id": f"Q-{n:02d}",
            "supplier_id": sid,
            "supplier": s["name"],
            "priority": "P0" if row["adv_current"] >= 2 else "P1",
            "items": codes,
            "actions": acts,
            "deadline": "T+7 工作日内回传",
        })

    # ---------- 2) 物料级缺口行动
    for gn, x in enumerate(calc["scarce"], start=1):
        it = items.get(x["item_code"], {})
        d = x["degree_adv"]
        if d == 0:
            gtype = "无厂家覆盖"
            act = ["补检索：排污许可证/环评批复/交易所交割名录/行业协会名录",
                   "仍无结果 → 询贸易商并索取原厂授权书 + 原厂 COA",
                   "仍无结果 → 评估替代牌号或进口，并在立项文件里写明"]
        elif d <= 2:
            gtype = "厂家单一"
            act = ["对该物料再补 1 家备选厂家", "确认可外售比例、最小起订量、季度锁量条款"]
        else:
            gtype = "规格/证据待补"
            act = ["向候选厂家索取 COA/规格书", "必要时第三方检测（铁含量/色度/水分等）"]
        if it.get("status") and it["status"] != "ok":
            act = [f"先解决该行歧义（status={it['status']}，见 02 表）"] + act
        gaps.append({"id": f"G-{gn:02d}", "item_code": x["item_code"], "item": _item_label(it),
                     "type": gtype, "severity": "P0" if d == 0 else "P1", "actions": act})

    # ---------- 3) 来源清单
    for ev in project["evidence"]:
        if ev.get("url"):
            refs.append({"id": ev["id"], "grade": ev["grade"], "org": ev["org"],
                         "title": ev["topic"], "date": ev.get("date", ""), "url": ev["url"]})
    refs.sort(key=lambda r: (r["grade"], r["id"]))
    return actions, gaps, refs
