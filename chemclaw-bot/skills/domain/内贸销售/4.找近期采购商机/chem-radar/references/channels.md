# 取数通道手册（channels）— 化工品采购商机雷达 · 产品无关

> 本文件只回答**「怎么把数据抓回来」**，不回答「抓什么词」（→ [`product-profiling.md`](product-profiling.md)）。
> 面向执行者：一个 agent 读完本文件，只凭本机 `pwsh` 就要能复现每一个通道。
> **每跑一次任务，必须在产出目录落一份 `channels_used.md`**（见 §8）。本次所有「实测」结论必须写进它。

---

## 0. 环境事实与纪律（违反会白跑）

| 事实 | 说明 |
|---|---|
| 唯一抓取方式 | `pwsh` + `Invoke-WebRequest -UseBasicParsing` 或 `curl.exe`；Python 侧用 stdlib（见 `scripts/radarlib.py` 的 `http_get`）。**不要依赖浏览器自动化**。 |
| 搜索引擎 | `web_search` / 各搜索源在本环境**常被反爬、或返回与行业无关的失真结果**，历史上曾整体不可用；`web_fetch` 会拒抓非公网 IP。**只试一次**，不灵立刻跳 A/B 通道，不要换措辞反复试。搜索引擎结果只能当「发现线索」，不能当证据。 |
| TLS | 很多站点 `301` 跳 `https`，而部分环境**完全没有 TLS 能力**。脚本一律 **先试原协议、失败换协议**（见 §6）。跳 https 的站一旦换协议仍失败 → 放弃，别绕。 |
| 编码 / 中文 | 页面多为 UTF-8，`.Content` 可直接正则；乱码页是 GBK（转 `[Text.Encoding]::GetEncoding('GB2312')`）。政务站常**不声明 charset**，PS 按 Latin-1 解出乱码 → 用 `WebClient.DownloadData` + `UTF8.GetString`（§4.4）。**控制台中文一律乱码：含中文的响应先落 UTF-8 文件，再用 read 工具读。** |
| 日期基准 / 上下文 | 日期一律用当次 `config.task.baseline_date / window_start / window_end`，**不要写死在脚本或文档里**；每次请求后**先正则过滤再打印**，单页最多打 20 行，不要把整页 HTML 灌进上下文。 |

标准取数片段（复制即用）：

```powershell
$ProgressPreference='SilentlyContinue'
$H=@{"User-Agent"="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}
$r=Invoke-WebRequest -Uri "http://..." -UseBasicParsing -TimeoutSec 30 -Headers $H; $r.Content
```

---

## 1. 通道优先级 A / B / C / D

| 级 | 通道 | 能拿到什么 | 证据强度 | 用法提要 |
|---|---|---|---|---|
| **A** | ① 巨潮资讯 cninfo 公告全文检索 ② 公共资源交易平台 / 政采平台的 epoint 全文检索 ③ 政府环评与行政审批公示 | **一手原文**：采购量/金额/单价/供应商、招标标的与截止日、项目产能与原辅材料表 | ✅ 直接引用 | 主力。**默认从 A 起手**，A 全空才降级 |
| **B** | 企业官网直连（首页 → 新闻/公告/产品栏目） | 项目进展、产能、投产时间 | ✅ 自述可引，须写明「公司官网自述」 | 用于核实主体与项目；官网常有 `/news` 栏目 |
| **C** | 交易所 / 财经站公司资料页与公告接口（深交所、上交所、东方财富公告接口） | 公告目录与**公告全文文本**、公司资料 | ⚠️ 转载，须回找一手；全文接口可作快速通路 | 适合按股票代码定向拉某主体的全部公告 |
| **D** | 百科 / 行业报道 / 聚合站 | 行业结构、公司简介 | ❌ 不作证据，**只作发现线索** | 拿到线索后回 A/B 找原文 |

**铁律**
1. 一个通道**只试一次**，不灵就换（§0 搜索引擎同理）；**不做并发**——并发会被判为爬虫（§2 第 4 条）。
2. **任何意外的「0 条」都先当成「未验证」，不是结论**：补头/补参、间隔后重试一次，并用**对照词**证明索引非空（§3、§4），再判定真零。
3. 领域站必须带 `Referer` / `X-Requested-With` 的，见 §2。

