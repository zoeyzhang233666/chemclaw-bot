---
name: chemical-second-source
description: >-
  Build a verifiable second supply source / alternate-supplier shortlist for any chemical or material, preserving a proven procurement research logic and output structure. Use when a buyer or sourcing manager asks 找备选供应商, 第二供应源, 双源, 备选池, 供应商比选, 替代供应商, second source, alternate supplier, supplier shortlist, dual sourcing, or “现有供应商风险太高，想找一家备选”. Product-agnostic: soda ash, titanium dioxide, caustic soda, methanol, resins, solvents, industrial gases, food additives, battery materials, etc. Delivers one self-contained interactive HTML plus a 10-sheet Excel workbook generated from one data.json, with evidence grades, same-source checks, spec/sample matrix and a 30/60/90-day validation plan. Includes a real soda-ash example and a synthetic schema example.
license: MIT
compatibility: Python 3.9+ with openpyxl>=3.1; Node.js only for optional JS syntax/UI checks. No network at build time; all data and CSS/JS are inlined.
metadata:
  version: 1.0.0
  author: procurement-research
  output: [html, xlsx, json]
  languages: [zh-CN]
  category: chemical-procurement-research
---

# 化工品第二供应源 · Chemical Second Source

## 这个 skill 解决什么问题

现有供应商有风险（亏损、单一基地、装置老化、区域限产、价格被动），但采购不能凭一篇报道就换供应商。正确动作是：

1. **先定义“兼容”**：把现有供应商的牌号、COA、内控指标拆成可检测项；
2. **再找“生产企业”**：按工艺路线、产区、集团、公开产能拉长名单；
3. **排除“假第二源”**：同集团、母子公司、同一实控人、纵向竞争、同一销售主体；
4. **用证据分级**：A=公告/政府，B=协会/券商/主流媒体，C=官网/百科；不确定的写“待核实”；
5. **用试样验证**：新装置、新工艺、非准入品牌一律首样，不拿“产能”当“质量”；
6. **把决策留给采购**：输出排序、差异、风险和下一步，不写“建议换成某一家”。

这个 skill 把上述过程固化成 **研究流程 + 数据契约 + 两个交付物**。它**不是纯碱模板**：把 `data.json` 换成任意化工品即可，HTML/Excel 代码不需要改。

## 默认输出

| 交付物 | 作用 | 硬要求 |
|---|---|---|
| `*.html` | 给采购/老板/质量部看的交互式工作台 | 单文件、离线打开、内联 CSS/JS/数据；卡片+表格、筛选、勾选对比、雷达、打印 |
| `*.xlsx` | 带走、打印、二次筛选、审厂记录 | 10 个工作表；含来源、同源、试样、风险、行动、尽调；至少 3 张图 |
| `data.json` | 唯一数据源；HTML 和 Excel 都从它生成 | 通过 `validate.py`；来源 ID 不悬空；规格矩阵完整 |
| `build_report.json` | 构建回执：数量、哈希、警告 | 由 `build_all.py` 自动生成 |

## 什么时候用 / 什么时候不用

**用**

- 现有供应商出现财务/装置/区域/合规风险，需要“1 主 + 1 备”；
- 新工厂、新项目、新牌号导入，需要可验证的备选池；
- 年度招标/询价前，需要一份有证据链的短名单；
- 老板问“除了这家还有谁”，需要把“谁、在哪、多大、什么工艺、能不能用、有什么坑”讲清楚；
- 客户/体系审核要求“关键原料有第二供应源”。

**不用**

- 投资研究、估值、买卖建议；
- 价格预测、期货交易；
- 供应商授标/合同审批（本 skill 只做研究辅助）；
- 需要现场审计结论、法律尽调结论的场景（这里只列“要审什么”）；
- 把贸易商、代理商、贴牌商当成“生产企业”的名单。

## 八条不可妥协的原则

