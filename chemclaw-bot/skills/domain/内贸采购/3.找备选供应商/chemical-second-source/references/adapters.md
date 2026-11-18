# 跨 agent / 跨机器适配

这个 skill 不依赖 DSH 专属 API。任何能读文件、写文件、执行 shell 的 agent 都能用。

## 1. 目录放置

把整个 `chemical-second-source/` 放到 agent 的 skills 目录，例如：

```text
# Claude Code / Codex 常见
~/.claude/skills/chemical-second-source/
~/.codex/skills/chemical-second-source/

# ChemClaw / WorkBuddy / 自建
<workspace>/skills/chemical-second-source/

# 任意项目
<project>/vendor/skills/chemical-second-source/
```

不要只复制 `SKILL.md`：还需要 `scripts/`、`templates/`、`examples/`。

## 2. 给 agent 的最小指令

```text
请使用 chemical-second-source skill：
1) 先读 SKILL.md，按 Step 0–10 执行；
2) 研究结果写到 data.json（不要手改 HTML/Excel）；
3) 跑 validate.py → build_all.py → qa.py；
4) 交付 HTML + Excel + build_report.json；
5) 不写“建议换成 X”，排序≠建议，决策权在采购。
```

Codex/通用 agent 可直接读 `AGENTS.md`，它更短。

## 3. 命令（Windows / macOS / Linux）

### Windows PowerShell

```powershell
$py = "C:\Path\To\python.exe"
& $py scripts/validate.py examples\02-minimal-template\data.json
& $py scripts/build_all.py examples\02-minimal-template\data.json out --prefix 示例化工品X
& $py scripts/qa.py out --node "C:\Path\To\node.exe"
```

### macOS / Linux

```bash
python3 scripts/validate.py examples/02-minimal-template/data.json
python3 scripts/build_all.py examples/02-minimal-template/data.json out --prefix 示例化工品X
python3 scripts/qa.py out --node "$(command -v node)"
```

### 不激活虚拟环境

用完整解释器路径即可；脚本只依赖 `openpyxl`。

## 4. 依赖

```bash
python -m pip install -r requirements.txt
```

- 唯一硬依赖：`openpyxl>=3.1`；
- Node.js 仅用于 `qa.py --node` 的 JS 语法检查；不装也能构建/打开 HTML；
- 构建不需要网络；
- 不需要 pandas/numpy/matplotlib/browser。

## 5. 各 agent 注意事项

### Claude Code

- 把 skill 放 `~/.claude/skills/`，在 `CLAUDE.md` 里加一句“涉及备选供应商/第二供应源时先读 chemical-second-source/SKILL.md”；
- 用 Bash 工具执行命令；
- 生成后让 Claude 读 `build_report.json` 并汇总。

### Codex

- 把目录放 `~/.codex/skills/` 或项目内；
- 让 Codex 先读 `AGENTS.md`；
- Codex 可能默认用 `python`/`py`；在 Windows 上明确解释器路径；
- 不要让 Codex 直接改 `templates/` 里的中文内容（产品差异放 `data.json`）。

### ChemClaw / WorkBuddy

- 若平台要求 `SKILL.md` + `scripts/` 结构，本目录已满足；
- 若平台只允许单文件 skill，把 `SKILL.md` 作为入口，把 `scripts/`/`templates/` 作为附件目录；
- 平台若不支持 Python，仍可用 `data.json` + 生成好的 HTML/Excel 作为模板手工替换；但推荐保留脚本。

### 通用 CLI agent

- 先 `pwd` 确认工作目录；
- 用绝对路径调脚本，避免 `cd` 混乱；
- 执行前确认 `python --version` ≥3.9、`openpyxl` 可导入；
- 输出目录不要与 skill 目录混在一起（建议 `out/` 或项目目录）。

## 6. 文件编码与中文

- 所有 `.py/.json/.md/.html/.css/.js` 用 UTF-8（无 BOM 更稳）；
- Windows 终端如显示乱码，设置：

```powershell
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

- Excel 字体用“微软雅黑”；macOS 没有时 Excel 自动回退，不影响结构；
- 中文文件名可用；打包 zip 时为非 ASCII 文件名设置 UTF-8 标志位 `0x800`。

## 7. 离线 / 内网

- 构建完全离线：CSS/JS/JSON 全内联，无 CDN；
- 研究阶段需要联网检索；如果内网只能访问部分站点，优先：
  - 巨潮资讯/交易所（公告）；
  - 政府/园区/生态环境（项目/处罚）；
  - 行业协会/券商（行业）；
  - 企业官网（线索）。
- 无法访问外网时，用采购内部资料/供应商提供的 COA/审计报告，仍按 A/B/C 标注（内部资料标“内部/待核”）。

## 8. 打包与分发

```bash
# 在 skill 根目录
zip -r chemical-second-source.zip . -x "*/__pycache__/*" "*.pyc" "out/*"
```

Windows PowerShell：

```powershell
Compress-Archive -Path * -DestinationPath ..\chemical-second-source.zip -Force
```

注意：

- 不要把 `out/`、`__pycache__`、临时 HTML/XLSX 打进去；
- 示例生成物可以保留（方便“先看成品”）；
- 如果平台对 zip 中文名敏感，用 `scripts/package.py` 设置 UTF-8 标志位，或改成英文目录名。

## 9. 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: openpyxl` | 没装依赖 | `pip install -r requirements.txt` |
| `python` 不是 3.9+ | 系统旧 Python | 用 `py -3`/完整路径/虚拟环境 |
| `validate.py` 找不到 `common` | 从其他目录直接跑脚本 | 用 `python scripts/validate.py`（脚本目录自动进 sys.path），不要复制单文件 |
| 中文乱码 | 终端编码/文件非 UTF-8 | 设 UTF-8；用 `read/write` 而不是重定向 |
| 生成 HTML 空白 | 模板占位符/JS 错误 | 重跑 `build_all.py`；`node --check`；看浏览器控制台 |
| Excel 打不开 | 文件被占用/生成中断 | 关闭 Excel；重跑；检查磁盘 |
| 图表空 | 数据区引用错/无数据 | 检查 `02` 数据行与 `len(data_rows)` |
| 文件名乱码 | zip 未设 UTF-8 标志 | 用 `_pack_skill.py` 或英文名 |
| `spawn EPERM`（浏览器截图） | 沙箱禁止子进程管道 | 跳过截图；用 `qa.py` + 人工打开；不要反复重试 |

## 10. 最小验收

```bash
python scripts/validate.py data.json
python scripts/build_all.py data.json out --prefix 产品名
python scripts/qa.py out
```

三条都通过，且人工打开 HTML/Excel 检查关键页，即可交付。
