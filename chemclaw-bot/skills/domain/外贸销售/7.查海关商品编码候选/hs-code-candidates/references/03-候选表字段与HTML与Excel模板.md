# 候选表字段、输出模板与对外话术

本文件是**数据字典 + 模板**。`scripts/build_html.py` 与 `scripts/build_workbook.py` 直接读 `case.json`，字段名必须与本文件一致。

---

## 一、case.json 顶层结构

```jsonc
{
  "meta": {                        // 口径
    "case_id": "HS-<产品>-2026-001",
    "query_date": "2026-10-19",
    "hs_version": "HS 2022 /《中华人民共和国进出口税则（2026）》（税委会公告2025年第12号，2026-01-01实施）",
    "rebate_version": "出口退税率文库 2026C 版（税总货劳函〔2026〕214号）"
  },
  "product": {                     // 产品属性
    "name_cn": "", "name_en": "", "cas": "", "aliases": [],
    "appearance": "", "form": "", "purity": "", "is_mixture": "",
    "use": [], "retail": "", "hazard": ""
  },
  "candidates": [ /* 见下 */ ],
  "ambiguity":  [ ["编码对/概念对", "判断要点", "为什么必须分清"] ],
  "six_tree":   [ ["层级", "内容"] ],
  "foreign":    [ { "country","hs6","sub","rate","note","src","url","level" } ],
  "missing":    [ ["M1","缺失信息","影响哪个编码决策","高/中","如何补证","后果"] ],
  "ac":         [ ["编码","名称","判断","理由","证据等级"] ],   // 误配清单（A-void-confusion）
  "regulatory": [ { "id","topic","conclusion","basis","level","condition","todo","effect" } ],
  "confirm":    [ ["Q1","问题","影响哪项结论","找谁确认","提出方"] ],
  "sources":    [ { "id","name","publisher","docno","date","url","level","used_for","verified","note" } ],
  "not_advice": ""
}
```

---

## 二、候选（candidates[]）字段字典

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | str | ✔ | C1、C2… 稳定编号 |
| `rank` | int | ✔ | 优先级，1 最高 |
| `code10` | str | ✔ | 中国报关 10 位编码（数字串，保留前导零） |
| `hs6` | str | ✔ | 国际 HS 6 位，形如 `4002.19` |
| `title` | str | ✔ | 人话标题，如"初级形状热塑丁苯橡胶（非充油 SBS）" |
| `name` | str | ✔ | 税则/数据库口径品名 |
| `verdict` | str | ✔ | 首选 / 并列候选 / 兜底候选 / 条件性候选 / 形态性候选 |
| `confidence` | str | ✔ | 高 / 中高 / 中 / 中低 / 低 + 适用前提 |
| `conditions` | str[] | ✔ | 成立条件，逐条，缺一不可 |
| `why` | str | ✔ | 为什么是这个码（1–3 句） |
| `basis` | str[] | ✔ | 法律依据，引用到注释/条文名 |
| `vuln` | str | ✔ | 风险点：什么情况会被推翻 |
| `mfn` `gen` `export_tax` `rebate` `vat` | str | ✔ | 税率字符串，含 `%` |
| `reg` `ciq` | str | ✔ | 监管条件、检验检疫类别（无则填 `无`） |
| `decl_elems` | str[] | ○ | 申报要素 |
| `agreement_rates` / `rcep` | obj | ○ | 国别 → 税率 |
| `url` | str | ✔ | 编码详情来源 |
| `rebate_status` | str | ○ | 退税率核验状态说明 |
| `tariff_source` | obj | ○ | 税则原文出处 `{name,url,level,note}` |

### 状态词表（只能用这些）

- `verdict`：首选 / 并列候选 / 兜底候选 / 条件性候选 / 形态性候选 / 不适用
- `confidence`：高 / 中高 / 中 / 中低 / 低（必须带前提括号）
- 证据等级：`A 官方原文` / `B 二手或供应商原始文件` / `C 第三方数据库` / `D 待核验`

---

## 三、HTML 要求的 9 个区块（与需求 1–7 条一一对应）

| 区块 | 回答哪条要求 |
|---|---|
| ① 归类路径 | 说明"怎么收敛"，让人看懂不是凑码 |
| ② 候选编码 | 需求 1：候选 + 归类理由 + 依据 |
| ③ 法律依据 | 需求 3：法律依据（条文原文 + 作用） |
| ④ 歧义与误配 | 需求 2：存在歧义时列候选及适用条件；不强行凑 |
| ⑤ 编码层级 | 需求 4：国际 6 位 / 中国 10 位 / 目的国层级 |
| ⑥ 监管条件 | 需求 6：各候选出口监管条件 + 税率 |
| ⑦ 缺失信息 | 需求 5：检查关键缺失信息 |
| ⑧ 待确认 | 需求 7：需报关行/预裁定确认的问题 |
| ⑨ 来源 | 每个结论可追溯 |

---

## 四、Excel 工作表（13 表）

| 表 | 用途 |
|---|---|
| 00_封面与口径 | 案例号、查询日期、HS 版本、退税文库、免责声明 |
| 01_产品属性 | 每个归类相关特征一行：取值、来源、影响、等级、是否确认 |
| 02_候选编码 | 候选总表（含税率、监管、检疫） |
| 03_归类依据 | 逐条候选 × 逐条依据 |
| 04_缺失信息 | 缺失字段与补证路径 |
| 05_歧义与误配 | 歧义对 + 误配/过期编码 |
| 06_编码层级对照 | HS6 → 中国 8/10 → 目的国 |
| 07_关税税率 | 各候选 × 各协定/RCEP 税率矩阵 |
| 08_出口监管条件 | 结论 + 依据 + 适用条件 + 仍需确认 |
| 09_申报要素填写 | 申报要素逐条填写建议与易错点 |
| 10_待确认问题 | 带责任方的确认清单 |
| 11_来源链接 | 可点击来源与核验情况 |
| 12_校验与统计 | 数量自检 |

---

## 五、对外话术模板

**给客户（英文）**

> The product is **{chemical identity}**, **{oil-extended: no / yes X%}**, **{filler: none / contains …}**, **{uncured / cured}**, supplied in **{form}**.
> Under the PRC Customs Tariff (2026) it classifies under **{10-digit code} — {name}**.
> Please confirm the import code in your tariff under **HS {6-digit}**; the national subdivisions differ between countries.
> Final classification is subject to the ruling of China Customs.

**给报关行（中文）**

> 品名/SBS，CAS 9003-55-8，未充油、未加填料、未硫化，颗粒状，非零售包装，用途【】。
> 我们初判 4002.1913（热塑丁苯橡胶），备选 4002.1914（若充油）/ 4005.9900（若含填料）。
> 请确认：①10 位编码；②申报要素"是否充油、热塑"如何表述；③2026C 版退税文库退税率；④是否需要预裁定。

**对内部（销售人员自用）**

> 这个编码的退税是【】%，一旦客户要求改成"改性料/复配料"配方，可能掉到 4005（退税 0%），报价前必须先拿配方。

---

## 六、写作纪律

1. 每个候选都必须有 `vuln`（风险点），没有风险点的候选说明还没想清楚。
2. `confidence` 必须带前提，如"中高（条件成立时）"。
3. 税率必须写 `%`，来源不明的写"—"，不要留空。
4. 凡是"不适用"的结论，`basis` 里必须写清查了哪份文件。
