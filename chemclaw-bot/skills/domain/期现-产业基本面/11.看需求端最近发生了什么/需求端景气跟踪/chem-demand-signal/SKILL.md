---
name: chem-demand-signal
description: Use when someone needs to know what actually happened to the DEMAND side of a chemical within a recent window — 看需求端最近发生了什么 / 下游需求变化 / 主要下游行业最近3个月用了多少 / 需求好不好 / 哪个下游在拖累 / 是真实需求还是价格假象 / downstream demand analysis / who buys this product and is it growing. Works for any chemical (纯碱、烧碱、尿素、甲醇、玻璃、PVC、PTA、碳酸锂、钛白粉…). Produces a self-contained interactive HTML demand dashboard, a multi-sheet Excel workbook, and a structured research JSON; every number carries a data date + caliber + source, proxies are graded A/B/C/D so price moves are never mistaken for consumption growth, and downstreams are compared one by one instead of averaged.
---

# 期现产业基本面 · 看需求端最近发生了什么

## 这个 Skill 解决什么问题

用户想知道的是**需求端最近到底发生了什么**，而不是价格怎么走。这类问题最容易出三种错：

1. **把价格当需求**——玻璃涨价了就说纯碱消费在增长，完全忽略同期产量、表观消费在下降。
2. **把所有下游简单平均**——浮法玻璃有周度日熔量，轻碱下游只有定性描述，直接把两者的"好坏"平均成一个数，结论没有信息量。
3. **占比不标年份**——同一家机构不同年份的占比被混用，甚至把 2024 年的结构套到 2026 年的需求判断上。

本 Skill 用一套固定流程把这些坑都堵上：**先定消费路径 → 再按下游逐一采数 → 给每个指标打 A/B/C/D 等级 → 分下游比较（不做跨下游平均）→ 按消费占比加权做传导分析 → 缺口如实披露**。

## 何时触发

用户说到或暗示以下任意一种：

- "看需求端最近发生了什么" / "下游需求变化" / "最近 3 个月需求怎么样"
- "这个品种主要卖给谁" / "哪些下游在拖累" / "需求是真实变好还是价格假象"
- "帮我研究一下 XX 的下游" / "下游开工、产量、库存怎么样"
- 写品种周报、月度策略、投资备忘录，需要需求端章节

**不适用**：只问价格行情（用 `chem-market-brief`）、只问采购议价（用 `chem-procure-brief`）、只找客户名单（用 `b2b-lead-sourcing`）。

## 交付物（三件套 + 模板）

| 交付物 | 文件 | 作用 |
|---|---|---|
| 交互式 HTML 报告 | `examples/<品种>-demand-3m/report.html` | 首屏需求结构 + 主要变化、下游卡片、筛选、下钻、证据库；单文件离线 |
| Excel 工作簿 | `examples/<品种>-demand-3m/workbook.xlsx` | 14 张表：结构/指标库/分级/历史/打分/传导/政策/价格库存/期货/缺口/来源/证据/口径 |
| 研究数据层 | `examples/<品种>-demand-3m/research.json` | 证据库 + 派生计算 + 叙事，可复跑、可审计 |
| 模板 | `templates/demand-research-template.json` | 换品种时填的骨架 |
| 生成脚本 | `scripts/build_research.py` 等 | 从 JSON 一键产出 HTML / Excel |

## 执行流程（8 步，不要跳步）

### Step 1 · 锁定研究口径（5 分钟，必须写下来）

先确认四件事，写进 `research.json` 的 `meta`：

- **品种与规格**：是哪个牌号/规格会影响下游口径（纯碱要分重碱/轻碱，烧碱分 32%/50%，PTA 分纤维级/瓶级）。
- **研究区间**：`30d` / `3m` / `1y`，并写明**起止日期**与**数据截止日**。
- **区域**：全国还是某区域（区域价差、区域产能结构不同）。
- **期货基准**：主力连续合约代码（如纯碱 SA0、玻璃 FG0），用于对照而非需求。

> 铁律：区间内的每个比较都要和**同一基线日期**对齐；禁止把 7 月中的一个点和 10 月的另一个点拼成一个"变化"。

### Step 2 · 识别下游消费路径（先结构，后数据）

