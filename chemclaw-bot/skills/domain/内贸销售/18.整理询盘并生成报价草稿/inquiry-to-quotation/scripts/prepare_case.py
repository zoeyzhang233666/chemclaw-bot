# -*- coding: utf-8 -*-
"""把纯碱案例的 fields.json 校正到 2026-10-19 版本，并生成演示用 fields_demo.json。

官方 fields.json 永远不含单价与口径；
fields_demo.json 只用于"销售已确认 1,180 元/吨"的版式演示，报价页会明确标注 DEMO。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

EX = Path(__file__).resolve().parent.parent / "examples" / "example-1-soda-ash-glass"
SRC = EX / "fields.json"


def main() -> int:
    doc = json.loads(SRC.read_text(encoding="utf-8"))
    doc["meta"].update({
        "inquiry_no": "INQ-20261019-01",
        "as_of": "2026-10-19",
        "customer": "江苏盐城华宇玻璃",
        "customer_contact": "王经理",
        "customer_email": "wangjian@huayuglass.com",
        "industry": "浮法玻璃",
        "case_disclaimer": "教学演示案例：客户、联系人、公司与交易均为虚构。",
        "sources": [
            {"id": "素材01", "type": "微信截图 OCR · 2026-10-18 至 10-19", "file": "input/微信截图_华宇玻璃.png", "chars": 286},
            {"id": "素材02", "type": "邮件 · 2026-10-19 14:32", "file": "input/询盘邮件_华宇玻璃.eml", "chars": 610},
            {"id": "素材03", "type": "客户需求表 · Excel / PDF 扫描件", "file": "input/客户需求表_华宇玻璃.xlsx", "chars": 420},
        ],
    })

    f = doc["fields"]
    f["product"].update({
        "value": "重质纯碱",
        "status": "extracted",
        "confidence": "高",
        "source": "素材02 · 主题：重质纯碱询价（华宇玻璃）——补充几点",
    })
    f["grade"].update({
        "value": "Na2CO3 ≥ 99.2%；Fe2O3 ≤ 0.003%；烧失量 ≤ 0.5%；180 目筛余 ≤ 5%",
        "status": "extracted",
        "confidence": "高",
        "source": "素材01 · 王经理：指标要求：Na2CO3 ≥ 99.2%，Fe2O3 ≤ 0.003%，烧失量 ≤ 0.5%，粒度 180 目筛余 ≤ 5%。",
    })
    f["quantity"].update({
        "value": "试单 200 吨；月用量约 800 吨",
        "status": "extracted",
        "confidence": "高",
        "source": "素材01 · 月用量大概 800 吨，先试单 200 吨看看稳定性。",
    })
    f["place"].update({
        "value": "江苏省盐城市亭湖区 华宇玻璃一期厂区",
        "status": "extracted",
        "confidence": "高",
        "source": "素材02 · 交货地点：江苏省盐城市亭湖区 华宇玻璃一期厂区（需提前一天预约卸车，厂区有地磅）。",
    })
    f["customer"].update({
        "value": "江苏盐城华宇玻璃",
        "status": "tbc",
        "confidence": "低",
        "note": "简称；开票主体全称、统一社会信用代码待客户提供营业执照/开票信息",
        "source": "素材02 · 江苏盐城华宇玻璃 采购部 王经理；开票抬头我让财务整理好发您。",
    })
    f["packaging"].update({
        "value": "1000kg 吨包；栈板 + 缠膜",
        "status": "extracted",
        "confidence": "高",
        "source": "素材02 · 包装请用 1000kg 吨包，栈板+缠膜，方便叉车卸货。",
    })
    f["delivery_date"].update({
        "value": "2026-10-31 前",
        "status": "extracted",
        "confidence": "中",
        "note": "客户原话“10 月底前”，按 10 月 31 日前理解；具体到货日需结合排产确认",
        "source": "素材02 · 试单希望 10 月底前到货；后续按月度计划滚动下单。",
    })
    f["payment"].update({
        "value": "",
        "status": "assumed",
        "confidence": "",
        "note": "询盘只要求“注明付款条件”，未给出客户条件；按我方默认假设，报价中须标“我方假设”",
        "source": "",
        "assume_default": "款到发货（电汇）",
    })
    f["incoterm"].update({
        "value": "",
        "status": "assumed",
        "confidence": "",
        "note": "客户要求送到厂区；运输组织方式未明确，按汽运整车假设",
        "source": "",
        "assume_default": "汽运整车",
    })
    f["validity"].update({
        "value": "",
        "status": "assumed",
        "confidence": "",
        "note": "客户要求注明有效期；纯碱随行就市，按 7 天假设",
        "source": "",
        "assume_default": "7",
    })

    doc["gate"]["tax_mode"].update({
        "value": "",
        "hint": "素材02：一般纳税人，需 13% 增值税专用发票 → 仅供提示，必须由我方点选确认",
    })
    doc["gate"]["freight_mode"].update({
        "value": "",
        "hint": "素材01/02：送到盐城厂区、预约卸车 → 倾向到厂价，但必须由我方点选确认",
    })

    doc["price"].update({
        "unit_price": None,
        "quote_quantity": 200.0,
        "quote_quantity_unit": "吨",
        "validity_days": 7,
        "company": "",
        "contact": "",
        "quote_no": "QT-20261019-01",
        "ack": "",
        "confirmed_at": "",
        "currency": "CNY",
    })
    doc["notes"] = [
        "客户提到上轮比价记录，最后一行“1?30”字迹不清；只作为客户价格敏感度线索，不进入我方单价。",
        "货币单位：人民币；数量单位：吨；价格口径：元/吨。",
        "本案例为教学演示，客户、联系人、公司与交易均为虚构。",
    ]
    doc["unreadable"] = [
        "素材01：手写比价表最后一行“1?30”被涂改/遮挡，无法确认是 1,130、1,230 还是 1,630；不猜，请客户补录或忽略。",
    ]

    # 官方版：无价格、无口径
    C.save_doc(doc, SRC)

    # 演示版：销售已确认 1,180 元/吨（仅用于展示版式，不是系统建议价）
    demo = json.loads(json.dumps(doc, ensure_ascii=False))
    demo["meta"]["customer"] = "江苏盐城华宇玻璃有限公司"
    demo["fields"]["customer"].update({
        "value": "江苏盐城华宇玻璃有限公司",
        "status": "extracted",
        "confidence": "中",
        "note": "演示用全称；真实报价前仍需客户提供营业执照/开票信息核对",
    })
    demo["fields"]["payment"].update({"value": "款到发货（电汇）", "status": "assumed"})
    demo["fields"]["incoterm"].update({"value": "汽运整车", "status": "assumed"})
    demo["fields"]["validity"].update({"value": "7", "status": "assumed"})
    demo["gate"]["tax_mode"]["value"] = "含税（13% 增值税专用发票）"
    demo["gate"]["freight_mode"]["value"] = "到厂价（含运费）"
    demo["price"].update({
        "unit_price": 1180.0,
        "quote_quantity": 200.0,
        "validity_days": 7,
        "company": "鲁盐化工（山东）有限公司",
        "contact": "内贸部 李经理  138****0000",
        "quote_no": "QT-20261019-01",
        "ack": "我确认该单价为我方销售价格（演示输入）",
        "confirmed_at": "2026-10-19",
    })
    demo["notes"].append("演示价 1,180 元/吨由演示者手动填入，仅用于展示报价版式；不是系统建议价，也不是成交价。")
    C.save_doc(demo, EX / "fields_demo.json")

    print(f"  ← {SRC}")
    print(f"  ← {EX / 'fields_demo.json'}")
    print("  官方版 blockers：" + ("无" if not C.blockers(doc) else "；".join(C.blockers(doc))))
    print("  演示版 blockers：" + ("无" if not C.blockers(demo) else "；".join(C.blockers(demo))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
