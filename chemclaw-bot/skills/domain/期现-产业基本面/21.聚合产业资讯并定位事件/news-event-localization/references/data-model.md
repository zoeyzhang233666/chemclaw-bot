# 数据模型（七文件）

所有数据以 JSON 存储于 `src/`。构建脚本从这里生成 HTML 与 Excel，**保证两个交付物的数字同源**。

---

## 1. `sources.json` —— 信息源

```jsonc
{
  "meta": {
    "case_id": "METHANOL-20261013-20261019",
    "product": "甲醇",
    "scope": "中国甲醇产业链（含进口/伊朗、华东华南港口、外采MTO…）",
    "window_start": "2026-10-13",
    "window_end": "2026-10-19",
    "window_label": "2026-10-13 至 2026-10-19（7个自然日）",
    "collect_time": "2026-10-20T10:20:00+08:00",
    "window_selection_rationale": "为什么选这个窗口（必须能回答三个前置条件）"
  },
  "sources": [
    {
      "src_id": "S01",
      "name": "生态环境部（气候司／政府信息公开）",
      "type": "政府公示 | 行业资讯 | 综合财经媒体 | 企业公告/互动问答 | 期货公司研究",
      "tier": "T0 | T1 | T2",
      "site": "https://www.mee.gov.cn",
      "list_url": "栏目页（可空，填空则显示“无固定栏目页”）",
      "access": "可读 | 部分可读 | 受限 | 不可访问",
      "access_note": "具体怎么受限（不要写“无法访问”）",
      "rss": "有/无",
      "value": "对本案例的价值",
      "in_window_items": 1,
      "reliability": "A 官方原文 | A 一手资讯机构（正文受限）| B 转载媒体 | C 自媒体",
      "note": "工程坑或使用注意"
    }
  ],
  "limitations": ["全局访问限制，逐条列出"]
}
```

**校验规则**：`src_id` 唯一；`tier ∈ {T0,T1,T2}`；`access` 必须是四个枚举值之一。

---

## 2. `news.json` —— 原始资讯条目

```jsonc
{
  "items": [
    {
      "news_id": "N01",
      "src_id": "S03",
      "publisher": "隆众资讯",              // 实际发布主体（可不同于 src 名）
      "title": "[甲醇]：天津渤化甲醇装置动态",
      "first_pub": "2026-10-16T00:00:00+08:00",  // 首发时间；未知用 null
      "first_pub_note": "为什么是这个时间 / 为何无法确定",  // 与 first_pub 二选一必填
      "list_ts": "2026-10-20T10:38:00+08:00",    // 列表页时戳（可选）
      "repub_time": null,                         // 转载时间（可选）
      "url": "https://...",
      "url_date_evidence": "URL 内嵌 26-1020-10", // 可选
      "content_level": "full | partial | summary_only | title_only",
      "core_points": ["逐条摘录，原文可引的部分加引号"],
      "event_hint": "EVT-...",                    // 由 dedupe 回填，可空
      "language": "zh",
      "is_organic": true,
      "outside_window": true,                     // 事件日超窗但报道在窗内
      "dup_of": "N08",                            // 可选：重复于哪条
      "dup_relation": "exact_copy",               // 可选
      "repub_delay_minutes": 67,                  // 可选
      "reliability_flag": "C-selfmedia：…",       // 可选：降级提示
      "note": "备注"
    }
  ]
}
```

### `content_level` 的含义与影响

| 值 | 含义 | 能支撑的最强结论 |
|---|---|---|
| `full` | 正文全文 | 可直接引用其内容 |
| `partial` | 摘要/导语/被截断 | 可引用已取得部分 |
| `summary_only` | 仅搜索引擎摘要 | 仅可作旁证 |
| `title_only` | 仅标题 | **只能证明"该标题在某时发布"，不能证明内容** |

---

## 3. `events.json` —— 事件

