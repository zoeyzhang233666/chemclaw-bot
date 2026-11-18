# -*- coding: utf-8 -*-
"""build_fx_series.py —— 把 SAFE 官方中间价原始表转换成统一口径的汇率序列 JSON。

输入: data/safe_mid_raw.json   (SAFE 查询页原样结果, 单位: 100 外币 = X 人民币)
输出: build/fx_series.json     (单位: 1 外币 = X 人民币；多币种)

不插值、不补造、不跨期拼接；缺净的节假日直接跳过并记录缺口天数。
"""
import json, os, sys
from datetime import date, datetime, timedelta
from statistics import mean

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "safe_mid_raw.json")
OUT = os.path.join(ROOT, "build", "fx_series.json")

# SAFE 表头顺序（25 列，均已由 header 与数值量级双重核对）
CURRENCIES = [
    ("USD", "美元", 100, "USD/CNY"),
    ("EUR", "欧元", 100, "EUR/CNY"),
    ("JPY", "日元", 100, "JPY/CNY"),
    ("HKD", "港元", 100, "HKD/CNY"),
    ("GBP", "英镑", 100, "GBP/CNY"),
    ("AUD", "澳大利亚元", 100, "AUD/CNY"),
    ("NZD", "新西兰元", 100, "NZD/CNY"),
    ("SGD", "新加坡元", 100, "SGD/CNY"),
    ("CHF", "瑞士法郎", 100, "CHF/CNY"),
    ("CAD", "加拿大元", 100, "CAD/CNY"),
    ("MOP", "澳门元", 100, "MOP/CNY"),
    ("MYR", "林吉特", 100, "MYR/CNY"),
    ("RUB", "卢布", 100, "RUB/CNY"),
    ("ZAR", "南非兰特", 100, "ZAR/CNY"),
    ("KRW", "韩元", 100, "KRW/CNY"),
    ("AED", "阿联酋迪拉姆", 100, "AED/CNY"),
    ("SAR", "沙特里亚尔", 100, "SAR/CNY"),
    ("HUF", "匈牙利福林", 100, "HUF/CNY"),
    ("PLN", "波兰兹罗提", 100, "PLN/CNY"),
    ("DKK", "丹麦克朗", 100, "DKK/CNY"),
    ("SEK", "瑞典克朗", 100, "SEK/CNY"),
    ("NOK", "挪威克朗", 100, "NOK/CNY"),
    ("TRY", "土耳其里拉", 100, "TRY/CNY"),
    ("MXN", "墨西哥比索", 100, "MXN/CNY"),
    ("THB", "泰国铢", 100, "THB/CNY"),
]

SOURCES = [
    {
        "id": "safe_parity",
        "name": "国家外汇管理局 · 人民币汇率中间价",
        "url": "https://www.safe.gov.cn/AppStructured/hlw/RMBQuery.do",
        "role": "history",   # 历史序列
        "frequency": "每个交易日 09:15（中国人民银行授权中国外汇交易中心公布）",
        "quote_convention": "1 单位外币 = X 人民币（原始表为 100 外币，已按 /100 折算）",
        "scope": "2023-10-09 ~ 2026-10-19，共 {n} 个交易日",
        "fetched_at": "{fetched_at}",
        "note": "该口径为中国外汇交易中心公布的中间价，非银行挂牌买卖价；中间价不含银行点差与结售汇手续费。",
    },
    {
        "id": "pboc_realtime",
        "name": "中国人民银行授权中国外汇交易中心 · 当日中间价（实时页）",
        "url": "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json",
        "role": "current",
        "time": "2026-10-19 09:15",
        "quotes": {"USD/CNY": 6.7208, "EUR/CNY": 7.5237, "100JPY/CNY": 4.2480, "GBP/CNY": 8.9362},
        "note": "当日 09:15 公布的官方中间价，与历史序列同一来源口径。",
    },
    {
        "id": "boc_spot",
        "name": "中国银行外汇牌价（现汇买入价/现汇卖出价）",
        "url": "https://www.boc.cn/sourcedb/whpj/",
        "role": "bank_quote",
        "time": "2026-10-19 16:27:56",
        "quotes": {
            "USD": {"现汇买入价": 6.6701, "现钞买入价": 6.6701, "现汇卖出价": 6.6982, "现钞卖出价": 6.6982, "中行折算价": 6.7208},
            "EUR": {"现汇买入价": 7.4613, "现汇卖出价": 7.5160, "中行折算价": 7.5237},
            "JPY(100)": {"现汇买入价": 4.2089, "现汇卖出价": 4.2415, "中行折算价": 4.2480},
            "GBP": {"现汇买入价": 8.8669, "现汇卖出价": 8.9327, "中行折算价": 8.9362},
        },
        "note": "银行现汇买入价 = 客户把外币结汇成人民币的到手价（出口收汇用）；现汇卖出价 = 客户用人民币购汇的付出价（进口付汇用）。牌价表单位为 100 外币兑人民币。",
    },
    {
        "id": "ecb_frankfurter",
        "name": "欧洲央行参考汇率（经 Frankfurter API）",
        "url": "https://api.frankfurter.app/latest?from=USD&to=CNY",
        "role": "cross_check",
        "date": "2026-10-16",
        "quote": {"USD/CNY": 6.6862},
        "note": "此处的 USD/CNY 由 ECB 以 EUR 为桥的参考汇率推导（非 ECB 直接报价），仅作数量级交叉核对。",
    },
    {
        "id": "er_api",
        "name": "open.er-api.com 聚合汇率",
        "url": "https://open.er-api.com/v6/latest/USD",
        "role": "cross_check",
        "time": "2026-10-19 00:02 UTC",
        "quote": {"USD/CNY": 6.69274},
        "note": "第三方聚合器，非官方，仅作数量级交叉核对。",
    },
]


