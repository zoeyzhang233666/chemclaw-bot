# 取证实操：哪些接口能拿到数据，哪些会失败

这份文件是"下次换个人/换个 agent 来做，能直接跑通"的备忘录。踩过的坑都记下来，省得重复试。

## 一、能稳定拿到数据的渠道（2026-10 验证）

### 1. 期货日线（大宗品种首选）

```
https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20d=/InnerFuturesNewService.getDailyKLine?symbol=EG0
```

- `symbol`：`EG0`（乙二醇连续）、`MA0`（甲醇）、`TA0`（PTA）、`SA0`（纯碱）、`FG0`（玻璃）、`UR0`（尿素）、`V0`（PVC）…
- 返回 `var d=([...])`，每项 `{d,o,h,l,c,v,p}`，**2018-12 起全量**，一次返回 1900+ 条。
- 请求头带 `Referer: https://finance.sina.com.cn/futures/quotes/EG0.shtml`。
- 交叉验证：`https://hq.sinajs.cn/list=nf_EG0`（实时快照，可核对最新收盘）。

### 2. 公开商品指数日频序列（生意社 / 100ppi）

页面：`https://www.100ppi.com/vane/detail-222.html`（222 = 乙二醇；别的品种换 product id）

图表数据接口（**必须先设 Cookie**）：

```
Cookie: HW_CHECK=f9357b080fd1206c7e5af509794a2a55
https://www.100ppi.com/graph/cindex.php?f=graph_ave&ppid=222&type=1&mode=3
```

- `type=1` 直接返回**元/吨**；`type=2` 返回**指数点**（指数 ÷ ≈100.4 得到元/吨，但两者不完全等价，优先用 type=1）。
- 返回 366 天日频数据，节假日沿用前一交易日值。
- 返回体是压缩/混淆过的 JS，里面有个 `permpd` 数组，**解包基数 = 62**（不是 64！）。用 node 执行解包即可。
- 不带 Cookie 会得到 636 字节的机器人页。

### 3. 当日现货快照（报价动态）

`https://www.100ppi.com/news/detail-YYYYMMDD-<id>.html`——生意社「XX商品报价动态」，
一条新闻里有几十家贸易商的分等级报价（含地区、产地）。用来**看当日离散度**，一般不构成有效区间。

企业竞拍/挂牌新闻同样在这个域名下，标题格式：
`2026年10月19日山西潞安化工聚酯级乙二醇起拍价5580元/吨`——这类**含"含税出厂/现汇/承兑"明示口径**，是很好的旁证。

### 4. 产业资讯快讯（可用于核对与事件）

我的钢铁网：`https://nenghua.mysteel.com/a/<yymmddHH>/<16位ID>.html`
文章 ID = 8 位 `yymmddHH` + `/` + 16 位大写字母数字。列表页只能翻到最近约 1 个月。

## 二、试过但失败的渠道（别再浪费时间）

| 渠道 | 现象 | 结论 |
|---|---|---|
| `push2his.eastmoney.com/api/qt/stock/kline/get` | `Remote end closed connection without response` 持续 | 该接口对本环境封锁，改用新浪 |
| `push2his.eastmoney.com/.../trends2/get` | 偶发成功 | 不稳定，不作主源 |
| `d.10jqka.com.cn/v6/line/...` | 404 / 502 | 需签名 |
| `service.99qh.com/Storage/PmPrice.ashx` | SSL 证书校验失败 | 放弃 |
| `www.oilchem.net`（隆众官网）正文 | 页面 144KB 但**正文需登录**，只有导航与标题 | 只能拿到标题与时间 |
| `nenghua.mysteel.com` 列表翻页 `-2.html` 等 | 404 | 列表只覆盖最近 1 个月 |
| 生意社新闻列表页 | 反爬，返回机器人页 | 用 `web_fetch` 抓单篇新闻即可 |

## 三、URL 的"日期规律"很有用

多数产业资讯的正文 URL 里带日期，改日期往往能直接拿到历史某天：

- 生意社：`news/detail-20261019-6362576.html`（日期 + 序号，序号无规律）
- 隆众：`oilchem.net/26-0915-13-440187a30996e466.html`（yymmdd + 时段 + hash）
- 我的钢铁网：`nenghua.mysteel.com/a/26101909/5ED38A25A88EBF5D.html`

但**只有生意社的单篇新闻可匿名抓正文**；隆众与我的钢铁网正文需要登录/授权。

## 四、取证的三个纪律

1. **先存原文再解析**。把 HTML/JSON 落到 `work/` 下，解析脚本只读本地文件——否则重跑一次又是一个版本。
2. **每个数字记 URL + 抓取时间**。报告里能点开原文，审计才过得去。
3. **交叉验证至少一次**。比如：当日新闻的点位 vs 图表序列的点位、期货收盘 vs 行情快照。
   本示例就靠这个发现了"生意社基准价 08:30 发布值 5,966.67 vs 图表当日更新值 5,808.33"的时点差异。

## 五、拿不到时的正确姿势

不要编，也不要"用行业均值推算"。按这个顺序降级：

1. 换渠道（资讯 → 协会 → 期货公司日报 → 行业媒体）；
2. 换频率（日频 → 周频 → 逐日快照）；
3. 换口径（现货价 → 指数，但**标注为代理口径**）；
4. 换窗口（3 年 → 1 年，但**写明 3 年是缺口**）；
5. 全都不行 → **就在报告里写缺口**，把 `gaps` 填满"试过哪些渠道、为什么补不上"。

一份明确写了缺口的报告，比一份看起来完整但数字站不住的报告有用得多。
