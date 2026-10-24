# 案例

| 编号 | 品种 / 市场 | 区间 | 用途 |
|---|---|---|---|
| 01 | 华东甲醇 | 2026-06-30 → 2026-10-19 | 完整真实案例，含换月陷阱与反向假设 |

## 怎么用这些案例

**学方法**：先读 `01/narrative.json` 的 `hypotheses`，看一正一反两条假设是怎么写的；
再读 `01/README.md` 的"演示的三条方法论要点"。

**做新案例**：

```bash
cp -r examples/01-methanol-huadong-2026Q3 examples/02-你的品种
# 清空 build/ 与 out/，保留 raw/ 作参照
# 改 case.json（窗口、三个数据文件、十个因子、口径合约）
python scripts/build_all.py --case examples/02-你的品种/case.json
```

**验证脚本没改坏**：重跑案例 01，对比 `01/README.md` 里的数字
（现货 +41.00%、MA2611 +39.31%、基差峰值 1264、开工率 83.8%）。

## 每个案例的目录约定

```
case.json        唯一手工输入
narrative.json   人工叙事
raw/             原始数据 + _src/ 原始响应
build/           中间产物（可删，重跑即生成）
out/             最终 HTML + Excel
README.md        本案例的结论速览
```