```jsonc
{
  "meta": {
    "event_id_rule": "EVT-<品种代码>-<YYYYMMDD>-<序号>",
    "types": ["项目投产","装置检修","停车复产","产能扩建","贸易政策","环保安全","下游需求","其他产业事件"],
    "confirm_levels": { "C1": "…", "C2": "…", "C3": "…", "C4": "…" }
  },
  "events": [
    {
      "event_id": "EVT-MEOH-20261018-001",
      "title": "南京诚志MTO装置停车，港口外采MTO开工降至零",
      "type": "停车复产",
      "sub_type": "下游MTO装置停产",
      "occur_date": "2026-10-18",
      "occur_date_note": "日期判定依据（必须写清为什么取这天）",
      "first_report": "2026-10-19T10:05:00+08:00",
      "first_report_note": "首发说明",
      "last_update": "2026-10-19T21:24:00+08:00",
      "region": "华东-江苏-南京",
      "province": "江苏",
      "nation": "中国",
      "product": "甲醇、聚烯烃（乙烯/丙烯）",
      "chain_node": "CHAIN-D03",                 // 可为 null
      "companies": ["ENT-C001"],
      "plants": ["PLT-C001-A"],
      "capacity_desc": "装置产能描述（无则写“不适用”或“未取得”）",
      "scale_desc": "客观规模说明（只做量级参照，不做供需结论）",
      "scale_data": [
        {"metric":"江浙地区MTO周均产能利用率","value":"20.06","unit":"%",
         "period":"2026-10-09~10-15","source":"隆众资讯（经…转引）"}
      ],
      "confirmed_facts": ["已确认事实，逐条"],
      "data_supported": ["有数据支持的客观描述"],
      "unconfirmed": ["尚未确认的信息"],
      "verify_status": "C2",
      "verify_basis": "为什么是这个级别（必须具体）",
      "news_refs": ["N08","N09","N13"],
      "dedupe": {
        "primary_news": ["N08"],
        "republish": ["N09"],
        "followups": ["N13"],
        "index_entries": ["N25"],
        "selfmedia": ["N11"],
        "why_merged": "合并理由"
      },
      "open_questions": ["Q01","Q02"],
      "impact_hint": "影响权重说明（禁止涨跌结论）"
    }
  ]
}
```

**校验规则**：`event_id` 唯一；`news_refs` 中每个 id 必须存在于 news；`dedupe.primary_news` 必须非空且是 `news_refs` 的子集；`companies`/`plants`/`chain_node`/`open_questions` 必须能解析。

---

## 4. `entities.json` —— 企业与装置

```jsonc
{
  "meta": {
    "plant_status_vocab": ["运行稳定","停车","停车-重启时间待定","长期停车",
                           "长期停车-部分拆除","降负","负荷偏低","不报价","投产在途","备案阶段","未知"]
  },
  "companies": [
    {
      "ent_id": "ENT-C001",
      "name": "南京诚志（诚志永清能源科技）",
      "short": "南京诚志",
      "group": "诚志股份",
      "province": "江苏", "city": "南京", "region": "华东",
      "route": "外采甲醇 MTO",
      "own_methanol": "无（外采为主）",
      "role": "甲醇下游-MTO",
      "listed": "000990.SZ（诚志股份）",
      "profile": "企业档案"
    }
  ],
  "plants": [
    {
      "plant_id": "PLT-C001-A",
      "ent_id": "ENT-C001",
      "name": "南京诚志一期MTO",
      "capacity": 60,                    // null = 未取得，禁止填估计值
      "unit": "万吨/年（烯烃）",
      "route": "MTO（外采甲醇）",
      "region": "华东-江苏-南京",
      "status": "停车",                  // 取自 status_vocab
      "status_since": "2026-10-18",      // null = 起始日未取得
      "status_source": "金联创（N08/N09）",
      "capacity_source": "…",            // capacity 非 null 时必填
      "note": "备注"
    }
  ]
}
```

