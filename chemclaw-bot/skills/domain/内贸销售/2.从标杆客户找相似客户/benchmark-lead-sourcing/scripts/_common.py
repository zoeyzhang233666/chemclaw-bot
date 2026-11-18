#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_common.py —— 各脚本共用的配置装载与判定函数（仅标准库）

配置来源优先级：project.json → skill_config.json（旧版）→ 内置默认。
产品特定内容全部来自配置，本模块不含任何产品硬编码。
"""
import json
import os
import re
import sys
from collections import Counter, OrderedDict


def setup_console():
    """让输出在 GBK 控制台/重定向下也不崩溃（Windows 中文环境必备）。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


DEFAULT_PROVINCES = ["内蒙古", "黑龙江", "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁",                     "吉林", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北",
                     "湖南", "广东", "广西", "海南", "四川", "贵州", "云南", "西藏", "陕西",
                     "甘肃", "青海", "宁夏", "新疆", "香港", "澳门", "台湾"]

PAREN = re.compile(r"[（(].*?[)）]")
NAME_NOISE = re.compile(r"(股份有限公司|有限责任公司|有限公司|集团有限公司|集团|公司|股份)")

DEFAULT_CONF_SCORES = {"高": 3, "中": 2, "低": 0}
CONF_ALIAS = {"中高": "中", "较高": "高", "较低": "低", "中低": "低", "high": "高",
              "medium": "中", "mid": "中", "low": "低"}
DEFAULT_THRESHOLDS = {"high": 11, "mid": 9}
DEFAULT_DIM_KEYWORDS = [("产品结构", ["产品结构", "配方", "产品"]),
                        ("工艺路线", ["工艺路线", "熔窑", "窑炉", "助熔", "工序", "反应",
                                      "工艺", "熔制", "碱化", "中和", "沉淀", "脱硫"]),
                        ("下游市场", ["下游"]),
                        ("规模", ["规模"]),
                        ("产业链位置", ["产业链"])]


# ------------------------------------------------------------------ 装载
def _legacy_to_project(cfg, directory):
    """把旧版 skill_config.json 映射成 project 结构。"""
    return {
        "project_id": os.path.basename(directory),
        "product": {"name": cfg.get("workbook_title", "本产品"), "grades": "", "aliases": [],
                    "use_summary": ""},
        "region": {"label": "", "provinces": []},
        "benchmark": {"name": "", "profile_file": "benchmark_profile.json"},
        "similarity_dimensions": [],
        "lanes": [],
        "file_blocks": cfg.get("file_blocks") or {},
        "strength_rules": cfg.get("strength_rules") or [],
        "default_strength": cfg.get("default_strength", 3),
        "priority_thresholds": cfg.get("priority_thresholds") or DEFAULT_THRESHOLDS,
        "confidence_scores": cfg.get("confidence_scores") or DEFAULT_CONF_SCORES,
        "peer_keywords": cfg.get("peer_keywords") or [],
        "buckets": cfg.get("buckets") or {},
        "industry_map": cfg.get("industry_map") or [],
        "report": {
            "title": cfg.get("workbook_title", "下游潜客开发地图"),
            "workbook_output": cfg.get("output", "下游潜客池.xlsx"),
            "html_output": "标杆客户复制与潜客池报告.html",
            "benchmark_name": "", "product_short": "",
            "headline_facts": [], "sales_script": "", "sop_steps": [],
            "evidence_note": "", "boundary_note": "",
        },
        "_legacy": True,
    }


def load_project(directory):
    pj = os.path.join(directory, "project.json")
    if os.path.exists(pj):
        with open(pj, "r", encoding="utf-8-sig") as fh:
            cfg = json.load(fh)
    else:
        sc = os.path.join(directory, "skill_config.json")
        if not os.path.exists(sc):
            raise SystemExit(f"找不到配置文件：{pj} 或 {sc}")
        with open(sc, "r", encoding="utf-8-sig") as fh:
            cfg = _legacy_to_project(json.load(fh), directory)
    cfg.setdefault("product", {})
    cfg["product"].setdefault("name", "本产品")
    cfg["product"].setdefault("grades", "")
    cfg["product"].setdefault("aliases", [])
    cfg["product"].setdefault("use_summary", "")
    cfg.setdefault("region", {"label": "", "provinces": []})
    cfg["region"].setdefault("provinces", [])
    cfg.setdefault("benchmark", {"name": "", "profile_file": "benchmark_profile.json"})
    cfg.setdefault("similarity_dimensions", [])
    cfg.setdefault("lanes", [])
    cfg.setdefault("strength_rules", [])
    cfg.setdefault("default_strength", 3)
    cfg.setdefault("priority_thresholds", DEFAULT_THRESHOLDS)
    cfg.setdefault("confidence_scores", DEFAULT_CONF_SCORES)
    cfg.setdefault("peer_keywords", [])
    cfg.setdefault("buckets", {"其他": ["其他"]})
    cfg.setdefault("industry_map", [])
    rep = cfg.setdefault("report", {})
    rep.setdefault("title", cfg.get("workbook_title") or "下游潜客开发地图")
    rep.setdefault("workbook_output", cfg.get("output") or "下游潜客池.xlsx")
    rep.setdefault("html_output", "标杆客户复制与潜客池报告.html")
    rep.setdefault("benchmark_name", cfg.get("benchmark", {}).get("name", ""))
    rep.setdefault("product_short", cfg["product"]["name"])
    for k in ("headline_facts", "sop_steps"):
        rep.setdefault(k, [])
    for k in ("sales_script", "evidence_note", "boundary_note"):
        rep.setdefault(k, "")
    return cfg


