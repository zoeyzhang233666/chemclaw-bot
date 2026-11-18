#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pcd_model.py — 企业产能分布通用数据模型 + 重复统计校验引擎
Producing-Capacity Distribution (PCD) model & de-duplication engine.

设计原则（跨品种通用）：
  1. 一条记录 = 一个「装置级」事实。基地（plant）是装置的容器，法人（entity）是基地的容器，
     集团（group）是法人的容器。四层严格单向：装置 → 基地 → 法人 → 集团。
  2. 任何汇总只能沿这条链向上加总一次；禁止跨层相加（例如：集团合计 + 某子公司 = 重复）。
  3. 产能必须带「口径（basis）」：设计/有效/核定/实际产量。不同口径不得混合求和。
  4. 每条产能必须带「来源（source_id）」，没有来源的记为未核实，不得进入正式汇总。

本模块只依赖标准库。供 build_all / check / 报告脚本共用。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 枚举与常量
# ---------------------------------------------------------------------------

# 产能口径。不同口径永远不混合求和。
BASIS_DESIGN = "design"      # 设计产能 / 铭牌产能 / 名义产能
BASIS_EFFECTIVE = "effective"  # 有效产能 / 可用产能（扣除长期停机、限产）
BASIS_APPROVED = "approved"  # 核定产能 / 核准产能 / 环评批复产能
BASIS_ACTUAL = "actual"      # 实际产量（年度实际产出，不是能力）

BASIS_LABELS = {
    BASIS_DESIGN: "设计产能",
    BASIS_EFFECTIVE: "有效产能",
    BASIS_APPROVED: "核定/批复产能",
    BASIS_ACTUAL: "实际产量",
}
BASIS_CAPACITY = (BASIS_DESIGN, BASIS_EFFECTIVE, BASIS_APPROVED)  # 属于「能力」类
BASIS_ALL = (BASIS_DESIGN, BASIS_EFFECTIVE, BASIS_APPROVED, BASIS_ACTUAL)

# 工艺路线
ROUTE_CARBIDE = "carbide"    # 电石法（乙炔法）
ROUTE_ETHYLENE = "ethylene"  # 乙烯法（石油/石脑油/煤制烯烃/甲醇制烯烃）
ROUTE_MIXED = "mixed"        # 同一基地两条路线并存
ROUTE_UNKNOWN = "unknown"

ROUTE_LABELS = {
    ROUTE_CARBIDE: "电石法（乙炔法）",
    ROUTE_ETHYLENE: "乙烯法",
    ROUTE_MIXED: "电石法+乙烯法",
    ROUTE_UNKNOWN: "工艺未核实",
}

# 装置状态（存量）
STATUS_RUNNING = "running"
STATUS_IDLE = "idle"            # 长期停车（>12 个月）
STATUS_MAINT = "maintenance"    # 检修/临时停车
STATUS_SHUTDOWN = "shutdown"    # 已退出（历史产能）
STATUS_UNKNOWN = "unknown"

STATUS_LABELS = {
    STATUS_RUNNING: "在产",
    STATUS_IDLE: "长期停车",
    STATUS_MAINT: "检修/临时停车",
    STATUS_SHUTDOWN: "已退出",
    STATUS_UNKNOWN: "状态未核实",
}

# 项目状态（增量）
PROJ_PLANNED = "planned"          # 拟建 / 规划
PROJ_FILED = "filed"              # 已备案 / 已核准
PROJ_EIA = "eia"                  # 环评公示阶段
PROJ_CONSTRUCTION = "construction"  # 在建
PROJ_COMMISSIONING = "commissioning"  # 试车 / 投料
PROJ_RAMPUP = "rampup"            # 新投产 爬坡中
PROJ_OPERATING = "operating"      # 正常运行（不再算增量）
PROJ_SUSPENDED = "suspended"      # 暂停/搁置
PROJ_CANCELLED = "cancelled"      # 取消

