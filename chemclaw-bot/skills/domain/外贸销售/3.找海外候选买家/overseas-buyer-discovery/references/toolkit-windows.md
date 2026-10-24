# 通道工具链（Windows / 无 API Key 场景）

本文件记录在本机实测可用的抓取与核验手段，以及失效时的替代方案。**先小样实测，再大规模调用**——搜索引擎的反爬是按请求量触发的。

---

## 1. 搜索

| 引擎 | 实测状态（2026-10） | 用法 |
|---|---|---|
| Brave HTML (`https://search.brave.com/search?q=`) | 结果质量最好；**高频后会转验证码**（返回 "captcha" 关键字） | 首选，控制频率；看到 captcha 立即停用 10–20 分钟 |
| Bing (`https://www.bing.com/search?q=`) | 结构可解析，但**未登录时结果相关性差**（会对语序做奇怪切分），且真实链接被包在 `bing.com/ck/a?…u=a1<base64>` 中 | 只作兜底；解析方式见下 |
| DuckDuckGo HTML / Lite | 返回 202（无结果页） | 不可用 |
| Mojeek / Yandex / Ecosia / Qwant | 返回验证码或纯 JS 壳 | 不可用 |
| 平台型检索（GitHub/Wikipedia 类 API） | 可用 | 适合查企业与标准事实 |
| 付费/平台检索工具 | 视环境而定 | 有则用，无则不依赖 |

**Bing 链接解码**：取 `u=a1XXXX`，去掉前两个字符，base64url 解码即得真实 URL（PowerShell 里 `a1aHR0…` → 去 `a1` → 补 `=` → `FromBase64String`）。

**搜索词策略**（印尼为例）：
- `"<英文本品>" <国家> importer distributor PT`
- `distributor <本品种>dense <本地城市>`（本地语言）
- `<行业本地词> bahan baku <本品种>`（本地语言“原料”）
- `site:<企业域名> <本品种>`
- `"<HS 编码>" <国家> imports 2024`

## 2. 页面抓取

```powershell
# 单页（返回清洗后的正文）
cmd /c "web_cmd.cmd -Mode fetch -Url https://example.co.id -Max 4000"
# 关键词上下文（精确定位“soda ash”出现在哪里）
cmd /c "web_cmd.cmd -Mode grep -Url https://example.co.id -Q soda -N 5"
# 批量并行（每行一个 URL；结果按 URL 命名写入 OutDir）
powershell -NoProfile -ExecutionPolicy Bypass -File fetch_many.ps1 -InFile urls.txt -Max 3000 -OutDir fetchout
```

要点：
- PowerShell 5.1 **没有** `ForEach-Object -Parallel`（参数集解析会报错），批量抓取用 `Start-Job`（`fetch_many.ps1` 已封装）。
- `Invoke-WebRequest -UseBasicParsing` 的 `RawContent` 会带 HTTP 头；清洗正文用 `[string]$r.Content`。
- 很多企业站（尤其印尼）对境外 IP 直连超时或 403：记录为“需人工复核”，不要当坏链。
- 带 `-MaximumRedirection 6` 跟随跳转；记录最终 URL 用于主体核验。

## 3. PDF（年报金矿）

```powershell
# 下载
Invoke-WebRequest <pdf-url> -OutFile raw\ar.pdf -UserAgent "Mozilla/5.0 …"
# 提取文本（bundled python + pypdf）
& "C:\Users\<user>\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" extract.py
```

`extract.py` 写法：

```python
import re
from pypdf import PdfReader
r = PdfReader("raw/ar.pdf")
pages = [(i+1, p.extract_text() or "") for i, p in enumerate(r.pages)]
full = "\n".join(t for _, t in pages)
open("raw/ar.txt", "w", encoding="utf-8").write(full)
for kw in ["soda ash", "raw material", "bahan baku", "Penggunaan Material"]:
    print(kw, [i for i, t in pages if kw.lower() in t.lower()][:20])
```

要点：
- 印尼上市公司年报（Laporan Tahunan & Keberlanjutan）的 **“Penggunaan Material / Use of Materials”** 表是纯碱等原料吨数的最佳来源，英文版与印尼语版常在同一 PDF。
- 下载大 PDF（>10MB）需 2–3 分钟，用后台任务，不要串行阻塞。
- Windows 控制台是 GBK 编码：`python` 输出前设置 `$env:PYTHONIOENCODING="utf-8"`，否则遇到特殊字符会抛 `UnicodeEncodeError`。

## 4. 官方数据

| 数据 | 入口 | 能回答什么 |
|---|---|---|
| UN Comtrade 公开 API | `https://comtradeapi.un.org/public/v1/preview/C/A/HS?reporterCode=<m49>&period=<y>&cmdCode=<hs>&flowCode=M` | 各国进口额/量/来源国结构（企业级没有） |
| WITS | `https://wits.worldbank.org/trade/comtrade/en/country/<CTY>/year/<Y>/tradeflow/imports/partner/wld/summary` | 同上，页面可直接读 |
| USGS Mineral Commodity Summaries | `https://pubs.usgs.gov/periodicals/mcs<Y>/mcs<Y>-<commodity>.pdf` | 全球供需、主要生产国、价格区间 |
| 中国 cninfo | `http://www.cninfo.com.cn/` | 中国上市公司公告（出口/供应关系、扩产） |
| 印尼 IDX | `https://www.idx.co.id/` | 年报入口（常有 403，需换镜像或直接抓 S3 链接） |

## 5. 常见故障对照

| 现象 | 原因 | 处理 |
|---|---|---|
| Brave 返回 "captcha" | 频率触发 | 换 Bing/直连，等 15 分钟 |
| Bing 结果与查询无关 | 未登录、语序切分 | 加引号、加 `site:`、改用英文短词 |
| `Invoke-WebRequest` 超时 30s | 目标站挡境外 IP | 记“需人工复核”，不重试 |
| PDF 下载 400 多字节 | 被反爬返回错误页 | 换来源（交易所镜像/S3） |
| python 打印中文报 GBK 错 | 控制台编码 | `$env:PYTHONIOENCODING="utf-8"` |
| 子代理上下文耗尽 | 一次读入整页 | 先落盘，再读摘要 |
