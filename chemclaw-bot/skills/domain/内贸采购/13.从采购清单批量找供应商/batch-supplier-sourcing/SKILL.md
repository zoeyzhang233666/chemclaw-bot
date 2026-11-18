---
name: batch-supplier-sourcing
description: Use when a buyer hands over a purchase list (Excel/CSV/PDF) and needs suppliers for every line — 批量找供应商 / 采购清单寻源 / 物料—供应商匹配矩阵 / 哪些厂家能同时供多个物料 / 分清厂家和贸易商 / 核实供应商是否真生产该产品. Covers 内贸采购. Produces a self-contained interactive HTML report plus a 13-sheet Excel workbook in which every supplier claim carries a graded, clickable evidence trace, ambiguities are asked rather than guessed, and producer (厂家) is strictly separated from trader (贸易商).
---

# 批量采购清单寻源（Batch Supplier Sourcing）

**一句话**：把一份采购清单变成一张可审计的“物料 × 企业”矩阵——每格都有出处，每个说不清的地方都变成一条要问客户的问题，而不是一个猜测。

## 何时用

- 客户给一份物料清单（Excel / CSV / PDF / 微信截图转表），要求“每一行都找供应商”。
- 客户问“这些料能不能在同一家买齐”、“哪些企业能同时供几种”。
- 客户要区分“真厂家”和“倒手贸易商”，并且要求给出核实依据。
- 客户要一份能直接发给供应商的询价清单 / 资质核验清单。

**不适用**：只找一种产品的厂家（用 `按产品找生产厂家`）；找下游买家（用 `b2b-lead-sourcing`）；只查价格行情（用 `chem-market-brief`）。

## 五条不可让步的规则

1. **厂家 ≠ 贸易商。** 只有能落到“自有装置 / 许可证载明的产能 / 该企业自己披露的产量”的主体才算厂家。贸易商单独立池（身份 T），未证实主体（U）不得进入比价名单。
2. **企业网站提到某产品 ≠ 有稳定供货能力。** 产品罗列最多给到 `partial_spec`（◐）；“产能 + 规格 + 对得上清单要求”三者齐备才给 `direct`（●）。
3. **不猜测。** 名称多义、CAS 校验失败、单位无法折算、数量为 0 —— 一律生成一条待确认问题（P0/P1/P2）+ 问谁 + 为什么问，绝不“自动纠正”后静默通过。
4. **每条企业结论都要有 grade + 原文引用 + 链接 + 日期。** 无链接的只能记 D 级、只能当线索。
5. **“本轮没查到” ≠ “市场没有”。** 空白格和“无厂家覆盖”必须写成“本报告本轮未查出可核验厂家”，并进入缺口清单。

## 工作流

```
① 读入清单  →  ② 字段映射  →  ③ 化学标准化  →  ④ 歧义清单（不猜）
                                             ↓
⑩ 交付      ←  ⑨ 矩阵与缺口  ←  ⑧ 分级取证  ←  ⑤ 候选企业（厂家/贸易商分离）
```

| 阶段 | 做什么 | 脚本 / 参考 |
|---|---|---|
| ① 读入 | 自动找表头、多 sheet、合并单元格、空行 | `scripts/lib_ingest.py` → `references/01` |
| ② 映射 | 品名/CAS/规格/数量/单位/包装/交付地 | `assets/field-map.json` |
| ③ 标准化 | 名称+别名+CAS（校验位）+浓度+形态+单位 | `assets/materials-reference.json`、`assets/rules.json`、`references/02` |
| ④ 歧义 | 分级提问，不填猜测值 | `references/08` |
| ⑤ 企业 | 先定身份 S/P/G/T/I/U，再谈覆盖 | `references/03` |
| ⑥–⑧ | 覆盖度五级 + 证据六档 + 可靠性排序 | `references/03`、`references/04` |
| ⑨ 矩阵 | 双向矩阵、跨物料企业、稀缺物料 | `references/04` |
| ⑩ 交付 | HTML + Excel + 询价包 | `references/06` |

## 快速开始

