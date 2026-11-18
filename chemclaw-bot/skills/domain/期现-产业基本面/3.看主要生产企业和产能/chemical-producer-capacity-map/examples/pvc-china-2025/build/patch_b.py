# -*- coding: utf-8 -*-
"""第二次数据修正：补齐已投产装置（防止重复计/漏计），修正置换备注语义。"""
import io
import json
import os

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def jload(n):
    with io.open(os.path.join(DATA, n), encoding="utf-8") as f:
        return json.load(f)


def jdump(n, obj):
    with io.open(os.path.join(DATA, n), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# ---------- A. 把已投产项目补进存量装置层（否则 R10 会报「项目已运行但存量未录」） ----------
d = jload("units.json")
uids = {u["uid"] for u in d["units"]}

NEW = [
    {
        "uid": "U-P305-01", "plant_id": "P305", "entity_id": "E305",
        "product": "聚氯乙烯树脂（电石法无汞）", "grade_class": "未细分",
        "basis": "design", "capacity": 60.0,
        "capacity_note": "陕西金泰氯碱神木 60 万吨/年电石法 PVC，全球首套 60 万吨级无汞催化示范装置；2024-05-11 试生产，2025-07-11 交工验收",
        "capacity_year": 2025, "route": "carbide", "route_note": "电石法，无汞催化剂",
        "start_year": 2025, "status": "running", "status_note": "2025-07-11 交工验收",
        "integrated_calcium_carbide": None, "source_id": "S72", "confidence": "B",
    },
    {
        "uid": "U-P306-01", "plant_id": "P306", "entity_id": "E306",
        "product": "聚氯乙烯树脂（电石法无汞）", "grade_class": "未细分",
        "basis": "design", "capacity": 30.0,
        "capacity_note": "甘肃耀望化工 30 万吨/年无汞电石法 PVC，2025-11 投产（兰州新区）",
        "capacity_year": 2025, "route": "carbide", "route_note": "电石法，无汞催化",
        "start_year": 2025, "status": "running", "status_note": "2025-11 投产",
        "integrated_calcium_carbide": None, "source_id": "S73", "confidence": "B",
    },
    {
        "uid": "U-P307-01", "plant_id": "P307", "entity_id": "E307",
        "product": "聚氯乙烯树脂", "grade_class": "未细分",
        "basis": "design", "capacity": 50.0,
        "capacity_note": "新浦化学（泰兴）50 万吨/年 PVC；2022-04 中交，2025 年 1—2 月量产",
        "capacity_year": 2025, "route": "ethylene", "route_note": "乙烯法",
        "start_year": 2025, "status": "running", "status_note": "2025 年 1—2 月量产",
        "integrated_calcium_carbide": False, "source_id": "S74", "confidence": "B",
    },
    {
        "uid": "U-P304-01", "plant_id": "P304", "entity_id": "E304",
        "product": "聚氯乙烯树脂（一期）", "grade_class": "未细分",
        "basis": "design", "capacity": 40.0,
        "capacity_note": "万华化学福建 40 万吨/年 PVC 一期；2022-02-07 开工，2025 年 5—7 月试车投产。二期 40 万吨状态未知，未计入",
        "capacity_year": 2025, "route": "ethylene", "route_note": "乙烯法（利用 MDI/TDI 副产氯化氢）",
        "start_year": 2025, "status": "running", "status_note": "2025-05 起试车，2025-07-30 复产",
        "integrated_calcium_carbide": False, "source_id": "S75", "confidence": "B",
    },
    {
        "uid": "U-P308-01", "plant_id": "P308", "entity_id": "E308",
        "product": "聚氯乙烯树脂", "grade_class": "未细分",
        "basis": "design", "capacity": 30.0,
        "capacity_note": "浙江镇洋发展 30 万吨/年 PVC，2023-05 投产；2026-09-19 起临时停产（预计不超过 4 个月）",
        "capacity_year": 2025, "route": "ethylene", "route_note": "乙烯法（纯外购乙烯，无一体化配套）",
        "start_year": 2023, "status": "idle",
        "status_note": "2026-09-19 起临时停产，原料乙烯涨价，2026H1 PVC 毛利率 -23.24%",
        "integrated_calcium_carbide": False, "source_id": "S68", "confidence": "A",
    },
    {
        "uid": "U-P302-01", "plant_id": "P302", "entity_id": "E302",
        "product": "聚氯乙烯树脂（二期）", "grade_class": "未细分",
        "basis": "design", "capacity": 30.0,
        "capacity_note": "浙江嘉化能源 PVC 二期 30 万吨/年；VCM 二期 2025-08-28 开车，PVC 2026 年逐步放量（爬坡中）",
        "capacity_year": 2026, "route": "ethylene", "route_note": "乙烯法（日本 JNC 悬浮法，外购乙烯）",
        "start_year": 2026, "status": "running", "status_note": "2026 年爬坡放量",
        "integrated_calcium_carbide": False, "source_id": "S66", "confidence": "B",
    },
    {
        "uid": "U-P110-02", "plant_id": "P110", "entity_id": "E110",
        "product": "聚氯乙烯树脂（2025 年新增线）", "grade_class": "未细分",
        "basis": "design", "capacity": 20.0,
        "capacity_note": "青岛海湾化学 2025 年 8—9 月试车的 20 万吨新增产能；现有 85 万吨见 U-P110-01",
        "capacity_year": 2025, "route": "ethylene", "route_note": "乙烯法",
        "start_year": 2025, "status": "running", "status_note": "2025-08 起试车",
        "integrated_calcium_carbide": False, "source_id": "S22", "confidence": "B",
    },
]
for u in NEW:
    if u["uid"] not in uids:
        d["units"].append(u)
jdump("units.json", d)
print("units 追加", len([u for u in NEW]), "条，共", len(d["units"]))

# ---------- B. 修正项目 replacement_note 的语义（供 R11 正确判断） ----------
p = jload("projects.json")
FIX = {
    "PR01": "未查到置换方案",
    "PR02": "公开表述「部分产能置换」但方案未披露",
    "PR03": "未查到置换方案",
    "PR04": "净新增（无置换）",
    "PR05": "未查到置换方案",
    "PR06": "净新增（无置换）",
    "PR10": "未查到置换方案",
    "PR11": "未查到置换方案",
    "PR12": "净新增（无置换）",
    "PR07": "搬迁淘汰原电石法（吨数未披露）",
}
for pr in p["projects"]:
    if pr["project_id"] in FIX:
        pr["replacement_note"] = FIX[pr["project_id"]]
jdump("projects.json", p)
print("projects 备注已语义化")
