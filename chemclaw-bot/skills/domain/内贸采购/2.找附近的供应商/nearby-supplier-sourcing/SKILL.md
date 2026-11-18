---
name: nearby-supplier-sourcing
description: Use when a buyer needs to find suppliers near a delivery address for a chemical product (内贸采购 / 找附近供应商 / 就近采购 / 供应商寻源 / 运距评估 / 工厂还是仓库 / 危险品运输资质). Produces an evidence-graded supplier list with factory-vs-warehouse classification, straight-line and road distances, and delivers a self-contained interactive HTML map plus a styled Excel workbook. Product-agnostic: works for soda ash, caustic soda, methanol, TiO2, resins, solvents, etc.
version: 1.0.0
license: MIT
entry: SKILL.md
outputs: [xlsx, html, dataset.json, evidence-notes.md]
---

# 就近供应商寻源与运距评估（Nearby Supplier Sourcing）

把「我要采购 X，收货地在 Y，每次 N 吨，找 100/300/500 公里内的供应商」这件事，
做成**可复核、可推翻、可交付**的研究流程：先证产品匹配，再比距离，最后标注缺口。

适用范围：任何化工品/材料（大宗、精细、危化、非危化）。不适用于纯价格指数研究、
不适用于下游客户名单（那用 lead-sourcing 类技能）。

---

## 0. 交付契约（Contract）

一次完整运行必须产出 4 个文件，缺一不可：

| 文件 | 作用 | 是否必需 |
|---|---|---|
| `<产品>_供应商运距清单.xlsx` | 8 个工作表的结构化台账，采购可直接改、可筛选 | **必需** |
| `<产品>_采购雷达.html` | 自包含单文件（无外链、无 CDN），地图+列表+证据抽屉 | **必需** |
| `dataset.json` | 唯一数据源，HTML/Excel 都由它生成，便于复算与审计 | 必需 |
| `evidence-notes.md` | 研究过程留痕：搜了什么、为什么采信、哪些放弃了 | 必需 |

> 不允许「先写 HTML 再补数据」。顺序恒为 **数据 → 校验 → 生成**。
> HTML 与 Excel 必须来自同一份 dataset.json，数字对不上即为缺陷。

---

## 1. 六步流程（Six steps）

### Step 1 — 锁参数（5 分钟，先问再查）

必须确定的 6 个参数，缺失就**假设并显式标注**，不要停下来等：

1. 产品 + 规格（牌号/含量/形态：重质 vs 轻质、32% 液碱 vs 片碱、国标等级）
2. 收货地（精细到园区/门牌；只有城市名也可，但距离误差要标注）
3. 单次数量与频次（决定「厂家直销」还是「区域仓+贸易」）
4. 最远可接受距离（默认 500 km，UI 提供 100/300/500 切换）
5. 运输方式（汽运整车 / 零担 / 罐车 / 铁路 / 水运 / 自提）
6. 是否危化品（决定第 5 节整块内容，见 `references/hazmat-classification.md`）

**禁止**：不要因为用户没给地址就拒绝开工。默认给一个**同产业特征的示例收货地**，
在 HTML 顶部和 Excel 封面用醒目样式标注「示例收货点，可替换」，并说明替换后距离会重算。

### Step 2 — 建候选池（最耗时，40% 时间）

按「先生产、后流通」的顺序找，来源优先级见 `references/research-playbook.md`：

- **生产厂家**：交易所交割品牌/厂库名单 → 上市公司年报与产能公告 → 行业协会产能排名
  → 环评/投产公示 → 企业官网「生产基地」
- **仓库/交割库**：期货交易所指定交割仓库公告（含门牌地址，是判断"仓库"的最佳证据）
- **贸易/经销**：只作为兜底，必须标"非生产，货源需核实"

每个候选先落 5 个字段：企业全称、角色、地址、坐标、一条可点击的证据。
**找不到地址就不要进表**，宁可少 3 家也不要 1 家假地址。

### Step 3 — 定角色与坐标（决定结论可信度）

角色只有四种，判定规则：

| 角色 | typeCode | 判定依据 |
|---|---|---|
| 生产工厂 | `factory` | 有产线/产能/产量证据，厂址可定位 |
| 仓库/交割库 | `warehouse` | 交易所交割库公告、仓储企业官网、物流园提货点 |
| 仅注册地址 | `registered` | 只有工商注册地，无生产/仓储证据 |
| 贸易商 | `trader` | 有采购销售行为但无自有产能 |

