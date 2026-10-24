# -*- coding: utf-8 -*-
"""core.py — 化工装置停车事件研究内核（纯标准库，无第三方依赖）

提供：
  1. 列名归一化（中英文表头都能读）
  2. 交易日历重建（用任一真实上市品种的日线）与“事件日→首个可交易交易日”对齐
  3. 事件去重（同一次停车被多家媒体重复报道）
  4. 事件重叠检测（窗口内的样本相互污染）
  5. 基准调整后的异常收益（市场模型 / 均值调整 / 匹配日）
  6. 描述统计（均值 / 中位数 / 分位数 / 胜率 / 自助法置信区间）

设计原则：任何缺失都返回 None 并留下 gap 说明，绝不插值、绝不补数。
"""
from __future__ import annotations

import bisect
import csv
import datetime as _dt
import io
import json
import math
import os
import re
import statistics
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ----------------------------------------------------------------------------
# 0. 常量与词汇表（整套技能共用，禁止自创同义词）
# ----------------------------------------------------------------------------

#: 三种日期必须分开存，时刻不同不能混用
DATE_FIELDS = {
    "announce_date": "企业公告日（上市公司公告/交易所披露日）；无公告则为空",
    "first_market_date": "市场首次获知日（媒体首次报道/盘面首次反应）；默认事件日候选",
    "actual_start_date": "实际停车日（装置真正停止进料/降负的日期）",
}

#: 事件类型词表
EVENT_TYPES = {
    "planned": "计划检修（提前公告/排入检修计划）",
    "unplanned": "意外停车（故障、事故、断供、胀库等非计划）",
    "restart": "重启/复产（方向与停车相反，用于方向性对照）",
}

#: 证据等级（与 chem-capacity-impact 保持一致，便于跨技能引用）
EVIDENCE_GRADES = {
    "E1": "一手官方：交易所/企业公告、环评、验收报告、政府统计",
    "E2": "行业权威：隆众/卓创/生意社/金联创、行业协会、交易所规则",
    "E3": "综合媒体：财经媒体、期货公司研报转述",
    "E4": "机构口径：咨询机构估算、券商模型",
    "E5": "待确认：无来源、仅口头、检索命中但产品/主体未核实",
}

#: 列名别名（中文表头直接读，不用改用户的 Excel）
COLUMN_ALIASES = {
    "event_id": ["event_id", "事件编号", "编号", "id"],
    "event_name": ["event_name", "事件", "事件名称", "事件描述"],
    "company": ["company", "企业", "企业名称", "主体", "公司"],
    "unit_name": ["unit_name", "装置", "装置名称", "装置/产线"],
    "product": ["product", "产品", "品种"],
    "capacity_wt": ["capacity_wt", "产能", "产能万吨", "单套产能(万吨)", "单套产能万吨", "capacity"],
    "region": ["region", "地区", "区域"],
    "country": ["country", "国家"],
    "event_type": ["event_type", "事件类型", "类型"],
    "announce_date": ["announce_date", "企业公告日期", "公告日期", "公告日"],
    "first_market_date": ["first_market_date", "市场首次获知日期", "首次披露时间", "首次报道日期", "事件日"],
    "actual_start_date": ["actual_start_date", "实际停车日期", "实际停车时间", "停车日期"],
    "actual_restart_date": ["actual_restart_date", "实际重启日期", "重启日期"],
    "duration_days": ["duration_days", "停车天数", "持续天数"],
    "include_flag": ["include_flag", "是否纳入", "纳入", "筛选结果"],
    "screening_reason": ["screening_reason", "筛选理由", "纳入理由", "剔除理由"],
    "evidence_grade": ["evidence_grade", "证据等级"],
    "product_verified": ["product_verified", "产品核验", "产品是否相符"],
    "source_title": ["source_title", "来源标题", "新闻标题"],
    "source_media": ["source_media", "来源媒体", "媒体"],
    "source_url": ["source_url", "来源链接", "链接", "URL"],
    "quote": ["quote", "原文摘录", "原文", "证据原文"],
    "notes": ["notes", "备注"],
    "in_comparison_set": ["in_comparison_set", "纳入统计", "可比"],
}

