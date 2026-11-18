# 数据契约：data.json 全字段说明

一个 `data.json` 就是一次核验。渲染器与自检脚本只认这份契约；**任何产品知识都只写在 findings / checklist 里，脚本里没有品名词。**

```json
{
  "schema_version": "1.0",
  "title": "…", "as_of": "YYYY-MM-DD",
  "meta": {...}, "subject": {...}, "product": {...},
  "classification_checklist": [...], "supplier_requirements": [...],
  "erp": {...}, "certs": [...], "crosscheck": [...], "oddities": [...],
  "request_list": [...], "manual_check": [...], "draft": {...},
  "risks": [...], "assessment": {...}, "evidence": [...],
  "scans": [...], "scan_note": "..."
}
```

---

## 0. 顶层

| 字段 | 必填 | 说明 |
|---|---|---|
| `schema_version` | ✓ | 固定 `"1.0"` |
| `title` | ✓ | 报告标题，含主体与产品 |
| `as_of` | ✓ | **全表唯一时间基准**；所有有效期判断相对它 |
| `meta.record_id` | ✓ | 记录号（建议 `QC-<产品>-<主体缩写>-<日期>`），用于索证编号与保存记录 |
| `meta.prepared_by` / `prepared_at` / `generated_at` / `scene` / `data_classification` | | 展示用 |

## 1. `subject` 供应商主体

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | ✓ | 企业全称（逐字） |
| `uscc` | ✓ | 统一社会信用代码；渲染前会做 GB 32100 校验码复算 |
| `uscc_source` | | 代码从哪里来（必须写清，不得用"公开信息"糊弄） |
| `aliases` | | 曾用名/简称 |
| `biz_lic_no` | | 旧 15 位工商注册号（有校验提示） |
| `legal_rep` / `capital` / `founded` / `types` / `credit_status` | | 工商字段 |
| `reg_addr` / `site_addr` | | 注册地址 / 生产或经营地址（常不一致，必须分别填） |
| `business_scope` | | 经营范围原文；**不得据此推断许可** |
| `id_note` / `chain` / `scope_note` | | 身份核验要点 / 关系链 / 经营范围≠许可范围的提醒 |
| `status` | ✓ | `已核实` 或 `待核验` |

## 2. `product` 产品

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` / `cas` / `spec` | ✓ | 名称、CAS、**浓度与规格** |
| `aliases` / `form` / `grade_std` / `packing` / `qty` / `usage` / `site` / `sds` | | 物料档案 |
| `verdict_summary` / `verdict_ok` | | 一句话定性 + 布尔（用于徽标） |
| `findings[]` | ✓ | 见下 |
| `gaps[]` | | 资料缺口（SDS、COA、规格书…） |

`findings[]` 每条：

```json
{"item":"是否属于易制爆危险化学品",
 "value":"属于。…",
 "verdict":"confirmed",              // confirmed | not_confirmed | pending
 "verdict_label":"已确认",           // 可选，覆盖默认标签
 "basis":"目录名称 + 条目号 + 文号",
 "condition":"适用条件/例外"}
```

> `verdict` 语义：`confirmed` = 已确认（结论成立且有依据）；`not_confirmed` = 未确认（**不等于不成立**）；`pending` = 待核验（缺资料/缺目录原文）。

## 3. `classification_checklist[]`

```json
{"id":"K01","item":"《危险化学品目录（2015版）》","verdict":"confirmed",
 "note":"…逐条核对说明…","basis":"文号/条款","impact":"若成立会触发什么义务"}
```

## 4. `supplier_requirements[]`

```json
{"role":"生产企业","licence":"危险化学品安全生产许可证","required":"必须",   // 必须 | 视情形
 "basis":"条例第X条 + 规章名","scope_check":"范围覆盖怎么核"}
```

`supplier_lead`：一段"角色→证照"的推理说明；`supplier_notes[]`：补充提醒。

## 5. `erp` 采购方

```json
{"name":"…","uscc":"…","usage":"…","storage":"…",
 "obligations":[{"item":"…","status":"必须","basis":"…","trigger":"触发条件","action":"落地动作/证据"}],
 "notes":["…"]}
