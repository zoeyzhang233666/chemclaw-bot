---
name: chem-product-quicklook
description: >-
  快速看懂一个化工品种：为一个具体化工品（甲醇、纯碱、烧碱、尿素、PVC、PTA、乙二醇、玻璃、碳酸锂、
  丙烯酸、钛白粉、苯乙烯、双氧水…）建立"品种研究入口"，输出可交互 HTML 研究页 + 12 表 Excel 工作簿。
  回答 8 个问题：是什么（名称/别名/CAS/牌号/计价单位）、怎么做（工艺路线与核心原料）、用在哪（下游与终端）、
  谁在生产（企业与产能/区域分布）、怎么流动（贸易与区域市场）、有没有期货（交易所/代码/合约/交割/期现关系）、
  盯什么指标（供需库存价格成本基差）、产业链逻辑如何串起来。触发词：快速看懂一个品种 / 品种研究入口 /
  品种入门 / 品种画像 / 产业链梳理 / 一个新品种怎么研究 / 建品种档案 / product onboarding /
  这个品种的产业链 / 产能分布在哪些企业。
  适用于任何化工品；无期货合约的品种会自动降级（跳过期货模块并标注缺口）。
  不用于行情日报（用 chem-market-brief）、不用于找客户（用 b2b-lead-sourcing）。
---

# 快速看懂一个品种（chem-product-quicklook）

## 这个技能解决什么

研究员接到一个陌生品种（或新同事入职、或跨品种比较），需要在一两个小时内建立
**可复核的认知框架**，而不是拿到一篇"行业综述"。本技能交付两件东西：

1. **交互式 HTML 研究入口页** —— 首屏即核心信息卡 + 产业链骨架 + 研究指标框架；
   产业链节点可点击展开，查看该节点的价格、企业、公共产能、在建项目；
   下方面板展开工艺 / 企业产能 / 下游 / 区域 / 期现 / 关键变量。
2. **12 表 Excel 工作簿** —— 产品百科、牌号规格、工艺路线、产业链节点、企业产能、
   下游需求、贸易区域、期货交割、关键指标、来源清单、缺口与核验。

**最重要的原则：页面里每一个数字都必须能回答"谁在什么时候说的"。
拿不到的数据标"缺口"，绝不用行业均值、估算值或"业内普遍认为"填充。**

## 何时使用 / 不使用

| 用 | 不用（改用别的技能） |
|---|---|
| 第一次接触某品种，要建立认知框架 | 只要当前行情与价格（→ chem-market-brief） |
| 要梳理某品种的产业链与产能格局 | 要找下游客户名单（→ b2b-lead-sourcing） |
| 要一个可交付给团队的品种档案 | 要看某个区域的市场地图（→ chemical-region-market-map） |
| 要做品种间横向对比的标准化底稿 | 采购决策前的价格研判（→ chem-procure-brief） |

## 工作流程（必须按序执行）

### 第 1 步：确认靶标与范围
- 锁定**唯一品种**：中文名 + 英文名 + CAS。CAS 不确认就不要往下做（同名异物是化工资讯最常见的坑）。
- 问清（或自行判定）三件事：**是否有期货合约**、**主要研究目的**（期货研究/现货贸易/采购/销售）、
  **是否需要区域细分**。这三项决定后续模块是否降级。
- 如果品种有多个计价形态（如烧碱的 32%/50% 液碱与固碱、纯碱的轻质/重质），
  必须在 `product.grades` 里分别列，不要只写一个。

### 第 2 步：按 8 问收集事实（每问都要落来源）
读取 `references/question-framework.md`，按 8 个问题逐项收集。
**收集规则：**
- 每个关键数字配 `来源 + 日期 + 口径`。同一指标出现多个数值时，**全部保留并列示冲突**，
  不要擅自选一个（见第 7 步）。
- 一手优先：交易所公告 > 国标/法规 > 协会年报 > 上市公司公告 > 期货公司/数据商研报 > 媒体转载。
- 媒体转载必须回溯原始机构（例："中国氮肥工业协会顾宗勤在××大会的报告"而非"某财经网报道"）。

