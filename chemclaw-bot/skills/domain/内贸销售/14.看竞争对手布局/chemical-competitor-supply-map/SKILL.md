---
name: chemical-competitor-supply-map
description: Build a product-agnostic competitive supply map for a chemical or material in a target Chinese region, preserving a proven research logic and output structure. Use when a domestic chemical sales rep needs to know who produces a product, where plants are, how far they are from a target city, where supply is dense or blank, what new capacity is coming, and which local customers to approach first. Triggers include 竞争供给地图, 竞争格局, 供给地图, 区域空白, 目标区域供给, 化工品竞争分析, 纯碱/烧碱/甲醇/钛白粉/塑料/新材料等任意化工品的区域销售布局, competitive supply map, plant map, capacity landscape. Delivers a self-contained interactive HTML plus a 9-sheet Excel workbook, generated from one data.json; includes a real soda-ash example and a synthetic schema example.
license: MIT
compatibility: Python 3.10+ with openpyxl; Node.js only for optional JS syntax/UI checks. No network at build time — ECharts, China GeoJSON and all data are inlined.
metadata:
  version: 1.0.0
  author: chemical-sales-research
  output: [html, xlsx, json]
  languages: [zh-CN]
  category: chemical-sales-research
---

# 化工品竞争供给地图 · Chemical Competitor Supply Map

## 这个 skill 解决什么问题

一个内贸销售要进入某个区域，首先要知道四件事：

1. **谁在供**：这个产品有哪些在产企业、工厂在哪、产能多大、什么工艺；
2. **离客户多远**：目标城市周边哪些省/工厂能覆盖，哪些距离带是空白；
3. **未来会不会更卷**：哪些新增/在建/搬迁项目会改变 12–36 个月的供给；
4. **先打谁**：目标区域有哪些下游客户，谁用量大、谁适合做锚点、下一步动作是什么。

这个 skill 把上述研究固化成一套**可复用的研究流程 + 数据契约 + 两个交付物**。它**不是**一个纯碱模板：把 `data.json` 换成任意化工品、任意目标区域即可，代码不需要改。

**默认输出**

| 交付物 | 作用 | 硬要求 |
|---|---|---|
| `*.html` | 给销售/老板看的交互式竞争供给地图 | 单文件、离线打开、内联 ECharts + 中国地图 + 数据 + 交互 |
| `*.xlsx` | 给销售带走/打印/二次筛选的工作簿 | 9 个工作表，含来源、冲突、缺口，至少 2 张图 |
| `data.json` | 唯一数据源；HTML 和 Excel 都从它生成 | 通过 `validate.py`，无悬空来源、无产能对不上 |
| `build_report.json` | 构建回执：数量、哈希、警告 | 由 `build_all.py` 自动生成 |

**示例**

- `examples/01-soda-ash-guangdong-jiangmen/`：真实纯碱案例（广东江门，17 家/22 厂/3,070 万吨样本，37 条来源，9 项冲突）。可直接打开看“成品长什么样”。
- `examples/02-minimal-template/`：**结构示例，不是研究结论**。3 家虚构企业、3 座工厂、4 条虚构来源，用来快速复制字段和跑通流程。

## 什么时候用 / 什么时候不用

**用**：区域进入、客户开发前的竞争摸底、销售包/投标材料、新产能跟踪、渠道布局、给老板解释“为什么先打这个城市”。

**不用**：

- 投资研究、估值、买卖建议；
- 价格预测、期货交易；
- 需要**市场份额**的结论（本 skill 明确禁止把样本覆盖当市场份额）；
- 需要企业级成本模型/完整供应链排产的场景（这里只做销售布局，不做工厂设计）。

## 五条不可妥协的原则