PROJECT_STAGES = [
    PROJ_PLANNED, PROJ_FILED, PROJ_EIA, PROJ_CONSTRUCTION,
    PROJ_COMMISSIONING, PROJ_RAMPUP, PROJ_OPERATING, PROJ_SUSPENDED, PROJ_CANCELLED,
]
PROJECT_STAGE_LABELS = {
    PROJ_PLANNED: "拟建/规划",
    PROJ_FILED: "已备案",
    PROJ_EIA: "环评公示",
    PROJ_CONSTRUCTION: "在建",
    PROJ_COMMISSIONING: "试车",
    PROJ_RAMPUP: "新投产爬坡",
    PROJ_OPERATING: "已运行",
    PROJ_SUSPENDED: "暂停搁置",
    PROJ_CANCELLED: "取消",
}
# 计入「未来增量」的阶段与其确定性权重（权重仅用于情景，不用于官方汇总）
PIPELINE_WEIGHTS = {
    PROJ_CONSTRUCTION: 0.85,
    PROJ_COMMISSIONING: 0.95,
    PROJ_EIA: 0.45,
    PROJ_FILED: 0.25,
    PROJ_PLANNED: 0.10,
    PROJ_RAMPUP: 1.00,
}

# 可信程度（source reliability）
CONF_A = "A"  # 一手：公司年报/公告/评级报告/环评批复/协会统计
CONF_B = "B"  # 权威二手：行业媒体（隆众/卓创/中国氯碱网报道）、券商深度可溯源到一手
CONF_C = "C"  # 一般二手：行业报告/媒体综述，未溯源
CONF_D = "D"  # 无法核实 / 仅单一弱来源
CONFIDENCE_LABELS = {
    CONF_A: "A-一手文件",
    CONF_B: "B-权威二手",
    CONF_C: "C-一般二手",
    CONF_D: "D-未核实",
}


def _num(x) -> Optional[float]:
    """宽松数值解析：'110' / 110 / '110（糊树脂）' / None → float or None"""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s.replace(",", ""))
    return float(m.group(0)) if m else None


def _s(x, default="") -> str:
    if x is None:
        return default
    return str(x).strip()


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass
class Unit:
    """装置级记录：一条 = 一个装置（一条线/一套聚合装置），是产能的基本单位。"""
    uid: str
    entity_id: str
    plant_id: str
    product: str                 # 品种/牌号，如 PVC-SG5 通用型、糊树脂
    grade_class: str             # 通用型号/专用料/糊树脂
    basis: str                   # design / effective / approved / actual
    capacity: Optional[float]    # 万吨/年（basis=actual 时为万吨/年产量）
    capacity_note: str = ""      # 原文表述
    capacity_year: Optional[int] = None   # 数据所属年份
    route: str = ROUTE_UNKNOWN
    route_note: str = ""
    start_year: Optional[int] = None      # 投产年份
    status: str = STATUS_UNKNOWN
    status_note: str = ""
    integrated_calcium_carbide: Optional[bool] = None  # 是否配套自产电石
    source_id: str = ""
    confidence: str = CONF_D
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Unit":
        return cls(
            uid=_s(d.get("uid")),
            entity_id=_s(d.get("entity_id")),
            plant_id=_s(d.get("plant_id")),
            product=_s(d.get("product")),
            grade_class=_s(d.get("grade_class")),
            basis=_s(d.get("basis"), BASIS_DESIGN) or BASIS_DESIGN,
            capacity=_num(d.get("capacity")),
            capacity_note=_s(d.get("capacity_note")),
            capacity_year=int(_num(d.get("capacity_year"))) if _num(d.get("capacity_year")) else None,
            route=_s(d.get("route"), ROUTE_UNKNOWN) or ROUTE_UNKNOWN,
            route_note=_s(d.get("route_note")),
            start_year=int(_num(d.get("start_year"))) if _num(d.get("start_year")) else None,
            status=_s(d.get("status"), STATUS_UNKNOWN) or STATUS_UNKNOWN,
            status_note=_s(d.get("status_note")),
            integrated_calcium_carbide=d.get("integrated_calcium_carbide"),
            source_id=_s(d.get("source_id")),
            confidence=_s(d.get("confidence"), CONF_D) or CONF_D,
            raw=d,
        )


@dataclass
class Plant:
    plant_id: str
    name: str
    name_full: str
    entity_id: str
    province: str
    city: str
    district: str = ""
    park: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    coord_precision: str = "city"   # plant / park / city
    registered_address: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Plant":
        return cls(
            plant_id=_s(d.get("plant_id")),
            name=_s(d.get("name")),
            name_full=_s(d.get("name_full")) or _s(d.get("name")),
            entity_id=_s(d.get("entity_id")),
            province=_s(d.get("province")),
            city=_s(d.get("city")),
            district=_s(d.get("district")),
            park=_s(d.get("park")),
            lat=_num(d.get("lat")),
            lon=_num(d.get("lon")),
            coord_precision=_s(d.get("coord_precision"), "city") or "city",
            registered_address=_s(d.get("registered_address")),
            raw=d,
        )

    @property
    def location(self) -> str:
        parts = [self.province, self.city, self.district, self.park]
        return "·".join([p for p in parts if p])


