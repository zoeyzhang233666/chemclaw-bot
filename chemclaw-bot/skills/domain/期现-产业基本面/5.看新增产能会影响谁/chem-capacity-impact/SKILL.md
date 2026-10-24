---
name: chem-capacity-impact
description: 用于回答「某企业/项目计划新增某产品的设计产能，会影响谁」这类产业基本面问题——核实项目事实（业主、地点、产能、工艺、阶段、投产时间），算新增产能占全国/区域/竞争半径的比，按单耗推上游原料需求，按投产月份与爬坡算首年与稳态产量，再识别受影响的上游、同区域同行、下游与物流主体。适用于聚丙烯、乙烯、PX、PTA、甲醇、烧碱、纯碱、尿素等任一可界定产能与工艺路线的化工品。触发词：新增产能会影响谁 / 新建装置影响 / 扩产影响分析 / 投产影响测算 / 产能占比 / 原料需求测算 / capacity impact / 谁受影响。产出单文件交互式 HTML 报告与 13 表 Excel 计算工作簿。
---

# 看新增产能会影响谁

## 这个技能在做什么

产业基本面研究里最常见的一类问题：

> 「某公司计划新增 XX 万吨 YY 产能，会在什么时候、以多大体量、影响哪些主体？」

这个问题有**四个陷阱**，本技能的整套结构就是围绕这四点设计的：

| 陷阱 | 错误做法 | 本技能的做法 |
|---|---|---|
| **拿设计产能当首年产量** | 40 万吨项目 → 写"新增供给 40 万吨" | 按投产月份 + 爬坡曲线逐月积分，首年可能只有 8.7 万吨 |
| **只算全国占比** | 40/4916 = 0.81% → "影响可以忽略" | 同时算区域（2.64%）与竞争半径（5.16%），结论可能反转 |
| **忽略分母口径** | 华东产能用 1,513 还是 994 万吨？ | 两套口径并列，各算一次，标出差异 |
| **预测价格方向** | "供给增加 → 价格下跌" | 只给量级、机制、可观测指标 |

## 工作流（9 步，与报告章节一一对应）

```
① 事实核验    →  七项必核字段 + 证据等级 E1–E5，任一关键字段 E5 则结论降级
② 相对规模    →  六组分母（全国/区域/半径/牌号/消费量/在建），每组给档位而非仅百分比
③ 原料需求    →  沿工艺链连乘单耗，单耗带依据等级 C1–C4 与区间
④ 产量情景    →  投产月份 × 开工率 × 爬坡曲线，输出首年/稳态/上限
⑤ 参数计算器  →  交互式改写假设，实时重算
⑥ 影响路径    →  产业链图 + 受影响对象打分（体量/传导/时滞/证据）
⑦ 区域格局    →  自给率、供给增量、竞争半径为内的同行梯度
⑧ 三类结论    →  事实 / 计算 / 情景，物理分离
⑨ 待核实      →  每条缺口写明影响哪一步、怎么补、优先级
```

## 快速开始

```bash
# 1. 准备数据（照抄 examples/_skeleton/project.json 的结构）
cp -r examples/_skeleton my-project
# 2. 编辑 my-project/project.json
# 3. 一键构建（校验 → 计算 → Excel → HTML → 自检）
python scripts/build_all.py my-project
# 产物在 my-project/output/ 与 my-project/build/data.json
```

单独跑各步：

```bash
python scripts/validate.py  my-project/project.json          # 口径校验
python scripts/compute.py   my-project/project.json --summary # 看关键数字
python scripts/build_xlsx.py my-project/project.json --out out.xlsx
python scripts/build_html.py my-project/project.json --out out.html
python scripts/check.py     my-project/project.json --xlsx out.xlsx --html out.html
```

只依赖标准库 + `openpyxl`（生成 Excel 用）+ 内联的 ECharts（无网络依赖）。

## 关键定义（必须统一，否则数字不可比）

- **设计产能**：公称能力（吨/年或万吨/年），存 `project.design_capacity_t`，**一律存吨**，展示时折算万吨。
- **首年产量**：自开车月到当年 12 月的累计产量，**不是**设计产能。
  `首年产量 = Σ_{k=1..(12-m+1)} 设计产能/12 × 稳定开工率 × f_ramp(k)`
- **稳态产量**：`设计产能 × 稳定开工率`。
- **上限产量**：`设计产能 × 100%`，仅作校验，**永不作为结论**。
- **占比**：分子为设计产能，分母为该口径**现有产能**（绑定年份与边界）。
- **档位词汇**（不可自创）：
  - 全国/消费量分母：`可以忽略 <1%` / `边际 1–3%` / `显著 3–8%` / `结构性 >8%`
  - 区域/竞争半径分母：`温和 <5%` / `明显 5–15%` / `重大 15–30%` / `洗牌级 >30%`
