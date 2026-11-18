# 数据契约：字段定义与合并规则

所有 lane 子代理产出的 JSON 必须严格符合本节字段，合并脚本据此去重、排序、出表。

---

## 1. 单条线索字段（leads_raw/NN_lane.json）

```json
{
  "company": "法定名称（最完整可核版本）",
  "alt_names": "简称 / 上市代码 / 英文名 / 曾用名",
  "country": "Indonesia",
  "type": "终端生产企业 | 直接进口商 | 经销商 | 待确认",
  "buyer_role": "在产业链中的角色一句话（如：浮法玻璃熔窑终端用户）",
  "region": "省/州 + 城市 + （厂址）",
  "region_short": "用于筛选器显示的短地域（如 Jawa Barat）",
  "main_business": "主营业务，40–80 字",
  "product_relation": "产品在其工艺/配方中的位置与用量逻辑",
  "evidence_tier": "A | B | C | 未核实",
  "evidence_summary": "证据要点：来源说了什么，含数字与期间",
  "evidence_urls": ["https://…"],
  "evidence_period": "如 2023–2025 年度",
  "evidence_scope": "终端消耗量 | 进口记录 | 目录列明 | 工艺相关",
  "volume_hint": "如 ≈13.7 万吨/年（未区分轻重质）",
  "evidence_list": [
    {"tier":"A","type":"上市公司年报-材料使用表","source_name":"…","url":"…","period":"2025","quote":"…","usable_as":"用量基线","caveat":"未区分轻重质"}
  ],
  "contact": ["公开渠道文字列表（兼容旧格式）"],
  "contact_struct": {"website":"","phone":"","email":"","address":"","social":"","note":"","verified_on":"2026-10-19"},
  "why_related": "关联原因分析：为什么该企业与本产品存在业务关联（不是行业套话）",
  "open_questions": ["可回答的具体问题", "…"],
  "verify_channel": "建议核验渠道",
  "peer_flag": false,
  "peer_note": "",
  "confidence": "高 | 中 | 低",
  "lane": "glass | detergent | distributor | silicate | pulp_paper | textile_ceramic | …",
  "link_status": "200 | 403(反爬，建议人工复核) | 坏链"
}
```

必填：`company, type, region, main_business, product_relation, evidence_tier, evidence_summary, confidence, lane`。缺任何一项的条目在合并时被拒并记入 `_rejected.json`。

## 2. 合并规则

1. **归一化**：小写、去标点、删除 `pt / pt. / perseroan terbatas / ltd / limited / co. / tbk / inc. / corporation`；全角转半角；合并多余空格。
2. **去重键**：归一化名称；若缺失，用“官网域名 + 城市”。
3. **冲突合并**：
   - 证据等级取**最高**，但必须在 `merge_note` 写明“由 X 级与 Y 级来源合并，均保留”。
   - 类型冲突（既像工厂又像经销商）→ `type=待确认`，并把两种判断写进 `why_related`。
   - 联系方式取并集，个人数据一律丢弃。
4. **排序**：按 §evidence-grading 的分数降序，分数相同按 `evidence_period` 新者优先。
5. **编号**：合并后统一分配 `id`（1..N），作为 HTML/Excel 的稳定主键。

## 3. 统计口径（报告必须给出）

- 按 `lane` 计数、按 `type` 计数、按 `region_short` 计数、按 `evidence_tier` 计数。
- `未核实` 条目单列，不能混在 C 级里充数。

## 4. 市场事实字段（market_facts.json）

```json
{"topic":"demand|imports|domestic_supply|price|regulation|logistics",
 "fact":"一句话事实","value":"数值","unit":"","period":"2024",
 "source_name":"UN Comtrade","source_url":"https://…","fetched":true,
 "confidence":"高|中|低","note":"口径说明（netWgt/CIF 等）"}
```

规则：**同一事实两个来源冲突时，两个都记**，并写明差异原因（口径、年份、统计范围）。
