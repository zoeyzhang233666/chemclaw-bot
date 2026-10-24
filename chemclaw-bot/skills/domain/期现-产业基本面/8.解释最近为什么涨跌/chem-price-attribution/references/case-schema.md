# 字段说明：case.json 与 narrative.json

## 一、case.json —— 唯一的手工输入

```jsonc
{
  "case": {
    "title": "华东甲醇 多因素行情归因",
    "product": "甲醇",
    "market": "华东（太仓/张家港）",
    "spec": "国标优等品"
  },
  "window":  { "start": "2026-06-30", "end": "2026-10-19" },
  "history_start": "2024-06-01",          // 算历史分位与 z 值的起点
  "asof": "2026-10-19",

  "spot":    { "file": "raw/ppi_base_price.csv", "name": "生意社 甲醇基准价（华东）",
               "src_url": "..." },
  "futures": { "file": "raw/MA0_daily.json", "name": "郑商所 甲醇主连",
               "src_url": "..." },

  "futures_front": {                       // 逐合约，用于基差/月差
    "file": "raw/MA_contracts.json",       // {合约: {日期: {close, oi}}}
    "extra": { "MA2701": "raw/MA2701.json" }
  },

  "meta": {
    "baseline_contract": "MA2611",         // 基差用哪个合约（必须全窗口有成交）
    "spread_pair": ["MA2611", "MA2612"],   // 月差用哪一对（必须固定）
    "note": "口径说明…"
  },

  "events": { "file": "raw/events.json" },

  "periods": [                             // 价格阶段（人工定稿，覆盖全窗口）
    { "id": "P1", "name": "P1 2026-06-30→07-10 高位回落", "start": "2026-06-30",
      "end": "2026-07-10", "desc": "…" }
  ],

  "drivers": [                             // 十个因子，逐个写全
    {
      "id": "cost_coal", "name": "煤炭成本（上游原料）",
      "group": "cost",                     // cost|supply|trade|inventory|demand|structure|policy
      "why": "甲醇现金流成本的主要项",
      "series": [                          // 逐日/逐周序列，脚本自动算变化
        { "id": "coal_qhd5500", "name": "秦皇岛港 5500 大卡动力煤现货价",
          "file": "raw/cctd_qinhuangdao.json", "value_field": "age",
          "unit": "元/吨", "src_url": "..." }
      ],
      "manual": [                          // 只有披露值的指标
        { "k": "周度开工率", "v": "83.8%（环比 +1.1pct）", "date": "2026-09-21",
          "unit": "%", "src": "…", "grade": "E2", "dir": "up", "cite": "…" }
      ]
    }
  ],

  "future_checks": [                       // 报告里"必须检查"的期现项
    "基差、月差的逐日序列", "持仓量迁移", "主连换月日的名义价"
  ]
}
```

### 字段纪律

- `series[].file` 与 `case` 同目录的相对路径；CSV 需 `date_field`/`value_field`。
- `manual[].grade` 只能填 `E1–E4`，填 E1 必须同时给 `date` 与 `src`。
- `manual[].dir` 是该指标的**自身方向**（`up`/`down`），不是"对价格的影响方向"。
- `periods` 若省略，脚本用异动识别的阶段结果。
- 口径类说明一律进 `meta.note`，**不进 `events`**（会污染证据分级）。

## 二、narrative.json —— 人写的部分

脚本算数，人写判断。结构：

```jsonc
{
  "title": "…", "subtitle": "…（含三条涨幅口径）",
  "one_liner": "一句话结论：…",
  "rehab": { "body": ["第 1 段…", "第 2 段…"] },     // 涨跌幅复核
  "periods": [ { "id": "P1", "price": "…", "read": "…",
                 "candidates": [{"factor":"…","level":"E1","note":"…"}] } ],
  "hypotheses": [                                    // 按证据强弱排序
    { "rank": 1, "claim": "…", "level": "E2",
      "supported_by": ["…"], "not_proven": ["…"] }
  ],
  "unexplained": [ { "item": "…", "note": "…" } ],
  "data_gaps":    [ { "item": "…", "impact": "…" } ],
  "limitations":  [ "…" ]
}
```

### 写作纪律

- `hypotheses` 必须先列**证据最强的**，即使它不是最"合理"的那个；
- 每条假设都要有 `not_proven`，写清它**为什么还没被证明**；
- 被证伪的假设（如"装置检修驱动上涨"）**保留在列表里**，标 E4 说明方向相反；
- `unexplained` 不得为空——总有价格动而数据没动的地方；
- 全文不出现预测性动词。

## 三、事件 JSON

```jsonc
[ { "id": "E01", "date": "2026-08-24", "title": "…",
    "group": "trade",                 // 与驱动 group 对应
    "evidence": "E2",                 // 该事件本身的可靠度
    "direction": "bullish", "magnitude": "…",
    "src": "生意社", "url": "https://…" } ]
```

`url` 必填。没有可引链接的"事件"不允许进清单。
