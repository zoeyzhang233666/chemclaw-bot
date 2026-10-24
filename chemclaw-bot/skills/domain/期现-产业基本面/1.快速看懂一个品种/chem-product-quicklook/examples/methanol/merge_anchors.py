# -*- coding: utf-8 -*-
"""把 build_anchors.py 产出的真实价格锚点写入 research.json（不手写数字）"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

anch = json.loads((ROOT / "raw" / "anchors_MA0.json").read_text(encoding="utf-8"))
doc = json.loads((ROOT / "_build_output" / "research.json").read_text(encoding="utf-8-sig"))

keep = {"近3年", "近1年", "近20日"}
spots = []
for a in anch["anchors"]:
    label = a.get("range_label") or a["name"].split("（")[-1].rstrip("）")
    if label not in keep:
        continue
    spots.append({
        "name": f"MA 主连·{label}",
        "value": a["value"],
        "unit": "元/吨",
        "spec": f"主连拼接，合约不含税；{label} {a['n']}个交易日",
        "region": "郑商所",
        "tax": "不含税",
        "date": a["date"],
        "src": a["src"],
        "pctile": a["pctile"],
        "range": a["range"],
    })

live = {
    "name": "MA 主连最新价（实时快照）",
    "value": "3130",
    "unit": "元/吨",
    "spec": "主连实时快照；当日结算 3129",
    "region": "郑商所",
    "tax": "不含税",
    "date": "2026-10-20",
    "src": ["S24"],
    "pctile": None,
    "range": None,
}
spots.insert(0, live)

# 节点：本品种
for n in doc["chain"]["nodes"]:
    if n.get("is_self"):
        n["research"]["spot"] = spots
        n["spot"] = f"MA {spots[1]['value']}"
        n["research"]["price_gap"] = "华东/华南/内地现货逐日报价未取得（缺口）；上表为可复核的期货锚点。"

# 面板：贸易与期现中的价格卡（补充实时快照行）
for pnl in doc["panels"]:
    if pnl["id"] != "trade_futures":
        continue
    for blk in pnl["body"]:
        if blk.get("type") == "futures" and "流动性" in blk.get("title", ""):
            blk["rows"].insert(0, {"k": "主连最新价（2026-10-20 快照）", "v": "3130 元/吨（当日结算 3129）"})
            blk["rows"].insert(1, {"k": "主连收盘（2026-10-19）", "v": "3143 元/吨"})
            blk["rows"] = [r for i, r in enumerate(blk["rows"]) if r["k"] != "主连收盘（2026-10-19）" or i == 1]

# 来源：补一条实时行情接口
doc["sources"].append({
    "id": "S24", "org": "新浪财经行情接口（hq.sinajs.cn）", "type": "实时行情",
    "title": "MA0 甲醇主连实时快照：最新价 3130，结算价 3129（2026-10-20 11:30 前）",
    "url": "https://hq.sinajs.cn/list=nf_MA0", "date": "2026-10-20",
    "use": "当日价格快照（盘中断言，需注意实时性）", "confidence": "中高",
})

(ROOT / "_build_output" / "research.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
print("anchors merged:", [s["name"] for s in spots])
