# 标杆客户复制 · 下游潜客池

本目录是一个**技能包（skill package）**，给销售/市场 agent 使用：从一家已成交的标杆客户出发，找出业务特征相似、因而会产生同类原料需求的下一批潜在客户。

## 何时加载

当用户提出以下任一诉求时，**先完整读取本目录的 `SKILL.md`**，再按其「九步工作流」执行：

- 「XX（标杆客户）是我的优质客户，帮我找相似客户 / 复制第二批潜客池」
- 「我要做 XX 化工品的内贸销售，从标杆客户找相似客户」
- 「下游需求工厂 / 客户线索 / 找客户 / 供应商开发名单 / 下游应用名单」
- English: "find look-alike prospects from my benchmark customer for a chemical product"

## 使用方式

1. 读取 `SKILL.md`（含工作流、gate、交付结构）。
2. 需要细节时按需读取 `references/` 下的对应文件（不要一次性全读）。
3. 用 `python scripts/*.py` 执行九个步骤；`scripts/fetch.py` 提供联网取证（仅依赖 Python 标准库）。
4. 交付物固定为：`下游潜客池.xlsx`（5 表）+ 单文件 `报告.html`（9 节，带筛选，可打印成 PDF）。

## 环境要求

- Python 3.8+；出 Excel 需要 `openpyxl`（`pip install -r requirements.txt`），出 HTML 报告无依赖。
- 联网：优先使用宿主 agent 自带的搜索/抓取工具；结构化取证（上市公司公告全文检索等）用 `scripts/fetch.py`。
- 若宿主支持子代理，lane 并行执行（并发 ≤8）；不支持子代理则串行执行并降低 lane 数量（见 `references/porting-to-other-agents.md`）。
