# 换品种 / 换品种组合 / 换数据源

本技能对品种无硬编码依赖。切换只需要改配置与品种库。

---

## 1 增加一个品种

### 第 1 步：确认 secid

`scripts/common.py` 的 `PRODUCT_LIB` 格式：

```python
PRODUCT_LIB = {
    '甲醇': ('115.MAM', 'MAM', '郑商所', 'MA'),
    #       主连secid    主连标签   交易所    合约代码前缀
}
```

新增一行即可：

```python
'尿素': ('115.URM', 'URM', '郑商所', 'UR'),
'玻璃': ('115.FGM', 'FGM', '郑商所', 'FG'),
'纯碱': ('115.SAM', 'SAM', '郑商所', 'SA'),
'塑料': ('114.lm',  'lm',  '大商所', 'l'),
'乙二醇': ('114.egm', 'egm', '大商所', 'eg'),
'苯乙烯': ('114.ebm', 'ebm', '大商所', 'eb'),
'焦煤': ('114.jmm', 'jmm', '大商所', 'jm'),
'螺纹钢': ('113.rbm', 'rbm', '上期所', 'rb'),
'铜':   ('113.cum', 'cum', '上期所', 'cu'),
'碳酸锂': ('225.lcm', 'lcm', '广期所', 'lc'),
```

### 第 2 步：探活

```bash
python scripts/fetch_futures.py 尿素 --probe
```

返回 `rc=0` 且有行情才算成功。若失败：

- `rc=100` / 空数据 → 大概率 secid 前缀或代码大小写错；
- 全部 host 都 `RemoteDisconnected` → 等待几分钟重试，或换 host。

### 第 3 步：确认合约月份

```bash
python scripts/fetch_futures.py 尿素 --list
```

列出当前挂牌合约与主力。**不要凭记忆猜合约代码**——2026 年做研究时，`2601` 及更早的合约都已到期，探活会 return 空，容易误判为「这个品种接口不支持」。

### 第 4 步：抓取

```bash
python scripts/fetch_futures.py 尿素 --contracts 2701,2705,2709 --beg 20250101 --out raw
```

主连与主力月份都要抓，`main_month_label` 才能填。

### 第 5 步：在研究配置里登记

```json
"futures": {
  "尿素": {"secid": "115.URM", "series_label": "UR主连",
           "name": "尿素主连", "main_month_label": "UR2701"}
}
```

---

## 2 换品种组合

`research.json` 的三个地方决定覆盖范围：

1. `report.products` —— 摘要卡与筛选项的品种列表；
2. `indicators[].product` —— 每条指标归属哪个品种；
3. `futures` —— 要抓哪些品种的行情。

页面会自动按 `report.products` 生成摘要卡与筛选器。**新增品种不用改 HTML 模板**。

注意：模板的品种主题色按 `甲醇 / PP / PVC` 三个硬编码 class 上色（`p-methanol / p-pp / p-pvc`），其余品种走默认青色。若要为每个新品种配色，改 `templates/brief.html` 里的 `prodCls()` 与对应 CSS：

```css
.card.p-urea::before{background:#0891b2}
```

```js
const prodCls = p => p==='甲醇'?'p-methanol':(p==='PP'?'p-pp':(p==='PVC'?'p-pvc':
                    (p==='尿素'?'p-urea':'')));
```

---

## 3 换数据源

### 换成其他期货行情接口

只要能产出同样结构的 JSON，`assemble.py` 完全不用改。文件格式（`raw/<label>.json`）：

```json
{
  "label": "MA主连",
  "secid": "115.MAM",
  "rows": [
    {"d": "2026-10-19", "o": 3150, "c": 3143, "h": 3160, "l": 3130, "v": 123456, "oi": 7890},
    {"d": "2026-10-20", "o": 3140, "c": 3117, "h": 3150, "l": 3100, "v": 234567, "oi": 7654}
  ]
}
```

字段：`d` 日期、`o` 开、`c` 收、`h` 高、`l` 低、`v` 成交量、`oi` 持仓量。前五个必需。

### 换成其他现货来源

现货是手工填进 `research.json` 的，没有程序依赖。换来源只需改 `source` 与 `source_url` 字段——但**必须重新核对四要素**（规格/区域/单位/税基），不同来源的口径常常不同。

### 换事件来源

`raw/events_raw.json` 的结构：

```json
{"events": [
  {"id": "E01", "products": ["甲醇"], "event_type": "geo",
   "entity": "霍尔木兹海峡", "title": "...", "detail": "...",
   "event_date": "2026-10-16", "quant": "...", "impact_path": "...",
   "status": "ongoing", "recorded_before": false,
   "source": "...", "source_url": "..."}
]}
```

`dedupe.py` 只依赖 `event_type` / `entity` / `quant` / `title` / `detail` / `event_date` / `status` / `recorded_before` 这几个字段。

`event_type` 可用的值见 `dedupe.py` 的 `TYPE_FAMILY`；用了未登记的类型也能跑，只是不会被归入类型族、去重会更保守。要扩展就改 `TYPE_FAMILY` 和 `assemble.py` 的 `TYPE_CN`（中文名）。

---

## 4 换产业链结构

`chain` 字段用于 Excel 的「品种与产业链」表和读者理解影响路径：

```json
"chain": {
  "甲醇": {
    "up": ["动力煤", "天然气", "伊朗进口甲醇"],
    "mid": ["国内甲醇装置", "沿海港口库存"],
    "down": ["MTO", "甲醛/醋酸/二甲醚"],
    "drivers": ["霍尔木兹通航", "MTO 利润", "11月进口回升"]
  }
}
```

`drivers` 是本期的核心变量清单——写它的过程其实就是在梳理「今天该盯哪几条线」，建议每期重新审视。

---

## 5 换市场（境外/其他资产）

当前实现服务于国内商品期货（含税/不含税、涨跌停、主力换月等特征）。若用于境外市场：

- 税基字段填 `—` 或 `不含税`，基差章节的税基说明要相应改写；
- 涨跌停与保证金规则不同，`significance()` 的价格阈值需要重设；
- 主力换月的 8% 阈值可能不适用（部分市场连续合约不跳接），应关闭 `main_contract_day_pct` 的换月判定。

---

## 6 无代码扩展：只想要不同版面

- 改色调：`templates/brief.html` 顶部的 `:root` 变量（`--accent` 等）；
- 改模块：`MODULES` 数组（每项 `[key, 中文标题, 说明]`），key 需与指标的 `module` 对应；
- 加一个模块：在 `MODULES` 加一项，并在 `moduleBody()` 里给出该模块取哪些指标；
- 改首屏卡片内容：`cards` 函数里的 `rows` 数组。

改完必须重跑 `check_html.py` 与 `simulate_render.js`——DOM 模拟器会验证每个品种仍有 5 个模块、图表 option 生成正常。
