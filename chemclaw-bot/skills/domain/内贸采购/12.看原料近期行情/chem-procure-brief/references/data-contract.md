# research.json 数据契约（唯一真源）

> 所有数字都在这个文件里手填一次；`assemble.py` 算出派生物；HTML 与 Excel 都只消费 `data.json`。
> **手填派生值（如"涨跌幅""分位"）就是错误**——脚本会重算并覆盖。

```bash
python scripts/build_all.py research.json --out out --name 品种-地区
```

## 顶层结构

```json
{
  "meta": {...},              // 必填
  "anchor": {...},            // 当前价（采购点、日期、口径、来源）
  "primary_point": "采购点名", // 首屏用哪个采购点做主线
  "quote_series": [...],      // 报价序列（点数越多分位越有意义）
  "spot": [...],              // 当期报价表（六项口径，含厂商挂牌/竞拍/指数）
  "spread_base": {...},       // 价差基准点与比较日期
  "spread_series": [...],     // 多采购点同期跟踪（画对比图/价差线）
  "futures": {...},           // 可选：期货日线，仅作参考
  "cost_lines": [...],        // 成本参考线（完全/现金/原料成本）
  "routes": [...],            // 工艺路线单耗表（算原料成本）
  "upstream": [...],          // 上游成本项（必须能自证）
  "downstream": [...],        // 下游需求项（必须能自证）
  "chain_proof": [...],       // 断点自证表（每条链的工艺依据）
  "balance": [...],           // 库存/开工/进口/到港
  "events": [...],            // 事件（带证据级别）
  "procurement": {...},       // 我方采购参数（库存天数、月用量…）
  "facts": [...],             // 可对外引用的事实
  "talk": [...],              // 供应商问答（答案禁方向词）
  "gaps": [...],              // 缺口清单
  "caveats": [...],           // 口径提醒
  "sources": [...]            // 来源清单
}
```

---

## meta（必填）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `product` | str | ✔ | 品种名，用于标题与文件名 |
| `asof` | `YYYY-MM-DD` | ✔ | **数据截止日**（不是写作日） |
| `spec` | str | 建议 | 规格/执行标准，如"≥99.9%（GB/T 338）" |
| `region` | str | 建议 | 采购区域，如"华东（太仓/常州罐区）" |
| `unit` | str | 建议 | 默认"元/吨" |
| `title` | str | 否 | 报告标题 |
| `subtitle` | str | 否 | 副标题（自动拼一句也行） |
| `anomaly_pct` | float | 否 | 异常点阈值，默认 3.5 |
| `quote_kinds` | [str] | 否 | 本品种出现的报价类型清单（显式列出可提醒读者口径混杂） |
| `buyer` | str | 否 | 我方身份描述 |
| `peer_products` | [str] | 否 | 相关品种（仅展示，不参与计算） |

## anchor（当前价）

```json
{
  "label": "华东太仓 主流价（期货公司日报口径）",
  "point": "华东太仓",
  "value": 3983,
  "range_lo": 3890, "range_hi": 4030,
  "date": "2026-10-16",
  "tax": "含税",
  "basis": "含税现汇 · 罐区自提",
  "prev_date": "2026-10-14",
  "prev_mid": 3845,
  "note": "同日另有 3960（指数口径）/3983（日报口径），差异来自取样时点",
  "src": "某期货公司 2026-10-16 日报（某资讯数据）"
}
```
`value` 必填；`range_lo/hi` 有区间就填，单点不填。`date` 距 `asof` 超过 3 天脚本会自动加 caveat。

## quote_series（报价序列，分位的基础）

```json
{"point":"华东太仓","date":"2026-10-13","lo":3730,"hi":3960,
 "spec":"目标品 国标优等品","tax":"含税","basis":"含税现汇·罐区","src":"…"}
```
- **只放真实报价日的点**，不补空、不插值。
- 同一采购点同日多条会被去重（保留第一条），差异请写进 `caveats`。
- 采购点越多越好，但**每个点都要 ≥3 条**才能算分位，≥8 条才不算"样本薄"。

## spot（当期报价表）

与 `quote_series` 同结构，另加 `quote_kind`（罐区现货/指数/厂商挂牌/竞拍成交/CFR）、`tier`（市场/产区/厂商/进口/指数）、`conf`（高/中/低）、`note`。外币报价加 `"unit":"美元/吨"`。

## spread_base / spread_series

```json
"spread_base": {"point":"华东太仓","dates":["2026-10-16"]},
"spread_series": [{"name":"太仓 vs 内蒙","base":"华东太仓",
  "note":"含运费与提货方式差异","src":"…",
  "rows":[{"point":"华东太仓","date":"2026-10-16","lo":3983,"hi":3983},
          {"point":"内蒙北线","date":"2026-10-16","lo":3115,"hi":3115}]}]
```
`dates` 留空则对每个有 ≥2 个点的日期都算价差。

## futures（可选）

