# 输出规范

## A. 交互式 HTML 报告

### 技术要求（强制）

| 项 | 要求 |
|---|---|
| 单文件 | 是。CSS/JS/数据全部内联 |
| 离线 | **零外部请求**。ECharts、Leaflet、地图数据全部内联 |
| 地图底图 | 用内嵌矢量陆地面，不用在线瓦片 |
| 响应式 | 1280 / 768 / 420 三档，`documentElement.scrollWidth - clientWidth == 0` |
| JS 错误 | 0 |
| 表格 | 超宽时容器内滚动，不撑破页面 |

### 结构（六段）

```
00 产品与口径确认   输入回显 + HS 候选表 + 口径边界 + 数据源 + 交叉核验
01 进口格局         6 个 KPI + 时间序列图 + 份额堆叠图 + 逐年份额表
02 国家比较         世界地图（份额着色，点击展开）+ 排序列表 + 主表 + 横向对比
03 产能结构         产能覆盖图 + 工艺表 + 装置级证据表（含原文引文）
04 关税与物流       关税表 / 非关税措施表 / 港口与咽喉点表（三个 tab）
05 采购含义         物流前提横幅 + 逐国建议卡 + 校验表 + 缺口表
```

### 交互要求

- 地图：悬停显示数字，点击打开证据抽屉
- 主表：点击表头排序；滑块按份额筛选；搜索框；复选 2–5 国
- 对比面板：指标行 × 国家列，可导出 CSV
- 证据抽屉：该国全部事实 + 产能来源 + 关税 + 物流 + 下一步按钮
- 键盘：`Esc` 关闭抽屉

### 视觉

- 配色：深青 `#0f6b63` / 沙金 `#b9ad8f` / 赭石 `#c07a1e` / 藏青 `#25344c`
- 背景 `#f2efe8`，纸感；卡片 `#fbf9f4`
- 数字一律 `font-variant-numeric: tabular-nums`
- 状态色：绿=可执行/通过，琥珀=需注意/受限，红=不可执行/缺口

### 地图着色

按中国进口**价值份额**五档：

| 份额 | 颜色 |
|---|---|
| >35% | `#0f4f4a` |
| 15–35% | `#2c7d72` |
| 5–15% | `#7bb3a1` |
| <5% | `#d8c7a1` |
| 无数据 | `#e9e4d6` |

### 关键实现提醒

1. **JSON 必须放进 `type="application/json"` 的 script 标签**，用 `JSON.parse` 读取。
   不要直接写成 `window.X = {...}`——大 JSON 与占位符替换叠加时极易产生语法错误，
   且报错位置会指向完全不相关的行。
2. 占位符替换顺序：**含 `{{`/`${` 的内容最后替换**，或用 `str.replace` 而非 `re.sub`
   （`re.sub` 会把 `\1`、`\g<1>` 当反向引用）。
3. GeoJSON 必须从 TopoJSON 转换，且 `geometry.type` 大小写正确（`Polygon`/`MultiPolygon`）。
4. 每个 feature 的 `properties` 里带 `iso3`，用它做着色键，不要靠数字 id 反查。

---

## B. Excel 工作簿

### 13 个 sheet 及必备列

| sheet | 必备内容 |
|---|---|
| `00_封面与结论` | 标题、口径、KPI、结论要点、使用前必读 |
| `01_关键指标` | 逐年 金额/数量/单位价值/同比/最大来源国；交叉核验块 |
| `02_中国进口来源逐年` | 年份×来源国×金额×数量×份额×份额(量)×单位价值 |
| `03_出口国自报` | 年份×报告国×对世界额/量×对华额/量×输华占比 |
| `04_国家汇总` | 每国一行：份额、5年均、同比、产能、覆盖率、关税、协定 |
| `05_生产企业与产能` | 装置级：企业、地点、产能、年份、工艺、沿海、口径、引文、URL、可信度 |
| `06_生产工艺` | 路线、使用范围、对采购含义 |
| `07_关税` | 来源国、协定关系、MFN%、优惠%、实际%、说明、协定状态 |
| `08_非关税措施` | 方向、措施、结论、注意、状态 |
| `09_物流与港口` | 咽喉点状态块 + 装货港表（距离/航时/状态/算法/风险）+ 中国卸货港 |
| `10_建议与不确定性` | 来源国、定位、事实理由、需核实的不确定性 |
| `11_数据来源` | 序号、来源名、URL、访问日期 |
| `12_缺口与方法` | 缺口表 + 校验结果 + 方法说明 |

### 格式规范

- 封面：深藏青标题带，KPI 大字（15pt 加粗青色）
- 表头：青色底白字，冻结前 3 行
- 数字：`#,##0.0`（千吨/百万美元）、`0.0%`（份额）
- 缺口单元格：**斜体红色**写"未找到"/"待核"，与其他单元格视觉区分
- 通过/需注意：绿色/琥珀色加粗
- 每个 sheet：A1 合并标题、A2 合并副标题（含来源与单位）
- 长文本列设置 `text_wrap`，行高 30–48

### 一致性

- 同一数字在 HTML 与 Excel 中必须完全一致（同一 `data.json`）
- 单位统一：千吨(kt)、百万美元(USD m)、美元/吨(USD/t)
- 小数位统一：千吨 1 位、百万美元 1 位、份额 1 位(%)、单位价值 0 位

---

## C. 数据骨架（JSON）

单一数据源，HTML 与 Excel 都从这里读：

```jsonc
{
  "meta": {"title","product","cas","grade","hs","hs8_cn","importer","sources":[...],"built"},
  "product_input": {"name","cas","grade","qty","destination","target_price","existing_suppliers"},
  "partners": [{                        // 每国一行，按份额降序
    "iso","label","value_m","qty_kt","unit_value","share","share5_avg",
    "growth_qty_yoy","cagr5_qty","exp_world_kt","exp_world_m","exp_cn_kt","exp_cn_share",
    "capacity_kt","capacity_sites","capacity_gap_sites","capacity_coverage","capacity_latest_year",
    "tariff":{...},"ports":[...]
  }],
  "totals": [{"year","value_m","qty_kt","unit_value"}],
  "years": [...],
  "share_series": {"SAU":[...]},        // 按价值份额
  "exp_series": {"SAU":{"years","world_m","world_kt","cn_m","cn_kt"}},
  "producer_rows": [{                  // 装置级证据
    "country","company","site","capacity_kt","year","route","coastal",
    "conf","source_url","quote","group_total"
  }],
  "process": [{"route","share","note"}],
  "tariff_detail": [{"country","agreement","agreement_status","mfn","pref","effective","note","tile"}],
  "ntm": [{"scope","item","finding","caveat","status"}],
  "logistics": {"asof","headline","headline_src","method_note","chokepoints":[...]},
  "ports": [{"iso","port","cn","chokepoint","nm","days","status","basis","risk"}],
  "cn_ports": [{"port","role","status"}],
  "cn_ports_note": "...",
  "checks": [{"iso","year","metric","pass_","detail"}],
  "china_import_partners": {"2025":[{"iso","value_m","qty_kt","share","share_qty","unit_value"}]},
  "data_notes": [{"k","v"}],
  "gaps": [{"item","why","fix"}]
}
```

### 字段约束

- `capacity_kt`：仅站点级合计，**不含集团合计行**；无披露则为 0/None
- `group_total_kt`：集团合计单列，不参与加总
- `share`：按**价值**；`share_qty` 按数量，两者不可混写
- `unit_value`：金额÷净重，报关加权平均，**非成交价**
- 所有比率用小数（0.547 表示 54.7%），渲染时再转百分比