```

`status` 取 `必须 / 视情形 / 建议`。

## 6. `certs[]` 证照（核心表）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | | 缺省自动 `C01…` |
| `name` / `type` | ✓ | 证照名称 / 分类 |
| `no` | | 证书编号；**未取得就留空**（页面显示"待核验"），不得编造 |
| `issuer` | | 发证机关 |
| `valid_from` / `valid_to` | | `valid_to` 可为 `"长期"` |
| `need` | ✓ | `required` / `conditional` / `none` |
| `status` | ✓ | `verified` / `mismatch` / `pending` / `no_public`（`expired` 由日期自动推导） |
| `cover` | ✓ | `cover` / `partial` / `not_cover` / `unknown` |
| `scope` | | 许可/核准范围**证载原文** |
| `coverage` | | 范围与本采购的比对说明 |
| `field_source` | ✓ | 字段来源：公开来源/上传扫描件/未取得 |
| `public_state` | | 公开状态：官网公开/可查询未取得/未发现公开记录… |
| `evidence_id` | ✓（verified 时） | 对应 `evidence[].id` |
| `url` | | 公开来源链接 |
| `crosscheck[]` | | 该证的交叉核验记录 |
| `discrepancies[]` | | 已发现的不一致点 |
| `note` | | 核验说明与缺口 |
| `subject_match` / `activity_match` / `coverage_note` | | 供 Excel「07 有效期与范围比对」使用 |

> 状态口径见 `references/judgement-rules.md`。**`verified` 必须同时有 `evidence_id` 或 `url`**，否则 `validate.py` 判 FAIL。

## 7. `crosscheck[]`

```json
{"item":"注册地址","left":"证照/供应商材料A侧","right":"主管部门公示B侧",
 "result":"一致","note":"处理意见"}      // 一致 | 部分一致 | 不一致
```

## 8. `oddities[]`

```json
{"item":"疑点","found":"已查到的事实","meaning":"可能解读（不作结论）","verify":"如何核实"}
```

## 9. `request_list[]` 索证清单

```json
{"code":"R01","cert":"证照/资料名","issuer":"出具机关","priority":"P0","reason":"为什么必须","ask":"要确认的具体问题"}
```

- `priority`：`P0`（不取得不得下单）/ `P1`（卡合同或首批发货）/ `P2`（档案完善）。
- 渲染时会**自动派生**：凡 `cert.need == required` 且状态非 `verified/expired` 的证照，若清单里没有同名项，会自动追加（标 `AUTO`）。人工清单优先保留编号。

## 10. `manual_check[]` 人工核验事项

```json
{"item":"…","why":"为什么必须人工","method":"核实方法","evidence":"需要的证据","owner":"责任人"}
```

## 11. `draft`

```json
{"intro":"说明这段话是什么","body":"可直接发送的邮件/公函正文（\\n 换行）"}
```

## 12. `risks[]`

```json
{"title":"…","level":"高","ref":"C02 / R01","fact":"事实","impact":"后果","action":"处置"}
```

`level`：`高 / 中 / 低`。

## 13. `assessment`

```json
{"grade_code":"G2","grade":"有条件推进（资料缺口型）","one_liner":"…","summary":"…",
 "verdict":{"键":"值"},"gates":[{"code":"GATE-1","name":"证照闸门","text":"…"}],
 "statements":[["可以写…","不能写…"]],"next_steps":[["T+0","…"]]}
```

`grade_code` 统一用 `G1`（可放行）/ `G2`（有条件推进，资料缺口）/ `G3`（暂不能放行）/ `G4`（不建议合作）。

## 14. `evidence[]`

```json
{"id":"E01","kind":"行政法规","title":"…","publisher":"…","date":"…","url":"…","supports":"支撑了哪几条"}
```

`kind` 建议：行政法规 / 部门规章 / 部门公告 / 规范性文件 / 国家标准 / 地方细则 / 上市公司公告 / 监管信息公开 / 企业官网 / 上传件。

## 15. `scans[]`

```json
{"file":"scans/01_营业执照_样例.svg","title":"…","kind":"MOCK · 模拟件","mode":"mock"}
```

- `mode`：`mock`（模拟演示件，**必须**标注）/ `upload`（真实上传件）/ `public`（官网下载件）。
- 未标注 `mode` → `validate.py` 判 FAIL（防止模拟件混入真实档案）。

---

## 命名与路径约定

- 示例目录建议 `<产品编码>/data.json` + `<产品编码>/scans/` + 输出到 `<产品编码>/out/`（HTML 用相对路径 `scans/` 引用扫描件，所以输出目录要与 scans 同级下的 `out/`）。
- 输出文件名由渲染器按 `主体_产品` 生成，可用 `--name` 覆盖。
