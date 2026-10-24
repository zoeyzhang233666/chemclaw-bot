# 示例

每个目录都是**可运行的完整案例**：`input.json`（数据）+ 同名 `.html` + 同名 `.xlsx`（成品）。

用法：复制最接近的一个，删掉产物，改 JSON，重新生成。

```bash
cp -R example-1-soda-ash my-case
rm my-case/*.html my-case/*.xlsx
# 改 my-case/input.json（保留结构，改 meta.slug）
python ../scripts/build_report.py my-case/input.json -o my-case
python ../scripts/selfcheck.py my-case/input.json --outdir my-case
```

---

## 目录

| 目录 | 产品 | 案例数 | 演示重点 | 数据可信度 |
|---|---|---|---|---|
| `example-1-soda-ash/` | 纯碱（无机碱，非危化品） | 5 | 四类结论全覆盖；排污许可"无机碱制造"；产能置换反向证明；交割厂库陷阱；脱敏样例 | 3 家真实 + 2 家合成 |
| `example-2-tio2/` | 钛白粉（无机颜料） | 3 | 换品类后硬证据怎么换；"颜料制造"行业类别；危化证不覆盖非危化品；硫酸法/氯化法 | 1 家真实 + 2 家合成 |
| `_skeleton/` | 占位 | 1 | 最小可运行结构，字段注释齐全 | 占位 |

---

## example-1：纯碱

五个案例覆盖全部四种结论：

| 企业 | 结论 | 分数 | 关键依据 |
|---|---|---|---|
| 山东海化股份有限公司 | 生产厂家 | 84 | 排污许可"无机碱制造" + 年报产量 319.31 万吨 + 120→100 万吨减量置换 |
| 内蒙古博源银根化工 | 生产厂家（天然碱） | 76 | 一期 500 万吨达产公告 + 10.78 亿吨碱矿 + 降负荷公告 |
| 浙江杭实善成实业 | 贸易经销 | 18 | 郑商所**贸易商**厂库 + 0 条硬证据 |
| 某食品配料公司（合成） | 分装或复配 | 33 | SC 分装单元 + 后处理设备 |
| 某询价供应商（合成） | 证据不足暂无法确认 | 8 | 仅报价单 + 无定位照片 |

**最值得看的三点**：

1. 交割厂库 ≠ 生产资质——公告里写的是"贸易商厂库"；
2. 产能置换公告是"反向硬证据"——有 120 万吨老线才需要置换；
3. 两个合成案例演示"证据不足"与"分装"如何与"厂家"区分。

---

## example-2：钛白粉

| 企业 | 结论 | 分数 | 关键依据 |
|---|---|---|---|
| 龙佰集团 | 生产厂家 | 80 | 151 万吨/年产能 + 2026H1 产量 65.75 万吨 + 氯化法 + 海外项目 |
| 某贸易公司（合成） | 贸易经销 | 20 | 有代理授权、无装置 |
| 某"厂家直销"（合成） | 证据不足 | 9 | 仅报价单与两张无定位照片 |

**演示重点**：同一个方法论，硬证据从"无机碱制造"换成"颜料制造"，从"产能置换"换成"硫酸法/氯化法分线产能"；同时展示"危化证不覆盖钛白粉"这个通用误区。

> 注意：只有龙佰集团的事实来自公开来源（证券时报、巨潮资讯半年报、官网）。另外两个案例是**脱敏合成样例**，不对应任何真实企业，仅用于演示判定路径。

---

## _skeleton：空白模板

结构完整、内容占位。适合：

- 新产品第一次跑；
- 给不熟悉 schema 的人做参照；
- 排查"为什么生成失败"（它能跑通，说明脚本没问题）。

---

## 新增一个案例的最小步骤

1. 复制 `_skeleton/input.json`；
2. 改 `meta`（report_id、product、slug）与 `product_profile`；
3. 填 `cases[0]`：
   - 先写 `verdict` 与 `dims`（`score` = `dims` 之和）；
   - 再写 `direct` / `indirect` / `excluded`；
   - 最后写 `headline` / `verdict_detail` / `gaps` / `next_action`；
4. `python ../scripts/validate.py my-case/input.json`；
5. `python ../scripts/build_report.py my-case/input.json -o my-case`。

多个供应商就复制 `cases` 数组元素，改 `id`（英文短名，HTML 锚点用）。

---

## 常见改写点

| 想改 | 位置 |
|---|---|
| 产品名/规格 | `meta.product`、`meta.product_spec`、每个 case 的 `product`/`spec` |
| 硬证据清单 | `product_profile.regimes` / `not_evidence` |
| 评分维度 | `dimensions`（权重合计 100） |
| 索取清单 | `materials` |
| 验厂脚本 | `onsite` |
| 数据来源 | `sources` |
