---
name: chem-chain-map
description: 以一个化工/材料品种为中心，向上展开 2 层主要原料与中间体、向下展开 2 层主要下游产品与终端应用，产出「可追溯证据的节点关系表 + 自包含交互式 HTML 产业链知识图谱 + 多 sheet Excel 研究工作簿」。适用于任何化工品（SBS、聚丙烯、PTA、钛白粉、纯碱、乙烯、DOP…），层数、工艺路线、支链均可按需调整。当用户说「看一个品种的产业链图 / 产业链图谱 / 上下游关系图 / 产业链梳理 / 品种研究地图 / 产业基本面研究 / 供应链地图」时使用。
---

# 化学品产业链知识图谱（chem-chain-map）

## 这个 Skill 解决什么问题

给一个品种，输出三样东西，**全部由同一份结构化数据驱动**：

| 产物 | 内容 | 用途 |
|---|---|---|
| `data/*.json` | 节点表、关系表、工艺参数、价格、企业产能、项目事件、证据来源、覆盖清单、禁用边 | 唯一事实源；任何结论都能回溯 |
| `*.html` | 自包含交互图谱（缩放/拖拽/展开/搜索/工艺筛选/上下游高亮/价格联动/层级表兜底） | 给业务方看、讲解、做研究导航 |
| `*.xlsx` | 12 个 sheet：节点、关系、工艺参数、价格、企业产能、项目事件、证据、覆盖、缺口、禁用边、对账 | 给研究员查、复核、交付 |

**核心约束（违反即视为交付失败）**

1. **不得为了图形完整而虚构关系**。宁可图上一个缺口，也不能画一条自己都说不清证据的线。
2. **必须区分节点类别**：`commodity`（化学品，可验证 CAS）/ `material`（配方材料、制品）/ `application`（终端应用）。材料与终端**没有单一 CAS**，不得编造。
3. **必须区分关系类型**：原料转化 ≠ 联产 ≠ 副产 ≠ 配方共混 ≠ 成型加工 ≠ 终端应用 ≠ 替代 ≠ 工艺路线。**不得把所有连接都画成"上下游"**。
4. **终端用途不能写成化学转化产品**。`SBS → 鞋` 是错的，必须是 `SBS →(配方共混) TPR 鞋底料 →(成型加工) 鞋底 →(终端应用) 鞋`。
5. **不同工艺不能混成一条链**。乙苯脱氢制苯乙烯与 C8 抽提制苯乙烯必须分成两条路线分别登记。
6. **单耗必须带口径**：化学计量 / 工业级（注明基准）/ 配方比（每 100 份）三选一。没口径就不许给数字。
7. **缺失 ≠ 0**。缺价格、缺产能、缺参数一律显式登记为缺口，**不估算、不插值、不外推**。
8. **覆盖完整度只对预冻结的核心清单有效**，不能声称"覆盖了整个产业链"。

---

## 执行流程（7 步）

### 第 1 步：锁定研究对象与参数

先问清（或从用户话里提取）5 个参数，缺的按默认值并在产物里注明：

| 参数 | 默认 | 说明 |
|---|---|---|
| `product` | 用户给定 | 目标品种；给出全名、别名、CAS、规格（牌号/纯度） |
| `up_depth` / `down_depth` | 2 / 2 | 向上、向下展开层数。图谱会多画 1~2 列"延长线"以让原料路线可辨认，**延长线不计入覆盖清单** |
| `routes` | 主流路线 + 明确的并列路线 | 例如 SBS 苯乙烯段有"乙苯脱氢"与"C8 抽提"两条 |
| `branches` | 全部主要下游 | 只做指定支链时，其余支链登记为"未覆盖"而非删除 |
| `show_price / show_enterprise / show_project / show_event` | 全 true | 关掉的项要在图谱与 Excel 里显式标注"按需求关闭" |

**品种身份核验**：CAS 必须是 `verified`（查得到权威来源）或 `不适用`（材料/终端）。填了 CAS 却没有来源的，一律标 `unverified` 并在缺口清单登记。

### 第 2 步：冻结核心清单（**动手画图之前**）

写 `data/core_checklist.json`，把"这一版必须覆盖到什么程度"先钉死：