1. **样本 ≠ 全行业**。报告里只写“样本在产”“样本覆盖”，不写“全国产能”“市场份额”。如果样本 3,070 万吨、全国口径 4,305–4,468 万吨，只能写“覆盖约 69–71%，这是覆盖度，不是份额”。
2. **产能 ≠ 产量**。产能是名义能力；产量是实际产出。产量缺失就写“未披露”，不要用产能替代。
3. **直线距离 ≠ 运费**。地图上的 km 是球面直线距离；只能用于排序和分层，不能当铁路/水运/短驳成本。
4. **项目毛增量 ≠ 净增**。搬迁、技改、置换、老线退出必须逐项判断；只加正向项目会系统性高估。
5. **证据分级，冲突并列**。每条产能至少能回到一个来源；A/B/C/D 标注证据强度；冲突不强行“抹平”，写清采用哪个口径、为什么、对结论有什么影响。

## 研究流程（七步，顺序不要乱）

### Step 1 · 锁定产品与目标区域

先写清楚：

- 产品全称、品种/规格（轻碱/重碱、片碱/液碱、聚合级/工业级……）；
- 目标省/市、目标客户或锚点客户；
- 销售半径假设（300/800/1500 km 或自有仓储半径）；
- 时间窗（数据截至日、项目观察期）。

输出到 `data.json` 的 `meta` 与 `target`。目标经纬度必填，因为距离和地图都靠它。

**常见错误**：把“华东”当目标区域。区域必须落到省/市/经纬度，否则无法做距离带。

### Step 2 · 建立产品-工艺-企业底图

先回答“这个产品有几种工艺、每种工艺对应哪些企业”。中国化工品的竞争结构通常由工艺路线决定：

- 纯碱：氨碱 / 联碱 / 天然碱；
- 烧碱：离子膜 / 隔膜；
- 甲醇：煤制 / 天然气 / 焦炉气；
- 钛白粉：硫酸法 / 氯化法；
- 塑料：不同原料路线与牌号。

这一层不要急着找数字，先把**工艺分类**和**企业长名单**拉出来。工艺分类会决定后面的颜色、图例、筛选和竞争判断。

### Step 3 · 目标区域需求与锚点客户

找 1 个锚点客户（最好公开可核实），回答：

- 它做什么产品、规模多大；
- 目标化工品在它的成本/工艺里起什么作用；
- 公开可推算的用量级是多少；
- 它现在的供应来源可能是什么（本地/外省/进口）；
- 它的认证周期、指标敏感点、采购习惯。

用量必须标“推算/假设”，不能写成企业披露。若找不到公开用量，就写“用量待核”，不要编。

### Step 4 · 在产供给普查（核心）

按“企业 → 工厂 → 产能 → 工艺 → 经纬度 → 来源”建表。建议顺序：

1. 上市公司年报/半年报/债券募集说明书：找“主要生产基地、产能、产量、在建项目”；
2. 公司官网/IR/公众号：找工厂地址、产能、产品牌号；
3. 政府/园区/环评/能评/安评公示：找项目规模、地点、时间；
4. 行业协会/统计局/海关：找行业总量、开工率、进出口；
5. 券商深度/行业媒体：只作为交叉验证，不单独作为 A 级证据；
6. 地图/物流：用于经纬度和距离，不用于产能。

**每个工厂至少要有一个来源 ID**；企业产能默认应等于其工厂产能之和（脚本会校验，差 >0.51 直接报错）。

**负增量**：冷修、停产、限产、退出、环保搬迁也要收集。没有负增量，项目表一定高估净增。

### Step 5 · 新增/在建/搬迁项目

逐项记录：

- 规模、地点、工艺、性质（新建/扩建/技改/搬迁/置换）；
- 状态（规划/备案/环评/开工/设备安装/试生产/投产）；
- 预计时间、净增判断、对目标区域的影响；
- 来源（环评/公告/开工报道）。

把“毛增量”和“净增”分开写。搬迁项目要标“净增 0（置换）”；技改要问“老线是否退出”。

### Step 6 · 区域需求与潜客