---

## 2. A 级主力：cninfo 全文检索（照抄级）

覆盖沪深两市全部公告，返回 JSON，支持关键词 + 日期区间。**采购需求、投产/复产/扩产最可靠的来源。**

```
http://www.cninfo.com.cn/new/fulltextSearch/full?searchkey=<URL编码关键词>&sdate=<YYYY-MM-DD>&edate=<YYYY-MM-DD>&isfulltext=true&sortName=nothing&sortType=desc&pageNum=1&pageSize=30
```

```powershell
# 必需请求头（照抄）：
$H=@{"User-Agent"="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120";
     "Referer"="http://www.cninfo.com.cn/";"X-Requested-With"="XMLHttpRequest"}
```

参数含义：

| 参数 | 含义 |
|---|---|
| `searchkey` | 关键词，必须 `[uri]::EscapeDataString($kw)` 编码。**多词以空格分隔 = AND 分词**，不是短语匹配 |
| `sdate` / `edate` | 检索窗口起止（服务端生效）。用 `config.task.window_start/window_end` |
| `isfulltext` | `false`＝**标题检索**；`true`＝**全文检索**（返回体多出 `announcements[].announcementContent`） |
| `pageNum` | 页码，从 1 起；`pageSize` 建议 30 |
| `sortName` / `sortType` | 排序，照抄 `nothing` / `desc` 即可 |

返回字段（本轮实测）：`totalAnnouncement`、`totalRecordNum`、`totalpages`、`hasMore`、`announcements[]`、`categoryList`、`classifiedAnnouncements`、`totalSecurities`。

解析片段：

```powershell
$j=$r.Content|ConvertFrom-Json; "total=$($j.totalAnnouncement) pages=$($j.totalpages)"
$j.announcements | ForEach-Object {
  $pub = if($_.adjunctUrl -match '/finalpage/(\d{4}-\d{2}-\d{2})/'){$Matches[1]}else{''}
  "$pub | $($_.secCode) $($_.secName) | $($_.announcementTitle)" }
```

### 实测坑（全部踩过，逐条遵守）

1. **两轮都跑，绝不用标题检索的 0 条下结论。** `isfulltext=false` 只值皮毛（关键词很少出现在标题里），`true` 才有正文命中。
   **实测对照**：同一窗口 `碳酸钠` → 标题 `total=0` / 全文 `total=41`；另一产品 `纯碱` → 标题 0 / 全文 164。→ 固定流程：先跑 `true`（主力），再跑 `false`（补「标题即事件」类）。
2. **必须带 `Referer` + `X-Requested-With`，否则会静默返回 `total=0`（假 0）。** 这是最坑的一个。
   → **任何意外的 0 条都视为「未验证」**：补头 + 间隔 15~20 秒后重试一次，再用对照词确认索引非空，才能写「真零」。
3. **`announcementTime` 是 UTC，比公告日期早一天**（实测：`announcementTime`→2026-08-17，而 PDF 在 `finalpage/2026-08-18/`）。
   → **`发布日` 一律取 `adjunctUrl` 里 `/finalpage/YYYY-MM-DD/` 的日期**，不要用转换出来的日期。
4. **并发即 403。** 请求之间留 **15~20 秒**；遇 403/5xx **退避重试**，不要连续猛打同一 URL。
5. **多词是 AND 分词**：`searchkey=碳酸钠 纯碱` 只返回同时含两词的公告，窄词组合命中率极低 → **宽词 + 人工筛**更划算。
6. **`announcementContent` 只有约 55 字的命中窗口**，够判断「是不是这件事」，但**吨数 / 金额 / 合同期这类硬数字必须下 PDF 抽正文**（§7）。
7. **主体改名要跟进**：改名后按旧名检索为 0（纯碱例：远兴能源已更名 **博源化工**，按旧名 total=0）。
   → 每个主体在 `config.company_aliases` 里维护「旧名 → 规范名」。

### 证据链接的两种形态

