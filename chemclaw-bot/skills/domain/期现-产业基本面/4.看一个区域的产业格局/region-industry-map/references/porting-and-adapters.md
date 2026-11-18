# 移植与扩展

这份技能被设计成"数据换、代码不换"。本文件说明换品种、换区域、换工具链时具体要动哪里。

---

## 1. 换品种 / 换区域（最常见的用法）

**只改 `regions.json`，一行代码都不动。**

| 要改的位置 | 例 |
|---|---|
| `meta.product` | "纯碱（碳酸钠 Na2CO3）" → "尿素（CO(NH2)2）" |
| `meta.region` / `region_level` / `focus_provinces` | "山东省" / "省" / `["山东"]` |
| `meta.capacity_unit` / `capacity_basis` | "万吨/年" / "合成氨产能" |
| `meta.capacity_scope_total` | 换成新区域的公开口径（没有就不填） |
| `sites[]` / `parks[]` / `projects[]` / `upstream[]` / `downstream[]` / `nodes[]` | 全部换成新事实 |
| `sources[]` | 换成新来源 |
| `narrative` | 重写（这是最花时间的部分） |

### 唯一必须同步改的代码：工艺枚举

`scripts/common.py`：

```python
PROCESSES = ('氨碱', '联碱', '天然碱', '其他', '未知')
```

换品种时按新品种的真实工艺路线改。例：

| 品种 | 建议枚举 |
|---|---|
| 纯碱 | 氨碱 / 联碱 / 天然碱 |
| 烧碱 | 离子膜 / 隔膜 / 水银（历史） |
| 尿素 | 煤头 / 气头 / 焦炉气 |
| 钛白粉 | 硫酸法 / 氯化法 |
| 磷酸铁锂 | 固相法 / 液相法 / 铁红法 |
| 玻璃 | 浮法 / 压延 / 拉引 |

如果不改，`validate.py` 会对每个站点报"工艺不在枚举内"警告（warning，不阻断）。

### 多区域（大区 / 全国）

- `meta.region_level` 改成 `大区` 或 `全国`，`region` 写"华东"或"全国"；
- `meta.focus_provinces` 填多个省，地图会一起高亮；
- `cities[]` 可以跨省（每条带 `province`），聚合会自动分省再汇总；
- 省级口径与全国口径同时存在时，`capacity_scope_total` 填全国，`narrative.coverage_note` 写明差额怎么来的。

---

## 2. 加一个新图层

地图图层由 `regions.json` 的 `layers[]` 驱动（留空时模板按默认 5 层渲染）。加层：

```json
"layers": [
  {"id": "producers", "label": "生产企业",  "on": true,  "shape": "circle"},
  {"id": "traders",   "label": "贸易商",    "on": false, "shape": "square"},
  {"id": "downstream","label": "下游用户",  "on": true,  "shape": "diamond"},
  {"id": "parks",     "label": "化工园区",  "on": true,  "shape": "park"},
  {"id": "projects",  "label": "新增项目",  "on": true,  "shape": "triangle"},
  {"id": "logistics", "label": "物流节点",  "on": false, "shape": "square"}
]
```

新图层要同时给数据：`sites[]` 里加 `role`，或新增数组（如 `stockpiles[]`）并在 `build_html.py` 的
`build_json()` 里透出。**模板不改样式协议的话，新图层会自动继承现有形状与配色。**

---

## 3. 换底图（换国家 / 换更细的行政级别）

当前底图：`scripts/assets/china_prov.json`（省级 GeoJSON，582 KB，35 个 feature）。

要换成市级：

1. 取一份市中图 GeoJSON，字段名里的 `name` 保持中文全称（如"潍坊市"）；
2. 覆盖 `scripts/assets/china_prov.json`；
3. `common.norm_city()` 负责把"潍坊"与"潍坊市"归一，确保匹配；
4. 重新构建，`qa.py` 的浏览器探针会检查地图是否真的画出路径。

要换国家：把 `assets/` 里的 GeoJSON 换掉，并改 `report.html` 里地图的
`center` / `zoom`（搜索 `geoCenter`）；`common.PROV_CENTER` 用于退化定位，一并替换。

**体积控制**：底图会被 gzip + base64 内联，压缩后约 1/8。市级底图（约 3000 个区县）压缩后仍在 1–2 MB，
可以接受；街道级就太重了，不要内联。

---

## 4. 换图表库 / 去掉图表

`report.html` 里所有图表都是 ECharts 实例，通过 `chart_guard(id, builder)` 创建。去掉某张图：
删掉对应 `<div class="chart" id="xxx">`，`chart_guard` 会自动跳过（它先检查元素是否存在）。

换库：只要保留 `chart_guard` 的签名（返回一个可销毁对象），其余随意。

---

## 5. 接自动化 / 批量跑

`build_all.py` 是纯命令行、无交互、退出码语义清晰（0 成功 / 1 失败）。批量：

```bash
for f in inputs/*.json; do
  name=$(python -c "import json,sys;d=json.load(open('$f'));print(d['meta']['product']+d['meta']['region'])")
  python build_all.py "$f" --out out --name "$name" --qa || echo "FAILED: $f"
done
```

也可以把 `build_html.build(path, out)` 与 `build_xlsx.build(path, out)` 当库函数直接调用。

### 定时刷新（项目与价格在变）

- 建议每月跑一次，`meta.asof` 与项目的 `status_asof` 一起更新；
- 只改动的字段：`projects[].status` / `status_asof`、`prices.observations`（追加新日期，不删旧的）；
- `prices.observations` 建议保留最近 12 个月，否则价格图会被历史数据压扁。

---

## 6. 已知限制（如实写在交付物里）

| 限制 | 说明 | 应对 |
|---|---|---|
| 注册企业数取不到 | 工商批量检索需付费口径，免费通道给不出可信的分市计数 | `cities[].registered = null`，KPI 显示"—"，缺口表登记 |
| 精确点位覆盖率低 | 现实里通常只有 1/3 的厂区能拿到精确坐标 | 用形状区分精度，县级/市级只作地区记录 |
| 不画运量 | 港口/铁路的分货种吞吐与流量几乎不公开 | `flows[]` 画定性流向，标注"不表示吨位" |
| 不折算需求 | 吨耗数据只有环评原辅材料表里有 | 没有来源就只描述下游规模，不给"年耗 X 万吨" |
| 集中度只看样本 | 样本覆盖率 < 100% 时 CR/HHI 只能说明结构 | 图上标"样本口径"，`concentration_note` 说明不能推导定价权 |

---

## 7. 给下一个接手的人的交接清单

- [ ] `regions.json` 里每条 `verify` 都是"还没做的事"，逐条看一遍
- [ ] `narrative.gaps` 按 P0/P1/P2 排序，P0 是下一次调研的起点
- [ ] `sources[].note` 写的是"引用了哪一句"，复核时只核这一句
- [ ] 否证条目（`capacity = null` + `note` 含"否证"）不要删，它们防重复劳动
- [ ] 跑一遍 `python scripts/selftest.py`，确认管线还是通的