坐标精度必须写进 `coord_note`（如"厂区中心点近似 ±2 km"），并在距离页展示。
**不允许**用城市中心点冒充厂址而不标注。

### Step 4 — 算距离（可复算）

- 直线：haversine（见 `references/distance-protocol.md` 的公式，脚本已实现）
- 公路：OSRM 路径规划（`assets/scripts/compute_routes.py`），同时取回路径几何给地图画线
- 不可达时降级：`公路 ≈ 直线 × 系数`，系数按地形取 1.15–1.35，并**在页面上标注"估算"**
- 输出绕行系数 = 公路/直线；异常值（<1.0 或 >1.6）要回查坐标

### Step 5 — 评分（两轴独立，绝不相加）

见 `references/scoring-model.md`。硬规则：

1. 匹配度 M（0–100）只看"能不能真供货"，不看远近
2. 物流分 L（0–100）只看距离分段，不看产品
3. 排序 = **先档位（A≥85 / B 70–84 / C<70），档内按 L 降序**
4. **禁止**把 M 与 L 加权成一个总分——这是本方法与其他"附近供应商"工具的核心差异

### Step 6 — 生成与自检

```bash
python assets/scripts/run_all.py --dataset dataset.json --out ./output
```

产出 xlsx + html。自检清单见第 7 节，逐项打勾后才交付。

---

## 2. 三条不可违反的规则

1. **近 ≠ 匹配**。2.6 公里的交割库不能排在高匹配碱厂前面；仓库类主体在
   `产品符合` 维度上限 30/35，永不给满分。
2. **不编造运费金额**。只给计费口径（吨公里/整车包干/回程车、装卸、过磅、压车）。
   用户提供报价后才可计算到厂价。
3. **缺口显式化**。拿不到的可供量、门牌、牌号、运费，写进 `gaps[]` 并在
   HTML「缺口」页与 Excel「06 数据缺口」逐条列出。**不要用推测填充，也不要用
   "大概/约"掩盖**。每条缺口必须能落到一个"下一步动作"。

---

## 3. 危化品分支（必做，不能跳过）

无论是不是危化品，都必须给出**判定结论 + 依据 + 后果**：

- 是：标注 UN 编号、危险类别、包装类别、所需资质（危险货物道路运输许可、押运员、
  专用车辆）、装卸与应急要求
- 否：明确写"不属于《危险化学品目录（2015 版）》、不属于 TDG 危险货物"，
  但仍写清粉尘/腐蚀/吸潮等作业风险与普通货运资质要求
- 边界情况：同一产品不同浓度/形态可能定性不同（如 32% 液碱 vs 片碱 vs 50% 液碱），
  必须按**采购的确切规格**判定，并在页面写明"若规格变化，本条失效"

细节见 `references/hazmat-classification.md`。

---

## 4. 输出结构（固定，不要自创）

### HTML（单文件，双击可开）

顶部：产品 + 规格 chips + 收货地 + 数据基准日 + 4 个 KPI
中段：地图（100/300/500 半径环 + 真实公路路径 + 工厂/仓库不同标记）｜候选列表（可按匹配/距离/角色筛选）
下段：距离×匹配矩阵、评分口径、采购路线、危化判定、缺口清单
交互：点企业开抽屉（概览/证据/距离/缺口 四页）、一键复制询价话术

### Excel（8 表，恒定）

`00 封面与说明` / `01 供应商总表` / `02 匹配度评分` / `03 证据链` /
`04 距离测算` / `05 运输与合规` / `06 数据缺口` / `07 询价清单`

表名、列序、冻结窗格、筛选、数据条都已固化在 `assets/scripts/build_xlsx.py`，
不要改结构，只改数据。

---

## 5. 证据分级（A/B/C/D）

| 级 | 含义 | 典型来源 | 能否单独支撑"在生产" |
|---|---|---|---|
| A | 官方/监管 | 交易所公告、政府公告、上市公司年报 | 能（产量/产能批复/交割资格） |
| B | 企业自述 | 官网、招聘页、企业公告 | 产能能，产量需交叉 |
| C | 二手 | 百科、行业媒体、券商研报 | 不能，需 A/B 补证 |
| D | 名录/推断 | 行业名录、搜索摘要 | 不能，只作线索 |