YES_WORDS = {"是", "1", "true", "yes", "y", "纳入", "in", "include"}
NO_WORDS = {"否", "0", "false", "no", "n", "剔除", "exclude", "out"}


# ----------------------------------------------------------------------------
# 1. 基础工具
# ----------------------------------------------------------------------------

def norm_header(h: str) -> str:
    """把任意表头归一化为内部字段名；不认识的返回 None。"""
    key = str(h or "").strip().lower().replace("\ufeff", "")
    key = re.sub(r"[\s_\-()（）\[\]]+", "", key)
    for field_name, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if key == re.sub(r"[\s_\-()（）\[\]]+", "", a.lower()):
                return field_name
    return None


def parse_date(v: Any) -> Optional[str]:
    """宽松解析日期，统一返回 YYYY-MM-DD；解析失败返回 None（不猜）。"""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in {"nat", "nan", "none", "-", "—", "n/a", "无", "待核"}:
        return None
    m = re.search(r"(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return _dt.date(y, mo, d).isoformat()
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
    if m:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    return None


def parse_flag(v: Any, default: Optional[bool] = None) -> Optional[bool]:
    if v is None:
        return default
    s = str(v).strip().lower()
    if not s:
        return default
    if s in YES_WORDS:
        return True
    if s in NO_WORDS:
        return False
    return default


def parse_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s or s in {"-", "—", "n/a", "无"}:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def normalize_event_type(v: Any) -> str:
    s = str(v or "").strip().lower()
    if any(k in s for k in ("重启", "复产", "恢复", "restart", "resume")):
        return "restart"
    if any(k in s for k in ("意外", "非计划", "故障", "事故", "断供", "胀库", "unplanned", "fault")):
        return "unplanned"
    if any(k in s for k in ("计划", "检修", "planned", "maintenance")):
        return "planned"
    return s or "unknown"


# ----------------------------------------------------------------------------
# 2. 事件对象
# ----------------------------------------------------------------------------

@dataclass
class Event:
    event_id: str
    event_name: str = ""
    company: str = ""
    unit_name: str = ""
    product: str = ""
    capacity_wt: Optional[float] = None
    region: str = ""
    country: str = ""
    event_type: str = "unknown"
    announce_date: Optional[str] = None
    first_market_date: Optional[str] = None
    actual_start_date: Optional[str] = None
    actual_restart_date: Optional[str] = None
    duration_days: Optional[float] = None
    include_flag: Optional[bool] = True
    in_comparison_set: Optional[bool] = True
    screening_reason: str = ""
    evidence_grade: str = "E5"
    product_verified: Optional[bool] = None
    source_title: str = ""
    source_media: str = ""
    source_url: str = ""
    quote: str = ""
    notes: str = ""
    # 运行期字段
    anchor_date: Optional[str] = None       # 实际用于对齐的交易日
    anchor_kind: str = ""                   # first_market / actual_start / restart ...
    gaps: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)

    def to_row(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def load_events_csv(path: str) -> List[Event]:
    """读取事件表 CSV（UTF-8/BOM/GBK 均可），中英文表头都可"""
    raw = open(path, "rb").read()
    text = None
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError(f"无法解码文件：{path}")
    return load_events_text(text)


def load_events_text(text: str) -> List[Event]:
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any((c or "").strip() for c in r)]
    if not rows:
        return []
    header = [norm_header(c) or f"_unknown_{i}" for i, c in enumerate(rows[0])]
    events: List[Event] = []
    for r in rows[1:]:
        rec = {}
        for i, cell in enumerate(r):
            if i < len(header) and not header[i].startswith("_unknown"):
                rec[header[i]] = cell
        if not rec.get("event_id") and not rec.get("event_name"):
            continue
        ev = Event(
            event_id=str(rec.get("event_id") or f"EV-{len(events)+1:02d}").strip(),
            event_name=str(rec.get("event_name") or "").strip(),
            company=str(rec.get("company") or "").strip(),
            unit_name=str(rec.get("unit_name") or "").strip(),
            product=str(rec.get("product") or "").strip(),
            capacity_wt=parse_float(rec.get("capacity_wt")),
            region=str(rec.get("region") or "").strip(),
            country=str(rec.get("country") or "").strip(),
            event_type=normalize_event_type(rec.get("event_type")),
            announce_date=parse_date(rec.get("announce_date")),
            first_market_date=parse_date(rec.get("first_market_date")),
            actual_start_date=parse_date(rec.get("actual_start_date")),
            actual_restart_date=parse_date(rec.get("actual_restart_date")),
            duration_days=parse_float(rec.get("duration_days")),
            include_flag=parse_flag(rec.get("include_flag"), True),
            in_comparison_set=parse_flag(rec.get("in_comparison_set"), True),
            screening_reason=str(rec.get("screening_reason") or "").strip(),
            evidence_grade=str(rec.get("evidence_grade") or "E5").strip().upper()[:2] or "E5",
            product_verified=parse_flag(rec.get("product_verified"), None),
            source_title=str(rec.get("source_title") or "").strip(),
            source_media=str(rec.get("source_media") or "").strip(),
            source_url=str(rec.get("source_url") or "").strip(),
            quote=str(rec.get("quote") or "").strip(),
            notes=str(rec.get("notes") or "").strip(),
        )
        events.append(ev)
    return events