- **PDF 直链（已确认可用）**：`http://static.cninfo.com.cn/<adjunctUrl>`，例 `http://static.cninfo.com.cn/finalpage/2026-02-26/1224984220.PDF`。
- **披露详情页**：形态随站点改版而变，**不要凭记忆拼**。要用就先真实打开一次，把验证过的 URL 原样写进 `证据来源`；不确定时**只写 PDF 直链**。

### 补充用法：服务端严格日期过滤的另一个 cninfo 接口

`http://www.cninfo.com.cn/new/hisAnnouncement/query`（POST，同样要上面的头）。字段：`pageNum` / `pageSize` / `column`（如 `szse`）/ `tabName=fulltext` / `searchkey` / `seDate`（`YYYY-MM-DD~YYYY-MM-DD`）/ `isHLtitle=true` / `category` / `plate` / `stock` / `sortName` / `sortType`。它的 `seDate` 是**服务端真实日期过滤**，返回体同样带 `announcements[].adjunctUrl`。

---

## 3. A 级：公共资源交易 / 政采平台的 epoint 全文检索（照抄级）

各省市公共资源交易平台的**列表页是 JS 壳**（9~10KB、不返回条目），但背后有一个可直接调的 **epoint 全文检索 REST 接口**——**这是能查到真实招标的唯一通道**。

### 3.1 怎么找到它（不要猜域名/路径）

1. 抓平台首页，正则抽 `href="…search…"` → 找到全文检索页，形如 `http://ggzy.xzsp.changzhou.gov.cn/search/fullsearch.html?cnum=001&wd=<词>`（本轮实测存在）。
2. 抓该检索页 HTML（约 11KB、无数据），正则抽 `rest` 相关字符串 → 得到接口 URL。实测命中 `/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew`（同页还有 `getHotWords` 热搜词接口）。
3. 抓该页引用的 `fullsearch.js`，读出**请求体字段语义**（该 JS 逐字段写了注释）。**先读 JS 再用**，不要猜参数。

已知接口形态（来自实测记录，仍须按 3.1 复核）：

| 平台 | 接口形态 |
|---|---|
| 常州 `ggzy.xzsp.changzhou.gov.cn` | `http://<域名>/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew`（**本轮实测可用**） |
| 江苏 `jsggzy.jszwfw.gov.cn` | `http://<域名>/inteligentsearch/rest/...` |
| 江西 `jxsggzy.cn` | `http://<域名>/XZinterface/rest/esinteligentsearch/getFullTextDataNew` |

### 3.2 请求体（POST JSON，字段语义抄自站点自身 JS）

```
{
 "token":"", "pn":0, "rn":30,              // pn=起始行(=页码×rn)，rn=记录数
 "sdt":"", "edt":"",                       // 起止时间 YYYY-MM-DD HH:mm:ss
 "wd":"<encodeURIComponent(关键词)>",       // 关键词；空格分隔＝全包含(AND)
 "inc_wd":"", "exc_wd":"",                 // 包含任意 / 不包含
 "fields":"title;content",                 // ⭐ 检索范围，必须带
 "cnum":"",                                // 分类号，";"分隔，不传=全部类别
 "sort":"", "ssort":"title",               // ssort=匹配度置顶字段
 "cl":500,                                 // 返回正文长度
 "terminal":"", "condition":null, "time":null,
 "highlights":"title;content", "statistics":null, "unionCondition":null,
 "accuracy":"",                            // 空＝and 匹配；1~100＝or 匹配
 "noParticiple":"1",                       // 1＝关键词不分词
 "searchRange":null
}
```

- 请求头：`Content-Type: application/json;charset=UTF-8`、`Referer: <检索页 URL>`（照 §2 的习惯带上）。
- `time` 参数可用日期区间：`[{"fieldName":"infodate","startTime":"YYYY-MM-DD 00:00:00","endTime":"YYYY-MM-DD 00:00:00"}]`（字段名按站点实际返回确认）。
- 返回：`result.totalcount`（总数）+ `result.records[]`（`title`/`content`/`infodate`/`linkurl`/`categorynum`）。**`linkurl` 是相对路径，必须拼回平台域名。**

### 3.3 三个必须遵守的实测结论

