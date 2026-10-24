# ChemClaw

[English](README.md) | 简体中文

ChemClaw 是基于 DeepSeek Harness（DSH）的化工业务助手，面向生产辅助、销售、采购、贸易、产业研究和期现研究。插件和独立桌面应用共用 `chemclaw-bot`，不修改 DSH。

内置 **50 个角色、15 个协作场景、108 个完整业务 Skills**，以及化学、统计、质询和交付辅助能力。50 位 Bot 和 15 个协作群会自动建好，并在侧栏按分类全部显示。打开「Bot」或「群聊」可查看用途、输入、成员分工和示例，直接开始对话，无需启用或组队。旧团队自动补齐预设，保留已有对话和自定义指令。

## 使用

- Windows：安装 `app/dist-pack/ChemClaw-0.2.0-win-x64.exe`，在应用中配置自己的模型。
- 官方 DSH 桌面版 **0.2.1-rc.2**：插件 → 添加插件，填入 `chemclaw-bot-0.2.0.tgz` 的完整路径，安装并启用，必要时重启。
- 不再需要运行旧手动 seed 脚本。已有团队、对话、自定义角色保留。

新安装默认简体中文、纸张主题。独立应用数据在 `~/.chemclaw`，工作文件在 `~/ChemClaw`；高级目录设置同屏校验冲突。原 DSH 数据只读导入。未配置 ChemClaw 发布源时禁用自动更新。

## 不打包 EXE，直接看源码效果

安装 **Node.js 24 LTS**，在项目根目录双击 **「启动 ChemClaw.cmd」**。首次自动安装依赖、构建客户端、同步插件并启动 GUI，需要联网，耐心等待终端窗口。

双击 **「开发 ChemClaw.cmd」** 可监听修改并重启 Host。开发数据在 `.chemclaw-dev`，工作文件在 `.chemclaw-workspace`，与正式应用隔离。先让任务完成，再修改源码。

已有依赖时也可以：

```powershell
cd D:\cursor-chembot\app
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
npm start
```

短命令不负责同步插件修改；日常预览建议使用根目录启动器。

## 连接器与文件

在 ChemClaw 设置的「连接器」中连接 **化工云数据中台**，只粘贴 Key，无需填写变量名。领取地址：[mcp.chem-cloud.cn](https://mcp.chem-cloud.cn/)。服务地址固定为 `https://datahub.chem-cloud.cn/mcp`。MCP 握手和工具发现完成后才显示已连接。不要把密钥发进聊天。

化工社公开查询默认匿名；PubChem、OPSIN、中英文维基百科无需 Key。历史日频行情需在连接器中安装受管 Python 环境，需要 Python 3.11+；不承诺实时，保留来源、口径与缺口。高级入口接受 HTTPS `mcpServers` JSON。不完整的高级服务不自动连接。

Bot 通过 DSH `present` 生成文件卡。点击卡片侧栏预览 HTML；文件按钮可在系统中打开或定位。Markdown 文件链接同样可点击。HTML 交互遵循宿主沙箱设置；连接器页提供启用交互预览的入口。文件删除或移动会显示错误。

普通 HTML、Excel、PPT、Word、PDF 由随包库和 `chem_deliver` 工具生成，无需 Python。复杂科学分析可安装可选依赖；转换现有 Office 文件、重算公式需另装 LibreOffice。示例仅供参考，模型可以改进分析与设计。

详见仓库中的 `chemclaw/docs/使用指南.md`、`chemclaw/docs/验收记录.md` 和 `docs/plans/2026-10-22-chemclaw.md`。

## 开发验证

在 `chemclaw-bot` 中运行 `npm ci`、`npm run harness`、`npm run build`、`npm test`、`node scripts/build-client.mjs --check`、`npm run lint`。Windows Host 冒烟：`node dev/bench-windows.mjs <新测试名称>`。在 `app` 中运行 `npm test` 和 `npm run dist`。

自动化使用 mock 与隔离数据，不代表模型研究质量。生产能力限于辅助研究和分析，期现能力限于研究和回测。模型由用户配置。

## 许可

Apache-2.0。基于 Fei2411 的 DS Bot，运行于 DeepSeek Harness。上游归属与第三方许可见 `NOTICE`。蓝云和龙虾图形为原创。旧 AGPL PPT 技能不分发；第三方参考固定版本并保留许可，普通业务不套用软件开发流程。


本轮状态：先审阅源码 GUI，得到用户明确确认后才重建 EXE。dist-pack 中的旧 EXE 不包含本轮界面修改。

模型：ChemClaw 设置 → 模型，APIHub 放在首位。领取 Key：https://apihub.chem-cloud.cn/；固定 API 地址：https://apihub.chem-cloud.cn/v1。填 Key、获取模型、勾选保存即可，其他供应商仍可添加。

已内置 dsh-free-search 0.9.12 的免费搜索与回退能力，结果保留出处。一个引擎失败不代表所有联网能力不可用。化工社匿名能力在公开研究数据中，可选授权单独折叠。
