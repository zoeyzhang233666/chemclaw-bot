---
name: chem-cost-model
description: Use when a domestic chemical buyer or manufacturing planner needs to know how much of a product's cost is raw material, and what a price move does to it — 测算原料成本占比 / 原料涨价影响 / 成本构成分析 / 敏感性分析 / 历史成本走势 / 原料单耗核算 / 我生产X，原料涨10%成本会怎样 / raw material cost share and price sensitivity for a chemical product. Works for bulk chemicals, fine chemicals and intermediates (DOP、苯酐、PVC、纯碱、钛白粉、三聚氰胺、尿素、甲醇、对苯二酚、丙烯酸、环氧乙烷、PET…), across different process routes and multi-material formulations. Delivers a self-contained interactive HTML cost calculator (edit dosage/price/%-change and it recomputes live, with cost-share, history curve, sensitivity heatmap and multi-material scenarios) plus an Excel workbook in which every result is a real formula, and an audit trail naming the process route, dosage basis, unit conversion, tax basis and every gap. It never treats theoretical raw-material cost as full production cost or profit, and never forecasts prices.
---

# 测算原料成本占比与涨价影响（化工 · 采购侧通用技能）

> 一句话：**把"这个产品主要靠哪几种原料、各占多少钱、涨跌 5%/10% 会怎样"说清楚，并且每一个数都能查到出处、改得动、算得回。**

## 0. 30 秒决定用不用

| 触发场景 | 典型原话 |
|---|---|
| 采购/成本测算 | "我生产 DOP，苯酐和异辛醇涨 10% 成本会涨多少？" |
| 报价/议价支撑 | "客户压价，我要拿出原料成本占比说话" |
| 年度预算 | "明年的原料预算是多少？按现在的单耗和价格" |
| 工艺对比 | "连续法比间歇法单耗低多少，折成钱是多少？" |
| 复盘归因 | "这三个月成本涨了 2000，是哪个原料涨的？" |

**不适用**：要预测原料未来价格、要判断"该不该现在囤货"、要算完整生产成本或利润、要报对外销售价。遇到这些，明确说明本技能只做**理论原料成本**的事实测算，不做预测与报价（见 `references/no-forecast-policy.md`）。

## 1. 铁律（违反任一条，产出即作废）

1. **理论原料成本 ≠ 生产成本 ≠ 利润。** 任何输出都必须同时声明"未纳入项"，且未纳入项不得隐含为零。
2. **不预测价格。** 敏感性只是"若涨/跌 X%"的机械演算，不写"预计""看涨/看跌""建议买入"。
3. **单耗必须有来源、有工艺、有单位。** 行业典型值必须注明来源与适用工艺；**不同工艺的单耗不得混在一起用**。
4. **用户实测优先。** 用户给的真实单耗/采购价，永远覆盖行业典型值；替换后必须重算并对比。
5. **缺数就写缺口。** 缺价格 → 该原料不计入成本（**不是 0**）并在缺口清单列出；缺历史 → 该时间窗写"无法计算"，**不插值、不生成**。
6. **口径不混。** 含税/不含税、元/吨与元/公斤、干基/湿基、出厂/送到、华东/山东，一律显式标注并在换算后才相加减。
7. **数据不分叉。** HTML / Excel / 报告的所有数字都来自同一个 `result.json`（由 `scripts/cost_engine.py` 一次算出）。手写数字＝错误。

## 2. 工作流（六步，输入 → 校验 → 计算 → 出稿 → 自检）

```
① 产品与工艺识别 → ② 单耗核验 → ③ 市场价格匹配 → ④ 建模计算 → ⑤ 出 HTML+Excel → ⑥ 自检
      process_route         dosage        price (六项口径)    cost_engine      build_all        qa
```

### ① 产品与工艺识别（决定后面所有口径）

- 确认**目标产品**的 CAS 与规格（例如 DOP = DEHP，CAS 117-81-7，酯含量 ≥99.0~99.6%）。
- 找出**主流工艺路线**（≥2 条时做横向对比，例如 DOP 的间歇/半连续/连续三条路线）。
- 写出**反应式**并做质量守恒校验：`python scripts/stoichiometry.py balance "A + 2B -> C + H2O"`。
- 同时识别：过量投料倍数（R）、催化剂体系、是否联产/副产。

### ② 单耗核验（最容易出错的一步）

按 `references/unit-consumption.md` 的四层口径分辨：

| 层级 | 定义 | 能否直接乘价格 |
|---|---|---|
| (i) 理论单耗 | `ν×MW原料 / MW产品`，100% 转化与收率 | 可作为**下界** |
| (ii) 净单耗 | 已扣回收、含转化/收率/副反应损失 | **首选**（环评吨耗表、ERP 消耗） |
| (iii) 表观投料 | 过量原料**不扣回收**（常见"1:2"、"摩尔比 1:2.2"） | **不能**直接当单耗 |
| (iv) 报价/包装口径 | 含量 98%、湿基、含量折算 | 必须先折算 |

