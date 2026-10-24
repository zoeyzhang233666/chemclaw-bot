# case.json 字段契约

`case.json` 是**唯一需要人工维护**的文件；`data.json`、HTML、Excel 全部由它派生。
不要在任何产物里手改数字——改 case 再重跑，否则两处数字会打架。

```bash
python scripts/validate.py case.json          # 改完先校验
python scripts/build_all.py case.json -render # 再生成
```

---

## meta（必填）

```json
"meta": {
  "title": "中国重质纯碱出口印度尼西亚市场研究",
  "subject": {"product_cn": "纯碱（碳酸钠，disodium carbonate）", "hs_code": "2836.20",
               "grade": "重质纯碱为主，兼看轻质", "unit": "t"},
  "country": {"name_cn": "印度尼西亚", "name_en": "Indonesia", "un_m49": 360},
  "research_year": 2025,
  "window": 5,
  "data_asof": "2026-10-19",
  "trade_source": {
    "name": "UN Comtrade public API",
    "dataset": "C/A/HS，HS6 283620，年度",
    "value_basis": "进口=CIF 海关价值（USD）；出口=FOB（USD）",
    "weight_basis": "净重 netWgt（kg）",
    "pull_record": "2026-10-19 拉取 reporterCode=360/156，period 2018-2025",
    "notes": ["…口径注意事项，会渲染到报告第 6 节…"]
  }
}
```

校验规则：`subject.hs_code` 必须是 6 位数字；`country.un_m49` 必须是 Comtrade 的 reporterCode；
`window` 决定报告表格展示多少年（长序列仍可放在 `imports_history` 里做对照）。

---

## structure

```json
"structure": {
  "product": ["重质纯碱 dense soda ash", "轻质纯碱 light soda ash"],
  "hs_scope_note": "HS 2836.20 不再区分重/轻、工业/食品级……",
  "hs_scope_sources": ["s-hscodeatlas"]
}
```
`hs_scope_note` 会被渲染进“贸易结构”板块的税号口径说明；没有它报告会缺一句关键免责。

---

## trade（海关）

```json
"trade": {
  "imports": [{"year": 2025, "value_usd": 225569363, "qty_t": null, "source": "comtrade"}],
  "imports_history": [ ...同上，可更长... ],
  "imports_history_note": "另取得 2018-2020 年金额……",
  "partners": {"2025": [{"rank": 1, "name": "美国 United States", "code": 842,
                          "value_usd": 157120000, "qty_t": 731566}]},
  "china_exports": [{"year": 2025, "to_idn_usd": 60914157, "to_idn_t": 287009,
                     "to_world_usd": 1234567890}],
  "china_exports_note": "中国口径 FOB 与印尼口径 CIF 存在差异……",
  "exports": [{"year": 2024, "value_usd": 3700000, "qty_t": 16000, "top_dest": "尼日利亚 Nigeria"}],
  "local_supply": [],
  "consumption_reference": []
}
```

| 字段 | 规则 |
|---|---|
| `value_usd` | 美元整数；单位必须确认（Comtrade 有时返回千美元，`validate` 会抓量级异常） |
| `qty_t` | 吨（浮点）；**未报送就是 `null`**，不插值、不换算 |
| `partners.<year>` | 键是字符串年份；金额合计不得大于 `imports` 同年的合计（校验会报错） |
| `china_exports.to_world_usd` | 用来算“印尼占中国该产品出口的比重”，缺了就不算，不估 |
| `consumption_reference` | 只放**有出处**的消费量参考（企业/部委表态），并且必须在报告里标成“参考/估算” |

---

## industries（本地产能与企业）⭐ 最能体现价值的部分

```json
"industries": {
  "local_production": [{
    "id": "pkt-bontang",
    "name": "Pupuk Kaltim × Rekind 纯碱项目",
    "role": "生产",                       // 生产 / 中试 / 拟建 / 贸易商
    "location": "东加里曼丹 Bontang 工业区",
    "capacity_t": 300000,
    "capacity_basis": "新闻稿披露的设计产能，非实际产量",
    "status": "在建",                     // 在运 / 在建 / 中试 / 拟建 / 停产
    "status_asof": "2025-11-10",
    "products": ["纯碱（重质为主）"],
    "facts": ["2025-10-31 举行开工仪式", "官方表述可满足全国约 30% 需求"],
    "sources": ["s-pkt-groundbreaking", "s-kompas-pkt"],
    "verify": ["实际投产时间", "一期实际产出与销售区域"]
  }],
  "local_absence_evidence": [
    {"claim": "印尼目前没有在运的纯碱生产装置", "source": "s-usgs", "kind": "official"}
  ],
  "consumers": [{
    "id": "xinyi",
    "name": "信义玻璃印尼（Xinyi Glass Indonesia）",
    "type": "下游直接用户",
    "location": "JIIPE Gresik 工业园",
    "products": "浮法玻璃 / 光伏玻璃",
    "buying_role": "直接用户：玻璃窑炉的纯碱原料",
    "facts": ["TKDN 约 80%，剩余 20% 进口投入全部是纯碱"],
    "sources": ["s-xinyi2", "s-beritajatim-xinyi"],
    "verify": ["年采购量与采购节奏", "供应商结构与验收标准"]
  }],
  "consumers_unnamed": [
    {"segment": "中小型玻璃/洗涤剂厂", "why_unnamed": "无公开采购信息",
     "search_hint": "印尼工业部 SIINas 企业库 + 展会名录"}
  ]
}
```