规则：`factory` 至少 1 条 A 或 2 条 B；否则降级为 `trader` 或标 C 档。
`warehouse` 靠交易所公告（A）即可认定"库存在"，但**不能**认定"此刻有货可卖"。

---

## 6. 数据模型

`dataset.json` 的完整字段见 `assets/dataset.template.json`，校验脚本：

```bash
python assets/scripts/validate_dataset.py dataset.json
```

必须包含：`meta`（产品/收货地/批量）、`hazmat`、`match.dims`、`logistics.rings`、
`playbook`、`items[]`（含 `evidence[]` 与 `gaps[]`）、`disclaimer[]`。
`road_km / straight_km / lScore / tier / rank` 由脚本计算，**不要手填**。

---

## 7. 交付前自检（逐项打勾）

- [ ] 每家都有 `typeCode`，且工厂/仓库划分有证据支撑
- [ ] 每家都有 `coord_note`，误差范围写清楚
- [ ] 每条证据有 `level`（A/B/C/D）、`url`、`date`
- [ ] C/D 级证据没有被用来单独证明"在生产"
- [ ] 匹配分与物流分分别展示，没有合成总分
- [ ] 排序符合"先档位后距离"，且能被 `rank` 复核
- [ ] 至少 1 条"近但不匹配"的案例被显式解释（不是悄悄删掉）
- [ ] 危化判定有结论、有依据、有"规格变化即失效"的提醒
- [ ] 全文无运费金额，只有计费口径
- [ ] 缺口数量 ≥ 企业数的一半（低于此说明你查得不够深，或写得太客气）
- [ ] HTML 无外链（`grep -c "http" report.html` 只应命中证据 URL 文本）
- [ ] Excel 能被 `openpyxl` 重新打开，8 个表齐全
- [ ] 示例收货地已显著标注"示例，可替换"

---

## 8. 目录

```
nearby-supplier-sourcing/
├── SKILL.md                      # 本文件
├── README.md                     # 安装到 chemclaw / workbuddy / codex / claude
├── AGENTS.md                     # Codex 风格入口
├── references/
│   ├── research-playbook.md      # 怎么找厂家/仓库/地址，搜索式模板
│   ├── scoring-model.md          # 五维评分与档位规则
│   ├── distance-protocol.md      # 距离口径、OSRM、降级方案
│   ├── hazmat-classification.md  # 危化判定与运输条款
│   ├── evidence-grading.md       # A/B/C/D 判定细则
│   └── output-spec.md            # HTML/Excel 字段与版式规范
├── assets/
│   ├── dataset.template.json
│   ├── dataset.schema.json
│   ├── template/report.html      # 数据驱动模板
│   └── scripts/
│       ├── run_all.py            # 一键：validate → geo → routes → scores → html → xlsx
│       ├── validate_dataset.py   # 结构与证据校验（弱证据高评分会被拦下）
│       ├── compute_routes.py     # haversine + OSRM + 降级估算
│       ├── compute_scores.py     # 匹配总分、档位、物流分、排序
│       ├── prepare_geo.py        # 省界底图下载与简化（带缓存与离线降级）
│       ├── build_html.py
│       └── build_xlsx.py
└── examples/
    ├── 01-soda-ash-shahe/        # 纯碱：非危化、厂家远/仓库近
    └── 02-caustic-soda-changzhou/# 液碱：危化品、厂家近、罐车
```

## 9. 平台适配

脚本只依赖 **Python 3.9+ 与 openpyxl**，不依赖任何 agent 专有 API；
网络只需 2 个可选端点（OSRM 路径、省界 GeoJSON），失败会降级并标注。
各平台安装方式见 `README.md`。

---

## 10. 常见失败模式（先看这里再动手）

| 现象 | 根因 | 纠正 |
|---|---|---|
| 列表前几名都是 5 公里内的贸易商 | 让距离主导了排序 | 回到 Step 5，先档位后距离 |
| 工厂和仓库混在一起说不清 | 没查交割库公告/仓储官网 | 用 `typeCode` 强制分类 |
| 地址写"某某市某某区" | 不敢查门牌 | 宁可标 `registered` + 缺口 |
| 危化品整块写"请咨询专业人士" | 没做判定 | 查 CAS → 目录 → UN 编号，三分钟能定 |
| 用户说"这个运费差不多 xx 元" | 编了金额 | 立刻删，改为计费口径 |
| HTML 打不开 | 引了 CDN/外链字体 | 模板已内联，禁止加外链 |
