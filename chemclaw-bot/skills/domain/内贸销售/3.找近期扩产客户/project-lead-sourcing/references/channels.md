# 通道：取证通道清单、URL 模板与失败模式

**先跑 `python scripts/b2bctl.py probe <项目目录>`。** 下表是纯碱华东那一轮在**某台特定机器**上的实测结论，只作为起点参考——**你的机器/网络可能完全不同，以 probe 结果为准**。

## 0. 先分清两件事：可达 ≠ 可解析

这是本 skill 里最容易搞错、也最容易让人误判覆盖率的一点。

| | 证明什么 | 怎么测 | 失败表现 |
|---|---|---|---|
| **可达性** | 这个 URL 能取到内容 | `b2bctl probe` | 302 跳 https / 连接失败 / 403 |
| **可解析性** | 能从里面**抽出项目条目** | 跑具体适配器（`python -m tools.eia selftest`） | HTTP 200、HTML 很长，但**抽不出条目** |

**JS 渲染的列表页正是第二类**：它返回 200、HTML 有 30~140 KB、里面全是导航与栏目文字，看起来完全正常——但项目清单是前端用 JS 注入的，服务端返回的 HTML 里**一条项目都没有**。

我实测过：用「HTML 长度」或「中文项目名关键词命中数」都**判别不出来**（JS 壳页的命中数甚至比真列表页还高，因为导航文字更多）。**唯一可靠的判据是跑适配器看能抽出几条。**

所以 `channels.json` 里：
- `status: 可达` 只表示可达；
- `needs_adapter_test: [...]` 列出必须再做可解析性实测的列表型通道。

## 1. 通道清单

| 通道 | 类型 | URL | 可达性（参考） | 可解析性 |
|---|---|---|---|---|
| 巨潮资讯 全文检索 GET | 公告 | `http://www.cninfo.com.cn/new/fulltextSearch/full?searchkey=<关键词>&isfulltext=true&sortName=nothing&pageNum=1&pageSize=30` | 可达 | ✅ 结构化 JSON，按相关度排序，`seDate` 不生效需客户端过滤 |
| 巨潮资讯 检索 POST | 公告 | `POST http://www.cninfo.com.cn/new/hisAnnouncement/query` | 可达 | ✅ 须带 `Referer` + `X-Requested-With`，否则返回空。**标题检索 + 服务端真实日期区间** |
| 东方财富 公告目录 | 公告 | `http://np-anotice-stock.eastmoney.com/api/security/ann?stock_list=<代码>&begin_time=&end_time=` | 可达 | ✅ 返回 `art_code` + 完整标题 + 真实日期区间 |
| 东方财富 公告全文 | 公告 | `http://np-cnotice-stock.eastmoney.com/api/content/ann?art_code=<X>&page_index=N` | 可达 | ✅ 每页最多 5000 字。**唯一能稳定拿到公告正文文本的通道** |
| 巨潮公告 PDF | 公告 | `http://static.cninfo.com.cn/<adjunctUrl>` | 可达 | ⚠️ 取决于 PDF 有无文本层（扫描件抽不出） |
| 泉州市生态环境局 | 环评 | `http://sthjj.quanzhou.gov.cn/hjgl/hbsp/<栏目>/` | 可达 | ✅ **纯静态列表**，`index.html` / `index_1.html`… 项目名与正文都能读。栏目：`hpslqkgk` 受理、`nzchpspyjgk` 拟审批、`zchpspjdgk` 审批决定 |
| 铜陵市生态环境局 | 环评 | `http://218.22.184.155:8231/work_List_Search.aspx?LCJD=1&lcjd1=1` | 可达 | ✅ 少数能解析的市级 ASP 平台 |
| 江苏省生态环境厅 | 环评 | `http://sthjt.jiangsu.gov.cn/` | 可达 | ❌ **环评列表栏目 JS 渲染** → 抓不到清单 |
| 苏州市生态环境局 | 环评 | `http://sthjj.suzhou.gov.cn/szhbj/bjgs/bjgs_lists.shtml` | 可达（28 KB） | ❌ 列表页可达但条目 JS 渲染 |
| 潍坊市生态环境局 | 环评 | `http://sthjj.weifang.gov.cn/` | 可达（144 KB） | ❌ 首页可达，条目 JS 渲染 |
| 福建省生态环境厅 | 环评 | `http://sthjt.fujian.gov.cn/` | 连接失败 | — |
| 中国产业信息类新闻站 | 新闻 | `http://www.chinairn.com/` | 可达 | ⚠️ 可读但可信度低，需回溯原始来源 |

