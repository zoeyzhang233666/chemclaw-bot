# 准备客户拜访 · 一页式拜访背景卡

本目录是一个**技能包（skill package）**，给化工行业内贸/外贸销售 agent 使用：拜访任何一家 B2B 客户前，生成一张 5 分钟能看完、来源可查证、现场可直接使用的拜访背景卡（Excel + HTML 双交付）。

## 何时加载

当用户提出以下任一诉求时，**先完整读取本目录的 `SKILL.md`**，再按其「六步工作流」执行：

- 「我要拜访 XX 客户，帮我准备一下 / 出一张拜访背景卡」
- 「我将拜访【企业】的【采购/技术/老板】，本次想推进【首次接触/技术对接/送样/报价】，我销售【产品】」
- 「拜访前帮我研究下这家客户做什么、最近发生了什么、行情怎么样、该问什么」
- English: "prepare a pre-visit brief / visit background card for a customer"

## 使用方式

1. 读取 `SKILL.md`（含六步工作流、纪律、交付结构）。
2. 需要细节时按需读取 `references/` 下的对应文件（不要一次性全读）。
3. 研究产出统一落盘为 `visit_data.json`（契约见 `references/data-contract.md`），再用
   `python scripts/build_visit_workbook.py --data visit_data.json --out 拜访背景卡.xlsx` 出 Excel。
4. HTML 以 `examples/soda-ash-flat-glass/*.html` 为母版改造；设计规范见 `references/output-spec.md`。

## 交付物（固定）

- `拜访背景卡_<客户>_<产品>_<日期>.xlsx`：8 表（使用说明/拜访概览/客户画像/大事记/行情监控/提问清单/历史沟通台账/数据来源），提问清单与台账可现场填写。
- `拜访背景卡_<客户>_<产品>_<日期>.html`：单文件一页卡，采购/技术/老板三版本标签页切换，可打印成 PDF。
- （可选）一页 Markdown 卡，便于贴进聊天工具。

## 环境要求

- Python 3.8+；出 Excel 需要 `openpyxl`（`pip install -r requirements.txt`）；HTML 无依赖。
- 联网：优先使用宿主 agent 自带的搜索/抓取工具做取证；无联网时降级模式见 `references/porting-to-other-agents.md`。
- 硬性纪律：不虚构客户原话与需求；每个价格带日期+来源；先落盘再汇报。
