# chemical-downstream-leads · 安装与速用

> 这是一个人工智能代理用的 **skill**（技能包）。它解决一件事：
> **给定一个化工品，找出一张「谁在用、在哪、用多少、怎么联系」的可核验线索表。**

## 一、安装到另一台电脑

Skill 就是一个文件夹。把这个文件夹整个复制到你那台电脑的 skills 目录即可：

| 位置 | 说明 |
|---|---|
| `~/.agents/skills/chemical-downstream-leads/` | 用户级（推荐，所有项目可用） |
| `<项目>/.agents/skills/chemical-downstream-leads/` | 项目级（只在该项目可用） |

复制后确认目录里有 `SKILL.md`（带 YAML frontmatter 的 `name` / `description`），代理在匹配到相关任务时会自动加载。

**依赖**：Python 3.10+（建议 3.12 及以上；全部脚本已在 3.14 上实跑验证）。
- `merge_leads.py` / `qa_links.py`：只用标准库。
- `build_workbook.py`：需要 `openpyxl`（`pip install openpyxl`）。
- `build_html.py`：只用标准库，生成的 HTML 完全自包含（无外部 CSS/JS/字体），可离线双击打开、可打印。

## 二、目录内容

```
SKILL.md                          方法论主体（第 0~8 步 + 三条硬约束 + 自检清单）
references/
  industry-map.md                 怎么把产品翻译成 lane（应用地图）+ 两个不同产品的实例
  search-queries.md               ⭐ 检索式设计：四词槽、五类高命中组合、消歧、两条不依赖搜索引擎的通路
  evidence-and-grading.md         证据分级、peer gate、六个造假陷阱、抽样复核
  fanout-briefs.md                任务书模板（六件套）、崩溃后的枚举式重开、补量命名
  delivery.md                     目录结构、skill_config.json 格式、Excel/HTML 结构、交付报告四块
  failure-log.md                  15 个常见失败模式与修法
  example_config_sbs.json         一个真实项目的完整配置（可直接照改成别的产品）
scripts/
  merge_leads.py                  合并去重 / 规范化 / 算强度与优先级 / 标注抽检结论
  qa_links.py                     来源链接抽检（可达性 + 主体一致性，区分反爬与坏链）
  build_workbook.py               生成四表 Excel
  build_html.py                   生成自包含 HTML 报告（可筛选、可打印）
```

## 三、最短路径（5 步跑完一个产品）

```bash
# 0. 建任务目录
mkdir my_task && cd my_task

# 1. 照 references/example_config_sbs.json 改出你自己的 skill_config.json
#    —— 必须重写 file_blocks（板块表）与 strength_rules（用量强度关键词）

# 2. 按 SKILL.md 第 1~2 步画应用地图、做三维切分，然后按 references/fanout-briefs.md
#    的任务书模板，把每一格派给一个子代理；子代理把结果写进 leads_raw/*.json

# 3. 合并
python <skill>/scripts/merge_leads.py --dir .

# 4. 抽检（先抽检，再合并一次，备注才会写进来源列）
python <skill>/scripts/qa_links.py --dir .
python <skill>/scripts/merge_leads.py --dir .

# 5. 出交付物
python <skill>/scripts/build_workbook.py --dir .
python <skill>/scripts/build_html.py --dir .
```

产物：`leads.json`（数据）、`<产品>下游需求工厂线索表.xlsx`（Excel 四表）、`<产品>下游需求工厂线索表.html`（HTML 报告）。

## 四、三条最容易违反、也最要命的规则

1. **没有出处就不是线索** —— 抓不到就写「未核实 / 低」，或直接丢弃。**绝不猜域名。**
2. **同行不是客户** —— 自己也生产这个产品的公司必须剔除，且交付时要报出名单。
3. **先落盘，再汇报** —— 子代理的上下文是易耗品；大 JSON 读进上下文会直接杀死这一格任务。

## 五、换产品时最容易忘记改的三处

| 位置 | 为什么必须改 |
|---|---|
| `file_blocks`（板块表） | 决定板块归属与统计口径，照抄别的产品会串板块 |
| `strength_rules`（强度关键词） | 决定 ★ 与优先级，不同产品的吨位口径完全不同 |
| `excluded_peers`（同行名单） | 不同产品的同行完全不同，漏了就白送竞品情报给销售 |