# ----------------------------------------------------------------------------
# 3. 交易日历
# ----------------------------------------------------------------------------

class TradingCalendar:
    """用真实品种日线重建交易日历。

    为什么不用“周一至周五”：法定节假日、临时休市、夜盘影响都会让非交易日出现
    假成交；用真实有成交的日期集合最稳。
    """

    def __init__(self, dates: Iterable[str]):
        self.days: List[str] = sorted({d for d in dates if d})
        self._idx = {d: i for i, d in enumerate(self.days)}
        self._dates = [_dt.date.fromisoformat(d) for d in self.days]

    def __len__(self) -> int:
        return len(self.days)

    def contains(self, d: str) -> bool:
        return d in self._idx

    def index(self, d: str) -> Optional[int]:
        return self._idx.get(d)

    def next_on_or_after(self, d: str) -> Optional[str]:
        i = bisect.bisect_left(self.days, d)
        return self.days[i] if i < len(self.days) else None

    def prev_on_or_before(self, d: str) -> Optional[str]:
        i = bisect.bisect_right(self.days, d) - 1
        return self.days[i] if i >= 0 else None

    def shift(self, d: str, n: int) -> Optional[str]:
        """从 d 所在（或之后的）交易日算起，平移 n 个交易日；越界返回 None"""
        base = self.index(d)
        if base is None:
            nxt = self.next_on_or_after(d)
            if nxt is None:
                return None
            base = self.index(nxt)
        # 若 d 本身不是交易日，base 指向其后第一个交易日，此时 n=0 应返回该日
        j = base + n
        if 0 <= j < len(self.days):
            return self.days[j]
        return None

    def count_between(self, d0: str, d1: str) -> Optional[int]:
        i, j = self.index(d0), self.index(d1)
        return None if (i is None or j is None) else j - i

    def is_holiday_like(self, d: str) -> bool:
        """d 不是该品种交易日 → 可能休市/停牌/数据缺失"""
        return d not in self._idx

    def near_holiday(self, d: str, lookback: int = 5) -> Optional[int]:
        """事件此前 lookback 个自然日内，是否有一天该品种没有交易（用于识别长假）"""
        d0 = _dt.date.fromisoformat(d)
        gap = 0
        for k in range(1, lookback + 1):
            dd = (d0 - _dt.timedelta(days=k)).isoformat()
            if not self.contains(dd):
                gap += 1
        return gap


