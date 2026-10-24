#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
new_case.py — 为一个新案例生成骨架（case_input.json + case_output.json），然后你只填证据。

用法：
    python new_case.py <国家中文> <ISO2> <产品中文> <产品缩写> <规格摘要> <输出目录>

示例：
    python new_case.py "越南" VNM "钛白粉" TiO2 "金红石型，TiO2 ≥ 93%" examples/C_vietnam_tio2
"""
import json, os, sys, datetime


def main():
    if len(sys.argv) < 7:
        print(__doc__)
        return 2
    country, iso2, product, abbr, spec, outdir = sys.argv[1:7]
    os.makedirs(outdir, exist_ok=True)
    today = datetime.date.today().isoformat()

    case_input = {
        "case_id": "OSM-%s-%s-%s" % (abbr, iso2, today.replace('-', '')),
        "country": {"zh": country, "en": "", "iso2": iso2},
        "destination": {"zh": "中国", "en": "China"},
        "product": {
            "name_zh": product, "name_en": "", "abbr": abbr, "cas": "",
            "hs_cn": "", "spec_summary": spec, "process_route": "",
            "packaging": "",
            "related_products_excluded": [],
        },
        "buyer_context": {
            "quantity": None, "only_actual_manufacturers": True,
            "certifications_needed": None, "packaging_needed": None,
            "destination_port": None,
        },
        "research_date": today,
        "notes": "",
    }

    case_output = {
        "meta": {
            "report_id": case_input["case_id"],
            "title": "%s %s实际生产企业核验调查报告" % (country, product),
            "subtitle": "海外候选生产商调查 · 制造证据分级 · 集团/生产/销售主体分离",
            "product": {
                "name_cn": product, "name_en": "", "abbr": abbr, "cas": "",
                "hs_cn": "", "spec_summary": spec, "packaging": "", "process_route": "",
            },
            "buyer_context": {
                "origin": country, "destination": "中国",
                "intent": "寻找公开资料显示可能实际生产%s的%s企业" % (product, country),
                "quantity": "未提供 — 需采购方补充",
                "only_actual_manufacturers": "是",
                "certifications_needed": "未指定",
                "packaging_needed": "未指定",
            },
            "research_date": today,
            "evidence_grade_legend": [
                {"grade": "A", "label": "有直接公开制造证据", "def": "官网产品页/产能表、年报、EPC 合同、官方投产公告、装置级公开产能数据"},
                {"grade": "B", "label": "有产品业务关联但制造身份待核验", "def": "有产品级公开记载但缺装置级证据，或证据链存在矛盾/缺口"},
                {"grade": "C", "label": "仅存在行业相关性", "def": "属化工集团或附属，但无该产品制造证据，或明确生产近似品"},
                {"grade": "D", "label": "贸易/代理/身份不明", "def": "贸易商、代理、经销、平台卖家或无法确认经营实体"},
            ],
            "funnel": {"step1": 0, "step2": 0},
            "funnel_note": {"step1": "", "step2": ""},
            "market_interpretation": "",
            "disclaimer": "本报告仅基于公开可获得资料。公开设计产能不等于当前实际可供货能力；产能、装置运行状态、认证与联系方式均以企业书面确认为准。未核验字段一律标注为『待核验』，不虚构。",
        },
        "groups": [],
        "companies": [],
        "trade_notes": [],
        "market_context": [],
        "questions": [{"id": "QS-00", "company": "通用",
                       "q": "本次采购的产品、规格、数量、到岸港、结算方式与认证要求，请先确认，以便统一询盘口径。"}],
        "sources": [],
    }

    # 放一个示例企业，避免空报告，同时示范字段填写
    case_output["companies"] = [{
        "id": "C-1", "rank": 1,
        "legal_name": "【待填写：企业法定英文名】",
        "cn_name": "", "legal_name_ar": "",
        "entity_type": "MANUFACTURER", "entity_type_label": "制造企业（工厂主体）",
        "grade": "B",
        "grade_reason": "【待填写：依据哪几条证据、指向什么、还缺什么】",
        "group": None, "ownership": "待核验", "established": "待核验",
        "hq": "待核验", "country": country, "site": "待核验",
        "product_page": "", "website": "",
        "official_channels": [{"channel": "官网联系页", "value": "待核验", "status": "待核验"}],
        "products_specs": [{"product": product, "grade": "待核验", "spec": spec, "source": "待核验"}],
        "capacity": {"expr": "待核验", "unit": "", "detail": "待核验", "caveat": "无法判断当前可供货能力"},
        "process": "待核验",
        "evidence": [{"id": "E1", "type": "第三方转述", "grade": "间接", "src": "S1",
                      "text": "【待填写：原文摘要】", "conf": "低"}],
        "certifications": [{"cert": "ISO 9001", "status": "待核验"}],
        "export_info": "待核验", "risks": ["待核验"],
        "open_questions": ["QS-01"],
    }]
    case_output["questions"].append({"id": "QS-01", "company": "C-1", "q": "贵司是否拥有并运营该产品的生产装置？装置名称、许可号与地址？"})
    case_output["sources"] = [{"id": "S1", "title": "【待填写来源标题】", "url": "https://待填写",
                               "date": "", "access": today, "status": "待下载", "note": ""}]

    with open(os.path.join(outdir, 'case_input.json'), 'w', encoding='utf-8') as f:
        json.dump(case_input, f, ensure_ascii=False, indent=2)
    with open(os.path.join(outdir, 'case_output.json'), 'w', encoding='utf-8') as f:
        json.dump(case_output, f, ensure_ascii=False, indent=2)

    print("已生成骨架：")
    print("  " + os.path.join(outdir, 'case_input.json'))
    print("  " + os.path.join(outdir, 'case_output.json'))
    print("下一步：按 SKILL.md 六步流程取证后填写 case_output.json，再运行 build_report.py / build_workbook.py / self_check.py")
    return 0


if __name__ == '__main__':
    sys.exit(main())