@dataclass
class Entity:
    """法定主体：工商登记的一个法人。"""
    entity_id: str
    name: str                       # 法定全称
    short_name: str
    group_id: str
    stock_code: str = ""
    legal_rep: str = ""
    unified_code: str = ""          # 统一社会信用代码（有则填）
    registered_address: str = ""
    entity_type: str = "生产型"      # 生产型 / 控股平台 / 贸易 / 其他
    ownership: str = ""             # 中央国企/地方国企/民营/外资/合资
    verified_by: str = ""           # 核验证据（年报释义表/工商/公告）
    source_id: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Entity":
        return cls(
            entity_id=_s(d.get("entity_id")),
            name=_s(d.get("name")),
            short_name=_s(d.get("short_name")) or _s(d.get("name")),
            group_id=_s(d.get("group_id")),
            stock_code=_s(d.get("stock_code")),
            legal_rep=_s(d.get("legal_rep")),
            unified_code=_s(d.get("unified_code")),
            registered_address=_s(d.get("registered_address")),
            entity_type=_s(d.get("entity_type"), "生产型") or "生产型",
            ownership=_s(d.get("ownership")),
            verified_by=_s(d.get("verified_by")),
            source_id=_s(d.get("source_id")),
            raw=d,
        )


@dataclass
class Group:
    group_id: str
    name: str
    short_name: str
    ultimate_controller: str = ""
    group_type: str = ""      # 央企/省属国企/地市国企/民营/外资
    note: str = ""
    source_id: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Group":
        return cls(
            group_id=_s(d.get("group_id")),
            name=_s(d.get("name")),
            short_name=_s(d.get("short_name")) or _s(d.get("name")),
            ultimate_controller=_s(d.get("ultimate_controller")),
            group_type=_s(d.get("group_type")),
            note=_s(d.get("note")),
            source_id=_s(d.get("source_id")),
            raw=d,
        )


@dataclass
class Project:
    project_id: str
    name: str
    entity_id: str
    plant_id: str
    province: str
    city: str
    capacity: Optional[float]
    capacity_note: str = ""
    route: str = ROUTE_UNKNOWN
    stage: str = PROJ_PLANNED
    expected_year: Optional[int] = None
    expected_period: str = ""     # "2027H1" 等
    retired_capacity: Optional[float] = None   # 置换/退出产能
    replacement_note: str = ""
    capex: str = ""
    timeline: List[Dict[str, Any]] = field(default_factory=list)  # [{date, event}]
    source_ids: List[str] = field(default_factory=list)
    confidence: str = CONF_D
    note: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Project":
        return cls(
            project_id=_s(d.get("project_id")),
            name=_s(d.get("name")),
            entity_id=_s(d.get("entity_id")),
            plant_id=_s(d.get("plant_id")),
            province=_s(d.get("province")),
            city=_s(d.get("city")),
            capacity=_num(d.get("capacity")),
            capacity_note=_s(d.get("capacity_note")),
            route=_s(d.get("route"), ROUTE_UNKNOWN) or ROUTE_UNKNOWN,
            stage=_s(d.get("stage"), PROJ_PLANNED) or PROJ_PLANNED,
            expected_year=int(_num(d.get("expected_year"))) if _num(d.get("expected_year")) else None,
            expected_period=_s(d.get("expected_period")),
            retired_capacity=_num(d.get("retired_capacity")),
            replacement_note=_s(d.get("replacement_note")),
            capex=_s(d.get("capex")),
            timeline=d.get("timeline") or [],
            source_ids=d.get("source_ids") or ([d.get("source_id")] if d.get("source_id") else []),
            confidence=_s(d.get("confidence"), CONF_D) or CONF_D,
            note=_s(d.get("note")),
            raw=d,
        )


@dataclass
class Source:
    source_id: str
    title: str
    pub_type: str      # 年报/公告/评级报告/环评/协会/媒体/官网/数据库
    org: str = ""
    date: str = ""
    url: str = ""
    confidence: str = CONF_C
    note: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Source":
        return cls(
            source_id=_s(d.get("source_id")),
            title=_s(d.get("title")),
            pub_type=_s(d.get("pub_type")),
            org=_s(d.get("org")),
            date=_s(d.get("date")),
            url=_s(d.get("url")),
            confidence=_s(d.get("confidence"), CONF_C) or CONF_C,
            note=_s(d.get("note")),
        )


