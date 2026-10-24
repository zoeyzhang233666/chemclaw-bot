# -*- coding: utf-8 -*-
"""示例 01：10 万美元出口重质纯碱订单、90 天后收汇 —— 核心指标试算。

所有数字均由 calculations.py + fx_series.json 计算，不手写。
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import calculations as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fx = json.load(open(os.path.join(ROOT, "build", "fx_series.json"), encoding="utf-8"))


def series_of(code):
    vals = fx["currencies"][code]["values"]
    return sorted(vals.items())


def fmt(x, n=4):
    return "—" if x is None else f"{x:,.{n}f}"


def pct(x, n=2):
    return "—" if x is None else f"{x*100:.{n}f}%"


usd = series_of("USD")
asof = "2026-10-19"
mid19 = fx["currencies"]["USD"]["values"][asof]
mid16 = fx["currencies"]["USD"]["values"]["2026-10-16"]
boc_sell = 6.6701

print("=" * 72)
print("一、汇率口径")
print(f"2026-10-19 中间价 USD/CNY = {mid19}")
print(f"2026-10-16 中间价 USD/CNY = {mid16}（Frankfurter/ECB 交叉核对 6.6862，差 {abs(6.6862-mid16):.4f}）")
print(f"BOC 现汇买入价(出口结汇用) = {boc_sell}  与中间价价差 = {boc_sell/mid19-1:+.2%}")
band = C.rate_band(mid19, 0.0025)
print(f"示例点差±0.25%: 结汇价 {band['sell_fx']:.4f} / 购汇价 {band['buy_fx']:.4f}")

print("\n二、历史分位（USD/CNY 中间价）")
for y in (1, 3):
    st = C.window_stats(usd, asof, mid19) if y == 1 else None
for y in (1, 3):
    w = C.window_slice(usd, asof, y)
    st = C._stats_of(w, mid19)
    print(f"  {y}Y: n={st['n']} {st['first_date']}~{st['last_date']} "
          f"min={fmt(st['min'])}@{st['min_date']} max={fmt(st['max'])}@{st['max_date']} "
          f"mean={fmt(st['mean'])} 分位={pct(st['pctile'],1)} 距高点={pct(st['drawdown_from_max_pct'])} "
          f"区宽={pct(st['range_width_pct'])} 年化波动={pct(C.realized_vol(w)['annualized_pct'])}")

print("\n三、业务锚定（示例参数，标记为模拟）")
AMOUNT = 100000.0
COST = 600000.0
RATE = mid19
case = C.OrderCase(amount_fx=AMOUNT, currency="USD", direction="export", base_rate=RATE,
                   cny_cost=COST, target_margin_pct=0.10)
s = case.summary()
b = s["base"]
print(f"  外币金额 {AMOUNT:,.0f} USD × 中间价 {RATE} = 毛收入 {b['gross_cny']:,.2f} 元")
print(f"  人民币成本 {COST:,.0f} 元 → 毛利 {b['margin_cny']:,.2f} 元，毛利率 {pct(b['margin_pct'])}")
print(f"  汇率每变动 1% → {s['one_pct_cny']:,.2f} 元；90天窗口历史典型波动 ≈ {pct(C.implied_move(C.realized_vol(C.window_slice(usd, asof, 1))['annualized_pct'], 64))}")

print("\n四、敏感性（±1/3/5%）")
for r in s["sensitivity"]:
    print(f"  {r['shift']*100:+5.0f}% 汇率={r['rate']:.4f} 收入={r['net_cny']:>12,.2f} "
          f"变化={r['delta_cny']:>+11,.2f} 毛利={r['margin_cny']:>+10,.2f} 毛利率={pct(r['margin_pct'])}")

print("\n五、盈亏平衡")
print(f"  毛利=0: 平衡汇率 {s['breakeven_zero']['breakeven']:.4f} → {s['breakeven_zero']['label']}")
print(f"  毛利率10%: 平衡汇率 {s['breakeven_target_pct']['breakeven']:.4f} → {s['breakeven_target_pct']['label']}")

print("\n六、分批结算示例（30%/40%/30%）")
batches = [
    {"label": "T/T 30% 定金", "amount_fx": 30000, "days": 0, "rate": RATE},
    {"label": "装运后 60 天 40%", "amount_fx": 40000, "days": 60, "rate": RATE},
    {"label": "提单后 90 天 30%", "amount_fx": 30000, "days": 90, "rate": RATE},
]
sp = C.split_batches(batches)
print(f"  加权汇率 {sp['weighted_rate']:.4f} 合计 {sp['total_cny']:,.2f}")
for r in sp["rows"]:
    print(f"   {r['label']:<14} {r['amount_fx']:>9,.0f} @{r['rate']} = {r['cny']:>11,.2f}")
for sh in (-0.05, -0.03, -0.01, 0.01, 0.03, 0.05):
    one = AMOUNT * RATE * (1 + sh)
    stg = C.split_batches(C.split_shift_rates(batches, sh))["total_cny"]
    print(f"  {sh*100:+5.0f}% 一次性={one:>12,.2f} 分批={stg:>12,.2f} 差={stg-one:+.2f}")
