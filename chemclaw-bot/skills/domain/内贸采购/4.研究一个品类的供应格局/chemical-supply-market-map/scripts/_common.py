#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_common.py —— 通用化工品供应格局研究：配置装载、校验、指标计算（仅 Python 标准库）

设计原则
  1. 产品无关：所有产品特定内容都来自 project.json + 三个 JSON 数据文件；
  2. 绝不估算：字段缺失一律写 "数据缺口"，不回填、不猜测、不用行业均值顶替；
  3. 向后兼容：缺字段不报错，只降级（例如没有 lat/lon 就不画气泡）。

目录约定（每个项目一个文件夹）
  project.json      品类 / 口径 / 指标 / 工艺 / 策略 / 风险 / 缺口 / 尽调 / 来源
  plants.json       基地级产能表（地图、区域、集中度都从这里算）
  companies.json    集团画像（抽屉、尽调卡）
  projects.json     新建/在建/拟建项目（时间线、净增还原）
"""
import json
import os
import re
import sys
from collections import Counter, OrderedDict

VERSION = "1.0.0"

CONF_LEVELS = ["高", "中高", "中", "中低", "低"]
CONF_ALIAS = {"较高": "高", "偏高": "中高", "中等": "中", "一般": "中", "偏低": "中低",
              "较低": "低", "high": "高", "medium": "中", "mid": "中", "low": "低"}

STATUS_ENUM = ["在产", "爬坡", "达产", "在建", "拟建", "停产", "退出"]
ACTIVITY_ENUM = ["A", "B", "C"]

# 中国省级行政区（按文字长度排列，保证「内蒙古」先于「内蒙」被匹配）
PROVINCES = [
    "内蒙古", "黑龙江", "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林",
    "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东",
    "广西", "海南", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏",
    "新疆", "香港", "澳门", "台湾",
]
PROVINCE_ALIAS = {"内蒙": "内蒙古", "广西壮族": "广西", "宁夏回族": "宁夏",
                  "新疆维吾尔": "新疆", "西藏自治区": "西藏"}
SHORT_PROVINCE = [p for p in PROVINCES if len(p) <= 2]

MISSING = "数据缺口"


# ------------------------------------------------------------------ 控制台
def setup_console():
    """Windows GBK 控制台下也不因中文/符号崩溃。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    return MISSING


# ------------------------------------------------------------------ 读写
def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, "r", encoding="utf-8-sig") as fh:
        raw = fh.read().strip()
    if not raw:
        return default if default is not None else {}
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise SystemExit(f"JSON 解析失败：{path}\n{exc}")


def dump_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)


def write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


# ------------------------------------------------------------------ 兜底默认
def _default_project():
    return {
        "schema_version": 3,
        "project_id": "chem-supply",
        "product": {"name": "本产品", "short": "本产品", "aliases": [], "grades": "",
                    "cas": "", "unit": "万吨/年", "price_unit": "元/吨（含税）", "hs_code": ""},
        "scope": {"geography": "中国大陆", "boundary": "", "base_year": None,
                  "forward_years": [], "report_date": "", "data_cutoff": "", "basis_notes": []},
        "buyer": {"applies": False},
        "metrics": {},
        "verdicts": [],
        "routes": [],
        "routes_note": "",
        "markets": [],
        "region_meta": {},
        "activity_legend": {"A": "交易活跃", "B": "中等活跃", "C": "低活跃"},
        "prices": {"lines": [], "annual": [], "periods": [], "current": [],
                   "outlook": {}, "caveat": ""},
        "strategies": [],
        "supplier_mix": [],
        "risks": [],
        "gaps": [],
        "dd": [],
        "scorecard": [],
        "sources": [],
    }


def load_project(directory):
    """读 project.json 并补齐默认结构（不改写文件）。"""
    path = os.path.join(directory, "project.json")
    if not os.path.exists(path):
        raise SystemExit(f"找不到 project.json：{path}\n先跑 python scripts/new_project.py --dir {directory} ...")
    cfg = load_json(path)
    base = _default_project()
    for key, val in base.items():
        if key not in cfg or cfg[key] is None:
            cfg[key] = val
        elif isinstance(val, dict):
            for sub, subval in val.items():
                cfg[key].setdefault(sub, subval)
    cfg["_dir"] = directory
    return cfg


