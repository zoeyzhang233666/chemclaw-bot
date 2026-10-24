# references/data-contract.md — data.json 字段契约

> 所有渲染器（HTML / XLSX）只认这份契约。换产品时**只改 data.json**，不改脚本。
> 模板见 `templates/data.template.json`。

---

## 1. 顶层结构

| 键 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema_version` | str | ✓ | 固定 `"1.0"` |
| `title` | str | ✓ | 报告标题 |
| `as_of` | `YYYY-MM-DD` | ✓ | **时间基准**。所有时效判断相对此日期 |
| `meta` | obj | ✓ | 见 1.1 |
| `inputs` | obj | ✓ | 见 2 |
| `product_identity` | obj | ✓ | 见 3 |
| `hs_candidates` | arr | ✓ | 见 4 |
| `hs_verdict` | obj | ✓ | 见 5 |
| `tax_rates` | obj | ✓ | 见 6 |
| `regulation_checklist` | arr | ✓ | 见 7 |
| `danger_distinction` | obj | ✓ | 见 8 |
| `transport` | obj | ✓ | 见 9 |
| `labels_packaging` | obj | ✓ | 见 10 |
| `documents` | arr | ✓ | 见 11 |
| `uploaded` | arr | ✓ | 见 12 |
| `gaps` | arr | ✓ | 见 13 |
| `responsibilities` | arr | ✓ | 见 14 |
| `to_confirm` | arr | ✓ | 见 15 |
| `timeline` | arr | | 见 16 |
| `supplier_request_en` | obj | ✓ | 见 17 |
| `sources` | arr | ✓ | 见 18 |
| `assessment` | obj | ✓ | 见 19 |
| `calculation` | obj | | 见 20 |

### 1.1 `meta`

```json
{
  "record_id": "ID-H2O2-KR-20261020",
  "prepared_by": "…", "prepared_at": "2026-10-20", "generated_at": "2026-10-20",
  "scene": "外贸采购 / 查进口资料要求",
  "data_classification": "内部（含模拟件）",
  "product_scope_note": "本结论绑定了哪些产品要素，任一变化须重跑",
  "methodology_version": "1.0",
  "demo_notice": "演示声明（有模拟件时必填）"
}
```

> `product_scope_note` 是**范围声明**：写清本底稿的结论只对哪一组输入成立。

---

## 2. `inputs` — 输入要素

| 键 | 说明 |
|---|---|
| `origin_country` / `origin_note` | 来源国；是否 WTO 成员、是否有自贸协定、是否受制裁 |
| `supplier` / `importer` | 供应商与进口企业（可用脱敏名） |
| `product_name_cn` / `product_name_en` | 中英文品名 |
| `cas` | **主成分** CAS（混合物时主成分放这里，其余放 composition） |
| `un_no` | UN 编号（非危险货物可留空） |
| `concentration` | 浓度，**必须写明质量分数还是体积分数** |
| `composition[]` | `{name, ename, cas, pct_min, pct_max, role}`。**稳定剂/添加剂必须逐个列出** |
| `physical_form` | 物态（是否水溶液） |
| `grade` | 工业级 / 试剂级 / 食品级… |
| `exec_standard` | 执行标准 |
| `usage` | 用途（越具体越好） |
| `usage_sensitivity` | 用途敏感性（是否食品/药品/消毒/涉军） |
| `packing` / `package_type` / `gross_weight` / `hs_packing_spec` | 包装描述、容器类型、单件毛重、**申报用「包装规格」表述** |
| `qty` | 数量（带单位，便于算税） |
| `transport_mode` | 海运/空运/陆运；是否散装 |
| `incoterm` / `pol_pod` / `eta` / `price_terms` | 贸易术语、起运目的港、预计到港、价格条款 |

**为什么 composition 要细到稳定剂**：危险化学品目录中「溶液」条目的适用前提是「仅含稳定剂/惰性化学品」。缺这一项，判定只能停在「视条件适用」。

---

## 3. `product_identity`

```json
{
  "identity_verdict": "confirmed | partial | pending",
  "one_liner": "一句话身份判断（给管理层看）",
  "confirmed": ["已取得的证据，按文件对应"],
  "unconfirmed": ["仍缺的要素"],
  "risk_points": [{"item": "…", "why": "…", "action": "…"}]
}
```

规则：`identity_verdict = "confirmed"` 时 `unconfirmed` 必须为空（校验器会查）。

---

## 4. `hs_candidates[]`

```json
{
  "code": "2847.00.0000", "desc": "…", "rank": 1,
  "confidence": "高 | 中 | 低",
  "basis": "章注/品目条文的推理链",
  "tests": "成立条件（可被第三方验证）",
  "alternatives": "不成立时去哪",
  "source": "S06,S18"
}
```

必须至少有一条 `rank = 1`，且 `hs_verdict.recommended` 必须在候选里。

---

## 5. `hs_verdict`

| 键 | 说明 |
|---|---|
| `recommended` | 推荐编码 |
| `uncertainty` | **必填**，写清不确定点 |
| `need_classification_ruling` | 「是」/「否（理由）」 |
| `declaration_elements[]` | 规范申报要素，**按当年税则顺序** |
| `declaration_example` | 用 `|` 分隔的填报示例 |
| `ciq_codes[]` / `ciq_note` | CIQ 扩展码与说明 |

---

## 6. `tax_rates`

```json
{
  "tariff_year": "2026", "hs": "2847000000",
  "mfn": {"rate": "5.5%", "note": "…"},
  "provisional": {"rate": "无", "note": "…"},
  "general": {"rate": "30%", "note": "…"},
  "vat": {"rate": "13%", "note": "…"},
  "consumption_tax": {"rate": "0", "note": "…"},
  "fta": [{"scheme": "…", "rate_hint": "…", "status": "verified|disputed|pending|claimed",
           "condition": "…", "source": "S19"}],
  "fta_note": "为什么这些税率不能直接用",
  "calc_note": "税费计算口径"
}
```

`status` 语义：
- `verified` 已核实（可写进结论）
- `disputed` 不同来源互相矛盾 → 必须同时在 `to_confirm` 里有一条
- `pending` 未核验
- `claimed` 仅供应商/货代口头声称

---

## 7. `regulation_checklist[]`

```json
{
  "id": "R01", "layer": "危险化学品管理", "item": "是否列入《危险化学品目录》",
  "verdict": "applies | conditional | pending | not_applies",
  "conclusion": "本单结论（人话）",
  "basis": "条文依据（到条/项）",
  "condition": "适用条件（applies/conditional 时必填）",
  "impact": "触发哪些义务",
  "owner": "责任方",
  "source": "S02,S03",
  "confidence": "high | medium | low"
}
```

**必需的层（方法学要求，校验器会查）**：危险化学品管理、运输、检验检疫、用途专项。
建议再覆盖：易制爆、两用物项、包装容器、新化学物质、储存安全。

---

## 8. `danger_distinction`

```json
{
  "lead": "两套体系为何必须分开",
  "chemical": {"regime", "applicable", "entry", "threshold", "consequence"},
  "goods":    {"regime", "applicable", "cls", "subsidiary", "un", "pg",
               "proper_shipping_name", "threshold", "consequence"},
  "matrix": [{"case", "chem", "goods", "note"}],
  "common_errors": ["…"]
}
```

`chemical.regime` 与 `goods.regime` **不得相同**（校验器会查）。
`matrix` 至少 3 行，且应覆盖阈值两侧。

---

## 9. `transport`

`mode, regime_standard, domestic_standard, un, proper_shipping_name_en, class, subsidiary_risk, packing_group, labels[], packing_instruction, segregation[], stowage[], emS, notes[]`

`transport.un` 必须与 `danger_distinction.goods.un` 一致。

---

## 10. `labels_packaging`

```json
{
  "ghs_label": {"required", "lang", "std", "pictograms[]", "signal_word",
                "h_statements[]", "p_statements[]", "elements[]", "note"},
  "transport_marks": ["…"],
  "package": {"type", "cert", "domestic_note", "compat"},
  "issues": [{"item", "level": "高|中|低", "fix"}]
}
```

`note` 必须说明：H/P 码是**建议口径**，须由供应商按 GB 30000 分项确认。

---

## 11. `documents[]`

```json
{
  "id": "D01", "group": "海外供应商资料", "name_cn": "…", "name_en": "…",
  "required": "必须 | 视情形 | 建议",
  "basis": "依据条文",
  "content_check": "必备关键字段清单",
  "uploaded_id": "U01 或 空",
  "status": "ok | partial | missing | pending | expired | na",
  "issue": "当前问题",
  "owner": "海外供应商 | 进口商 | 承运人 | 报关代理 | 第三方检测机构",
  "source": "S05"
}
```

规则：
- `status` 为 `partial` 时 `issue` 必填；
- `uploaded_id` 必须指向存在的上传件；
- `required = 必须` 时 `basis` 必填。

---

## 12. `uploaded[]`

```json
{
  "id": "U01", "file": "SDS_xxx.pdf（模拟）", "type": "SDS|COA|PI|TDS|标签",
  "lang": "en|zh|ko", "is_mock": true, "mock_note": "…", "received": "2026-10-12",
  "extracted": [{"field": "…", "value": "…", "page_ref": "第3节"}],
  "checks": [{"id": "C-U01-1", "item": "…", "result": "pass|fail|warn|na", "note": "…"}],
  "verdict": "usable | usable_with_fix | not_usable",
  "verdict_note": "一句话理由"
}
```

规则：
- `is_mock = true` 时 `mock_note` 必填，且文件名建议带「模拟」；
- `extracted` 必须写 `page_ref`（否则不可复核）；
- `checks` 不得为空。

---

## 13. `gaps[]`

```json
{"id": "G01", "priority": "P0 | P1 | P2", "missing": "…", "why": "…",
 "ask": "怎么要（具体动作）", "related_doc": "D02", "owner": "…", "blocking": "是 | 否"}
