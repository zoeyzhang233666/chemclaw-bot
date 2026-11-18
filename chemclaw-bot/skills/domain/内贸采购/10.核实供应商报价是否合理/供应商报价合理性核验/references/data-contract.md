# research.json 数据契约

一个 `research.json` = 一次报价核验的完整底稿。脚本只读它 + `specs/<品种>.json` + `series/*.json`，
所以**所有事实都必须落在本文件里**，不能只存在报告正文。

```jsonc
{
  "meta": {
    "report_id": "SQV-MEG-HD-20261019",
    "title": "华东地区工业级乙二醇供应商报价合理性核验",
    "product_family": "乙二醇",
    "spec_file": "specs/meg.json",       // 与 research.json 同级的相对路径，或 specs/ 下的文件名
    "asof": "2026-10-19",                 // 数据基准日（ISO），所有窗口以此为终点
    "asof_note": "…",
    "prepared_for": "内贸采购",
    "data_nature": "…",
    "disclaimer": "不预测价格、不给议价建议"
  },

  "quote": {
    "is_test_input": true,                // true 时报告与 Excel 必须显著标注
    "test_badge": "测试输入（非真实供应商报价）",
    "supplier_label": "测试供应商A",
    "supplier_type": "生产厂",
    "product_name": "乙二醇",
    "product_aliases": ["MEG", "EG"],
    "spec_text": "工业级",
    "grade_claimed": "工业级（含量未写明）",
    "purity": null,                        // 未知就 null
    "process": null,
    "value": 5900,                         // 合同单位下的数值
    "unit": "元/吨",                       // 支持 元/吨、元/kg（自动×1000）
    "tax":     {"included": true, "vat_rate": 0.13, "text": "含13%增值税"},
    "delivery":{"basis": "ex_works", "text": "工厂车板交付", "origin": "江苏·连云港"},
    "destination": "江苏·苏州",
    "region_supplier": "华东（苏北）",
    "quantity": {"value": 60, "unit": "吨/次", "basis": "整批"},
    "payment":  {"terms": "电汇 30% 预付，余款月结", "cash_discounted": false},
    "packing": "散水（槽车）",
    "validity": "未注明",
    "pricing_formula": "固定价",
    "quote_date": "2026-10-19",
    "unknowns": ["含量", "工艺路线", "报价有效期"],
    "raw_text": "报价原话，逐字保留"
  },

  "market": {
    "spot_anchors": [                      // 每条六项口径必须齐全
      {
        "id": "LZ-2026-10-19-0930",
        "date": "2026-10-19", "time": "09:30",
        "region": "华东", "spec": "聚酯级 含量≥99.9%",
        "price_type": "华东自提价（主流价）",
        "value": 5635, "unit": "元/吨",
        "tax_included": true, "delivery": "自提",
        "change": -102, "bid": 5630, "ask": 5640,
        "source_name": "隆众资讯", "source_title": "…",
        "url": "https://…",
        "role": "primary",                 // primary / cross_check / index
        "tier": "产业资讯日更报价",
        "note": "原文要点，引述不改写"
      }
    ],
    "enterprise_prices": [                 // 挂牌/结算/竞拍，单列，不参与偏离
      {"id": "...", "party": "中石化华东", "month": "2026-10", "list_price": 6300, "note": "…", "source": "…"}
    ],
    "spot_series_3m": [                    // 逐日现货快照（可少于完整序列）
      {"date": "2026-10-12", "region": "华东", "spec": "聚酯级", "value": 5780,
       "tax_included": true, "delivery": "自提", "source": "…", "url": "…", "change": -100}
    ],
    "series_files": {                      // 与 research.json 同级的相对路径
      "ppi_daily_1y": "series/ppi_benchmark_1y.json",
      "futures_daily_3y": "series/eg0_daily.json"
    },
    "series_meta": {                       // 每个序列的口径必须写清
      "ppi_daily_1y": {"name": "生意社乙二醇基准价", "unit": "元/吨", "freq": "日", "tax": "含税",
                        "region": "全国综合", "spec": "聚酯级综合", "source": "…", "url": "…",
                        "validate": "如何交叉验证过"}
    },
    "futures_reference": {"date": "…", "close": 4976, "pct": -6.90, "basis_note": "为何不能直接相减"},
    "transport": {"freight_supplier_to_dest": null, "gap": "缺运价", "reference_note": "…"}
  },

  "benchmark": {
    "primary_anchor_id": "LZ-2026-10-19-0930",
    "secondary_anchor_ids": ["LA-2026-10-19-1019"],
    "interval_by_target": {                // 键 = 税费|交付
      "included|ex_works": {"low": 5580, "high": 5665, "center": 5635,
                             "basis": "区间怎么来的",
                             "confidence": "medium",
                             "caveat": "局限，会显示为醒目提示"},
      "included|delivered": {"low": null, "center": null, "basis": "缺运价 → 缺口"}
    },
    "interval_method": "口径转换说明"
  },

  "comparability": [                        // 十类口径逐项
    {"item": "产品含量/等级", "quote": "工业级", "market": "聚酯级 ≥99.9%",
     "status": "unknown", "direction": "工业级通常更低", "quantifiable": false,
     "label": "待确认",                     // 已对齐 / 已有依据（方向） / 待确认 / 不可比
     "evidence": "依据或为什么无法量化"}
  ],

  "percentile_plan": [                      // 只做说明；实际窗口由 model.py 按 series_files 计算
    {"window": "3m", "series": "spot_snapshots", "note": "…"}
  ],

  "gaps": [
    {"id": "G1", "item": "3 个月逐日现货", "impact": "…", "tried": "试过哪些渠道",
     "why": "为什么缺", "next": "补数路径"}
  ],

  "evidence_summary": {
    "explainable": [{"difference": "出厂 vs 库提", "amount": "约 +55 元/吨",
                      "direction": "报价偏低方向", "basis": "同日两个真实报价之差"}],
    "pending": ["含量是否 ≥99.9%", "运价", "报价有效期"]
  }
}
```

## 字段硬性要求

| 字段 | 要求 |
|---|---|
| `meta.asof` | 必须是 ISO 日期；所有历史窗口以此为终点 |
| `quote.tax.included` | 布尔值，别用"是/含税"字符串 |
| `quote.delivery.basis` | `ex_works` 或 `delivered` |
| `spot_anchors[*].tax_included` | 布尔；`delivery` 必须写明出厂/自提/库提/到厂 |
| `spot_anchors[*].role` | `primary` 有且只有一个 |
| `series_files` | 指向的 JSON 必须是 `{"meta": {...}, "points": [{"d": "YYYY-MM-DD", "v": 数值}]}`；期货序列用 `c`（收盘）字段时，model.py 会自动取 `c` |
| `comparability[*].label` | 只能用四种标签之一 |
| `gaps[*]` | `tried` 和 `why` 不许空——缺口必须能解释为什么补不上 |

## series 文件格式

```json
{
  "meta": {"name": "生意社乙二醇基准价", "unit": "元/吨", "freq": "日", "tax": "含税",
           "region": "全国综合", "spec": "聚酯级综合", "source": "…", "url": "…"},
  "points": [{"d": "2025-10-19", "v": 4268.33}, {"d": "2025-10-20", "v": 4263.33}]
}
```

期货序列可含 `o/h/l/c/v`，`points` 里用 `c` 作为值；`model.py` 会优先用 `c`。
