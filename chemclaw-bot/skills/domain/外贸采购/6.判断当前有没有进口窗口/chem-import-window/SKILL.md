---
name: import-window-check
description: 判断某个化工品从海外进口到中国、当前有没有进口窗口（进口价差）—— 把海外 FOB/CFR/CIF 报价按真实贸易术语折算成中国到岸含税成本，与国内同规格、同交货地、同税基的现货价对齐后算价差，并给出历史价差序列、敏感性、归因，同时区分"理论价差"与"可执行贸易利润"。Use when the user asks 判断当前有没有进口窗口 / 进口合不合算 / 进口成本折算 / 海外报价换算人民币 / 美金价与国内现货价差 / 内外盘价差 / 进口盈亏 / CFR 还是 FOB 划算 / 关税与增值税怎么算进成本 / 进口窗口打开了没有, for any chemical product (乙二醇 MEG、甲醇、苯乙烯、丙烯腈、PX、双酚A、纯碱、尿素、钛白粉、塑料粒子、精细化工中间体…), any overseas market (中东、东北亚、东南亚、北美、欧洲) and any Chinese region (华东、华南、华北、山东…). Delivers a self-contained interactive HTML dashboard plus a live-formula Excel workbook in which every number carries incoterm + currency + freight + FX date + duty/VAT basis + source, and every missing input is marked as a data gap instead of being estimated.
---

# 进口窗口判断（进口价差 / Import Window）

## 这个 Skill 解决什么

外贸采购最常被问的一句话是"现在从海外进口合不合算"。要回答它，必须把**两套完全不同的价格语言**对齐：

| | 海外报价 | 国内现货 |
|---|---|---|
| 币种 | USD | CNY |
| 贸易术语 | FOB 装运港 / CFR 中国主港 / CIF | 出厂自提 / 罐区库提 / 送到 |
| 税 | 不含中国关税与进口环节增值税 | 含 13% 增值税 |
| 交货地点 | 到岸（不含内陆） | 已在国内（可能含配送） |
| 货物状态 | 船货，装期 T+15~30 天 | 罐内现货，款到即提 |

**直接把 685 美元/吨乘汇率去减 5,865 元/吨，得到的数是错的**。本 Skill 就是把这条链路做对：

```
海外报价(FOB/CFR/CIF, USD)
   → [若 FOB] + 国际运费 + 保险费        = CIF(USD)
   → × 当日汇率                          = 关税完税价格(CNY)
   → + 关税(完税价 × 关税税率)            = 含关税价
   → + 进口环节增值税((完税价+关税) × 13%) = 含增值税价
   → − 可抵扣增值税（一般纳税人）          ⟵ 关键：不能拿含税对比不含税
   → + 港杂/报关/仓储/短驳               = 进口含税净成本
   ══════════════════════════════════
     进口含税净成本  ⟷  国内含税现货价   → 理论进口价差
```

## 什么时候用 / 不用

**用**：判断进口窗口、算进口成本、内外盘价差、进口盈亏、论证"进口货是否比国产便宜"。
**不用**：纯国内区域价差（用 `region-price-spread`）、纯行情简报（用 `chem-market-brief`）、出口报价（用 `算出口报价`）。

## 三条不能破的红线

1. **不得把含税与不含税直接相减。** 国内现货价含 13% 增值税。若进口增值税可抵扣（一般纳税人），必须从进口成本中剔除，再与国内含税价比较；若不可抵扣，才把增值税计入成本 —— 并且国内端的进项抵扣也要同步核实。
2. **不得在没有真实运价时把运费填成 0 或"估计值"。** 中东→华东化学品船运费典型 40–90 美元/吨（约 270–600 元/吨），凭空填 0 会把结论整体扭曲 300–600 元/吨。拿不到就登记为**缺口**，并在页面上明示"FOB 报价当前不可折算"。
3. **不得用当前参数倒推历史。** 历史价差必须逐点使用**当日**的海外报价、**当日**汇率、**当期**生效的税率。缺任一者，该日留空并写明原因；不做插值，不用最新汇率套历史价。

同时：**不预测价格、不给交易指令。** 输出的是"同一口径下的折算与比较"，不是"建议买入"。

## 工作流（8 步，对应页面 01–08 区块）

| 步 | 动作 | 产出 | 常见错误 |
|---|---|---|---|
| 1 | 抓海外报价：FOB/CFR/CIF、规格、港口、日期、来源、批量 | `quote{}` | 把"FOB 韩国"直接当到岸价 |
| 2 | 抓国内现货：价格、含税与否、交货方式、规格、区域、来源 | `domestic{}` | 用全国均价冒充华东单点 |
| 3 | 取**当日**汇率（USD/CNY）+ 运费 + 保险 | `fx{}` `freight{}` | 拿今天的汇率算上周的价格 |
| 4 | 取该商品当日关税税率、增值税率、能否抵扣 | `tax.profiles[]` | 凭记忆写 5.5%，不做验证 |
| 5 | 逐项折算，得出进口含税净成本与理论价差 | 引擎输出 | 漏掉港杂与内陆段 |
| 6 | 做可比性核对（9 项检查） | `compatibility` | 只看数字不看口径 |
| 7 | 历史序列 + 敏感性 + 归因 + 异常阶段 | `history` `sensitivity` | 插值连线伪造趋势 |
| 8 | 明确区分理论价差与可执行利润；登记全部缺口 | `gaps[]` | 把理论价差当利润汇报 |

## 快速开始

