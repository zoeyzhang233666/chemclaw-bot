# 换一个品种：最小改造清单

本技能的统计核、图表、Excel 结构、三重校验全部与品种无关。
换品种只改**两个地方**：数据源适配器、文案。

---

## 一、目录约定

```
<你的项目>/
  raw/                    原始抓取（可删可留，但保留能复现）
  build/data.json         装配产物 ← 唯一数据源
  data/events.json        可核验事件（人工整理）
  out/                    HTML / XLSX / 截图 / QA 报告
```

## 二、你要产出的东西

只有一个：**统一观测数组**，写进 `raw/observations.json`：

```json
{
  "s1": [
    {"date": "2026-07-28", "lo": 1180, "hi": 1250, "mid": 1215,
     "basis": "华东重质纯碱主流市场报价",
     "url": "https://www.100ppi.com/news/detail-20260728-5990717.html"}
  ],
  "s2": [],
  "s3": []
}
```

- `s1` = 主口径（客户问的那句话）
- `s2` / `s3` = 辅助口径，**可以留空数组**

## 三、改哪里

### 3.1 `scripts/assemble.py`

改 `DATA["meta"]` 里的六项描述：

```python
"meta": {
    "product": "纯碱",                                  # ← 品种
    "spec": "重质纯碱（≥99.2%，GB/T 210-2022 优等品）",   # ← 规格
    "region": "华东",                                    # ← 地区
    "unit": "元/吨",                                     # ← 单位
    "tax": "含税（增值税13%）",                           # ← 含税
    "delivery": "主流市场报价 / 实单商谈",                # ← 交付
    "source": "生意社（100ppi.com）",                     # ← 来源
}
```

再改序列命名与 `series_of()` 的字段映射（区间型用 `lo/hi/mid`，单点型用 `value`）。

### 3.2 `data/events.json`

把可核验事件换成新品种的。**没有就留空数组**——不要为了好看编事件。

### 3.3 `scripts/build_html.py`

只需改 `__TITLE__` 一行（如果品种名硬编码了的话）。

### 3.4 `scripts/build_xlsx.py`

改 `s00()`/`s01()` 里的标题与口径表内容。

**其余全部不用动**：`price_stats.py`、`validate.py`、`check_html.py`、`check_xlsx.py`。

---

## 四、运行

```bash
# 1. 装配
python scripts/assemble.py

# 2. 数据校验
python scripts/validate.py

# 3. 出 HTML
python scripts/build_html.py build/data.json --out "out/<品种>-历史价格位置分析.html"
python scripts/check_html.py "out/<品种>-历史价格位置分析.html"

# 4. 出 Excel
python scripts/build_xlsx.py build/data.json --out "out/<品种>.xlsx"
#    重算（LibreOffice Kit）
node <cli.js> recalculate --input "out/<品种>.xlsx" --output "out/recalc.xlsx"
python scripts/check_xlsx.py "out/recalc.xlsx" build/data.json
```

三个检查器都必须是 `FAIL=0` 才能交付。

---

## 五、换源时的常见情况

| 情况 | 处理 |
|---|---|
| 源给的是**单点价**（如基准价、结算价） | 用 `value` 字段，`lo=hi=mid=value` |
| 源给的是**周度/月度均价** | 可以做，但要在报告里明确频率；波动率算法需相应调整 |
| 源只有 **1–2 年**数据 | 正常交付，但 3 年/5 年窗口会显示「不计算」或标注真实样本范围 |
| 源是**付费**的（卓创/隆众/Mysteel） | 尊重授权，只展示统计结果与必要的核验信息 |
| 源有**多规格**（如液碱 32%/50%） | 各规格**分别成序列**，不要混算 |
| 数据里有明显的**口径切换点** | 必做覆盖率检测，按 `method.md` 第 8 节披露 |

---

## 六、验收口诀

> **三个干净**：数据干净（每条可追溯）、统计干净（分位是计数）、交付干净（HTML 无报错、Excel 无错误值）。
>
> **三个绝不**：绝不预测、绝不插值、绝不把区间位置叫分位。