- **影响强度**：`100 × (0.35·体量̂ + 0.25·传导 + 0.20·时滞 + 0.20·证据)`，其中 `体量̂ = min(1, log10(1+100·体量占比))`；
  档位 `高 ≥70 / 中 45–70 / 低 <45`。

## 证据分级

| 级 | 含义 | 典型来源 |
|---|---|---|
| E1 | 一手官方 | 环评报告书、竣工环保验收、备案证、交易所公告、统计年鉴 |
| E2 | 行业权威 | 行业媒体（隆众/卓创/金联创）、协会、交易所规则 |
| E3 | 综合媒体 | 财经媒体、企业新闻稿转载 |
| E4 | 机构口径 | 咨询机构估算、券商研报 |
| E5 | 待确认 | 无来源、仅口头、模拟输入 |

单耗另加**依据等级**：`C1 工程值`（环评/可研）＞ `C2 区间中值` ＞ `C3 化学计量下限` ＞ `C4 情景假设`。
**环评报告书的"原辅料消耗表"是最高性价比的单耗来源**——它同时给出设计值与年耗量，可反算准确单耗。

## 三条铁律

1. **不把设计产能当首年产量。** 报告必须同时给出首年、稳态、上限三个数，并说明倍数差。
2. **不预测价格方向。** 只给量级、机制与可观测指标。见 `references/no-forecast-policy.md`。
3. **缺数就写缺口。** 查不到就进 `gaps`，标明影响哪一步计算与补齐路径，**绝不编造行业均值**。

## 模拟输入的强制要求

当项目为研究用模拟（如"某 40 万吨 PP 项目"）时：

- `meta.simulated: true` + `meta.simulated_note`（说明哪些是模拟、哪些是真实背景数据）
- 业主名必须用中性占位（`某化工新材料有限公司`），**绝不使用真实上市公司名**
- HTML 顶部橙色横幅、Excel `00` 表红底提示
- 回复用户时明确说明"主体与进度为模拟，非真实项目"
- 但**单耗、分母、区域结构、价格等背景数据仍必须取真实公开来源并标日期**

## 文件结构

```
chem-capacity-impact/
├── SKILL.md
├── README.md
├── references/
│   ├── project-verification.md    ① 七项必核字段与证据等级
│   ├── capacity-share.md          ② 六组分母与档位词汇
│   ├── raw-material-demand.md     ③ 单耗连乘与依据等级
│   ├── production-scenarios.md    ④ 爬坡模型与首年产量
│   ├── impact-pathway.md          ⑥ 影响强度打分与主体识别
│   ├── adapters.md                换产品时怎么改（乙烯/PX/甲醇/纯碱…）
│   ├── data-contract.md           project.json 完整字段说明
│   ├── presentation-spec.md       HTML/Excel 呈现规范
│   ├── no-forecast-policy.md      禁用词与改写表
│   └── qa-checklist.md            交付前自检清单
├── scripts/
│   ├── build_all.py               一键流水线
│   ├── validate.py                口径校验（可独立跑）
│   ├── compute.py                 计算引擎（可独立跑 CLI）
│   ├── build_xlsx.py              13 表工作簿
│   ├── build_html.py              单文件 HTML
│   ├── check.py                   结构自检
│   ├── templates/report.html      HTML 模板（改样式只动这里）
│   └── assets/echarts.min.js      内联图表库
└── examples/
    ├── _skeleton/                 填空骨架
    └── 01-pp-pdh-40wt-sim/        完整范例：40 万吨/年 PDH-PP（模拟项目）
```

## 换一个产品怎么做

不改代码，只改 `project.json`。要点：

1. **`chain.nodes/edges`**：把工艺链画出来，每条"原料→装置"边挂 `unit_key`。
2. **`unit_consumption`**：每个 `unit_key` 一条，填 `value` / `range` / `purity` / `on_site` / `evidence`。
   优先找**环评报告书的原辅料消耗表**（E1 + C1）。
3. **`capacity_bases`**：六个 `key` 固定（`national`/`regional`/`radius`/`grade`/`consumption`/`pipeline`），
   查不到就把 `value_t` 留 0 —— 报告会自动把它渲染成"分母缺失，无法计算"，而不是报错。
4. **`stakeholders`**：按 `upstream`/`competitor`/`downstream`/`logistics`/`byproduct` 分类填，
   每条给 `impact_basis`（`transmission`/`lag`/`volume_basis_t`/`market_t`）。

详见 `references/adapters.md`。

## 不要做的事

- ❌ 把 `capacity_t` 直接写成"当年新增供给"
- ❌ 用产量、开工率、表观消费单一指标代替产能做分母
- ❌ 在没有环评/公告时给出确定性结论（应降级为情景）
- ❌ 编造运费、库存、区域需求等查不到的中间参数
- ❌ 输出"涨/跌/利多/利空/看涨/看跌"等方向性判断
- ❌ 在模拟项目里使用真实上市公司名作为业主
