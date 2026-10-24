# 外贸合同审阅 Skill · Foreign Trade Contract Review

把一份外贸销售/采购合同，拆成 **「原文位置 → 问题 → 商务后果 → 待确认事项 → 处理状态」**
的可核查清单，并产出两份可直接使用的交付物：

- `review.html` — **左右双栏交互报告**：左侧合同原文，右侧风险提示；点风险跳到原文，点原文上的标记跳到风险条目；按主题/等级/状态筛选；每条可填负责人、处理状态、备注；可导出清单。
- `review.xlsx` — **9 页审阅工作簿**：使用说明 / 审阅总览 / 条款索引 / 问题清单 / 确认事项 / 缺失条款 / 原文摘录 / 法律引用 / 依据与边界。

适用于任何国家、任何化工品、任何语言、FOB/CIF/CFR/DAP/EXW 等任一贸易术语。

---

## 快速开始

```bash
# 进入示例目录
cd examples/soda-ash-indonesia-cif

# 1. 合同文本 -> 结构化块（每段拿到一个稳定 id）
python scripts/parse_contract.py contract_source.txt contract_parsed.json

# 2. 校验：锚点是否有效、引用是否逐字命中
python scripts/qa_report.py --parsed contract_parsed.json --issues "data_issues_0*.json"

# 3. 生成 HTML
python scripts/build_report.py contract_parsed.json data_meta.json \
    data_issues_0*.json --out review.html

# 4. 生成 Excel
python scripts/build_workbook.py contract_parsed.json data_meta.json \
    data_issues_0*.json --out review.xlsx

# 5. 浏览器自测（可选，需本机 Chrome）
python scripts/cdp_test.py review.html
```

依赖：Python 3.9+、`openpyxl`。第 5 步额外需要 Chrome。
脚本路径以实际解压位置为准（上面的 `scripts/` 相对解压根目录）。

---

## 目录

```
SKILL.md                         技能主文档：六步审阅法、质量门、边界
README.md                        本文件
references/
  review-checklist.md            11 类必查清单（含危险化学品专章）
  clause-library.md              风险条款模式 → 说明 → 英文修改草案
  incoterms-and-payment.md       贸易术语与付款方式核验要点
  legal-verification.md          法律规则核实登记（✅已核实 / ⚠️需律师 / ❌未核实）
  data-schema.md                 数据字段定义
  html-report.md                 报告页面结构与交互说明
templates/
  contract_markup.md             合同标记语法
  data_meta.template.json        元信息模板
  data_issues.template.json      问题数据模板
  report.css / report.js         报告样式与交互层（可直接改）
scripts/
  parse_contract.py              合同标记 -> contract_parsed.json
  qa_report.py                   数据与报告校验（构建前后都能跑）
  build_report.py                生成 review.html
  build_workbook.py              生成 review.xlsx
  cdp_test.py                    无头浏览器行为自测（29 项）
examples/
  soda-ash-indonesia-cif/        完整样例（见该目录 README）
```

---

## 六步法

1. **结构化识别** — 主体、产品、交易条件、条款结构，形成条款索引
2. **内部一致性扫描** — 同一件事在多处出现是否矛盾（最高产出的一步）
3. **代入我方身份** — 卖方还是买方，成本落在谁身上
4. **缺失条款检核** — 用清单过，没写的标「缺失」，不标「无问题」
5. **法律依据检索** — 只引用能给出处的，逐条标核实状态
6. **落到商务后果** — 具体场景 + 可估量级 + 我方失去什么

---

## 三条硬规则

| 规则 | 落地方式 |
|---|---|
| 每条问题必须锚定原文 | `qa_report.py` 逐字比对 `quote` 与合同原文，对不上直接失败 |
| 不得编造法律 | `references/legal-verification.md` 三档标注；境外法一律标「需律师确认」 |
| 不把正常商业安排判成违法 | 只描述「我方承担什么后果」，不写「违法/无效」 |

**缺失的条款**：用 `category: "missing"` + `anchors: []`，
明确说明「合同未约定」，不得推测条款存在。

---

## 质量门

交付前逐条打勾：

- [ ] 报告写明我方身份与「模拟/真实」性质
- [ ] `qa_report.py` 全绿（锚点、引文、枚举、结构）
- [ ] 缺失条款单独成表，措辞为「未约定」
- [ ] 法律引用逐条标核实状态，境外法标「需律师确认」
- [ ] 商务后果可估量（金额/天数/比例）
- [ ] 免责声明在 HTML 与 Excel 均出现
- [ ] HTML 交互自测通过（或手动点过定位/筛选/填写/导出）
- [ ] Excel 打开无损坏，筛选与下拉可用

---

## 边界

产出是**业务审阅材料**，不是法律意见：

- 不对合同效力下结论
- 不核验对手资信、货物实测品质、目的国监管现状
- 不做税务、外汇、海关归类结论

「建议修改措辞」是**谈判起点草案**，不是终稿。
任何法律适用结论须经中国法及对方国家法执业律师复核。
