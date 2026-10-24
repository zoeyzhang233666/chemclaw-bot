# -*- coding: utf-8 -*-
"""build_data.py —— 生成示例 data.json（工业级乙二醇，**全部为模拟数据**）。

生成物：examples/mdeg/samples/01_*.html 等可打印的"模拟原始文件"，
        以及 examples/mdeg/data.json（引擎输入）。

所有企业名、批号、数值均为虚构，仅用于测试核对流程。文件内与 HTML 报告均带
【模拟数据】水印，禁止当作真实质量记录使用。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "..", "examples", "mdeg")
SAMPLES = os.path.join(EX, "samples")
os.makedirs(SAMPLES, exist_ok=True)

MOCK = "模拟数据 SIMULATED — 非真实质量记录，仅用于流程演示"

# --------------------------------------------------------------------------------------
# 产品指标别名表（跨品类通用，可按品类扩展）
# --------------------------------------------------------------------------------------
ALIASES = [
    {"canonical": "乙二醇含量", "aliases": ["纯度", "含量", "纯度(质量分数)", "Purity", "含量(质量分数)", "乙二醇纯度"],
     "category": "含量", "basis": "mandatory", "critical": True,
     "method_note": "面积归一化法受响应因子影响；与滴定法结果不可直接比较"},
    {"canonical": "水分", "aliases": ["水含量", "水", "含水量", "Water", "水分(质量分数)", "H2O"],
     "category": "水分", "basis": "mandatory", "critical": True,
     "method_note": "卡尔费休淬灭严格，红外法在含羟基基体中读数偏高，两法不可直接等效"},
    {"canonical": "酸度", "aliases": ["酸度(以乙酸计)", "总酸度", "Acidity"],
     "category": "杂质", "basis": "mandatory", "critical": False,
     "method_note": "滴定法下限受终点判断影响，接近方法检出下限时宜用离子色谱复核"},
    {"canonical": "铁", "aliases": ["铁含量", "Fe", "铁(Fe)"], "category": "杂质", "basis": "mandatory",
     "critical": False, "method_note": "AAS 与 ICP-OES 在所给限值水平上可视为等效（须注明）"},
    {"canonical": "灰分", "aliases": ["灼烧残渣", "灰份", "Ash"], "category": "杂质", "basis": "mandatory",
     "critical": False, "method_note": "灼烧温度 800℃/850℃ 差异会影响残渣量，须同条件比较"},
    {"canonical": "色度", "aliases": ["铂钴色度", "色度(铂钴)", "Color", "APHA"], "category": "物性",
     "basis": "customer", "critical": False, "method_note": "铂钴比色，须注明光照与观察条件"},
    {"canonical": "密度", "aliases": ["密度(20℃)", "相对密度", "Density"], "category": "物性",
     "basis": "customer", "critical": False, "method_note": "温度敏感，测定温度须为 20℃；15℃/25℃ 数据不可直接比较"},
    {"canonical": "醛(以乙醛计)", "aliases": ["醛含量", "醛类(以乙醛计)", "Aldehydes"], "category": "杂质",
     "basis": "customer", "critical": True,
     "method_note": "分光光度法测的是'以乙醛计'的总醛，与乙醛/甲醛分项浓度不可直接换算"},
    {"canonical": "外观", "aliases": ["Appearance", "外观与状态"], "category": "外观", "basis": "mandatory",
     "critical": False, "method_note": "目视法：无色透明、无可见机械杂质，需描述观察条件"},
    {"canonical": "二乙二醇(DEG)", "aliases": ["DEG", "二甘醇", "二乙二醇"], "category": "杂质",
     "basis": "customer", "critical": True,
     "method_note": "气相色谱外标法受分流比影响；部分厂家 COA 不列该指标"},
    {"canonical": "蒸发残渣", "aliases": ["残渣", "不挥发物"], "category": "杂质", "basis": "customer",
     "critical": False, "method_note": "烘干温度与恒重方式须一致，影响残渣称量结果"},
]

PRODUCT = {
    "name": "工业用乙二醇",
    "en_name": "Ethylene Glycol, Industrial Grade",
    "grade": "优等品",
    "cas": "107-21-1",
    "un": "3082",
    "hs": "2905310000",
    "basis": "as_received",
    "use": "聚酯原料（PET 切片）/ 防冻液调和",
    "indicator_aliases": ALIASES,
    "equivalent_methods": [
        ["GB/T 14571.2-2018", "ASTM E203-16", "JIS K 0068"],
        ["GB/T 14571.2", "GB/T 6283"],
    ],
}

SUPPLIER = {
    "name": "浙江东越石化有限公司（模拟）",
    "short": "东越石化(模拟)",
    "contact_name": "周敏",
    "contact": "质量部 / qa@example-supplier.cn（模拟邮箱）",
    "addr": "浙江省宁波市北仑区（模拟地址）",
    "role": "生产厂家",
}

# --------------------------------------------------------------------------------------
# 采购规格书
# --------------------------------------------------------------------------------------
SPEC_MAIN = {
    "doc_type": "采购规格书",
    "spec_no": "CMSY-QS-MEG-2026-03",
    "title": "工业用乙二醇 采购质量规格书",
    "rev": "Rev.C",
    "effective": "2026-03-01",
    "standard_ref": "GB/T 4649-2018",
    "buyer": "中化明阳新材料有限公司（模拟）",
    "loc": "规格书 P1-P2 · 表1 技术要求",
    "items": [
        {"name": "纯度", "name_key": "乙二醇含量", "unit": "%", "limit": "≥99.9", "method": "GB/T 14571.1",
         "basis": "as_received", "category": "含量", "critical": True,
         "loc": "规格书 §4.1 表1 第1行"},
        {"name": "水分", "name_key": "水分", "unit": "%", "limit": "≤0.08", "method": "GB/T 6283",
         "basis": "as_received", "category": "水分", "critical": True, "loc": "规格书 §4.1 表1 第2行"},
        {"name": "色度", "name_key": "色度", "unit": "Hazen", "limit": "≤10", "method": "GB/T 3143",
         "basis": "as_received", "category": "物性", "critical": False, "loc": "规格书 §4.1 表1 第3行"},
        {"name": "酸度(以乙酸计)", "name_key": "酸度", "unit": "%", "limit": "≤0.001", "method": "GB/T 14571.4",
         "basis": "as_received", "category": "杂质", "critical": False, "loc": "规格书 §4.1 表1 第4行"},
        {"name": "铁", "name_key": "铁", "unit": "ppm", "limit": "≤0.5", "method": "GB/T 14571.3",
         "basis": "as_received", "category": "杂质", "critical": False,
         "loc": "规格书 §4.1 表1 第5行（注1：铁以 Fe 计，ppb 表示时须换算）"},
        {"name": "灰分", "name_key": "灰分", "unit": "%", "limit": "≤0.002", "method": "GB/T 14571.5",
         "basis": "as_received", "category": "杂质", "critical": False, "loc": "规格书 §4.1 表1 第6行"},
        {"name": "醛(以乙醛计)", "name_key": "醛(以乙醛计)", "unit": "ppm", "limit": "≤5", "method": "GB/T 14571.6",
         "basis": "as_received", "category": "杂质", "critical": True, "loc": "规格书 §4.1 表1 第7行"},
        {"name": "密度(20℃)", "name_key": "密度", "unit": "g/cm³", "limit": "≥1.112", "method": "GB/T 4472",
         "basis": "as_received", "category": "物性", "critical": False, "loc": "规格书 §4.1 表1 第8行"},
        {"name": "外观", "name_key": "外观", "unit": "—", "limit": "无色透明、无可见机械杂质",
         "method": "目视法", "basis": "as_received", "category": "外观", "critical": False,
         "loc": "规格书 §4.1 表1 第9行"},
        {"name": "蒸发残渣", "name_key": "蒸发残渣", "unit": "%", "limit": "≤0.002", "method": "GB/T 6324.2",
         "basis": "as_received", "category": "杂质", "critical": False, "loc": "规格书 §4.1 表1 第10行"},
    ],
}

SPEC_CONTRACT = {
    "doc_type": "合同技术附件",
    "spec_no": "CMSY-HT-2026-0417-附件2",
    "title": "年度采购框架合同 · 技术附件（质量条款）",
    "rev": "第1版",
    "effective": "2026-04-20",
    "standard_ref": "GB/T 4649-2018",
    "buyer": "中化明阳新材料有限公司（模拟）",
    "loc": "技术附件 §3 表3-1",
    "items": [
        {"name": "乙二醇含量", "name_key": "乙二醇含量", "unit": "%", "limit": "≥99.85", "method": "GB/T 14571.1",
         "basis": "as_received", "category": "含量", "critical": True,
         "loc": "技术附件 §3.2 表3-1 第1行（低于国标优等品 99.90%，按合同优先原则执行 ≥99.85%）"},
        {"name": "水分", "name_key": "水分", "unit": "%", "limit": "≤0.08", "method": "GB/T 6283",
         "basis": "as_received", "category": "水分", "critical": True, "loc": "技术附件 §3.2 表3-1 第2行"},
        {"name": "醛(以乙醛计)", "name_key": "醛(以乙醛计)", "unit": "ppm", "limit": "≤5", "method": "GB/T 14571.6",
         "basis": "as_received", "category": "杂质", "critical": True, "loc": "技术附件 §3.3 特殊质量条款"},
        {"name": "外观", "name_key": "外观", "unit": "—", "limit": "无色透明、无可见机械杂质",
         "method": "目视法", "basis": "as_received", "category": "外观", "critical": False,
         "loc": "技术附件 §3.2 表3-1 第9行"},
        {"name": "色度", "name_key": "色度", "unit": "Hazen", "limit": "≤10", "method": "GB/T 3143",
         "basis": "as_received", "category": "物性", "critical": False, "loc": "技术附件 §3.2 表3-1 第3行"},
        {"name": "灰分", "name_key": "灰分", "unit": "%", "limit": "≤0.002", "method": "GB/T 14571.5",
         "basis": "as_received", "category": "杂质", "critical": False, "loc": "技术附件 §3.2 表3-1 第6行"},
        {"name": "二乙二醇(DEG)", "name_key": "二乙二醇(DEG)", "unit": "%", "limit": "≤0.01",
         "method": "GB/T 14571.7", "basis": "as_received", "category": "杂质", "critical": True,
         "loc": "技术附件 §3.3 特殊质量条款（合同新增，规格书未约定）"},
    ],
}

STANDARD = {
    "code": "GB/T 4649-2018",
    "title": "工业用乙二醇（非合同引用，仅供参照；合同/规格书限值与国标不一致时以合同为准）",
    "loc": "参照：GB/T 4649-2018 表1 优等品",
    "items": [
        {"name": "乙二醇含量", "name_key": "乙二醇含量", "unit": "%", "limit": "≥99.9", "method": "GB/T 14571.1",
         "category": "含量"},
        {"name": "水分", "name_key": "水分", "unit": "%", "limit": "≤0.08", "method": "GB/T 6283", "category": "水分"},
        {"name": "色度", "name_key": "色度", "unit": "Hazen", "limit": "≤10", "method": "GB/T 3143", "category": "物性"},
        {"name": "酸度", "name_key": "酸度", "unit": "%", "limit": "≤0.001", "method": "GB/T 14571.4",
         "category": "杂质"},
        {"name": "铁", "name_key": "铁", "unit": "ppm", "limit": "≤0.5", "method": "GB/T 14571.3", "category": "杂质"},
        {"name": "灰分", "name_key": "灰分", "unit": "%", "limit": "≤0.002", "method": "GB/T 14571.5",
         "category": "杂质"},
        {"name": "醛", "name_key": "醛(以乙醛计)", "unit": "ppm", "limit": "≤5", "method": "GB/T 14571.6",
         "category": "杂质"},
        {"name": "密度(20℃)", "name_key": "密度", "unit": "g/cm³", "limit": "≈1.113", "method": "GB/T 4472",
         "category": "物性"},
        {"name": "外观", "name_key": "外观", "unit": "—", "limit": "无色透明、无可见机械杂质", "method": "目视法",
         "category": "外观"},
        {"name": "蒸发残渣", "name_key": "蒸发残渣", "unit": "%", "limit": "≤0.002", "method": "GB/T 6324.2",
         "category": "杂质"},
        {"name": "二乙二醇", "name_key": "二乙二醇(DEG)", "unit": "%", "limit": "≤0.01", "method": "GB/T 14571.7",
         "category": "杂质"},
    ],
}


def item(name_key, name, value, unit, method, loc, lod=None, replicate=None, basis="as_received",
         comment=None, unit_display=None):
    d = {"name": name, "name_key": name_key, "value": value, "unit": unit, "method": method,
         "loc": loc, "basis": basis}
    if unit_display:
        d["_unit_display"] = unit_display
    if lod:
        d["lod"] = lod
    if replicate:
        d["replicate"] = replicate
    if comment:
        d["comment"] = comment
    return d


COA_A = {
    "batch_no": "DY-EG-260512A",
    "file": "COA_A_东越石化_DY-EG-260512A（模拟）.html",
    "label": "批 A · DY-EG-260512A",
    "collect_date": "2026-05-16",
    "linked_delivery_batch": "DY-EG-260512A",
    "tank": "T-207",
    "header": {
        "product_name": "乙二醇（工业用）",
        "grade": "优等品",
        "producer": "浙江东越石化有限公司",
        "batch_no": "DY-EG-260512A",
        "report_no": "COA-DY-2605-1182",
        "mfg_date": "2026-05-12",
        "test_date": "2026-05-13",
        "retest_date": "2026-08-12",
        "test_standard": "GB/T 4649-2018",
        "conclusion": "检验合格",
        "packing": "槽车散装 / 31.6 t",
    },
    "signoff": {"cert_code": "Q7XK-9D2M-4TLP-81AA", "inspector": "李工", "reviewer": "王工",
                "issuer": "质量部（红章位置）"},
    "items": [
        item("乙二醇含量", "乙二醇纯度（质量分数）", "99.92", "%", "GB/T 14571.1-2018", "COA 表 §1 第1行"),
        item("水分", "水分", "0.075", "%", "GB/T 6283-2008", "COA 表 §1 第2行"),
        item("色度", "色度（铂钴）", "5", "Hazen", "GB/T 3143-1982", "COA 表 §1 第3行"),
        item("酸度", "酸度（以乙酸计）", "0.0001", "%", "GB/T 14571.4-2018", "COA 表 §1 第4行"),
        item("铁", "铁（Fe）", "0.32", "ppm", "GB/T 14571.3-2018", "COA 表 §1 第5行", lod="0.05 ppm"),
        item("灰分", "灰分（灼烧残渣）", "0.0015", "%", "GB/T 14571.5-2018", "COA 表 §1 第6行"),
        item("醛(以乙醛计)", "醛（以乙醛计）", "3.1", "ppm", "GB/T 14571.6-2018", "COA 表 §1 第7行", lod="0.5 ppm"),
        item("密度", "密度（20℃）", "1.1132", "g/cm³", "GB/T 4472-2011", "COA 表 §1 第8行"),
        item("外观", "外观", "无色透明液体，无可见机械杂质", "—", "目视法", "COA 表 §1 第9行"),
        item("蒸发残渣", "蒸发残渣", "0.0012", "%", "GB/T 6324.2-2004", "COA 表 §1 第10行"),
        item("二乙二醇(DEG)", "二乙二醇（DEG）", "0.006", "%", "GB/T 14571.7-2018", "COA 表 §1 第11行"),
    ],
}

COA_B = {
    "batch_no": "DY-EG-260603B",
    "file": "COA_B_东越石化_DY-EG-260603B（模拟）.html",
    "label": "批 B · DY-EG-260603B",
    "collect_date": "2026-06-06",
    "linked_delivery_batch": "DY-EG-260603B",
    "tank": "T-208",
    "header": {
        "product_name": "乙二醇",
        "grade": "—",
        "producer": "东越石化有限公司",
        "batch_no": "DY260603B",
        "report_no": "DY-QC-26-0603",
        "mfg_date": "2026-06-03",
        "test_date": "2026-06-04",
        "retest_date": "",
        "test_standard": "GB/T 4649-2018",
        "conclusion": "符合优等品要求",
        "packing": "槽车散装 / 31.4 t",
    },
    "signoff": {"cert_code": "", "inspector": "张", "reviewer": "", "issuer": ""},
    "items": [
        item("乙二醇含量", "纯度", "99.86", "%", "GB/T 14571.1-2018", "COA-B 表 第1行"),
        item("水分", "水分", "865", "ppm", "GB/T 6283-2008", "COA-B 表 第2行"),
        item("铁", "铁含量", "580", "ppb", "GB/T 14571.3-2018", "COA-B 表 第3行", lod="检出限 8 ppb"),
        item("醛(以乙醛计)", "醛类（以乙醛计）", "7.2", "ppm", "GB/T 14571.6-2018", "COA-B 表 第4行"),
        item("色度", "色度", "12", "Hazen", "GB/T 3143-1982", "COA-B 表 第5行"),
        item("酸度", "酸度", "未检测", "%", "—", "COA-B 表 第6行", comment="标注'本批未检'"),
        item("外观", "外观", "微带浅黄色，透明度略差", "—", "目视法", "COA-B 表 第7行"),
        item("密度", "密度（15℃）", "1.1171", "g/cm³", "GB/T 4472-2011", "COA-B 表 第8行",
             comment="测定温度为 15℃，与规格约定的 20℃ 不同"),
    ],
}

# 历史批次（近一年，同一供应商）
HIST = [
    {"batch_no": "DY-EG-251120H", "mfg_date": "2025-11-20", "items": [
        item("乙二醇含量", "纯度", "99.93", "%", "GB/T 14571.1-2018", "历史台账"),
        item("水分", "水分", "0.062", "%", "GB/T 6283-2008", "历史台账"),
        item("铁", "铁", "0.21", "ppm", "GB/T 14571.3-2018", "历史台账"),
        item("醛(以乙醛计)", "醛类", "2.4", "ppm", "GB/T 14571.6-2018", "历史台账"),
        item("色度", "色度", "4", "Hazen", "GB/T 3143-1982", "历史台账")]},
    {"batch_no": "DY-EG-260120J", "mfg_date": "2026-01-20", "items": [
        item("乙二醇含量", "纯度", "99.94", "%", "GB/T 14571.1-2018", "历史台账"),
        item("水分", "水分", "0.058", "%", "GB/T 6283-2008", "历史台账"),
        item("铁", "铁", "0.19", "ppm", "GB/T 14571.3-2018", "历史台账"),
        item("醛(以乙醛计)", "醛类", "2.1", "ppm", "GB/T 14571.6-2018", "历史台账"),
        item("色度", "色度", "3", "Hazen", "GB/T 3143-1982", "历史台账")]},
    {"batch_no": "DY-EG-260310K", "mfg_date": "2026-03-10", "items": [
        item("乙二醇含量", "纯度", "99.93", "%", "GB/T 14571.1-2018", "历史台账"),
        item("水分", "水分", "0.069", "%", "GB/T 6283-2008", "历史台账"),
        item("铁", "铁", "0.25", "ppm", "GB/T 14571.3-2018", "历史台账"),
        item("醛(以乙醛计)", "醛类", "2.8", "ppm", "GB/T 14571.6-2018", "历史台账"),
        item("色度", "色度", "5", "Hazen", "GB/T 3143-1982", "历史台账")]},
    {"batch_no": "DY-EG-260418L", "mfg_date": "2026-04-18", "items": [
        item("乙二醇含量", "纯度", "99.91", "%", "GB/T 14571.1-2018", "历史台账"),
        item("水分", "水分", "0.073", "%", "GB/T 6283-2008", "历史台账"),
        item("铁", "铁", "0.28", "ppm", "GB/T 14571.3-2018", "历史台账"),
        item("醛(以乙醛计)", "醛类", "3.0", "ppm", "GB/T 14571.6-2018", "历史台账"),
        item("色度", "色度", "6", "Hazen", "GB/T 3143-1982", "历史台账")]},
]

DATA = {
    "meta": {
        "title": "工业级乙二醇 到货 COA 与采购质量规格书核对",
        "as_of": "2026-06-08",
        "buyer_name": "采购部 林工",
        "buyer_contact": "采购部 / lin.mm@example-buyer.cn（模拟邮箱）",
        "spec_ref": "CMSY-QS-MEG-2026-03 Rev.C / CMSY-HT-2026-0417 附件2",
        "target_coa_batch": "DY-EG-260603B",
        "tone": "formal",
        "simulated": True,
        "sim_note": "本文档所有企业名称、批号、数值均为模拟构造，仅用于演示 COA 核对流程，不得作为真实质量记录或索赔依据。",
        "export_base": "乙二醇到货COA核对报告_20260608",
    },
    "product": PRODUCT,
    "supplier": SUPPLIER,
    "contract": {"no": "CMSY-HT-2026-0417", "attach": "附件2 技术附件", "price_terms": "详见商务附件（本核对不涉及价格）",
                 "quality_clause": "§7.2 到货检验以本合同技术附件为准；买方有权按约定方法复检，复检不合格批次按 §7.5 处理",
                 "qty": "框架 12,000 t/年；单批 1×31.5 t 槽车"},
    "specs": [SPEC_MAIN, SPEC_CONTRACT],
    "standards": [STANDARD],
    "coas": [COA_A, COA_B],
    "historical_batches": HIST,
    "alerts": [
        {"level": "高", "text": "批 B 的 COA 结论文本为「符合优等品要求」，但水分、铁、醛、色度 4 项实测已越过合同限值——结论与数据矛盾，须作为异议核心证据。"},
        {"level": "中", "text": "批 A 与批 B 的水分单位分别为 % 与 ppm、铁分别为 ppm 与 ppb，须换算后才能比较；ppm↔% 为 1e-4 量级，换算误差不影响结论。"},
        {"level": "中", "text": "本合同技术附件的乙二醇含量限值 ≥99.85% 低于规格书与国标优等品 99.90%，按'合同优先'原则判定；该差异本身须在合同中书面固化。"},
        {"level": "低", "text": "所有文件均为模拟数据，任何结论不得用于真实索赔或收货决策。"},
    ],
}


# --------------------------------------------------------------------------------------
# 生成"模拟原始文件"（可打印 HTML，便于演示"点击定位原文"）
# --------------------------------------------------------------------------------------
def _f(t): return float(str(t).replace(",", "."))


def _dev(row, lim_txt):
    """在样例文件上原位标出偏离（用于演示点击定位）。"""
    return ""


def write_samples():
    C = "color:#111;font-family:'SimSun','Songti SC',serif"
    def coa_html(c, title, extra_note=""):
        rows = []
        for it in c["items"]:
            v = it["value"]
            meth = it["method"]
            unit = it.get("_unit_display") or it["unit"]
            hi = ""
            if it["name_key"] == "水分" and v not in ("未检测",):
                pass
            rows.append(
                f'<tr><td>{it["name"]}</td><td class="v">{v}</td><td>{unit}</td>'
                f'<td>{meth}</td><td>{it.get("lod","") or ""}</td></tr>')
        h = c["header"]
        return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{title}</title><style>
body{{{C};max-width:900px;margin:24px auto;background:#fffdf8;font-size:13px}}
.sim{{background:repeating-linear-gradient(45deg,#fff3cd,#fff3cd 10px,#ffe8a8 10px,#ffe8a8 20px);
color:#7a5b00;font:600 13px/1.5 sans-serif;padding:8px 12px;border:1px solid #e6c85f;margin-bottom:14px}}
.wm{{position:fixed;inset:0;pointer-events:none;display:flex;align-items:center;justify-content:center;
transform:rotate(-28deg);font:900 96px/1 sans-serif;color:rgba(200,60,40,.07);z-index:0}}
h1{{text-align:center;font-size:20px;letter-spacing:4px;margin:6px 0 2px}}
.sub{{text-align:center;color:#666;font-size:12px;margin-bottom:10px}}
table{{width:100%;border-collapse:collapse;background:#fff}}
th,td{{border:1px solid #999;padding:5px 8px;vertical-align:top}}
th{{background:#f2f0e8;font-weight:600}}
td.v{{text-align:right;font-family:'Courier New',monospace}}
.kv td:first-child{{width:130px;background:#faf8f2}}
.foot{{display:flex;justify-content:space-between;margin-top:14px;font-size:12px;color:#333}}
.stamp{{border:2px solid #c00;color:#c00;padding:6px 10px;transform:rotate(-6deg);font-weight:700}}
</style></head><body><div class="wm">模拟 SIMULATED</div>
<div class="sim">⚠ {MOCK}｜文件：{c['file']}</div>
<h1>{h['product_name']} 质量分析证书（COA）</h1>
<div class="sub">Certificate of Analysis ｜ 生产企业：{h['producer']}</div>
<table class="kv">
<tr><td>证书编号</td><td>{h['report_no']}</td><td>产品等级</td><td>{h['grade']}</td></tr>
<tr><td>生产批号</td><td>{h['batch_no']}</td><td>包装/数量</td><td>{h['packing']}</td></tr>
<tr><td>生产日期</td><td>{h['mfg_date']}</td><td>检测日期</td><td>{h['test_date']}</td></tr>
<tr><td>复检期至</td><td>{h['retest_date'] or '（未标注）'}</td><td>检测依据</td><td>{h['test_standard']}</td></tr>
</table>
<table style="margin-top:10px">
<tr><th style="width:34%">检验项目</th><th style="width:16%">实测值</th><th style="width:10%">单位</th><th style="width:22%">检测方法</th><th>检出限</th></tr>
{''.join(rows)}
</table>
<p style="margin:10px 0 0"><b>检验结论：</b>{h['conclusion']}　{extra_note}</p>
<div class="foot">
<div>编制：{c['signoff']['inspector']}　审核：{c['signoff']['reviewer'] or '（空）'}　签发：{c['signoff']['issuer'] or '（空）'}<br>
防伪码：{c['signoff']['cert_code'] or '（无）'}</div>
<div class="stamp">质量部检验专用章（模拟）</div></div>
<div class="sim" style="margin-top:18px">本文件为流程演示所构造的模拟 COA，数值与单位差异按测试用例设计，不代表任何真实企业或产品。</div>
</body></html>"""

    open(os.path.join(SAMPLES, "COA_A_东越石化_DY-EG-260512A（模拟）.html"), "w", encoding="utf-8").write(
        coa_html(COA_A, "COA 批A · DY-EG-260512A（模拟）"))
    open(os.path.join(SAMPLES, "COA_B_东越石化_DY-EG-260603B（模拟）.html"), "w", encoding="utf-8").write(
        coa_html(COA_B, "COA 批B · DY-EG-260603B（模拟）",
                 "注：水分、铁单位分别为 ppm、ppb；部分项目未检测；色度与醛类实测值高于合同限值。"))

    # 规格书
    rows = "".join(f'<tr><td>{i["name"]}</td><td>{i["unit"]}</td><td class="v">{i["limit"]}</td>'
                   f'<td>{i["method"]}</td><td>{i.get("loc","")}</td></tr>' for i in SPEC_MAIN["items"])
    spec_html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{SPEC_MAIN['title']}（模拟）</title><style>