def load_dataset(directory):
    """装载完整数据集：config + plants + companies + projects。

    两个数据文件都支持两种写法：
      {"plants": [...]}   或  直接是 [...]（便于手工维护）
    """
    cfg = load_project(directory)
    plants = _rows(load_json(os.path.join(directory, "plants.json"), []), "plants")
    companies = _rows(load_json(os.path.join(directory, "companies.json"), []), "companies")
    projects = _rows(load_json(os.path.join(directory, "projects.json"), []), "projects")
    return {"cfg": cfg, "plants": plants, "companies": companies, "projects": projects,
            "dir": directory}


def _rows(data, key):
    if isinstance(data, dict):
        return data.get(key) or data.get("rows") or []
    return data if isinstance(data, list) else []


# ------------------------------------------------------------------ 数值与文本
def num(value, default=0.0):
    """安全转数字；"待确认"/"数据缺口"/None 一律返回 default。"""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    m = re.match(r"^-?\d+(?:\.\d+)?$", text)
    return float(text) if m else default


def fmt_num(value, digits=0):
    if value is None or value == MISSING:
        return MISSING
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if digits <= 0:
        return f"{v:,.0f}"
    return f"{v:,.{digits}f}"


def fmt_pct(value, digits=1):
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return MISSING


def norm_conf(value):
    text = str(value or "中").strip()
    text = CONF_ALIAS.get(text, text)
    return text if text in CONF_LEVELS else "中"


def norm_status(value, default="在产"):
    text = str(value or "").strip()
    return text if text in STATUS_ENUM else default


def infer_status(cap_base, cap_forward):
    """没有显式 status 时，按产能变化推断。"""
    b, f = num(cap_base), num(cap_forward)
    if b > 0 and f > 0:
        return "在产"
    if b == 0 and f > 0:
        return "在建"
    if b > 0 and f == 0:
        return "退出"
    return "拟建"


def province_of(text):
    """从任意文本里识别省份；识别不到返回空串（不猜）。"""
    raw = str(text or "")
    for alias, canon in PROVINCE_ALIAS.items():
        if alias in raw:
            return canon
    for p in PROVINCES:
        if p in raw:
            return p
    return ""


def source_ids(text):
    """从 "S1/S2" 或 "见 S1" 里抽取来源 ID。"""
    return re.findall(r"S\d{1,3}", str(text or ""))


# ------------------------------------------------------------------ 指标
def hhi(values):
    """Herfindahl-Hirschman Index（0–10000，按份额平方和）。"""
    vals = [num(v) for v in values if num(v) > 0]
    total = sum(vals)
    if total <= 0:
        return MISSING
    return round(sum((v / total * 100) ** 2 for v in vals), 1)


def cr_n(values, n=5):
    vals = sorted((num(v) for v in values if num(v) > 0), reverse=True)
    total = sum(vals)
    if total <= 0:
        return MISSING
    return round(sum(vals[:n]) / total * 100, 1)


def region_rollup(plants, province_field="province", key_field="company_id"):
    """按省汇总：产能、企业数、基地数、份额。"""
    rows = OrderedDict()
    for p in plants:
        prov = p.get(province_field) or province_of(p.get("province")) or "未标注"
        row = rows.setdefault(prov, {"province": prov, "capacity_base": 0.0,
                                     "capacity_forward": 0.0, "companies": set(),
                                     "sites": 0, "routes": set()})
        row["capacity_base"] += num(p.get("capacity_base"))
        row["capacity_forward"] += num(p.get("capacity_forward"))
        row["companies"].add(p.get(key_field) or p.get("company_id") or p.get("site"))
        row["sites"] += 1
        if p.get("route"):
            row["routes"].add(p["route"])
    total_base = sum(r["capacity_base"] for r in rows.values()) or 1
    total_fwd = sum(r["capacity_forward"] for r in rows.values()) or 1
    out = []
    for r in rows.values():
        r["group_count"] = len(r["companies"])
        r["share_base"] = r["capacity_base"] / total_base
        r["share_forward"] = r["capacity_forward"] / total_fwd
        r["companies"] = sorted(r["companies"])
        r["routes"] = sorted(r["routes"])
        out.append(r)
    out.sort(key=lambda x: -x["capacity_base"])
    return out


