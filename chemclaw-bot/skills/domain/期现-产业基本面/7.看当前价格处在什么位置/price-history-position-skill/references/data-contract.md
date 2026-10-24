# 数据契约与适配器写法

---

## 1. 统一观测结构

所有数据源都必须归一到这个结构：

```json
{
  "date": "2026-07-28",
  "lo": 1180,
  "hi": 1250,
  "mid": 1215,
  "basis": "华东重质纯碱主流市场报价",
  "url": "https://www.100ppi.com/news/detail-20260728-5990717.html"
}
```

| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `date` | `YYYY-MM-DD` | ✔ | **数据日期**（报价描述的那一天），不是发布日期 |
| `lo` | float | 条件 | 区间低端；区间报价必填 |
| `hi` | float | 条件 | 区间高端；区间报价必填 |
| `mid` | float | ✔ | 主序列取值。区间取中值；单点价则 `lo=hi=mid` |
| `value` | float | 条件 | 单点型序列（如基准价）用这个字段 |
| `basis` | string | ✔ | 该条的原始口径文字（用于审计） |
| `url` | string | ✔ | 原文链接。**没有链接的观测不得入库** |

> 硬规则：`url` 为空的行一律丢弃并计数。不可核验的价格等于编造的价格。

### `date` 与发布日期的区别

很多日评是**次日发布昨日行情**。例如「7 月 28 日华东地区纯碱市场暂稳运行」实际描述的是
**7 月 27 日**的价格调整。必须从正文里取数据日期，不能直接用URL里的发布日期。

案例中的漏判数据：2026-07-28 的文章正文写的是 7 月 27 日下调 50 元。
若按发布日期入库，整条序列会整体错位一天。

---

## 2. 装配后的数据结构（`build/data.json`）

```json
{
  "meta": {
    "product": "纯碱", "spec": "重质纯碱（≥99.2%）", "region": "华东",
    "asof": "2026-07-28", "generated_at": "2026-10-20 16:03",
    "unit": "元/吨", "tax": "含税（增值税13%）",
    "delivery": "主流市场报价 / 实单商谈", "source": "...", "source_url": "..."
  },
  "series": {
    "S1": {"name": "华东·重质纯碱·主流市场区间中值", "role": "主口径",
           "note": "...", "data": [ <观测> ... ]},
    "S2": {...}, "S3": {...}
  },
  "analysis": {
    "S1_mid": {
      "series_n": 358, "first_date": "...", "last_date": "...",
      "last_value": 1215.0, "stale_days": 0,
      "windows": {"365": {...}, "1095": {...}},
      "volatility": {"30": {...}, "90": {...}, "365": {...}},
      "anomalies": {"level": [...], "jump": [...]},
      "seasonality": {"monthly": [...], "season_index": {...}},
      "gaps": {"runs": [...], "run_count": 40, "single_missing": 69},
      "mdd": {"mdd_pct": -42.14, "peak_date": "...", "trough_date": "..."}
    },
    "S1_lo": {...}, "S1_hi": {...}, "S2_mid": {...}, "S3_value": {...}
  },
  "coverage_change": [ {"series": "S1", "months_zero": 11, "first_full_month": "2024-08"} ],
  "caveats": [ {"level": "bad", "title": "...", "body": "..."} ],
  "events": [ {"date": "...", "title": "...", "detail": "...", "source": "...", "url": "..."} ],
  "sources": [ {"name": "...", "used_for": "...", "url": "..."} ]
}
```

### 窗口对象字段

```json
"1095": {
  "available": true,
  "n_obs": 358,
  "from": "2024-07-17", "to": "2026-07-28",
  "stats": {"min": 1215, "max": 2100, "mean": 1457.6, "median": 1450,
            "p10": ..., "p25": ..., "p75": ..., "p90": ..., "std": ...},
  "percentile": {"percentile_inclusive_pct": 0.28,
                 "percentile_midrank_pct": 0.14,
                 "pct_above": 99.72, "n": 358},
  "range_position_pct": 0.0,
  "change": {"pct_change": -42.14, "abs_change": -885.0, "from_date": "...", "from_value": 2100},
  "insufficient_sample": false
}
```

`available: false` 时必须有 `n_obs` 与 `reason`，**不得省略整个窗口对象**——
省略会让前端渲染出「无数据」而不是「样本不足，不计算」，两者含义不同。

---

## 3. 写一个新数据源的适配器

适配器只做一件事：把任意数据源变成 `series` 里的 `data` 数组。

```python
# adapters/my_source.py
import json, re, urllib.request

BASE = "https://example.com/price"

def fetch(date_str):
    """取回一天的原始响应。失败返回 None，不要抛异常打断整批。"""
    try:
        with urllib.request.urlopen(f"{BASE}?d={date_str}", timeout=20) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None

RANGE = re.compile(r"(\d{3,5})\s*[-–~]\s*(\d{3,5})\s*元/吨")

def parse(html, data_date, url):
    """必须返回统一观测结构；解析不出来就返回 None。"""
    m = RANGE.search(html)
    if not m:
        return None
    lo, hi = float(m.group(1)), float(m.group(2))
    if not (lo <= hi) or not (500 <= lo <= 100000):     # 合理性护栏
        return None
    return {"date": data_date, "lo": lo, "hi": hi, "mid": (lo + hi) / 2,
            "basis": "华东重质纯碱主流市场报价", "url": url}
```

### 适配器五条纪律

1. **单条失败不炸批**：返回 `None` 并计数，继续下一条。
2. **合理性护栏**：价格量级、`lo <= hi`、单日变动上限。越界记为可疑并人工复核，**不要静默接受**。
3. **数据日期从正文取**，不从 URL 或列表页取。
4. **保留原文链接**，`url` 缺失即丢弃。
5. **可断点续跑**：已入库的日期跳过，中间失败重跑不重复不计丢。

### 反爬处理（真实经验）

见 `pitfalls.md`。要点：**全局限速 + 冷却并发递增**，不要用密集重试硬碰——
重试越猛，封得越死。

---

## 4. 三条序列的角色划分

| 角色 | 用途 | 规则 |
|---|---|---|
| **主口径 S1** | 回答「这个价在历史什么位置」 | 规格+地区+含税+交付完全对得上客户问的那句话 |
| **辅助 S2** | 同区域不同规格 | 用来说明「规格差异有多大」，不替代 S1 |
| **辅助 S3** | 同规格不同区域 | 用来说明「这是全国现象还是区域现象」，不替代 S1 |

**铁律**：三条各自独立算分位，**永不拼接、永不换算、永不对齐成一条**。
图上看可以同框对比，统计上必须分开。
