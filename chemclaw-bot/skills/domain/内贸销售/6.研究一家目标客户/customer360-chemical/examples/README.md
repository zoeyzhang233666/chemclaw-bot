# examples · 参考例子

研究任意客户前，先对照这里的范例理解"判断怎么下、证据怎么摆、估算怎么标"。

| 目录 | 场景 | 教学点 |
|---|---|---|
| `example-1-haihua-sodaash-salt` | **真实研究**：卖原盐 → 纯碱上市公司（山东海化 000822） | ①同名/近名主体区分表的标准做法 ②"补充供应商"型判断（有需求但被内供挤占） ③供应三层结构+需求估算标注 ④实控人变更史画法 ⑤"给账期前必看"风险横幅 |
| `example-2-viscose-caustic-direct-fit` | **虚构教学**：卖烧碱 → 非上市粘胶短纤工厂 | ①直接原料接口的正例判断（五接口命中原料层） ②非上市企业证据路径：环评公示/排污许可/招聘替代年报 ③处罚"已整改"的表述方式 |
| `example-3-trader-not-a-customer` | **虚构教学**：卖环氧丙烷 → 化工贸易公司 | ①**诚实反例**："是否生产企业"是第一道判断，五接口全部打不上时必须输出"可能不是目标客户"，不许硬凑 ②贸易商的风险横幅写法（货权/结算，非评级） |
| `example-4-lithium-plant-capex-window` | **虚构教学**：卖耐腐蚀泵 → 在建磷酸铁锂新厂 | ①项目窗口期客户：项目与动态是主分区 ②时间线逐条翻译"对我的产品的含义" ③新设项目公司的股东穿透与资金核实 |

## 重要声明

- **example-1 为真实公开信息研究**（检索窗口截至 2026 年 10 月，证据为真实链接）。
- **example-2/3/4 为虚构教学数据**：公司不存在，`meta.is_demo = true`，证据 URL 均为 `example.com` 占位符。它们只演示数据结构与判断方法，**实际研究必须用真实检索结果填充**，渲染时页面顶部会自动出现教学示例横幅。
- 所有估算数字均标注口径；范例中的"行业经验值"仅作演示，换产品时必须查证对应工艺的真实单耗。

## 运行范例

```bash
python scripts/build.py examples/example-1-haihua-sodaash-salt/data.json -o output/ex1
python scripts/build.py examples/example-2-viscose-caustic-direct-fit/data.json -o output/ex2
python scripts/build.py examples/example-3-trader-not-a-customer/data.json -o output/ex3
python scripts/build.py examples/example-4-lithium-plant-capex-window/data.json -o output/ex4
```
