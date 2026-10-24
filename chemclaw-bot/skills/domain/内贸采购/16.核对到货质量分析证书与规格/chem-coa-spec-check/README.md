# chem-coa-spec-check

内贸采购 · 【核对到货质量分析证书与规格】的可复用技能包。

把供应商随车带来的 **COA / 检验报告** 与 **采购规格书 / 合同技术附件 / 适用标准**逐项核对，
输出一份**可追溯**的核对结论、一份可发给供应商的**质量异议函草案**，
以及一份能被复核的 **Excel 工作簿**。**不作收货决定。**

---

## 一分钟上手

```bash
python scripts/build_all.py          # 用内置的乙二醇模拟样例跑全流程
```

跑完得到：

```
examples/mdeg/out/
  乙二醇到货COA核对报告_20260608-核对报告.html     ← 双击打开（单文件，无需联网）
  乙二醇到货COA核对报告_20260608-核对工作簿.xlsx   ← 12 页签
```

## 用自己的数据

```bash
# 1) 从原始文件抽候选（HTML/PDF/DOCX/XLSX/TXT）
python scripts/extract.py 到货COA.pdf --kind coa -o _coa.json --pretty

# 2) 按 _coa.json 里的 conf（高/中/低）与 loc（行号）逐项回原件确认，
#    把确认后的值填进 data.json（结构见 references/data-contract.md，
#    空白模板 templates/data.template.json）

# 3) 出报告
python scripts/build_all.py --data examples/我的产品/data.json --no-samples
```

---

## 它到底判什么

对**每一个**规格约定或 COA 里出现的指标，给出六种状态之一：

`符合` · `不符合` · `规格未约定` · `COA未检测` · `无法判断`

- `不符合` 会带**偏离幅度**（以限值为分母，如 `+44.00%`）
- `无法判断` 一定写清楚**卡在哪个维度**（名称/量纲/方法/基准/检出限）
- 证书本身另有 **完整性得分**（100 起扣：高 −18 / 中 −8 / 低 −3）

---

## 核心设计（为什么这样做）

### 1. "读"与"判"分离
`extract.py` 只负责把文件变成候选数据，且每条都带**置信度**和**原文行号**。
判定引擎只吃结构化 JSON。这样"读错"和"判错"是两件事——前者可回原件复核，后者可复算。

### 2. 判定顺序即规则
```
有规格限值吗？ → 没有 = 规格未约定
COA 有这个数吗？ → 没有 = COA未检测
能比吗（五维）？ → 不能 = 无法判断
比出来的结果 → 符合 / 不符合（+偏离）
```
把"能不能比"放在"大不大"之前，是这份技能与"Excel 里手搓 if"的根本区别。

### 3. 可比性五维（`COMP_DIMS`）
名称·量纲·方法·基准·限值类型，任一不过就是 `无法判断`。
**别名表里没有的名字，一律不算同一个指标。** 这一条拦住绝大多数误判。

### 4. 换算必须可复算
报告里带"单位换算台账"：原值、原单位、系数、换算后值、说明、**是否跨判定线**。
换算前后结论翻转 → 强制 `无法判断` + 提示回原件（典型的单位标注错位）。

### 5. 趋势先归一化再算
每个批次先换算到规格单位，再进序列、算统计量。
历史版本曾把 `865 ppm` 与 `0.08 %` 放在同一序列里，得到"水分均值 144 %"——现在不会了。

### 6. 不作收货决定
输出里只有事实、偏离、待补事项。`validate.py` 会扫"建议收货/建议退货/同意接收"等词并**报错拦截**。

---

## 目录结构

```
chem-coa-spec-check/
├── SKILL.md                       技能说明（给 agent 读）
├── README.md                      本文件（给人读）
├── scripts/                       Python 3.9+，核心零依赖
│   ├── coa_lib.py                 解析·换算·可比性·判定·偏离·趋势
│   ├── engine.py                  引擎（逐项/完整性/方法/趋势/异议/函件）
│   ├── extract.py                 文件 → 候选数据（多格式，带置信度）
│   ├── render_html.py             单文件 HTML 报告（内联 CSS/JS，SVG 图）
│   ├── render_xlsx.py             12 页签工作簿（含公式与折线图）
│   ├── validate.py                结构/语义/合规三关
│   ├── build_all.py               一键流水线
│   └── build_example_data.py      重建模拟样例
├── references/                    规范与手册（data-contract 必读）
├── templates/data.template.json   空白输入
├── examples/mdeg/                 工业用乙二醇（模拟）完整案例
└── assets/coa-report.css          报告样式
```

---

## 扩展指南

| 想做的事 | 改哪里 |
|---|---|
| 支持新单位 | `coa_lib.DIMENSIONS` 对应 `_mkdim(...)` 的 `members` 加一项 |
| 新增产品别名 | 在 `data.json` 的 `product.indicator_aliases` 里加，**不用改代码** |
| 认定"方法等效" | `data.json` 的 `product.equivalent_methods` 里成组列出 |
| 新增完整性检查项 | `engine.check_completeness()` 里 `add(level, field, msg, action)` |
| 改函件语气 | `engine.draft_message()` 的 `formal/firm/soft` 分支 |
| 改报告样式 | `assets/coa-report.css`，然后重跑 `render_html.py` |
| 新增 Excel 页签 | `render_xlsx.py` 里加 `sh_xxx()` 并在 `render()` 注册 |

---

## 排查

| 现象 | 原因与处理 |
|---|---|
| `KeyError` 在 `comparability` | 指标名不在别名表 → 加入 `indicator_aliases` |
| 全部"方法不同" | 方法号后缀格式乱（`GB/T 14571.1-2018` vs `GBT14571.1`）→ `coa_lib.method_id` 已归一，仍不同说明确实不同 |
| 趋势数值离谱 | 某批次单位异常 → 看报告"单位换算台账"的换算说明 |
| 报告出现 `None` | 模板字段为空 → `render_html` 用 `fmt()` 兜底，检查 `data.json` 该字段 |
| `validate.py` 报 `DECISION` | 函件里写了收货结论 → 改成"请贵司说明/请提供复检报告" |
| Excel 公式不显示结果 | openpyxl 不重算 → 在 Excel 里 Ctrl+Alt+F9，或用 LibreOffice `recalculate` |

---

## 已知边界

- **不判断工艺适用性**：超限的货能不能用，取决于用户的工艺，报告不答。
- **不判断商务责任**：只列事实，不写"供应商违约"。
- **不做 OCR**：扫描件需先 OCR 或人工抄录（`extract.py --instructions` 有模板）。
- **不自动扩方法等效性**：方法是否等效需专业判断，宁可落 `无法判断`。
- **历史批次只用于趋势**：不参与本批判定。

---

## 数据声明

`examples/mdeg/` 下所有企业名称、批号、日期、检测数值均为**模拟构造**，
仅用于演示流程，不得作为真实质量记录或索赔依据。样例文件均带 `SIMULATED` 水印。