数据抓取用 `scripts/fetch_source.py`（无头浏览器，带 UA 与 locale，能把正文抽出来并落盘备查）：

```bash
python scripts/fetch_source.py --list urls.txt --out raw/          # 批量抓
python scripts/fetch_source.py --url <URL> --name 某来源 --grep 产能  # 抓单页并检索关键词
```

### 第 3 步：写 research.json（唯一数据源）
所有内容写进一个 `research.json`，模板见 `assets/research.template.json`，
字段规范见 `references/data-contract.md`。要点：
- `chain.nodes` 是产业链图的唯一真相，5 列（上游/工艺/本品种/下游/终端）可按品种调整。
- 每个节点都要有 `research.actions`，映射到 `scenes`，这样 HTML 里点"深入"能生成研究任务给其他技能。
- 期货品种填 `has_futures: true` 并在 `research.futures` 写合约要素；
  无期货则 `false` 且**必须**给出 `gapnote` 说明，不允许留空。

### 第 4 步：价格锚点必须算，不能写"约 XXX"
这是本技能与"AI 生成行业报告"的分水岭。**禁止手写价格。**
用 `scripts/fetch_futures_series.py` 拉日线、`scripts/build_anchors.py` 算分位与区间：

```bash
python scripts/fetch_futures_series.py --symbol MA0 --out raw/MA0.json
python scripts/build_anchors.py raw/MA0.json --name "郑商所甲醇主连" --symbol MA0 \
    --spec "主连拼接价，不含税" --region 郑商所 --tax 不含税 --src S22 --out raw/anchors.json
```
把产出的 anchors 合并进 research.json（见 `examples/methanol/merge_anchors.py`）。
现货价同样处理：拿到逐日序列才算数，**没有序列就在 `price_gap` 里写缺口**。

### 第 5 步：校验
```bash
python scripts/validate.py research.json      # 结构与事实纪律检查，必须 0 error
```
`validate.py` 会拦住：空字段、来源 id 悬空、期货要素缺失、方向性措辞（看涨/看跌/抄底）、
"约/左右"等模糊数字无来源、面板缺必备模块。

### 第 6 步：出 HTML 与 Excel
```bash
python scripts/build_html.py research.json --out out/
python scripts/build_xlsx.py research.json --out out/
```

### 第 7 步：渲染 QA（不可跳过）
```bash
python scripts/qa_render.py "out/甲醇-品种研究入口.html" --shots out/shots
python scripts/check_xlsx.py "out/甲醇-品种研究入口.xlsx" --research research.json
```
`qa_render.py` 用无头浏览器真实点击：展开/收起、节点抽屉 5 个页签、面板切换、
工艺卡展开、指标折叠、三种宽度下的横向溢出。**必须 0 失败**才能交付。

### 第 8 步：交付并列出缺口
在回复里明确写出：① 交付物路径；② 关键数字的来源与日期；③ **缺口清单**（哪些数据没拿到、为什么、
建议怎么补）。不要隐藏缺口——缺口清单本身就是研究成果。

## 口径冲突：本技能的核心竞争力

同一个品种在不同来源里数字不同是常态，处理方式决定了报告的专业度：

| 情形 | 正确处理 | 错误做法 |
|---|---|---|
| 全国产能两个数（如 1.15 亿吨 vs 1.08 亿吨） | 两列并列，标注机构、时点、是否剔除长期停车装置 | 取平均或只留一个 |
| 集团产能 vs 单厂产能 vs 存量产能 | 三种口径分别列，注明"不可混用" | 混着用来算集中度 |
| 下游占比年份不同（2024 vs 2025） | 分年分机构列，明确"禁止相加" | 直接把两年数据拼成一张饼图 |
| 单耗因技术代际不同（MTO 2.66/2.87/3.0） | 列区间 + 说明技术代际 | 用一个数做利润测算还不声明 |

详见 `references/caliber-and-conflict.md`。

## 四种信息必须分开标注

页面与 Excel 里主动区分，读者才不会误用：

