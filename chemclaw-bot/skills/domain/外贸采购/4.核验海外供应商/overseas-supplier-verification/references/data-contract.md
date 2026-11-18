# project.json 数据契约

> 一份 `project.json` 描述**一份核验的全部内容**。渲染器不认识"乙二醇"，只认识这里的字段。
> 空白骨架见 `templates/project.template.json`；完整实例见 `examples/`。

---

## 1. 顶层字段

```jsonc
{
  "schema_version": "1.0",
  "meta":          { … },     // 必填
  "summary":       { … },     // 必填：结论摘要
  "sections":      [ … ],     // 必填：正文区块
  "evidence":      [ … ],     // 必填：证据索引
  "documents":     [ … ],     // 文件核验
  "entity_map":    [ … ],     // 主体映射
  "subject_master":{ … },     // 主体档案
  "gaps":          [ … ],     // 待确认事项
  "timeline":      [ … ],     // 事件时间轴
  "rfi":           { … }      // 英文询证清单
}
```

### meta

| 字段 | 说明 |
|---|---|
| `doc_no` | 报告编号，如 `OSV-SA-MEG-2026-001` |
| `title` | 报告标题 |
| `subject_full` | 被核验主体全称 |
| `country` / `product` / `product_spec` | 国家、采购品、规格 |
| `incoterm` | 贸易术语 |
| `as_of` | **核验基准日**（全文唯一时间基准） |
| `author` / `reviewer` / `version` | 编制、复核、版本 |
| `export_prefix` | 导出文件名前缀（不含扩展名） |
| `disclaimer` | 免责声明（渲染到封面） |

---

## 2. summary（结论）

```jsonc
{
  "verdict": "identify_only",   // identify_only | proceed_with_gaps | hold | insufficient
  "headline": "一句话结论",
  "text": "2–4 句展开",
  "key_findings": ["已确认事实1", "…"],
  "not_concluded": ["不认定…", "…"]
}
```

**verdict 四选一**：

| 值 | 中文 | 含义 |
|---|---|---|
| `identify_only` | 仅识别身份 | 主体可识别，但交易层面未闭环；不可直接付款 |
| `proceed_with_gaps` | 可推进但需补证 | 关键要素大部分可核，缺口明确且可补 |
| `hold` | 暂停推进 | 存在必须先澄清的主体或收款问题 |
| `insufficient` | 证据不足 | 无法识别主体 |

> **没有"风险等级"字段，也不允许新增。** validate.py 会把 `risk_score`/`score`/`rating` 判为阻断项。

---

## 3. sections（正文区块）

```jsonc
{ "id": "s01", "no": "01", "title": "企业身份", "sub": "副标题", "blocks": [ … ] }
```

### 区块类型

| type | 用途 | 关键字段 |
|---|---|---|
| `verdict` | 结论块 | `kicker, headline, text, rows:[{k,v}]` |
| `lead` | 说明段（可含 `<b>`） | `text, muted` |
| `note` | 提示条 | `text, tone:"warn"` |
| `boundary` | 五态口径卡 | `items:[{t,d}], foot` |
| **`table`** | **通用表（最常用）** | 见下 |
| `hierarchy` | 集团层级图 | `layers:[{layer, nodes[]}], note` |
| **`matrix_map`** | 主体一致性矩阵 | `rows:[{item,a,b,c,state,evid,note}], foot` |
| `chain` | 单据链条 | `items:[{code,name,role,self}]` |
| `steps` | 下一步步骤 | `items:[{n,t,d}]` |
| `risknotes` | 要点卡 | `items:[{t,d}]` |
| `grid` | 卡片两列 | `cards:[{h,text}]` |

### table 约定（重要）

```jsonc
{
  "type": "table", "name": "identity", "title": "身份要素逐项核验",
  "columns": [
    { "h": "要素", "width": "130px" },
    { "h": "核验结果" },
    { "h": "状态", "align": "c", "width": "96px" },
    { "h": "证据", "align": "c", "width": "90px" }
  ],
  "rows": [
    ["法定名称", "…", "已核实", "E04,E05"],
    ["商业登记号 CR", "…", "未知", "—"]
  ],
  "foot": "表注（可选）"
}
```

