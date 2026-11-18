# -*- coding: utf-8 -*-
"""一次性数据修正脚本：应用批次 A 核查结论。"""
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


# ---- 1. 修正渤化两期口径 ----
d = jload("units.json")
for u in d["units"]:
    if u["uid"] == "U-P100-01":
        u["capacity"] = 40.0
        u["capacity_year"] = 2021
        u["product"] = "聚氯乙烯树脂（悬浮法，一期）"
        u["capacity_note"] = (
            "渤化集团官网：PVC 80 万吨（60 万吨/年离子膜烧碱 + 80 万吨/年 PVC 项目）。此处 40 万吨为一期口径"
            "（2021-12 试车投产）；二期 40 万吨见 U-P100-02（2025-09-28 全面投产）。两者合计 120 万吨 = 渤化集团 PVC 总产能。"
            "2022 年起不再采购电石 ⇒ 乙烯法。"
        )
    if u["uid"] == "U-P100-02":
        u["product"] = "聚氯乙烯树脂（悬浮法，二期）"

# ---- 2. 新增/修订：宜宾天原、中盐糊树脂、三友利用率、华塑利用率、阳煤、英力特状态 ----
by_uid = {u["uid"]: u for u in d["units"]}

# 三友：评级报告合计 52.5 万吨（40 通用 + 7 专用 = 47，余 5.5 万吨为其他树脂口径偏差）
# 保持 40+7，另在口径对比中记录 52.5 的合计表述。

# 中盐：树脂 40 + 糊树脂 24
by_uid["U-P060-01"]["capacity"] = 40.0
by_uid["U-P060-01"]["capacity_note"] = (
    "中盐内蒙古化工 2025 年报：树脂 40 万吨 + 糊树脂 24 万吨，产能利用率 106.08%（电石法，自备电石）。"
    "本行为树脂 40 万吨部分。"
)
by_uid["U-P060-01"]["confidence"] = "A"
by_uid["U-P060-01"]["source_id"] = "S11"
by_uid["U-P060-01"]["capacity_year"] = 2025
by_uid["U-P060-01"]["status_note"] = "利用率 106.08%"

d["units"].append({
    "uid": "U-P060-02", "plant_id": "P060", "entity_id": "E060",
    "product": "聚氯乙烯糊树脂（EPVC）", "grade_class": "糊树脂",
    "basis": "design", "capacity": 24.0,
    "capacity_note": "中盐内蒙古化工 2025 年报：糊树脂 24 万吨（与树脂 40 万吨分列）",
    "capacity_year": 2025, "route": "carbide", "route_note": "电石法",
    "start_year": None, "status": "running", "status_note": "利用率 106.08%（合并口径）",
    "integrated_calcium_carbide": True, "source_id": "S11", "confidence": "A",
})

# 华塑利用率
by_uid["U-P090-01"]["status_note"] = "产能利用率 90.63%（2025 年报）"

# 三友利用率
by_uid["U-P080-01"]["status_note"] = "产能利用率 80.00%（2025 年报）"
by_uid["U-P080-02"]["status_note"] = "产能利用率 80.00%（2025 年报，合并口径）"

# 阳煤：30 万吨（2024 年报），不是 25.06 万吨产量
by_uid["U-P130-01"]["basis"] = "design"
by_uid["U-P130-01"]["capacity"] = 30.0
by_uid["U-P130-01"]["capacity_year"] = 2024
by_uid["U-P130-01"]["capacity_note"] = (
    "阳煤化工 2024 年报：PVC 设计产能 30 万吨/年，产能利用率 83.53%（对应产量约 25.06 万吨）。"
    "工艺为「以乙烯、氯气、氢气为原料，采用氧氯化平衡法和直接氯化法」，配套 UOP/Total MTO+OCP 烯烃装置 ⇒ 乙烯法。"
)
by_uid["U-P130-01"]["status_note"] = "利用率 83.53%；2025 年报巨潮不可得，运行状态以 2024 年报为准"
by_uid["U-P130-01"]["route_note"] = "乙烯法（MTO+OCP 氧氯化）"

# 英力特：2026-09-22 公告停产（PVC 价格不及预期）
by_uid["U-P070-01"]["status"] = "idle"
by_uid["U-P070-01"]["status_note"] = (
    "2026-09-22 公告：氯碱运行部生产线（PVC）+ 部分电石装置临时停产，理由为 PVC 价格不及预期；已连亏四年。"
    "年报口径仍为 22 万吨。"
)
by_uid["U-P070-02"]["status"] = "idle"
by_uid["U-P070-02"]["status_note"] = "同上"

# 亿利：只有 2022 年报数字，2023 后状态未知
by_uid["U-P140-01"]["status_note"] = (
    "亿利洁能 2022 年报口径（利用率 102.67%）；巨潮无 2023 年后年报，2023—2026 运行状态未知"
)
by_uid["U-P140-01"]["status"] = "unknown"
by_uid["U-P140-01"]["confidence"] = "B"

# 大沽：塘沽厂区已关停，主体迁天津南港
for u in d["units"]:
    if u["plant_id"] == "P100":
        u["status_note"] = (u.get("status_note") or "") + " ｜ 塘沽老厂区 2022 年关停，主体迁天津南港工业区"

