# 数据契约（Data Schema）

`inquiry.json` 是唯一数据源。HTML 和 Excel 都由它生成，**不要手改产物**。

## 顶层结构

```jsonc
{
  "meta":         { ... },     // 报告元信息与打标
  "inquiry":      { ... },     // 询盘原文
  "extraction":   [ ... ],     // 提取字段
  "subject":      { ... },     // 主体识别
  "domains":      [ ... ],     // 域名核验
  "email_auth":   [ ... ],     // 发信认证
  "matrix":       [ ... ],     // 联系方式一致性矩阵
  "business_fit": { ... },     // 业务相关性
  "checks":       [ ... ],     // 五区块核验（核心）
  "linkage":      [ ... ],     // 同名/错配排查
  "risks":        [ ... ],     // 风险
  "sources":      [ ... ],     // 来源库
  "requests":     [ ... ],     // 资料清单
  "actions":      [ ... ],     // 行动
  "messages":     [ ... ],     // 英文话术
  "boundaries":   [ ... ]      // 使用边界
}
```

## meta

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | str | ✔ | 报告标题 |
| `subtitle` | str | | 副标题，写主体与产品 |
| `as_of` | `YYYY-MM-DD` | ✔ | 核验基准日 |
| `synthetic` | bool | ✔ | `true` = 模拟/演示数据（页面会出现横幅） |
| `synthetic_note` | str | 模拟时必填 | 说明哪些字段是虚构的 |
| `disclaimer` | str | ✔ | 免责声明 |
| `client_slug` | str | | 用于默认文件名 |
| `inquiry_id` / `product` / `product_spec` / `quantity` / `incoterm` / `packaging` / `hs_code` / `prepared_by` | str | | 出现在封面 |

## inquiry

```jsonc
{
  "subject": "...", "from": "Name <mail>", "from_name": "...",
  "to": "...", "date": "...", "reply_to": "...",
  "body_lines": ["Dear ...", ""],          // 每行一个字符串，保留空行
  "attachments": [{"name": "x.pdf", "note": "..."}],
  "notes": ["提取阶段的观察，不是结论"]
}
```

## extraction[]

```jsonc
{
  "id": "X01",                // 可省略，自动编号
  "field": "公司英文名",
  "value": "PT Sinar Kaca Nusantara",
  "evidence": "邮件正文 + 签名栏",   // 原文出处，必填
  "confidence": "high|medium|low",
  "note": "PT 前缀需逐字比对"
}
```

## subject

```jsonc
{
  "name_extracted": "...",
  "name_normalized": "...",
  "registry_check": { "portal": "...", "search_terms": ["..."], "result": "...",
                      "result_note": "...", "status": "verified|unverified" },
  "nib_oss":   { ... },   // 各国换名字：nib_oss / mca_cin / gstin / mst / cnpj
  "npwp_tax":  { ... },
  "customs_id":{ ... },
  "summary_rows": [ {"k": "登记全称", "v": "...", "verified": false} ]
}
```

> `result_note` 是必填项中最重要的一条：它说明"为什么这个检索结果不能直接当结论"。

## matrix[] / email_auth[]

| 字段 | 取值 |
|---|---|
| `mismatch` | `same` / `partial` / `different` / `unknown` / `misattribution` |

`matrix` 必含四类 `item`：名称、地址、电话、邮箱（校验器会检查）。
`email_auth` 建议含：发件域名、Reply-To、SPF、DKIM/DMARC、Received 链、签名与抬头一致性。

## business_fit

```jsonc
{
  "headline": "一句话业务相关性判断",
  "product_use": "产品用途说明（为什么这个行业会买）",
  "demand_math": [ {"label": "...", "value": "...", "note": "..."} ],
  "keywords": [ {"id":"B01","kode":"23111","label":"...","why":"...","status":"unverified","note":"..."} ],
  "signals":  [ {"id":"S01","signal":"...","status":"verified","strength":"high","note":"..."} ]
}
```

