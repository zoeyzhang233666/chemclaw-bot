# 快速开始（5 分钟跑通）

## 0. 环境

- Python 3.8+
- `pip install openpyxl`（仅 Excel 需要）
- 不需要网络、不需要 Node、不需要浏览器（HTML 生成后双击即可看）

## 1. 复制模板

```bash
mkdir examples/myprod-demand-3m
cp templates/demand-research-template.json examples/myprod-demand-3m/research.json
```

## 2. 按顺序填 JSON（详见 SKILL.md 的 8 步）

最小可跑通集合：

| 字段 | 最小要求 | 不填会怎样 |
|---|---|---|
| `meta` | product / window / asof 必填 | 校验失败 |
| `structure` | 至少 2 套口径，各含 org/year/basis/items | 校验失败 |
| `evidence` | 每条含 id/seg/metric/date/caliber/src/url；非数值类标 `qualitative:true` | 校验失败 |
| `gaps` | 至少登记 1 条（无缺口也需说明） | 校验失败 |
| `segments` | 有 `share` 的才进入卡片与加权 | 卡片区为空 |
| `series` | 同一口径的相邻点，才能算变化 | 无迷你趋势图（不阻断） |
| `sentiment` + `weights` + `dominance_weights` | 三者齐全才出加权传导指数 | 只显示结构权重（不阻断） |
| `proxy` / `transmission` / `policy` / `seasonal` / `sections` | 建议都填 | 对应区块为空（不阻断） |

## 3. 生成三件套

```bash
python scripts/build_research.py examples/myprod-demand-3m/research.json
python scripts/render_html.py    examples/myprod-demand-3m/research.json -o examples/myprod-demand-3m/report.html
python scripts/render_xlsx.py    examples/myprod-demand-3m/research.json -o examples/myprod-demand-3m/workbook.xlsx
```

## 4. 自检

```bash
python scripts/check_all.py examples/myprod-demand-3m/report.html \
                           examples/myprod-demand-3m/workbook.xlsx \
                           examples/myprod-demand-3m/research.json
```

看到 `✓ 全部通过` 即可交付。若报错，按提示逐条改 JSON——**不要改脚本去迁就数据**。

## 5. 参考现成案例

```bash
# 完整案例（137 条证据，纯碱）
python scripts/render_html.py examples/soda-ash-demand-3m/research.json -o /tmp/r.html

# 跨品种框架演示（尿素，7 条方法示意证据，不含真实数值）
python scripts/render_html.py examples/urea-demand-demo/research.json -o /tmp/u.html
```

建议先打开 `examples/soda-ash-demand-3m/report.html` 看成品长什么样，再倒推 JSON 该怎么写。

## 常见报错速查

| 报错 | 原因 | 修法 |
|---|---|---|
| `structure[0] 占比合计 88.0%` | 占比没凑满 100（含"其他"） | 补齐 `其他` 项 |
| `下游 pv 没有任何 A 级指标` | 该下游全是价格/利润 | 补日熔量/产量/订单，或在 `gaps` 说明并在正文标"低置信" |
| `evidence X 缺字段 caliber` | 没写统计口径 | 补"谁统计+范围+频率" |
| `evidence X url 非 https` | 用了 http | 换 https 链接 |
| `gaps 为空` | 没登记缺口 | 至少写一条，或写明"本次无缺口，因…" |
| `HTML 重复 id` | 自加的 section 与 JS 容器同名 | 改名（本 Skill 踩过：`section#policy` 撞 `div#policy`） |
| `Excel 与 JSON 数值不一致` | 手工改过 xlsx | 永远从 JSON 重新生成 |
