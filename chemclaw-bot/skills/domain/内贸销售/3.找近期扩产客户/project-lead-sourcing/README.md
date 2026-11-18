# project-lead-sourcing

把「未来 N 个月里，哪些正在建的项目会新增对本产品的需求」变成一张能打电话的表——**产品无关**（任意化工品/材料），**agent 无关**（任何能执行 shell 的 agent），交付 **Excel + 交互式 HTML**。

一条记录 = **一个具体项目**（业主企业 + 项目 + 建设阶段 + 预计投产时间 + 在哪用本产品 + 可点开的出处），并按**销售时点**分组：现在就该联系 / 3-6 个月后再联系 / 仅需关注。

## 快速开始

```bash
# 0) 只需要 Python 3.8+；出 xlsx 另需 openpyxl（没有会自动降级 CSV）
python -c "import openpyxl" 2>/dev/null || pip install openpyxl

# 1) 建项目（定契约）
python scripts/b2bctl.py new ./我的项目 \
    --product 纯碱 --formula Na2CO3 \
    --region 华东 --provinces 山东,江苏,浙江,安徽,上海,福建,江西 \
    --months 6 \
    --peers "山东海化,三友化工,中盐化工"

# 2) 探通道（换机器必跑！）
python scripts/b2bctl.py probe ./我的项目

# 3) 填应用地图：编辑 ./我的项目/lanes.json
#    每个 lane = 一个下游应用方向；写清用料逻辑、用量强度★、产业集聚地、5~8 家具名候选
python scripts/b2bctl.py lanes-check ./我的项目

# 4) 生成派工单
python scripts/b2bctl.py brief ./我的项目
#    有子代理就把 briefs/NN_*.md 全文分发；没有就顺序自己跑
#    产出写到 ./我的项目/leads_raw/NN_<lane>.json

# 5) 校验 → 合并 → 出表
python scripts/b2bctl.py collect ./我的项目
python scripts/b2bctl.py all     ./我的项目     # merge + 链接抽检 + build

# 6) 交付前自检（退出码非 0 就是没过，别带着失败交付）
python scripts/b2bctl.py check ./我的项目
```

**别忘了填两个判断性文件**，否则第 3、4 块交付不完整、`check` 会判不通过：
- `peers_excluded.md` —— 第三块：在 lane 检索阶段就被判定为同行、因而没进 JSON 的主体
- `gaps.md` —— 第四块：哪些通道失效/哪些板块在萎缩/哪些只能人工补证

这两个文件由 `new` 生成时首行带 `<!-- STATUS: UNFILLED -->`。**写完后把那一行删掉**，
`check` 才会放行——这是防止"交付了但第三/四块是空模板"的闸门。

## 不用网络也能验证

自带一份**真实**范例（纯碱·华东·未来 6 个月，103 条线索）：

```bash
cp -r examples/soda-ash-huadong /tmp/demo
python scripts/b2bctl.py merge /tmp/demo && python scripts/b2bctl.py build /tmp/demo \
  && python scripts/b2bctl.py check /tmp/demo
```

应复现出 **103 条**线索、销售时点 **16 / 43 / 44**，并生成 xlsx + html + md 三件套。

## 交付物长什么样

| 文件 | 内容 |
|---|---|
| `<产品><地区>未来<N>个月项目级潜客表.xlsx` | 6 表：说明与行业地图 / **项目线索总表（带筛选、来源超链接）** / 项目时间线 / 重点客户TOP / 分布统计 / 剔除与缺口 |
| `...html` | **单文件、离线可开**。项目时间线 ↔ 企业表**双视图**；按销售时点/建设阶段/省份/板块/角色筛选；点项目开抽屉 = 企业背景 + 证据与来源 + **「找客户最近的切入点」** |
| `方法与边界说明.md` | 交付四块的文字版（条数与分布 / 置信度分级 / 剔除的同行 / 缺口与负结果） |

## 目录

```
SKILL.md              agent 读这个（9 步流程 + 完成判据）
references/           方法、证据纪律、通道、时点规则、闸门、失败日志、移植
  method.md           为什么以项目为单位 + lane 设计 + 单耗估法与负结果
  evidence.md         trace 纪律、置信度判定、四个「严禁编造」的坑
  channels.md         通道清单、URL 模板、可达 vs 可解析
  timing.md           销售时点规则（含"在建但投产时间未披露"为什么算 3-6 个月）
  gates.md            五道闸门（地区/peer/去重/链接/自检）
  schema.md           18 个采集字段 + 8 个派生字段
  failure-log.md      11 种崩溃模式与修法
  portability.md      换电脑/换 agent/换国家 + 验收清单
  interface.md        内部模块契约
scripts/
  b2bctl.py           唯一入口：new/probe/lanes-check/brief/collect/merge/qa/build/all/check
  lib/                产品无关的核心（common/merge/qa/report_out/excel_out/html_out/channels）
  tools/              通道适配器（http/cninfo/eastmoney/eia/pdftext）
  channels.default.json   通道注册表（换国家改这里）
  templates/lane_brief.md.tmpl
examples/soda-ash-huadong/  真实范例（含预生成的交付物）
```

## 依赖与移植

- **只要 Python 3.8+**，其余全是标准库（无 requests / pandas / lxml）。
- `openpyxl` 仅用于 xlsx；缺失时自动降级 CSV 并明确提示。
- `node` 可选，用于 `check` 校验 HTML 内联 JS 语法。
- 换国家：改 `scripts/channels.default.json` + `config.json` 的 `provinces`。
- 详见 [references/portability.md](references/portability.md)。

## 设计上的一个取舍

`probe` 只判断**可达性**，不假装能判断**可解析性**。JS 渲染的列表页会返回 200 和几十上百 KB 的 HTML，
看起来完全正常却抽不出任何项目条目——用长度或关键词启发式**判别不出来**（壳页的命中数反而更高）。
所以本 skill 要求对列表型通道**跑一次适配器实测**（`python -m tools.eia selftest`），
而不是给一个看起来聪明但会骗人的自动判定。覆盖率报告宁可保守。