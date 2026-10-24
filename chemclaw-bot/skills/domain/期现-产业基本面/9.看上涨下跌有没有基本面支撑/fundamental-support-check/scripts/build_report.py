# -*- coding: utf-8 -*-
"""
fundamental-support-check · 参考实现
====================================
把结构化证据数据集（dict）渲染为：
  1) 交互式 HTML 报告（自包含、无外部依赖，含内联 SVG 折线图）
  2) Excel 工作簿（11 个工作表）

用法：
    from build_report import build_all
    build_all(dataset, outdir="out", product="PP", window="2026-10-01 ~ 2026-10-19")

dataset 结构（最小必填）：
{
  "meta":   {"product":..., "window":..., "spot_caliber":..., "fut_caliber":...},
  "sources":[{"id","name","publisher","date","tier","url","note","retrieved"}, ...],
  "series": {"pp":[[date, value|null], ...], "upstream":[[...]], "cost":[[...]]},
  "fut":    [{"date","contract","price","role","source"}, ...],
  "fut_raw": [["2701", open, low, high, close, chg, volume, oi, "source"], ...],
  "windows":[{"name","start","start_price","end","end_price","abs_change","pct","status","note"}, ...],
  "spread": [["2701-2705", near, far], ...],
  "basis":  [{"date","spot","spot_caliber","fut","basis","status","note"}, ...],
  "inventory": [{"item","value","unit","date","prev","change","change_pct","hist_pctile","status","dir","note"}, ...],
  "supply": / "demand": / "cost": / "expect": 同结构,
  "evidence":[{"id","cls","name","period","metric","hist","verdict","status","tier","src","comment"}, ...],
  "caliber": [{"topic","text"}, ...],
  "summary": {"price_verdict","driver","support":[],"diverge":[],"missing":[],"no_conclusion"},
}

完整可运行实例见 examples/pp-2026q4/ （dataset 由同目录的 data.py 提供）。
"""
import json
import os

STATUS_SET = ("支撑上涨", "背离", "数据不足")


# ---------------------------------------------------------------- 校验
def validate(ds):
    errs = []
    if not ds.get("evidence"):
        errs.append("evidence 为空")
    src_ids = {s["id"] for s in ds.get("sources", [])}
    for e in ds.get("evidence", []):
        for k in ("id", "cls", "name", "period", "metric", "status", "tier", "comment"):
            if not e.get(k):
                errs.append(f"证据 {e.get('id')} 缺字段 {k}")
        for sid in e.get("src", []):
            if sid not in src_ids:
                errs.append(f"证据 {e['id']} 引用了不存在的来源 {sid}")
        # 铁律1：期货/盘面价格本身不能作为基本面支撑证据（现货同步上涨可以，但要标注）
        nm = e.get("name", "")
        if e.get("cls") == "价格" and e.get("status") == "支撑上涨" and ("期货" in nm or "主力" in nm or "月差" in nm):
            errs.append(f"证据 {e['id']}：期货/月差类证据不得判定为『支撑上涨』（价格上涨本身不是基本面证据）")
        # 铁律3：预期类不得判支撑
        if e.get("cls") == "预期" and e.get("status") == "支撑上涨":
            errs.append(f"证据 {e['id']}：预期类证据不得判定为『支撑上涨』")
    if errs:
        raise ValueError("数据集校验失败：\n  - " + "\n  - ".join(errs))
    return True


def stats(ds):
    c = {k: 0 for k in STATUS_SET}
    for e in ds["evidence"]:
        if e["status"] in c:
            c[e["status"]] += 1
    return c


# ---------------------------------------------------------------- 指标计算（R 系列）
def pct(a, b):
    if a is None or b in (None, 0):
        return None
    return (a - b) / b


def percentile_rank(vals, v):
    vals = [x for x in vals if x is not None]
    if not vals or v is None:
        return None
    below = sum(1 for x in vals if x < v)
    eq = sum(1 for x in vals if x == v)
    return (below + 0.5 * eq) / len(vals) * 100


def basis(spot, fut):
    """R03 基差"""
    return None if (spot is None or fut is None) else spot - fut


def spread(near, far):
    """R04 月差"""
    return None if (near is None or far is None) else near - far


def processing_spread(down, up, ratio=1.0):
    """R11 加工价差"""
    return None if (down is None or up is None) else down - up * ratio


def transmission_beta(down_pct, up_pct):
    """R12 成本传导率"""
    if down_pct is None or not up_pct:
        return None
    return down_pct / up_pct


def window_return(series, d0, d1):
    """R01 窗口涨幅"""
    m = dict(series)
    if d0 not in m or d1 not in m:
        return None
    a, b = m[d0], m[d1]
    if a in (None, 0) or b is None:
        return None
    return dict(start=a, end=b, abs_change=b - a, pct=(b - a) / a)


# ---------------------------------------------------------------- 渲染入口
def build_all(ds, outdir="out", tag="report"):
    validate(ds)
    os.makedirs(outdir, exist_ok=True)
    html_path = os.path.join(outdir, f"{tag}.html")
    xlsx_path = os.path.join(outdir, f"{tag}.xlsx")
    write_html(ds, html_path)
    write_xlsx(ds, xlsx_path)
    return html_path, xlsx_path


def write_html(ds, path):
    """把 dataset 注入 HTML 模板。模板与本文件同目录的 report_template.html。"""
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_template.html")
    if not os.path.exists(tpl):
        raise FileNotFoundError(
            "缺少 report_template.html。可复制 examples/pp-2026q4/PP-基本面支撑核验报告.html "
            "作为模板，或使用 DSH 工作区中的 build/make_html.py 生成。")
    with open(tpl, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__DATA__", json.dumps(ds, ensure_ascii=False, separators=(",", ":")))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def write_xlsx(ds, path):
    """生成 11 表工作簿（实现见 xlsx_renderer.py）"""
    from xlsx_renderer import render_xlsx
    return render_xlsx(ds, path)


if __name__ == "__main__":
    print(__doc__)