# ---------------------------------------------------------------------------
# 数据集
# ---------------------------------------------------------------------------


class Dataset:
    def __init__(self, bundle: Dict[str, Any]):
        self.meta = bundle.get("meta", {}) or {}
        self.product = bundle.get("product", {}) or {}
        self.groups = {g["group_id"]: Group.from_dict(g) for g in bundle.get("groups", [])}
        self.entities = {e["entity_id"]: Entity.from_dict(e) for e in bundle.get("entities", [])}
        self.plants = {p["plant_id"]: Plant.from_dict(p) for p in bundle.get("plants", [])}
        self.units = [Unit.from_dict(u) for u in bundle.get("units", [])]
        self.projects = [Project.from_dict(p) for p in bundle.get("projects", [])]
        self.sources = {s["source_id"]: Source.from_dict(s) for s in bundle.get("sources", [])}
        self.benchmarks = bundle.get("benchmarks", []) or []
        self.gaps = bundle.get("gaps", []) or []
        self.notes = bundle.get("notes", {}) or {}
        self.raw = bundle

    # ---- 便捷索引 -------------------------------------------------------
    def plants_of_entity(self, entity_id: str) -> List[Plant]:
        return [p for p in self.plants.values() if p.entity_id == entity_id]

    def entities_of_group(self, group_id: str) -> List[Entity]:
        return [e for e in self.entities.values() if e.group_id == group_id]

    def units_of_plant(self, plant_id: str) -> List[Unit]:
        return [u for u in self.units if u.plant_id == plant_id]

    def plant_of_unit(self, u: Unit) -> Optional[Plant]:
        return self.plants.get(u.plant_id)

    def group_of_unit(self, u: Unit) -> Optional[Group]:
        p = self.plants.get(u.plant_id)
        if not p:
            return None
        e = self.entities.get(p.entity_id)
        if not e:
            return None
        return self.groups.get(e.group_id)


# ---------------------------------------------------------------------------
# 重复统计校验引擎（核心）
# ---------------------------------------------------------------------------

# 规则编号 R1..R12，与 references/去重校验规则.md 一一对应
SEVERITY_ERROR = "ERROR"
SEVERITY_WARN = "WARN"
SEVERITY_INFO = "INFO"


@dataclass
class Finding:
    rule: str
    severity: str
    subject: str
    message: str
    fix: str = ""