来源等级（写入 `dosage.source`）：`user` > `enterprise` > `eia`/`patent`/`standard` > `assoc` > `textbook` > `research` > `media` > `simulated` > `none`。
**`simulated` 必须在页面与 Excel 中标黄，并写明"仅演示，不得当作企业实际单耗"。**

### ③ 市场价格匹配（六项口径）

每条价格必须具备：**规格 · 地区 · 交货方式 · 含税与否 · 计价单位 · 数据日期 · 来源**。
用 `scripts/fetch_prices.py` 抓可公开核验的现货序列（生意社基准价等）；拿不到就留空进缺口清单。详见 `references/price-data-standard.md`。

### ④ 建模计算

把研究结果写成 `input.json`（结构见 `references/data-contract.md`，模板见 `examples/input.template.json`），然后：

```bash
python scripts/build_all.py examples/01-dop-dehp/input.json --out out --name DOP-华东
```

`build_all.py` 会：校验 → 计算 → 生成 HTML → 生成 Excel → 打印缺口清单。

### ⑤ 出稿

- **HTML**：单文件、零外链、双击即开。首屏 = 成本 + 占比 + 近期变化；下方 = 成本构成图、历史曲线、敏感性热力图、组合情景、缺口、公式与来源。
- **Excel**：11 个工作表，**除原始输入外全部是公式**，改单耗/价格/幅度自动重算。

### ⑥ 自检

```bash
python scripts/validate.py out/../input.json      # 输入是否达标
python scripts/check_result.py out/result.json    # 计算结果是否自洽（±10% 必须等于 ±10%）
python scripts/qa_render.py out/xxx.html          # 渲染/交互（需要 playwright）
python scripts/check_workbook.py out/xxx.xlsx out/result.json   # Excel 公式重算是否等值（需要 Excel）
```

四项全绿才算交付。`references/qa-checklist.md` 是人工复核清单。

## 3. 公式（唯一权威实现：`scripts/cost_engine.py`）

```
单项成本        c_i = q_i × p_i
理论原料成本    C   = Σ c_i
成本占比        w_i = c_i / C × 100%
单项价格影响    Δc_i(r) = q_i × p_i × r          （r 为涨跌幅，+5% → r=0.05）
组合情景        C'(r) = Σ q_i × p_i × (1 + r_i)
历史成本        C_t   = Σ q_i × p_i(t)            （q 固定、p 取真实序列）
贡献分解        Δc_i  = q_i × (p_i,T − p_i,0)    （ΔC_T≈0 时不给占比）
```

完整推导、单耗换算、税口径处理、收率与联产分摊见 `references/formulas.md`。

## 4. 交付物结构

```
<产品>-<区域>/
  <产品>-<区域>_理论原料成本.html        单文件交互计算器
  <产品>-<区域>_理论原料成本.xlsx        公式版工作簿（11 表）
  result.json                          全部计算结果的唯一来源
```

## 5. 用户可上传/补充的数据（优先级最高）

- 真实生产单耗、原料配比、收率、能耗
- 实际采购价格、历史采购记录（成交价、数量、账期）
- 生产工艺、辅助材料、其他成本项

拿到这些数据时：**替换参数 → 重跑 → 新旧结果并列对比**，并在页面注明"含企业实测参数"。

## 6. 目录

```
SKILL.md
references/
  methodology.md          研究方法：从产品到成本的六步玩法
  formulas.md             全部公式与推导（含单位、税、收率、联产）
  unit-consumption.md     单耗四层口径与来源分级（防"1:2 当单耗"的坑）
  price-data-standard.md  价格六项口径与采集标准
  data-contract.md        input.json / result.json 字段规范
  presentation-spec.md    HTML 与 Excel 的版式与信息层级
  no-forecast-policy.md   不预测与边界表述规范
  qa-checklist.md         交付前人工复核清单
examples/
  input.template.json     空白模板（可复制填写）
  01-dop-dehp/            完整示例：DOP，真实价格 + 环评单耗
  02-meoh-natural-gas/    第二个示例：证明"换产品照样能用"
scripts/
  build_all.py            一键：校验→计算→HTML→Excel
  cost_engine.py          计算引擎（唯一实现）
  units.py                单位与价格口径换算
  stoichiometry.py        化学式、分子量、反应式配平、理论单耗
  validate.py             输入校验
  check_result.py         结果自洽性校验
  build_html.py / build_xlsx.py / templates/ / assets/
  fetch_prices.py         抓取公开现货序列（生意社）
  refresh_prices.py       更新已保存模型的价格序列
  qa_render.py / check_workbook.py   渲染与公式重算自检
tests/
  test_engine.py          公式与换算的单测
```

## 7. 安装

```bash
# 任选其一
cp -r chem-cost-model ~/.claude/skills/          # Claude Code / Codex 类
cp -r chem-cost-model ~/.agents/skills/          # 通用 agents 目录
# ChemClaw / WorkBuddy：放入其 skills 目录并保持目录名 chem-cost-model
```

依赖：Python 3.9+、`openpyxl`。可选：`playwright`（渲染自检）、Excel 或 LibreOffice（公式重算自检）。

Windows 下建议先 `$env:PYTHONUTF8='1'`。