def company_rollup(plants, companies):
    """集团级汇总；画像优先取 companies.json，缺失字段标数据缺口。"""
    by_id = {}
    for p in plants:
        cid = p.get("company_id") or p.get("company") or "未标注"
        row = by_id.setdefault(cid, {"id": cid, "sites": 0, "capacity_base": 0.0,
                                     "capacity_forward": 0.0, "provinces": set(),
                                     "routes": set()})
        row["sites"] += 1
        row["capacity_base"] += num(p.get("capacity_base"))
        row["capacity_forward"] += num(p.get("capacity_forward"))
        if p.get("province"):
            row["provinces"].add(p["province"])
        if p.get("route"):
            row["routes"].add(p["route"])
    profiles = {c.get("id") or c.get("name"): c for c in companies}
    total_base = sum(r["capacity_base"] for r in by_id.values()) or 1
    total_fwd = sum(r["capacity_forward"] for r in by_id.values()) or 1
    out = []
    for cid, row in by_id.items():
        prof = profiles.get(cid, {})
        merged = dict(prof)
        merged.update({
            "id": cid,
            "name": prof.get("name") or cid,
            "sites": row["sites"],
            "capacity_base": row["capacity_base"],
            "capacity_forward": row["capacity_forward"],
            "share_base": row["capacity_base"] / total_base,
            "share_forward": row["capacity_forward"] / total_fwd,
            "provinces": sorted(row["provinces"]),
            "routes": sorted(row["routes"]),
            "output_base": prof.get("output_base", MISSING),
            "utilization": prof.get("utilization", MISSING),
            "has_profile": bool(prof),
        })
        out.append(merged)
    out.sort(key=lambda x: -x["capacity_base"])
    return out


def project_rollup(projects):
    """项目净值还原：毛产能、退出、净影响。"""
    rows = []
    for p in projects:
        gross = num(p.get("capacity"))
        retired = num(p.get("capacity_retired"))
        net_raw = p.get("net")
        if net_raw is not None and str(net_raw).strip() != "" and str(net_raw) not in (MISSING, "待确认"):
            net = num(net_raw)
            net_label = f"{net:+.0f}"
        elif retired > 0:
            net = gross - retired
            net_label = f"{net:+.0f}"
        else:
            net = None
            net_label = "待确认"
        rows.append({
            "id": p.get("id") or p.get("name"),
            "name": p.get("name", ""),
            "company_id": p.get("company_id", ""),
            "province": p.get("province", ""),
            "route": p.get("route", ""),
            "capacity": gross,
            "capacity_retired": retired,
            "type": p.get("type", ""),
            "status": p.get("status", ""),
            "date": p.get("date", ""),
            "year": p.get("year"),
            "step": p.get("step", ""),
            "net": net,
            "net_label": net_label,
            "impact": p.get("impact", ""),
            "source": p.get("source", ""),
        })
    rows.sort(key=lambda x: (str(x["date"]), str(x["id"])))
    return rows


def coverage(sample_capacity, national_capacity):
    """样本覆盖率；全国产能缺失时返回数据缺口而不是瞎算。"""
    nat = num(national_capacity)
    if nat <= 0:
        return MISSING
    return round(num(sample_capacity) / nat * 100, 1)