1. ⭐ **必须带 `fields=title;content`，否则关键词被忽略、返回全量数据**（看着像「命中很多」，其实全是噪声）。
   **本轮实测**：`碳酸钠` 带 fields → `total=8`；**同一请求不带 fields → `total=57619`**（全库）。站点自身 JS 注释也写明不传则搜索无效。
2. ⭐ **必须同时用学名和俗名检索**。**本轮实测**：`碳酸钠 → total=8`，而 `纯碱 → total=0`。同义词覆盖是产品画像的产物（→ `config.product.aliases`）。
3. ⭐ **「0 条」要用对照词验证是不是真零**。用必然高频的词（如 `投标人`）确认索引非空：**本轮实测 `投标人 → total=17312`**（历史运行中曾为 998/752/603）→ 故上面的 `纯碱=0` 是**真零**，不是抓取失败。
   另外：**省级索引可能不含市级公告**（同一项目在市级平台查得到、省级索引 0 条）→ 省、市两级都要跑。

### 3.4 其它注意点

- 请求间隔 ≥ 5 秒，出现 403/连接重置就退避；不同平台限流强度不同。
- 分类号（`cnum`）不传＝返回后台配置的全部类别；想只看某类公告时才传，且**类别号必须从页面里读出来**，不要编。
- 放弃判据：**三次内拿不到「服务端返回的、含 records 的 JSON」，就放弃该平台并写进 `channels_used.md`**。

---

## 4. A 级：政府环评 / 行政审批公示

### 4.1 两种已验证的技术栈

1. **静态 TRS 列表（推荐，可逐页翻）** —— 生态环境局「受理公示 / 拟审批公示 / 审批决定公示」三栏。入口用**目录 URL（带尾斜杠）或 `index.htm`**；**本轮实测 `index.html` 会 404**，探测入口时两种后缀都试。分页 `index_1.html`、`index_2.html`…；条目链接形如 `tYYYYMMDD_<数字>.htm`。→ 列表页只给标题，**正文/附件才有产能与原辅材料表**。
2. **ASP 动态列表页** —— 列表由 ASP 页面直接返回（不是 JSON）。已记载可用的城市之一：安徽铜陵市生态环境局。→ 当作一类技术栈，换城市时用同样方法重新探测；**入口域名必须当次确认，不要凭记忆拼**。

### 4.2 列表页是 JS 壳时怎么办（别在同一页面耗超过 3 次）

判别：HTTP 200 但**正文长度恒定、无任何条目**（某省厅列表页正文恒 33 字符）。
处理顺序：① 找该站的检索/JSON 接口（4.3）→ ② 换栏目（受理 / 拟审批 / 审批决定 / 竣工验收）→ ③ 换同级**区县**站点 → ④ 换上级省厅**转发页**或「行政审批局」（而非「生态环境局」）→ ⑤ 换市。

### 4.3 地方政府部门接口的通用发现法

政务站的列表数据常由 JSON 接口驱动（XHR），**发现方法固定为**：

1. 抓栏目列表页 HTML → 若无条目，正则抽 `src="*.js"`。
2. 逐个抓这些 JS，`IndexOf` 搜 `ajax` / `rest` / `api` / `url:` → 定位接口 URL。
3. 在同一段代码里读**请求体对象**（参数名与注释通常都在），照抄字段，不要自己命名。
4. 先请求**第 1 页、rn=1**（`Content-Type: application/json` + `Referer`），确认 `total/count` 与 `records/list` 形状。
5. 用**对照词**证明索引非空（§3.3 第 3 条），再翻页；把实测成功的 URL、方法、请求体样例、返回字段写进 `channels_used.md`。

**政务站 JSON 接口的常见参数模式**（名字因站而异，**必须确认后再用**）：

