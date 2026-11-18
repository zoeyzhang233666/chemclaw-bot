# references/demo-methanol-data.json 使用说明

本文件是 `scripts/check_formulas.js` 的**最小可用示例数据集**（甲醇 2026-10 示范案例），
与正式 `data.json` 结构一致，只是精简掉了图表、术语等展示用字段。

## 用途

```bash
# 1) 直接跑内置示范数据
node scripts/check_formulas.js

# 2) 跑自己的数据
node scripts/check_formulas.js path/to/your-data.json
```

内置示范数据的存放位置：`assets/example-data.json`。

## 字段对照

| 字段 | 必填 | 说明 |
|---|---|---|
| `meta.product` / `meta.futures_contract` / `meta.question` / `meta.data_cutoff` | ✔ | 缺任何一个 H1 判 FAIL |
| `sources{ID: {title,url,date}}` | ✔ | 每条必须有 url（H2） |
| `inventory.series[{date,value,change}]` | ✔ | 周度库存，单位万吨 |
| `basis.rows[{date,spot,fut_close,fut_settle,basis_close,basis_settle,basis_pct}]` | ✔ | 没有单一现货订价的日期把 spot 置 null，不要用区间中值 |
| `month_spread.points[{date,near_close,far_close,mc}]` | ✔ | mc = far − near |
| `longshort{start_close,start_close_other,end_close,change_pct}` | 建议 | 用于验证“跨换月假跌幅” |
| `import_parity{cfr,fx,freight,port,duty,vat,...}` | 建议 | 缺运保费会 SKIP |
| `flow{arrivals,d_inv,implied_withdrawal}` | 建议 | 表观提货恒等式 |
| `checks[{id,got,expect,tol,status}]` | 建议 | 页面内嵌校验项，与页面第 11 节同源 |
| `verdict.coexistence_found{status}` | 建议 | 并存核对结论必须显式给出 |

## 判定语义

- `PASS`：公式与符号一致性成立
- `FAIL`：数值不符或符号方向错误 → **不得交付**
- `SKIP`：数据未提供（不算失败，但交付说明里要写明“该项未验证”）
- `INFO`：仅供参考的派生值（例如两种基差口径的差）
