# chem-import-window · 进口窗口判断

判断某化工品从海外进口到中国**当前有没有进口窗口**：把海外 FOB/CFR/CIF 报价折算成中国到岸含税成本，与国内同规格、同交货地、同税基的现货价对齐后算价差，并给出历史序列、敏感性、归因，同时**明确区分理论价差与可执行贸易利润**。

> 只是一个"把两种价格语言对齐"的计算与取证工具。**不预测价格，不给交易指令。**

## 目录结构

```
chem-import-window/
├── SKILL.md                       技能主文档（触发条件、工作流、红线）
├── README.md                      本文件
├── references/                    7 份方法论文档
│   ├── comparability.md               内外盘可比性 9 项检查
│   ├── cost-formulas.md               折算公式全集
│   ├── incoterms.md                   贸易术语转换矩阵
│   ├── tax-and-vat.md                 关税/暂定税率/进口增值税/抵扣
│   ├── history-alignment.md           历史序列对齐（同日配对、不插值）
│   ├── sensitivity-and-attribution.md 敏感性与归因
│   ├── no-forecast-policy.md          不预测/不指令的表述边界
│   ├── qa-checklist.md                交付前自检清单
│   └── data-sources-cn.md             国内数据源检索路径与坑
├── schema/data.schema.json        案例数据契约
├── scripts/
│   ├── lib/import-window-engine.js   ★ 单一计算真源（HTML/Excel/校验共用）
│   ├── assets/template.html          看板模板
│   ├── assets/echarts.min.js         内联图表库（Apache-2.0）
│   ├── validate.js                   数据契约 + 禁用词校验
│   ├── cross_check.js                三路交叉校验（JS vs Python 基准，360 场景）
│   ├── reference_calc.py             Python 独立基准实现
│   ├── build_html.cjs                生成单文件离线 HTML
│   ├── build_xlsx.py                 生成 10 页活公式 Excel
│   ├── check_xlsx.py                 LibreOffice 重算 + 活公式验证
│   ├── qa_render.py                  页面数字 vs 引擎 + 交互 QA
│   ├── qa_layout.py                  版面/溢出/响应式 QA
│   └── selftest.py                   一键全量自检
└── examples/
    ├── 00-template/                  最小骨架（换品种即可跑）
    ├── 01-meg-huadong/               ★ 完整示例：中国华东进口乙二醇
    └── 02-fob-no-freight/            降级示例：FOB 缺运费 → 正确地算不出来
```

## 快速运行

```bash
# 一键自检（跑全部示例的全部检查）
python scripts/selftest.py

# 生成看板
node scripts/build_html.cjs examples/01-meg-huadong/data/case.json out.html

# 生成 Excel
node -e "const e=require('./scripts/lib/import-window-engine.js'),fs=require('fs');const a=e.analyze(JSON.parse(fs.readFileSync('examples/01-meg-huadong/data/case.json','utf8')));fs.writeFileSync('eng.json',JSON.stringify({cif_cny:a.current.totals.cif_cny,duty:a.current.totals.duty,vat:a.current.totals.vat,cost:a.current.totals.net_cost,spread:a.current.spread.abs_cny}))"
python scripts/build_xlsx.py examples/01-meg-huadong/data/case.json out.xlsx --engine-json eng.json
```

## 三路交叉校验

同一个公式由三套独立实现计算，必须一致：

| 实现 | 位置 | 用途 |
|---|---|---|
| JS 引擎 | `scripts/lib/import-window-engine.js` | 生成 HTML / 页面交互重算 |
| Python 基准 | `scripts/reference_calc.py` | 独立复算，防止 JS 算错 |
| Excel 公式 | `build_xlsx.py` 生成 | 让用户在 Excel 里自己改参数 |

`cross_check.js` 会用 **360 个参数组合**（FOB/CFR/CIF × 5 档运费 × 4 档关税 × 3 档汇率 × 2 档抵扣）逐一对齐，任何不一致都判失败。

## 设计要点

1. **单一真源**：所有口径只写一次（引擎）；HTML 内联同一份代码，Excel 公式与之逐项对应，`9-引擎校验` 页并列比对。
2. **缺口不填平**：缺汇率 → 拒绝折算（不插值）；缺运费且为 FOB → 拒绝折算（不按 0 算）；缺境内费用 → 显示"未取得"并登记缺口。
3. **历史不造假**：每个点用**当日**报价 + 当日汇率 + 当期税率；缺日留空；数据不足时页面显示"数据不足"，不画曲线。
4. **税率版本化**：`tax.profiles[]` 按 `effective_from` 生效，历史回算自动取当期版本，绝不拿现在的税率倒推过去。
5. **表述有边界**：`validate.js` 内置禁用词扫描（建议买入/目标价/后市看涨…），生成物里出现即报错。

## 已验证示例

| 示例 | 案例 | 结果 | 作用 |
|---|---|---|---|
| 01 | 进口乙二醇（MEG）→ 华东张家港，2026-10-16 | 净成本 4,831.95 元/吨，价差 +1,033.38 元/吨，口径 `fragile` | 完整路径：真实数据、5 个历史锚点、9 项缺口、17 条来源 |
| 02 | 进口甲醇（FOB 波斯湾）→ 华南，运费未取得 | **不可计算**（NO_FREIGHT），页面与 Excel 均显示"待补" | 证明 Skill 敢说"算不出来" |
| 00 | 模板 | 通过结构校验 | 换品种的起点 |

详见 `examples/01-meg-huadong/README.md` 与 `examples/01-meg-huadong/out/CALC-VERIFICATION.md`。

## 环境依赖

- Node.js ≥ 18（`validate.js` / `cross_check.js` / `build_html.cjs`）
- Python ≥ 3.10 + `openpyxl`（`build_xlsx.py`）、`playwright`（QA 脚本）
- LibreOffice（`check_xlsx.py` 重算；可选，缺失时该步会失败但不影响其他产物）

## 版本

v1.0.0 · 引擎 `1.0.0`