| 作用 | 常见参数名 |
|---|---|
| 栏目/分类 | `categorynum` / `colId` / `type` / `cnum` |
| 分页 | `pageNo` / `pageIndex` / `pageNum` / `pn`（起始行）+ `pageSize` / `rn` |
| 关键词 | `wd` / `keyword` / `searchkey`（常需 URL 编码；空格＝AND） |
| 必带字段范围 | `fields=title;content`（同 epoint，**不带就噪声或空**） |
| 日期区间 | `sdt`/`edt`，或 `time`/`dateRange` 数组（`fieldName`+`startTime`+`endTime`，`YYYY-MM-DD HH:mm:ss`） |
| 匹配方式 | `accuracy`（空=and，1~100=or）；`noParticiple=1` 不分词 |
| 返回长度 | `cl` / `contentLength` |

**政务站通用坑**：① 普遍限流（首次 200、随后 403）→ 留间隔；② 多数提供**附件 PDF 直链**，**产能与原辅材料表在附件里，不在正文**；③ 分页常是表单提交（`pageModel.numberNo`、`pageNo` 之类隐藏字段）而不是 `?page=2`，找不到就翻归档目录（`/202609/`、`/art/2026/...`）。

### 4.4 编码与读取（政务站专用写法）

政务站常不声明 charset，`Invoke-WebRequest` 会按 Latin-1 解出乱码。固定用：

```powershell
$wc=New-Object System.Net.WebClient
$wc.Headers.Add('User-Agent','Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120')
[System.Text.Encoding]::UTF8.GetString($wc.DownloadData($url))
```

---

## 5. 死通道清单与放弃理由（如实记录，避免重复踩）

| 通道 | 现象 | 放弃理由 |
|---|---|---|
| `search.ccgp.gov.cn`（中国政府采购网） | 持续「频繁访问」拦截 | 反爬不可绕，且无对照口径可验证 |
| 江苏政采检索接口 `ccgp-jiangsu.gov.cn` | **强制图形验证码** | **本机模型无图像输入能力，无法识别**（首页可开，检索接口不可用） |
| `zcygov.cn` / `zfcg.sh.gov.cn` / `ccgp-shandong.gov.cn` | 前端 SPA，无服务端数据 | 无接口可调，抓到的永远是空壳 |
| `ccgp-jiangxi.gov.cn` | 强制跳 https | 本环境无 TLS 凭据 |
| `tender.com.cn` | 106 字节空壳 | 无内容 |
| 行情/资讯站 `100ppi.com`、`oilchem.net`、`chem99.com`、`sci99.com`、`glass.com.cn`、`cnbm.com.cn`、`zj.gov.cn`、`tianyancha.com`、`qcc.com` | **301 跳 https**（本轮实测 `100ppi.com` 与 `ggzy.gov.cn` 均 301） | **301→https 一律放弃，不要试图绕过** |
| 国家公共资源交易平台 `ggzy.gov.cn` | 301 / 连接被关闭 | 无 http 明文入口 |
| 浙江/福建/安徽/上海政采、山东 `ggzyjy`、无锡/徐州/苏州/南京/盐城/扬州/温州/芜湖/潍坊等市级平台、泉州某路径 | SPA / 强制 https / 502 / 超时 / 404 | 逐个记入 `channels_used.md`；**同一站点只试一次** |
| `chinaiol.com` | 制冷空调行业站 | 与化工品无关（**行业错配也是死通道的一种**） |

**判定原则**：一个通道若 **3 次请求内**拿不到「服务端返回的、含条目正文或 JSON 的响应」，即判死，写清现象后换通道。

---

## 6. HTTPS / HTTP 自适应写法

```python
# scripts/radarlib.py 已实现：http_get(url, headers=None, retries=3, backoff=6)
#   ① 按原协议请求；② 失败换另一种协议重试（https 用不校验的 context）
#   ③ 连续 3 次 SSL 失败 → 判定「本环境无 TLS 能力」，之后只走 http，不再空耗
```

手写 pwsh 版（无公共库时照抄）：

```powershell
function Get-Any([string]$u){
  foreach($cand in @($u, ($u -replace '^http://','https://'), ($u -replace '^https://','http://'))){
    try { return Invoke-WebRequest -Uri $cand -UseBasicParsing -TimeoutSec 25 -Headers $H } catch {} }
  return $null }
```

