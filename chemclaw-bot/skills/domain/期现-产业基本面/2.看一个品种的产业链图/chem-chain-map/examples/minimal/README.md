# 示例：最小可用数据集（与品种无关）

这个目录是**换品种时的起手模板**。只有 8 个节点、7 条关系，但跑通了完整流程
（校验 → HTML → Excel → 浏览器自检）。

```bash
python tools/run_all.py --data-dir examples/minimal/data --out-dir examples/minimal --verify
```

覆盖完整度 100%（7/7），因为清单本身就是这个小骨架。

---

## 文件

| 文件 | 内容 |
|---|---|
| `data/meta.json` | 品种参数（占位） |
| `data/nodes.json` | 8 个节点：2 个上游原料、1 个并列原料、目标品种、1 个替代品、2 个下游产品、1 个终端 |
| `data/relations.json` | 7 条关系，覆盖 conversion / route_option / blend / substitution / processing / application |
| `data/sources.json` | 1 条占位来源 |
| `data/core_checklist.json` | 4 个核心节点 + 3 条核心关系 |
| `DEMO_chain.html` | 生成结果（文件名取自 `meta.chain_id`） |
| `DEMO_chain.xlsx` | 生成结果 |
| `DEMO_report.json` | 校验与覆盖率明细 |

---

## 骨架结构

```
N_UP2 (col -2) ──conversion──┐
N_UP1 (col -1) ──conversion──┼──→ N_PRIMARY (col 0)
N_RA  (col -1) ──route_option┘
                                    │
              ┌──blend──────────────┤
              ↓                     ↓
        N_P1 (col 1, material)  N_P2 (col 1)
              │                     │
        processing              processing
              ↓                     ↓
        N_APP (col 2, application)
              
N_SUB (col 1) ──substitution──→ N_PRIMARY
```

---

## 换成你的品种，就改这 5 个文件

1. **`meta.json`** — 改 `chain_id`、`product_name`、`product_full_name`、`focus_question`、`user_params`
2. **`nodes.json`** — 按你的品种重写节点；记得：
   - `commodity` 要填真 CAS
   - `material` / `application` 的 CAS 必须是 `{"value":"不适用","status":"不适用"}`
   - `column` 从左到右递增
   - `node_role` 决定同列内的上下顺序
3. **`relations.json`** — 按决策树填类型（见 `references/02-relation-taxonomy.md`）
4. **`sources.json`** — 换成你查到的真实来源（A~C 级，带 `key_quotes`）
5. **`core_checklist.json`** — **先冻结再填数据**

可选再补：`prices_verified.json`、`enterprises.json`、`projects.json`、`events.json`、`forbidden_links.json`、`processes.json`。

字段细节见 `references/03-data-contract.md`，操作手册见 `references/07-new-product-playbook.md`。

---

## 注意

本目录的数据是**纯占位**（来源 S99 是虚构标识），只用于验证流程，**不得用于任何研究结论**。
真实案例请参考 `examples/sbs/`。