按目标省/市找下游客户，至少覆盖 2–3 个赛道。每个潜客写：

- 公开规模（产线/产能/门店/项目）；
- 用量级（推算，标 `*`）；
- 使用场景；
- 为什么优先（本地、规模、指标、认证、物流）；
- 下一步动作（技术交流/送样/报价/框架）；
- 证据等级与来源。

**同行不列入潜客**；贸易商与终端要分开。潜客样本不是全量，报告里要写“样本”。

### Step 7 · 三角验证与结论

对每个关键数字至少做一次交叉验证：

- 年报 vs 官网 vs 行业报道；
- 产能 vs 产量 vs 销量；
- 项目规模 vs 环评 vs 开工报道；
- 本地供给 vs 海关/物流调入线索。

然后写三层结论：

1. **竞争密集区**：样本产能集中在哪些省、哪些工艺；
2. **区域空白/远距**：目标区域本地有多少、最近的外省货在多远、300–800 km 是否有货；
3. **未来变量**：哪些项目会改变格局、销售窗口在什么时候。

最后写**数据缺口**和**边界**：查不到什么、哪些结论不能下、下一步补什么。缺口不是免责声明，是取证清单。

> 详细检索词、来源优先级、冲突处理、项目净增判断、潜客筛选，见 `references/research-playbook.md`。

## 数据契约（只改数据，不改代码）

完整字段见 `references/data-contract.md`。最小结构：

```json
{
  "meta": {
    "product": "产品全称",
    "product_short": "简称",
    "unit": "万吨/年",
    "asof": "2026-10-19",
    "region": "省 · 市",
    "province": "省",
    "city": "市",
    "target_lon": 113.08,
    "target_lat": 22.58,
    "anchor_customer": "锚点客户全称",
    "anchor_short": "锚点简称",
    "processes": [{"name": "工艺甲", "color": "#2F6F8F"}],
    "distance_bands": [
      {"label": "≤300km 本地", "max": 300},
      {"label": "300–800km 近邻", "max": 800},
      {"label": "800–1500km 长途", "max": 1500},
      {"label": ">1500km 超长途", "max": null}
    ]
  },
  "target": {"province": "省", "city": "市", "region": "省 · 市", "lon": 113.08, "lat": 22.58,
             "customer": "锚点客户全称", "customer_short": "锚点简称"},
  "companies": [
    {"id": "co_1", "name": "企业全称", "short": "简称", "hq": "总部", "process": "工艺甲",
     "capacity": 100, "output": 80, "cap_year": "2025", "grade": "A",
     "products": "产品", "coverage": "覆盖线索", "new": "新增描述",
     "source_ids": ["S01"], "projects": ["pr_1"]}
  ],
  "plants": [
    {"id": "pl_1", "company_id": "co_1", "name": "工厂名", "province": "省", "city": "市",
     "lon": 111.7, "lat": 38.5, "process": "工艺甲", "capacity": 100, "cap_year": "2025",
     "products": "产品", "note": "备注", "grade": "A", "source_ids": ["S01"]}
  ],
  "projects": [],
  "prospects": [],
  "sources": [],
  "conflicts": [],
  "gaps": [],
  "boundaries": [],
  "demand_by_prov": {},
  "narrative": {}
}
```

**关键规则**

- `id` 全局唯一；工厂必须引用存在的 `company_id`；所有 `source_ids` 必须存在。
- 企业 `capacity` 省略时自动等于其工厂产能之和；显式填写则必须一致（差 ≤0.51）。
- 经纬度是工厂坐标，不是注册地；同一企业多基地要拆成多座工厂。
- `distance_bands` 的 `max` 决定距离分层；最后一条用 `null`。
- `processes` 的颜色决定地图/矩阵/Excel 的工艺色；不填会自动补色，但建议显式给。
- `narrative` 是“人话层”：`hero_lede`、`conclusions`、`pipeline_foot`、`prospect_conclusions`、`method_conclusions`、`anchor_facts`、`anchor_use_value` 等；缺省会生成通用文案，但正式交付应手写。
- `meta.coverage` 用于“样本覆盖度”：`{"industry_low": 4305, "industry_high": 4468}`；没有就留空，脚本只显示来源条数，不编覆盖率。

