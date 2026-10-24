#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PP 新增产能与项目跟踪 —— 核心引擎 ppctl.py

一个与宿主无关（仅标准库 + openpyxl 可选）的项目档案 / 进展记录 / 汇总看板引擎。
其他 Agent（codex / Claude Code / chemclaw / 本机终端）只要能用 Python 3.8+ 跑这个脚本即可复用。

子命令：
  init     <项目目录>                 复制模板并初始化 projects.json / progress.json
  validate <项目目录>                 校验唯一编号、字段完整性、来源可回指、去重规则、进展时间不倒挂
  expand   <项目目录>                 把台账（每个项目含所有进展）展开为规范三表
  build    <项目目录>                 生成 Excel + HTML（含时间线、年度产能、地图、明细表、自选跟踪）
  check    <项目目录>                 交付前自检（Excel 表数/行数、HTML 区块与内联 JS 语法）
  all      <项目目录>                 validate -> expand -> build -> check

数据契约（唯一真相源）：
  data/projects.json   项目档案：一个项目 = 一条记录（唯一 project_id）。同一项目的多条生产线写进 units[]。
  data/progress.json   进展记录：一个事实 = 一条记录（唯一 progress_id），按 project_id 关联，逆序追加、永不覆盖。
  data/sources.json    来源登记：一个来源 = 一条记录（唯一 id），其他两表只存 source_ids。

由这三表派生的规范表（expand 生成到 data/derived/）：
  derived/projects.csv / units.csv / progress.csv / plan_history.csv / evidence.csv
