---
name: chemical-supply-market-map
description: Use when a procurement or sourcing team needs a supply-market landscape for any chemical product — who makes it, where, with what capacity and process route, what is under construction, where prices have been, and what that means for buying — 供应市场全景 / 采购视角研究 / 供应商格局 / 产能分布 / 集中度与区域结构 / 新建在建项目 / 价格区间与波动 / 断供风险 / supply market landscape / procurement market study / supplier landscape / capacity map / buying strategy for a chemical. Product-agnostic: works for 纯碱、烧碱、PVC、尿素、甲醇、钛白粉、碳酸锂、PTA、黄磷… and delivers a self-contained HTML plus a 16-sheet Excel workbook in which every figure carries a source and every missing figure is marked as a gap, never estimated.
license: MIT
---

# 化工品供应市场全景（采购视角）

> 一句话：把「这个品种谁能供、在哪里供、用什么工艺供、未来两年多出来多少、价格在什么位置、采购该担心什么」做成一张可交互的全景图 + 一本可追溯的数据包。

本技能**不含任何具体产品的数据**。所有产品差异都在项目配置里（`project.json` + 三个 JSON 数据文件），
脚本只负责结构、计算与呈现。换产品 = 换配置，复制 `examples/` 里任一目录改名即可。

## 何时加载

用户提出以下任一诉求时使用：

- 「帮我做 XX（化工品）的供应格局 / 供应市场全景 / 产能地图」
- 「采购视角看 XX：谁在供、集中在哪、未来两年新增多少、价格什么位置」
- 「XX 有哪些主要生产企业、产能多少、集中在哪些省」
- 「XX 的断供风险 / 单源依赖 / 区域集中」相关的研究
- English: "supply market landscape for X", "who produces X in China", "procurement risk map for X"

**不适用**：单点价格查询与行情快评（用 `chem-market-brief`）；找下游客户（用 `b2b-lead-sourcing`）；
区域拜访路线（用 `chemical-region-market-map`）。

## 输入（缺什么就问，一次问清）

| 项 | 必需 | 说明 |
|---|---|---|
| 产品 | ✅ | 全名 + 简称 + CAS；有规格等级（液碱/片碱、重碱/轻碱）必须写明 |
| 地域范围 | ✅ | 具体国家/区域，不接受「全球」；默认中国大陆 |
| 基准年 | ✅ | 通常是上一个完整年度 |
| 采购方信息 | 可选 | 年用量、到厂价、运费、库存天数；没有就用默认模拟值并标注 |
| 交付物 | 隐含 | HTML + Excel 双交付；用户没特别说就按默认 |

启动时用一次 `ask_user_question` 问全，带推荐项。

## 六段分析框架（每一步都有完成判据）

| # | 模块 | 要回答的问题 | 完成判据（不满足不进入下一步） |
|---|---|---|---|
| 1 | 供给端产能 | 谁在产、产多少、什么口径 | `plants.json` ≥10 条基地/≥5 个集团；全国产能有来源 |
| 2 | 区域结构 | 集中在哪些省、贸易活跃度 | 每个省有产能合计；贸易活跃度 A/B/C 有标注 |
| 3 | 工艺路线 | 哪几条路线、原料依赖、成本带 | 每条路线有产能、原料单耗、成本区间 |
| 4 | 新增项目 | 未来 1–2 年多出来多少（**净**） | 每个项目有类型/时间/净影响；置换必须扣减 |
| 5 | 价格 | 历史区间、周期位置、区域价差 | 至少 4 年年度数据 + 当前价 + 区域价差 |
| 6 | 采购关注 | 集中度、单源、区域、政策风险 | ≥5 项风险，每项有证据 + 可执行动作 |

## 五道 gate（每一道不过就不交付）

1. **口径 gate**：全国产能/产量出现多套公开数字时，**并列展示，不取平均**；在 `scope.basis_notes` 与
   `metrics.*_note` 里写清来源与时点。
2. **缺口 gate**：任何拿不到的数字写「数据缺口」，并在 `gaps` 里登记「影响 / 现状 / 补齐方式 / 优先级」。
   **禁止**用行业均值、邻近年份、比例外推的方式补。
3. **净增 gate**：置换、搬迁、技改项目的产能不能直接算作新增；`capacity_retired` 必须填，
   净影响无法确认就填 `net: null`，报告里显示「待确认」且不进基准预测。
4. **来源 gate**：`plants[].source` 与 `sources[]` 必须对得上；没有来源的基地标「未核实」，
   不作唯一依据。
5. **集中度 gate**：CR5 与 HHI 必须注明是「样本口径」还是「全国口径」；样本覆盖率 <70% 时
   必须在报告里显著提示「集中度可能被低估」。

## 十步工作流

```bash
# 0. 建项目（目录名随意，建议 <产品>-<地域>-<年>）
python scripts/new_project.py --dir work/soda-ash-cn-2026 \
    --product "纯碱（碳酸钠，Na₂CO₃）" --short 纯碱 --cas 497-19-8 \
    --grades "重质/轻质" --year 2025 --forward 2026,2028
```

1. **定契约**：品类、地域、基准年、采购方参数、交付物。写进 `project.json` 的 `product/scope/buyer`。
2. **探通道**：确认本次能用哪些证据源（年报/公告/协会/价格机构/海关），每级实测一次，记进 `采集说明.md`。
   详见 `references/evidence-channels.md`。
3. **定口径**：先查「全国产能有几种说法」，写进 `metrics.capacity_total` 与 `basis_notes`。
   口径打架是这类研究最常见的翻车点。
4. **铺产能**：`plants.json` 一条 = 一个基地。先做 5 条跑通管线，再批量补到 20–40 条。
   **每条必须有 `source`**（S 编号）。