1. **排序 ≠ 建议，决策权在采购。** 所有页面写“排序 ≠ 建议 · 决策权在采购”；不出现“建议换成 X”“X 是最佳供应商”。
2. **先规格，后厂家。** 同品种不同牌号/等级可能完全不兼容；规格不确定就标“待核/需试样”，不能因为“都是纯碱/都是钛白粉”就判定可替代。
3. **只把生产企业放进主池。** 贸易商、代理商、贴牌商可以放“渠道备注”，不能占“第二供应源”名额；必须做股权/生产地址/生产许可穿透。
4. **同源只能算一个独立源。** 母子公司、同一实控人、同一集团统一销售、同一生产基地不同法人，都要显著提示；同时入选会高估独立性。
5. **证据分级 + 日期 + 链接。** 每个关键数字至少一个来源 ID；A/B/C 标注；没有来源的数字不进正文，放“待核实”。
6. **产能 ≠ 产量，距离 ≠ 运费。** 产能是名义能力；运距是地理距离；运费是“距离 × 费率”的区间估算，不是承运商报价。
7. **新装置/新工艺/非准入必试样。** “全流程贯通”“已出货”不等于“重质比例/粒度/白度/杂质稳定”；首样至少 3 批，新装置追加稳定性批次。
8. **双源不是替换。** 目标是“现有 + 备选”的供应韧性；不是建议立刻切走现有供应商。商务动作写“锁量/试单/备供”，不写“替换”。

## 研究流程（十步，顺序不要乱）

### Step 0 · 锁定输入（5 分钟）

先问清/写清：

- 产品全称、品种/等级/牌号（例：重质纯碱 II 类优等品；金红石型钛白粉 R-996；离子膜 32% 液碱）；
- 现有供应商全称、工厂地址、工艺、名义产能、品牌/资质；
- 收货地（省/市/园区）、月采购量、包装/卸货条件；
- 关键质量指标/客户特殊要求（食品级、光伏级、电池级、医用级……）；
- 数据截止日、可接受的运距/运输方式、是否需要备选“同城/同省”。

写入 `meta` / `params` / `baseline`。**收货地必须落到城市/园区**，否则运距和运费没有意义。

### Step 1 · 拆规格（Spec decomposition）

把“能不能用”拆成 9–15 项可检测指标，每项写：

- 指标名、单位、目标值/上限、检测方法/标准；
- 现有供应商最近 COA 的实际值（有就填，没有写“待取”）；
- 对下游工艺的影响（例：Fe₂O₃ 影响光伏玻璃透光率；粒度影响下料/熔化；水分影响称量与结块）。

写入 `spec_items`。**不要只写“符合国标”**：国标是最低门槛，客户内控往往更严。

### Step 2 · 建现有供应商基线（Baseline）

至少回答：

- 身份：上市代码/统一社会信用代码、集团、实控人、股权性质；
- 生产地：省/市/园区/厂区，到收货地运距、运输方式；
- 产能：名义产能、实际产量（若公开）、装置条数/投产时间；
- 产品：牌号、等级、主营产品结构；
- 资质：行业准入、交割品牌、体系认证、食品/危化品等；
- 财务/风险：最近一年营收/净利、公开亏损/诉讼/环保/安全/检修；
- 规格：COA 关键项、客户投诉/结块/批次稳定性。

写入 `baseline`。基线的 `risk_summary` 是“为什么建第二源”的背景，不是“必须换”的结论。

### Step 3 · 拉长名单（Long list，15–30 家）

按以下顺序找，不要先搜“XX 供应商排名”（广告/贸易商多）：

1. **工艺路线**：这个产品有几种工艺？每种工艺对应哪些企业/产区？
   - 纯碱：氨碱 / 联碱 / 天然碱；
   - 钛白粉：硫酸法 / 氯化法；
   - 烧碱：离子膜 / 隔膜；
   - 树脂：悬浮 / 本体 / 乳液；溶剂：石油基 / 煤基 / 生物基。
2. **产区**：主产区企业名单 + 园区/环评/能评公示；
3. **上市公司/集团**：年报“主要生产基地、产能、在建项目”、债券募集书；
4. **行业协会/券商**：只做交叉验证，不单独作为 A 级；
5. **下游客户/同行**：客户合格供方名录、公开招标/中标公告；
6. **海关/进出口**：进口货源可作为“外源”，但要单独标“进口/船期/汇率”。

写入 `candidates`（先 15–30 家，最后保留 5–15 家）。**贸易商不占名额**；同一集团多基地可保留，但要在 `same_source` 标注。

### Step 4 · 身份穿透与同源排查（核心）

逐家确认：

- 是**生产企业**还是贸易/代理/贴牌？看生产地址、生产许可、环评主体、COA 抬头；
- 股权链：直接股东 → 上层集团 → 实控人 → 是否与现有供应商/池内其他家同源；
- 同一集团不同法人/基地：能否独立报价/独立供货/独立承担质量责任？
- 纵向竞争：供应商是否向下游延伸（例：纯碱厂被玻璃集团全资；钛白粉厂被涂料集团控股）；
- 同一销售主体：两家工厂是否由同一销售公司统一定价/签合同？

