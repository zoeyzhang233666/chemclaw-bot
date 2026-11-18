# -*- coding: utf-8 -*-
"""
build_cache.py —— 库存季节性研究的“数据接入层”
==================================================
把原始数据源（周报原文 JSON + 本地抓取缓存 + config.json）解析成一份
规范化的 `data/cache.json`，供 downstream 的 season.py / 报告生成脚本读取。

设计原则
--------
1. 口径与样本不混：华东（江苏+浙江）、全国港口（华东+华南）分别成列；
   A 样本（2022-04 起周度逐地区披露）与 B 样本（2016-08~2018-05 简报加总）
   分别成表，绝不拼接。
2. 每个数据点都带“证据”：截至日、原文发布时间、URL、披露状态。
3. 覆盖范围做量化：地级/省级组件缺失、递推值、替代值都单独打标，
   覆盖偏差用 `east − port_total` 在两者都可得的周次上度量。
4. 断点显式化：config.json 里声明的每一个断点都写进 `breaks`，
   并给出断点前后可用的统计样本。

用法
----
python build_cache.py --config ../examples/01-甲醇-华东港口库存/config.json \
                      --src <原始数据目录> --out <输出目录>

原始数据目录需要包含（见 references/02-数据源与取证清单.md）：
  lz_weekly.json    —— 逐周数值（asof / 江苏 / 浙江 / 广东 / 福建 / 华东总计 / 华南总计 / 港口总计）
  bodies.json       —— 周报原文（url / title / time / body），用于逐条取证
  inventory_2016_2018.csv —— B 样本回溯表（可选）
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

WEEKLY_MAX_GAP_DAYS = 10  # 相邻两期超过 10 天，视为当期缺报

RE_TOTAL = re.compile(r"港口库存总量在([\d.]+)万吨")
RE_CHG = re.compile(r"较上一期数据(增加|减少)([\d.]+)万吨")
RE_REG = re.compile(
    r"华东地区(累库|去库)，库存(增加|减少)([\d.]+)万吨；"
    r"华南地区(累库|去库)，库存(增加|减少)([\d.]+)万吨"
)


def _num(x):
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(v) else v


def _present(x) -> bool:
    """安全判空：None / NaN / NaT / pd.NA 视为缺失，其余视为有值。"""
    if x is None:
        return False
    try:
        if pd.isna(x):
            return False
    except (TypeError, ValueError):
        pass
    return True


def _pick(rec: dict, *cands):
    """
    按候选键顺序取值，容忍键名变体。
    历史抓取缓存曾把 '华东_chg' 一类键名回退成乱码（'����_chg'），
    因此日期类/分项类字段一律用 _pick 读取，并用逐键校验兜底。
    """
    for c in cands:
        if c in rec and rec[c] is not None:
            return rec[c]
    return None


def _regional_chg(rec: dict, region: str):
    """
    取某个大区的周度增减量：先试 '<大区>_chg'，再按“非中文键且以 _chg 结尾”的
    回退键按出现顺序辨认（抓取缓存中这些键以固定顺序落盘：华东在前、华南在后）。
    """
    v = _pick(rec, region + "_chg")
    if v is not None:
        return _num(v)
    fallback = [k for k in rec.keys() if not re.search(r"[\u4e00-\u9fff]", k) and k.endswith("_chg")]
    order = {"华东": 0, "华南": 1}
    i = order.get(region)
    if i is not None and len(fallback) == 2:
        return _num(rec.get(fallback[i]))
    return None


def _signed(sign_word, value):
    if value is None:
        return None
    v = float(value)
    return v if sign_word in ("增加", "累库") else -v


def load_sources(src_dir: Path):
    raw = json.loads((src_dir / "lz_weekly.json").read_text(encoding="utf-8"))
    bodies = {}
    bf = src_dir / "bodies.json"
    if bf.exists():
        for r in json.loads(bf.read_text(encoding="utf-8")):
            if isinstance(r, dict) and r.get("url"):
                bodies[r["url"]] = r
    hist = pd.DataFrame()
    hf = src_dir / "inventory_2016_2018.csv"
    if hf.exists():
        hist = pd.read_csv(hf, encoding="utf-8-sig")
    return raw, bodies, hist


def parse_evidence(body: dict) -> dict:
    """从原文中抽取可核验证据：总量、周变化、区域分项、显性卸货量。"""
    text = (body or {}).get("body") or ""
    out = {"total": None, "chg": None, "east_chg": None, "south_chg": None, "arrival": None,
           "has_region_split": False}
    m = RE_TOTAL.search(text)
    if m:
        out["total"] = float(m.group(1))
    m = RE_CHG.search(text)
    if m:
        out["chg"] = _signed(m.group(1), m.group(2))
    m = RE_REG.search(text)
    if m:
        out["has_region_split"] = True
        out["east_chg"] = _signed(m.group(2), m.group(3))
        out["south_chg"] = _signed(m.group(5), m.group(6))
    m = re.search(r"显性外轮[卸计入货]{0,4}([\d.]+)万吨", text)
    if m:
        out["arrival"] = float(next(g for g in m.groups() if g))
    return out


def build_a_sample(raw, bodies):
    """A 样本：2022-04 起周度逐地区表 + 原文证据。"""
    rows = []
    prev_asof = None
    for r in sorted(raw, key=lambda x: x["asof"]):
        asof = pd.Timestamp(r["asof"])
        url = r.get("url")
        ev = parse_evidence(bodies.get(url))
        rows.append({
            "asof": asof,
            "week": asof,  # 发布日多为周三，直接以截至日为周锚点
            "iso_year": asof.isocalendar().year,
            "iso_week": int(asof.isocalendar().week),
            "posted": r.get("posted"),
            "url": url,
            "title": r.get("title"),
            "jiangsu": _num(r.get("江苏")),
            "zhejiang": _num(r.get("浙江")),
            "guangdong": _num(r.get("广东")),
            "fujian": _num(r.get("福建")),
            "east_tbl": _num(r.get("华东总计")),
            "south_tbl": _num(r.get("华南总计")),
            "port_total": _num(r.get("港口总计")) if _num(r.get("港口总计")) is not None else _num(r.get("total")),
            "east_chg_tbl": _regional_chg(r, "华东"),
            "south_chg_tbl": _regional_chg(r, "华南"),
            "ev_total": ev["total"],
            "ev_east_chg": ev["east_chg"],
            "ev_south_chg": ev["south_chg"],
            "ev_region_split": ev["has_region_split"],
            "ev_arrival": ev["arrival"],
            "gap_days": None if prev_asof is None else (asof - prev_asof).days,
        })
        prev_asof = asof
    df = pd.DataFrame(rows)
    return df


def resolve_east(df: pd.DataFrame) -> pd.DataFrame:
    """
    华东口径取值与“真实周变化”的复原。

    取值优先级：
      1) east_table     —— 原文/表格直接给出的华东总计（江苏+浙江）
      2) east_sum       —— 江苏 + 浙江 两项均在时加总
      3) east_estimated —— 由上一期 + 正文“华东地区累库/去库 X 万吨”递推（必须相邻两期、链长 ≤2）

    关键修正：周报表格给出的是**局部口径**（当期采到的港口），当某一周只采到部分港口、
    下一周补齐时，直接用相邻两期表格值相减会制造一个虚假跳变。因此：
      chg_official = 正文披露的华东增减额（is_chg_official=True，优先）
      chg_table    = 表格值相减（仅用于核对，is_chg_official=False）
    统计与累去库一律使用 `east_dchg`（复原后的真实周变化）。
    """
    df = df.copy()
    df["east_sum"] = [
        (a + b) if (pd.notna(a) and pd.notna(b)) else None
        for a, b in zip(df["jiangsu"], df["zhejiang"])
    ]
    df["east"] = None
    df["east_method"] = None
    df["east_chain"] = 0
    df["east_table_raw"] = [
        round(float(v), 2) if pd.notna(v) else None for v in df["east_tbl"]
    ]
    last_val, last_i, chain = None, None, 0
    # 注意：不要用 df.iterrows()——pandas 3 会把整行升为同一 dtype，
    # 使 object 列中的 None 变成 NaN 或字符串 'None'，导致判空失真。
    for i, east_tbl, east_sum, ev_chg in zip(df.index, df["east_tbl"].tolist(),
                                             df["east_sum"].tolist(), df["ev_east_chg"].tolist()):
        v, method = None, None
        adjacent = (last_i is not None and i - last_i == 1)
        if _present(east_tbl):
            v, method = round(float(east_tbl), 2), "east_table"
        elif _present(east_sum):
            v, method = round(float(east_sum), 2), "east_sum"
        elif last_val is not None and adjacent and _present(ev_chg) and chain < 2:
            v, method = round(last_val + float(ev_chg), 2), "east_estimated"
            chain += 1
        df.at[i, "east"] = v
        df.at[i, "east_method"] = method
        df.at[i, "east_chain"] = chain if method == "east_estimated" else 0
        if v is not None:
            last_val, last_i = v, i
        if method != "east_estimated":
            chain = 0

    # ---- 复原真实周变化 ----
    east_prev = df["east"].shift(1)
    df["east_table_prev"] = east_prev
    df["east_dchg_table"] = [None if not (_present(c) and _present(p)) else round(float(c) - float(p), 2)
                             for c, p in zip(df["east"].tolist(), east_prev.tolist())]
    df["east_dchg_ev"] = df["ev_east_chg"]
    df["east_dchg"] = [
        round(float(ev), 2) if _present(ev) else tbl
        for ev, tbl in zip(df["east_dchg_ev"].tolist(), df["east_dchg_table"].tolist())
    ]
    df["is_chg_official"] = df["east_dchg_ev"].map(_present)
    df["east_dchg_gap"] = [
        None if not (_present(a) and _present(b)) else round(float(a) - float(b), 2)
        for a, b in zip(df["east_dchg_ev"].tolist(), df["east_dchg_table"].tolist())
    ]
    return df


def coverage_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    覆盖与频率标记。
    - n_prov_stated / prov_full：当期四个省份是否齐全（局部口径的证据）
    - east_full：江苏 + 浙江是否齐全
    - gap_long（>10 天）/ gap_very_long（>16 天）：春节前后常见“双周报”，
      只把 >16 天视为确定缺报，避免把正常双周报误判为缺报。
    """
    df = df.copy()
    df["n_prov_stated"] = df[["jiangsu", "zhejiang", "guangdong", "fujian"]].notna().sum(axis=1)
    df["prov_full"] = df["n_prov_stated"] == 4
    df["east_full"] = df[["jiangsu", "zhejiang"]].notna().all(axis=1)
    df["gap_long"] = df["gap_days"].fillna(7) > WEEKLY_MAX_GAP_DAYS
    df["gap_very_long"] = df["gap_days"].fillna(7) > 16
    df["week_missing"] = df["gap_very_long"]
    return df