```

P0 = 不取得不得报关/不得使用；P1 = 影响税费、时效或质量；P2 = 档案完善。

---

## 14. `responsibilities[]`

```json
{"actor": "海外供应商", "items": ["…"], "notes": "…"}
```

`actor` 必须能归一化到：`海外供应商 / 进口商 / 承运人 / 报关代理 / 第三方检测机构 / 监管机构`。

---

## 15. `to_confirm[]`

```json
{"id": "Q01", "topic": "…", "why": "为何不能自判", "who": "谁确认",
 "how": "怎么核实", "impact_if_wrong": "判断错的代价", "severity": "高 | 中 | 低"}
```

五个字段全必填。

---

## 16. `timeline[]`

```json
[{"t": "T-45", "action": "…", "owner": "…"}]
```

---

## 17. `supplier_request_en`

```json
{
  "title": "Documentation Request — …",
  "intro": "英文正文（可含中文法规名，但正文用英文）",
  "items": [{"no": "1", "doc": "…", "detail": "…", "due": "URGENT — within 3 working days"}],
  "closing": "…"
}
```

要求：**英文撰写**；每项写清「这份文件必须包含什么」与「时限」。

---

## 18. `sources[]`

```json
{"id": "S01", "kind": "法律|行政法规|公告|国家标准|国际规则|政务数据库",
 "title": "…", "publisher": "…", "date": "发布/实施", "effective": "现行有效|部分替代|已废止|未核实",
 "url": "https://…", "supports": "支撑了哪条结论", "accessed": "YYYY-MM-DD",
 "tier": "A|B|C"}