写入 `same_source`。`flag` 建议值：`同源` / `同集团` / `纵向竞争` / `多厂区` / `非同源` / `单一`。**同源不是“不能买”，是“不能算两个独立源”**。

### Step 5 · 区位、物流与产能

每家写：

- 省/市/园区/厂区地址；
- 到收货地的**地理运距**（km）与运输方式（汽运/铁路/水运/多式联运）；
- 运费区间（元/吨）：`距离 × 费率` 的结构化估算；注明年份/口径；
- 名义产能（`capacity`）与产能备注（几条线、投产时间、重质/轻质比例、实际产量）；
- 是否新装置（`new_plant`）、是否在搬迁/技改/限产。

**禁止**把“集团总产能”直接写成“可售货源”；多厂区必须锁定具体厂区/销售主体。

### Step 6 · 资质、公开风险与证据台账

资质按行业选：

- 纯碱：郑商所免检交割品牌、食品生产许可（SC，如适用）、ISO；
- 钛白粉：硫酸法/氯化法准入、危化品、REACH/客户认证；
- 烧碱/危化品：安全生产许可、危化品经营/运输、排污许可；
- 食品添加剂/医药：SC/药品 GMP/FSSC 22000 等。

风险至少覆盖：财务（亏损/现金流/涉诉）、装置（新线/老化/检修/故障）、环保/安全（限产/处罚）、资质（非准入/证书到期）、同源/独立性、规模/单一基地、价格/供给。

每条风险写：`company / type / category / fact / impact / source_id / status`。`status` 只允许 `已公开` / `待核实`；**待核实不能写成结论**。

### Step 7 · 规格兼容与试样计划

对每个候选 × 每个规格项，标三态：

- `COA`：可凭批次 COA/出厂检验追溯，但仍需核对批次与项目；
- `试样`：必须首样/小批量验证（新装置、新工艺、非准入、天然碱/矿源差异、粒度/白度敏感）；
- `审核`：需现场审核/封样/包装确认（食品级、危化品、客户审厂）。

写入 `spec_status`。首样建议：

- 每家 20–50 kg × 3 批（新装置 5 批）；
- 检测周期 7–10 个工作日；
- 判定依据：客户内控 + 国标/行标 + 下游小试/中试；
- 留样 12 个月，记录批次/生产日期/检验员。

### Step 8 · 横向对比（不造“唯一总分”）

对比维度固定为：

1. 身份与区位（全称、集团/实控人、股权、生产地、运距、运输、运费）；
2. 产能与产品（工艺、产能、等级/牌号、主营）；
3. 规模与财务（营收、净利、员工）；
4. 资质与规格（准入、规格兼容、试样要求、风险摘要）；
5. 风险与同源（风险等级/分、同源关系、需核实）；
6. 与现有供应商的差异（工艺、运距、产能、资质、风险）。

HTML 里做基线 + 所选备选的对比弹窗、雷达和差异列表；Excel 里做 `03_横向对比`。**不输出“综合得分排名第一”**；雷达是相对刻度，不是评分模型。

### Step 9 · 30/60/90 天双源行动

按“验证与建源”写，不写“替换”：

- 0–30 天：锁定 2–3 家、同源排查、首轮询价、产能/排产证明、COA；
- 31–60 天：首样/小试、到厂试运（1 车）、包装/卸货/计量验证；
- 61–90 天：现场审核、商务条款（最小起订/账期/赔付/月度锁量）、1 主 + 1 备框架；
- 持续：季度风险复盘、年度复审、备用源保持“热备”（小比例试单）。

写入 `actions`。责任要落到岗位（采购/质量/物流/法务/财务），产出要可验收。

### Step 10 · 生成与 QA

```bash
python scripts/validate.py examples/01-soda-ash/data.json
python scripts/build_all.py examples/01-soda-ash/data.json out --prefix 纯碱
python scripts/qa.py out --node /path/to/node
```

生成后人工检查：

- HTML 离线打开是否正常、筛选/勾选/对比/打印是否可用；
- Excel 10 个表是否齐全、列宽/换行/冻结/筛选是否正常；
- 每个关键数字能否点回来源；同源提示是否显著；“待核实”是否没有写成结论；
- 页面/工作簿是否出现“建议换成 X”之类越界表述。

