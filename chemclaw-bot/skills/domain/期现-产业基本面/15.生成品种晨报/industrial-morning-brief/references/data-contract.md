# 数据契约（research.json / data.json）

两个文件是同一份信息的「输入态」与「输出态」。
`research.json` 由研究者手写（唯一需要人判断的文件）；`data.json` 由 `assemble.py` 生成，HTML 与 Excel 都只读它，因此**两者永远同源**。

---

## 一、research.json

### 顶层

```json
{
  "report":     { ... },   // 本期元信息
  "profile":    { ... },   // 研究配置（可跨期复用）
  "paths":      { "raw": "raw" },
  "futures":    { ... },   // 需要抓取的期货序列
  "indicators": [ ... ],   // 指标清单（核心）
  "events":     [ ... ],   // 事件清单（一般由 dedupe.py 产出后合入）
  "excluded":   [ ... ],   // 明确排除的资讯及理由
  "gaps":       [ ... ],   // 数据缺口
  "sources":    [ ... ],   // 来源清单
  "chain":      { ... }    // 产业链结构
}
```

### report

| 字段 | 必填 | 说明 |
|---|---|---|
| `report_date` | ✔ | 报告日，`YYYY-MM-DD`。决定「陈旧天数」的计算基准 |
| `prev_baseline_date` | ✔ | 对比基线日 |
| `prev_label` | | 基线的可读描述，如「上一期晨报 10月16日（上周五收盘）」 |
| `title` / `products` / `cutoff` | ✔ | 标题、品种数组、数据截止说明 |
| `session_note` | ✔ | 本期口径说明，显示在页面顶部提示条 |
| `issue` | | 期号，用于历史晨报对照 |

### futures

```json
"futures": {
  "甲醇": {"secid": "115.MAM", "series_label": "MA主连",
           "name": "甲醇主连", "main_month_label": "MA2701"}
}
```

`main_month_label` **强烈建议填**：主连在换月日会跳接，只有同时持有主力实际月份才能算出可比涨跌（见 `change-detection.md` 第 4 节）。

### indicators（核心，逐条）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✔ | 稳定唯一键。**跨期必须保持不变**，否则基线对不上 |
| `product` | ✔ | 品种中文名 |
| `module` | ✔ | `price` / `basis` / `spread` / `inventory` / `runrate` / `demand` / `cost` |
| `name` | ✔ | 指标全名，含规格，如「华东 PVC 电石法现货价」 |
| `spec` / `region` / `unit` / `tax` | ✔ | 四要素。缺税基的现货与期货不可比 |
| `freq` | ✔ | `daily` / `weekly` / `monthly` |
| `current` / `data_date` | ✔ | 本期值 + **它自己的发布日期**（不是报告日） |
| `base` / `base_date` | | 同口径上期值。首次出现留空 → 自动判为「新增指标」 |
| `tier` | | 人工建议级别；最终以算法结果为准（`significance`） |
| `formula` | | 派生指标必填，如「江苏主流价 3,965 − 主力收盘 3,143」 |
| `what` | ✔ | 发生了什么。只陈述事实与数字 |
| `why` | ✔ | 为什么重要。讲传导机制，不下方向结论 |
| `verify` | ✔ | 今天继续验证什么。必须可执行、可检验 |
| `history` | | `[{date, v, tag}]`，供抽屉展示历史轨迹 |
| `source` / `source_url` | ✔ | 来源名称与可点开的链接 |
| `note` | | 备注 |

**四要素缺一不可**，因为「3,965」这个数字离开「江苏、含税、元/吨、10-19」就毫无意义，而没有意义的数据不该出现在晨报里。

### events / excluded / gaps / sources / chain

见样例 `examples/01-ma-pp-pvc-2026-10-20/research.json`，字段直观。要点：

- `events[].event_date` 是**事件发生日**，与 `data_date` 严格区分；
- `gaps[]` 三项：`item` / `why` / `how`，即「缺什么 / 为什么缺 / 怎么补」；
- `excluded[]` 必须写 `reason`，并尽量给出 `check`（别人如何自行核对你的排除判断）。

---

## 二、data.json（自动生成，勿手改）

