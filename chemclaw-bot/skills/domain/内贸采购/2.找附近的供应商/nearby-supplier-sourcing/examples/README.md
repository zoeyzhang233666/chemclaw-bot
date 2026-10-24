# 示例说明（examples）

两个示例都跑完了完整流程，成品在各自的 `output/` 下：

| 目录 | 产品 | 收货地 | 危化 | 亮点 |
|---|---|---|---|---|
| `01-soda-ash-shahe/` | 重质纯碱（GB/T 210-2022 Ⅱ类优等品） | 河北邢台沙河 · 玻璃深加工园（示例） | 否 | 100/300 km 内**一家碱厂都没有**，只有交割库 → 逼出"匹配与距离分开"的方法 |
| `02-caustic-soda-changzhou/` | 离子膜液碱 32%（GB 209-2018） | 江苏常州滨江化工园（示例） | 是（8 类 / UN1824） | 厂家就在园区，300 km 内竞争充分 → 瓶颈变成危货运力而不是距离 |

## 各自看什么

### 01 纯碱（非危化 · 远厂 + 近仓）

1. 打开 HTML，默认「全部」视图：14 家里排第一的是 423 km 外的河南金大地，
   而 **2.6 km 的沙玻物流只排到 B 档第 7**——因为它不生产，只是交割库提货点。
2. 点「100 km」：只剩 1 家（同园区仓库）。这就是"附近"在实际中的样子。
3. 右侧矩阵：左上"黄金区"是空的，左下"近但不匹配"挤着仓储企业——这张图就是方法的解释。
4. 抽屉 → 距离页：唐山三友绕行系数 1.26（太行山绕行），天津渤化 1.22。
5. Excel 的 `05 运输与合规`：纯碱**不在**危化品目录，但仍写了粉尘/碱性/防潮与普通货运资质。

### 02 液碱（危化 · 近厂）

1. 首屏 7 家，前 4 名全在 100 km 内——与纯碱完全相反的形态，说明方法不挑产品。
2. 打开任意一家抽屉：距离页出现"起终点同在园区内"的提示（中盐常州滨江 1.7 km 直线 / 5.2 km 公路），
   提醒你短途绕行系数失真、应确认能否管道输送。
3. `05 运输与合规`：UN1824 / 8 类 / 包装 II、危货运输许可、押运员、冬季结晶——**这是纯碱案例里完全没有的整块内容**。
4. 江苏索普（60 km，很近）只有 C 档 56 分：氯碱出身但主业已转醋酸，是否仍卖液碱未核实 → 又一个"近 ≠ 匹配"。

## 怎么复现

```bash
cd nearby-supplier-sourcing

# 示例 1
python assets/scripts/run_all.py \
  --dataset examples/01-soda-ash-shahe/dataset.json \
  --out     examples/01-soda-ash-shahe/output

# 示例 2
python assets/scripts/run_all.py \
  --dataset examples/02-caustic-soda-changzhou/dataset.json \
  --out     examples/02-caustic-soda-changzhou/output

# 离线（不请求 OSRM，距离按系数估算）
python assets/scripts/run_all.py --dataset ... --out ... --no-osrm
```

重跑会自动覆盖 `output/`（含 `dataset.json`、`geo_simplified.json`、`routes.json` 与两份成品）。

## 做第三个示例

1. 复制 `examples/01-soda-ash-shahe/dataset.json` 作为骨架
2. 换掉 `meta.product` / `meta.origin` / `items[]`，删掉所有旧的 `road_km` 等计算字段
3. 每家企业至少 1 条 A 或 2 条 B 级证据（工厂），否则会被校验拦下
4. `python assets/scripts/run_all.py --dataset ... --out ...`

> 校验脚本会拦住"弱证据高评分"：例如用行业名录（D 级）证明一家企业在产、还给它 A 档，
> 会被直接报错——这正是技能想强制的纪律。

## 数据口径提醒

两个示例的收货地都是**示例点**（`origin.is_example = true`），HTML 顶部与 Excel 封面
都有醒目提示。换成真实门牌后，距离、半径筛选、档内排序都会变，必须重跑。
