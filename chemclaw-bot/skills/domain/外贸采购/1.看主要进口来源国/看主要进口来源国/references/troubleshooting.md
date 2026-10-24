# 排错手册

## Comtrade

**403 Out of call volume quota**
公共 API 有配额。等待提示的时间（通常 30–35 分钟）后再跑；
或减少请求：只抓份额 >0.5% 的国家、只抓 5 年。

**400 Invalid parameter value**
检查是否传了 `partnerCode=*` 或 `all`（不允许），
或 `period=2023,2024`（预览版一次只能一个年份）。

**Maximum number of periods for preview is 1**
同上，改成单年循环。

**某国某年无数据**
`data` 为空数组。先确认该国该年真的没贸易，还是没报告。
若是报告缺失，标记 gap，不要写 0。

## 数据质量

**netWgt 为 null 但 amount 有值**
该国该年没报数量。不要把 0 当分母算单位价值。

**单位价值异常高/低（>10 万美元/吨 或 <100 美元/吨）**
通常是金额极小（几万美元）导致除法失真，或是单位（kg/L/磅）混用。
先用 `V06-unit-value` 筛出来，再人工判断。

**某国对华出口 > 该国对华进口统计**
镜像偏差。正常范围 CIF 比 FOB 高 5–20%。超过 30% 必须解释：
转口、原产地误判、统计滞后、低报价值。

**合计不等于分项之和**
检查是否有 "Other Asia, nes"(490)、"Areas, nes"(899) 这类合并项，
以及是否把世界合计行（partnerCode 0）与本国自身（partnerCode = 本国）
误当作来源国。

## HTML 报告

**页面空白 / 地图不显示 / 报 "Unexpected token '{'"**
几乎总是 JSON 注入方式错误。**把大 JSON 放进
`<script type="application/json">` 再用 `JSON.parse` 读取**，
不要写成 `window.X = {...}`。

**占位符替换后出现 `\1` 之类的残留**
用了 `re.sub`。改用 `str.replace`，或把可能含反斜杠的内容最后替换。

**地图全部灰色**
GeoJSON 的 `geometry.type` 大小写错（应为 `Polygon` / `MultiPolygon`），
或 feature 里没有可用于着色的 `properties.iso3`。

**打开需要联网**
ECharts/Leaflet/地图数据必须内联；底图用内联矢量陆地面，
不要用在线瓦片（会有 CORS 与离线两个问题）。

**窄屏横向滚动条**
给 grid 子项加 `min-width: 0`。

## Excel

**openpyxl 无法写 numWgt=None**
写数字前先判断 None，写"未找到"文本并用特殊格式标出。

**合并单元格报错 "Can't merge single cell"**
`merge_range(r, c, r, c, ...)` 合并单个单元格是无效的，改用 `write`。

## 判断类

**不知道某个装置产能**
写 "not found"，进缺口表。**不要用行业平均值或"约"来填。**
一个带引用的缺口，比一个无引用的数字有用得多。
