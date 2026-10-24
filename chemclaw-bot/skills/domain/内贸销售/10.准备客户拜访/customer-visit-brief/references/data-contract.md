# 数据契约 · visit_data.json

`visit_data.json` 是唯一事实来源：研究先写它，Excel 由 `scripts/build_visit_workbook.py` 消费它生成，HTML 按它改造母版。
编码 UTF-8；数组元素除特别说明外均为字符串；缺失的可选块直接省略键。

## 顶层结构

```jsonc
{
  "meta":   { ... },        // 必填：卡片头与文件命名
  "kpis":   [ {...} ],      // 建议 3–6 条：关键数字看板
  "profile":        [ [维度, 信息, 来源] ],                    // 研究面A
  "timeline":       [ [日期, 类型, 事件, 对拜访的意义, 来源] ],  // 研究面C，≥5条
  "market":         [ [品种, 规格地区, 价格, 单位, 数据日期, 近期变化, 来源, url] ],  // 研究面D
  "market_note":    "谈判含义一段话",
  "risks_opportunities": [ [类型(风险|机会), 内容, 对我方动作的含义, 状态] ],      // 可选
  "usage":          [ [条目, 说明] ],       // 可选，缺省用内置通用版
  "questions":      { "版本名": [ {"no":1, "q":"问题", "why":"为什么问"} ] },  // 1–3个版本
  "ledger_example": { ... },               // 可选：台账格式示例行（必须带"（示例）"前缀）
  "ledger_baseline":"首访基线采集清单一句话",
  "sources":        [ [序号, 类别, 要点, 来源名称, 日期, url] ]  // 全部可核验来源
}
```

## meta 字段

| 键 | 必填 | 说明 |
|---|---|---|
| title | ✓ | 卡片大标题，如"客户拜访背景卡 · 福莱特玻璃集团（纯碱采购）" |
| customer / stock_code | ✓ / 可 | 企业全称 / 股票代码或"未上市" |
| positioning | ✓ | 一句话行业定位（光伏玻璃全球第二 · 纯碱大客户） |
| our_product | ✓ | 我方产品与规格级别 |
| visit_purpose / visit_target / duration | ✓ | 本次目标 / 拜访对象 / 建议时长 |
| date_generated / data_cutoff | ✓ | 生成日期 / 数据截至日（YYYY-MM-DD） |
| history_note | ✓ | "已上传 N 份记录（见台账）"或"未上传记录 → 第⑤节留空，不虚构客户需求" |
| generator | 可 | 署名（如 ChemClaw / WorkBuddy / 销售姓名） |

## kpis 字段

| 键 | 必填 | 说明 |
|---|---|---|
| value / unit | ✓ / 可 | 数值与单位（区间价写区间） |
| label | ✓ | 指标名 + 口径与日期（如"在产熔化量（2026-03，华泰口径）"） |
| delta | 可 | 变化说明；方向箭头由 tone 生成，不要手写箭头 |
| tone | ✓ | up（▲涨）/ down（▼跌）/ flat（→持平） |
| source | ✓ | 来源（日期）——KPI 是从 market/timeline 提炼的，出处必须保留 |

## questions 约定

- 键名即版本名（`采购版` / `技术版` / `老板版`），**每版 5–8 问**。
- `why` 对应研究面与待验证项，如"估需求量与采购节奏（对应大事记3-09冷修）"。

## ledger_example 约定（防虚构的关键）

示例行 9 个键与台账列一致：`date, channel, person, points, confirmed, unresolved, evidence, recorder, next`。
**每个值必须带"（示例）"前缀**——它是格式演示，不是客户信息。

## 合法性检查（步骤④前自查）

1. `meta` 七个必填键非空。
2. `market` 每行第 5、7 列（数据日期、来源）非空；`sources` 每行第 6 列 URL 以 http 开头且与来源名对应。
3. `timeline` 每行第 4 列（意义）非空——没有意义的事件不上卡。
4. 无上传记录时：不出现任何 `ledger_example` 以外的"客户确认"内容。
5. `questions` 每个版本 5–8 条。
