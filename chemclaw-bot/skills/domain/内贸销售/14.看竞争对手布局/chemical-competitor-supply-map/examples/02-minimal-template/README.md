# 示例 02 · 最小结构模板（全虚构）

> **结构示例，不是研究结论。**
> 所有企业、数字、链接、客户均为虚构，仅用于复制字段和跑通“data.json → HTML + Excel”的流程。禁止用于真实业务判断。

## 用途

- 新产品的起点：复制 `data.json`，替换成真实企业/工厂/来源；
- 教 agent 认识字段：3 家企业、3 座工厂、2 个项目、3 家潜客、4 条来源；
- 回归测试：任何代码改动后，跑这个最小样例确认没有破坏通用性。

## 打开

- `示例品_示例省示例市_竞争供给地图.html`
- `示例品_示例省示例市_竞争供给地图.xlsx`
- `data.json`

## 字段覆盖

这个样例故意覆盖了：

- 两种工艺（工艺甲/工艺乙），地图/矩阵/图表都有颜色；
- 企业产能 = 工厂产能之和（100+60+180=340）；
- 项目：技改 + 新建；2027/2028；
- 潜客：玻璃 + 日化；S/A/B 优先级；
- 来源：A/B/C 三种等级；
- 冲突：1 项；
- 缺口：2 条；边界：2 条；
- `meta.is_synthetic: true`。

它**没有**覆盖：多基地企业、搬迁/置换、进口/出口、价格、真实经纬度精度。正式项目要补。

## 重新构建

```bash
cd ../..
python scripts/validate.py examples/02-minimal-template/data.json
python scripts/build_all.py examples/02-minimal-template/data.json examples/02-minimal-template
python scripts/qa.py \
  --data examples/02-minimal-template/data.json \
  --html examples/02-minimal-template/示例品_示例省示例市_竞争供给地图.html \
  --xlsx examples/02-minimal-template/示例品_示例省示例市_竞争供给地图.xlsx
```

## 复制成自己的项目

```bash
cp examples/02-minimal-template/data.json my-product.json
# 编辑 my-product.json：
# 1) meta / target：产品、区域、经纬度、锚点客户
# 2) companies / plants：真实企业 + 工厂 + 来源
# 3) projects / prospects / sources / conflicts / gaps
# 4) narrative：结论、动作卡
python scripts/build_all.py my-product.json out/
```

## 注意

- 示例里的 `https://example.com/s1` 等链接是占位，不要当真实来源；
- 潜客用量 `*` 是假设，不是企业披露；
- 不要把这个样例的数字写进真实报告。