## 生成与验收

### 一键生成

```bash
cd chemical-competitor-supply-map
python scripts/build_all.py examples/01-soda-ash-guangdong-jiangmen/data.json \
  examples/01-soda-ash-guangdong-jiangmen
```

输出：

```text
纯碱_广东江门_竞争供给地图.html
纯碱_广东江门_竞争供给地图.xlsx
build_report.json
```

### 先验数据，再验成品

```bash
python scripts/validate.py path/to/data.json
python scripts/qa.py --data path/to/data.json \
  --html path/to/out.html --xlsx path/to/out.xlsx
```

`validate.py` 管数据（必填、外键、产能合计、距离带合计、利用率警告、市场份额措辞）；`qa.py` 管成品（HTML 是否内联、章节是否齐全、Excel 是否 9 表、行数/链接/图表是否够、合并单元格是否重叠）。

`qa.py` 通过后再交付。若环境有 LibreOffice，可额外用 `soffice`/LibreOffice Kit 做 PDF 目检；没有也不影响数据与结构验收。**不要**为了预览去安装系统 LibreOffice。

### HTML 必须包含的 6 个章节

1. `#mapsec` 竞争供给地图 + 企业叠加 + 工艺/图层筛选 + 右侧区域读数；
2. `#matrixsec` 企业对比矩阵（产能/产量/工厂/距离/覆盖/新增/等级）；
3. `#densitysec` 省级供给 + 距离带 + 工艺结构 + 区域对照表；
4. `#newsec` 新增产能时间线；
5. `#prospectsec` 锚点客户 + 潜客表 + 销售动作卡；
6. `#methodsec` 来源清单 + 口径冲突 + 数据缺口 + 方法结论。

### Excel 必须包含的 9 个工作表

`00_封面`、`01_企业矩阵`、`02_工厂明细`、`03_新增项目`、`04_区域对照`、`05_目标区域与潜客`、`06_数据来源`、`07_口径与冲突`、`08_数据缺口与边界`。

详细版式、字号、颜色、打印设置见 `references/design-system.md`；验收清单见 `references/qa-checklist.md`。

## 在其他 Agent / 电脑上用

### Claude Code

```bash
# 用户级
cp -r chemical-competitor-supply-map ~/.claude/skills/
# 或项目级
mkdir -p .claude/skills && cp -r chemical-competitor-supply-map .claude/skills/
```

重启会话后，Claude Code 会自动发现 `SKILL.md`。首次构建前确认 `python -c "import openpyxl"` 可用；缺了就 `python -m pip install openpyxl`（只装一次，构建本身不联网）。

### Codex

把整个目录放到项目的 `skills/chemical-competitor-supply-map/`，或放到 Codex 的用户 skills 目录（不同版本路径可能不同，以当前 Codex 文档为准）。让 Codex 先读 `SKILL.md`，再执行 `scripts/build_all.py`。Codex 不需要 DSH 专有工具；只需要 Python + openpyxl。

### ChemClaw / WorkBuddy

优先上传**解压后的整个文件夹**（保留 `SKILL.md`、`scripts/`、`references/`、`examples/`、`assets/`）。如果平台只支持 zip，上传 `dist/chemical-competitor-supply-map.zip`；如果只支持单文件，至少上传 `SKILL.md` + `scripts/` + `references/data-contract.md`，再让它按流程执行。平台的“知识库/技能”入口不同，但核心是同一件事：让 agent 能读到 `SKILL.md` 和脚本。

### 通用 Python 环境

