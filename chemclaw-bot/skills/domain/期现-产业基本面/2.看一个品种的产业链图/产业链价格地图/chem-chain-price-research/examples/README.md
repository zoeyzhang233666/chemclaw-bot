# 示例

两个例子，一个用来**抄结构**，一个用来**看完成态**。

## `template-example/` —— 空白模板（起手用这个）

- `chain-data.json`：五列骨架（上游原料 → 中间体 → 直接原料与助剂 → 本体产品 → 下游应用），
  7 个占位节点、6 条关系、7 条缺口登记、0 条价格。
- `template-example-chain.html`：由上面的数据生成，可以打开看"骨架长什么样"。
- **不含任何真实价格**，节点统一标为待取价状态；请勿直接交付。

用法：

```bash
cp examples/template-example/chain-data.json ./my-product/chain-data.json
# 替换 stages / nodes / links 里的名称与结构
python scripts/build_chain_html.py ./my-product/chain-data.json -o my-product-chain.html
```

## `sbs/` —— SBS 完整实例（看完成态）

- `chain-data.json`：SBS 全链 12 个节点、15 条关系、84 条原始报价记录、2 张附加明细、5 条缺口。
- `sbs-chain.html`：生成的交付物，可直接打开体验悬停/点击交互。
- `README.md`：这一份研究的数据日、来源、口径、缺口与校验记录。

它演示了几件在真实研究里一定会遇到的事：

1. 上游原料（石脑油、乙烯、纯苯、环己烷、丁二烯、苯乙烯）逐环节多地区报价，**不平均**成一个价；
2. 溶剂（环己烷）用虚线连接，标注为工艺投入而非等量消耗；
3. 下游四个应用方向（改性沥青、鞋材、热熔胶、聚合物改性）**没有授权报价**，
   如实画成缺口而不是编一个价格；
4. 资讯口径（早间提示里的区间价、涨跌）单独放进明细区，不与结构化报价混排；
5. 缺口逐条登记（含"接口观测数为 0"这种证据）。

## 两个例子都能复现

```bash
python scripts/validate_dataset.py examples/sbs/chain-data.json
python scripts/build_chain_html.py examples/sbs/chain-data.json -o examples/sbs/sbs-chain.html
python scripts/verify_html.py examples/sbs/sbs-chain.html --source examples/sbs/chain-data.json
node scripts/verify_render.js examples/sbs/sbs-chain.html        # 可选
```

三个校验脚本都不联网、不装包（`verify_render.js` 需要 Node，可选）。