# 乌海化工/鸿达：已实质退出，110 万吨
by_uid["U-P200-01"]["capacity"] = 110.0
by_uid["U-P200-01"]["capacity_year"] = 2022
by_uid["U-P200-01"]["capacity_note"] = (
    "鸿达兴业 2022 年报：PVC 110 万吨/年，产能利用率 44.62%。2023-10 乌海化工 PVC/烧碱/电石装置停产检修超 2 个月并"
    "被乌海中院裁定受理破产重整；2024-04 集团被裁定破产；股票已股债双退；2026-03-16 再被裁定受理重整。"
    "按「已退出/长期停车」处理，不计入在产供给。"
)
by_uid["U-P200-01"]["confidence"] = "A"
by_uid["U-P200-01"]["status"] = "shutdown"
by_uid["U-P200-01"]["status_note"] = "已实质退出：破产重整，产能不计入在产供给"

# ---- 3. 新增：宜宾天原 ----
d["units"].append({
    "uid": "U-P400-01", "plant_id": "P400", "entity_id": "E400",
    "product": "聚氯乙烯树脂", "grade_class": "未细分",
    "basis": "design", "capacity": 50.0,
    "capacity_note": "宜宾天原集团 2025 年报：PVC 设计产能 50 万吨/年，产能利用率 78.44%",
    "capacity_year": 2025, "route": "carbide", "route_note": "电石法（电石全部外购，非一体化）",
    "start_year": None, "status": "running",
    "status_note": "利用率 78.44%；电石 100% 外购（2025 年采购额 26.52 亿元，占成本 15.54%）",
    "integrated_calcium_carbide": False, "source_id": "S76", "confidence": "A",
})

jdump("units.json", d)
print("units.json 已更新，共", len(d["units"]), "条")

# ---- 4. 新增实体/基地：宜宾天原 ----
r = jload("roster.json")
r["groups"].append({
    "group_id": "G28", "name": "宜宾天原集团股份有限公司（独立上市）", "short_name": "天原集团",
    "ultimate_controller": "宜宾市国有资产监督管理委员会", "group_type": "地方国企",
    "note": "四川宜宾，PVC 50 万吨/年，电石法但电石全部外购——不属于「西北电石一体化低成本」象限，成本结构与其他电石法企业显著不同。",
    "source_id": "S76",
})
r["entities"].append({
    "entity_id": "E400", "name": "宜宾天原集团股份有限公司", "short_name": "天原集团",
    "group_id": "G28", "stock_code": "002386.SZ", "unified_code": "",
    "registered_address": "四川省宜宾市", "entity_type": "生产型（独立上市）",
    "ownership": "宜宾市国资委", "verified_by": "2025 年报：PVC 设计产能 50 万吨、利用率 78.44%；原材料表显示电石全部外购",
    "source_id": "S76",
})
r["plants"].append({
    "plant_id": "P400", "name": "宜宾基地（天原集团）",
    "name_full": "宜宾天原集团股份有限公司 宜宾 PVC 生产基地", "entity_id": "E400",
    "province": "四川省", "city": "宜宾市", "district": "", "park": "宜宾临港经济技术开发区",
    "lat": 28.77, "lon": 104.62, "coord_precision": "city",
    "registered_address": "四川省宜宾市",
})
jdump("roster.json", r)
print("roster.json 已更新：集团", len(r["groups"]), "法人", len(r["entities"]), "基地", len(r["plants"]))

# ---- 5. 追加来源 S76 ----
s = jload("sources.json")
s["sources"].append({
    "source_id": "S76", "pub_type": "年报",
    "title": "宜宾天原集团股份有限公司 2025 年年度报告",
    "org": "巨潮资讯网 / 天原集团(002386)", "date": "2026-04", "url": "https://www.cninfo.com.cn/",
    "confidence": "A",
    "note": "PVC 设计产能 50 万吨/年、产能利用率 78.44%；原材料表「电石 谈判、询比价」，2025 年采购额 26.52 亿元，占成本 15.54%，即电石 100% 外购",
})
s["sources"].append({
    "source_id": "S77", "pub_type": "年报",
    "title": "中盐内蒙古化工股份有限公司 2025 年年度报告（产能与开工情况表）",
    "org": "上海证券交易所 / 中盐化工(600328)", "date": "2026-04-30", "url": "https://www.cninfo.com.cn/",
    "confidence": "A",
    "note": "树脂 40 万吨 + 糊树脂 24 万吨，产能利用率 106.08%；引全国 PVC 产能 2,932 万吨（电石法 2,055 + 乙烯法 877），开工率约 81.45%",
})
s["sources"].append({
    "source_id": "S78", "pub_type": "年报",
    "title": "安徽华塑股份有限公司 2025 年年度报告（产能与开工情况）",
    "org": "巨潮资讯网 / 华塑股份(600935)", "date": "2026-04-30", "url": "https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600935&id=12093600",
    "confidence": "A",
    "note": "PVC 64 万吨/年，产能利用率 90.63%；引全国 PVC 产能 2,993 万吨、71 家企业、平均 43.5 万吨",
})
s["sources"].append({
    "source_id": "S79", "pub_type": "年报",
    "title": "内蒙古君正能源化工集团股份有限公司 2025 年年报（引中国氯碱网分省产能）",
    "org": "上海证券交易所 / 君正集团(601216)", "date": "2026-04", "url": "https://www.cninfo.com.cn/",
    "confidence": "A",
    "note": "2025 年末全国 PVC 产能 3,087.5 万吨：电石法 2,016 / 乙烯法 888 / 天然气法 22；71 家企业、平均 43.5 万吨；分省：内蒙古 500、新疆 449、山东 420、青海 100、天津 172、浙江 147、河北 111、山西 105、宁夏 94、四川 82、安徽 77、江苏 133（万吨）",
})
jdump("sources.json", s)
print("sources.json 已更新，共", len(s["sources"]), "条来源")
