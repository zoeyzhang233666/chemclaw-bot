# 真实汇率数据源与取数方法

> 原则：**宁可标注缺口，也不伪造序列。** 分位数的意义完全依附于数据的真实性。

---

## 1. 数据源清单

### 1.1 ECB 欧元参考汇率（主力源，历史序列）

| 项目 | 说明 |
|---|---|
| 提供方 | European Central Bank |
| 基准货币 | EUR（所有报价为 1 EUR = X 外币） |
| 发布时点 | 每工作日约 16:00 CET |
| 覆盖 | USD、GBP、JPY、AUD、SGD、KRW、INR、HKD、CNY 等 |
| 获取方式 | Frankfurter API `https://api.frankfurter.app/{start}..{end}?from=CNY&to=USD`；或 ER-API |
| 换算 | ECB 不直接给 `USD/CNY`，需经 EUR 交叉：`USD/CNY = (EUR/CNY) / (EUR/USD)` |

**实测可用性**：
- `urllib` 直连需带浏览器 `User-Agent`（否则 403）。
- 需关闭证书校验（`ssl.CERT_NONE`），否则偶发 `SSL: UNEXPECTED_EOF_WHILE_READING`。
- Frankfurter 返回结构为 `{"start_date":..., "end_date":..., "rates": {"YYYY-MM-DD": {"USD": ...}}}`，**没有** `date` 字段，遍历 `rates` 的键。

### 1.2 CFETS / 中国人民银行中间价

| 项目 | 说明 |
|---|---|
| 提供方 | 中国外汇交易中心（受权自中国人民银行） |
| 接口 | `https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json` |
| 结构 | 顶层 `records` 数组，每项含 `vrtEName`、`price` 等 |
| 发布时点 | 每交易日 **9:15** |
| 特点 | 官方权威，海关计征汇率的上游来源 |

**实测**：2026-10-20 09:15 USD/CNY 中间价 **6.7200**；同日 CNY/SAR **0.56010**、EUR/CNY **7.5159**、100JPY/CNY **4.2327**、GBP/CNY **8.9187**、AUD/CNY **4.6780**、SGD/CNY **5.2375**。

### 1.3 银行外汇牌价

| 项目 | 说明 |
|---|---|
| 提供方 | 中国银行、招商银行等 |
| 关注字段 | **现汇卖出价**（`cash_remittance_sell` / 现汇卖出） |
| 获取 | 银行官网牌价页；多数需抓 HTML 或走内部系统 |

> ⚠️ `boc.cn`、`pbc.gov.cn`、`customs.gov.cn`、`gov.cn`、`mofcom.gov.cn`、`safe.gov.cn`、`gss.mof.gov.cn` 在部分网络环境下存在 **TLS 指纹阻断**，`urllib`/`curl` 会报 `SSL: UNEXPECTED_EOF_WHILE_READING` 或 `curl exit 35`。此时改用浏览器取数或公开镜像，并如实标注来源。

### 1.4 不可用源（已验证）

| 源 | 问题 |
|---|---|
| Frankfurter 取 `SAR` | 404 —— ECB 不发布 SAR |
| Frankfurter 取 `CNY` 以外新兴市场币种 | 覆盖不全 |

**SAR 的解决办法**：`SAR/CNY = USD/CNY × (1/3.75)`（沙特里亚尔对美元官方挂钩 **3.75**，SAMA 公布），并与 CFETS 直报 `CNY/SAR` 交叉验证。案例中 `6.7200 ÷ 3.75 = 1.7920`，CFETS 直报 `1/0.56010 = 1.78540`，差 0.37%，取 CFETS 直报值。

---

## 2. 取数实现要点

```python
import ssl, json, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ..."
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(url, headers={
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})
with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
    data = json.loads(r.read().decode("utf-8"))
```

三个必备条件：**浏览器 UA + Accept 头 + 关闭证书校验**。缺任一条都可能 403/握手失败。

---

## 3. 历史序列的构建

案例数据集 `data/fx_real_data.json`：

| 项目 | 值 |
|---|---|
| 区间 | 2019-12-31 → 2026-10-19 |
| 观测数 | **1,743** 个交易日 |
| 覆盖 | USD/EUR/GBP/JPY/SGD/AUD/KRW/INR/HKD → CNY，外加 SARCNY（USD/CNY × 3.75 挂钩折算） |
| 结构 | `{"daily": {"USDCNY": [["2026-10-19", 6.6807], ...]}}` |

**构建规则**：
1. 只保留**同一交易日**在全部所需币种上都有数据的日期（避免插值造点）。
2. 缺失日直接跳过，**不插值、不平滑、不填补**。
3. 每个点都是原始发布值，可回溯到具体日期与来源。

---

## 4. 校验与合理性检查

取到数据后用这五条过一遍：

| # | 检查 | 判据 |
|---|---|---|
| 1 | 观测数是否合理 | 6 年日频应 ≈ 1500–1600；明显偏少说明缺日 |
| 2 | 极值是否落在常识区间 | 案例：最低 6.3104（2022-02-28）、最高 7.3498（2025-04-09） |
| 3 | 均值是否夹在极值之间 | 案例均值 6.9113 ✓ |
| 4 | 与另一源交叉折算是否吻合 | ECB 6.6807 vs ER-API 6.6937，差 −0.19% ✓ |
| 5 | 当日数据与官方口径是否一致 | CFETS 6.7200 vs ECB 6.6807，差 0.59%（时点/基准差异，合理） |

---

## 5. 当前分位数的计算

```
percentile = (区间内 ≤ 当前值的观测数 − 1) / (区间内观测数 − 1)
```

减 1 是为了**排除当前观测本身**，否则当前值会把自己的分位往上抬。

案例实测（当前中间价 6.7200）：

| 区间 | 观测数 | 分位 |
|---|---|---|
| 近 1 年 | — | **13.7%** |
| 近 3 年 | — | **4.6%** |
| 近 5 年 | — | 16.6% |
| 全样本 | 1,743 | 27.0% |

以市场汇率 6.6807 计：近 1 年 0.4%、近 3 年 0.1%、近 5 年 11.9%、全样本 22.9%。

**读法**：近 3 年 4.6% 表示“过去三年里只有 4.6% 的交易日，美元比今天更便宜”，即当前人民币处于近三年**偏强**位置（进口成本相对偏低）。

> 分位 ≠ 预测。它只描述“当前在历史分布中的相对位置”，不暗示未来方向。这一点必须在输出中明确写出。

---

## 6. 数据时效性

每次运行都应在输出中固化：

- 每个汇率值的**数据时点**（日期 + 若是中间价则加 9:15）；
- 历史序列的**末端日期**；
- 生成时间戳。

用户隔天再打开 HTML/Excel，已固化的数是当时的值，**不会**自动更新。需要更新时重新运行脚本或手工替换 `01 参数与汇率` 页签的数值单元格。