**校验规则**：`plant.ent_id` 必须存在；`capacity` 非 null 时 `capacity_source` 必填。

---

## 5. `chain.json` —— 产业链

```jsonc
{
  "nodes": [
    {
      "node_id": "CHAIN-D03",
      "name": "甲醇制烯烃 MTO/CTO（沿海外采 + 西北一体化）",
      "layer": "上游原料 | 甲醇生产 | 流通/进口 | 下游需求 | 衍生路线",
      "product": "乙烯/丙烯/聚烯烃",
      "region": "江苏/浙江/山东/天津 + 西北",
      "capacity_note": "规模提示（可空，空则显示“—”）",
      "desc": "节点说明",
      "data_ref": "对应数据指标名",
      "related_nodes": ["CHAIN-T01"]
    }
  ],
  "edges": [
    {"from":"CHAIN-T01","to":"CHAIN-D03","label":"外采原料"}
  ],
  "indicators": [
    {
      "node_id": "CHAIN-T01",
      "name": "中国甲醇港口样本库存",
      "freq": "周",
      "latest": "36.72 万吨（2026-10-14）",
      "prev": "30.51 万吨（2026-10-08）",
      "source": "隆众资讯",
      "link": "https://..."
    }
  ]
}
```

**校验规则**：`edges.from/to` 与 `indicators.node_id` 必须能解析到节点。

---

## 6. `dedupe.json` —— 去重关系

```jsonc
{
  "meta": {
    "relation_types": {
      "primary": "该事件的首发报道（主记录）",
      "republish": "同一稿件的转载（内容一致）",
      "followup": "同一事件的后续更新",
      "index_entry": "同一内容的索引/列表形态",
      "selfmedia": "自媒体/社区转述（降级为旁证）",
      "conflict": "关键事实不一致（并置保留）"
    }
  },
  "links": [
    {
      "event_id": "EVT-MEOH-20261018-001",
      "news_id": "N09",
      "relation": "republish",
      "basis": "判定依据（可审计，写具体证据）",
      "conf_weight": "对确认度的作用：同源，不增加独立确认度"
    }
  ],
  "unassigned": [
    {"news_id": "N12", "reason": "为什么不立事件", "event_id": null}
  ]
}
```

**校验规则**：每条 `links` 的 event_id/news_id 必须存在；同一 (event, news) 不得重复；**每条 news 必须出现在 links 或 unassigned 之一**（不可两边都有，也不可都不在）。

---

## 7. `toverify.json` —— 待验证事项

```jsonc
{
  "questions": [
    {
      "q_id": "Q01",
      "event_id": "EVT-MEOH-20261018-001",   // "*" 表示全局问题
      "question": "待验证的问题（要具体）",
      "why_matters": "为什么重要",
      "evidence_needed": "需要什么证据",
      "where_to_get": "去哪里取（可执行）",
      "status": "未取得 | 部分取得 | 冲突未解 | 预期未验证 | …",
      "priority": "高 | 中 | 低",
      "blocked_by": "当前卡点"
    }
  ]
}
```

**校验规则**：`q_id` 唯一；`event_id` 必须是 `*` 或存在的 event；被事件 `open_questions` 引用的必须存在。

---

## 字段间的硬约束

| 约束 | 原因 |
|---|---|
| `news.first_pub` 与 `news.first_pub_note` 至少一个非空 | 时间不确定时必须说明为什么 |
| `plant.capacity` 非空 → `capacity_source` 必填 | 禁止无源产能 |
| `event.verify_status ∈ {C1..C4}` 且 `verify_basis` 非空 | 确认度必须可解释 |
| `event.dedupe.primary_news ⊆ event.news_refs` | 防止主记录游离 |
| 每条 news 在 dedupe 中恰好被归类一次 | 防止静默丢失 |
| 事件 `type` 必须在八类枚举内 | 保证筛选可用 |