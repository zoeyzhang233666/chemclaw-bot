# 检查采购合同风险点 · contract-review-risk-points

内贸采购场景下，审阅采购合同 / 框架协议的**业务风险点**，输出可追溯的条款索引、逐条风险提示与三张办理清单。

> 本 Skill 输出的是**业务审查提示**，不是法律意见。条款效力、责任分配、争议胜负一律交法务/律师。

---

## 它解决什么问题

用户拿来一份采购合同，问「这份合同有什么坑」。这类需求如果直接让模型「凭感觉提风险」，会出现三个通病：

1. 说不清风险落在哪一条、哪一页；
2. 把行业惯例当成合同已有约定；
3. 给出「该条款无效」这类越界结论。

本 Skill 用一套固定流程把这三个通病堵死：**先建条款索引 → 再按 10 个主题逐条比对 → 每条风险必须带条款锚点与逐字原文 → 缺失必须是缺失 → 最后按办理人拆清单**。

---

## 交付物

| 交付物 | 打开方式 | 用途 |
|---|---|---|
| `合同风险审查-交互页面.html` | 双击即可，离线可用 | 左原文右风险双栏；按主题/类型/严重度筛选；点击定位；处理状态与备注 |
| `合同风险审查-风险事项与问题清单.xlsx` | Excel | 10 个工作表：条款索引、风险总表、原文引用、法规核对、采购/法务/供应商三张清单、统计 |
| `虚构演示合同-*.docx` | Word | 仅在用户没有原件时生成的演示合同（明确标注虚构） |

---

## 目录

```
SKILL.md                      主流程（给 Agent 的执行说明）
references/
  contract-structure.md       合同结构识别与条款索引规范
  checklist.md                10 主题检查清单 + 业务影响写法
  chem-hazmat.md              危险化学品专项（资质/运输/信息传递/安全）
  chemical-products.md        不同化工品的检查差异
  legal-refs.md               法规标准适用性核对方法与常用清单
  output-spec.md              数据契约与交付物呈现要求
  failure-log.md              14 个常见失败模式与修正
  templates/                  空模板 + 两份示例数据
examples/
  液碱32采购合同演示/          完整示例（虚构演示合同 + 审查结果 + HTML + Excel）
  非危化品-表面活性剂示例/      非危化品对照示例
scripts/
  common.py                   加载与校验（所有脚本共用）
  build_review_html.py        交互式 HTML 生成器（精修版）
  render_html.py              HTML 通用渲染器（任意合同）
  build_review_xlsx.py        Excel 工作簿生成器
  build_contract_docx.py      由数据生成演示合同 DOCX
  paginate_contract.py        校对条款页码锚点
```

---

## 快速开始

```bash
# 1. 校验数据（硬校验：条款锚点、统计一致性；构建脚本会自动执行）
python -c "import sys; sys.path.insert(0,'scripts'); from common import load_case, validate_case; c=load_case('<案例目录>'); r=validate_case(c['contract'], c['review']); print(r['errors'] or 'OK', r['warnings'])"

# 2. 生成交付物
python scripts/build_review_html.py --dir <案例目录> --out <输出.html>
python scripts/build_review_xlsx.py --dir <案例目录> --out <输出.xlsx>

# 3. 仅用户没有原件时：生成演示合同
python scripts/build_contract_docx.py --dir <案例目录> --out <合同.docx>
```

依赖：Python 3.10+、`openpyxl`、`python-docx`；页码校对另需 LibreOffice Kit 与 `pymupdf` 或 `pypdf`。

---

## 适用与不适用

**适用**：内贸采购合同、框架协议、主协议+订单；化工品（液碱、盐酸、甲苯、片碱、助剂……）及一般工业原料。

**不适用/需谨慎**：外贸合同（Incoterms、信用证、跨境争议解决不在此覆盖）、工程类合同、软件采购、纯法务条款审查（本 Skill 不做效力判断）。

---

## 边界声明

- 本 Skill **说明合同写了什么、哪些没写、可能造成什么业务后果、建议找谁确认**。
- 本 Skill **不**评价条款效力、不判断诉讼胜负、不替代律师。
- 法规与标准的现行状态以**核对日期**为准，正式签约前需重新核对。

> 本结果属于业务审查提示，不是法律意见，也不替代律师或法务的专业审查。涉及条款效力、是否可执行、法律责任分配等问题，必须以公司法务/外部律师意见为准。
