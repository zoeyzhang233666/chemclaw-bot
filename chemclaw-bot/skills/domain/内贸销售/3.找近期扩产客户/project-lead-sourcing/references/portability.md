# 可移植性：换电脑、换 agent、换国家

目标是**任何能执行 shell 的 agent** 都能用，且结果结构完全一致。

## 1. 依赖

| 需要什么 | 说明 |
|---|---|
| **Python 3.8+** | 全部核心功能 |
| `openpyxl` | **仅**用于出 `.xlsx`。没有就自动降级为 CSV 并明确提示 |
| `node` | **可选**，仅用于 `b2bctl check` 校验 HTML 内联 JS 语法 |

**除 `openpyxl` 外全部是 Python 标准库**——没有 requests、没有 pandas、没有 lxml。
`tools/http.py` 自带编码级联（`charset → utf-8 → gb18030 → big5 → latin-1`），不需要 `chardet`。

```bash
python -c "import openpyxl; print(openpyxl.__version__)"   # 有就出 xlsx
```

## 2. agent 工具映射

管线把**所有重活放在命令行**里，agent 只负责三件事：执行命令、读写文件、做语义判断。

| 方法论动作 | 有子代理的宿主（DSH / Claude Code） | 无子代理的宿主（codex / 终端） |
|---|---|---|
| 探通道 | `b2bctl probe` | 同 |
| 铺 lane | 把 `briefs/NN_*.md` **全文**交给子代理，并发 ≤8 | **顺序**执行每个 brief，做完一个再下一个 |
| 收 lane | 子代理 `write` 落盘 | 自己 `write` 落盘 |
| 合并/抽检/出表 | `b2bctl merge/qa/build` | 同 |
| 联网检索 | 宿主自带搜索（若有），把能力登记进 `channels.json` | `tools/cninfo.py` 等 http 通道 |

**关键**：有没有子代理只影响**快慢**，不影响**结果结构**。因为字段 schema、闸门规则、交付格式全部在代码里，不在 agent 的行为里。

### 各 agent 的具体注意点

- **codex**：没有子代理，也没有 `ask_user_question`；把第 1 步的三个问题**直接在回复里问**，或从用户原话里提取。用 `apply_patch` / shell 写文件。
- **chemclaw / workbuddy**：若有自带的化工数据库或检索工具，**那就是最强通道**——登记进 `channels.json` 的 `host_tools`，并让 lane `来源` 回溯到原始页面。
- **DSH**：有 `subagent`，但**不能给正在运行的子代理追加指令**（只能对已结束的继续发消息）。所以 **brief 必须一次写完整**。
- **任何 agent**：如果宿主没有 `write` 工具，用 shell 重定向即可（`> file`）。落盘路径是相对项目根的普通路径，没有任何宿主专属语义。

## 3. 目录与调用约定

技能根目录（`scripts/` 是相对技能根的路径）：

```
project-lead-sourcing/
  SKILL.md                      agent 读这个
  references/                   按需细读
  scripts/
    b2bctl.py                   唯一入口
    lib/  tools/                纯标准库实现
    channels.default.json       通道注册表（换国家改这里）
    config.example.json
    templates/lane_brief.md.tmpl
  examples/soda-ash-huadong/    可离线跑通的完整范例
```

调用方式（**与当前工作目录无关**，`b2bctl` 自己解析相对技能根的路径）：

```bash
python <技能根>/scripts/b2bctl.py <command> <项目目录> [...]
```

项目目录是**用户的任务目录**，可以在任何地方，与技能根无关。

## 4. Windows 特有

1. **控制台编码**：`b2bctl` 启动时会 `sys.stdout.reconfigure(encoding='utf-8')`。若仍有中文乱码，先 `chcp 65001`。
2. **CSV 降级用 `utf-8-sig`**：这样 Excel 双击不乱码。
3. **不要在路径里用中文以外的怪字符**——`render_stem()` 会清掉 `\ / : * ? " < > |`，但项目目录名由你控制。
4. **`.ps1` 如果你自己写**：必须存成 **UTF-8 with BOM**，否则 PS 5.1 按 ANSI 读源码会让中文字符串破坏语法。**优先用 Python 工具，避开这个坑。**

## 5. 换国家 / 换地区

1. **改 `scripts/channels.default.json`**：把当地的公告/许可/招标平台加进去（字段含义见文件内 `_comment`）。
2. **`probe` 不认国家**——它只判断"能不能连通、内容像不像目标页"，所以扩展成本很低。
3. **`config.json` 的 `provinces`** 换成当地行政区；地区闸门是**前缀匹配**，容忍"XX省"vs"XX"。
4. 若当地不流行"环评公示"，把 `references/channels.md` 里的 EIA 部分替换为**建设许可 / 环境许可 / 项目审批**的对应平台。

## 6. 移植时的验收清单

在新机器上，按顺序跑一遍，**每一步都要过**：

```bash
cd <技能根>

# 1) 冒烟：建一个空项目
python scripts/b2bctl.py new /tmp/probe-demo --product 纯碱 --region 华东 \
       --provinces 山东,江苏,浙江 --months 6

# 2) 探通道（必须能跑完并写出 channels.json；可达数可以为 0，但结果要落盘）
python scripts/b2bctl.py probe /tmp/probe-demo

# 2b) 列表型通道的可解析性实测（关键：可达 ≠ 能抽出条目）
cd scripts && python -m tools.eia selftest && cd ..

# 3) 用自带范例验证端到端（不需要网络）
cp -r examples/soda-ash-huadong /tmp/demo
python scripts/b2bctl.py lanes-check /tmp/demo
python scripts/b2bctl.py collect    /tmp/demo
python scripts/b2bctl.py merge      /tmp/demo
python scripts/b2bctl.py build      /tmp/demo
python scripts/b2bctl.py check      /tmp/demo
```

第 3 步应该产出 `纯碱华东未来6个月项目级潜客表.xlsx` + `.html` + `方法与边界说明.md` 三件套
（**103 条线索**，`16 / 43 / 44` 的销售时点分布），且 `check` 退出码为 0。
若你复现出的数字与此一致，说明移植完全成功。

范例里的 `gaps.md` / `peers_excluded.md` 已经是填好的（无 `STATUS: UNFILLED` 标记），所以能过。
**你自己新建的项目**这两个文件是脚手架模板，不填就会被 `check` 拦下——这是故意的。

**这一步通过 = 移植成功**，剩下的只是数据源差异。

## 7. 已知的环境差异（不要当成 bug）

| 现象 | 是否正常 |
|---|---|
| `probe` 可用通道数为 0 | 正常（受限网络）。此时只能靠宿主 agent 自带的联网搜索 |
| 某省环评列表抓不到（`len` 极小） | 正常，该栏目是 JS 渲染。会体现在第四块的覆盖缺口里 |
| 大量条目的 `年需求量估算` = 无法估算 | **正常**。公开渠道普遍不披露单耗，纯碱那轮只有 36% 能估 |
| HTTPS 站点全部不可达 | 受限网络的正常表现，用明文 http 入口替代 |
| `check` 报 `GAPS:BEGIN` 还在 | **不正常**——第四块没写完，去写 `gaps.md` |