```json
"futures": {"exchange":"某交易所","code":"XX","series":"raw/XX_daily.json","note":"主连连续，不含税"}
```
序列文件由 `fetch_futures.py` 生成，字段 `d,o,c,h,l,v,oi,pct`。**只作参考，不参与结论。**

## cost_lines（成本参考线）

```json
{"name":"某路线完全成本","value":2638,"date":"2026-10-08","route":"A路线",
 "type":"完全成本","derived":true,"note":"由利润与售价反推","src":"…"}
```
`type` ∈ 完全成本 / 现金成本 / 原料成本。`derived:true` 表示是推算值，报告会标"派生值"。

## routes（工艺路线单耗表）

```json
{"name":"A路线（外购原料）","date":"2026-10-16",
 "inputs":[{"item":"原料 X","qty":1.55,"unit":"吨","price":785,"date":"2026-10-16","src":"…"},
           {"item":"加工费","qty":1,"unit":"吨","price":null,"src":"未取得"}],
 "note":"单耗来自公开工艺参数；加工费缺失故不合计","src":"…"}
```
- `qty` = 每吨产品耗用量；`unit` 见 `chain-mapping.md` 换算表。
- 任一输入 `price` 为空 → 该路线 `complete:false`，报告显示"分项不全，未合计"。**这是设计而非缺陷。**

## upstream / downstream

```json
{"name":"原料 X（某规格）","role":"A路线主原料","value":785,"unit":"元/吨",
 "chg":"较上月 +15","date":"2026-10-16","direction":"up",
 "ratio":"1.55 吨/吨（工艺参数）","logic":"…传导逻辑…","link":"直接","src":"…"}
```
`direction` ∈ up / down / gap。**无数字必须用 `gap`**（脚本会强制）。`link` ∈ 直接 / 间接。

## chain_proof（断点自证，防"乱连链"）

```json
{"relation":"原料→产品","from":"原料 X","to":"目标品","ratio":"1.55 吨/吨",
 "share":"占该路线产能 70%（口径…）","evidence":"工艺依据…","src":"…","checked":true}
```
`checked:false` → 报告标红、caveat 提示"数字不可外引"。

## balance（供给库存与开工）

```json
{"k":"港口总库存","v":"36.72 万吨","date":"2026-10-14","prev":"周环比 +6.21 万吨",
 "scope":"某资讯样本","src":"…","level":"低/中/高（可选）"}
```
`v` 用字符串以便写区间/多值；`scope` 必填（不同样本不可相加）。

## events（事件）

```json
{"date":"2026-10-19","tag":"检修","title":"…","detail":"…",
 "impact":"利多（对价格，事后）/ 利空 / 中性 / 双向",
 "evidence":"公开报道 | 机构观点 | 传闻 | 待确认",
 "price_ref":3143,"after":"之后的报价/供需变化","src":"…","url":"…"}
```
`日期 > asof` 报 error；`evidence` 为传闻/待确认 → 自动进"未采纳消息"。

## procurement（我方参数）

```json
{"inventory_days":12,"monthly_usage":3000,"purchase_frequency":"每周补单",
 "current_source_points":["华东太仓","常州"],
 "contract_terms":["含税现汇，罐区自提"],
 "notes":"库存与用量为示例假设值，请替换为 ERP 实际数"}
```
`inventory_days` 必填（否则无法算"可支撑到哪天"）。若为假设值，必须在 `notes` 里写"示例/假设"，脚本会在 Excel 标"假设值"。

## facts / talk / gaps / caveats / sources

```json
"facts": [{"kind":"价格","k":"…","v":"…","note":"…","src":"…"}],
"talk":  [{"q":"供应商问：…","a":"回答（禁用方向词）"}],
"gaps":  [{"item":"…","status":"缺口|口径冲突|待更新","detail":"…","impact":"…","fix":"…"}],
"caveats":["口径提醒…"],
"sources":[{"name":"…","date":"2026-10-16","type":"研究报告","url":"https://…"}]
```
`talk[].q` 允许出现"看跌/抄底"等客户原话；`talk[].a` 绝对禁止。

---

## 校验级别（validate.py）

| 级别 | 触发 | 后果 |
|---|---|---|
| ERROR | 缺 `meta.product/asof`；`spot` 无价；事件日期 > asof；`gaps` 缺 item/detail；方向性词；`primary_point` 不在序列里；日期不可解析 | 流水线停止，不出产物 |
| WARN | 缺 `point/spec/tax/basis/date/src`；缺 `chain_proof`；缺 `procurement.inventory_days`；URL 非 http；`balance/cost_lines` 空 | 继续，但缺口会进报告 |
| INFO | 单点序列 <3 条；外币口径；传闻事件；未通过链路；锚价距 asof >3 天 | 仅提示 |

## 命名与目录约定

```
<项目>/
├─ research.json          手填
├─ raw/                   原始抓取（期货日线、文章文本）
└─ out/                   产物（HTML + Excel）
   └─ build/data.json     中间数据
```
