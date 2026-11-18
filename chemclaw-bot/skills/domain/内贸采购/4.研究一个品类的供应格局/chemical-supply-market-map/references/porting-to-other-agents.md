# 移植到其他 agent（chemclaw / workbuddy / codex / Claude Code / DSH）

本技能包只依赖两样东西：**Markdown 指令** + **Python 3.8+**（Excel 额外要 `openpyxl`）。
没有任何私有 API、没有前端构建、没有外部 CDN，所以理论上任何能跑 shell 的 agent 都能用。

---

## 一、能力矩阵

| 能力 | 必需？ | 没有时的降级 |
|---|---|---|
| 读写本地文件 | ✅ 必需 | 无法使用 |
| 执行 shell / Python | ✅ 必需 | 只能手工做，不推荐 |
| 联网检索 | 建议 | 用模型知识 + 用户提供材料，缺口如实登记 |
| 子代理并行 | 可选 | 串行采集，减少 lane 数 |
| `openpyxl` | 可选 | `--html-only`，只交付 HTML |
| `playwright` | 可选 | 人工打开页面检查 |

---

## 二、三种接入方式

### 1. 有 `SKILL.md` 约定（Claude Code / DSH / Claude Skills）

```bash
python scripts/install.py --target claude     # ~/.claude/skills/chemical-supply-market-map
python scripts/install.py --target dsh        # ~/.agents/skills/chemical-supply-market-map
```

装完重启 agent。触发词写在 `SKILL.md` 的 `description` 里（中英双语），agent 会按语义自动加载。

### 2. 读 `AGENTS.md` 的 agent（Codex / WorkBuddy 等）

两种做法，任选其一：

**做法 A：全局指令里加一行指针**（推荐）

在 `~/.codex/AGENTS.md` 或项目根的 `AGENTS.md` 里加：

```markdown
## 供应市场全景研究
当用户要做化工品「供应格局 / 供应市场全景 / 产能地图 / 采购视角研究」时，
先完整读 `<绝对路径>/chemical-supply-market-map/SKILL.md`，按它的十步工作流执行。
```

**做法 B：直接安装到项目内**

```bash
python scripts/install.py --target <你的项目>/.agents/skills
```
然后把包内 `AGENTS.md` 的内容追加到项目 `AGENTS.md`。

### 3. 自建 / 其他工具（chemclaw、内部 workbuddy 等）

只有两条要求：

1. 把整个 `chemical-supply-market-map/` 目录放到 agent 能读到的位置；
2. 让 agent 知道「遇到这类任务先读 `SKILL.md`」。

如果该 agent 有 system prompt 配置，把 `AGENTS.md` 全文贴进去最简单。

---

## 三、安装命令

```bash
# 看装到哪
python scripts/install.py --target all
# 生成可搬运的 zip（拷到别的机器上解压即可）
python scripts/install.py --pack chemical-supply-market-map.zip
# 不要 examples（包更小，约少 1 MB）
python scripts/install.py --pack chemical-supply-market-map-min.zip --no-examples
```

依赖：

```bash
pip install -r requirements.txt          # 只有 openpyxl
pip install playwright && playwright install chromium   # 可选，用于 ui_check
```

---

## 四、跨机器差异（Windows / macOS / Linux）

| 项 | 说明 |
|---|---|
| 路径分隔符 | 脚本内全部用 `os.path.join`，无需改 |
| 编码 | Windows 控制台可能是 GBK：脚本启动时 `reconfigure(utf-8)`，不会崩 |
| 字体 | HTML 优先 微软雅黑 → PingFang SC → Noto Sans SC，macOS/Linux 会自动回落 |
| 换行 | 写入统一 UTF-8 + `\n`，不影响 |
| 无 Python | 只能看 examples 里已生成的 HTML/Excel，无法做新项目 |
| 无网络 | 见下节 |

---

## 五、无网络时怎么办

1. 用模型知识与用户上传材料先填 `plants.json`（5–10 条即可起步）。
2. 每个数字的 `source` 写「模型知识，待核实」并把 `confidence` 设「低」。
3. 在 `gaps` 里加一条：「本次无联网，全部产能未经外部核实」。
4. 交付时明确说明：「本版为离线初稿，联网后需逐条核验 S 级来源」。

**不要**在没有来源的情况下把 `confidence` 写「高」。

---

## 六、打包分发

```bash
python scripts/install.py --pack chemical-supply-market-map.zip
```

zip 内结构（保持原样解压即可）：

```
chemical-supply-market-map/
├── SKILL.md  AGENTS.md  README.md  requirements.txt
├── scripts/     new_project / build_all / build_excel / _render / _common /
│                check_project / ui_check / install
├── assets/      template.html  style.css  app.js
├── references/  workflow / data-model / metrics-formulas / data-gaps /
│                procurement-framework / output-structure / evidence-channels /
│                delivery-checklist / failure-log / porting-to-other-agents
├── templates/   project.json  plant_row.json  company_row.json  project_row.json
│                lane_brief.md
└── examples/    soda-ash-cn-2026/  caustic-soda-cn-2026/
```

---

## 七、给不同 agent 的一句话提示词

- **Codex**：「读 `chemical-supply-market-map/SKILL.md`，按十步工作流给我做 <产品> 的供应市场全景，
  最后用 `check_project.py` 体检。」
- **chemclaw**：「用 chemical-supply-market-map 技能做 <产品> 供应格局；产能数据不足处明确标缺口，不要估算。」
- **workbuddy / DSH**：「加载 chemical-supply-market-map，输出 HTML + Excel，示例对照 examples/soda-ash-cn-2026。」