```bash
python --version           # 3.10+
python -c "import openpyxl"  # 必须
python scripts/build_all.py data.json outdir
```

无网络也能构建；ECharts 和中国 GeoJSON 已放在 `scripts/assets/`。

> 各平台适配、路径、常见报错见 `references/adapters.md`。

## 什么时候需要改代码

**不需要改**：换产品、换区域、换企业、换项目、换潜客、换文案——只改 `data.json`。

**需要小改**：

- 目标国家不是中国：替换 `scripts/assets/china_prov.json`，并调整 `app.js` 的 `registerMap`/`geo` 配置；
- 需要新的图表维度（如开工率、进出口、价格）：在 `build_html.py` / `build_xlsx.py` 增加字段和图表；
- 需要新的 Excel 表：同时改 `build_xlsx.py` 与 `qa.py` 的 9 表校验；
- 需要新的交互（如区域对比、路线规划）：改 `templates/app.js`，再跑 `node --check`。

改代码后必须重新跑两个示例，确认不是“只对纯碱有效”。

## 质量红线（交付前逐条打勾）

- [ ] 没有“市场份额”“市占率”；只有“样本覆盖/样本内占比”。
- [ ] 没有把产能当产量；产量缺失写“未披露”。
- [ ] 没有把直线距离当运费；距离只用于排序/分层。
- [ ] 项目毛增量与净增分开；搬迁/技改/置换已单列。
- [ ] 每条产能至少一个来源；冲突有 A/B 口径、采用理由、影响。
- [ ] 潜客有来源；用量标“推算”；同行未混入。
- [ ] 数据缺口 ≥5 条，且是“下一步取证”，不是免责声明。
- [ ] `validate.py` 与 `qa.py` 都通过。
- [ ] HTML 离线打开无 CDN、无报错；手机宽度无横向溢出（表格内部可横滑）。
- [ ] Excel 9 表齐全，来源可点击，打印区域合理，至少 2 张图。
- [ ] 示例 01 与示例 02 都能重新构建。

## 文件地图

```text
chemical-competitor-supply-map/
├── SKILL.md                     ← 本文件；agent 入口
├── README.md                    ← 人读的快速开始
├── LICENSE
├── scripts/
│   ├── common.py                ← 归一化、距离、聚合、默认文案
│   ├── validate.py              ← 数据校验
│   ├── build_html.py            ← HTML 生成（内联 CSS/JS/ECharts/GeoJSON）
│   ├── build_xlsx.py            ← 9 表 Excel
│   ├── build_all.py             ← 一键构建 + build_report
│   ├── qa.py                    ← 成品硬门禁
│   ├── templates/
│   │   ├── app.js               ← 地图/矩阵/抽屉/图表交互
│   │   └── style.css            ← 版式
│   └── assets/
│       ├── echarts.min.js
│       └── china_prov.json
├── references/
│   ├── research-playbook.md     ← 研究流程、检索词、证据规则
│   ├── data-contract.md         ← 字段表 + 最小示例 + 常见错误
│   ├── design-system.md         ← HTML/Excel 视觉规范
│   ├── qa-checklist.md          ← 验收清单
│   └── adapters.md              ← Claude Code / Codex / ChemClaw / WorkBuddy
├── examples/
│   ├── 01-soda-ash-guangdong-jiangmen/
│   │   ├── data.json
│   │   ├── 纯碱_广东江门_竞争供给地图.html
│   │   ├── 纯碱_广东江门_竞争供给地图.xlsx
│   │   └── README.md
│   └── 02-minimal-template/
│       ├── data.json
│       ├── 示例品_示例省示例市_竞争供给地图.html
│       ├── 示例品_示例省示例市_竞争供给地图.xlsx
│       └── README.md
└── dist/                        ← 可选 zip
```

## 一句话

**先证据、后结论；先样本、后全行业；先距离分层、后销售动作。** 把 `data.json` 换掉，这套地图就能用在下一个化工品上。
