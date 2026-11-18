# 数据源、接口与口径

## 一、期货

| 来源 | 接口 | 说明 |
|---|---|---|
| 新浪财经 | `https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_={code}/InnerFuturesNewService.getDailyKLine?symbol={symbol}` | 日线，含开高低收、成交量、持仓量；主连用 `MA0`，逐合约用 `MA2611` |

- **主连**（`MA0`）：换月即跳接，换月日有名义价 → 只能看趋势，不能算基差。
- **逐合约**：`MA2601…MA2612` 等，需要哪个抓哪个；已到期合约仍有历史，但当日持仓为 0，
  必须按持仓量过滤（本 Skill 用 `min_oi=500`）。

## 二、现货

| 来源 | 用途 | 坑 |
|---|---|---|
| 生意社 100ppi `https://www.100ppi.com/mprice/detail-1-<id>.html` | 基准价（日频） | 分页 `/list---{n}.html`；只覆盖近月，长历史要另想办法 |
| 生意社 快讯 `https://www.100ppi.com/kx/list---{n}.html` | 事件、装置动态、周评 | 页面是重定向链接，抓取时需跟随 |
| 生意社 资讯 `https://www.100ppi.com/news/list---{n}.html` | 深度复盘稿 | 摘要与正文可能不同步 |

**基准价 vs 参考价是同源两条链**，不是两个独立来源。详见 `caveats.md #3`。

## 三、能源

| 品种 | 来源 | 字段 |
|---|---|---|
| 动力煤（秦皇岛 5500 大卡） | CCTD 中国煤炭市场网 ECharts JSON | `name`=日期，`age`=5500 现货，`~` 表示缺失 |
| 原油 | 新浪 SC0 | 主连日线 |
| 天然气 | 公开渠道零散 | 国内甲醇用气量占比小，通常记为缺口 |

**煤价口径**：秦皇岛港 5500 大卡**平仓价含税**。坑口价与到厂价不同，
跨口径相减得到的"成本差"是错的——需要到厂价时必须单独注明口径。

## 四、产业数据（周频）

| 项目 | 通常来源 | 频率 |
|---|---|---|
| 行业开工率、周产量 | 卓创／隆众／生意社周评 | 周 |
| 港口库存 | 卓创周度港口库存 | 周 |
| 到港量 | 船期／海关／资讯机构周报 | 周 |
| 下游开工、利润 | 卓创下游周报 | 周 |

这些数据多数**在付费墙后**。抓不到时：

1. 记进 `data_gaps`，写明"影响哪一条结论"；
2. 若能从公开稿件里取到**具体数值与日期**（如"9/21 周度开工率 83.8%"），
   可以进 `manual`，但必须带 `date` 与 `src`；
3. **绝不**用"约""大概""行业平均"填数。

## 五、抓取实现要点

只用标准库（`urllib.request`），因为运行环境常无 `requests`：

```python
import ssl, urllib.request
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req, context=ctx, timeout=30).read()
```

- 新浪 JSONP 外面包了 `var _=(...)`，正则取出括号内部分再 `json.loads`；
- 文件一律以 `utf-8` 落盘，读取时用 `utf-8-sig`（防止 BOM 导致 `json.loads` 失败）；
- 每个 `raw/` 文件旁边建议留 `_src/` 目录存原始响应，便于复核。

## 六、数据落地约定

```
raw/
  MA0_daily.json          主连日线
  MA_contracts.json       {合约: {日期: {close, open, high, low, volume, oi}}}
  MA2701.json             超出主文件的合约单独存
  ppi_base_price.csv      date(YYYYMMDD),price
  cctd_qinhuangdao.json   [{name, age, ...}]
  events.json             事件清单（含 url）
  _src/                   原始响应快照
```

## 七、抓不到时的处理顺序

1. 换一个公开来源（生意社 → 行业网站 → 交易所公告）；
2. 找可引的**具体数值 + 日期**，进 `manual` 并标 E1/E2 需谨慎；
3. 都没有 → 进 `data_gaps`，写明"缺这项，哪条结论因此无法检验"。

**永远不要**为了填满表格去估一个数。
