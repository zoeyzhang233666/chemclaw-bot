# 示例

## 01-meoh-huadong —— 完整跑通的实例

**题材**：华东地区甲醇最近 3 个月的原料行情（采购视角）
**数据窗口**：2026-07-16 → 2026-10-19
**采购点**：华东太仓（主）、常州、内蒙北线、山东临沂、河南、河北、广东、生意社江苏基准价、CFR 中国
**产物**：

```
01-meoh-huadong/
├─ research.json                              手填数据（唯一真源）
├─ raw/甲醇_MA主连_daily.json                  期货日线（仅参考）
├─ build/data.json                           装配后的中间数据（HTML/Excel 同源）
├─ out/甲醇-华东_原料行情底稿_采购.html         交互看板（1.1 MB，零外链）
├─ out/甲醇-华东_原料行情底稿_采购.xlsx         12 表工作簿
└─ shots/{full,drawer,mobile}.png             渲染自检截图
```

**复现命令**

```bash
cd examples/01-meoh-huadong
python ../../scripts/build_all.py research.json --out out --name 甲醇-华东 --shots shots
```

期望末段输出：

```
--- 静态自检：0 error ---
--- 工作簿自检：0 error ---
== 0 项失败
```

### 这个例子演示了什么

| 技能要点 | 在实例中的体现 |
|---|---|
| 六项口径 | 15 条报价全部带点位/规格/含税/提货方式/日期/来源；同一采购点同日三种口径（区间 3890–4030、指数 3960、日报 3983）分列并说明差异 |
| 不预测 | 全文无方向性词汇；事件只写"同期"；`talk[].a` 全部中性；`validate.py` 无命中 |
| 稀疏序列处理 | 太仓 9 个真实报价点，报告显式标"90 天 8 个点"，不插值 |
| 区域价差 | 太仓 vs 内蒙/临沂/河南/河北/广东同日比较；未取得运价 → 对应链路 `checked:false` 并标红 |
| 产业链自证 | 煤制 1.55 吨煤/吨、气制约 1000–1100 方/吨、MTO 约 2.8–3.0 吨甲醇/吨烯烃，每条都有工艺依据与占比 |
| 成本不全不合计 | 煤制路线只算原料成本 1216.8，加工费缺失 → 显式"分项不全，未合计" |
| 传闻隔离 | "伊朗装置恢复满负荷""海峡已开放"两条只有单一来源 → 进"未采纳消息"，图上不标点 |
| 缺口清单 | 8 条：当日区间价、日度序列、运价、MTO 理论毛利、传统下游分品种开工、两套库存口径冲突、伊朗负荷、采购参数为假设值 |
| 采购参数 | 库存 12 天 → 自动推算"可支撑至 2026-10-28"；月用量 3000 吨 → 自动算"每涨 100 元/吨，月度采购额变动 30 万元" |

### 换品种时的最小改动

只改 `research.json`：

1. `meta`：product / spec / region / asof / unit。
2. `anchor` + `quote_series` + `spot`：换成新品种的真实报价（六项口径齐全）。
3. `upstream` / `downstream` / `chain_proof` / `routes`：按 `references/chain-mapping.md` 重新推链。
4. `balance` / `events` / `facts` / `talk` / `gaps` / `sources`：全部重写。
5. `futures`：没有场内期货就整块删掉（工具会自动处理，只在 KPI 少一张卡）。

`scripts/` 与 `templates/` 一行都不用改——这是本技能"通用"的定义。

---

## 模板

`research.template.json` 是带说明的空白模板，复制成新项目的 `research.json` 再改。
`validate.py` 对模板只出 INFO（占位符不算错），实盘数据才会触发 ERROR/WARN。