```bash
# 1) 写一份 case.json（照 examples/01-meg-huadong/data/case.json 的结构，按 schema 校验）
# 2) 校验数据契约
node scripts/validate.js examples/01-meg-huadong/data/case.json

# 3) 生成单文件离线 HTML
node scripts/build_html.cjs <case.json> <out.html>

# 4) 生成活公式 Excel（并把引擎结果写入「9-引擎校验」页）
node scripts/engine_cli.js <case.json> > engine.json
python scripts/build_xlsx.py <case.json> <out.xlsx> --engine-json engine.json

# 5) 三路交叉校验 + 渲染/版面检查
node scripts/cross_check.js <case.json>          # Python 基准 vs JS 引擎
python scripts/check_xlsx.py <out.xlsx> --case <case.json>   # Excel 重算 vs 引擎
python scripts/qa_render.py <out.html> --case <case.json>    # 页面数字 vs 引擎 + 交互
python scripts/qa_layout.py <out.html>           # 区块/溢出/响应式

# 6) 一键全量自检
python scripts/selftest.py                       # 跑全部示例 + 全部检查
```

## 输出形态

**A. 单文件交互 HTML**（~1.1 MB，内联 ECharts，零外部请求，双击即开）
- 首屏四卡：① 海外报价 ② 折算进口成本 ③ 国内现货 ④ 理论价差
- 下拉：商品 / 海外市场 / 国内区域 / 历史区间（全部可得 · 30 天 · 3 个月 · 1 年）
- 08 个分析区块：口径核对 → 折算明细 → 参数实时重算 → 敏感性 → 历史与价差 → 事件与异常 → 理论 vs 真实 → 缺口与来源
- 参数区可改汇率、运费、关税、增值税、境内费用、国内价，改完 ①–④ 与所有图表立即重算
- 缺口随时可见：拿不到的项显示"缺"而不是 0

**B. Excel 工作簿**（10 个工作表，全部活公式）
`0-说明 / 1-参数 / 2-进口成本折算 / 3-可比性核对 / 4-历史价差 / 5-敏感性 / 6-理论vs真实 / 7-来源清单 / 8-缺口登记 / 9-引擎校验`
- 黄色 = 输入，蓝灰 = 公式；改「1-参数」任一格，全表重算
- 「9-引擎校验」把独立引擎的结果并列，出现"复核"即说明公式口径漂移

## 数据契约（细节见 `schema/data.schema.json`）

一份 case 的关键字段：

```jsonc
{
  "meta":   { "case_id", "title", "generated_at", "disclaimer" },
  "product":{ "name_cn", "spec", "hs_code_cn", "cas" },
  "quote":  { "date", "price_usd", "term", "premium_usd", "spec", "port", "source_id" },
  "domestic":{ "date", "price_cny", "tax_included", "delivery", "spec", "region", "source_id" },
  "fx":     { "date", "rate", "source_id", "rows":[{"date","rate"}] },   // rows 用于历史回算
  "freight":{ "source": "none|quote|series|simulated", "usd_per_ton", "date", "quality" },
  "tax":    { "profiles":[{ "effective_from", "duty_rate", "vat_rate", "provisional" }] },
  "params": { "vat_recoverable", "inland_cost_cny" },
  "quotes_hist":[...], "domestic_hist":{"rows":[...]},
  "sources":[{ "id","publisher","title","date","url","excerpt","tier" }],
  "gaps":   [{ "id","severity","item","impact","fix" }]
}
```

## 参考资料

| 文件 | 内容 |
|---|---|
| `references/comparability.md` | 内外盘可比性 9 项检查清单 + 每项的判定标准与纠正办法 |
| `references/cost-formulas.md` | 折算公式全集（含 CIF/CFR/FOB 三种入手路径、保险与完税价调整） |
| `references/incoterms.md` | 贸易术语到"到岸成本"的转换矩阵，以及常见误用 |
| `references/tax-and-vat.md` | 关税/暂定税率/协定税率、进口环节增值税、抵扣与不可抵扣口径 |
| `references/history-alignment.md` | 历史序列对齐规则：同日配对、缺日留空、税率版本、不插值 |
| `references/sensitivity-and-attribution.md` | 敏感性设计、盈亏平衡、变化归因的正确做法 |
| `references/no-forecast-policy.md` | 不预测、不指令的表述边界（含可用/禁用措辞表） |
| `references/qa-checklist.md` | 交付前自检清单（数字级、口径级、表述级） |
| `references/data-sources-cn.md` | 国内可核验数据源检索路径与坑（会员墙、反爬、口径陷阱） |

## 示例

| 目录 | 说明 |
|---|---|
| `examples/01-meg-huadong/` | **完整示例**：中国华东进口乙二醇（MEG），2026-10 真实数据，含事实表、缺口登记、HTML、Excel、校验输出 |
| `examples/00-template/` | 最小可用模板（换成你的品种/市场/地区即可跑） |

## 常见坑（血泪版）

1. **把 CFR 当 CIF 用**：CFR 不含保险。货值高时保险虽小（5–15 元/吨），但口径不严会被审单打回。
2. **把全国均价当华东价**：隆众"全国主流市场均价"与张家港实际成交可差 100–200 元/吨。
3. **用今天的汇率算上周的价**：汇率 ±3% 会让价差动 ±150~300 元/吨，与很多"窗口"同量级。
4. **忽略增值税抵扣**：含税减含税看着对，实际多算了 13% 的增值税（628 元/吨），结论直接反转。
5. **虚构历史曲线**：只有 5 个锚点却画出 30 天曲线，是最容易被一眼看穿、也最伤信誉的事。
6. **把理论价差报成利润**：理论价差 1,033 元/吨，扣掉资金成本、损耗、罐容与对手方风险后可能只剩一半。

## 版本

- v1.0.0 · 计算引擎 `scripts/lib/import-window-engine.js` 为 HTML/Excel/校验脚本共用的**单一计算真源**，任何口径修改必须改引擎并重跑 `selftest.py`。