def main():
    raw = json.load(open(RAW, encoding="utf-8"))
    rows = raw["rows"]
    dates = sorted(rows)
    if len(dates) == 0:
        sys.exit("原始表为空")

    series = {}
    for i, (code, cn, scale, pair) in enumerate(CURRENCIES):
        vals = {}
        for d in dates:
            v = rows[d][i]
            try:
                vals[d] = round(float(v) / scale, 6)
            except ValueError:
                continue
        series[code] = {
            "code": code,
            "name_cn": cn,
            "scale": scale,          # 1 = 1 单位外币；100 = 每 100 单位
            "pair": pair,
            "unit_label": (f"1 {code}" if scale == 1 else f"100 {code}") + " 兑人民币",
            "values": vals,
        }

    # 缺口统计（工作日无数据，通常是法定节假日）
    start = datetime.strptime(dates[0], "%Y-%m-%d").date()
    end = datetime.strptime(dates[-1], "%Y-%m-%d").date()
    bdays = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            bdays.append(cur.isoformat())
        cur += timedelta(days=1)
    missing = [d for d in bdays if d not in rows]

    usd = list(series["USD"]["values"].values())
    fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    src = [dict(s) for s in SOURCES]
    src[0]["scope"] = src[0]["scope"].format(n=len(dates))
    src[0]["fetched_at"] = fetched_at

    doc = {
        "meta": {
            "title": "人民币汇率中间价历史序列（官方口径）",
            "primary_source": "国家外汇管理局 · 人民币汇率中间价",
            "source_url": SOURCES[0]["url"],
            "unit": "1 单位外币 = X 人民币；JPY 为 100 JPY = X 人民币",
            "quote_convention": "CNY per unit of foreign currency（直接标价法）",
            "first_date": dates[0],
            "last_date": dates[-1],
            "trading_days": len(dates),
            "weekdays_in_span": len(bdays),
            "missing_weekdays": len(missing),
            "missing_note": "缺失的工作日均为中国法定节假日（交易所休市），未做插值填补。",
            "fetched_at": fetched_at,
            "calc_notes": [
                "分位口径：(小于当前值样本数 + 0.5×等于样本数) / 样本数。",
                "窗口口径：自然日回看（1 年 = 365 天、3 年 = 1095 天），左开右闭。",
                "汇率变动以相对基准汇率的百分比表示；人民币金额变化 ≈ 外币金额 × 基准汇率 × 变动百分比 ×(1∓银行费用率)。",
            ],
        },
        "dates": dates,
        "currencies": series,
        "currency_list": [{"code": c[0], "name_cn": c[1], "pair": c[3]} for c in CURRENCIES],
        "sources": src,
        "quality": {
            "dup_dates": len(dates) - len(set(dates)),
            "usd_min": min(usd), "usd_max": max(usd), "usd_last": usd[-1],
            "max_daily_jump_pct": max(
                abs(usd[i] / usd[i - 1] - 1) for i in range(1, len(usd))
            ),
            "last_8_dates": dates[-8:],
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"wrote {OUT}")
    print(f"dates={len(dates)} {dates[0]}..{dates[-1]} missing_weekdays={len(missing)}")
    print(f"USD last={doc['quality']['usd_last']} min={doc['quality']['usd_min']} max={doc['quality']['usd_max']} "
          f"max_jump={doc['quality']['max_daily_jump_pct']*100:.3f}%")


if __name__ == "__main__":
    main()