**“本地无产能”要有证据链**：`local_absence_evidence` 至少两条，其中一条最好是 T1/T2。
只说“我们判断本地没有厂”是不合格的——这恰恰是客户最容易反驳的点。

---

## downstream

```json
"downstream": {"note": "……", "items": [{
  "segment": "玻璃",
  "demand_signal": "信义玻璃在 Gresik 建浮法+光伏产线；部长公开表态纯碱是进口依赖项",
  "scale_note": "公开披露的产线规模：浮法 612,500 t/y（印尼另一家）",
  "gap": "吨玻璃纯碱单耗、按应用拆分的需求量",
  "sources": ["s-xinyi2", "s-muliaglass-en"]
}]}
```
`gap` 字段是**强制**的：每一段下游都必须写出“这一段我们不知道什么”。

---

## competition

```json
"competition": {
  "source_countries": [{"name": "美国 United States", "basis": "份额 69.7%，单位价值 $215/t",
                        "evidence": "s-comtrade 口径；s-usgs 产量背景"}],
  "distributors": [{"name": "PT …", "role": "分销/进口", "products": "纯碱、烧碱",
                    "source": "s-lestari-kimia"}],
  "price_observation": [{"kind": "market_research", "claim": "IndexBox 估算 2026 年 CIF 280–360 美元/吨",
                         "note": "机构估算，非成交价，不可作报价锚点"}],
  "china_hs_code_note": "中国出口口径 HS 283620；印尼进口口径 2836.20.00"
}
```

---

## policy

```json
"policy": {
  "hs_line": {"code": "2836.20.00", "description": "Sodium carbonates（碳酸钠）",
              "verify_note": "八位税号与分档税率需以 INSW/DJBC 最新 BTKI 为准"},
  "tariffs": [{
    "id": "t-mfn",
    "item": "最惠国（MFN）进口关税",
    "rate_pct": null,                    // ← 没核到就是 null
    "status": "gap",                     // fact / official / gap
    "detail": "第三方汇总站以 WITS 2023 口径给出 0%（s-yizhou-idn）；未在 INSW 逐条核验",
    "sources": ["s-yizhou-idn", "s-tradegov-tariff"]
  }],
  "ntm": [{"id": "p-lartas", "item": "LARTAS 进口限制/许可证", "status": "need_confirm",
           "detail": "……", "sources": ["s-tradegov-restricted", "s-kemendag-9permen"]}],
  "trade_relations": [{"id": "r-acfta3", "item": "ACFTA 3.0", "status": "fact",
                       "detail": "2025-10-28 签署；未取得全文……", "sources": ["s-acfta-upgrade"]}]
}
```
**硬规则**：`rate_pct` 有值 ⇒ `status` 必须是 `fact`/`official`；否则 `validate` 会警告并在报告里打“待核实”。

---

## reports / sources / gaps / verify_actions

```json
"reports": [{"id": "r-indexbox", "type": "机构估算", "title": "Indonesia Soda Ash Market",
             "key_points": ["……"], "source": "s-indexbox",
             "caveat": "机构估算，方法与样本不公开，只能作方向参考"}]

"sources": [{"id": "s-tradegov-tariff", "kind": "official",
             "publisher": "US ITA trade.gov", "title": "Indonesia - Import Tariffs",
             "url": "https://www.trade.gov/country-commercial-guides/indonesia-import-tariffs",
             "date": "2025-11-17", "tier": 1}]

"gaps": [{"id": "g-consume", "level": "市场级",
          "item": "全国纯碱年消费量（万吨）",
          "why": "海关只给进口量；国内产量与库存无公开数据",
          "impact": "无法给出真实市场规模，只能用进口额代理",
          "how_to_close": "印尼统计局/工业部年报，或行业协会会员产量汇总"}]

"verify_actions": [{"priority": "P0", "action": "用 INSW 按 2836.20.00 核验 MFN/ACFTA/RCEP 税率",
                    "owner": "外贸销售", "when": "首次报价前"}]
```

- `sources[].kind`：`official / regulation / company / media / trade_assoc / market_research / estimate / unnamed`
- `sources[].tier`：1=官方直发，2=政府指南/主流媒体转述官方，3=商业估算/行业媒体，4=第三方汇总站
- `gaps[].level`：`企业级` / `市场级` / `政策级` / `数据级`
- `verify_actions[].priority`：P0 报价前必须解决，P1 首轮触达，P2 签约前后台

---

## 校验会抓什么

| 检查 | 报错/警告 |
|---|---|
| 缺 `meta.subject.hs_code` 等必填字段 | error |
| 引用了未在 `sources` 登记的 id | error |
| 某年伙伴金额合计 > 该年进口合计 | error |
| 金额量级异常（< 1e3 或 > 1e12，疑似单位错） | error |
| 预测性表述（预计将增长/必将/一定会…） | error |
| `partners` 有某年明细但 `imports` 无该年合计 | warning |
| `gaps` 为空 | warning |
| 税率数值但状态非 official | warning |
| 来源只有 T3/T4 | warning |
