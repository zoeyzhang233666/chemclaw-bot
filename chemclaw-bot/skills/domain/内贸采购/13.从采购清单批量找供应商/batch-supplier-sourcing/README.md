# 批量采购清单寻源（batch-supplier-sourcing）

把采购清单变成一张**可审计的「物料 × 企业」矩阵**：每一格都有出处，每个说不清的地方都变成一条要问客户的问题，而不是一个猜测。

- 严格区分 **厂家（S/P/G）** 与 **贸易商（T/I）**，未证实主体（U）不进候选池
- 每条企业结论都带 **证据等级 + 原文引用 + 链接 + 日期**
- 输出 **单文件交互式 HTML** + **13 表 Excel**

## 快速开始

```bash
python -m pip install -r requirements.txt

# 1) 清单 → 项目骨架（自动解析 + 自动生成待确认问题）
python scripts/make_project.py 采购清单.xlsx --out project.json --title "2027年度原料寻源"

# 2) 补 suppliers / evidence / links（结构见 templates/project.schema.json）
#    完整范例：examples/northeast-china-batch/project.json

# 3) 校验
python scripts/validate_project.py project.json

# 4) 出报告
python scripts/build_all.py project.json
```

## 直接看范例

```bash
python scripts/build_all.py examples/northeast-china-batch/project.json
```

范例 = **模拟采购清单（30 行，含 8 种故意的脏数据）× 真实可核验的公开企业信息（41 条证据，全部带链接）**。

结果看 `examples/northeast-china-batch/output/`。

## 目录

```
SKILL.md                 技能说明（给 AI 用）
README.md                本文件
references/              8 篇方法参考
assets/                  物料字典(95 种) / 字段别名 / 规则阈值
scripts/                 解析、匹配、校验、出报告的 Python
templates/               project.json 的 JSON Schema
examples/                清单 + 完整项目 + 输出成品
```

## 关键口径

| 维度 | 取值 |
|---|---|
| 身份 | S 厂家 / P 部分生产 / G 集团内生产 / T 贸易商 / I 集成商 / U 未证实 |
| 覆盖度 | ● direct / ◐ partial_spec / ○ disclose / ◆ dist_only / × not_listed |
| 证据 | A 权威·许可 / a 法定披露 / B 官方·交易所 / C 媒体 / D 无链接 / E 推断 |
| 风险 | 厂家 0 → 无覆盖；≤2 → 单一；direct<2 → 规格/证据不足 |

## 依赖

`openpyxl`、`pandas`（可选，读 CSV）。Python 3.9+。无网络调用，HTML 无 CDN 依赖。

## License

MIT，见 `LICENSE`。