产出两样东西：

1. **直接下游产品**（谁把它变成别的产品）：纯碱 → 浮法玻璃、光伏压延玻璃、日用玻璃、硅酸钠、碳酸锂。
2. **终端应用与消费行业**（谁最终买单）：浮法 → 建筑门窗/幕墙/汽车 → 房地产竣工；光伏玻璃 → 组件 → 光伏电站装机。

**至少并列 2–3 套占比口径**，每套都标：统计年份、来源机构、分母定义（内需 / 表观含出口 / 全部应用含损耗）。
详见 [`references/demand-structure-playbook.md`](references/demand-structure-playbook.md)。

```json
{"structure":[{"org":"卓创/协会（研报引用）","year":2024,"basis":"表观消费3596万吨",
  "items":[["平板玻璃",46,1639],["光伏玻璃",21,752],["日用玻璃",12,431],["其他",21,774]]}]}
```

> 占比是**权重**，不是结论。三套口径必须在报告里同时出现，并给出"换权重后结论是否改变"的敏感性表。

### Step 3 · 按下游逐一采集指标（核心工作量）

对每个下游，按**六个维度**找数：价格、开工率、产量、库存、利润、订单/消费。

每个数字都必须是这个结构（字段即 Excel 与 HTML 的通用契约）：

```json
{"id":"F23","seg":"float","kpi":"日熔量","metric":"浮法玻璃日熔量","value":14.23,"unit":"万吨/日",
 "date":"2026-10-13","period":"2026-10-13","caliber":"钢联/卓创口径，全国在产日熔量","yoy":-11.8,
 "src":"zjtk1014","url":"https://...","quote":"截至10月13日，浮法玻璃日熔量维持在14.23万吨/日…","grade":"A"}
```

- `value` 拿不到就填 `null` 并在 `gaps` 里登记，**不要估算、不要插值**。
- `caliber` 必须能回答："谁统计的、统计范围、是否含税、是日/周/月"。
- `quote` 必须是从原文摘出的原句，方便复核。
- ID 前缀约定：`F` 浮法、`P` 光伏、`L` 轻碱/锂电、`Q` 定性、`R` 房地产、`S` 装机、`C` 政策。

数据源优先级与抓取方法见 [`references/data-sources.md`](references/data-sources.md)。

### Step 4 · 给每个指标打等级（决定报告能不能用）

见 [`references/proxy-grading.md`](references/proxy-grading.md)。速查：

| 等级 | 含义 | 能否用于"消费增长"判断 | 例 |
|---|---|---|---|
| **A** | 真实需求：直接等于下游产量/消耗，或按固定物耗系数换算 | 可以（注明系数） | 浮法/光伏日熔量、深加工订单天数、表观消费 |
| **A-** | 真实需求代理但有结构偏差 | 可以，需交叉验证 | 开工率（受产线大小影响） |
| **B** | 间接：库存、表观、利润等由供需差推导 | 不可单独使用 | 企业库存、原料库存天数、利润 |
| **C** | 景气/情绪：价格、期货、基差 | 不可使用 | 玻璃现货价、30 城成交 |
| **D** | 定性：机构调研描述 | 仅作辅助 | "加工厂开工率同比大幅下降" |

**价格永远不进需求打分。** 这是本 Skill 最重要的一条。

### Step 5 · 分下游比较（禁止平均）

对每个下游：

1. 用**同口径相邻两期**算变化（`build_derived.py` 里的 `series_stats`），跨口径只做方向判断并标红。
2. 引用机构给出的同比/环比（这些是原文数据，比自算更权威）。
3. 给该下游内部各指标打分（-2…+2，按重要性加权）得到**分项景气指数**。

然后用**消费占比**加权得到传导指数：

```
传导指数 = Σ(分项景气指数 × 该下游消费占比)
```

并对权重做敏感性（换用第二、第三套口径再算一遍）。详见 [`references/transmission-playbook.md`](references/transmission-playbook.md)。

> 注意措辞：传导指数是"景气度向需求传导的方向与强度"，**不是消费量增速**，也不能反推吨数。

### Step 6 · 写传导分析（终端 → 采购）