- `core_nodes`：目标品种、直接原料、关键中间体、主要下游配方材料、终端应用、主要替代品。每项给 `priority`（P0/P1/P2）与 `required_criteria`。
- `core_relations`：产品骨架上的必经边（原料→产品、产品→主要下游、主导应用→终端）。
- `meta.scope_statement`：**明确写出不覆盖什么**（新兴应用、替代路线、牌号清单、贸易流…）。
- `meta.criteria_definitions`：每个判定词的含义（`node_present` / `identity_verified` / `role_classified` / `evidence_linked` / `price_mapped` / `direction_verified` / `quant_available`）。

覆盖率 = 通过的核心条目 / 冻结的核心条目。**先把清单冻结，再去补数据**，这样覆盖率才是对自己诚实，而不是事后挑容易的算。

> 反模式：先画完图，再倒推一份"恰好都能通过"的清单。这等于自证清白。

### 第 3 步：建立节点与关系（数据契约见 `references/03-data-contract.md`）

依次写：`meta.json` → `nodes.json` → `relations.json` → `processes.json` → `sources.json`，
再补 `prices_verified.json`、`enterprises.json`、`projects.json`、`events.json`、
`forbidden_links.json`、`core_checklist.json`。

**每写一条关系，问自己三句**：
1. 这是同一物质的变化（conversion），还是两个东西一起出来（coproduction/byproduct），还是物理混合（blend），还是成型（processing），还是用途（application），还是市场替代（substitution），还是并列路线（route_option）？
2. 方向从哪到哪？上游的 `column` 是否严格小于下游？
3. 有数字吗？有口径吗？没有的话，我写了 `missing` 吗？

**同时写 `forbidden_links.json`**：把这条链上最容易被画错的边登记成禁用项（例：`SBS → 鞋`、`SBS → 公路`、`纯苯 → 苯乙烯`、`TPR → SBS`）。校验器会对这些边直接 FATAL。

### 第 4 步：抓价格与核实产能

- 价格：每抓一条序列，记录 `规格 / 区域 / 含税口径 / 基准日期 / 来源 id`；不同口径的序列**不合并、不平均**。
- 产能：只登记有来源的条目，注明口径（SBS 单产品、还是 SBC 合计）。合计只统计已核验条目，**不得表述为行业总产能**。
- 抓不到就登记缺口，写清"为什么抓不到 + 到哪里能补"（付费库、企业挂牌价、协会月报）。

详见 `references/04-evidence-and-verification.md`。

### 第 5 步：校验（不过不放行）

```bash
python tools/check_schema.py --data-dir examples/sbs/data    # JSON 契约
python tools/validate_chain.py --data-dir examples/sbs/data  # 业务规则 + 覆盖率
```