```

`tier` 语义见 `verification-rules.md` 第 1 节。**不得**让任何监管结论只由 C 级来源支撑。

---

## 19. `assessment`

```json
{
  "grade": "auto | A|B|C|D",
  "grade_text": "由闸门自动推导",
  "one_liner": "总体结论一段话",
  "verdict": {"产品身份": "…", "HS归类": "…", "监管属性": "…", "税费": "…", "运输与包装": "…", "单证完备度": "…"},
  "statements": [["可以写…", "不能写…"]],
  "next_steps": [["T+0", "…"]]
}
```

`grade = "auto"` 时由 `imrules.overall_grade()` 按六道闸门计算：

```
D — 必须件缺失/过期，或关键闸门 fail
C — 待确认闸门 ≥ 3
B — 待确认闸门 1~2
A — 全部通过
```

---

## 20. `calculation`

```json
{"cif_usd": 24200, "fx": 7.118, "cif_cny": 172255.6,
 "duty_rate": "5.5%", "duty_cny": 9474.06,
 "vat_base_cny": 181729.66, "vat_rate": "13%", "vat_cny": 23624.86,
 "total_tax_cny": 33098.92,
 "fta_scenario": [{"rate": "…", "duty": 0, "note": "…"}],
 "note": "汇率与估算口径说明"}
```

校验器会重算 `cif_cny × duty_rate` 与 `vat_base_cny × vat_rate`，误差超过 1% 报错。