> 检索词、来源优先级、身份/产能/物流核实方法，见 `references/research-playbook.md`。
> 字段逐项说明，见 `references/data-contract.md`。

## 数据契约（只改数据，不改代码）

完整字段见 `references/data-contract.md`。最小结构：

```json
{
  "meta": {
    "product": "产品全称",
    "product_short": "简称",
    "unit": "万吨/年",
    "asof": "2026-10-19",
    "buyer_site": "省 · 市（园区）",
    "buyer_short": "苏州",
    "volume": "800 吨/月",
    "volume_t": 800,
    "volume_period": "月",
    "spec": "关键规格",
    "use_case": "下游用途",
    "qualification_label": "行业准入/交割品牌",
    "qualification_short": "准入",
    "grade_label": "等级 / 牌号",
    "near_km": 500,
    "fin_year": "2025",
    "output_year": "2024",
    "processes": [
      {"name": "工艺甲", "color": "#b45309", "cost_score": 55},
      {"name": "工艺乙", "color": "#1f5eff", "cost_score": 75}
    ],
    "risk_categories": ["财务", "装置", "资质", "同源", "行业"],
    "same_source_note": "同源特别提示",
    "spec_note": "首样/检测口径",
    "disclaimer": "研究辅助，不构成替换/授标建议"
  },
  "params": {"monthly": 800, "receiver": "收货地", "freight_rate": 0.45, "water_rate": 0.12, "truck_load_t": 30, "price_assumption": 1150},
  "baseline": {"id": "S00", "name": "现有供应商", "short": "现有", "process": "工艺甲", "capacity": 280, "distance": 760, "freight_low": 200, "freight_high": 360, "qualified": true, "risk_level": "中高", "risk_score": 4, "evidence": ["SRC01"]},
  "candidates": [
    {"id": "S01", "name": "备选企业", "short": "备选", "province": "江苏", "city": "连云港", "site": "园区", "distance": 400, "transport": "汽运", "freight_low": 80, "freight_high": 190, "process": "工艺乙", "capacity": 110, "grade": "等级", "brand": "牌号", "qualified": true, "new_plant": true, "risk_level": "中", "risk_score": 3, "spec_fit": "中高", "sample": "必须", "same_source": "无", "evidence": ["SRC02"], "verify": ["待核事项"]}
  ],
  "spec_items": [{"id": "assay", "label": "主含量", "target": "≥99.2%"}],
  "spec_status": {"S01": {"assay": "COA"}},
  "same_source": [{"group": "集团", "parent": "母公司", "entities": ["A", "B"], "relation": "母子公司", "implication": "只能算一个源", "verify": "销售主体", "flag": "同源"}],
  "risks": [{"company": "企业", "type": "财务", "category": "财务", "fact": "公开事实", "impact": "影响", "source_id": "SRC01", "status": "已公开"}],
  "actions": [{"phase": "第 0–30 天", "action": "锁定 2–3 家", "detail": "动作说明", "owner": "采购", "output": "询价单"}],
  "sources": [{"id": "SRC01", "name": "来源名", "url": "https://...", "grade": "A", "date": "2026-01-01"}]
}
```

### 字段速查

| 块 | 必填 | 说明 |
|---|---|---|
| `meta` | product/product_short/unit/asof/buyer_site/spec/processes | 页面标题、单位、截止日、收货地、规格、工艺颜色 |
| `params` | monthly/receiver/freight_rate | 月量、收货地、汽运费率；`price_assumption` 可选 |
| `baseline` | name/short/process/capacity/distance/freight_low/high | 现有供应商；`qualified`/`risk_level`/`risk_score` 建议填 |
| `candidates` | id/name/short/process/capacity/distance/freight_low/high/risk_level/risk_score/qualified/evidence | 5–15 家；`new_plant`/`tags`/`verify` 强烈建议 |
| `spec_items` | id/label/target | 9–15 项；顺序即矩阵列顺序 |
| `spec_status` | 每家候选 × 每个 spec id | 值只能是 `COA`/`试样`/`审核` |
| `same_source` | group/parent/entities/relation/implication/verify/flag | 同源提示 |
| `risks` | company/type/fact/impact/status | `source_id` 必须存在；`category` 可覆盖默认归类 |
| `actions` | phase/action/detail/owner/output | 30/60/90 天动作 |
| `sources` | id/name/url/grade/date | `grade` 只能是 A/B/C；ID 与正文引用一致 |

