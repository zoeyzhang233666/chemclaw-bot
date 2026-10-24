# 00 快速上手（30 分钟跑通）

## 目录

```

batch-supplier-sourcing/
├── SKILL.md
├── README.md
├── CHANGELOG.md
├── LICENSE
├── requirements.txt
├── assets/
│   ├── materials-reference.json   # 95 种大宗/基础化工品的标准名、CAS、别名、形态、危险属性
│   ├── field-map.json             # 清单表头别名 → 标准字段
│   └── rules.json                 # 单位表、证据分、身份权重、覆盖度分、稀缺阈值
├── scripts/
│   ├── make_project.py            # 清单 → project.json 骨架（含自动歧义提问）
│   ├── validate_project.py        # 结构与证据规则校验
│   ├── build_all.py               # 一键出 HTML + Excel
│   ├── lib_ingest.py / lib_common.py / lib_match.py / lib_model.py
│   ├── lib_excel.py / lib_html.py / lib_actions.py
│   └── make_example_list.py       # 生成范例用的模拟清单
├── templates/
│   └── project.schema.json
├── references/
└── examples/
    ├── purchase-lists/northeast-china-plant/
    └── northeast-china-batch/
```

## Step 0 环境

```bash
python -m pip install -r requirements.txt    # openpyxl / pandas
```

仅需 Python 3.9+，无网络调用，无外部 JS。

## Step 1 准备清单

支持 `.xlsx / .xlsm / .csv / .json`。表头不必在首行——脚本会自动找“命中别名最多”的那一行。

允许的表头写法（节选，见 `assets/field-map.json`）：

| 标准字段 | 常见写法 |
|---|---|
| `raw_name` | 物料名称 / 品名 / 产品名称 / 化学品名称 / 名称规格 |
| `cas` | CAS / CAS号 / CAS No. / CAS登记号 |
| `form` | 规格 / 形态 / 型号 / 浓度 / 品级 |
| `quantity` | 数量 / 需求量 / 采购量 / 用量 |
| `unit` | 单位 / 计量单位 / 单位(UOM) |
| `annual_usage` | 年用量 / 年度需求 / 年需求量 |
| `packing` | 包装 / 包装规格 / 包装形式 |
| `delivery` | 交付地点 / 到货地 / 收货地 / 交货地 |
| `spec` | 技术要求 / 质量要求 / 执行标准 / 指标 |

## Step 2 生成骨架

```bash
python scripts/make_project.py 采购清单.xlsx --out project.json --title "2027年度原料寻源" --buyer "XX 工厂采购部"
```

输出：`items`（标准化后的行）、`ambiguities`（待确认问题）、`parse_notes`（解析提示）。
此时 `suppliers / evidence / links` 都是空数组。

## Step 3 补三类数据（核心工作）

按 `templates/project.schema.json` 填：

1. **suppliers** —— 每家企业一个对象：`id / name / short / identity(S|P|G|T|I|U) / province / identity_note / evidence_ids`
2. **evidence** —— 每条证据：`id / grade / org / topic / quote / detail / url / date / items`
3. **links** —— 每条“企业×物料”关系：`item_code / supplier_id / identity / coverage / confidence / degree / current_relation / potential_relation / rationale`

`degree` 取值：`independent`（独立可成立）/ `confirmable`（一确认即可成立）/ `conditional`（有条件）/ `co_list_only`（只出现在同一产销表中）/ `not_covered` / `not_recommended`。

## Step 4 校验

```bash
python scripts/validate_project.py project.json
```

必须 0 ERROR。WARN 逐条判断：

- “企业证据没有命中该物料” → 在该企业某条证据的 `items` 里补这个物料码（跨品种推断必须写进 `rationale`）
- “仅有 D/E 级证据” → 该主体应改为 U

## Step 5 出报告

```bash
python scripts/build_all.py project.json
```

得到 `output/*.html` + `output/*.xlsx`。HTML 直接双击打开，无需服务器。

## 范例对照

想直接看成品：

```bash
python scripts/build_all.py examples/northeast-china-batch/project.json
```

- 清单：`examples/purchase-lists/northeast-china-plant/purchase_list_simulated.xlsx`（30 行模拟数据，含 8 种故意制造的脏数据）
- 结果：`examples/northeast-china-batch/output/`
- 说明：企业全部真实可核验，清单与数量虚构

## 时间预算

| 步骤 | 单项清单（≤10 行） | 中型（10–30 行） | 大型（30–100 行） |
|---|---|---|---|
| 解析 + 歧义 | 5 min | 10 min | 20 min |
| 企业检索（每物料 3–5 家） | 0.5–1 h | 2–4 h | 1–2 天 |
| 证据录入 | 0.5 h | 1–2 h | 4–8 h |
| 出报告 + 自查 | 10 min | 20 min | 40 min |

**先做“主料”（占成本 80% 的 8–15 个物料），辅料可先给“待补”占位**——报表设计允许“待补厂家”这类 U 级占位行，但会被计入缺口清单，不能假装已找到。
