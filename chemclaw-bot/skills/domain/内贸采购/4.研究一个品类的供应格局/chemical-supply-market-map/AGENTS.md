# 化工品供应市场全景（采购视角）

本目录是一个**技能包（skill package）**，给采购/寻源/市场研究的 agent 使用：
输入一个化工品，输出「谁能供、在哪供、什么工艺、未来两年多出来多少、价格在什么位置、采购该担心什么」
的一张可交互全景（HTML）+ 一本可追溯数据包（Excel）。

## 何时加载

当用户提出以下任一诉求时，**先完整读取本目录的 `SKILL.md`**，再按其十步工作流执行：

- 「帮我做 XX（化工品）的供应格局 / 供应市场全景 / 产能地图」
- 「采购视角看 XX：谁在供、集中在哪、未来新增多少、价格什么位置」
- 「XX 有哪些主要生产企业、产能多少、集中在哪些省」
- 「XX 的断供风险 / 单源依赖 / 区域集中」
- English: "supply market landscape for X", "who produces X in China", "procurement risk map for X"

不适用：单点价格行情（用 `chem-market-brief`）；找下游客户（用 `b2b-lead-sourcing`）。

## 使用方式

1. 读 `SKILL.md`（含六段框架、五道 gate、十步工作流、固定交付结构）。
2. 需要细节时按需读 `references/` 下的对应文件（**不要一次全读**）。
3. 用 `python scripts/*.py` 执行；产品差异全部写在 `project.json` + 三个 JSON 数据文件里。
4. 交付物固定为：`<简称>供应格局全景_<年>.html`（单文件、离线可开）+ `<简称>供应格局数据包_<年>.xlsx`（16 表）。

## 硬约束

- **不估算**：拿不到的数据写「数据缺口」并在 `gaps` 里登记影响与补齐方式。
- **每个数字有来源**：`sources[]` 里的 S 编号，没有来源就标「未核实」。
- **毛产能 ≠ 净新增**：置换/搬迁必须扣减退出产能，不确定就标「待确认」。
- **口径并列不平均**：同一指标有多个公开口径时并列展示，不取平均。

## 环境要求

- Python 3.8+；出 Excel 需要 `openpyxl`（`pip install -r requirements.txt`），出 HTML 无依赖。
- 联网：优先用宿主自带的搜索/抓取工具收集证据。
- 若宿主支持子代理，产能/画像/项目可拆 lane 并行（并发 ≤5）；不支持则串行。

## 快速自检

```bash
python scripts/build_all.py --dir examples/soda-ash-cn-2026 --check
python scripts/build_all.py --dir examples/soda-ash-cn-2026
python scripts/check_project.py --dir examples/soda-ash-cn-2026
```