def coverage_bias(df: pd.DataFrame) -> pd.DataFrame:
    """在华东与全国港口都可得的周次上，度量华南占总量比例的变化（样本覆盖漂移证据）。"""
    d = df.dropna(subset=["east", "port_total"]).copy()
    d["south_share"] = (d["port_total"] - d["east"]) / d["port_total"]
    d["year"] = d["asof"].dt.year
    return d


def share_ref_south(df: pd.DataFrame, ref_days: int = 365) -> float:
    """
    近 ref_days 天“华南 / 全国港口”比例的中位数。
    作为把全国港口总量折算为华东时的参考占比——只用于**水平定位**，
    不进入分位计算，且必须标注为替代值。
    """
    d = df.dropna(subset=["east", "port_total"]).copy()
    if d.empty:
        return float("nan")
    d["south_share"] = (d["port_total"] - d["east"]) / d["port_total"]
    asof = pd.to_datetime(df["asof"]).max()
    recent = d[pd.to_datetime(d["asof"]) >= asof - pd.Timedelta(days=ref_days)]
    base = recent if len(recent) else d
    return float(base["south_share"].median())


def add_east_from_port(df: pd.DataFrame, ref_days: int = 365) -> pd.DataFrame:
    """
    生成华东水平替代值 east_from_port = 全国港口总量 ×（1 − 华南占比参考值）。
    缺失期（水平不再逐地区披露）用它做“大致在哪”的定位，禁止用于分位与结论。
    """
    df = df.copy()
    share = share_ref_south(df, ref_days)
    df["east_from_port"] = [round(float(p) * (1 - share), 2) if pd.notna(p) else None
                            for p in df["port_total"]]
    df.attrs["share_ref_south"] = share
    return df