```bash
# 1) 从清单生成项目骨架（自动解析 + 生成待确认问题）
python scripts/make_project.py 采购清单.xlsx --out project.json --title "2027年度原料寻源"

# 2) 人工/调研补齐 project.json 里的 suppliers / evidence / links
#    （结构见 templates/project.schema.json，完整范例见 examples/northeast-china-batch/project.json）

# 3) 校验：引用完整性、证据规则、覆盖度口径
python scripts/validate_project.py project.json

# 4) 出报告（HTML + Excel）
python scripts/build_all.py project.json
```

输出：

```
output/
  <清单名>_批量寻源报告_YYYYMM.html   # 单文件、可离线打开、可交互
  <清单名>_批量寻源报告_YYYYMM.xlsx   # 13 个工作表
```

## 交付物长什么样

**HTML（单文件，无外部依赖）**

- ① 概览与结论（KPI + 5 条结论摘要，每条都能点回证据）
- ② 物料标准化表：**单元格可编辑**，改动本地留存，可导出 CSV 交回客户确认
- ③ 待确认事项：P0/P1/P2 分级
- ④ 候选企业：按身份/省份/覆盖数过滤
- ⑤ **双向匹配矩阵**：物料→企业、企业→物料一键切换；按身份/省份/覆盖数/危化品过滤；**点格子弹出证据抽屉**（判定理由 + 原文引用 + 链接）
- ⑥ 跨物料企业（打包谈判对象） ⑦ 稀缺与风险 ⑧ 证据库 ⑨ 危险与监管
- ⑩ **一键生成每家企业的询价清单**（可复制 / 下载 .txt）

**Excel（13 表）**：00 封面 / 01 物料标准化表 / 02 待确认 / 03 候选供应商 / 04 物料→供应商矩阵 / 05 供应商→物料矩阵 / 06 多物料覆盖 / 07 稀缺与风险 / 08 证据明细 / 09 危险与监管 / 10 询价与资质核验 / 11 来源库 / 12 方法与字段映射

## 关键口径（背下来）

| 维度 | 取值 | 含义 |
|---|---|---|
| 身份 | S 厂家 / P 部分生产 / G 集团内生产 / T 贸易商 / I 集成商 / U 未证实 | 只有 S/P/G 计入厂家覆盖 |
| 覆盖度 | direct ● / partial_spec ◐ / disclose ○ / dist_only ◆ / not_listed × | ● 需证据 A-a-B 且规格对得上 |
| 证据 | A 权威库·许可 / a 法定披露 / B 官方·交易所 / C 媒体 / D 无链接自述 / E 推断 | D/E 不得单独支撑企业结论 |
| 可靠性 | 覆盖度分 × 身份权重（S 1.0、P 0.6、G 0.5、T 0.4、I 0.5、U 0.1） | 只用于排序，不是商务评分 |
| 稀缺 | 厂家 0 → 无覆盖；≤2 → 单一；direct<2 → 规格/证据不足 | 阈值见 `assets/rules.json` |

## 参考文件

- `references/00-quickstart.md` — 30 分钟跑通一遍
- `references/01-intake-and-field-mapping.md` — 读入与字段映射（含 PDF/图片/脏表）
- `references/02-chem-normalization.md` — 化学名称、CAS、浓度、单位标准化
- `references/03-evidence-and-identity.md` — 证据分级与厂家/贸易商判定
- `references/04-coverage-and-matrix.md` — 覆盖度、跨物料、稀缺判定
- `references/05-hazard-and-compliance.md` — 危险属性与监管提示
- `references/06-output-spec.md` — 输出规格与字段字典
- `references/07-qa-checklist.md` — 交付前自查清单
- `references/08-abnormal-handling.md` — 异常清单处理手册（15 种脏数据）
- `examples/northeast-china-batch/` — 完整范例（模拟清单 × 真实企业证据）
- `templates/project.schema.json` — project.json 结构

## 常见坑

1. 把集团销售公司当厂家 → 判 G，并注明“集团内生产主体”。
2. 把“年报提到该产品”当产能 → 只能 ◐，除非同一份文件给出产能/产量。
3. 同一物料的多行（不同浓度/包装）合并成一行 → 会掩盖产线差异，按行保留并注明重复项。
4. 用“行业常识”补 CAS → 一律禁止，CAS 必须来自字典或客户确认。
5. 把“上游原料”当“本企业产品”（如硫磺之于硫酸厂）→ 只能 disclose，且必须写明“为主要原料而非产品”。