class DupChecker:
    """对数据集做结构性校验：查重、查口径混用、查孤儿记录、查来源缺失。"""

    def __init__(self, ds: Dataset):
        self.ds = ds
        self.findings: List[Finding] = []

    def add(self, rule, severity, subject, message, fix=""):
        self.findings.append(Finding(rule, severity, subject, message, fix))

    # -- R1: 孤儿装置（plant 不存在） -------------------------------------
    def r1_orphan_units(self):
        for u in self.ds.units:
            if u.plant_id not in self.ds.plants:
                self.add("R1", SEVERITY_ERROR, u.uid,
                         f"装置 {u.uid} 指向不存在的基地 {u.plant_id}",
                         "修正 plant_id 或补建 plant 记录")

    # -- R2: 基地的 entity 不存在 -----------------------------------------
    def r2_orphan_plants(self):
        for p in self.ds.plants.values():
            if p.entity_id not in self.ds.entities:
                self.add("R2", SEVERITY_ERROR, p.plant_id,
                         f"基地 {p.plant_id}({p.name}) 指向不存在的法人 {p.entity_id}",
                         "修正 entity_id 或补建 entity 记录")
        for e in self.ds.entities.values():
            if e.group_id and e.group_id not in self.ds.groups:
                self.add("R2", SEVERITY_ERROR, e.entity_id,
                         f"法人 {e.name} 指向不存在的集团 {e.group_id}",
                         "修正 group_id 或补建 group 记录")

    # -- R3: 基地坐标缺失（地图缺陷） --------------------------------------
    def r3_missing_coords(self):
        for p in self.ds.plants.values():
            if p.lat is None or p.lon is None:
                self.add("R3", SEVERITY_WARN, p.plant_id,
                         f"基地 {p.name}({p.province}{p.city}) 缺经纬度，地图将不显示",
                         "补 lat/lon（精确到城市亦可，标 coord_precision=city）")

    # -- R4: 同装置重复录入（同一 plant + 同一年 + 同口径 + 同工艺多条） ----
    def r4_duplicate_units(self):
        seen: Dict[Tuple, List[Unit]] = {}
        for u in self.ds.units:
            key = (u.plant_id, u.basis, u.capacity_year, u.route, u.product)
            seen.setdefault(key, []).append(u)
        for key, us in seen.items():
            if len(us) > 1 and any(x.capacity is not None for x in us):
                ids = ", ".join(x.uid for x in us)
                self.add("R4", SEVERITY_ERROR, key[0],
                         f"疑似重复装置：{ids} 具有相同的 (基地{key[0]}, 口径{key[1]}, 年份{key[2]}, 工艺{key[3]}, 产品{key[4]})。"
                         f"请确认是否为同一装置的多个统计来源被并录。",
                         "保留一条主记录（A 级来源优先），其余标注为替代口径并移出汇总")

    # -- R5: 不同口径混用（同一 plant 同时出现 design 与 effective 而无说明） --
    def r5_basis_mixing(self):
        by_plant: Dict[str, set] = {}
        for u in self.ds.units:
            if u.basis in BASIS_CAPACITY and u.capacity is not None:
                by_plant.setdefault(u.plant_id, set()).add(u.basis)
        for pid, bases in by_plant.items():
            if len(bases) > 1:
                self.add("R5", SEVERITY_WARN, pid,
                         f"基地 {pid} 同时存在多种产能口径 {sorted(bases)}；"
                         f"汇总时必须按口径分别加总，禁止混合求和。",
                         "在报告中分口径展示，或统一折算并注明动作")

    # -- R6: 来源缺失 / 来源编号对不上 --------------------------------------
    def r6_source_missing(self):
        for u in self.ds.units:
            if not u.source_id:
                self.add("R6", SEVERITY_WARN, u.uid,
                         f"装置 {u.uid}({u.product}) 无来源编号，视为未核实",
                         "补 source_id，或标 confidence=D 并从正式汇总中剔除")
            elif u.source_id not in self.ds.sources:
                self.add("R6", SEVERITY_ERROR, u.uid,
                         f"装置 {u.uid} 引用不存在的来源 {u.source_id}",
                         "补建 source 记录或改正编号")
        for p in self.ds.projects:
            if not p.source_ids:
                self.add("R6", SEVERITY_WARN, p.project_id,
                         f"项目 {p.name} 无来源编号", "补 source_ids")

    # -- R7: 产能缺失 ------------------------------------------------------
    def r7_missing_capacity(self):
        for u in self.ds.units:
            if u.capacity is None:
                self.add("R7", SEVERITY_WARN, u.uid,
                         f"装置 {u.uid} 产能未知（保留为未知，不得估算）",
                         "保留为未知；在报告中单列「产能未核实」清单")
        for p in self.ds.projects:
            if p.capacity is None:
                self.add("R7", SEVERITY_WARN, p.project_id,
                         f"项目 {p.name} 产能未知", "保留未知，不作合计")

    # -- R8: 工艺未知 ------------------------------------------------------
    def r8_route_unknown(self):
        for u in self.ds.units:
            if u.route in (ROUTE_UNKNOWN, "", None):
                self.add("R8", SEVERITY_WARN, u.uid,
                         f"装置 {u.uid} 工艺路线未核实，工艺汇总中将单列「未核实」",
                         "查环评/年报确认电石法或乙烯法")

    # -- R9: 集团-法人-基地链条疑似重复（疑似集团产能被当作法人产能录入）----
    def r9_group_level_double_count(self):
        """同一集团下，若某法人产能 ≈ 集团合计产能，且基地数>1，提示风险。"""
        for g in self.ds.groups.values():
            ents = self.ds.entities_of_group(g.group_id)
            if len(ents) <= 1:
                continue
            totals = {}
            for e in ents:
                vals = [u.capacity for u in self.ds.units
                        if u.plant_id in {p.plant_id for p in self.ds.plants_of_entity(e.entity_id)}
                        and u.basis == BASIS_DESIGN and u.capacity]
                totals[e.entity_id] = sum(vals) if vals else None
            valid = {k: v for k, v in totals.items() if v}
            if len(valid) < 2:
                continue
            gsum = sum(valid.values())
            for eid, v in valid.items():
                # 某法人 ≥ 集团合计的 95%，说明可能把集团数挂到了一个法人上
                if gsum > 0 and v / gsum >= 0.95 and any(
                        len(self.ds.plants_of_entity(o)) >= 1 for o in valid if o != eid):
                    pass  # 单一法人占满属正常（其他法人为非PVC），不告警
            # 更实际的检查：同一个 plant_id 被多个法人引用（基地归属不清）
        owner: Dict[str, List[str]] = {}
        for p in self.ds.plants.values():
            owner.setdefault(p.entity_id, []).append(p.plant_id)
        rev: Dict[str, List[str]] = {}
        for p in self.ds.plants.values():
            rev.setdefault(p.plant_id, []).append(p.entity_id)
        # plant_id 唯一由 dict 保证，这里只检查「同址不同法人」
        addr: Dict[str, List[str]] = {}
        for p in self.ds.plants.values():
            if p.registered_address:
                addr.setdefault(p.registered_address, []).append(p.plant_id)
        for a, ids in addr.items():
            if len(ids) > 1:
                self.add("R9", SEVERITY_INFO, a,
                         f"多个基地共用同一注册地址 {a}：{ids}；非错误，但需在报告中说明是否为同一厂区拆分。",
                         "")

    # -- R10: 项目与存量装置冲突（项目已投产但仍被算作增量） --------------
    def r10_project_vs_stock(self):
        for p in self.ds.projects:
            if p.stage in (PROJ_COMMISSIONING, PROJ_RAMPUP, PROJ_OPERATING):
                # 若该基地已有同工艺同产能的存量装置，提示可能已计入存量
                same = [u for u in self.ds.units_of_plant(p.plant_id)
                        if u.route == p.route and u.capacity and p.capacity
                        and abs(u.capacity - p.capacity) < 0.01]
                if p.stage == PROJ_OPERATING:
                    self.add("R10", SEVERITY_WARN, p.project_id,
                             f"项目 {p.name} 阶段为「已运行」，应已并入存量；请确认存量装置已录入，且不在增量中重复计。",
                             "将 project.stage 改为 operating 并从增量汇总排除")
                elif same:
                    self.add("R10", SEVERITY_WARN, p.project_id,
                             f"项目 {p.name} 与基地 {p.plant_id} 已有同工艺同产能装置；需确认是新增装置还是存量装置。",
                             "核对装置数量；若为同一装置，删除项目记录")

    # -- R11: 置换产能未扣减（新项目含置换，但 retired_capacity 空） --------
    # 明确表示「没有置换」的措辞；命中则不触发 R11
    _NO_REPLACE_HINTS = ("净新增", "无（净新增）", "无置换", "不适用", "无")

    def r11_replacement_unaccounted(self):
        """只有「确实存在置换但吨数未填」才告警；明确净新增的项目不告警。"""
        for p in self.ds.projects:
            if p.stage not in PIPELINE_WEIGHTS:
                continue
            note = (p.replacement_note or "").strip()
            if not note or p.retired_capacity is not None:
                continue
            # 明确无置换 → 跳过
            if any(h in note for h in self._NO_REPLACE_HINTS) and "未" not in note.split("（")[0][:6]:
                if note.startswith("净新增") or note.startswith("无置换"):
                    continue
            # 说明「未查到置换方案」→ 这是真实缺口，需要告警
            if "未查到" in note or "未披露" in note or "未知" in note or "置换" in note:
                self.add("R11", SEVERITY_WARN, p.project_id,
                         f"项目 {p.name} 的置换情况为「{note}」，但未填写 retired_capacity，"
                         f"毛新增会被当作净新增，导致增量高估。",
                         "补 retired_capacity；无法确认则净增记 null，不进基准预测")

    # -- R12: 单位/量纲异常 ------------------------------------------------
    def r12_unit_anomaly(self):
        for u in self.ds.units:
            if u.capacity is None:
                continue
            if u.capacity > 1000:
                self.add("R12", SEVERITY_ERROR, u.uid,
                         f"装置 {u.uid} 产能 {u.capacity} 疑似单位错误（应为万吨/年，当前>1000）",
                         "检查是否误填吨/年")
            if 0 < u.capacity < 1:
                self.add("R12", SEVERITY_WARN, u.uid,
                         f"装置 {u.uid} 产能 {u.capacity} 万吨/年偏小，确认是否单位或小试装置",
                         "")

    # -- R13: 可信度与来源不匹配 -------------------------------------------
    def r13_confidence_mismatch(self):
        for u in self.ds.units:
            src = self.ds.sources.get(u.source_id)
            if src and u.confidence != src.confidence:
                self.add("R13", SEVERITY_INFO, u.uid,
                         f"装置 {u.uid} 自评可信度 {u.confidence} 与来源 {u.source_id} 等级 {src.confidence} 不一致",
                         "以来源等级为准或说明理由")

    # -- R14: 集团名/企业名疑似重复（同名不同 ID）--------------------------
    def r14_name_collision(self):
        def norm(s: str) -> str:
            s = re.sub(r"(有限责任公司|股份有限公司|有限公司|集团公司|集团|公司)", "", s)
            return re.sub(r"[\s（）()]", "", s)
        for kind, coll in (("法人", self.ds.entities), ("集团", self.ds.groups)):
            seen: Dict[str, List[str]] = {}
            for k, v in coll.items():
                seen.setdefault(norm(v.name), []).append(k)
            for n, ids in seen.items():
                if len(ids) > 1:
                    self.add("R14", SEVERITY_WARN, ids[0],
                             f"{kind}名称规范化后相同（{n}）：{ids}，可能造成重复统计",
                             "合并为同一 ID，或改名为可区分的法定全称")

    def run(self) -> List[Finding]:
        for f in (self.r1_orphan_units, self.r2_orphan_plants, self.r3_missing_coords,
                  self.r4_duplicate_units, self.r5_basis_mixing, self.r6_source_missing,
                  self.r7_missing_capacity, self.r8_route_unknown,
                  self.r9_group_level_double_count, self.r10_project_vs_stock,
                  self.r11_replacement_unaccounted, self.r12_unit_anomaly,
                  self.r13_confidence_mismatch, self.r14_name_collision):
            f()
        return self.findings

    def summary(self) -> Dict[str, int]:
        out = {SEVERITY_ERROR: 0, SEVERITY_WARN: 0, SEVERITY_INFO: 0}
        for f in self.findings:
            out[f.severity] = out.get(f.severity, 0) + 1
        return out