每一跳都要写清：机制、滞后、强度、可用证据。特别要把"价格 → 需求"这一跳标为**弱相关**，并给出本区间的反例（如有）。

纯碱案例里的反例：光伏玻璃 2.0mm 价格 3 个月 +24%，同期光伏玻璃表观消费 −13%——价格由减产推动，消费仍在下降。

### Step 7 · 政策、季节性、事件

只收录能核到**原始公告或权威报道**的事件，每条写：生效日期、内容、对需求的方向、可核验性说明、链接。
季节性要说明今年是否兑现（"旺季不旺"本身就是结论）。

### Step 8 · 生成三件套并自检

```bash
python scripts/build_research.py  examples/<品种>-demand-3m/research.json
python scripts/render_html.py     examples/<品种>-demand-3m/research.json out/report.html
python scripts/render_xlsx.py     examples/<品种>-demand-3m/research.json out/workbook.xlsx
python scripts/check_all.py       out/report.html out/workbook.xlsx
```

自检必须全绿才能交付：无重复 id、无外链、无占位符、无 `undefined`、证据条数与证据库一致、HTML 与 Excel 数值同源、四个断点无横向溢出、抽屉/筛选可交互。

## 报告必须有的"反误用"段落

HTML 与 Excel 里都要显式写出（用户会拿这五行去质辩）：

1. 玻璃价格上涨 ≠ 纯碱消费增长（给本区间反例）。
2. 不对下游简单平均（说明为什么）。
3. 不同机构口径不可相减（列出本报告涉及的口径差异）。
4. 占比必须带年份与来源，禁止跨口径相加。
5. 只陈述已发生事实，不预测价格。

## 常见失败模式

| 症状 | 根因 | 修法 |
|---|---|---|
| 结论"需求整体偏弱"但说不清哪个下游拖累 | 做了跨下游平均 | 拆到分项指数，各给权重与依据 |
| 数字对不上 | 把"在产/有效/实际运行"三种日熔量口径相减 | 标红，只做方向判断 |
| 被追问"你怎么知道消费降了" | 只用了价格/利润 | 补 A 级指标：日熔量、表观消费、订单天数 |
| 交付后发现有 `undefined` | JS 模板里对 null 直接取属性 | `check_all.py` 会拦住 |
| 用户不信数据 | 没有原文摘录与链接 | 每条证据带 `quote` + `url` |

## 本 Skill 自带案例

`examples/soda-ash-demand-3m/` 是纯碱（2026-07-15 → 2026-10-19）的完整实例：
137 条证据、3 套占比口径、18 个代理指标分级、21 项打分、6 条传导链、6 条政策事件、6 条缺口。
直接读它比读文档快：[`examples/soda-ash-demand-3m/README.md`](examples/soda-ash-demand-3m/README.md)。

## 文件索引

```
chem-demand-signal/
├── SKILL.md                          ← 你在读
├── references/
│   ├── demand-structure-playbook.md  消费路径识别与多口径占比
│   ├── proxy-grading.md              A/B/C/D 代理指标分级规范
│   ├── transmission-playbook.md      传导分析与加权（反简单平均）
│   ├── indicator-caliber-spec.md     需求指标口径规范（单位/频率/误用）
│   ├── data-sources.md               数据源优先级与抓取方法
│   └── qa-checklist.md               交付前检查清单
├── scripts/
│   ├── build_research.py             校验并规范化 research.json
│   ├── render_html.py                → 单文件离线 HTML 看板
│   ├── render_xlsx.py                → 14 表 Excel 工作簿
│   └── check_all.py                  HTML/Excel 双端自检
├── templates/
│   ├── demand-research-template.json 研究数据层骨架
│   └── asset-library.js              SVG 图表库（折线/环形/柱状/迷你图）
└── examples/
    └── soda-ash-demand-3m/           纯碱完整案例（report.html / workbook.xlsx / research.json / README.md）
```

## 复用约定

- 换品种只需要换 `research.json`，脚本不改。
- `scripts/` 只依赖 Python 3 标准库 + `openpyxl`；HTML 不依赖 CDN、不依赖 ECharts（SVG 手绘），可离线打开、可邮件发送。
- 所有文案、占比、打分都能在 JSON 里找到出处，改数字只改 JSON。