# ------------------------------------------------------------------ 体检
def validate_dataset(ds):
    """返回 (errors, warnings, stats)。errors 非空即不可交付。"""
    cfg, plants, companies, projects = ds["cfg"], ds["plants"], ds["companies"], ds["projects"]
    errors, warnings = [], []
    stats = {}

    if not cfg["product"]["name"] or cfg["product"]["name"] == "本产品":
        errors.append("product.name 未填写")
    if not cfg["scope"].get("report_date"):
        warnings.append("scope.report_date 为空（报告会把「数据截止」写成数据缺口）")
    if not plants:
        errors.append("plants.json 为空：产能表/地图/区域/集中度全部无法计算")
    if not cfg["sources"]:
        errors.append("sources 为空：所有数字都无法回溯")

    # plants
    seen_ids = set()
    no_cap = 0
    no_source = 0
    bad_prov = 0
    bad_status = 0
    no_geo = 0
    for i, p in enumerate(plants, 1):
        pid = p.get("id") or f"row{i}"
        if pid in seen_ids:
            errors.append(f"plants.json 第 {i} 行 id 重复：{pid}")
        seen_ids.add(pid)
        if num(p.get("capacity_base")) == 0 and num(p.get("capacity_forward")) == 0:
            no_cap += 1
        if not p.get("source"):
            no_source += 1
        if not p.get("province"):
            warnings.append(f"plants.json 第 {i} 行缺少 province（{pid}）")
        if p.get("lat") is None or p.get("lon") is None:
            no_geo += 1
        st = p.get("status")
        if st and st not in STATUS_ENUM:
            bad_status += 1
            warnings.append(f"plants.json 第 {i} 行 status 不在枚举内：{st}")

    stats["plants"] = len(plants)
    stats["plants_without_capacity"] = no_cap
    stats["plants_without_source"] = no_source
    stats["plants_without_geo"] = no_geo
    stats["plants_bad_status"] = bad_status
    if no_source:
        warnings.append(f"{no_source} 个基地没有 source（必须在表里显示「未核实」）")
    if no_geo:
        warnings.append(f"{no_geo} 个基地没有经纬度：地图气泡会缺失（不估算坐标）")

    # companies
    if not companies:
        warnings.append("companies.json 为空：企业抽屉只有自动汇总，没有画像/尽调问题")
    company_ids = {c.get("id") or c.get("name") for c in companies}
    orphan = [p.get("company_id") for p in plants if p.get("company_id") not in company_ids]
    if orphan:
        warnings.append(f"{len(set(orphan))} 个 company_id 没有对应画像（抽屉会退化显示）")

    # projects
    if not projects:
        warnings.append("projects.json 为空：新建/在建项目与净增还原将是空的")
    for i, p in enumerate(projects, 1):
        if not p.get("date"):
            warnings.append(f"projects.json 第 {i} 行缺少 date（时间线无法排序）")
        if p.get("type") in ("置换", "搬迁") and num(p.get("capacity_retired")) == 0 \
                and str(p.get("net", "")).strip() in ("", MISSING, "待确认"):
            warnings.append(f"projects.json 第 {i} 行是置换/搬迁但没给退出产能和净影响（{p.get('name')}）")

    # routes
    route_plants = {p.get("route") for p in plants if p.get("route")}
    route_cfg = {r.get("name") for r in cfg["routes"]}
    if route_cfg:
        unknown = route_plants - route_cfg
        if unknown:
            # 允许缩写（"联碱" 对应 "联碱法"）：能对上的就不报
            unmatched = {u for u in unknown
                         if not any(u in r or r in u for r in route_cfg if r)}
            if unmatched:
                warnings.append(f"plants.json 出现未在 routes 注册的工艺：{sorted(unmatched)}")
    elif route_plants:
        warnings.append("routes 未配置：工艺结构图将由 plants 现算（建议显式配置）")

    # sources
    ids = [s.get("id") for s in cfg["sources"]]
    if len(ids) != len(set(ids)):
        errors.append("sources 的 id 有重复")
    for s in cfg["sources"]:
        if not str(s.get("url", "")).startswith("http"):
            warnings.append(f"来源 {s.get('id')} 没有可用 URL（导出时会标「无链接」）")
        if s.get("confidence") and norm_conf(s.get("confidence")) != s.get("confidence"):
            warnings.append(f"来源 {s.get('id')} 置信度不在 {CONF_LEVELS}：{s.get('confidence')}（已按「{norm_conf(s.get('confidence'))}」显示）")

    # gaps / dd / scorecard
    if not cfg["gaps"]:
        warnings.append("gaps 为空：报告无法说明「哪些数据没拿到」")
    if not cfg["dd"]:
        warnings.append("dd 为空：企业尽调卡没有可执行问题")
    weight = sum(num(x[1]) for x in cfg["scorecard"] if isinstance(x, (list, tuple)) and len(x) > 1)
    if cfg["scorecard"] and weight != 100:
        warnings.append(f"scorecard 权重合计 {weight}，不等于 100")

    stats["companies"] = len(companies)
    stats["projects"] = len(projects)
    stats["sources"] = len(cfg["sources"])
    stats["routes"] = len(cfg["routes"])
    stats["gaps"] = len(cfg["gaps"])
    stats["dd"] = len(cfg["dd"])
    stats["sample_capacity"] = sum(num(p.get("capacity_base")) for p in plants)
    stats["sample_capacity_forward"] = sum(num(p.get("capacity_forward")) for p in plants)
    stats["provinces"] = len({p.get("province") for p in plants if p.get("province")})

    # 交叉核对
    declared = num(cfg["metrics"].get("sample_capacity"))
    if declared and stats["sample_capacity"] and abs(declared - stats["sample_capacity"]) > 1:
        warnings.append(f"metrics.sample_capacity={declared} 与 plants 加总 {stats['sample_capacity']:.0f} 不一致")
    return errors, warnings, stats


# ------------------------------------------------------------------ 渲染辅助
def order_by_priority(rows, field="priority"):
    rank = {"高": 0, "中高": 1, "中": 2, "中低": 3, "低": 4}
    return sorted(rows, key=lambda x: rank.get(str(x.get(field, "中")), 9))


def count_map(rows, field):
    return Counter(str(r.get(field) or MISSING) for r in rows)