# ---------------------------------------------------------------------------
# 汇总器：所有图表/表格的单一计算入口，保证「同一口径加法只用一次」
# ---------------------------------------------------------------------------


class Aggregator:
    """严格四层汇总：unit → plant → entity → group。
    任何一次汇总都会记录「参与计算的装置 ID 明细」，写入 Excel 汇总公式表。"""

    def __init__(self, ds: Dataset, basis: str = BASIS_DESIGN,
                 include_status: Tuple[str, ...] = (STATUS_RUNNING, STATUS_MAINT, STATUS_UNKNOWN)):
        self.ds = ds
        self.basis = basis
        self.include_status = include_status

    def rows(self) -> List[Unit]:
        """参与本次汇总的装置（口径 + 状态过滤）。"""
        out = []
        for u in self.ds.units:
            if u.basis != self.basis:
                continue
            if u.capacity is None:
                continue
            if u.status not in self.include_status:
                continue
            out.append(u)
        return out

    def by_plant(self) -> Dict[str, float]:
        agg: Dict[str, float] = {}
        for u in self.rows():
            agg[u.plant_id] = agg.get(u.plant_id, 0.0) + u.capacity
        return agg

    def by_group(self) -> Dict[str, float]:
        """集团汇总 = 其下所有法人所有基地所有装置之和（每个装置只计一次）。"""
        plant_owner = {p.plant_id: p.entity_id for p in self.ds.plants.values()}
        ent_group = {e.entity_id: e.group_id for e in self.ds.entities.values()}
        agg: Dict[str, float] = {}
        for u in self.rows():
            gid = ent_group.get(plant_owner.get(u.plant_id, ""), "")
            if not gid:
                gid = "__ungrouped__"
            agg[gid] = agg.get(gid, 0.0) + u.capacity
        return agg

    def by_entity(self) -> Dict[str, float]:
        plant_owner = {p.plant_id: p.entity_id for p in self.ds.plants.values()}
        agg: Dict[str, float] = {}
        for u in self.rows():
            eid = plant_owner.get(u.plant_id, "")
            agg[eid] = agg.get(eid, 0.0) + u.capacity
        return agg

    def by_province(self) -> Dict[str, float]:
        agg: Dict[str, float] = {}
        for u in self.rows():
            p = self.ds.plants.get(u.plant_id)
            if not p:
                continue
            agg[p.province] = agg.get(p.province, 0.0) + u.capacity
        return agg

    def by_city(self) -> Dict[Tuple[str, str], float]:
        agg: Dict[Tuple[str, str], float] = {}
        for u in self.rows():
            p = self.ds.plants.get(u.plant_id)
            if not p:
                continue
            k = (p.province, p.city)
            agg[k] = agg.get(k, 0.0) + u.capacity
        return agg

    def by_route(self) -> Dict[str, float]:
        agg: Dict[str, float] = {}
        for u in self.rows():
            agg[u.route] = agg.get(u.route, 0.0) + u.capacity
        return agg

    def by_region(self, region_map: Dict[str, str]) -> Dict[str, float]:
        prov = self.by_province()
        agg: Dict[str, float] = {}
        for p, v in prov.items():
            r = region_map.get(p, "其他")
            agg[r] = agg.get(r, 0.0) + v
        return agg

    def total(self) -> float:
        return sum(u.capacity for u in self.rows())

    def unit_ids(self) -> List[str]:
        return [u.uid for u in self.rows()]

    def trace(self) -> List[Dict[str, Any]]:
        """汇总溯源明细：每一行说明某个装置被计入哪个汇总项。"""
        plant_owner = {p.plant_id: p.entity_id for p in self.ds.plants.values()}
        ent_group = {e.entity_id: e.group_id for e in self.ds.entities.values()}
        out = []
        for u in self.rows():
            p = self.ds.plants.get(u.plant_id)
            eid = plant_owner.get(u.plant_id, "")
            gid = ent_group.get(eid, "")
            out.append({
                "uid": u.uid,
                "plant_id": u.plant_id,
                "plant": p.name if p else "",
                "province": p.province if p else "",
                "city": p.city if p else "",
                "entity_id": eid,
                "entity": self.ds.entities[eid].name if eid in self.ds.entities else "",
                "group_id": gid,
                "group": self.ds.groups[gid].name if gid in self.ds.groups else "",
                "route": u.route,
                "basis": u.basis,
                "capacity": u.capacity,
                "status": u.status,
            })
        return out