`check_schema.py` 查字段契约（必填、类型、枚举）。
`validate_chain.py` 查业务规则：外键/证据/禁用边/节点类别/量化口径/有向环/列单调性/**布局几何**（重叠、越界、连线穿节点、斜线段）。

- FATAL → 必须修数据，不许绕过。
- WARN → 记进缺口清单，在交付物里说明。

### 第 6 步：生成 HTML 与 Excel

```bash
python tools/build_chain_html.py --data-dir examples/sbs/data --out out/sbs_chain.html
python tools/build_chain_xlsx.py --data-dir examples/sbs/data --out out/sbs_chain.xlsx
```

坐标由 `tools/chain_layout.py` 在 Python 端预先算好并注入，浏览器只负责绘制与交互。
**布局质量是可测的**，不是靠肉眼：布局自检不过时 HTML 会自动降级为「层级关系表」视图，节点与证据一条不丢。

### 第 7 步：交付前自检

```bash
python tools/verify_html.py out/sbs_chain.html       # 34 项交互与渲染断言
```

再过一遍 `references/06-qa-checklist.md`。

---

## 交互式图谱能做什么（交付给业务方的部分）

| 交互 | 行为 |
|---|---|
| 点击节点 | 侧栏显示：身份（CAS/规格/别名）、价格走势与样本点、主要企业与公开产能、相关项目、产业事件、相邻关系、证据来源与关键原文 |
| 点击连线 | 侧栏显示：关系类型、工艺描述、单耗数值与单位、量化状态、**计算口径**、单耗来源证据 |
| 节点悬停 | 上游血缘高亮（蓝）／下游血缘高亮（绿）／无关节点变暗 |
| 缩放 / 拖拽 | 滚轮缩放、按住空白拖拽；「适应」按可读比例聚焦目标品种，「总览」整图入屏 |
| 搜索 | 按名称/别名/CAS 过滤，下拉直达节点并居中 |
| 工艺筛选 | 按关系类型 chip 或下拉按关系类型 / 工艺族过滤，非相关边淡出 |
| 价格联动 | Ctrl/⌘ 多选两个节点 → 并排价格曲线 + 共同交易日 + 对数价格相关系数（**明确标注样本量不足，不作因果结论**） |
| 层级表 | 一键切到表格视图：层级/节点/类别/CAS/上游/下游/缺口/证据，可点击回图谱 |
| 覆盖面板 | 顶部仪表盘展示覆盖率、核心节点/关系通过数、未达标项清单与口径说明，可折叠 |

---

## 目录结构

```
chem-chain-map/
├── SKILL.md                      ← 本文（Agent 入口）
├── README.md                     ← 人读的快速上手与设计说明
├── references/
│   ├── 01-method.md              产业链拆解方法：怎么定层数、怎么选节点、怎么判关系
│   ├── 02-relation-taxonomy.md   9 类关系的判定标准与常见误判
│   ├── 03-data-contract.md       全部 JSON 字段契约与最小示例
│   ├── 04-evidence-and-verification.md  证据分级、核验动作、抓价策略
│   ├── 05-layout-and-rendering.md 布局规则、走线规则、几何自检指标
│   ├── 06-qa-checklist.md        交付前逐项检查表
│   └── 07-new-product-playbook.md 换一个品种时的操作清单（含选品与参数）
├── examples/
│   ├── sbs/                      完整实例（36 节点 / 48 关系 / 25 来源，含成品 HTML + XLSX）
│   └── minimal/                  与品种无关的最小模板（8 节点，演示数据契约）
├── tools/
│   ├── chain_layout.py           布局引擎（Python 端预算坐标 + 几何自检）
│   ├── check_schema.py           JSON Schema 契约校验
│   ├── validate_chain.py         业务校验 + 覆盖率
│   ├── build_chain_html.py       HTML 生成
│   ├── build_chain_xlsx.py       Excel 生成
│   ├── verify_html.py            浏览器端 34 项交互断言（Playwright）
│   ├── fetch_prices.py           公开价格抓取（可换数据源）
│   └── run_all.py                一键：schema → 校验 → HTML → XLSX → 自检
└── assets/
    ├── chain.html.tpl            页面骨架
    ├── chain.css                 深色专业主题
    ├── chain_graph.js            绘制与交互运行时
    └── schemas/*.schema.json     JSON Schema（供编辑器/CI 校验）
```

---

## 换一个品种要做的事

1. 复制 `examples/minimal/data` 到新目录，改 `meta.json` 的 `product`。
2. 按第 1 步填参数，按第 2 步冻结核心清单。
3. 填节点与关系（先骨架 20~40 个节点，别一上来铺 200 个）。
4. 跑 `validate_chain.py`，把 FATAL 清零、WARN 登记进缺口。
5. 生成 HTML + XLSX，跑 `verify_html.py`。
6. 按 `references/07-new-product-playbook.md` 复核。

**层数与列号无关**：`column` 是图谱列号，缺列是正常的（没有节点落在那一层）。层数一致性只由「物质流边的 column 严格递增」来保证，由校验器检查。

---

## 常见失败模式（本 Skill 专门防的）

| 失败模式 | 后果 | 本 Skill 的对策 |
|---|---|---|
| 把所有连接画成上下级箭头 | 读者以为副产、配方、终端都是一回事 | 9 类关系 + 不同线型/颜色 |
| 把终端用途写成转化产品 | 单耗链条被污染，成本模型算错 | `forbidden_links` 硬拦截（FATAL） |
| 两条工艺路线画成一条 | 单耗互相污染，价格传导结论错 | 并列路线独立登记 + `typical` 标记 |
| 单耗没有口径 | 数字看起来精确，实际不可比 | 三选一口径 + `basis_grade` 必填 |
| 缺口悄悄填上估算值 | 结论建立在虚构数据上 | `missing` 状态 + 缺口清单 + 覆盖率扣分 |
| 覆盖率虚报 | 让人误以为已经研究透了 | 预冻结清单 + 范围声明 + 分母可见 |
| 图画歪了/线穿节点 | 读者看不懂，交付物失去价值 | 布局几何自检 + 自动降级层级表 |

---

## 依赖

- Python 3.9+、`openpyxl`（Excel）、`playwright`（可选，仅自检用）
- 生成的 HTML **无任何外部依赖**：CSS/JS/SVG 全内联，离线可开、可发邮件附件

详细方法请读 `references/01-method.md`；字段细节读 `references/03-data-contract.md`。
