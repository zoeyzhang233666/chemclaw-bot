---
name: coa-spec-check
description: >
  Compare an inbound material's Certificate of Analysis (COA / 检验报告) against the purchase
  spec sheet, contract technical annex, or applicable national/industry standard, item by item,
  and produce a traceable verdict for each quality indicator plus supplier quality-objection
  points and a ready-to-send objection draft. Use for 内贸采购到货核对 / 到货质量分析证书与规格核对 /
  COA 与采购规格书比对 / 检验报告指标核对 / 来料质量证书审核 / 供应商质量异议函 / 多批次质量趋势.
  Handles unit conversion (%, ppm, ppb, mg/kg, mg/L), max/min/range/detection-limit values,
  method and basis differences, and multi-batch trends. Never makes the accept/reject decision.
---

# 到货质量分析证书（COA）与采购规格核对

把一张随车来的《质量分析证书》和采购规格书 / 合同技术附件逐项摆在一起，
回答四个问题：**哪些符合、哪些不符合（差多少）、哪些因为条件缺失没法判、证书本身够不够格**。
最后给出可直接发给供应商的质量异议要点与函件草稿。

> **本技能不作收货决定。** 报告只呈现事实与判断，"收不收、怎么处置"由采购/质量/生产/商务按合同共同决策。

---

## 何时使用

- 到货了，供应商拿来一份 COA / 检验报告 / 化验单，要判断"是不是按合同做的"
- 要写质量异议函、索赔函、让步接收沟通函，需要事实底稿
- 想复盘某供应商近几个批次的指标趋势（缓慢劣化 / 突跳）
- 要核对"这张证书本身是否规范"（批号、日期、方法、签名、结论）

**不适合**：判断货物能否用于某个具体工艺（那是工艺适用性评估）；
判断商务责任划分（那是合同/法务判断）。

---

## 输入（三条路径，任选）

| 路径 | 做法 | 适用 |
|---|---|---|
| **A. 直接给结构化 input** | 按 `references/data-contract.md` 填 `data.json` | 已有整理好的数据 |
| **B. 给原始文件** | `python scripts/extract.py <file> --kind coa -o coa.json --pretty` 抽出候选，**人工确认**后合并进 `data.json` | PDF / HTML / DOCX / XLSX / TXT |
| **C. 扫描件/照片** | 先 OCR 或人工抄录成文本（`extract.py --instructions` 有模板），再走 B | 图片、模糊 PDF |

**路径 B/C 的铁律**：`conf` 标为 `低` 的字段**必须**回原件确认，并写入 `review_log`。
看不清的数字写 `?`，不填"最像的那个"。见 `references/exception-handling.md`。

---

## 输出

1. **`<同名>-核对报告.html`** —— 单文件（无外链、无 CDN），含：
   - 结论概览：六种状态计数、可量化核验比例、证书完整性得分、最大偏离
   - 抽取确认：文件抽取结果与原文位置，关键值可逐项确认
   - 逐项比对：状态筛选 / 关键词搜索 / 点任意指标 → 定位 COA 与规格原文位置 / 单位换算台账
   - 多批次对照、证书完整性检查、方法差异、批次趋势（SVG 图）
   - 异议要点 + 三种语气函件草稿（可复制/下载）
   - "本报告不作收货决定"免责声明
2. **`<同名>-核对工作簿.xlsx`** —— 12 页签：说明免责 / 核对结论 / 逐项比对（含偏离公式）/ 单位换算台账 /
   批次趋势（含折线图）/ 完整性检查 / 方法差异 / 多批次对照 / 异常问题清单 / 异议要点 / 原始数据 / 判定规则

---

## 六种判定状态（只此六种）

| 状态 | 含义 |
|---|---|
| `符合` | 可比、可量化核验，实测在限值内 |
| `不符合` | 可比、可量化核验，实测越过限值（附偏离%） |
| `规格未约定` | 合同/规格/标准均无限值——不能据以判不合格 |
| `COA未检测` | 规格约定了，但 COA 缺项 / 空值 / 写"未检测" |
| `无法判断` | 有数但不能比：名称/量纲/方法/基准/限值类型不可比，或检出限不明 |

**判定顺序不能颠倒**：先问"有没有"→ 再问"能不能比"→ 最后才问"大不大"。
先比大小是最大的错误来源。详见 `references/matching-rules.md`。

---

## 五条硬规则

1. **名称相似 ≠ 同一指标。** 别名表里没有的对应关系，一律 `无法判断`，交人确认。
   （`总酸` vs `酸度`、`醛类` vs `乙醛` 都不同）
