# 03 · 因子构造与未来收益对齐

> 目标：构造 6 个「t 时刻一定算得出来」的因子，并把它们与 t 之后的收益严格错开。

## 3.1 六个标准因子

| 代码 | 名称 | 定义 | 最少需要历史 | 捕捉什么 |
|---|---|---|---|---|
| F1 | 时点分位 | 当期值在过去已公布周值中的百分位 | 26 周 | 相对水位（历史视角） |
| F2 | 绝对水平 | 当期库存 | — | 绝对水位 |
| F3 | 周度变化 | 当期 − 上期 | 2 周 | 累库/去库速度 |
| F4 | 周度变化率 | 当期/上期 − 1 | 2 周 | 规模无关的速度 |
| F5 | 同比 | 当期 / 去年同 ISO 周 − 1 | 53 周 | 剔除季节性的水位 |
| F6 | 四周累计变化 | 当期 − 4 周前 | 5 周 | 平滑单周噪声 |
| S | 连续状态 | 同向变化的连续周数（±） | — | 趋势持续性 |

## 3.2 expanding 分位（不可用全样本排名）

```python
def expanding_pct_rank(vals, min_obs=26):
    out = np.full(len(vals), np.nan)
    for i in range(len(vals)):
        hist = vals[:i]                       # 严格只用 t 之前
        hist = hist[~np.isnan(hist)]
        if len(hist) >= min_obs and not np.isnan(vals[i]):
            out[i] = (hist < vals[i]).mean()
    return out
```

同理 `expanding_z`：

```python
out[i] = (vals[i] - hist.mean()) / hist.std(ddof=1)
```

**为什么必须 expanding**：用全样本 p20 分组，等于在 2022 年就已经知道 2026 年才会出现的极值 —— 分类本身携带了未来信息，会让所有分组检验系统性偏强。

## 3.3 同比只能用"去年同 ISO 周"

```python
inv = df.set_index(["iso_year", "iso_week"])["total"]
df["ly"]  = [inv.get((y-1, w), np.nan) for y, w in zip(df.iso_year, df.iso_week)]
df["yoy"] = df["total"] / df["ly"] - 1
```

若用 `shift(52)`，遇到 53 周年份会错位一周。

## 3.4 连续变化状态

```python
run = []
for i in range(len(df)):
    s = np.sign(df.wow_chg.iloc[i])
    k = 1; j = i - 1
    while j >= 0 and np.sign(df.wow_chg.iloc[j]) == s:
        k += 1; j -= 1
    run.append(int(s * k))     # 正=连续累库周数，负=连续去库周数
```

`run ≤ -2` 即"连续 2 周以上去库"。甲醇案例中这是唯一通过安慰剂检验的状态。

## 3.5 未来收益对齐（最容易出错的一步）

### 错误做法

| 错误 | 后果 |
|---|---|
| 用 `asof` 当天收盘作基期 | 同日 16:30 的价格已含消息，未来收益被截断 |
| 用 `asof` 当天收盘、`asof + 7天` 作终点 | 终点是周末，价格取到下一交易日，窗口长度不一致 |
| 用 `pub_ts` 当天收盘 | 若 `pub_ts` 在 16:30 之后，勉强可用；但在 14:00 时不可用 |

### 正确做法

```python
# 交易日数组（升序）
dates = px["date"].to_numpy()
# 公布后第一个交易日
i = int(np.searchsorted(dates, np.datetime64(pub_ts.normalize())))
base = px.iloc[i]                       # 基期收盘

for h in (1, 2, 4):
    end = px.iloc[i + h]                # h 个交易日之后
    fwd_spot  = end.spot / base.spot - 1
    fwd_fut   = end.fut  / base.fut  - 1
    fwd_basis = end.basis - base.basis   # 元/吨
```

三个目标：

| 目标 | 定义 | 单位 |
|---|---|---|
| 现货价格变化 | 现货收益 | % |
| 期货收益率 | 主力期货收益 | % |
| 基差变化 | 差额 | 元/吨 |

> 注：用"交易日间隔"而非"自然日间隔"，保证每个 h 的窗口长度一致；不足 h 个交易日时置 NaN。

## 3.6 价差与基差的两种写法

- **差额（元/吨）**：`fwd_basis = basis_end − basis_base`，直观、可加总
- **变化率**：`basis_rate = basis / fut`，`fwd = rate_end − rate_base`，跨时期可比

研究库存对"基差变化"的影响时，建议同时报告两者；差异大说明期货价格波动主导。

## 3.7 单位与符号约定（写进报告，避免读者误读）

- 库存：万吨
- 价格：元/吨
- 收益：小数，展示时 ×100 加 `%`
- 基差 = 现货 − 期货（正 = 现货升水 / backwardation）
- 相关系数一律 **Spearman ρ**（对异常值稳健）
- p 值一律**双侧**
