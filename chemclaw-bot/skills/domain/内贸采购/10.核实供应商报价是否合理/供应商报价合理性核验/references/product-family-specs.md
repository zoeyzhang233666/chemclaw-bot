# 品种族规格文件（specs/）怎么写

`specs/` 是**唯一允许存放品种专属规则的地方**。`scripts/` 里的代码对任何品种一视同仁——
没有"乙二醇的工业级比聚酯级便宜 X 元"这种硬编码，也不允许出现。

## 一、为什么必须分开

同一个"规格差异"，在三种品种族里含义完全不同：

| 品种族 | 规格差异的典型形态 | 能不能用统一系数？ |
|---|---|---|
| 大宗化工品（乙二醇、甲醇、PTA） | 聚酯级 / 工业级 / 纤维级，含量 ≥99.9% vs 未注明 | **不能**：价差随行情从 0 到数百元跳动 |
| 精细化工品（助剂、表活、电子级） | 含量、色度、金属离子、水分、批次稳定性 | **不能**：一单一价，无公开均价 |
| 中间体（如某类酯、醚） | 上游工艺路线（煤制/乙烯法）、异构体比例 | **不能**：取决于下游用途 |

所以规则写在 `specs/<品种>.json`，报告在用到时引用并注明出处。乙二醇的规则**不得**变成默认值。

## 二、规格文件结构

```jsonc
{
  "family": "乙二醇（MEG）",
  "family_code": "meg",
  "scope_note": "本文件只适用于乙二醇……其他品种须新建 specs/<品种>.json",
  "product": {
    "cn_name": "乙二醇", "aliases": ["MEG", "EG"], "cas": "107-21-1",
    "unit_canonical": "元/吨",
    "futures": {"exchange": "DCE", "continuous_symbol": "EG0",
                 "basis_note": "期货不含税，不能直接减现货"}
  },
  "vat_rate": 0.13,
  "spec_terms": {                    // 术语映射：报告里怎么解释供应商写的"工业级"
    "聚酯级": {"grade": "聚酯级", "purity": "≥99.9%", "premium": "同地区最高价档"},
    "工业级": {"purity": "含量未明确", "premium": "通常低于聚酯级"}
  },
  "regions": {                       // 该品种的计价区域与基准点
    "华东": {"primary": "张家港", "sub": ["太仓", "江阴"]}
  },
  "delivery_bases": {"出厂": "…", "到厂": "…", "库提": "…", "到港": "…"},
  "packing": {"散水": {"adj": 0}, "吨桶": {"adj_gap": "需供应商确认"}},
  "annual_anchors": [                // 年度锚点（≠序列，不出分位）
    {"year": 2024, "value_low": 4300, "value_high": 4800, "value_avg": null,
     "nature": "年度首末价 + 全年区间", "method": "怎么来的",
     "source": "URL", "confidence": "high"}
  ],
  "events": [                        // 近期已发生的行情变化（事实 + 来源）
    {"d": "2026-10-19", "title": "…", "fact": "…", "price_effect": "…",
     "source": "…", "phase": "属于哪个价格阶段"}
  ],
  "gaps_declared": ["该品种拿不到哪些数据"],
  "comparability_notes": {"purity": "…", "region": "…"}
}
```

## 三、写 specs 的四条纪律

1. **只写可追溯的规则。** 每个 `premium`/`adj` 都要能指向一个来源或一次同日真实报价对比；
   拿不到就写 `adj_gap`，别编系数。
2. **`confidence` 必须诚实。** 由走势图坐标目测得来的区间标 `low`；官方/媒体明确给出的标 `high`。
3. **`annual_anchors` 不是序列。** 它只能用于"报价相对某年锚点高多少/低多少"，
   **绝不能**拿去算分位、也不能插值成曲线。
4. **`scope_note` 必写。** 这是给下一个改这份文件的 agent 看的护栏。

## 四、新建一个品种的清单

```
specs/<code>.json          ← 复制本文件的字段，重写内容
examples/<序号>-<品种>-<地区>/
  research.json            ← 按 data-contract.md 填
  series/*.json            ← 拿到的序列（没有就不放，缺口写进 gaps）
  input/                   ← 报价单原文/截图
  output/                  ← 生成的 HTML + Excel
```

然后：

```bash
python scripts/model.py examples/<目录>/research.json --out work/x_model.json
python scripts/build_html.py work/x_model.json --out examples/<目录>/output/x.html
python scripts/build_xlsx.py work/x_model.json --out examples/<目录>/output/x.xlsx
python scripts/check_output.py work/x_model.json examples/<目录>/output
```

## 五、反例（千万别这么写）

```jsonc
// ✗ 把乙二醇的行情规律当成通用规则
"premium_rules": {
  "工业级": "-300 元/吨",          // 对甲醇毫无意义，对精细品更是错的
  "华东": "+55 元/吨库提溢价"       // 这是某一天的观测值，不是常数
}
```

正确做法：把这类观测**写进 research.json 的 `evidence_summary.explainable`**，
注明"同日两个真实报价之差"和日期——它是**当次证据**，不是**品种常数**。