body{{font-family:'SimSun','Songti SC',serif;color:#111;max-width:960px;margin:24px auto;background:#fffdf8;font-size:13px}}
.sim{{background:repeating-linear-gradient(45deg,#fff3cd,#fff3cd 10px,#ffe8a8 10px,#ffe8a8 20px);
color:#7a5b00;font:600 13px/1.5 sans-serif;padding:8px 12px;border:1px solid #e6c85f;margin-bottom:14px}}
h1{{text-align:center;font-size:20px;letter-spacing:3px}}h2{{font-size:15px;border-left:4px solid #8a6d3b;padding-left:8px}}
table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #999;padding:5px 8px}}
th{{background:#f2f0e8}}td.v{{font-family:'Courier New',monospace;font-weight:700;background:#fffbe6}}
</style></head><body><div class="sim">⚠ {MOCK}｜文件：采购质量规格书_CMSY-QS-MEG-2026-03（模拟）.html</div>
<h1>{SPEC_MAIN['title']}</h1>
<p style="text-align:center;color:#666">文件编号 {SPEC_MAIN['spec_no']}　版本 {SPEC_MAIN['rev']}　生效 {SPEC_MAIN['effective']}　适用标准 {SPEC_MAIN['standard_ref']}</p>
<h2>§4.1 技术要求（表1）</h2>
<table><tr><th style="width:26%">项目</th><th style="width:12%">单位</th><th style="width:18%">指标</th><th style="width:24%">试验方法</th><th>条款位置</th></tr>
{rows}</table>
<h2>§4.2 说明</h2>
<ol><li>表1 指标为到货验收判据，任一项不满足即视为该批不符合。</li>
<li>铁以 Fe 计；若报告用 ppb 表示，须换算为 ppm 后对照（1 ppm = 1000 ppb）。</li>
<li>密度测定温度须为 20℃；其他温度数据须换算或注明后另行判定。</li>
<li>醛以乙醛计的总醛，不得以单一醛分项替代。</li>
<li>供应商提供的 COA 须含批号、生产日期、检测日期、检测依据与检测方法。</li></ol>
<div class="sim" style="margin-top:16px">本规格书为流程演示所构造的模拟文件。</div></body></html>"""
    open(os.path.join(SAMPLES, "采购质量规格书_CMSY-QS-MEG-2026-03（模拟）.html"), "w", encoding="utf-8").write(spec_html)

    # 合同技术附件
    rows2 = "".join(f'<tr><td>{i["name"]}</td><td>{i["unit"]}</td><td class="v">{i["limit"]}</td>'
                    f'<td>{i["method"]}</td><td>{i.get("loc","")}</td></tr>' for i in SPEC_CONTRACT["items"])
    open(os.path.join(SAMPLES, "合同技术附件_CMSY-HT-2026-0417-附件2（模拟）.html"), "w", encoding="utf-8").write(
        f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{SPEC_CONTRACT['title']}（模拟）</title>
<style>body{{font-family:'SimSun',serif;max-width:960px;margin:24px auto;background:#fffdf8;font-size:13px}}
.sim{{background:#fff3cd;color:#7a5b00;padding:8px 12px;border:1px solid #e6c85f;margin-bottom:14px;font-family:sans-serif}}
h1{{text-align:center;font-size:19px}}h2{{font-size:15px;border-left:4px solid #8a6d3b;padding-left:8px}}
table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #999;padding:5px 8px}}th{{background:#f2f0e8}}
td.v{{font-family:'Courier New',monospace;font-weight:700;background:#fffbe6}}</style></head><body>
<div class="sim">⚠ {MOCK}｜文件：合同技术附件_CMSY-HT-2026-0417-附件2（模拟）.html</div>
<h1>{SPEC_CONTRACT['title']}</h1>
<p style="text-align:center;color:#666">编号 {SPEC_CONTRACT['spec_no']}　{SPEC_CONTRACT['rev']}　生效 {SPEC_CONTRACT['effective']}</p>
<h2>§3.2 质量指标（表3-1）</h2>
<table><tr><th style="width:26%">项目</th><th style="width:12%">单位</th><th style="width:18%">指标</th><th style="width:24%">试验方法</th><th>条款位置</th></tr>
{rows2}</table>
<h2>§3.3 特殊质量条款</h2>
<ul><li>醛（以乙醛计）≤5 ppm，须逐批检测并列入 COA。</li><li>二乙二醇（DEG）≤0.01%，为本合同新增要求（采购规格书未约定）。</li></ul>
<h2>§7 质量责任</h2><p>§7.2 到货检验以本附件为准；§7.5 复检不合格批次按合同商务条款处理。</p>
<div class="sim" style="margin-top:16px">本技术附件为流程演示所构造的模拟文件。</div></body></html>""")

    # 历史批次台账
    hrows = "".join(
        f'<tr><td>{b["batch_no"]}</td><td>{b["mfg_date"]}</td>' +
        "".join(f'<td>{next((x["value"]+" "+str(x["unit"]) for x in b["items"] if x["name_key"]==k), "—")}</td>'
                for k in ("乙二醇含量", "水分", "铁", "醛(以乙醛计)", "色度")) + "</tr>" for b in HIST)
    open(os.path.join(SAMPLES, "历史批次台账_近一年（模拟）.html"), "w", encoding="utf-8").write(
        f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>历史批次台账（模拟）</title>
<style>body{{font-family:'SimSun',serif;max-width:1000px;margin:24px auto;background:#fffdf8;font-size:13px}}
.sim{{background:#fff3cd;color:#7a5b00;padding:8px 12px;border:1px solid #e6c85f;margin-bottom:14px;font-family:sans-serif}}
table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #999;padding:5px 8px}}th{{background:#f2f0e8}}</style>
</head><body><div class="sim">⚠ {MOCK}｜文件：历史批次台账_近一年（模拟）.html</div>
<h1 style="text-align:center;font-size:18px">供应商来料历史批次台账（近一年 · 模拟）</h1>
<table><tr><th>批号</th><th>生产日期</th><th>纯度 %</th><th>水分 %</th><th>铁 ppm</th><th>醛 ppm</th><th>色度 Hazen</th></tr>
{hrows}</table><div class="sim" style="margin-top:16px">历史数据为模拟构造，仅用于演示趋势对比。</div></body></html>""")

    print("samples written ->", SAMPLES)


def main():
    write_samples()
    with open(os.path.join(EX, "data.json"), "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=1)
    print("data.json written")


if __name__ == "__main__":
    main()
