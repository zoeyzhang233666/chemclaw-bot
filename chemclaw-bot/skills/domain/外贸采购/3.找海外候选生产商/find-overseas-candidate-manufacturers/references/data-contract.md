# 数据契约：`case_input.json` 与 `case_output.json`

所有脚本（`build_report.py`、`build_workbook.py`、`self_check.py`）只依赖这两个文件，因此**换产品/换国家不需要改代码**。

---

## `case_input.json`

```json
{
  "case_id": "OSM-<产品缩写>-<国家代码>-<YYYYMMDD>",
  "country": {"zh": "沙特阿拉伯", "en": "Saudi Arabia", "iso2": "SA"},
  "destination": {"zh": "中国", "en": "China"},
  "product": {
    "name_zh": "乙二醇（单乙二醇 / MEG）",
    "name_en": "Monoethylene glycol (MEG)",
    "abbr": "MEG",
    "cas": "107-21-1",
    "hs_cn": "2905.31.00.00",
    "spec_summary": "…",
    "process_route": "…",
    "packaging": "…",
    "related_products_excluded": ["DEG", "TEG", "丙二醇", "聚醚多元醇"]
  },
  "buyer_context": {
    "quantity": null,
    "only_actual_manufacturers": true,
    "certifications_needed": null,
    "packaging_needed": null,
    "destination_port": null
  },
  "research_date": "2026-10-20",
  "notes": "…"
}
```

> 采购买漏的字段（quantity / certifications 等）一律 `null`，报告里显示"未提供 — 需采购方补充"，**不要编造**。

---

## `case_output.json`

```json
{
  "meta": {
    "report_id": "...",
    "title": "...",
    "subtitle": "...",
    "product": {
      "name_cn": "...", "name_en": "...", "cas": "...",
      "hs_cn": "...", "hs_un": "...",
      "spec_summary": "...", "packaging": "...", "process_route": "..."
    },
    "buyer_context": {
      "origin": "...", "destination": "...", "intent": "...",
      "quantity": "...", "only_actual_manufacturers": "...",
      "certifications_needed": "...", "packaging_needed": "..."
    },
    "research_date": "YYYY-MM-DD",
    "evidence_grade_legend": [
      {"grade": "A", "label": "...", "def": "..."},
      {"grade": "B", "label": "...", "def": "..."},
      {"grade": "C", "label": "...", "def": "..."},
      {"grade": "D", "label": "...", "def": "..."}
    ],
    "disclaimer": "..."
  },

  "groups": [
    {"id": "G-SABIC", "name": "...", "name_en": "...", "type": "...", "note": "..."}
  ],

  "companies": [
    {
      "id": "C-SHARQ",
      "rank": 1,
      "legal_name": "...",            // 必填
      "legal_name_ar": "...",         // 可选，当地语名
      "cn_name": "...",
      "entity_type": "MANUFACTURER | JV_MANUFACTURER | GROUP_SALES | AFFILIATE_SALES | TRADER | AGENT | UNKNOWN",
      "entity_type_label": "制造企业（工厂主体）",
      "grade": "A | B | C | D",
      "grade_reason": "...",          // 必填：为什么判这个级
      "group": "G-SABIC",             // 对应 groups[].id
      "ownership": "...",
      "established": "...",
      "hq": "...",
      "country": "...",
      "site": "...",                  // 实际工厂所在地，用于筛选
      "product_page": "...",
      "website": "...",
      "official_channels": [
        {"channel": "...", "value": "...", "status": "已核验 | 待核验 | ..."}
      ],
      "products_specs": [
        {"product": "...", "grade": "...", "spec": "...", "source": "S3 | 待核验"}
      ],
      "capacity": {
        "meg_mtpa": "...",            // 通用版可改名为 expr；报告统一读 capacity 内的主值
        "unit": "...",
        "detail": "口径明细与冲突",
        "caveat": "当前可供货能力判断"
      },
      "process": "...",
      "evidence": [
        {"id": "E1", "type": "官网产能表", "grade": "直接", "src": "S3",
         "text": "原文摘要", "conf": "高 | 中 | 低"}
      ],
      "certifications": [{"cert": "...", "status": "..."}],
      "export_info": "...",
      "risks": ["..."],
      "open_questions": ["QS-01"]
    }
  ],

  "trade_notes": [
    {"type": "平台挂牌/贸易商", "desc": "...", "grade": "D"}
  ],

  "market_context": [
    {"claim": "...", "source": "S23", "conf": "中高"}
  ],

  "questions": [
    {"id": "QS-01", "company": "C-SHARQ", "q": "..."}
  ],

  "sources": [
    {"id": "S3", "title": "...", "url": "https://...", "date": "...",
     "access": "YYYY-MM-DD", "status": "已核验 | 检索索引命中 | 直连失败 | 待下载"}
  ]
}
```

---

## 字段规则

1. **`grade` 与 `entity_type` 正交**，两者都必须有。
2. **`grade_reason` 必填**，不能写"看起来很专业"这类空话，必须点到具体证据。
3. **`evidence[].src` 必须能在 `sources[]` 里找到**；证据文本是原文摘要，不是转述结论。
4. **`open_questions` 的编号必须存在于 `questions[]`**。
5. **`status` 枚举**：`已核验`（全文读到）/`检索索引命中`（搜索引擎摘要命中，直连被拦）/`直连失败`/`待下载`。后三类在报告里要被显式标注，不得当作唯一 A 级依据。
6. **禁止字段**：不要加"综合评分""推荐指数"这类无法回溯的数字。
7. **空值约定**：字符串用 `"—"`（展示为缺失），无法取得的用 `"待核验"`。**不要用 `null` 混入展示字段**（除 `case_input` 的采购方未提供项）。

## 分栏规则（HTML 与 Excel 必须一致）

```python
MANUF_TYPES = {"MANUFACTURER", "JV_MANUFACTURER"}
left_column  = entity_type in MANUF_TYPES and grade in {"A", "B"}
right_column = not left_column
```

原因：C 级（近似品/非目标品）和 D 级（销售/贸易）都不能进"生产商"栏，但它们必须出现在"防误判"栏里。

## 排序规则

```python
sorted(companies, key=lambda c: (GRADE_ORDER[c["grade"]], 0 if c["entity_type"] in MANUF_TYPES else 1, c["rank"]))
```
