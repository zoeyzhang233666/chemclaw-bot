# 跨 Agent / 跨电脑适配

> 这个 skill 只依赖 Python 3 + openpyxl。没有 DSH 专有 API、没有数据库、没有网络。
> 不同平台的“技能目录”不同，但入口都是 `SKILL.md` + `scripts/`。

## 1. 通用检查

在目标电脑上：

```bash
python --version
python -c "import openpyxl; print(openpyxl.__version__)"
node --version   # 可选，只有跑 app.js 语法检查/UI QA 时需要
```

如果 `openpyxl` 缺失：

```bash
python -m pip install openpyxl
```

只装一次。构建时不需要联网。

## 2. Claude Code

### 用户级

```bash
mkdir -p ~/.claude/skills
cp -r chemical-competitor-supply-map ~/.claude/skills/
```

### 项目级

```bash
mkdir -p .claude/skills
cp -r chemical-competitor-supply-map .claude/skills/
```

重启会话，输入“用 chemical-competitor-supply-map 做一个 XX 产品的竞争供给地图”。Claude Code 会读取 `SKILL.md` 的 frontmatter 和正文。

**注意**：不要把 `SKILL.md` 改名；不要只复制 `scripts/` 而漏掉 `references/`（agent 需要字段说明）。

## 3. Codex

不同 Codex 版本的技能目录可能不同。优先放在：

```text
<project>/skills/chemical-competitor-supply-map/
```

或 Codex 文档指定的用户级 skills 目录。让 Codex：

1. 先读 `SKILL.md`；
2. 按“研究流程”建 `data.json`；
3. 运行 `python scripts/validate.py`；
4. 运行 `python scripts/build_all.py`；
5. 运行 `python scripts/qa.py`。

如果 Codex 只能执行单条命令，直接让它跑 `build_all.py`，再让它读 `build_report.json` 确认数量。

## 4. ChemClaw

ChemClaw 的技能/知识库入口因部署而异。通用做法：

1. 把**整个解压后的文件夹**上传到“技能/知识库/工作区”；
2. 确认平台能读到 `SKILL.md`（而不是只索引 PDF/Word）；
3. 在对话里明确：“读取 chemical-competitor-supply-map/SKILL.md，按里面的流程执行”；
4. 如果平台只支持文件上传、不支持执行 Python，至少让它按 `SKILL.md` 产出 `data.json`，再把 `data.json` 拿到本地跑构建。

**不要**只上传 HTML 成品；那样 agent 学不到研究流程。

## 5. WorkBuddy

同上：优先上传文件夹/zip；如果 WorkBuddy 有“自定义技能/工具”入口，把 `scripts/build_all.py` 注册为命令，把 `SKILL.md` 作为说明。若只能上传文档，至少保留：

- `SKILL.md`
- `references/data-contract.md`
- `references/research-playbook.md`
- `examples/02-minimal-template/data.json`

## 6. 纯命令行 / 其他 Agent

```bash
cd chemical-competitor-supply-map
python scripts/build_all.py path/to/data.json path/to/out
```

任何能执行 shell 的 agent 都能用；只要它能把 `data.json` 写出来。

## 7. Windows 注意事项

- 路径含中文/空格：用引号；PowerShell 用 `&` 调用可执行文件。
- 长路径：把 skill 放在 `C:\skills\` 这类短路径，避免 260 字符限制。
- 文件名：HTML/Excel 可以中文；zip 内部 UTF-8；老 Windows 解压可能乱码，建议用 7-Zip。
- 换行：脚本用 `\n`；Excel 不受影响。
- 编码：所有 JSON/HTML/Python 用 UTF-8；PowerShell 输出中文先 `$env:PYTHONIOENCODING='utf-8'`。

## 8. macOS / Linux

```bash
python3 --version
python3 -m pip install --user openpyxl
python3 scripts/build_all.py data.json out/
```

字体：Excel 里的 `Microsoft YaHei` 在 macOS 可能被替换；不影响数据，只影响观感。需要更稳可把 `build_xlsx.py` 的 `FONT` 改成 `PingFang SC` 或 `Noto Sans CJK SC`。

## 9. 离线 / 内网

- ECharts + 中国 GeoJSON 已内联；HTML 不需要网络。
- 来源链接是外链，离线打开时点不开，但文本仍在。
- Excel 超链接是外链；离线时同样只显示文本。
- 如果内网禁止外部字体，HTML 已用系统字体 fallback；Excel 用本机字体。

## 10. 常见报错

| 报错 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: openpyxl` | 没装依赖 | `python -m pip install openpyxl` |
| `meta.target_lon / target_lat 必填` | 没填目标坐标 | 补经纬度 |
| `企业 ... 与工厂合计 ... 不一致` | 多基地漏拆/产能口径 | 拆工厂或改企业产能 |
| `工厂 ... 缺少 lon/lat` | 只写地址 | 补坐标 |
| `引用不存在的来源` | source_ids 拼错 | 修 ID 或补 source |
| HTML 打开空白 | 资源未内联/JS 报错 | 看控制台；重新 `build_all` |
| HTML 地图空白 | GeoJSON/ECharts 未加载 | 确认 `assets` 存在；不要用 CDN |
| Excel 图表空白 | 数据源是隐藏列/空 | 用可见单元格；重新生成 |
| 中文乱码 | 非 UTF-8 | 统一 UTF-8；PowerShell 设 `PYTHONIOENCODING` |
| `qa.py` 报合并重叠 | 手工改过表 | 重新生成，不要手改 |

## 11. 版本与升级

- 本 skill 的 `metadata.version` 在 `SKILL.md`；升级时保留旧 `data.json` 兼容。
- 新增字段应可选；新增必填字段要写迁移说明。
- 升级后至少重跑 `examples/01` 与 `examples/02`，确认不是“只对某个产品有效”。

## 12. 安全

- 不要把 API key、数据库密码、客户隐私写进 `data.json`。
- 来源 URL 只放公开页面；不要放内网/带 token 的链接。
- 示例 02 全虚构；示例 01 只用公开来源。
- 对外交付前，检查 `sources` 是否有版权限制/付费内容；必要时只保留标题和日期。