**列位置约定**：
- 状态列 = **倒数第二列**
- 证据列 = **最后一列**（`"E04,E05"` 逗号分隔）
- `rows` 的列数**必须等于** `columns` 的列数（不相等时渲染器会警告并按原样输出）

状态值可写中文或英文：`已核实/verified`、`存在疑点/doubt`、`未核实/unverified`、`未知/unknown`、`不适用/na`。

---

## 4. evidence（证据）

```jsonc
{
  "id": "E05",
  "claim": "被核验的事实（一句话）",
  "publisher": "发布方",
  "type": "industrial_db",       // official | regulatory | media | directory | industry_db | encyclopedia | mock
  "grade": "secondary",          // primary | secondary | tertiary | mock
  "stance": "support",           // support | context | note
  "url": "https://…",
  "published": "2023-05-04",
  "accessed": "2026-10-20",
  "quote": "逐字原文摘录",
  "used_for": "支撑哪条结论",
  "note": "局限说明"
}
```

全部 9 个字段**必填**（`note` 可为空字符串，`url` 可为空但会提示）。

---

## 5. documents（文件核验）

```jsonc
{
  "id": "F01", "name": "形式发票 PI", "type": "PI",   // PI|CR|SDS|COA|BANK|CONTACT|PROFILE|CATALOGUE|CERT
  "holder": "名义持有人", "issuer": "出具方", "pages": "1 页",
  "provided": true, "mock": true,
  "checks": [ { "k": "CR 号载明", "ok": false, "v": "未载" } ],
  "note": ""
}
```

- `mock: true` → 界面显示紫色「模拟」标记，且永不计入"已核实"
- 状态自动推导：未提供→未知；模拟且有 ✕ →存在疑点；全部 ✓ →已核实

---

## 6. entity_map（主体映射）

```jsonc
{ "layer": "生产层", "entity": "主体全称", "kind": "manufacturer",
  "jurisdiction": "Saudi Arabia", "evidence": "E04,E05",
  "state": "已核实", "note": "说明" }
```

`kind`：`group_parent` / `manufacturer` / `manufacturer_jv` / `contract_party` / `exporter` / `beneficiary` / `agent` / `distributor` / `trader`

---

## 7. gaps（待确认事项）

```jsonc
{ "id": "G01", "area": "企业身份", "gap": "缺 CR 号",
  "impact": "无法唯一识别主体", "action": "索取 CR 证书",
  "owner": "采购", "priority": "高" }   // 高|中|低
```

---

## 8. rfi（英文询证）

```jsonc
{ "title": "Supplier Due-Diligence Enquiry — [Product]",
  "to": "…", "from": "…", "date": "YYYY-MM-DD", "ref": "Buyer-DDQ-XXXX",
  "intro": "…",
  "clauses": [ { "id": "A1", "text": "Confirm the full legal name …" } ] }
```

条款**必须是英文**（validate 会检查）。

---

## 9. 校验规则（validate.py）

| 编号 | 规则 | 级别 |
|---|---|---|
| F01 | 引用的证据 ID 必须存在 | 阻断 |
| F02 | 证据 9 字段齐全，grade/stance 合法 | 阻断 |
| F03 | 「已核实」行必须引用证据 | 阻断 |
| F04 | 「已核实」不得只依赖三手来源；单一二手来源给警告 | 阻断/警告 |
| F05 | 「已核实」不得引用模拟件 | 阻断 |
| F06 | 不得出现任何评分字段或评分数值 | 阻断 |
| F07 | section 结构完整 | 阻断 |
| F08 | 有「未知」就必须有 gap 记录 | 阻断 |
| W01 | 「存在疑点」行建议挂证据 | 警告 |
| W02 | 未知占比 >60% 提示研究不足 | 警告 |
| W03 | 证据超过 3 年（用于已核实）提示刷新 | 提示 |
| W04 | 中文法定名建议补英文名 | 警告 |
| W05 | 有 PI/银行信息却无一致性矩阵 | 阻断 |
| RFI | 条款须为英文、≥8 条、含 to/from/ref/intro | 阻断/警告 |

---

## 10. 渲染命令

```bash
python scripts/validate.py project.json --strict
python scripts/build_all.py project.json -o out/
# 或分开
python scripts/build_html.py project.json -o out/
python scripts/build_xlsx.py project.json -o out/     # 需 openpyxl
```