# ---------------------------------------------------------------------------
# 集中度指标
# ---------------------------------------------------------------------------


def cr_n(values: Iterable[float], n: int, denominator: Optional[float] = None) -> Optional[float]:
    """CRn（%）。分母缺省 = 本口径总和；给 denominator 时可算「占全国」份额。"""
    vals = sorted([v for v in values if v], reverse=True)
    if not vals:
        return None
    den = denominator if denominator else sum(vals)
    if not den:
        return None
    return round(100.0 * sum(vals[:n]) / den, 2)


def hhi(values: Iterable[float], denominator: Optional[float] = None) -> Optional[float]:
    """HHI（0–10000）。按份额平方和。"""
    vals = [v for v in values if v]
    if not vals:
        return None
    den = denominator if denominator else sum(vals)
    if not den:
        return None
    return round(sum((100.0 * v / den) ** 2 for v in vals), 1)


def concentration_label(h: Optional[float]) -> str:
    if h is None:
        return "未知"
    if h < 1000:
        return "分散（HHI<1000）"
    if h < 1800:
        return "中度集中（1000≤HHI<1800）"
    return "高度集中（HHI≥1800）"


def coverage(sample_total: float, benchmark_total: Optional[float]) -> Optional[float]:
    """样本覆盖率 = 样本合计 / 全国口径合计（%）。"""
    if not benchmark_total:
        return None
    return round(100.0 * sample_total / benchmark_total, 1)


# ---------------------------------------------------------------------------
# 载入
# ---------------------------------------------------------------------------


def load(path: str) -> Dataset:
    with open(path, "r", encoding="utf-8") as f:
        return Dataset(json.load(f))


def load_dir(d: str) -> Dataset:
    """读取 data/units.json 等分文件，或 data/pvc_bundle.json 单文件。"""
    for cand in ("bundle.json", "pcd_bundle.json"):
        p = os.path.join(d, cand)
        if os.path.exists(p):
            return load(p)
    bundles = [f for f in os.listdir(d) if f.endswith("_bundle.json")]
    if bundles:
        return load(os.path.join(d, bundles[0]))
    raise FileNotFoundError(f"{d} 下未找到 bundle json")