def calendar_from_csv(path: str, date_col: str = "date") -> TradingCalendar:
    with open(path, encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        dates = [parse_date(row.get(date_col)) for row in rd]
    return TradingCalendar([d for d in dates if d])


# ----------------------------------------------------------------------------
# 4. 去重与重叠
# ----------------------------------------------------------------------------

STOPWORDS = {"甲醇", "装置", "停车", "万吨", "公司", "集团", "检修", "的", "及", "等"}


def _tokens(s: str) -> set:
    s = re.sub(r"\s+", "", s or "")
    return {t for t in re.findall(r"[\u4e00-\u9fa5]{2,4}|[A-Za-z]{2,}", s)} - STOPWORDS


def find_duplicates(events: Sequence[Event], date_tolerance_days: int = 3,
                    jaccard_threshold: float = 0.34) -> List[Dict[str, Any]]:
    """找“同一次停车被多条消息重复报道”。

    判定：日期相近（≤容忍天数）+ 主体/装置文本相似（Jaccard），或产能相同且主体相同。
    返回候选重复组，交给人工裁决；不自动删除。
    """
    groups: List[Dict[str, Any]] = []
    used = set()
    for i, a in enumerate(events):
        if i in used:
            continue
        group = [a]
        for j in range(i + 1, len(events)):
            b = events[j]
            if j in used:
                continue
            da = a.first_market_date or a.actual_start_date
            db = b.first_market_date or b.actual_start_date
            if not da or not db:
                continue
            gap = abs((_dt.date.fromisoformat(da) - _dt.date.fromisoformat(db)).days)
            if gap > date_tolerance_days:
                continue
            ta, tb = _tokens(a.company + a.unit_name + a.event_name), _tokens(b.company + b.unit_name + b.event_name)
            jac = len(ta & tb) / max(1, len(ta | tb))
            same_cap = (a.capacity_wt is not None and a.capacity_wt == b.capacity_wt)
            if jac >= jaccard_threshold or (same_cap and a.company and a.company == b.company):
                group.append(b)
                used.add(j)
        if len(group) > 1:
            used.add(i)
            groups.append({
                "group": [g.event_id for g in group],
                "reason": "日期相近且主体/装置文本相似" if len(group) else "",
                "action": "建议合并为1条，保留证据等级最高者，其余记入重复报道清单",
            })
    return groups


def overlap_pairs(spans: Sequence[Tuple[str, int, int, str]],
                  window: Tuple[int, int] = (-5, 20)) -> List[Dict[str, Any]]:
    """事件窗口重叠检测。

    参数 spans: [(event_id, t_start_idx, t_end_idx, anchor_date), ...]，索引为交易日序号。
    两个样本的 [t_start, t_end] 区间相交即视为重叠；重叠样本的路径不是独立观测，
    必须标注，并在统计中给出“全样本 / 去重叠子样本”双口径。

    去重叠规则（确定性、可复现）：按事件日从早到晚，保留先发生者，
    与已保留样本窗口相交的事件进入排除集。
    """
    ordered = sorted(spans, key=lambda s: s[1])
    pairs: List[Dict[str, Any]] = []
    keep: List[Tuple[str, int, int, str]] = []
    excluded: List[Dict[str, Any]] = []
    for cur in ordered:
        hit = None
        for kp in keep:
            if cur[1] <= kp[2] and kp[1] <= cur[2]:
                hit = kp
                break
        if hit:
            excluded.append({
                "event_id": cur[0], "overlaps_with": hit[0],
                "cur_window": [cur[1], cur[2]], "kept_window": [hit[1], hit[2]],
            })
            pairs.append({"a": hit[0], "b": cur[0], "kept": hit[0], "excluded": cur[0]})
        else:
            keep.append(cur)
    return [{"overlap_pairs": pairs,
             "excluded_in_dedup_subsample": excluded,
             "kept_in_dedup_subsample": [k[0] for k in keep],
             "window": list(window)}]


# ----------------------------------------------------------------------------
# 5. 描述统计
# ----------------------------------------------------------------------------

def quantile(xs: Sequence[float], q: float) -> Optional[float]:
    """线性插值分位数（与 numpy 的默认 linear 一致），小样本也稳定"""
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def describe(xs: Sequence[Optional[float]]) -> Dict[str, Any]:
    v = [x for x in xs if x is not None]
    if not v:
        return {"n": 0, "missing": len(list(xs))}
    mean = sum(v) / len(v)
    var = sum((x - mean) ** 2 for x in v) / (len(v) - 1) if len(v) > 1 else None
    return {
        "n": len(v),
        "missing": len(list(xs)) - len(v),
        "mean": mean,
        "median": statistics.median(v),
        "sd": math.sqrt(var) if var is not None else None,
        "min": min(v),
        "max": max(v),
        "p05": quantile(v, 0.05),
        "p25": quantile(v, 0.25),
        "p75": quantile(v, 0.75),
        "p95": quantile(v, 0.95),
        "win_rate": sum(1 for x in v if x > 0) / len(v),
        "positive_n": sum(1 for x in v if x > 0),
        "negative_n": sum(1 for x in v if x < 0),
        "zero_n": sum(1 for x in v if x == 0),
    }


def bootstrap_ci(xs: Sequence[float], stat: str = "mean", n_boot: int = 5000,
                 alpha: float = 0.05, seed: int = 20261020) -> Optional[Tuple[float, float]]:
    """自助法置信区间。样本很小时区间会很宽——这正是要展示的诚实结论。"""
    import random
    v = [x for x in xs if x is not None]
    if len(v) < 3:
        return None
    rnd = random.Random(seed)
    vals = []
    fn = (lambda s: sum(s) / len(s)) if stat == "mean" else statistics.median
    for _ in range(n_boot):
        vals.append(fn([rnd.choice(v) for _ in v]))
    return (quantile(vals, alpha / 2), quantile(vals, 1 - alpha / 2))


def sign_test_p(xs: Sequence[float]) -> Optional[float]:
    """符号检验（双侧）：H0 为涨跌各半。小样本下用精确二项分布。"""
    v = [x for x in xs if x is not None and x != 0]
    n = len(v)
    if n == 0:
        return None
    k = sum(1 for x in v if x > 0)
    # 精确双侧二项 p 值
    def comb(n_, k_):
        return math.comb(n_, k_)
    tail = sum(comb(n, i) for i in range(0, min(k, n - k) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def wilcoxon_like_summary(xs: Sequence[float]) -> Dict[str, Any]:
    """返回可用于报告的中位数与符号检验；不做正态假设。"""
    v = [x for x in xs if x is not None]
    obs = [x for x in v if x != 0]
    res = {"n": len(v), "n_nonzero": len(obs), "median": statistics.median(v) if v else None}
    if len(obs) >= 6:
        res["sign_test_p"] = sign_test_p(obs)
    else:
        res["sign_test_p"] = None
        res["note"] = "非零样本<6，不做检验，只给描述"
    return res


# ----------------------------------------------------------------------------
# 6. 读写
# ----------------------------------------------------------------------------

def write_csv(path: str, rows: Sequence[Dict[str, Any]], fieldnames: Optional[Sequence[str]] = None,
              encoding: str = "utf-8-sig") -> None:
    if not rows:
        open(path, "w", encoding=encoding).write("")
        return
    fn = list(fieldnames or rows[0].keys())
    with open(path, "w", newline="", encoding=encoding) as f:
        w = csv.DictWriter(f, fieldnames=fn, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fn})


def read_csv(path: str) -> List[Dict[str, Any]]:
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return list(csv.DictReader(io.StringIO(raw.decode(enc))))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法解码：{path}")


def ensure_dir(p: str) -> str:
    os.makedirs(p, exist_ok=True)
    return p


def dump_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