## 两个示例

- `examples/01-soda-ash/`：**真实研究案例**。重质纯碱，现有供应商山东海化，收货地苏州，12 家备选、9 项规格、45 条来源；可直接打开看“成品长什么样”，也可作为研究口径参照。
- `examples/02-minimal-template/`：**结构模板，不是研究结论**。3 家虚构企业、5 项规格、3 条虚构来源；复制这个目录，替换数据即可跑通。

两个目录都带生成好的 HTML + Excel，不需要先装环境才能看。重新生成时：

```bash
python scripts/build_all.py examples/02-minimal-template/data.json examples/02-minimal-template --prefix 示例化工品X
```

## 目录结构

```
chemical-second-source/
├── SKILL.md
├── README.md
├── AGENTS.md                 # 给 Codex/通用 agent 的短入口
├── requirements.txt
├── LICENSE
├── scripts/
│   ├── common.py             # 读入/normalize/统计
│   ├── validate.py           # 数据校验（硬错误退出 1）
│   ├── build_html.py         # data.json → 单文件 HTML
│   ├── build_xlsx.py         # data.json → 10-sheet Excel
│   ├── build_all.py          # 校验 + 两个产物 + build_report.json
│   ├── qa.py                 # HTML/Excel 结构 QA + node --check + 运行时 smoke
│   ├── smoke_js.js           # 可选运行时 smoke（DOM stub 执行内联 JS）
│   ├── package.py            # 打包 zip（UTF-8 文件名标志）
│   └── templates/
│       ├── workbench.html
│       ├── style.css
│       └── app.js
├── references/
│   ├── research-playbook.md
│   ├── data-contract.md
│   ├── evidence-grading.md
│   ├── same-source-checklist.md
│   ├── spec-compatibility.md
│   ├── industry-adaptation.md
│   ├── design-system.md
│   ├── qa-checklist.md
│   └── adapters.md
├── examples/
│   ├── 01-soda-ash/          # 真实案例 + 生成物
│   └── 02-minimal-template/  # 合成 schema 模板 + 生成物
└── dist/                     # 可选：打包 zip
```

## 换电脑 / 换 agent

这个 skill 只依赖 **文件读写 + shell + Python 3.9+ + openpyxl**；不需要 DSH 专属 API、不需要联网、不需要数据库、不需要 Node（Node 只用于可选 JS 语法检查）。

- **Claude Code / Codex / ChemClaw / WorkBuddy / 其他 agent**：把整个 `chemical-second-source/` 目录放进 skills 目录，或直接让 agent 读 `SKILL.md` + `AGENTS.md`；按 Step 0–10 执行，产物用 `build_all.py` 生成。
- **Windows**：用 `py -3` 或完整 Python 路径；中文文件名可用；Excel 字体用“微软雅黑”，macOS 缺字体时自动回退。
- **macOS/Linux**：`python3`；路径用 `/`；中文字体回退到 PingFang/Noto。
- **没有 openpyxl**：`python -m pip install -r requirements.txt`；**不要**用 CSV 冒充 xlsx，也不要用空文件占位。
- **没有 Node**：跳过 `qa.py --node`，HTML 仍可打开；`build_all.py` 不需要 Node。
- **离线**：构建不需要网络；研究阶段需要联网检索，但产物完全离线。

详细适配见 `references/adapters.md`。

## 交付前自检（最短版）

- [ ] 页面/工作簿没有“建议换成 X”“X 最佳”这类越界结论；
- [ ] 每家候选是生产企业，不是贸易商；同源关系已标注；
- [ ] 每个关键数字有来源 ID；`待核实` 没有写成事实；
- [ ] 规格矩阵覆盖所有候选 × 所有指标；新装置/新工艺/非准入已标“必须试样”；
- [ ] 运距/运费/产能口径写清；没有把集团产能当可售货源；
- [ ] HTML 单文件离线可开；Excel 10 个表齐全、可筛选/打印；
- [ ] `build_report.json` 已生成，警告已读。

## 边界

本 skill 输出的是**采购研究辅助材料**，不是供应商授标、合同审批、法律尽调或投资建议。所有“待核实”必须以营业执照、生产许可、COA、现场审核、合同条款为准；最终决策权在采购组织。