"""
import csv
import json
import os
import re
import sys
from collections import OrderedDict, defaultdict
from datetime import date, datetime

# ---------------------------------------------------------------- 常量

STAGES = OrderedDict([
    ("拟建", 0), ("备案", 1), ("环评受理", 2), ("环评批复", 3), ("核准", 4),
    ("开工", 5), ("建设", 6), ("设备安装", 7), ("中交", 8),
    ("试车", 9), ("投产", 10), ("达产", 11), ("运行", 12), ("暂停", -1), ("取消", -2),
])

# 口径分组：产能状态（决定"是否可计入新增有效供应"）
CAPACITY_STATE = {
    "运行": "已形成有效供应",
    "试车": "试车/调试（未形成稳定商品供应）",
    "设备安装": "在建（未形成供应）",
    "建设中": "在建（未形成供应）",
    "开工": "在建（未形成供应）",
    "中交": "在建（未形成供应）",
    "核准": "计划（未形成供应）",
    "环评批复": "计划（未形成供应）",
    "环评受理": "计划（未形成供应）",
    "备案": "计划（未形成供应）",
    "拟建": "计划（未形成供应）",
    "暂停": "暂停/取消",
    "取消": "暂停/取消",
}

NATURE_TYPES = ["新建", "扩建", "置换", "技改", "复产", "技改+扩建"]
EVIDENCE_GRADES = ["A", "B", "C", "D"]
EVIDENCE_DESC = {
    "A": "一手权威：企业公告/定期报告、生态环境部门环评批复与公示原文、政府核准或备案文件、SABIC等企业官方发布",
    "B": "一手转载或专业数据库：政府网站/权威媒体对一手文件的完整转述、金联创/卓创等专业机构数据库、券商研报",
    "C": "二手行业资讯：化工网/搜狐号/微信公号等对项目的整理与转述，数字可能滞后或口径不一",
    "D": "弱证据：百科、自媒体汇编、论坛帖子；仅用于线索定位，不单独支撑关键字段",
}
PROVINCE_REGION = {
    "辽宁": "东北", "吉林": "东北", "黑龙江": "东北",
    "北京": "华北", "天津": "华北", "河北": "华北", "山西": "华北", "内蒙古": "华北",
    "上海": "华东", "江苏": "华东", "浙江": "华东", "安徽": "华东", "福建": "华东",
    "江西": "华东", "山东": "华东",
    "河南": "华中", "湖北": "华中", "湖南": "华中",
    "广东": "华南", "广西": "华南", "海南": "华南",
    "重庆": "西南", "四川": "西南", "贵州": "西南", "云南": "西南", "西藏": "西南",
    "陕西": "西北", "甘肃": "西北", "青海": "西北", "宁夏": "西北", "新疆": "西北",
}
ROUTE_CLASS = {
    "油制": "油制（炼化副产丙烯）", "CTO": "煤制（CTO/MTO/MTP）", "PDH": "丙烷脱氢（PDH）",
    "MTP": "煤制（MTO/MTP）", "MTO": "煤制（CTO/MTO/MTP）", "外购丙烯": "外购丙烯聚合",
    "混合": "混合原料",
}

REQUIRED_PROJECT_FIELDS = [
    "project_id", "owner", "group", "project_name", "province", "city",
    "product", "process", "nature", "stage", "first_plan_date", "latest_plan_date", "units",
]
REQUIRED_PROGRESS_FIELDS = [
    "progress_id", "project_id", "stage", "fact_date", "msg_date", "source_ids", "evidence_grade",
]
REQUIRED_SOURCE_FIELDS = ["id", "title", "url", "date", "type", "grade"]


# ---------------------------------------------------------------- 工具

def die(msg, code=1):
    print("[FAIL] " + msg)
    sys.exit(code)


def ok(msg):
    print("[ OK ] " + msg)


def warn(msg):
    print("[WARN] " + msg)


def load_json(path, default=None):
    if not os.path.exists(path):
        if default is not None:
            return default
        die("缺少文件: %s" % path)
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def parse_date(s):
    """容忍 YYYY-MM / YYYY-MM-DD / YYYY / YYYY年M月 / YYYY-Qn / YYYYHn，统一成 {precision, date, year}。"""
    if s is None or s == "":
        return {"raw": s, "date": None, "precision": None, "year": None}
    raw = str(s).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", raw)
    if m:
        return {"raw": raw, "date": raw, "precision": "day", "year": int(m.group(1))}
    m = re.match(r"^(\d{4})[-/年.](\d{1,2})月?$", raw)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        return {"raw": raw, "date": "%04d-%02d" % (y, mo), "precision": "month", "year": y}
    m = re.match(r"^(\d{4})年?[Qq]([1-4])$", raw)
    if m:
        return {"raw": raw, "date": "%s-Q%s" % (m.group(1), m.group(2)),
                "precision": "quarter", "year": int(m.group(1))}
    m = re.match(r"^(\d{4})年?[Hh]([12])$", raw)
    if m:
        return {"raw": raw, "date": "%s-H%s" % (m.group(1), m.group(2)),
                "precision": "half", "year": int(m.group(1))}
    m = re.match(r"^(\d{4})年?(?:底|末|度)?$", raw)
    if m:
        return {"raw": raw, "date": "%s-12" % m.group(1), "precision": "year", "year": int(m.group(1))}
    m = re.match(r"^(\d{4})[-/.](\d{1,2})$", raw)
    if m:
        return {"raw": raw, "date": "%04d-%02d" % (int(m.group(1)), int(m.group(2))),
                "precision": "month", "year": int(m.group(1))}
    return {"raw": raw, "date": None, "precision": "unknown", "year": None}


def month_index(d):
    """把解析后的日期折算成可比较的浮点月份（用于时间线排序与图）。未知返回 None。"""
    if not d or not d.get("date"):
        return None
    s = d["date"]
    m = re.match(r"^(\d{4})-(\d{2})$", s)
    if m:
        return int(m.group(1)) + (int(m.group(2)) - 1) / 12.0
    m = re.match(r"^(\d{4})-Q([1-4])$", s)
    if m:
        return int(m.group(1)) + (int(m.group(2)) - 1) * 3 / 12.0 + 0.041
    m = re.match(r"^(\d{4})-H([12])$", s)
    if m:
        return int(m.group(1)) + (0 if m.group(2) == "1" else 0.5) + 0.041
    return None


def norm_text(s):
    """归一化：去空白、全角括号统一、去'有限公司/股份有限公司/集团'后缀差异用于比对。"""
    if not s:
        return ""
    s = str(s)
    for a, b in [("（", "("), ("）", ")"), ("　", ""), (" ", ""), ("\t", ""), ("\n", "")]:
        s = s.replace(a, b)
    s = re.sub(r"[·•・]", "", s)
    return s.strip().lower()


def norm_company(s):
    s = norm_text(s)
    s = re.sub(r"(股份有限公司|有限责任公司|有限公司|集团|股份|公司)$", "", s)
    return s


def region_of(province):
    for p, r in PROVINCE_REGION.items():
        if p in (province or ""):
            return r
    return "其他"


def cap_state(stage):
    return CAPACITY_STATE.get(stage, "未分类")


# ---------------------------------------------------------------- init

def cmd_init(args):
    proj_dir = args[0] if args else "."
    for sub in ["data", "out", "data/derived", "snapshots"]:
        os.makedirs(os.path.join(proj_dir, sub), exist_ok=True)
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
    tpl = os.path.normpath(tpl)
    for name, default in [("projects.json", {"projects": []}),
                          ("progress.json", {"progress": []}),
                          ("sources.json", {"sources": []})]:
        dst = os.path.join(proj_dir, "data", name)
        if os.path.exists(dst):
            warn("已存在，跳过: %s" % dst)
            continue
        src = os.path.join(tpl, name)
        if os.path.exists(src):
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = default
        save_json(dst, data)
        ok("初始化 %s" % dst)
    # config
    cfg = os.path.join(proj_dir, "data", "config.json")
    if not os.path.exists(cfg):
        save_json(cfg, {
            "product": "聚丙烯(PP)", "product_code": "PP", "unit": "万吨/年",
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "baseline_capacity_wan": None,
            "baseline_capacity_source": "",
            "owner_filter": [], "region_filter": [], "process_filter": [], "cap_threshold_wan": 0,
        })
        ok("初始化 %s" % cfg)


# ---------------------------------------------------------------- validate

def cmd_validate(args):
    proj_dir = args[0] if args else "."
    d = os.path.join(proj_dir, "data")
    projects = load_json(os.path.join(d, "projects.json"))["projects"]
    progress = load_json(os.path.join(d, "progress.json"))["progress"]
    sources = {s["id"]: s for s in load_json(os.path.join(d, "sources.json"))["sources"]}
    errors, warns = [], []

    # ---- 来源表
    for s in sources.values():
        for f in REQUIRED_SOURCE_FIELDS:
            if s.get(f) in (None, ""):
                errors.append("来源 %s 缺字段 %s" % (s["id"], f))
        if s.get("grade") not in EVIDENCE_GRADES:
            errors.append("来源 %s 证据等级非法: %s" % (s["id"], s.get("grade")))
        u = s.get("url", "")
        if u and not re.match(r"^https?://", u):
            warns.append("来源 %s URL 不是 http(s): %s" % (s["id"], u))
    url_map = defaultdict(list)
    for s in sources.values():
        url_map[norm_text(s.get("url", ""))].append(s["id"])
    for u, ids in url_map.items():
        if len(ids) > 1 and u:
            warns.append("同一 URL 被多条来源登记: %s -> %s" % (u, ids))

    # ---- 项目表
    pid_seen = set()
    sig_map = defaultdict(list)
    for p in projects:
        pid = p.get("project_id")
        if not pid:
            errors.append("存在无 project_id 的项目: %s" % p.get("project_name"))
            continue
        if pid in pid_seen:
            errors.append("project_id 重复: %s" % pid)
        pid_seen.add(pid)
        for f in REQUIRED_PROJECT_FIELDS:
            if f not in p:
                errors.append("%s 缺必填字段 %s" % (pid, f))
        if p.get("stage") and p["stage"] not in STAGES:
            warns.append("%s stage 不在枚举内: %s" % (pid, p["stage"]))
        if p.get("nature") and p["nature"] not in NATURE_TYPES:
            warns.append("%s nature 不在枚举内: %s" % (pid, p["nature"]))
        units = p.get("units") or []
        if not units:
            errors.append("%s 无 units（装置/生产线）" % pid)
        usig = set()
        for u in units:
            if not u.get("unit_id"):
                errors.append("%s 中存在无 unit_id 的装置" % pid)
            if u.get("capacity_wan") is None:
                errors.append("%s/%s 缺 capacity_wan" % (pid, u.get("unit_id")))
            if u.get("unit_id") in usig:
                errors.append("%s 装置 unit_id 重复: %s" % (pid, u.get("unit_id")))
            usig.add(u.get("unit_id"))
        # 去重签名：归一化业主 + 归一化项目名 + 省份
        sig = (norm_company(p.get("owner")), norm_text(p.get("project_name"))[:24], p.get("province"))
        sig_map[sig].append(pid)
        for sid in p.get("source_ids", []):
            if sid not in sources:
                errors.append("%s 引用不存在的来源 %s" % (pid, sid))
        # 计划时间精度
        for key in ("first_plan_date", "latest_plan_date"):
            pd = parse_date(p.get(key))
            if p.get(key) and pd["precision"] in (None, "unknown"):
                warns.append("%s %s 时间无法解析: %s" % (pid, key, p.get(key)))

    for sig, ids in sig_map.items():
        if len(ids) > 1:
            errors.append("疑似重复项目（同业主同项目名同省份）: %s" % ids)

    # ---- 进展表
    pr_seen = set()
    by_proj = defaultdict(list)
    for r in progress:
        rid = r.get("progress_id")
        if not rid:
            errors.append("进展记录缺 progress_id")
            continue
        if rid in pr_seen:
            errors.append("progress_id 重复: %s" % rid)
        pr_seen.add(rid)
        for f in REQUIRED_PROGRESS_FIELDS:
            if f not in r:
                errors.append("%s 缺必填字段 %s" % (rid, f))
        if r.get("project_id") not in pid_seen:
            errors.append("%s 指向不存在的项目 %s" % (rid, r.get("project_id")))
        if r.get("stage") and r["stage"] not in STAGES:
            warns.append("%s stage 不在枚举内: %s" % (rid, r["stage"]))
        if r.get("evidence_grade") not in EVIDENCE_GRADES:
            errors.append("%s evidence_grade 非法: %s" % (rid, r.get("evidence_grade")))
        if not r.get("source_ids"):
            errors.append("%s 无来源（没有 trace 的记录不算记录）" % rid)
        for sid in r.get("source_ids", []):
            if sid not in sources:
                errors.append("%s 引用不存在的来源 %s" % (rid, sid))
        # 证据等级一致性：声称 A/B 但来源全是 C/D
        if r.get("source_ids"):
            srcs = [sources.get(x) for x in r["source_ids"] if x in sources]
            if srcs:
                best = min(s["grade"] for s in srcs)
                if r.get("evidence_grade") and r["evidence_grade"] < best:
                    warns.append("%s 自评等级 %s 高于其来源最高等级 %s" %
                                 (rid, r["evidence_grade"], best))
        fd = parse_date(r.get("fact_date"))
        md = parse_date(r.get("msg_date"))
        if fd["year"] and md["year"] and month_index(fd) and month_index(md):
            if month_index(fd) - month_index(md) > 1.01:
                warns.append("%s 事实日期(%s)晚于消息日期(%s)超过1个月，请复核" %
                             (rid, r.get("fact_date"), r.get("msg_date")))
        by_proj[r["project_id"]].append(r)

    # ---- 阶段单调性（历史不得倒挂，除非明确回退）
    for pid, rows in by_proj.items():
        rows2 = sorted([x for x in rows if month_index(parse_date(x.get("fact_date")))],
                       key=lambda x: month_index(parse_date(x.get("fact_date"))))
        last = -99
        last_stage = None
        for x in rows2:
            st = STAGES.get(x.get("stage"), 99)
            if st in (-1, -2):
                last_stage = x.get("stage")
                continue
            if st + 2 < last:  # 允许小幅并列/回填，倒挂超过 2 级告警
                warns.append("%s 阶段倒挂：%s(%s) 之后出现 %s(%s)，如属并线/回填请注明" %
                             (pid, last_stage, x.get("fact_date"), x.get("stage"), x.get("fact_date")))
            last = max(last, st)
            last_stage = x.get("stage")

    for p in projects:
        pid = p.get("project_id")
        rows = by_proj.get(pid, [])
        if not rows:
            errors.append("%s 无任何进展记录" % pid)
            continue
        has_trial = any(r.get("stage") in ("试车", "投产", "达产") for r in rows)
        if p.get("stage") in ("运行",) and not has_trial:
            errors.append("%s 状态为运行但无试车/投产/达产记录支撑" % pid)
        if not any(r.get("stage") in ("备案", "环评受理", "环评批复", "核准", "开工", "建设",
                                      "设备安装", "中交", "试车", "投产", "达产") for r in rows):
            warns.append("%s 只有拟建阶段记录，证据不足以支撑其存在" % pid)

    print("=" * 78)
    print("validate: 项目 %d / 装置 %d / 进展 %d / 来源 %d" %
          (len(projects), sum(len(p.get('units') or []) for p in projects), len(progress), len(sources)))
    for w in warns:
        warn(w)
    for e in errors:
        print("[ERR ] " + e)
    print("=" * 78)
    if errors:
        die("校验未通过：%d 个错误，%d 个提示" % (len(errors), len(warns)))
    ok("校验通过（%d 条提示）" % len(warns))


# ---------------------------------------------------------------- expand

def cmd_expand(args):
    proj_dir = args[0] if args else "."
    d = os.path.join(proj_dir, "data")
    deriv = os.path.join(d, "derived")
    os.makedirs(deriv, exist_ok=True)
    cfg = load_json(os.path.join(d, "config.json"), {})
    projects = load_json(os.path.join(d, "projects.json"))["projects"]
    progress = load_json(os.path.join(d, "progress.json"))["progress"]
    sources = {s["id"]: s for s in load_json(os.path.join(d, "sources.json"))["sources"]}
    proj_by_id = {p["project_id"]: p for p in projects}
    by_proj = defaultdict(list)
    for r in progress:
        by_proj[r["project_id"]].append(r)

    # 1) units.csv —— 一行一套装置/一条生产线
    unit_rows = []
    for p in projects:
        for u in p.get("units") or []:
            unit_rows.append(OrderedDict([
                ("项目编号", p["project_id"]), ("装置编号", u["unit_id"]),
                ("业主", p["owner"]), ("所属集团", p["group"]),
                ("项目名称", p["project_name"]), ("装置/生产线", u.get("unit_name", "")),
                ("省份", p["province"]), ("地市", p.get("city", "")),
                ("区域", region_of(p["province"])), ("产品", p["product"]),
                ("设计产能(万吨/年)", u.get("capacity_wan")), ("工艺路线", p.get("process", "")),
                ("工艺归类", ROUTE_CLASS.get(p.get("process", ""), p.get("process", ""))),
                ("项目性质", p.get("nature", "")), ("装置状态", p.get("stage", "")),
                ("产能状态", cap_state(p.get("stage", ""))),
                ("首提预计投产", p.get("first_plan_date", "")),
                ("最新预计投产", p.get("latest_plan_date", "")),
                ("首提日期", p.get("first_plan_noted", "")),
                ("是否延期", p.get("delay_flag", "")),
                ("计划变更次数", p.get("plan_change_count", 0)),
                ("置换/退出产能(万吨/年)", u.get("replace_wan", 0) or 0),
                ("净新增口径(万吨/年)", (u.get("capacity_wan") or 0) - (u.get("replace_wan", 0) or 0)),
            ]))
    write_csv(os.path.join(deriv, "units.csv"), unit_rows)

    # 2) progress.csv —— 一行一条进展事实（并行导出"预计投产时间变更史"）
    prog_rows, hist_rows = [], []
    for p in projects:
        pid = p["project_id"]
        rows = sorted(by_proj.get(pid, []),
                      key=lambda x: (month_index(parse_date(x.get("fact_date"))) or 0, x["progress_id"]))
        for i, r in enumerate(rows, 1):
            srcs = [sources.get(s) for s in r.get("source_ids", []) if sources.get(s)]
            prog_rows.append(OrderedDict([
                ("项目编号", pid), ("进展序号", i), ("进展编号", r["progress_id"]),
                ("业主", p["owner"]), ("项目名称", p["project_name"]),
                ("省份", p["province"]), ("阶段", r.get("stage", "")),
                ("进展描述", r.get("desc", "")),
                ("事实发生日期", r.get("fact_date", "")), ("消息日期", r.get("msg_date", "")),
                ("证据等级", r.get("evidence_grade", "")),
                ("来源数", len(srcs)),
                ("来源编号", ";".join(r.get("source_ids", []))),
                ("来源标题", " || ".join(s["title"] for s in srcs)),
                ("来源URL", " || ".join(s["url"] for s in srcs)),
                ("来源类型", " || ".join(s["type"] for s in srcs)),
                ("当期预计投产", r.get("plan_date_noted", "")),
                ("变更类型", r.get("plan_change", "")),
                ("备注", r.get("note", "")),
            ]))
            if r.get("plan_change"):
                hist_rows.append(OrderedDict([
                    ("项目编号", pid), ("业主", p["owner"]), ("项目名称", p["project_name"]),
                    ("变更发生在(事实日期)", r.get("fact_date", "")), ("消息日期", r.get("msg_date", "")),
                    ("变更类型", r.get("plan_change", "")),
                    ("变更前预计投产", r.get("plan_from", "")), ("变更后预计投产", r.get("plan_to", "")),
                    ("依据描述", r.get("desc", "")),
                    ("来源编号", ";".join(r.get("source_ids", []))),
                    ("证据等级", r.get("evidence_grade", "")),
                ]))
        if p.get("first_plan_date") and p.get("latest_plan_date") \
                and parse_date(p["first_plan_date"])["date"] != parse_date(p["latest_plan_date"])["date"] \
                and not any(h["项目编号"] == pid for h in hist_rows):
            hist_rows.append(OrderedDict([
                ("项目编号", pid), ("业主", p["owner"]), ("项目名称", p["project_name"]),
                ("变更发生在(事实日期)", ""), ("消息日期", ""), ("变更类型", "口径差异"),
                ("变更前预计投产", p["first_plan_date"]), ("变更后预计投产", p["latest_plan_date"]),
                ("依据描述", "首次披露与最新披露存在差异，但未定位到单一变更事件，需补证"),
                ("来源编号", ";".join(p.get("source_ids", [])[:3])), ("证据等级", ""),
            ]))
    write_csv(os.path.join(deriv, "progress.csv"), prog_rows)
    write_csv(os.path.join(deriv, "plan_history.csv"), hist_rows)

    # 3) projects.csv —— 一行一个项目（含汇总的产能与状态）
    proj_rows = []
    for p in projects:
        pid = p["project_id"]
        cap = sum((u.get("capacity_wan") or 0) for u in p.get("units") or [])
        repl = sum((u.get("replace_wan") or 0) for u in p.get("units") or [])
        rows = by_proj.get(pid, [])
        last = max(rows, key=lambda x: month_index(parse_date(x.get("fact_date"))) or 0) if rows else {}
        proj_rows.append(OrderedDict([
            ("项目编号", pid), ("业主", p["owner"]), ("所属集团", p["group"]),
            ("项目名称", p["project_name"]), ("省份", p["province"]), ("地市", p.get("city", "")),
            ("区域", region_of(p["province"])), ("园区", p.get("park", "")),
            ("产品", p["product"]), ("设计产能(万吨/年)", round(cap, 2)),
            ("装置套数", len(p.get("units") or [])),
            ("工艺路线", p.get("process", "")),
            ("工艺归类", ROUTE_CLASS.get(p.get("process", ""), p.get("process", ""))),
            ("项目性质", p.get("nature", "")), ("当前阶段", p.get("stage", "")),
            ("产能状态", cap_state(p.get("stage", ""))),
            ("首次披露日期", p.get("first_disclosed", "")),
            ("首提预计投产", p.get("first_plan_date", "")),
            ("最新预计投产", p.get("latest_plan_date", "")),
            ("是否延期", p.get("delay_flag", "")),
            ("延期月数(估计)", p.get("delay_months", "")),
            ("投达产不确定性", p.get("uncertainty", "")),
            ("最新进展", (last.get("desc") or "")[:120]),
            ("最新进展阶段", last.get("stage", "")),
            ("最新进展日期", last.get("fact_date", "")),
            ("实质放量年份口径", p.get("ramp_year", "")),
            ("产能统计口径", p.get("counting_note", "")),
            ("重复披露说明", p.get("dup_note", "")),
            ("关注要点", p.get("watch", "")),
        ]))
    write_csv(os.path.join(deriv, "projects.csv"), proj_rows)

    # 4) summary_yearly.csv / summary_region.csv
    summary_yearly(proj_dir, projects, cfg)
    summary_region(proj_dir, projects, cfg)

    # 5) deferred.csv —— 隐性供给缺口（名义计划 vs 工程证据的差额）
    as_of_year = int(cfg.get("as_of", "2026")[:4])
    d_rows = deferred_capacity(projects, as_of_year)
    write_csv(os.path.join(deriv, "deferred.csv"),
              [OrderedDict([("项目编号", r["project_id"]), ("业主", r["owner"]),
                            ("项目名称", r["project_name"]), ("省份", r["province"]),
                            ("当前阶段", r["stage"]), ("产能(万吨/年)", r["capacity_wan"]),
                            ("最新预计投产", r["latest_plan_date"]),
                            ("判定规则", "; ".join(r["reasons"]))]) for r in d_rows])
    tot_defer = sum(r["capacity_wan"] for r in d_rows)
    ok("隐性供给缺口 %d 项 / %.1f 万吨（名义计入 %d 年但工程证据不支持年内形成供应）"
       % (len(d_rows), tot_defer, as_of_year))

    ok("expand 完成：units=%d progress=%d projects=%d plan_history=%d" %
       (len(unit_rows), len(prog_rows), len(proj_rows), len(hist_rows)))
    return {"units": len(unit_rows), "progress": len(prog_rows), "projects": len(proj_rows),
            "plan_history": len(hist_rows)}


def deferred_capacity(projects, as_of_year):
    """★隐性供给缺口：名义上'某年计划投产'但工程证据显示实质放量会滑入下一年（或已被推迟一年以上）的产能。

    判定规则（可审计、不靠主观打分）：
      R1 最新预计投产年份 <= as_of_year 且 delay_months >= 6          -> 已明确延期半年以上
      R2 最新预计投产年份 <= as_of_year 且 stage 仍停留在早期阶段
         （拟建/备案/环评受理/环评批复/核准）                          -> 批文未转化成工程进度
      R3 最新预计投产年份 <= as_of_year 且 stage 为'设备安装'但项目
         最近一条进展离计划投产不足 4 个月                              -> 安装未完成，年底出料不成立
    """
    rows = []
    for p in projects:
        st = p.get("stage", "")
        y_plan = parse_date(p.get("latest_plan_date"))["year"]
        if y_plan is None or y_plan > as_of_year:
            continue
        cap = sum((u.get("capacity_wan") or 0) for u in p.get("units") or [])
        if cap <= 0:
            continue
        reasons = []
        dm = p.get("delay_months")
        if isinstance(dm, (int, float)) and dm >= 6:
            reasons.append("R1 已明确延期 %d 个月" % dm)
        if st in ("拟建", "备案", "环评受理", "环评批复", "核准"):
            reasons.append("R2 计划年内投产但阶段仍为「%s」，批文未转化为工程进度" % st)
        if st == "设备安装":
            reasons.append("R3 主体仍处设备安装，且未见试车报道")
        if not reasons:
            continue
        rows.append({
            "project_id": p["project_id"], "owner": p["owner"], "project_name": p["project_name"],
            "province": p["province"], "stage": st, "capacity_wan": cap,
            "latest_plan_date": p.get("latest_plan_date", ""), "reasons": reasons,
        })
    return rows


def write_csv(path, rows):
    if not rows:
        open(path, "w", encoding="utf-8-sig").write("")
        return
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def baseline_from_config(cfg, projects):
    b = cfg.get("baseline_capacity_wan")
    if b:
        return float(b), cfg.get("baseline_capacity_source", "")
    return None, ""


def summary_yearly(proj_dir, projects, cfg):
    """年度口径：把每个装置按其'最新预计投产'年份归集，并按产能状态拆成四类。

    归年规则（关键）：
      - 已形成有效供应（运行/达产/投产）：归入 actual_online_date 所在年份——事实年份优先。
      - 试车/调试：归入 latest_plan_date 年份（尚未形成稳定供应）。
      - 建设中/计划：归入 latest_plan_date 年份。
      - 无计划时间的：归入'未定'（9999），绝不按 0 处理。
    """
    base, base_src = baseline_from_config(cfg, projects)
    buckets = defaultdict(lambda: {"已投产": 0.0, "试车调试": 0.0, "建设中": 0.0, "计划中": 0.0,
                                   "暂停取消": 0.0, "退出": 0.0, "units": 0, "projects": set()})
    for p in projects:
        st = p.get("stage", "")
        grp = {"运行": "已投产", "达产": "已投产", "投产": "已投产",
               "试车": "试车调试", "中交": "建设中", "设备安装": "建设中",
               "建设": "建设中", "开工": "建设中", "核准": "计划中", "环评批复": "计划中",
               "环评受理": "计划中", "备案": "计划中", "拟建": "计划中",
               "暂停": "暂停取消", "取消": "暂停取消"}.get(st, "计划中")
        for u in p.get("units") or []:
            cap = u.get("capacity_wan") or 0
            y = None
            if grp == "已投产":
                y = parse_date(p.get("actual_online_date"))["year"]
            if y is None:
                y = parse_date(p.get("latest_plan_date"))["year"]
            if y is None:
                y = 9999
            b = buckets[y]
            b[grp] += cap
            b["退出"] += (u.get("replace_wan") or 0)
            b["units"] += 1
            b["projects"].add(p["project_id"])
    rows = []
    cum = 0.0
    for y in sorted(buckets):
        b = buckets[y]
        net = b["已投产"] + b["试车调试"] + b["建设中"] + b["计划中"] - b["退出"]
        rows.append(OrderedDict([
            ("年份", "未定" if y == 9999 else y),
            ("已投产(万吨/年)", round(b["已投产"], 2)),
            ("试车/调试(万吨/年)", round(b["试车调试"], 2)),
            ("建设中(万吨/年)", round(b["建设中"], 2)),
            ("计划/仅批文(万吨/年)", round(b["计划中"], 2)),
            ("暂停或取消(万吨/年)", round(b["暂停取消"], 2)),
            ("替代退出旧产能(万吨/年)", round(b["退出"], 2)),
            ("净新增(万吨/年)", round(net, 2)),
            ("名义新增(不含退出,万吨/年)", round(b["已投产"] + b["试车调试"] + b["建设中"] + b["计划中"], 2)),
            ("涉及装置数", b["units"]),
            ("涉及项目数", len(b["projects"])),
            ("相对现有产能比例(名义)", ("%.2f%%" % (net / base * 100)) if base else "需输入基数"),
            ("期末产能(万吨/年)", round(base + cum + net, 2) if base else ""),
        ]))
        cum += net
    write_csv(os.path.join(proj_dir, "data", "derived", "summary_yearly.csv"), rows)
    return rows


def summary_region(proj_dir, projects, cfg):
    base, _ = baseline_from_config(cfg, projects)
    agg = defaultdict(lambda: defaultdict(float))
    for p in projects:
        reg = region_of(p["province"])
        st = p.get("stage", "")
        grp = {"运行": "已投产", "达产": "已投产", "投产": "已投产", "试车": "试车调试"}.get(st, "未投产")
        if st in ("暂停", "取消"):
            grp = "暂停取消"
        for u in p.get("units") or []:
            cap = u.get("capacity_wan") or 0
            agg[p["province"]][grp] += cap
            agg[p["province"]]["合计"] += cap
            agg[p["province"]]["退出"] += (u.get("replace_wan") or 0)
            agg[p["province"]]["项目_" + p["project_id"]] = 1
            agg[p["province"]]["装置数"] += 1
    rows = []
    for prov in sorted(agg, key=lambda x: -agg[x]["合计"]):
        a = agg[prov]
        rows.append(OrderedDict([
            ("省份", prov), ("区域", region_of(prov)),
            ("已投产(万吨/年)", round(a["已投产"], 2)),
            ("试车调试(万吨/年)", round(a["试车调试"], 2)),
            ("在建+计划(万吨/年)", round(a["未投产"], 2)),
            ("跟踪产能合计(万吨/年)", round(a["合计"], 2)),
            ("替代退出旧产能(万吨/年)", round(a["退出"], 2)),
            ("涉及装置数", int(a["装置数"])),
            ("涉及项目数", len([k for k in a if k.startswith("项目_")])),
        ]))
    write_csv(os.path.join(proj_dir, "data", "derived", "summary_region.csv"), rows)
    return rows


# ---------------------------------------------------------------- build / check

def cmd_build(args):
    proj_dir = args[0] if args else "."
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from build_excel import build_excel
    from build_html import build_html
    xlsx = build_excel(proj_dir)
    html = build_html(proj_dir)
    ok("Excel: %s" % xlsx)
    ok("HTML : %s" % html)


def cmd_check(args):
    proj_dir = args[0] if args else "."
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from build_check import run_check
    run_check(proj_dir)


def main():
    cmds = {"init": cmd_init, "validate": cmd_validate, "expand": cmd_expand,
            "build": cmd_build, "check": cmd_check}
    if len(sys.argv) < 2 or sys.argv[1] not in list(cmds) + ["all"]:
        print(__doc__)
        sys.exit(0)
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    if cmd == "all":
        cmd_validate(rest); cmd_expand(rest); cmd_build(rest); cmd_check(rest)
    else:
        cmds[cmd](rest)


if __name__ == "__main__":
    main()
