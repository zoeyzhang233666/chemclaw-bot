# 数据契约

三份输入 + 一份研究层，JSON 字段定义。全部 UTF-8。

---

## 1. `build/prices.json` —— 价格输入

```json
{
  "trade_days": ["2020-06-01", "2020-06-02", "..."],
  "spot":   [{"date": "2020-06-01", "value": 1333.33}],
  "future": [{"date": "2020-06-01", "value": 1476.0}],
  "basis":  [{"date": "2020-06-01", "value": -142.67}]
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `trade_days` | 否 | 交易日历。缺省时取 `future` 的日期；再缺则取 `spot` |
| `spot` | 建议 | 现货。缺失时现货与基差指标全部留空 |
| `future` | 建议 | 期货。缺失时期货与基差指标全部留空 |
| `basis` | 否 | 独立基差。缺省时由**同日** `spot − future` 现场计算；两值不全即留空，**绝不跨日拼凑** |

> `trade_days` 必须覆盖**事件前后完整窗口**，否则窗口会因越界被判失败。
> 若某日无数据，把该日从 `spot` 里删掉即可，不要在 `trade_days` 里删——日历要连续。

---

## 2. `build/events.json` —— 事件配置

```json
{
  "product": "纯碱（重质纯碱，SA 期货）",
  "unit": "元/吨",
  "windows": [1, 5, 10, 20],
  "events": [ { ...事件对象... } ]
}
```

### 事件对象字段

**必填**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str | 唯一编号，如 `E3`、`E9a` |
| `name` | str | 政策文件全称 |
| `market_first_aware` | date | **市场第一次能获知**的时间。征求意见稿/吹风/媒体先曝 → 填更早那天 |
| `comparable_group` | str | 可比组 ID（`G1`/`G2`/`GPL`…）。**不同组永不合并统计** |

**强烈建议**

| 字段 | 说明 |
|---|---|
| `publish_date` | 原文正式发布日 |
| `effective_date` | 政策生效日。缺省则跳过该锚点 |
| `policy_type` | 政策类型，用于分类筛选 |
| `scope` | 全国 / 区域 / 单企业 |
| `strength` | 强 / 中 / 弱 |
| `binding` | true=强制，false=指导 |
| `status` | 核验状态：`原文已核（…）` / `二手转载` / `存疑` / `未找到` |
| `sources` | `[{title, url, verified}]` 政策原文链接 |

**展示与判读**

| 字段 | 说明 |
|---|---|
| `short` | 时间线/曲线上的短标签 |
| `issuer` / `doc_no` | 发布机关 / 文号 |
| `objects` | 涉及产品、区域、企业、监管对象 |
| `region_detail` / `enterprises` | 区域明细 / 受影响企业产能 |
| `channel` | 传导渠道 |
| `content` | 政策核心内容（原文要点，2~4 句） |
| `content_short` | 一句话摘要 |
| `fact_summary` | 窗口内**发生了什么**（只写事实） |
| `interpretation` | 可能的归因与**边界**（必写"不能把…全部归因于"） |
| `confounders` | string[] 同期混杂因素 |
| `comparable_note` | 分组理由 |
| `in_stats` | 是否纳入统计（边界事件填 false） |

> **`interpretation` 是防线**：每条都必须显式写出归因边界。
> 自检时若发现某事件的 `interpretation` 里没有出现"不能/不等同/无法分离/仅"这类限定词，说明写成了断言，要改。

---

## 3. `event_study.py` 输出

### `event_stats.json`

```json
{
  "product": "...", "unit": "元/吨", "windows": [1,5,10,20],
  "calendar": {"start": "...", "end": "...", "n_days": 1546},
  "data_coverage": {"spot": {"n":1546,"first":"...","last":"..."}, "...": {}},
  "min_n_for_significance": 5,
  "gaps": ["没有现货序列：..."],
  "groups": {"G1": ["E2","E3"], "GPL": ["E12"]},
  "events": [
    {
      "id": "E3", "name": "...", "meta": { ...原事件对象... },
      "anchors": {
        "market_first_aware": {
          "ok": true,
          "align": {"anchor":"2021-08-17","first_trade_day":"...","base_date":"...",
                    "anchor_is_trading_day": true, "shift_days":0,
                    "ends": {"1": {"idx":10,"date":"...","ok":true}}},
          "windows": {
            "base": {"date":"...","spot":2483.33,"future":2757.0,"basis":273.67},
            "1": {"ok":true,"date":"...","spot":..,"future":..,"basis":..,
                  "spot_chg":..,"future_chg":..,"basis_chg":..,
                  "spot_pct":..,"future_pct":..}
          },
          "path": [{"k":0,"date":"...","spot":..,"future":..,"basis":..}],
          "lead_days_pub_to_eff": 0
        },
        "publish_date": {...}, "effective_date": {...}
      }
    }
  ],
  "stats": {
    "market_first_aware": {
      "1": {
        "future_chg": {
          "G1": {
            "n":5, "mean":10.0, "median":3.0, "std":61.9,
            "min":-45.0, "max":112.0, "iqr":..,
            "positive_ratio":0.6,
            "quantiles":{"q0.00":..,"q0.25":..,"q0.50":..,"q0.75":..,"q1.00":..},
            "significance_allowed":true, "significant":false,
            "p_value":0.7363, "test":"one-sample t-test...", "t_stat":..,
            "members":[{"id":"E2","value":3.0}]
          }
        },
        "spot_chg": {...}, "basis_chg": {...}, "spot_pct": {...}, "future_pct": {...}
      },
      "5": {...}, "10": {...}, "20": {...}
    },
    "publish_date": {...}, "effective_date": {...}
  }
}
```

**关键不变量**（自检会验）：
- `significance_allowed == false` ⇒ `p_value is None`
- 缺失价格 ⇒ 路径里该点 `null`，绝不出现插值后的小数
- `basis_chg` 不提供百分比（基差可正可负，百分比无意义）

### `event_windows.csv`
扁平表：`event_id,event_name,anchor,anchor_date,window,window_end,spot_base,spot_end,spot_chg,spot_pct,future_base,...,basis_chg,comparable_group`

### `paths.json`
`[{id, name, anchors: {anchor_key: [path...]}}]`，供绘图。

---

## 4. `build/research.json` —— 研究事实层（HTML/Excel 唯一数据源）

```json
{
  "meta": {"product":"...","title":"...","subtitle":"...","scope":"...","period":"...","asof":"2026-10-20"},
  "tags": [{"text":"13 个政策事件","hi":true}],
  "verdict": {
    "kpis": [{"label":"...","value":"...","note":"..."}],
    "callouts": [{"level":"danger|warn|info|ok","html":"<b>一、…</b>…"}]
  },
  "dataQuality": {
    "sources": [{"key":"spot","name":"...","scope":"...","coverage":"...","freq":"...",
                 "grade":"中-高（双源交叉验证一致）","url":"...","fetched":"...","note":"..."}],
    "gaps": ["..."], "notes": "..."
  },
  "comparability": {
    "mergeable": false,
    "verdict": "...",
    "dimensions": [{"dim":"约束性","same":false,"note":"..."}],
    "groups": [{"id":"G1","members":"E2, E3","n":5,"allow":true,"reason":"..."}]
  },
  "confounders": [{"when":"...","factor":"...","type":"...","why":"...","impact":"..."}],
  "limits": [{"title":"1 · 样本量的硬约束","level":"danger","body":"..."}],
  "events": [ ...与 events.json 同结构 + windows/paths 由构建器回填... ],
  "xlsxConclusions": ["【重要】…"],
  "xlsxNav": [["01 政策原文与日期","…"]],
  "method": [{"k":"事件对齐方式","v":"…"}],
  "footer": "..."
}
```

### `level` 取值含义
| level | 用途 |
|---|---|
| `danger` | 会改变结论的重大限制（样本不足、归因陷阱、信息污染） |
| `warn` | 需注意的方法问题（锚点敏感、窗口重叠、口径偏差） |
| `info` | 中性说明 |
| `ok` | 通过/可用的判定 |

### `events[].windows` 回填结构（构建器自动填，勿手写）
```json
{"1": {"date":"...","spot":..,"spot_chg":..,"spot_pct":..,
       "future":..,"future_chg":..,"future_pct":..,"basis":..,"basis_chg":..}}
```

---

## 5. 校验清单

- [ ] 每个事件的三个日期至少填 `market_first_aware`，另两个尽量填
- [ ] `comparable_group` 全部有值，且分组理由写在 `comparable_note`
- [ ] 每个事件 `sources` 至少 1 条且 `url` 可打开
- [ ] `verdict.callouts` 覆盖：显著性、锚点敏感、最大归因陷阱、核验修正、信息污染
- [ ] `dataQuality.gaps` 每条都有"缺什么 + 为什么 + 影响"
- [ ] `limits` 至少包含"样本量"与"不能证明因果"两条
- [ ] 所有结论数字来自 `event_stats.json`，无手敲
