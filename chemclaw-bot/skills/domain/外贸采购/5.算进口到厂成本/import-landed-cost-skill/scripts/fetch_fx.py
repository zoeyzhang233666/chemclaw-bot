# -*- coding: utf-8 -*-
"""
fetch_fx.py — 汇率取数工具（市场参考汇率 + 海关计征汇率候选）

设计要点（与 SKILL.md「汇率双轨」原则一致）：
  1. 市场参考汇率：用 exchangerate-api 公开牌价抓取"当前"汇率，仅作市场参考，不能替代银行实际成交价。
  2. 海关计征汇率：按《关税法》第六十条 + 海关总署《确定进出口货物计税价格办法》第16条口径，
     应为"申报之日所对应日期的中国人民银行人民币汇率中间价"（操作惯例：上月第三个星期三，
     遇法定节假日顺延至第四个星期三）。本脚本向 PBOC 外汇牌价接口取数，
     若接口不可达，标记为「待确认」并给出应人工录入的日期 —— 绝不折算成估算值。

用法：
  python fetch_fx.py --base USD --to CNY --out fx_snapshot.json
  python fetch_fx.py --date 2026-10-20 --base USD --to CNY      # 指定申报日，自动推算计征汇率取数日
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) import-landed-cost/1.0"}


def third_wednesday_prev_month(ref: dt.date) -> dt.date:
    """计征汇率取数日 = 上一个月的第三个星期三（法定节假日顺延的情形需人工核对）。"""
    y, m = (ref.year, ref.month - 1) if ref.month > 1 else (ref.year - 1, 12)
    weds = [
        dt.date(y, m, d)
        for d in range(1, calendar.monthrange(y, m)[1] + 1)
        if dt.date(y, m, d).weekday() == 2
    ]
    return weds[2]


def _get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def market_rate(base: str, to: str) -> dict:
    url = "https://api.exchangerate-api.com/v4/latest/" + base
    try:
        data = json.loads(_get(url))
        return {
            "type": "市场参考汇率（公开牌价）",
            "source": "exchangerate-api.com v4 公开牌价",
            "url": url,
            "date": data.get("date"),
            "pair": f"{base}/{to}",
            "rate": data.get("rates", {}).get(to),
            "note": "仅为公开市场参考价，不含银行买卖点差、手续费与锁汇成本；实际购汇成本以银行成交价为准。",
        }
    except Exception as e:  # noqa: BLE001
        return {"type": "市场参考汇率（公开牌价）", "url": url, "rate": None,
                "status": "待确认", "error": str(e)}


def market_rate_ecb(base: str, to: str) -> dict:
    """ECB 欧元参考汇率交叉（frankfurter），独立的第二市场参考源。"""
    url = f"https://api.frankfurter.app/latest?from={base}&to={to}"
    try:
        data = json.loads(_get(url))
        return {"type": "市场参考汇率（ECB 参考汇率交叉）", "source": "European Central Bank via frankfurter.app",
                "url": url, "date": data.get("date"), "pair": f"{base}/{to}",
                "rate": data.get("rates", {}).get(to),
                "note": "ECB 每日参考汇率（非实时），仅作市场参考。"}
    except Exception as e:  # noqa: BLE001
        return {"type": "市场参考汇率（ECB 参考汇率交叉）", "url": url, "rate": None,
                "status": "待确认", "error": str(e)}


def pboc_midrate(ccy: str, day: dt.date) -> dict:
    """中国人民银行人民币汇率中间价（海关计征汇率口径）。"""
    q = urllib.parse.urlencode({"lang": "CN", "startDate": day.isoformat(),
                                "endDate": day.isoformat()})
    url = ("https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json?"
           "t=" + str(int(dt.datetime.now().timestamp() * 1000)) + "&" + q)
    out = {"type": "海关计征汇率口径（PBOC 人民币汇率中间价）",
           "source": "中国外汇交易中心受权公布的人民币汇率中间价（中国人民银行）",
           "url": "https://www.chinamoney.com.cn/chinese/bkccpr/",
           "query_date": day.isoformat(), "pair": f"{ccy}/CNY", "rate": None,
           "is_latest_only": True,
           "note": ("站点 JSON 接口仅返回最新一次中间价，不提供任意历史日期；"
                    "海关计征汇率必须取「申报之日对应日期的上一个月第三个星期三」中间价，"
                    "故此处不填值，标记待确认，请人工查询后录入且不得以最新价代替。")}
    try:
        data = json.loads(_get(url))
        for rec in data.get("records", []):
            if rec.get("vrtEName") == f"{ccy}/CNY":
                out["latest_published_midrate"] = rec.get("price")
                break
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
    out["status"] = "待确认"
    return out


def declared_date_midrate_hint(day: dt.date) -> str:
    """提示人工取数路径。"""
    return (f"申报日 {day.isoformat()} → 计征汇率取数日 {third_wednesday_prev_month(day).isoformat()}"
            "（遇法定节假日顺延至第四个星期三）。请在 chinamoney 历史牌价页 / 海关总署公布的计征汇率表核取。")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="USD")
    ap.add_argument("--to", default="CNY")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="申报日 YYYY-MM-DD")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    dec_date = dt.date.fromisoformat(a.date)
    fx_day = third_wednesday_prev_month(dec_date)
    snap = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "declaration_date": dec_date.isoformat(),
        "customs_rate_fetch_date": fx_day.isoformat(),
        "market": market_rate(a.base, a.to),
        "market_cross": market_rate_ecb(a.base, a.to),
        "customs": pboc_midrate(a.base, fx_day),
        "customs_hint": declared_date_midrate_hint(dec_date),
        "reminder": "海关计税汇率不等于市场汇率；两者必须分别列示，不得互相替代。",
    }
    text = json.dumps(snap, ensure_ascii=False, indent=2)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
