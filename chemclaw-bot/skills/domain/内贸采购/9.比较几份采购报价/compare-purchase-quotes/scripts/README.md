# 比较几份采购报价 · 使用说明

## 一分钟上手

```bash
# 1) 抽字段（PDF / XLSX / DOCX / 文本；图片需 OCR）
python scripts/extract_quotes.py 报价A.pdf 报价B.xlsx 报价C.png -o extracted.json

# 2) 把抽到的字段核对、补全，写成引擎输入（见下），算到厂成本
python scripts/quote_engine.py     # 先跑内置自检

# 3) 按 examples/ 的样式产出 HTML 报告 + Excel 工作簿
```

## 引擎输入格式

```python
from quote_engine import QuoteEngine

quotes = [
    {
        "code": "A",
        "price_raw": 6.20, "unit_raw": "元/公斤",       # 元/公斤 | 元/吨 | 元/桶 | 元/袋 | 元/升
        "barrel_kg": None,                              # 元/桶 或 元/袋 时必填净重
        "tax_included": True, "tax_rate": 0.13,
        "invoice": "special",                           # special | normal | unknown
        "purity": 0.9992, "spec_ok": True,              # 低于询价规格时 spec_ok=False
        "tiers": [[22, 6.20], [110, 6.17]],             # [下限吨, 单价]
        "pack_cost_single": 0.0,                        # 包装另计金额（元/吨）
        "freight_by": "buyer",                          # buyer | seller
        "freight_key": "hz_zhangjiagang",
        "capital_days": 21.0,                           # 加权付款天数（不是合同账期）
        "deposit": None,                                # 或 {"amount": 300000, "days": 180}
        "pack_deposit_per_unit": None,                  # 或 {"amount": 30, "unit_kg": 220}
        "vehicle_cleanup": False,
    },
]

eng = QuoteEngine(quotes, {"qty_ton": 200, "fund_rate": 0.045})
res = eng.compute_all()
for c, r in res.items():
    print(c, r["landed"], r["landed_purity"], r["rank"])
```

## 常用调用

| 需求 | 调用 |
|---|---|
| 改参数重算 | `QuoteEngine(quotes, {...})` 换 assumptions |
| 单参数敏感性 | `eng.sensitivity("freight", [0, 20, 42, 60, 80])` |
| 情景组合 | `eng.scenarios([{"name": "资金成本10%", "assumptions": {"fund_rate": 0.10}}])` |
| 市场压力 | `eng.price_sweep(4800, 6800, 21)` |
| 盈亏平衡量 | `eng.breakeven_qty("A", "B")` |

## 输出后必查

1. 分项加总 = 合计
2. 每个结果能追溯到公式与来源
3. 所有缺失字段都在待确认清单里，且带「向谁要什么」

## 示例文件

| 文件 | 说明 |
|---|---|
| `examples/乙二醇三供应商比价.html` | 交互式报告：KPI、统一比价表、成本瀑布、可展开明细、参数可调重算、敏感性、待确认 |
| `examples/乙二醇三供应商比价.xlsx` | 11 表工作簿：原始数据、标准化字段、公式、成本汇总（公式联动）、敏感性、情景、待确认 |
| `examples/供应商A_报价函.pdf` | 样例报价（键值分行，元/公斤，含税自提） |
| `examples/供应商B_报价明细.xlsx` | 样例报价（元/吨不含税，数量阶梯，价格联动，保证金） |
| `examples/供应商C_报价单.png` | 样例报价（元/桶，含运，铁桶押金，规格偏低） |

> 全部样例均为**模拟业务样例**，供应商名称、价格、条款均为虚构。

## 依赖

- `quote_engine.py`：零依赖（纯标准库）
- `extract_quotes.py`：零依赖；PDF 需 `pymupdf`，图片需 `pytesseract` + tesseract 中文包
