# -*- coding: utf-8 -*-
"""Build a self-contained supplier-risk HTML dashboard from data.json.

Usage:
    python build_html.py data.json [out.html]
"""
import json
import re
import sys
from pathlib import Path

from normalize import normalize

BASE = Path(__file__).resolve().parent
DATA_PATH = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else BASE / "data.json"
DATA = normalize(json.loads(DATA_PATH.read_text(encoding="utf-8")))
META = DATA["meta"]
TEMPLATE = BASE / "assets" / "template.html"

PRODUCT = META.get("product", "化工品")
TITLE = META.get("title", f"{PRODUCT}供应商近期风险雷达")
PERIOD_TAG = META.get("period_tag") or META.get("query_date", "")[:7] or "report"
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path.cwd() / f"{TITLE}_{PERIOD_TAG}.html"

WINDOWS = META["windows"]
DEFAULT_KEY = META.get("window_default", "6m")
DEFAULT_WIN = WINDOWS[DEFAULT_KEY]
IN_WINDOW = [e for e in DATA["events"] if DEFAULT_WIN["start"] <= e["date"] <= DEFAULT_WIN["end"]]
SUPPLIERS = DATA["suppliers"]
PROCESSES = {s.get("process", "").strip() for s in SUPPLIERS if s.get("process")}
LISTED = sum(1 for s in SUPPLIERS if s.get("code") != "非上市" and "非上市" not in s.get("market", ""))
NONLISTED = len(SUPPLIERS) - LISTED
LISTED_TEXT = f"{len(SUPPLIERS)} 家 · {LISTED} 家上市 + {NONLISTED} 家非上市" if NONLISTED else f"{len(SUPPLIERS)} 家 · 全部上市"

SCOPE_SUMMARY = META.get("scope_summary")
if not SCOPE_SUMMARY:
    switch = " / ".join(w["label"] for k, w in WINDOWS.items() if k != DEFAULT_KEY)
    names = "、".join(s["name"] for s in SUPPLIERS)
    SCOPE_SUMMARY = (f"{DEFAULT_WIN['label']}（{DEFAULT_WIN['start']} 至 {DEFAULT_WIN['end']}），"
                     f"可切换 {switch}。覆盖 {len(SUPPLIERS)} 家{PRODUCT}生产企业：{names}。")

TOKENS = {
    "TITLE": TITLE,
    "PERIOD_TAG": PERIOD_TAG,
    "PRODUCT": PRODUCT,
    "QUERY_DATE": META.get("query_date", ""),
    "QUERY_TIME": META.get("query_time", META.get("query_date", "")),
    "DEFAULT_WINDOW_LABEL": DEFAULT_WIN["label"],
    "DEFAULT_WINDOW_TAG": DEFAULT_KEY.upper(),
    "DEFAULT_WINDOW_START": DEFAULT_WIN["start"],
    "DEFAULT_WINDOW_END": DEFAULT_WIN["end"],
    "SUPPLIER_COUNT": len(SUPPLIERS),
    "PROCESS_COUNT": len(PROCESSES),
    "EVENT_TOTAL": len(DATA["events"]),
    "EVENT_IN_WINDOW": len(IN_WINDOW),
    "CATEGORY_COUNT": 5,
    "LISTED_TEXT": LISTED_TEXT,
    "FIN_PERIOD": META.get("financial_period", "本期"),
    "SCOPE_SUMMARY": SCOPE_SUMMARY,
}

html = TEMPLATE.read_text(encoding="utf-8")
for key, value in TOKENS.items():
    html = html.replace(f"%%{key}%%", str(value))

left = sorted(set(re.findall(r"%%[A-Z_]+%%", html)))
if left:
    raise SystemExit(f"unreplaced placeholders: {left}")
if html.count("__DATA_JSON__") != 1:
    raise SystemExit("template must contain exactly one __DATA_JSON__ hook")

payload = json.dumps(DATA, ensure_ascii=False)
if "</script>" in payload.lower():
    raise SystemExit("data contains </script>; refuse to inject")
html = html.replace("__DATA_JSON__", payload)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding="utf-8")
print(f"saved: {OUT}")
print(f"suppliers={len(SUPPLIERS)} events={len(DATA['events'])} in_window={len(IN_WINDOW)} bytes={len(html.encode('utf-8'))}")