1. **产业链事实**（谁在哪有装置、下游是谁）→ 标来源
2. **典型工艺参数**（吨耗、温度压力、碳排强度）→ 标 `SB 工艺典型值`，说明不代表某企业实测
3. **公开统计**（产能、产量、进口量、开工率）→ 标机构 + 时点
4. **研究判断**（"煤价占可变成本 70% 以上"）→ 显式写"研究判断"

`validate.py` 会对第 2/4 类做提醒，交付前逐条自查。

## 无期货品种的降级处理

若品种没有国内期货合约（如很多精细化工品）：
- `product.has_futures = false`
- `research.futures` 不填数组，仅保留一个 `gapnote` 说明"无期货合约，期现关系不适用"
- 面板 `trade_futures` 改为"贸易与区域市场"，去掉交割与基差内容，补区域价差与运费
- 研究框架里把"期现"维度换成"贸易流/区域价差"
- 价格锚点改用现货报价序列（若只有点位则只写点位 + 日期 + 来源，并标"单点，非序列"）

参见 `examples/no-futures-example/`。

## 不要硬编码本品种知识

本技能的所有模板（`scripts/templates/`）**不含任何品种事实**，只含结构与样式。
甲醇的知识全部在 `examples/methanol/` 的数据里。新增品种时：
1. 复制 `assets/research.template.json`
2. 按 `references/question-framework.md` 逐项填写
3. 不要改 `templates/` 下的文件（除非是修 bug 并同步更新 QA）

`references/` 里的工艺路线库、指标库是**方法参考**，不是可直接复制的答案：
路线名称可以借鉴，参数必须重新核来源。

## 文件结构

```
chem-product-quicklook/
├── SKILL.md
├── README.md
├── references/
│   ├── question-framework.md      8 问的展开方法与每问的坑
│   ├── data-contract.md           research.json 全字段规范
│   ├── chain-graph-method.md      产业链图怎么建、列怎么分、节点取舍
│   ├── caliber-and-conflict.md    口径冲突处理手册
│   ├── route-library.md           常见工艺路线模板（方法参考）
│   ├── indicator-library.md       指标库与"为什么看"
│   ├── capacity-survey.md         企业与产能调查方法
│   ├── futures-rules.md           期货合约与交割要素采集清单
│   └── qa-checklist.md            交付前自检清单
├── assets/
│   ├── research.template.json     空白数据模板
│   └── research.schema.json       JSON Schema
├── examples/
│   ├── methanol/                  甲醇完整案例（含数据、来源、构建脚本）
│   └── no-futures-example/        无期货品种降级示例
└── scripts/
    ├── build_html.py              数据 → 单文件 HTML
    ├── build_xlsx.py              数据 → 12 表 Excel
    ├── validate.py                结构 + 事实纪律校验
    ├── qa_render.py               无头浏览器交互 QA
    ├── check_xlsx.py              Excel 结构与一致性自检
    ├── build_anchors.py           日线 → 价格锚点（分位/区间）
    ├── fetch_futures_series.py    拉期货日线
    ├── fetch_source.py            抓网页正文并落盘
    └── templates/                 shell.html / styles.css / engine.js
```

## 依赖

- Python 3.9+：`openpyxl`（Excel）、`playwright`（渲染 QA，需 `playwright install chromium`）
- 可选：`requests`（fetch_source 的简易模式）
- 无 Node 依赖；HTML 为单文件，ECharts 内联，离线可打开

## 常见失败模式

| 症状 | 原因 | 处理 |
|---|---|---|
| `validate.py` 报 directional | 写了"看涨/看跌/抄底" | 品种入口页不做方向判断，改成中性描述 |
| 页面节点数与数据不符 | research.json 里 node id 重复 | 检查 id 唯一性 |
| 抽屉"企业"页签为空 | 节点没填 `research.companies` 且没给 `companies_gap` | 至少给缺口说明 |
| QA 报横向溢出 | 表格列太多或长文本未换行 | 拆表或加 `table-layout:fixed` |
| 期货要素 validate 失败 | `has_futures:true` 但缺"交易所/合约/交易单位/交割" | 补齐或改 false + gapnote |
