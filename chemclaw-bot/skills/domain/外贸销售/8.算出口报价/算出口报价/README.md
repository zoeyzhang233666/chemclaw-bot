# 算出口报价（化工品外贸）

给外贸销售用的**出口报价测算工具**：从出厂价出发，按 Incoterms® 2020 拆成本段，算出 FOB / CFR / CIF 参考价、人民币与外币报价、运费/汇率/毛利敏感性。

交付两件东西：

- **交互式 HTML 计算器** — 单文件、离线、首屏即结论，改运费/汇率/毛利实时重算
- **Excel 工作簿** — 12 张表，全部公式驱动，改一个单元格全表联动

---

## 三条使用原则

1. **系统不给价**。运费、保险费、税费、毛利——全部由你提供。没有依据的，系统写"待补数据"，不编。
2. **系统不算商业价格**。它算出的是"在你的成本与毛利假设下，各术语对应的报价是多少"，不等于你该报多少。
3. **退税单列，不抵减成本**。退多少、要不要贴进报价，是你的商业决定。

---

## 三分钟上手

### 1. 写一个输入文件

参考 `examples/soda-ash-qingdao-jakarta/input.json`，最少只需要这些：

```json
{
  "product_cn": "重质纯碱",
  "product_en": "Soda Ash Dense",
  "hs_code": "2836200000",
  "quantity_mt": 500,
  "pol": "青岛港 Qingdao (CNQDG)",
  "pod": "雅加达港 Jakarta (IDJKT)",
  "exw_cny_per_t": 1450,
  "packaging_cny_per_t": 60,
  "inland_cny_per_t": 110,
  "port_cny_per_t": 95,
  "freight_usd_per_container": 1250,
  "container_load_mt": 25,
  "insurance_rate_of_cif": 0.003,
  "fx_to_cny": { "USD": 7.10 },
  "quote_currency": "USD",
  "gp_mode": "margin_on_price",
  "gp_value": 0.08,
  "gp_basis_term": "FOB"
}
```

### 2. 算一遍

```bash
python scripts/calc_engine.py input.json -o result.json
```

### 3. 生成交付物

```bash
python scripts/build_html.py input.json -o 报价计算器.html
python scripts/build_xlsx.py input.json -o 报价工作簿.xlsx
```

打开 HTML 即可用；打开 Excel 改任意参数看全表联动。

---

## 完整算例

`examples/soda-ash-qingdao-jakarta/` 是一个完整可运行的案例（重质纯碱 500 t，青岛 → 雅加达）：

| 术语 | 成本 ¥/t | 报价 ¥/t | 报价 USD/t |
|---|---|---|---|
| FOB | 1740.00 | 1891.30 | 266.38 |
| CFR | 2095.00 | 2277.17 | 320.73 |
| CIF | 2101.94 | 2284.71 | 321.79 |

> 其中内陆运费、港口费、海运费、装柜吨数、保险费率标注为 **SIMULATED（模拟值）**，仅用于演示完整计算流程，**不是实时运价**。真实报价必须替换为货代/保险公司的书面报价。

---

## 目录

```
算出口报价/
├── SKILL.md                 AI 入口（工作流与红线）
├── README.md                本文件
├── INSTALL.md               安装说明
├── PORTABLE_PROMPT.md       跨 AI 平台的独立提示词
├── references/              术语、公式、参数、敏感性、校验、QA、出处
├── scripts/                 引擎与生成器
├── templates/               HTML 模板
├── products/                产品画像
└── examples/                完整算例
```

---

## 环境

- 生成期：Python 3.9+，`openpyxl`（生成 Excel 时）
- 使用期：任意现代浏览器，**零依赖、离线**

详见 `references/portability.md`。

---

## 版本

v1.0.0 — 见 `CHANGELOG.md`