```
{
  "meta":       { generated, tool, version },
  "report":     {...},                      // 原样透传
  "profile":    {...},
  "baseline":   { "date", "label", "prev_label", "indicator_count" },
  "futures":    { "甲醇": {close, open, high, low, pct_day, pct_day_method,
                           rolled, open_chg_pct, prev_close, prev_date,
                           chg_5d, chg_20d, chg_60d, year_pos, quarter_pos,
                           candles_60[], candles_250[], main_month{}, n, first} },
  "indicators": [ { ...见下 } ],
  "events":     [ { ...见下 } ],
  "excluded":   [...],
  "gaps":       [...],
  "sources":    [...],
  "chain":      {...},
  "summary":    { indicators_total, with_base, is_new, tier_A/B/C,
                  events_total, events_A/B/C, events_dup, events_repeat }
}
```

### indicators 输出字段（在输入基础上追加）

| 字段 | 说明 |
|---|---|
| `abs` / `pct` | 变动绝对值 / 百分比。`base` 为空时为 `null`，**不会算成 0** |
| `has_base` / `is_new` | 是否有可比基线 / 是否为首次出现 |
| `base_source` | 基线来源。三种值：`上一期报告` / `配置指定（上一期该指标未发布）` / `配置指定（上一期沿用了源头未更新）` |
| `stale_days` | 数据发布日期距报告日天数。`>1` 时页面标「未更新」 |
| `significance` | 算法级别 `A/B/C`，覆盖输入的 `tier` |

### events 输出字段

| 字段 | 说明 |
|---|---|
| `event_type_cn` | 事件类型中文名（英文枚举只留在原始数据） |
| `score` / `tier` | 重要性评分与级别 |
| `dup_count` / `dup_sources` / `dedupe_note` | 合并了多少条转载、来自谁 |
| `status` | `done` 已兑现 / `ongoing` 持续推进 / `plan` 计划未兑现 / `repeat` 旧闻仅进展 / `comment` 观点类 |
| `repeat_note` | 旧闻的时效提示文案 |
| `exclude_reason` | C 级不进正文的原因 |
| `stale_days` | 事件发生日距报告日天数 |

---

## 三、基线文件的两种合法形态

`assemble.py --baseline` 同时接受：

1. **上一期的 `data.json`**（首选）：读每条指标的 `current` / `current_date`；
2. **上一期的 `research.json`**：读 `current` / `data_date`，缺失时退回 `base` / `base_date`。

两者字段命名不同（`current_date` vs `data_date`），解析器已两边兼容。上传基线时最容易踩的坑是把 `research.json` 当 `data.json` 读，导致所有日期落到 `base_date`、上期值错位——如果发现上期日期普遍比预期早一天，先查这里。

## 四、跨期稳定性的要求

`id` 是唯一关联键。修改 `id` 等于宣告「这是一个新指标」，上一期数据不会被继承。
因此**第一次建好 `id` 后就不要改**；确实要拆指标时，用新 id 并让旧 id 退休，不要原地改名。

## 五、最小可用示例

```json
{
  "report": {"report_date": "2026-10-20", "prev_baseline_date": "2026-10-16",
             "title": "甲醇晨报", "products": ["甲醇"], "cutoff": "10-20 10:00",
             "session_note": "期货收盘 vs 上期收盘"},
  "paths": {"raw": "raw"},
  "futures": {"甲醇": {"secid": "115.MAM", "series_label": "MA主连",
                       "name": "甲醇主连", "main_month_label": "MA2701"}},
  "indicators": [{
    "id": "MA-future", "product": "甲醇", "module": "price",
    "name": "甲醇主力收盘", "spec": "主连", "region": "郑商所",
    "unit": "元/吨", "tax": "不含税", "freq": "daily",
    "current": 3143, "data_date": "2026-10-19",
    "base": 3366, "base_date": "2026-10-16",
    "what": "10月19日主力收 3,143 元/吨。",
    "why": "跌破前低后基差被动走扩，需观察现货是否跟随。",
    "verify": "夜盘能否站稳 3,100。",
    "source": "东方财富行情", "source_url": "https://quote.eastmoney.com/"
  }],
  "events": [], "excluded": [], "gaps": [], "sources": [], "chain": {}
}
```
