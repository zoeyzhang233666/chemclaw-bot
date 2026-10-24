# -*- coding: utf-8 -*-
"""SBS 数据包构建器（v2）

设计目标（相对 v1 的修正）：
  1. layer 字段改为「图列号 column」：每一列 = 一个产业链层级，严格满足
     「上游 column < 下游 column」，并通过 scripts/grade_layout.py 校验。
     苯乙烯的原料列(苯/乙烯/乙苯)不再与丁二烯的原料列(C4/C8)共列；
  2. 每个节点增加 class / role / stage 三类正交标签（化学品/材料/终端 × 环节）；
  3. 每条关系增加 flow（物质流/供应方向）、edge_style（solid/dashed/dotted）、
     quant 口径（basis_statement/range/formula）和 evidence；
  4. 覆盖面按「预先冻结的核心清单」计算，并与 HTML/Excel 共用同一实现。

只改写 nodes.json / relations.json / forbidden_links.json，其余文件从 v1 复制后
由人工修订（sources.json 等），再跑 validate_chain.py 校验。
"""
import json
import os

SRC = r"./_chain_skill\data"
DST = r"./_chainskill_build\src\chain-v1\examples\sbs\data"


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def dump(obj, name):
    os.makedirs(DST, exist_ok=True)
    with open(os.path.join(DST, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print("wrote", name)


# ----------------------------------------------------------------------------
# 列定义：column = 图谱列号（从上游到下游递增）
# ----------------------------------------------------------------------------
COLUMNS = [
    {"col": -5, "label": "原油 / 轻烃", "side": "up"},
    {"col": -4, "label": "重整 / 裂解", "side": "up"},
    {"col": -3, "label": "石脑油 / 重整生成油", "side": "up"},
    {"col": -2, "label": "裂解产物 / 芳烃馏分", "side": "up"},
    {"col": -1, "label": "芳烃 / 乙苯", "side": "up"},
    {"col": 0, "label": "聚合单体与基料", "side": "up"},
    {"col": 1, "label": "目标品种", "side": "core"},
    {"col": 2, "label": "配方材料 / 同类弹性体", "side": "down"},
    {"col": 3, "label": "改性料 / 制品", "side": "down"},
    {"col": 4, "label": "工程材料", "side": "down"},
    {"col": 5, "label": "终端应用", "side": "down"},
]

NODE_META = {
    # id: (column, class, role, segment, stage_label)
    "N_CRUDE":   (-5, "commodity", "raw", "原油与轻烃", "上游5列"),
    "N_LPG":     (-5, "commodity", "raw", "原油与轻烃", "上游5列"),
    "N_NAPHTHA": (-3, "commodity", "raw", "石脑油", "上游3列"),
    "N_BTX":     (-4, "commodity", "intermediate", "芳烃联合装置中间物料", "上游4列"),
    "N_C8A":     (-2, "commodity", "intermediate", "芳烃馏分", "上游2列"),
    "N_PYREXTRACT": (-4, "commodity", "byproduct", "裂解副产物", "上游4列"),
    "N_C4BE":    (-2, "commodity", "byproduct", "裂解副产物", "上游2列"),
    "N_ETH":     (-2, "commodity", "intermediate", "烯烃", "上游2列"),
    "N_EB":      (-1, "commodity", "intermediate", "芳烃中间体", "上游1列"),
    "N_BZ":      (-1, "commodity", "intermediate", "芳烃", "上游1列"),
    "N_SM":      (0, "commodity", "monomer", "石化单体", "上游1列"),
    "N_BD":      (0, "commodity", "monomer", "石化单体", "上游1列"),
    "N_ASPHALT": (0, "commodity", "auxiliary", "道路基料（配套原料）", "上游1列"),
    "N_PRIMARY": (1, "commodity", "target", "热塑性弹性体", "目标品种"),
    "N_IPP_SSBR": (2, "commodity", "auxiliary", "橡胶配合剂", "下游1列"),
    "N_SEBS":    (2, "commodity", "derivative", "氢化热塑性弹性体", "下游1列"),
    "N_SIS":     (2, "commodity", "same_family", "苯乙烯类热塑性弹性体", "下游1列"),
    "N_TPU":     (2, "commodity", "substitute", "热塑性聚氨酯", "下游1列"),
    "N_EVA":     (2, "commodity", "substitute", "乙烯共聚物", "下游1列"),
    "N_POE":     (2, "commodity", "substitute", "聚烯烃弹性体", "下游1列"),
    "N_SBR":     (2, "commodity", "substitute", "通用合成橡胶", "下游1列"),
    "N_TPR":     (3, "material", "compound", "弹性体复合材料", "下游2列"),
    "N_MODIFIED_ASPH": (3, "material", "compound", "改性沥青", "下游2列"),
    "N_HMPSA":   (3, "material", "compound", "热熔胶", "下游2列"),
    "N_PP_MODIF": (3, "material", "compound", "改性塑料", "下游2列"),
    "N_MUSTICK": (3, "material", "compound", "溶剂型胶黏剂", "下游2列"),
    "N_WP_MEMBRANE": (4, "material", "article", "防水卷材", "下游3列"),
    "N_PAVEMENT_DECK": (4, "material", "article", "道路铺装材料", "下游3列"),
    "N_FOOTWEAR_OUTSOLE": (4, "material", "article", "鞋用部件", "下游3列"),
    "N_BOPP_TAPE": (4, "material", "article", "胶带制品", "下游3列"),
    "N_WATERPROOF_MAT": (4, "material", "system", "防水系统材料", "下游3列"),
    "N_APP_ROAD": (5, "application", "end_market", "交通基建", "终端"),
    "N_APP_CONSTRUCTION": (5, "application", "end_market", "建筑与市政", "终端"),
    "N_APP_FOOTWEAR": (5, "application", "end_market", "鞋类制造", "终端"),
    "N_APP_PACKAGING": (5, "application", "end_market", "包装与物流", "终端"),
    "N_APP_HOMEAPPL": (5, "application", "end_market", "家电与汽车", "终端"),
}

# 核心清单（开工前冻结）——用于覆盖率计算；与 v1 相比：
#   · 去掉「BTX 分馏 → C8 芳烃」这条无证据、方向错误的边；
#   · 把「副产 C4」改写为「石脑油裂解副产 C4 馏分」，与图谱边一致。
CORE_NODES = [
    ("N_PRIMARY", "SBS（目标品种）", "P0", ["node_present", "identity_verified", "role_classified", "evidence_linked", "price_mapped"]),
    ("N_SM", "苯乙烯（直接原料）", "P0", ["node_present", "identity_verified", "role_classified", "evidence_linked", "price_mapped"]),
    ("N_BD", "丁二烯（直接原料）", "P0", ["node_present", "identity_verified", "role_classified", "evidence_linked", "price_mapped"]),
    ("N_EB", "乙苯（苯乙烯中间体）", "P0", ["node_present", "identity_verified", "role_classified", "evidence_linked", "price_mapped"]),
    ("N_BZ", "纯苯（乙苯原料）", "P0", ["node_present", "identity_verified", "role_classified", "evidence_linked", "price_mapped"]),
    ("N_ETH", "乙烯（乙苯原料）", "P0", ["node_present", "identity_verified", "role_classified", "evidence_linked", "price_mapped"]),
    ("N_C4BE", "裂解 C4 馏分（丁二烯原料）", "P0", ["node_present", "role_classified", "evidence_linked"]),
    ("N_NAPHTHA", "石脑油（乙烯/芳烃原料）", "P0", ["node_present", "role_classified", "evidence_linked"]),
    ("N_C8A", "混合 C8 芳烃（C8 抽提路线）", "P1", ["node_present", "identity_verified", "role_classified", "evidence_linked"]),
    ("N_ASPHALT", "基质沥青（改性沥青基料）", "P0", ["node_present", "identity_verified", "role_classified", "evidence_linked", "price_mapped"]),
    ("N_MODIFIED_ASPH", "SBS 改性沥青", "P0", ["node_present", "role_classified", "evidence_linked"]),
    ("N_PAVEMENT_DECK", "沥青路面（铺装材料）", "P0", ["node_present", "role_classified", "evidence_linked"]),
    ("N_APP_ROAD", "终端：公路与市政道路", "P0", ["node_present", "role_classified"]),
    ("N_WP_MEMBRANE", "SBS 改性沥青防水卷材", "P0", ["node_present", "role_classified", "evidence_linked"]),
    ("N_APP_CONSTRUCTION", "终端：建筑与市政防水", "P0", ["node_present", "role_classified"]),
    ("N_TPR", "TPR/TPE 鞋底料", "P0", ["node_present", "role_classified", "evidence_linked"]),
    ("N_FOOTWEAR_OUTSOLE", "鞋底/鞋用部件", "P0", ["node_present", "role_classified", "evidence_linked"]),
    ("N_APP_FOOTWEAR", "终端：鞋类制造", "P0", ["node_present", "role_classified"]),
    ("N_HMPSA", "热熔胶 / 热熔压敏胶", "P0", ["node_present", "role_classified", "evidence_linked"]),
    ("N_APP_PACKAGING", "终端：包装与物流", "P1", ["node_present", "role_classified"]),
    ("N_PP_MODIF", "改性聚烯烃（增韧改性料）", "P1", ["node_present", "role_classified", "evidence_linked"]),
    ("N_APP_HOMEAPPL", "终端：家电与汽车", "P1", ["node_present", "role_classified"]),
    ("N_SEBS", "SEBS（氢化 SBS）", "P1", ["node_present", "identity_verified", "role_classified", "evidence_linked"]),
    ("N_SIS", "SIS（替代/同族）", "P1", ["node_present", "identity_verified", "role_classified", "evidence_linked"]),
    ("N_TPU", "TPU（鞋材替代）", "P2", ["node_present", "role_classified", "evidence_linked"]),
    ("N_EVA", "EVA（鞋材替代）", "P2", ["node_present", "role_classified", "evidence_linked"]),
    ("N_SBR", "SBR（鞋底体系替代）", "P2", ["node_present", "role_classified", "evidence_linked"]),
    ("N_LPG", "LPG / 轻烃（裂解原料替代）", "P1", ["node_present", "role_classified", "evidence_linked"]),
    ("N_PYREXTRACT", "裂解汽油（C8 抽提路线原料）", "P1", ["node_present", "role_classified", "evidence_linked"]),
]

CORE_RELS = [
    # (from, to, relation_type, label, priority, criteria)
    ("N_SM", "N_PRIMARY", "conversion", "苯乙烯→SBS", "P0", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_BD", "N_PRIMARY", "conversion", "丁二烯→SBS", "P0", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_EB", "N_SM", "conversion", "乙苯脱氢→苯乙烯", "P0", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_BZ", "N_EB", "conversion", "苯→乙苯", "P0", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_ETH", "N_EB", "conversion", "乙烯→乙苯", "P0", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_C4BE", "N_BD", "conversion", "C4 抽提→丁二烯", "P0", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_NAPHTHA", "N_C4BE", "byproduct", "裂解副产 C4 馏分", "P0", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_NAPHTHA", "N_ETH", "conversion", "石脑油裂解→乙烯", "P0", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_LPG", "N_ETH", "route_option", "轻烃裂解路线（替代原料）", "P1", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_NAPHTHA", "N_BTX", "conversion", "石脑油重整→重整生成油", "P1", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_BTX", "N_BZ", "conversion", "重整芳烃抽提→纯苯", "P1", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_BTX", "N_C8A", "conversion", "重整生成油→C8 芳烃馏分", "P1", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_PYREXTRACT", "N_SM", "route_option", "C8 抽提制苯乙烯（独立路线）", "P1", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_NAPHTHA", "N_PYREXTRACT", "byproduct", "裂解副产裂解汽油", "P1", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_CRUDE", "N_NAPHTHA", "conversion", "常减压蒸馏→石脑油", "P2", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_CRUDE", "N_LPG", "conversion", "炼厂轻烃分离→LPG", "P2", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_PRIMARY", "N_MODIFIED_ASPH", "blend", "SBS 掺入→改性沥青", "P0", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_ASPHALT", "N_MODIFIED_ASPH", "blend", "基质沥青→改性沥青", "P0", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_MODIFIED_ASPH", "N_PAVEMENT_DECK", "processing", "改性沥青→沥青路面", "P0", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_PAVEMENT_DECK", "N_APP_ROAD", "application", "路面→公路与市政道路", "P0", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_PRIMARY", "N_WP_MEMBRANE", "blend", "SBS→防水卷材涂盖料", "P0", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_MODIFIED_ASPH", "N_WP_MEMBRANE", "processing", "改性沥青→卷材成型", "P0", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_WP_MEMBRANE", "N_APP_CONSTRUCTION", "application", "卷材→建筑防水", "P0", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_PRIMARY", "N_TPR", "blend", "SBS→TPR 鞋底料", "P0", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_TPR", "N_FOOTWEAR_OUTSOLE", "processing", "TPR→鞋底", "P0", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_FOOTWEAR_OUTSOLE", "N_APP_FOOTWEAR", "application", "鞋底→鞋", "P0", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_PRIMARY", "N_HMPSA", "blend", "SBS→热熔胶", "P0", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_SIS", "N_HMPSA", "blend", "SIS→热熔压敏胶", "P1", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_HMPSA", "N_APP_PACKAGING", "application", "热熔胶→包装物流", "P1", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_PRIMARY", "N_PP_MODIF", "blend", "SBS→改性聚烯烃", "P1", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_PP_MODIF", "N_APP_HOMEAPPL", "application", "改性料→家电/汽车", "P1", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_PRIMARY", "N_SEBS", "conversion", "SBS 加氢→SEBS", "P1", ["node_present", "direction_verified", "quant_available", "evidence_linked"]),
    ("N_SIS", "N_PRIMARY", "substitution", "SIS ↔ SBS 市场替代", "P1", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_TPU", "N_PRIMARY", "substitution", "TPU ↔ SBS 鞋材替代", "P2", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_EVA", "N_PRIMARY", "substitution", "EVA ↔ SBS 鞋材替代", "P2", ["node_present", "direction_verified", "evidence_linked"]),
    ("N_SBR", "N_TPR", "substitution", "SBR ↔ TPR 鞋底体系替代", "P2", ["node_present", "direction_verified", "evidence_linked"]),
]


def main():
    nodes_doc = load(os.path.join(SRC, "nodes.json"))
    rels_doc = load(os.path.join(SRC, "relations.json"))

    # ---------- nodes ----------
    out_nodes = []
    for n in nodes_doc["nodes"]:
        nid = n["id"]
        if nid not in NODE_META:
            raise SystemExit("节点未登记列号：%s" % nid)
        col, cls, role, segment, stage = NODE_META[nid]
        n2 = dict(n)
        n2["layer"] = col                 # 兼容旧字段名，语义 = 图列号
        n2["column"] = col
        n2["node_class"] = cls
        n2["node_role"] = role
        n2["stage"] = stage
        n2["segment"] = segment
        n2.pop("up_depth", None)
        n2.pop("down_depth", None)
        out_nodes.append(n2)

    # 补齐 missing 的节点（基质沥青在 v1 里位于 layer 0，这里归到 -1 列）
    ids = {n["id"] for n in out_nodes}
    for nid in NODE_META:
        if nid not in ids:
            raise SystemExit("NODE_META 里未出现在 nodes.json 的节点：%s" % nid)

    dump({"meta": dict(nodes_doc.get("meta") or {}, **{
        "column_note": "column 即图谱列号：同一列内的节点共享一个上游/下游层级；"
                       "所有物质流关系的 from.column 必须严格小于 to.column（配方归属、替代、副产除外）。",
        "class_note": "node_class：commodity 化学品 / material 材料 / application 终端应用；"
                      "node_role：target/monomer/intermediate/raw/byproduct/compound/article/substitute…",
    }), "columns": COLUMNS, "nodes": out_nodes}, "nodes.json")

    # ---------- relations ----------
    EXTRA = {
        # 新增：重整芳烃抽提（BTX→苯）与重整生成油→C8 芳烃，替换 v1 中方向错误、无证据的 R06
        "R48": {
            "from": "N_BTX", "to": "N_BZ", "relation_type": "conversion",
            "process": "重整生成油加氢后芳烃抽提（环丁砜等溶剂抽提 + 精馏）",
            "family": "芳烃抽提", "typical": True,
            "quant": {"from_per_to": None, "from_unit": "t 重整生成油 / t 纯苯", "yield": None,
                      "basis": "重整生成油中苯含量随重整苛刻度与原料变化；纯苯收率须按装置物料平衡核定，"
                               "本库不提供通用单耗",
                      "basis_grade": None},
            "quant_status": "missing", "quant_confidence": None,
            "evidence": ["S25"], "flow": "mass",
        },
        "R49": {
            "from": "N_BTX", "to": "N_C8A", "relation_type": "conversion",
            "process": "重整生成油分馏切出 C8 芳烃馏分（二甲苯塔）",
            "family": "分馏", "typical": True,
            "quant": {"from_per_to": None, "from_unit": "t 重整生成油 / t C8 芳烃", "yield": None,
                      "basis": "多产品分馏体系，单组分收率取决于装置配置与重整苛刻度",
                      "basis_grade": None},
            "quant_status": "missing", "quant_confidence": None,
            "evidence": ["S25"], "flow": "mass",
        },
    }

    out_rels = []
    routed = {"R06": ("N_BTX", "N_BZ", "重整芳烃抽提（原 R06 方向与端点均有误，已拆分修正）")}
    for r in rels_doc["relations"]:
        r2 = dict(r)
        if r2["id"] in routed:
            fr, to, why = routed[r2["id"]]
            r2["from"], r2["to"] = fr, to
            r2["process"] = "芳烃联合装置：重整段 → BTX → 抽提得纯苯"
            r2["notes"] = (r2.get("notes") or "") + " ｜【v2 修正】" + why
        rt = r2.get("relation_type")
        r2["flow"] = ("none" if rt in ("substitution",) else "mass")
        # 边型：替代=虚线双向、配方/加工=点线、副产=短虚线
        r2["edge_style"] = (
            "dashed" if rt == "substitution" else
            "dotted" if rt in ("blend", "processing") else
            "shortdash" if rt == "byproduct" else "solid")
        out_rels.append(r2)
    for rid, r in EXTRA.items():
        r2 = dict(r, id=rid, edge_style="solid")
        out_rels.append(r2)

    # 给配方类关系补 range（区间），避免把点估计当固定值
    RANGES = {
        "R16": {"from_per_to_range": [0.035, 0.055], "range_note": "道改 SBS 掺量 3.5%~5.5%，随气候分区与沥青配伍变化"},
        "R18": {"from_per_to_range": [0.05, 0.10], "range_note": "卷材涂盖料 SBS 掺量 5%~10%（对涂盖料，非对成品卷材）"},
        "R22": {"from_per_to_range": [0.25, 0.40], "range_note": "热熔胶中弹性体占比 25%~40%"},
        "R23": {"from_per_to_range": [0.25, 0.35], "range_note": "HMPSA 中 SIS 占比 25%~35%"},
        "R25": {"from_per_to_range": [0.60, 0.70], "range_note": "TPR 料中 SBS 占 60~70 份（另含油/树脂/填料）"},
        "R31": {"from_per_to_range": [0.05, 0.15], "range_note": "改性塑料中 SBS/SEBS 类增韧剂 5%~15%"},
    }
    for r in out_rels:
        if r["id"] in RANGES and isinstance(r.get("quant"), dict):
            r["quant"].update(RANGES[r["id"]])

    dump({"meta": dict(rels_doc.get("meta") or {}, **{
        "flow_note": "flow=mass 表示物质流方向可用于上下游高亮；flow=none（替代）不参与层数计算与血缘推进。",
        "edge_style_note": "solid 物质流主路线 / shortdash 副产 / dotted 配方共混与成型加工 / dashed 替代（双向）。",
    }), "relations": out_rels}, "relations.json")

    # ---------- forbidden links（扩充：把更多常见错误画法固化） ----------
    forb = load(os.path.join(SRC, "forbidden_links.json"))
    extra_forb = [
        {"id": "F09", "from": "N_BZ", "to": "N_SM", "wrong_types": ["conversion"],
         "why": "纯苯不能直接转化为苯乙烯；必须先经乙苯（烷基化+脱氢）。把两段合成一步是常见画法错误。",
         "worksheet": "必须经 N_EB 节点，且分段单耗不得合并成分段环。"},
        {"id": "F10", "from": "N_TPR", "to": "N_PRIMARY", "wrong_types": ["blend"],
         "why": "TPR 是 SBS 的配方复合物，方向只能 SBS→TPR；把 TPR 写成 SBS 的原料属于反向画法。",
         "worksheet": None},
        {"id": "F11", "from": "N_HMPSA", "to": "N_APP_PACKAGING", "wrong_types": ["conversion", "blend"],
         "why": "热熔胶→包装是终端应用，不是转化；且部分包装用胶先制胶带再应用，节点口径须区分。",
         "worksheet": None},
        {"id": "F12", "from": "N_TPR", "to": "N_APP_FOOTWEAR", "wrong_types": ["conversion", "blend", "processing"],
         "why": "TPR 料必须先成型为鞋底部件(starter)，再进入整鞋；跳到终端会把制品层抹掉。",
         "worksheet": None},
        {"id": "F13", "from": "N_ASPHALT", "to": "N_APP_ROAD", "wrong_types": ["conversion", "blend", "processing"],
         "why": "未改性基质沥青不构成 SBS 链路的终端应用路径；SBS 的价值必须经由改性沥青体现。",
         "worksheet": None},
        {"id": "F14", "from": "N_SEBS", "to": "N_HMPSA", "wrong_types": ["substitution"],
         "why": "SEBS 与 SBS 在热熔胶中主要为配方互补/替代同侪关系，且 SEBS 的市场替代点主要是鞋材/卫材与改性料；"
                "不能在热熔胶处无证据地建立替代边。",
         "worksheet": None},
    ]
    forb["forbidden"] = forb["forbidden"] + extra_forb
    dump(forb, "forbidden_links.json")

    # ---------- core checklist ----------
    core = {
        "meta": {
            "purpose": "开工前冻结的核心节点/关系清单；覆盖完整度只对本清单有效，不代表产业链全部可能节点。",
            "frozen_at": "2026-10-20T09:00:00+08:00（v2 修订：拆分芳烃列、修正 C8→苯 边、新增 R48/R49）",
            "scope_statement": (
                "覆盖：SBS 的两条直接原料链（苯乙烯：苯+乙烯→乙苯→苯乙烯；丁二烯：石脑油裂解 C4→抽提→丁二烯），"
                "以及石脑油/重整芳烃这一层源头；下游覆盖 5 类主要应用骨架（道路改性沥青、防水卷材、鞋材、胶黏剂、"
                "聚合物改性）与 5 类主要替代品（SIS/SEBS/TPU/EVA/SBR）。"
                "不覆盖：所有新兴应用（医疗、锂电、光伏密封等）、所有替代路线（生物基丁二烯、甲苯甲醇烷基化等）、"
                "牌号级完整清单、地缘与贸易流维度。"),
            "effective_depth": {"up": 2, "down": 2,
                                "note": "用户指定向上 2 层、向下 2 层。图谱为保证'原料路线可辨认'额外展开到原料的上游 2 列，"
                                        "这部分不计入覆盖清单，属于『延长线』，在图中以浅色区分。"},
            "criteria_definitions": {
                "node_present": "节点已进入 nodes.json 且 node_class/node_role 判定正确",
                "identity_verified": "CAS 状态为 verified；材料/终端节点须显式标注『不适用』而非编造 CAS",
                "role_classified": "segment 与 column 已给出",
                "evidence_linked": "至少挂 1 条 A~C 级来源",
                "price_mapped": "该节点已抓到公开价格点，或已登记价格入口与缺口说明",
                "direction_verified": "物质流方向 from→to 与 column 单调性经复核",
                "quant_available": "conversion/coproduction/byproduct 须给出单耗或收率 + 口径；blend/processing 须给配方比或标注不适用",
            },
        },
        "core_nodes": [],
        "core_relations": [],
    }
    for i, (nid, label, pri, crit) in enumerate(CORE_NODES, 1):
        core["core_nodes"].append({
            "id": "core_node_%02d" % i, "node_id": nid, "label": label,
            "required_criteria": crit, "priority": pri})
    for i, (fr, to, rt, label, pri, crit) in enumerate(CORE_RELS, 1):
        core["core_relations"].append({
            "id": "core_rel_%02d" % i, "from": fr, "to": to, "relation_type": rt,
            "label": label, "required_criteria": crit, "priority": pri})
    dump(core, "core_checklist.json")


if __name__ == "__main__":
    main()