- 优先级：**先试 https，失败回退 http**；反之亦然（站点可能只支持一种）。
- 某些环境**完全没有 TLS 能力**：此时只能覆盖 http 明文可抓的站点 →**必须在交付报告的「覆盖缺口」一节如实写明**（例：「浙江/上海/安徽省级政务网与多家行情站因强制 https 不可达，本表对这些省份的覆盖被系统性低估」）。不要使用任何绕过 TLS 的手段。

---

## 7. PDF 取硬数字（正文检索给不了的吨数/金额/合同期）

- **何时下 PDF**：需要**吨数、金额、合同期、原辅材料表**时（`announcementContent` 的 55 字窗口不够）。抽取工具：纯 stdlib 的 `zlib` + `ToUnicode` CMap，或 `pdfminer.six`。
- **容错正则**（PDF 表格会逐字排版成 `1 0 7 5 t / a`、`S BS`）：`年\s*用\s*量`、`t\s*/\s*a`、`采\s*购\s*量`（按产品词改）。
- **无文本层**（扫描件 / 某些港股年报 PDF）→ 抽不出正文，**放弃并在 `channels_used.md` 标注**，不要猜内容。
- **一律先落 UTF-8 文件再用 read 读**（§0 中文乱码）。

---

## 8. 「本次可用通道清单」制度：`channels_used.md`

**每跑一次任务**，在**该任务的产出目录**（`config.task.outdir`）落一份 `channels_used.md`。这是复现、交接与写「覆盖缺口」的依据。

```markdown
# 本次可用通道清单 · <产品> · <区域> · 任务日 <baseline_date>

| 通道 | 级别 | 实测入口 URL | 本次状态 | 命中条数 | 不可用原因 | 备注 |
|---|---|---|---|---|---|---|
| cninfo 全文检索 | A | http://www.cninfo.com.cn/new/fulltextSearch/full | 可用 | 41 | — | 标题检索 0，全文 41 |
| 常州公共资源交易 epoint | A | http://ggzy.xzsp.changzhou.gov.cn/inteligentsearch/rest/... | 可用 | 8 | — | 关键词用学名；不带 fields 时 total=57619（噪声） |
| 某市生态环境局 | A | http://.../hjgl/hbsp/<col>/ | 可用 | 6 | — | index.html 404，用目录 URL |
| 某省级政采平台 / 某行情站 | A / D | http://... | 不可用 | 0 | 前端 SPA / 301 跳 https | 环境无 TLS |

## 真零 vs 假零（对照词验证）
- 对照词 `<必命中词>` → total=<N>，证明索引非空；故 `<目标词>` 的 0 条为**真零**。

## 覆盖缺口
- <哪些省份/通道因强制 https、SPA、图形验证码而不可达，导致哪部分被系统性低估>
```

---

## 9. 链接抽检（link gate）

**每个任务收尾必须做**：随机抽 ≥40 条**唯一链接**逐条探测（不足 40 时全量）。

- 探测方式：`GET`（PDF 用 `HEAD`，避免拉几十 MB），带 UA + `Referer`，`-MaximumRedirection 0`，超时 25s。
- **失败必须退避后重试一次**——限流会造成**假失败**。
- 抽检前把 `证据来源` 里 **URL 与中文说明之间补一个空格**（全角括号紧跟 URL 会被解析成「URL+中文」而误判）。
- 判定**必须区分两类失败**：

| 判定 | 触发 | 处置 |
|---|---|---|
| 可达 | 2xx/3xx 且正文含主体名 | 通过 |
| **反爬拦截** | 403 / 401 / 人机验证页 | ⚠️ **浏览器里其实能打开** → 标「**需人工复核**」，**不算坏链** |
| **真空页 / 故障站** | 200 但正文空、无主体名；404 / 410；连接失败 | ❌ **真坏链**，必须修复或删除该条证据 |
| 仅 HTTPS | 301/302 且 Location 是 https 而本环境无 TLS | ❌ 本环境不可达 → 记入覆盖缺口 |

- 输出 `leads_raw/_qa_report.json`：`抽样数 / 可达数 / 可达率 / 明细[]（url, status, bytes, 结论）`，并把「反爬拦截」单列计数。
- 抽检结论只能按 URL 匹配；同一主体在多个原始文件里链接不同，**要支持按公司名回退匹配**，否则会漏标。