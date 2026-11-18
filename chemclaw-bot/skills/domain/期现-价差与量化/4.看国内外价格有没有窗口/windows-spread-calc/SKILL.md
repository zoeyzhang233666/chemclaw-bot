---
name: windows-spread-calc
description: >
  用「看国内外价格有没有窗口」场景回答：某个化工品/材料在海外市场（FOB/CFR/CIF 某港口）
  的报价，折成中国境内可比成本后，与国内现货价相比是高还是低、这个差在过去一段时间怎么变、
  哪些参数在决定它。触发词：内外价差、进口成本、到岸成本、CFR 折人民币、进口窗口、
  内外盘价差、进口划不划算、海内外价格对比、进口盈亏、倒挂、套利窗口（仅做测算不做建议）。
  产出：自包含交互 HTML 报告（可改汇率/运费/关税/保险/术语并实时重算，含成本瀑布、
  价差曲线、敏感性矩阵、公式抽屉）+ 11 表 Excel 活公式模型。适用于任意化学品，
  不限于乙二醇。
---

# 看国内外价格有没有窗口（windows-spread-calc）

## 这个 Skill 解决什么问题

业务方的原话往往是：「美国/中东/东南亚这个货现在多少钱一吨，折成人民币到中国港口到底多少？
跟国内华东/山东的现货比，是不是有窗口？」

这句话里有四个陷阱，本 Skill 的全部设计都在防它们：

| 陷阱 | 典型错误 | 本 Skill 的做法 |
|---|---|---|
| **口径不齐** | 拿 CFR 美元价 × 汇率，直接减国内含税现货价 | 先折到四层成本（CIF / 含税到岸 / 可抵扣 VAT / 经济成本），再按四个口径分别减 |
| **重复计费** | 报价已是 CFR，却又加了一遍海运费 | 按 Incoterms 自动屏蔽已含费用，参数填了也按 0 计并报警 |
| **伪造历史** | 用今天的运费去算去年的价差 | 历史每一行标注汇率/运费来源（实测 / 月度均值 / 假设），缺失就标 gap，绝不插值 |
| **把价差当利润** | 「价差 500 元/吨，赶紧进口」 | 全文只描述口径差异，不出现交易指令；缺口清单独列影响方向 |

## 硬性规则（不可协商）

1. **不把理论价差称为可实现的套利利润**，不生成任何进口交易指令、下单建议、点价时机。
   报告用 `G1~G4` 四个口径描述差，且每个都注明「只描述口径差异，不是利润」。
2. **口径必须统一**：产品、规格、币种、税基（含税/不含税）、交货地点（送到/出厂/港口）、
   日期。任一不一致就必须显式调整或在缺口里写明。
3. **识别贸易术语已含的费用，防止重复计费**。EXW/FCA/FOB/CFR/CIF/DAP 的包含关系见
   `references/incoterms-matrix.md`；代码里由 `core.check_terms()` 强制拦截。
4. **历史价差只用对应时点可获得的数据**，或明确标记的条件性假设；
   不得用当前运费冒充历史实际成本（`validate.py` 会拦截 3 条以上完全相同的 "actual" 运费）。
5. **缺数据是结论，不是障碍**：每个缺失都必须进缺口清单，写明对结论的影响方向与补齐办法。
6. **每个数字都要有六要素**：数值 · 规格 · 地区 · 含税与否 · 日期 · 来源。

## 七步流程

| 步骤 | 做什么 | 落到的文件/表 |
|---|---|---|
| 1 取报价 | 海外 FOB/CFR/CIF + 国内现货，记录六要素 | `research.json` 的 `overseas` / `domestic` |
| 2 折人民币 | 汇率、海运、保险、关税、其他显式费用 | `research.json` 的 `cost_params` |
| 3 分四层 | 进口到岸 / 税费现金 / 可抵扣 VAT / 可比经济成本 | `core.import_cost()` → Excel「3 成本折算」 |
| 4 算价差 | 当前 G1~G4 + 观察窗口内的变化 | Excel「4 价差四口径」「5 历史序列」 |
| 5 拆驱动 | 海外报价 / 国内价 / 汇率 / 运费 各贡献多少 | Excel「8 归因分解」 |
| 6 做敏感性 | 单参数 + 运费×汇率二维矩阵 | Excel「7 敏感性」 |
| 7 列假设 | 假设、公式、来源、缺口 | Excel「10 缺口与来源」「11 公式表」 |

## 快速开始

```bash
# 0) 准备（只需一次）：把 echarts.min.js 放进 scripts/assets/
#    通常可以从 chem-market-brief Skill 复制：
#    ~/.agents/skills/chem-market-brief/scripts/assets/echarts.min.js

# 1) 复制模板，填成自己的案例
cp research.template.json examples/02-my-product/research.json
#    只需要填 research.json 一个文件：价格、参数、历史序列、来源、缺口

# 2) 一键构建（含自检）
python scripts/build_all.py examples/02-my-product

# 产物
#   examples/02-my-product/output/report.html   ← 交互报告，双击即可看
#   examples/02-my-product/output/model.xlsx    ← Excel 活公式模型
#   examples/02-my-product/build/data.json      ← 唯一事实源，HTML/Excel 都从它来
```