`keywords.kode` 放该国的业务分类码（印尼 KBLI / 印度 NIC / 巴西 CNAE），这是业务相关性的硬证据。

## checks[]（核心）

```jsonc
{
  "id": "K01",
  "section": "A|B|C|D|E",
  "title": "企业是否真实存在（登记检索）",
  "question": "在登记册上，能否检索到完全一致的主体？",
  "status": "verified|discrepancy|unverified|not_applicable",
  "severity": "high|medium|low",       // 仅 discrepancy 必填
  "finding": "我看到什么（事实陈述，不推断）",
  "verified_facts": ["..."],
  "doubts": ["必须有具体矛盾"],
  "unknowns": ["..."],
  "boundary": "为什么这个结论不能往前推一步",
  "source_ids": ["SRC01"],
  "next_ids": ["Q01"],                 // 指向 requests[].id
  "action": "下一步动作"
}
```

### 校验规则（`validate.py` 强制执行）

- `status=verified` → `source_ids` 必填，且每个 id 存在于 `sources`
- `status=discrepancy` → `doubts`、`boundary`、`next_ids` 三项必填
- `section` 必须是 A–E；A–D 区块至少各一条
- `next_ids` 必须指向存在的 `requests[].id`

## linkage[]

```jsonc
{ "id":"L01", "name":"近似名主体", "relation":"name_collision|domain_link|role_ambiguity|impersonation",
  "detail":"...", "rule":"只有登记号/NIB 相同才判定同一主体。" }
```

**必须有一条 `name_collision`**（校验器会警告）。

## risks[]

```jsonc
{ "id":"R01", "category":"主体身份", "severity":"high", "status":"unverified",
  "fact":"看到了什么", "impact":"影响我方什么", "action":"做什么", "source_ids":["SRC01"] }
```

## sources[]

```jsonc
{ "id":"SRC01", "name":"AHU Online", "org":"Kemenkumham RI", "url":"https://ahu.go.id/",
  "grade":"A|B|C|D", "kind":"registry|regulation|sanctions|method|industry|counterparty_document|other",
  "date":"2026-10", "retrieved":"2026-10-19", "note":"能证明什么/不能证明什么", "reliability":5 }
```

`kind` 为 `registry|sanctions|regulation` 时 `url` 必填。

## requests[]

```jsonc
{ "id":"Q01", "priority":"P0|P1|P2", "category":"主体|业务|地址|产能|合同|渠道|技术|付款",
  "zh":"中文表述", "en":"English wording（必填，会直接发给对方）",
  "why":"为什么需要（必填）", "source_ids":["SRC02"] }
```

## actions[]

```jsonc
{ "id":"T01", "phase":"T+0|T+1|…", "action":"...", "detail":"...",
  "owner":"...", "priority":"P0", "status":"open|doing|done" }
```

## messages[]

```jsonc
{ "id":"MSG01", "title":"首次回信 · 索取 P0 注册资料", "channel":"邮件",
  "purpose":"这封信要达成什么", "body_en":"Subject: ...\n\nDear ...,\n...",
  "notes":["写作要点"] }
```

`body_en` 必须含 `Subject:` 行。

## 命名与 ID 约定

| 前缀 | 用途 | 示例 |
|---|---|---|
| `X` | 提取字段 | X01 |
| `B` / `S` | 业务关键词 / 业务信号 | B01 / S01 |
| `K` | 核验项 | K01 |
| `M` | 一致性矩阵 | M01 |
| `L` | 关联主体 | L01 |
| `R` | 风险 | R01 |
| `SRC` | 来源 | SRC01 |
| `Q` | 资料索取 | Q01 |
| `T` | 行动 | T01 |
| `MSG` | 话术 | MSG01 |

ID 可以省略，脚本会自动补；但**显式写出来**更利于后续引用。
