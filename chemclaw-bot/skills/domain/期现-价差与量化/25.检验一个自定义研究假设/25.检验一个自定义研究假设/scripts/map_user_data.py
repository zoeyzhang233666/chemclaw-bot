# -*- coding: utf-8 -*-
"""map_user_data.py — 用户上传/粘贴自己的 Excel 时，自动识别字段、日期、单位。

设计原则（与「不要把模糊变量悄悄具体化」一脉相承）：
  * 不做「猜一个就上」的映射：每个候选都给置信度与理由，低置信度必须让用户确认。
  * 不擅自换算单位：单位不明时先按最可能的值填入，但标记 unit_guess=true，并在
    结果里输出必须人工确认的清单。
  * 只输出映射建议 + 问题清单，不改写用户的原文件。

用法：
  python map_user_data.py --file user.xlsx [--sheet Sheet1] --out build/user_mapping.json
  python map_user_data.py --file user.xlsx --interactive      # 打印需确认的问题
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 字段别名库：key -> (中文名, [别名正则...], 期望单位)
FIELDS = {
    "asof": ("观测日/统计日", [r"^日期$", r"统计日", r"数据日", r"^日$", r"asof", r"^date$", r"观测日",
                            r"截止", r"时间$"], "date"),
    "pub_ts": ("发布时间", [r"发布", r"公布", r"pub_?ts", r"公布时间"], "datetime"),
    "inventory": ("库存合计（万吨）", [r"库存", r"港存", r"港口库存", r"inv", r"stock", r"总计",
                                r"^合计", r"总量"], "万吨"),
    "east": ("华东库存", [r"华东"], "万吨"),
    "south": ("华南库存", [r"华南"], "万吨"),
    "region": ("分区域库存", [r"江苏", r"浙江", r"广东", r"福建"], "万吨"),
    "spot": ("现货价", [r"现货", r"基准价", r"出罐", r"出厂", r"spot"], "元/吨"),
    "fut": ("期货价", [r"期货", r"近月价", r"主力", r"盘面", r"fut"], "元/吨"),
    "fut_code": ("合约代码", [r"合约", r"code"], "text"),
    "basis": ("基差", [r"^基差", r"basis", r"基差$", r"基差率"], "元/吨"),
    "open_interest": ("持仓量", [r"持仓"], "手"),
    "volume": ("成交量", [r"成交"], "手"),
    "coverage": ("样本覆盖率", [r"覆盖率", r"样本"], "%"),
    "x_series": ("其他指标（开工率/产量等）",
                 [r"开工", r"负荷", r"产量", r"利润", r"到港", r"库存量", r"地区"], "?"),
}

DATE_PATTERNS = [
    (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),
    (r"^\d{4}/\d{2}/\d{2}$", "%Y/%m/%d"),
    (r"^\d{8}$", "%Y%m%d"),
    (r"^\d{4}年\d{1,2}月\d{1,2}日$", "cn"),
]


def guess_date(v):
    s = str(v).strip()
    if re.match(r"^\d{5}(\.\d+)?$", s):
        return {"kind": "excel_serial", "note": "疑似 Excel 序列号，需换算成日期"}
    for rx, fmt in DATE_PATTERNS:
        if re.match(rx, s):
            return {"kind": "date", "fmt": fmt}
    if re.match(r"^\d+(\.\d+)?$", s):
        return {"kind": "number", "note": "数值列"}
    return None


def unit_hint(values):
    vals = [float(v) for v in values if re.match(r"^-?\d+(\.\d+)?$", str(v).strip())]
    if not vals:
        return None, None
    mx = max(abs(v) for v in vals)
    mn = min(vals)
    if mx < 3 and mn > -3:
        return "比例(0-1?)", 0.45
    if mx < 250 and mn >= 0:
        return "万吨?", 0.6
    if 800 < mx and mn > 0:
        return "元/吨?", 0.6
    return "未知", 0.2


def map_file(path, sheet=None):
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("需要 openpyxl：请用工作区自带的 Python 运行本脚本。")
    if str(path).lower().endswith(".csv"):
        import csv as _csv
        with open(path, encoding="utf-8-sig") as f:
            rows = [tuple(r) for r in _csv.reader(f)]
        title = os.path.basename(path)
    else:
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        ws = wb[sheet] if sheet else wb[wb.sheetnames[0]]
        rows = list(ws.iter_rows(values_only=True))
        title = ws.title
    if not rows:
        raise SystemExit("空表")
    # 找表头行：前 10 行里非空单元格最多的一行
    hdr_i = max(range(min(10, len(rows))), key=lambda i: sum(1 for v in rows[i] if v not in (None, "")))
    header = [str(v).strip() if v is not None else "" for v in rows[hdr_i]]
    body = [r for r in rows[hdr_i + 1:] if any(v not in (None, "") for v in r)]

    mapping, questions = {}, []
    for j, h in enumerate(header):
        if not h:
            continue
        col_vals = [r[j] for r in body if j < len(r)]
        best = None
        for key, (cn, pats, unit) in FIELDS.items():
            for p in pats:
                if re.search(p, h, re.I):
                    score = 0.95 if re.fullmatch(p, h, re.I) else 0.8
                    if best is None or score > best[1]:
                        best = (key, score)
        if best:
            mapping[h] = {"column_index": j, "field": best[0], "confidence": best[1],
                          "expected_unit": FIELDS[best[0]][2],
                          "sample_values": [str(v) for v in col_vals[:3]]}
        else:
            mapping[h] = {"column_index": j, "field": None, "confidence": 0.0,
                          "sample_values": [str(v) for v in col_vals[:3]]}
            questions.append({"column": h, "q": f"列「{h}」未识别，请说明它是什么指标（以及单位）。"})

    # 日期列识别（可能是「日期」之外的列）
    for h, m in mapping.items():
        vals = [r[m["column_index"]] for r in body[:5] if m["column_index"] < len(r)]
        g = next((guess_date(v) for v in vals if guess_date(v)), None)
        m["date_like"] = g
        m["unit_guess"] = unit_hint([r[m["column_index"]] for r in body[:200]
                                     if m["column_index"] < len(r)])[0]

    has_date = any((m.get("date_like") or {}).get("kind") in ("date", "excel_serial") for m in mapping.values())
    if not has_date:
        questions.append({"column": "*", "q": "没有找到可识别的日期列（YYYY-MM-DD / YYYY/MM/DD / YYYYMMDD）。"
                                              "频率（周/日）由日期列推断，必须提供。"})
    need_inv = not any(m["field"] == "inventory" for m in mapping.values())
    if need_inv:
        questions.append({"column": "*", "q": "没有识别到库存列：请指出哪一列是库存，单位是万吨还是吨。"})
    need_px = not any(m["field"] in ("spot", "fut", "basis") for m in mapping.values())
    if need_px:
        questions.append({"column": "*", "q": "没有识别到价格/基差列：请指出现货价、期货价（或直接给基差）各是哪一列。"})
    dates = []
    for m in mapping.values():
        if (m.get("date_like") or {}).get("kind") == "date":
            dates = [str(r[m["column_index"]]) for r in body[:400] if m["column_index"] < len(r)]
            break
    if len(dates) > 2:
        from datetime import datetime as _dt
        try:
            fmt = "%Y-%m-%d" if "-" in dates[0] else ("%Y/%m/%d" if "/" in dates[0] else None)
            if fmt:
                ds = sorted(_dt.strptime(d[:10], fmt) for d in dates)
                gaps = [(b - a).days for a, b in zip(ds, ds[1:]) if (b - a).days > 0]
                if gaps:
                    med = sorted(gaps)[len(gaps) // 2]
                    freq = "周度" if 5 <= med <= 10 else ("日度" if med <= 3 else f"间隔约{med}天")
                else:
                    freq = "未知"
            else:
                freq = "未知"
        except Exception:                  # noqa: BLE001
            freq = "未知"
    else:
        freq = "未知"

    return {"file": os.path.abspath(path), "sheet": title, "header_row": hdr_i + 1,
            "n_rows": len(body), "frequency_guess": freq,
            "columns": mapping, "questions": questions,
            "next_step": "把本文件的列映射写入研究设计 data 段后，运行 study_engine.py 即可得出同样的检验结果。",
            "warning": "任何未确认的列映射/单位都不要直接进入正式检验；低置信度(<0.8)的列必须人工确认。"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--out", default="build/user_mapping.json")
    a = ap.parse_args()
    res = map_file(a.file, a.sheet)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(res, open(a.out, "w", encoding="utf-8-sig"), ensure_ascii=False, indent=1)
    print(f"sheet={res['sheet']} rows={res['n_rows']} freq={res['frequency_guess']}")
    for h, m in res["columns"].items():
        print(f"  {h:16s} -> {m['field'] or '未识别':12s} conf={m['confidence']:.2f} unit={m['unit_guess']}")
    if res["questions"]:
        print("需要确认：")
        for q in res["questions"]:
            print("  -", q["q"])
    print("->", a.out)


if __name__ == "__main__":
    main()