只想重跑某一步：

```bash
python scripts/validate.py  <case>/research.json
python scripts/assemble.py  <case>/research.json --out <case>/build/data.json
python scripts/build_html.py <case>/build/data.json --out <case>/output/report.html
python scripts/build_xlsx.py <case>/build/data.json --out <case>/output/model.xlsx
```

## 脚本清单

| 脚本 | 作用 | 何时单独用 |
|---|---|---|
| `scripts/core.py` | **唯一计算内核**：四层成本、四口径价差、敏感性、归因、术语守卫 | 想在任何 Python 代码里复用公式 |
| `scripts/assets/core.js` | 同上的浏览器镜像（`window.WSC`），与 `core.py` 逐值一致 | 改 HTML 交互逻辑时 |
| `scripts/wio.py` | IO、格式化、禁用词检查 | 写新脚本时 import |
| `scripts/validate.py` | 校验 `research.json`：六要素、术语合法性、重复计费、历史标签 | **填完 research.json 第一件事** |
| `scripts/assemble.py` | `research.json` → `data.json`（含瀑布、归因、敏感性、场景） | 改了案例数据后 |
| `scripts/build_html.py` | `data.json` + 模板 → 自包含 HTML | 改版式/图表时 |
| `scripts/build_xlsx.py` | `data.json` → 11 表 Excel 活公式模型 | 改表结构时 |
| `scripts/build_all.py` | 串起全部步骤 | 日常就用这个 |
| `scripts/selftest.py` | 30 项内核恒等式/边界自检，不依赖外部数据 | 改 `core.py` 后必跑 |
| `scripts/check_consistency.py` | Python ↔ JS 随机参数逐值比对（需 node） | 改任一侧内核后必跑 |
| `scripts/check_package.py` | 占位符残留、外链、体积、工作表齐全性 | 交付前 |
| `scripts/fetch_data.py` | 抓期货日线（新浪）、汇率（ECB）、中间价（CFETS） | 需要补序列时 |

## 数据契约

`research.json` 的字段、必填项、历史序列的标签规则，见
`references/data-contract.md`。核心只有一句话：
**你只需要提供"报价 + 参数 + 观测点"，所有派生数字都由代码算。**

## 报告结构（HTML 十节）

0. 基准时点 KPI（四层成本 + 四口径价差）
1. 交互面板（改参数全页重算）
2. 成本瀑布
3. 历史价差曲线 + 逐点明细表
4. 驱动分解
5. 敏感性（单参数 + 二维矩阵）
6. 口径守卫（术语已含什么）
7. 数据口径（每个数字的六要素）
8. 数据缺口
9. 底层公式与逐项代入
10. 边界与声明

版式与文案规范见 `references/report-structure.md`。

## 适配任意品种

同一套代码可以处理任何「海外报价 vs 国内现货」的组合，只要把变量换成你的：
换 HS 编码与税率、换运费口径、换国内基准地、换纯度/包装系数。

- 普货、有暂定税率、按 FOB 采购 → 见 `references/adapters.md` 的「场景 A」
- 液态散化、按 CFR 到岸、有港杂与罐租 → 「场景 B」
- 固体袋装、按 CIF、有皮重折算 → 「场景 C」

## 参考文档

- `references/import-cost-formulas.md` —— 全部公式的推导与逐项说明（含"为什么保险费这样算"）
- `references/incoterms-matrix.md` —— 术语 × 费用层对照矩阵与常见误配
- `references/data-contract.md` —— research.json 字段规范与历史标签规则
- `references/data-sources.md` —— 各类数据的公开来源、取数口径与坑
- `references/qa-checklist.md` —— 交付前 20 项自检清单
- `references/adapters.md` —— 三类典型场景的参数模板
- `references/report-structure.md` —— HTML 十节的内容与文案规范

## 示例

`examples/01-meg-cfr-china-huadong/` —— 乙二醇 CFR 中国到岸价 vs 华东现货，
27 个对齐观测点，完整走通七步，含真实的缺口清单与免责声明。
它的 `research.json` 是本 Skill 的最佳母本：看不懂字段时，照抄结构改内容即可。

## 常见错误

| 症状 | 原因 | 处理 |
|---|---|---|
| 报告里 CIF = 0 | `cost_params.ocean_freight` 未填或术语写成 CIF 又填运费 | 看第 6 节的冲突提示 |
| HTML 打开是白屏 | `scripts/assets/echarts.min.js` 没放（build_html 会报错） | 见"快速开始"第 0 步 |
| Excel 与 HTML 数字不同 | 改了 `core.py` 没同步 `core.js` | 跑 `check_consistency.py` |
| validate 报"禁用表述" | 文案里出现了交易类词汇 | 改写成描述性表述；否定句（"不给出…指令"）会被放行 |
| 历史曲线断点很多 | 汇率超过 `fx_max_stale_days` 视为缺失 | 补汇率数据，**不要**放宽阈值硬凑 |