**注意第 3 列与第 4 列的分歧**：江苏厅、苏州、潍坊在 `probe` 里都显示 `可达`，HTML 长度也不小（28 KB / 144 KB），**但它们抽不出项目条目**。如果只看 probe 就以为"环评覆盖了 4 个省"，会严重高估覆盖率——这就是为什么第四块必须写清"环评只打通了泉州市与铜陵市"。

## 2. 核心失败模式：明文 HTTP 才能用

在受限网络环境里，**只有直接提供内容的明文 http 主机可用**；任何 `301/302` 跳转到 `https://` 的站点都连不上。

诊断方法（`tools/http.py` **不跟随跳转**，就是为了看清这一点）：

```python
from tools import http
r = http.fetch('http://例.com/页面')
print(r['status'], r['final_url'], r['note'])
# 302 https://例.com/页面 redirect->https   ← 本机不可达，别再重试
```

于是：
- **政府站点的地市级页面**（很多是 https）经常不可达；省级站点的栏目页常常是 JS 渲染（正文长度极小）。
- **判断"JS 渲染/空壳"的方法**：HTTP 200 但正文长度很小（几百字节）。probe 里用 `min_len` 卡这个。

## 3. 巨潮的两个接口别搞混

| | GET `/new/fulltextSearch/full` | POST `/new/hisAnnouncement/query` |
|---|---|---|
| 排序 | **相关度**（`sortName` 实测无效） | 时间 |
| 日期过滤 | `seDate` **不生效**，需客户端过滤 | **服务端 `seDate=起~止` 真实生效** |
| 用途 | 全文里找关键词命中（能拿到 `announcementContent` 高亮片段） | 按标题在某个时间区间里找公告 |
| 头要求 | 无 | **必须** `Referer` + `X-Requested-With: XMLHttpRequest` |

本 skill 的 `tools/cninfo.py` 两个都实现了，`query()` 是更精准的那个。

## 4. 东方财富：拿公告正文的唯一稳定途径

很多公告的**关键信息在正文里**（产能、投产时间、原辅材料），标题什么也说明不了。

```bash
# 1) 列出某代码在区间内的公告，按标题过滤
python -m tools.eastmoney list 600176 --begin 2026-01-01 --end 2026-12-31 --grep 池窑

# 2) 取某条公告的完整正文
python -m tools.eastmoney text AN202608201828203124
```

正文接口每页返回上限约 5000 字，`notice_text()` 会自动翻页拼接。

## 5. EIA 通道的使用方式

```bash
# 列出泉州市局某栏目的第 0~5 页
python -m tools.eia quanzhou --col nzchpspyjgk --pages 6

# 按关键词过滤（正则）
python -m tools.eia quanzhou --col hpslqkgk --pages 6 --grep "纯碱|硅|玻璃"

# 读详情页并做"正文闸门"
python -m tools.eia page <url> --keywords "碳酸钠,纯碱,Na2CO3"
```

**正文闸门很重要**：只有详情页正文里**真的出现本产品名/学名/分子式**（`hits > 0`），才认定本产品进入了该项目工序，否则不要收录（也许它用的是烧碱）。
这一步能挡掉大量"行业看着像但其实不用本产品"的误报——例如**拜耳法氧化铝用烧碱，不用纯碱**。

## 6. 如果宿主 agent 自带联网搜索

**那是你最强的通道**，优先用它来发现项目，然后**回溯到原始页面**作为 `来源`（不要用搜索结果的链接页当来源）。把它的能力登记进 `channels.json`：

```json
{ "host_tools": [ { "id": "host_web_search", "name": "宿主 agent 搜索",
                    "kind": "搜索", "status": "可用(宿主工具)",
                    "note": "用于发现线索；来源必须回溯到原始页面" } ] }
```

## 7. 给新国家/新地区扩展通道

`channels.default.json` 里的条目是**中国口径**的。换国家时直接改这个文件（或用 `probe --channels <你的注册表>`），把当地的：
- 公司公告/披露系统（如 SEC EDGAR、各交易所公告库）
- 环境/建设许可公示（相当于环评）
- 项目审批/招标平台

加进去。字段含义见文件内 `_comment`。**probe 只做"能不能连通、内容像不像目标页"的判断，不认国家**，所以扩展成本很低。