2. **不做无依据换算。** `%` ↔ `mg/L` 缺密度就不换算；换算跨越判定线 → `无法判断` + 提示回原件。
3. **`未检出` ≠ 合格。** 必须拿到检出限；检出限 > 限值时这个结果证明不了任何事。
4. **合同优先。** 合同放宽了国标，不得用国标提高要求；合同没约定的方法，不算法"不合格"。
5. **不猜、不补、不改写。** 看不清的写 `?`；批号对不上就如实报告"对不上"，不为了对上而改写。

---

## 快速开始

```bash
# 跑内置样例（工业用乙二醇，模拟数据）：重建样例 + 校验 + 出报告
python scripts/build_all.py

# 用自己的数据
python scripts/extract.py COA.pdf --kind coa -o tmp_coa.json --pretty
#   → 逐项核对 conf/loc，把确认后的值填进 data.json
python scripts/build_all.py --data examples/我的产品/data.json --no-samples

# 只校验，不出报告
python scripts/validate.py data.json
```

依赖：Python 3.9+。核心引擎与 HTML 零第三方依赖；Excel 需要 `openpyxl`；
PDF 抽取需要 `pdfminer.six` / `PyMuPDF` / `pdfplumber` 之一（都没有就按路径 C 抄录）。

---

## 目录

```
chem-coa-spec-check/
├── SKILL.md                      本文件
├── README.md                     给维护者：架构、扩展、排查
├── scripts/
│   ├── coa_lib.py                核心库：解析/换算/可比性/判定/偏离/趋势
│   ├── engine.py                 比对引擎：逐项判定、完整性、方法差异、趋势、异议
│   ├── extract.py                文件 → 候选 data.json（带置信度与行号）
│   ├── render_html.py            单文件交互报告
│   ├── render_xlsx.py            12 页签工作簿
│   ├── validate.py               结构/语义/合规三关校验
│   ├── build_all.py              一键流水线
│   └── build_example_data.py     重建模拟样例
├── references/
│   ├── data-contract.md          输入 JSON 字段规范（**先读这个**）
│   ├── matching-rules.md         判定顺序、可比性五维、偏离算法、严重度
│   ├── unit-conversion.md        能做/不能做的换算，系数表
│   ├── exception-handling.md     异常与人工确认手册
│   └── quality-gates.md          交付前质量门
├── templates/data.template.json  空白输入模板
├── examples/mdeg/
│   ├── samples/                  模拟原始文件（COA×2、规格书、合同附件、历史台账）
│   ├── data.json                 整理后的结构化输入
│   ├── NOTES.md                  样例讲解（每个坑对应哪一行）
│   └── out/                      生成好的 HTML 与 XLSX
└── assets/coa-report.css         报告样式（已被 inline 进 HTML，改这里再重渲染）
```

---

## 常见坑（都已在引擎里处理，但要知道为什么）

| 坑 | 后果 | 引擎怎么做 |
|---|---|---|
| 865 ppm 直接和 0.08 % 比 | 判"符合"（错） | 先换算到规格单位：0.0865 % ⇒ 不符合 |
| 580 ppb 当 0.58 % 比 | 判"符合"（错） | ppb → ppm：0.58 > 0.5 ⇒ 不符合 |
| `未检出` 直接判符合 | 掩盖"测不到" | 无检出限 → COA未检测；检出限>限值 → 无法判断 |
| 报了个漂亮的 LOD 值 | 假合格 | 结构识别（恰为限值 1/5 量级）→ 无法判断 |
| 单位标注错位 | 结论反转 | 换算前后判定翻转 → 强制无法判断 |
| 合同放宽了标准 | 误判不合格 | 规格按 priority 取，标准只兜底 |
| 批号不一致 | 证书张冠李戴 | 完整性高优先级问题 + 异议点 |
| 趋势里混单位 | 假趋势 | 每个批次先归一化到规格单位再算 |

---

## 下游动作（报告给你的建议清单）

1. 对超限项要求"同一样品、约定方法"的复检报告，或书面技术说明
2. 对缺检项要求补充检测结果 + 方法 + 检出限
3. 对证书缺陷要求补发正式证书（批号、结论、方法、签章）
4. 把多批次趋势作为"是否属持续性问题"的事实依据（不替用户定性为"质量事故"）
5. 是否让步接收、是否索赔、是否换供应商 —— **由人决定，报告只提供事实**