def block_of(cfg, filename):
    """文件名前缀 → 行业板块：优先 lanes[].block，其次旧版 file_blocks。"""
    base = os.path.basename(filename)
    for lane in cfg.get("lanes") or []:
        lid = str(lane.get("id") or "")
        if lid and base.startswith(lid + "_"):
            return lane.get("block") or lane.get("name") or "其他"
    for k, v in (cfg.get("file_blocks") or {}).items():
        if base.startswith(k):
            return v
    return "其他"


def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, "r", encoding="utf-8-sig") as fh:
        raw = fh.read().strip()
    if not raw:
        return default if default is not None else {}
    try:
        return json.loads(raw)
    except ValueError:
        return default if default is not None else {}


# ------------------------------------------------------------------ 判定
def norm_name(name):
    return NAME_NOISE.sub("", PAREN.sub("", name or "")).strip()


def provinces_of(cfg):
    return cfg.get("region", {}).get("provinces") or DEFAULT_PROVINCES


def province_of(loc, provinces=None):
    loc = loc or ""
    for p in (provinces or DEFAULT_PROVINCES):
        if p in loc:
            return p
    return "未标注"


def region_ok(loc, provinces):
    if not provinces:
        return True
    return any(p in (loc or "") for p in provinces)


def strength_of(sub, cfg):
    text = sub or ""
    for level, keys in (cfg.get("strength_rules") or []):
        if any(k in text for k in keys):
            return int(level)
    return int(cfg.get("default_strength", 3))


def priority_of(conf, strength, cfg):
    scores = cfg.get("confidence_scores") or DEFAULT_CONF_SCORES
    th = cfg.get("priority_thresholds") or DEFAULT_THRESHOLDS
    score = strength * 2 + scores.get(conf, 2)
    if score >= th.get("high", 11):
        return "高"
    if score >= th.get("mid", 9):
        return "中"
    return "低"


def norm_conf(value):
    c = str(value or "中").strip()
    c = CONF_ALIAS.get(c, c)
    return c if c in ("高", "中", "低") else "中"


def is_peer(sub, cfg):
    """细分行业命中同行关键词即判为同行（peer gate 的工程兜底）。"""
    text = sub or ""
    return any(k and k in text for k in (cfg.get("peer_keywords") or []))


def bucket_of(sub, buckets):
    t = sub or ""
    for name, keys in OrderedDict(buckets or {}).items():
        if any(k in t for k in keys):
            return name
    return "其他"


def dim_keywords(cfg):
    dims = cfg.get("similarity_dimensions") or []
    if not dims:
        return DEFAULT_DIM_KEYWORDS
    out = []
    for d in dims:
        if isinstance(d, dict) and d.get("name"):
            out.append((d["name"], d.get("keywords") or [d["name"]]))
    return out or DEFAULT_DIM_KEYWORDS


def norm_dims(text, cfg):
    t = text or ""
    return {name for name, keys in dim_keywords(cfg) if any(k in t for k in keys)}


def load_qa(raw_dir):
    """读抽检报告，返回 {来源URL: 备注}（只收录未通过的）。"""
    data = load_json(os.path.join(raw_dir, "_qa_report.json"), [])
    out = {}
    for row in data if isinstance(data, list) else []:
        url = (row.get("来源") or row.get("来源URL") or "").strip()
        if not url:
            continue
        if not (row.get("可达") and row.get("主体一致")):
            out[url] = (row.get("备注") or "抽检未通过").strip()
    return out


def urls_of(source):
    return [u for u in re.split(r"\s+", source or "") if u.startswith("http")]


def counts(leads, provinces=None):
    return {
        "板块": Counter(x.get("板块", "") for x in leads),
        "省份": Counter(province_of(x.get("所在地", ""), provinces) for x in leads),
        "置信度": Counter(x.get("置信度", "中") for x in leads),
        "优先级": Counter(x.get("优先级", "中") for x in leads),
        "强度": Counter(x.get("用量强度", "") for x in leads),
    }