def build_b_sample(hist: pd.DataFrame) -> pd.DataFrame:
    if hist is None or hist.empty:
        return pd.DataFrame()
    h = hist.copy()
    h["asof"] = pd.to_datetime(h["asof"])
    h["iso_year"] = h["asof"].dt.isocalendar().year
    h["iso_week"] = h["asof"].dt.isocalendar().week
    cols = ["asof", "iso_year", "iso_week"]
    for k in ("江苏", "浙江", "广东", "福建"):
        if k in h.columns:
            cols.append(k)
    out = h[cols].rename(columns={"江苏": "jiangsu", "浙江": "zhejiang", "广东": "guangdong", "福建": "fujian"})
    if "total" in h.columns:
        out = out.assign(port_total=h["total"].values)
    out = out.rename(columns={"iso_year": "iso_year", "iso_week": "iso_week"})
    out["year"] = out["asof"].dt.year
    return out


def annotate_breaks(df: pd.DataFrame, breaks: list) -> pd.DataFrame:
    df = df.copy()
    df["break_flag"] = ""
    for b in breaks:
        bdate = pd.Timestamp(b["date"])
        before = df["asof"] < bdate
        after = df["asof"] >= bdate
        if "披露" in b["kind"] or "范围" in b["kind"]:
            # 标记断点当周之后的数据点
            df.loc[after, "break_flag"] = df.loc[after, "break_flag"].astype(str) + b["kind"] + ";"
        else:
            df.loc[before, "break_flag"] = df.loc[before, "break_flag"].astype(str) + b["kind"] + ";"
    df["break_flag"] = df["break_flag"].replace("nan", "")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    raw, bodies, hist = load_sources(Path(args.src))

    a = build_a_sample(raw, bodies)
    a = resolve_east(a)
    a = coverage_flags(a)
    a = add_east_from_port(a)          # 华东水平替代值（仅用于缺失期定位）
    a = annotate_breaks(a, cfg.get("breakpoints", []))

    # 证据一致性检查：原文总量 vs 数据表总量
    a["ev_total_diff"] = [
        (round(t - e, 2) if (_present(t) and _present(e)) else None)
        for t, e in zip(a["port_total"], a["ev_total"])
    ]
    a["ev_ok"] = a["ev_total_diff"].apply(lambda x: (x is None) or abs(x) < 0.02)
    a["east_chg_vs_ev"] = [
        (round(float(c) - float(e), 2) if (_present(c) and _present(e)) else None)
        for c, e in zip(a["east_chg_tbl"], a["ev_east_chg"])
    ]

    bias = coverage_bias(a)
    b = build_b_sample(hist)

    summary = {
        "a_weeks": int(len(a)),
        "a_start": a["asof"].min().strftime("%Y-%m-%d"),
        "a_end": a["asof"].max().strftime("%Y-%m-%d"),
        "a_prov_full_weeks": int(a["prov_full"].sum()),
        "a_east_full_weeks": int(a["east_full"].sum()),
        "a_east_available": int(a["east"].notna().sum()),
        "a_east_derived": int((a["east_method"] == "derived").sum()),
        "a_ev_region_split": int(a["ev_region_split"].sum()),
        "a_ev_ok_weeks": int(a["ev_ok"].sum()),
        "a_missing_weeks": int(a["week_missing"].sum()),
        "b_weeks": int(len(b)),
        "b_start": (b["asof"].min().strftime("%Y-%m-%d") if len(b) else None),
        "b_end": (b["asof"].max().strftime("%Y-%m-%d") if len(b) else None),
    }

    # 覆盖偏差统计（按年）
    bias_year = (
        bias.groupby("year")
        .agg(n=("south_share", "size"), south_share_med=("south_share", "median"),
             south_share_min=("south_share", "min"), south_share_max=("south_share", "max"))
        .reset_index()
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    a.attrs["share_ref_south"] = float(a.attrs.get("share_ref_south", share_ref_south(a)))
    a.to_pickle(out / "a_sample.pkl")
    b.to_pickle(out / "b_sample.pkl")
    payload = {
        "cfg": cfg,
        "summary": summary,
        "a_records": json.loads(a.assign(asof=a["asof"].dt.strftime("%Y-%m-%d")).to_json(orient="records", force_ascii=False, date_format="iso")),
        "b_records": (json.loads(b.assign(asof=b["asof"].dt.strftime("%Y-%m-%d")).to_json(orient="records", force_ascii=False, date_format="iso"))
                      if len(b) else []),
        "coverage_bias_year": json.loads(bias_year.to_json(orient="records", force_ascii=False, date_format="iso")),
    }
    (out / "cache.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()