5. **补画像**：`companies.json` 一个集团一条。没有公开画像的集团可以留空——抽屉会退化显示
   基地汇总，不会编造。
6. **项目与净增**：`projects.json`。`type` 区分 新建/扩建/技改/置换/搬迁/退出；
   置换填 `capacity_retired`；不确定填 `net: null`。
7. **价格与策略**：`project.json.prices` + `markets` + `strategies` + `supplier_mix`。
8. **体检**：`python scripts/build_all.py --dir <项目> --check` —— 看错误与警告。
9. **出表出图**：`python scripts/build_all.py --dir <项目>` —— 同时产出 HTML 与 xlsx。
10. **交付前终检**：`python scripts/check_project.py --dir <项目>`，有子代理/浏览器时再跑
    `python scripts/ui_check.py --html <报告.html>`；最后按 `references/delivery-checklist.md` 口述四块。

## 固定交付结构（不许自由发挥）

**HTML（单文件，零外部依赖，可离线打开、可打印成 PDF）**：6 个标签页

| # | 标签 | 内容 |
|---|---|---|
| 01 | 全景 | KPI 条 + 工艺环形图 + 区域条形 + 成本带 + 头部集团对比 + 核心结论卡 |
| 02 | 企业表 | 可搜索/排序的集团表，点击行 → 右侧抽屉：基地明细、优势/风险、采购判断、尽调问题 |
| 03 | 项目时间线 | 按年份分组，点击项目 → 抽屉：毛产能/置换/净影响/进度/对供给的影响 |
| 04 | 价格 | 年度折线 + 当前价位卡 + 区域价差 + 阶段复盘表 + 情景判断 |
| 05 | 采购关注 | 风险卡（按等级排序）+ 策略卡 + 建议供应商组合 + 采购量测算 |
| 06 | 数据与来源 | 口径说明、口径提示、数据缺口表、来源列表（可点击）、使用限制 |

**Excel（16 张表，顺序固定）**：`00_封面` `01_核心结论` `02_企业产能` `03_区域汇总` `04_工艺路线`
`04A_原料与成本` `05_新增项目` `05A_净增还原` `06_价格历史` `06A_价格周期` `07_采购关注`
`07A_采购策略` `08_尽调清单` `09_供应商评分` `10_数据缺口` `11_来源与口径`。
含 5 个原生图表、冻结窗格、筛选、数据校验、数据条、横向打印区域。

细节见 `references/output-structure.md`。

## 产物与文件布局

```
work/<项目>/
├── project.json      ← 唯一事实来源（品类/口径/指标/工艺/策略/风险/缺口/尽调/评分/来源）
├── plants.json       ← 基地级产能（所有汇总从这张表算）
├── companies.json    ← 集团画像（抽屉里的尽调卡）
├── projects.json     ← 项目表（时间线与净增还原）
├── data_bundle.json  ← 渲染用中间件（自动生成，便于排查）
├── <产品>供应格局全景_<年>.html
└── <产品>供应格局数据包_<年>.xlsx
```

## 口径纪律（写进每一份交付物）

- 产能 = **名义/设计能力**，≠ 可售量，≠ 产量。三者分开写。
- 集团产能 = 合并口径；基地产能 = 单一工厂口径。不要混加。
- 样本合计 ≠ 全国产能。样本覆盖率必须写出来。
- 毛新增 ≠ 净新增 ≠ 实际可增量（爬坡打折）。
- 价格必须带：日期、规格、地区、含税/不含税、折百与否。

`references/data-gaps.md` 给了完整的「什么算缺口、怎么写、怎么补」规则。

## 环境适配

| 环境 | 最低要求 | 无网络的降级方案 |
|---|---|---|
| 任意 Python 3.8+ | 标准库即可出 HTML | 依赖模型知识 + 用户材料，缺口如实登记 |
| + `openpyxl` | 出 Excel | 只交付 HTML，并在交付说明里写明 |
| + `playwright` | 自动点一遍 HTML | 人工打开检查 |
| 有子代理 | lane 并行采集 | 串行，减少 lane 数 |

产品无关性由三点保证：① 脚本里没有产品名；② 地图类组件的缺失不影响交付（删掉对应片段即可）；
③ 所有枚举、单位、颜色都来自配置。

各 agent 的安装与接入方式见 `references/porting-to-other-agents.md`。

## 参考文件（按需读，不要一次全读）

| 文件 | 什么时候读 |
|---|---|
| `references/workflow.md` | 开始一个项目时 |
| `references/data-model.md` | 写 `project.json` 与三个 JSON 时（字段全表） |
| `references/metrics-formulas.md` | 算 CR5/HHI/覆盖率/净增/成本分位时 |
| `references/data-gaps.md` | 遇到拿不到的数字时 |
| `references/procurement-framework.md` | 写风险、策略、尽调、评分时 |
| `references/output-structure.md` | 要知道每张表/每个标签放什么时 |
| `references/evidence-channels.md` | 找证据时 |
| `references/delivery-checklist.md` | 交付前逐条过 |
| `references/failure-log.md` | 出错时先查这里 |
| `references/porting-to-other-agents.md` | 装到 chemclaw / workbuddy / codex 时 |

## 示例

- `examples/soda-ash-cn-2026/` —— 完整示例（纯碱，32 基地 / 24 集团 / 9 项目 / 30 来源，
  交付物已生成，可直接打开对照）
- `examples/caustic-soda-cn-2026/` —— 精简示例（烧碱，8 基地 / 5 项目 / 3 来源，含无 URL 的
  来源占位，演示「数据不全时报告长什么样」）

两个示例用**同一套脚本**生成，证明换产品只需换配置。
