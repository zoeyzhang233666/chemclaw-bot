# 示例 02：骨架（占位数据，用来学契约）

**这里的数字和企业名都是占位**，没有任何业务含义，不能用于销售。它的用途只有三个：

1. 用最小数据跑通全流程（6 城 / 5 下游 / 6 企业 / 2 项目，约 30 秒生成）；
2. 让你照着结构写自己的 `data.json`；
3. 当回归测试用例——改完脚本跑一遍，能立刻发现破坏了什么。

## 覆盖了哪些写法

| 写法 | 在哪看 |
|---|---|
| 只填下游家数 `n`，让脚本自己算 `kt` / `share` | `cities[].inds` |
| 显式给经纬度（不依赖城市坐标库） | `cities[].lon/lat` |
| 不给 `tier`，让脚本按机会指数自动分档 | `cities`（都没有 tier） |
| 低置信条目的写法（`conf:"低"` + 「未核实」来源） | 示例企业 C |
| 误判条目怎么写「为什么像 / 实际用什么」 | 示例误判 F |
| 负增量项目 | `projects[].P02`（kt = −0.5） |
| 只给一个省时，省级表自动聚合 | `provinces`（仅广东一行） |

## 预期输出

- HTML 6 个城市气泡、5 张下游卡、5 个 canvas；
- Excel 12 表，`03 城市明细` 6 行、`05 客户线索` 6 行、`02 合计` 57 家；
- `validate.py` 会报 **1 条 warning**：「示例企业 C 是生产型但置信度低」——**这是故意的**，用来演示低置信条目的写法。真实项目里这条警告应当要么核实升为"中"，要么降级为线索池。

## 换成你自己的

```bash
cp data.json my.json
# 替换 meta.product / meta.region / cities / lanes / companies / projects / prices / route / narrative
# 删掉所有「占位」字样，逐条补 src
python ../scripts/validate.py my.json
python ../scripts/build_all.py my.json --out out --name 产品-区域
```
