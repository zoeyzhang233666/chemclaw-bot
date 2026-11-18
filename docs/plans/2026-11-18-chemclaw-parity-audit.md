# ChemClaw desktop v0.3.8 migration — parity audit (2026-11-18)

> 范围：PR #156（`feat/upstream-v038-migration`）对比当前 `main`，仅作首次源码/CI 核查。**不是完整验收、不是合并许可。**
>
> 基准 PR HEAD：`b5d9671ea47e829cdb19bcc8384ca2c5357a85ff`。完整 CI：[Test run 44228714595](https://github.com/zoeyzhang233666/chemclaw-bot/actions/runs/44228714595)，结果 `failure`。
>
> 决策原则：**上游 DS-Bot v0.3.8 作为运行时底座；ChemClaw 旧版 main 作为品牌、界面、化工配置与交互验收基准。** 不为了绿灯删功能/删测试；避免在多个 PR 中重复移植同一功能。

## A. 已有明确源码证据的差异

| 优先级 | 功能 / 风险 | main → #156 源码现状 | 处理与验收标准 |
| --- | --- | --- | --- |
| P0 | 专家分类 / 侧栏快捷筛选 | `chemclaw-bot/src/client/sidebar.js` 的旧版使用 `sidebarCategories`、`CategoryMenu`、`SidebarFilters`；新侧栏改为上游 `sectionId` / sections 组织，不再使用这些入口；`src/client/sidebar-filters.js` 在新分支被删除，`src/shared/sidebar-prefs.js` 与 `src/client/sidebar-categories.js` 仍在但不再接入侧栏。 | 把原“专家分类、筛选、分类折叠、手动排序/移动、分组”体验映射到新的 section 架构或明确保留兼容组件；**验证旧 sidebar prefs/分类分配在升级后不丢失**。与 main 截图比较，不能仅有普通分区就算通过。 |
| P0 | “复制专家”入口 | 旧版 `src/client/new-chat.js` 包含 `Copy expert`、`actions.duplicateBot` 入口，新版 `new-chat.js` 缺少对应代码（仍有创建 Bot、创建群聊）。`test/copy-expert-entry.test.js` 在 PR 中被删除。 | 恢复原创建菜单和命令入口，保留独立副本语义、继承能力、独立会话；恢复/改写对应测试。 |
| P0 | 首次打开不主动问候 | `app/scripts/check-packed.mjs` 校验欢迎页面时若出现消息即报 `A preset sent an unsolicited first message`；本轮 Windows GUI、Mac arm64 和 x64 都在相应安装态验证阶段失败。 | 查明真实的预设/升级触发路径与欢迎页交互；**不可简单删除断言**。无模型、首次授权、安装后初次打开都应停留欢迎页，用户主动发消息前不生成问候。 |
| P0 | 浏览器用户拒绝保护 | Windows 和 Linux 的 `app/scripts/check-browser.mjs` 校验在第 86 行报 `Missing expected rejection`，期望 `Rejected by user`。 | 核查浏览器操作审批/拒绝传递是否真的回归；不能修改断言来掩盖权限问题。 |
| P0 | Docker 构建路径 | CI Docker job 报 `"/ds-bot": not found`，说明仍有旧目录引用。 | 调整迁移后的 Docker context/COPY/路径；运行完整镜像启动及数据迁移检查。 |
| P1 | 预设专家、群与技能库 | `seed/catalog.json` 有 **50 个 roles（含主 Bot）和 15 个 groups**；`src/host/catalog-seed.js` 的 `seedChemClawTeam` 当前函数只直接创建主 Bot；`src/host/roster.js` 的 `bootstrap` 会调用 `ensureSkillLibrary` 与 `seedChemClawTeam`。原 `src/host/chemclaw-seed.js` 被移除。PR 描述称迁移 fixture 能生成 50/15，**但仅凭现有主路径与本轮失败 CI 不足以确认所有实机初装/升级路径均正确**。 | 分别检查初装、旧版 0.3.x 升级、重复启动和部分预设缺失时的实际数量、分类、可用性、技能分配，以及无重复创建；使用独立测试数据。 |
| P1 | 化工技能库 | `src/client/skill-library.js` 在两分支文件 SHA 相同；`src/client/settings.js` 已有 SkillLibrary 页面挂载。 | 保持旧有技能分类、搜索、图标、Try asking、安装/编辑/调用及推荐专家，实测 DSH 原生技能与化工技能是否能共存。 |
| P1 | APIHub / 芯化和云 MCP / 化工数据 | #156 有 `src/client/industry-connectors.js`、`src/host/company-connectors.js` 和相关设置项；存在并不等于授权、接入、错误处理、工具能力全部可用。 | 验证预置服务地址、密钥安全保存、连接状态、工具列表和一次实际调用（测试 Key / mock），不得把密钥写到仓库或日志。 |
| P1 | Mac 安装载体 | `app/electron-builder.yml` 当前 `mac.target: zip`（理由：无 Developer ID/公证的 DMG 可能被拦截），并非默认 DMG；`app/package.json` 单独存在 `dist:mac-preview` 路径。当前完成的是 arm64 .app 的 `pack --dir`，并**没有可下载的 M 芯片安装压缩包**；上传的 `macos-ui-arm64` 是测试截图。 | CI 修复后先产出适用于 Apple Silicon 的**独立测试 ZIP**，如果还要 DMG，另行验证签名/系统阻拦风险并明确文件格式；不把截图 artifact 当安装包。 |
| P1 | 桌面 profile 测试 | `Desktop app profile` job 的 `npm test` 报 `ReferenceError: chat is not defined`，以及“脚本应等启动窗口关闭”的断言失败；其他日志中的故意失败测试不必一律算主因。 | 定位测试夹具/启动流程差异并修复，明确回归影响；不直接跳过测试。 |
| P1 | Computer Use 能力可用性 | 新代码有 `src/client/computer.js`、`src/host/computer/*`、`app/src/computer-indicator.mjs` 与 DSH computer-use 依赖；但用户反馈最新版 DS-Bot 的 Chief 自称不能用。 | 区分“功能代码存在 / 总开关启用 / OS 权限具备 / Bot 工具已注册 / 实际调用成功”；以一次需经用户允许的 GUI 操作与日志为验收，不以 Chief 自述判断。 |
| P1 | 非桌面目录变更范围 | #156 差异共 992 个文件，其中包含约 80 个 `mobile/` 路径；本次目标是桌面迁移。 | 审查这些文件是否为上游基底更新所必需；不能未经专门验收就将移动端变化视作已验证。 |

## B. 优先实施顺序

1. **先保功能，再修 CI：** 为侧栏分类、复制专家、专家初始化的旧版行为补等价回归（允许为新版 API 重写断言，不允许降低覆盖）；形成对照表和基准界面截图。
2. **集中恢复 ChemClaw 定制入口：** UI 分类、创建入口、设置/技能/数据源。尽量以配置和独立模块接入 v0.3.8，不重写上游运行时；旧状态字段转换要有迁移测试。
3. **逐类消除构建阻断：** 欢迎页自动消息 → 浏览器拒绝 → desktop profile → Docker 路径。每次修改只跑关联的短测试，收敛后再统一运行完整 GitHub CI。
4. **运行独立数据夹具：** 新安装、从旧版本升级、重复启动；核对 50/15、历史会话/附件/长文本、用户自建 Bot/群/分类/技能，不能污染真实用户目录。
5. **产出 macOS ARM64 预览安装包并比对：** 对旧 ChemClaw 的欢迎页、分类、专家、技能库、设置逐屏截图对照；检查 Computer Use 的授权与真实操作。确认后再决定是否合并或 Release。

## C. 明确的禁区

- 不在此阶段合并 main、发 Release、触发 auto-update、要求用户频繁实机安装。
- 不触碰真实用户数据或凭证；迁移只能在隔离的 fixture 中验证。
- 不将“代码存在”视为“完整可用”，也不以“CI 全绿”代替界面和用户数据兼容验收。
- 不应以删除断言、禁用关键能力或大规模替换 ChemClaw 旧界面作为 CI 修复手段。

## D. 可复核来源

- [PR #156](https://github.com/zoeyzhang233666/chemclaw-bot/pull/156)
- [CI Test 44228714595](https://github.com/zoeyzhang233666/chemclaw-bot/actions/runs/44228714595)
- [main sidebar.js](https://github.com/zoeyzhang233666/chemclaw-bot/blob/main/chemclaw-bot/src/client/sidebar.js) / [migration sidebar.js](https://github.com/zoeyzhang233666/chemclaw-bot/blob/feat/upstream-v038-migration/chemclaw-bot/src/client/sidebar.js)
- [main new-chat.js](https://github.com/zoeyzhang233666/chemclaw-bot/blob/main/chemclaw-bot/src/client/new-chat.js) / [migration new-chat.js](https://github.com/zoeyzhang233666/chemclaw-bot/blob/feat/upstream-v038-migration/chemclaw-bot/src/client/new-chat.js)
- [migration catalog-seed.js](https://github.com/zoeyzhang233666/chemclaw-bot/blob/feat/upstream-v038-migration/chemclaw-bot/src/host/catalog-seed.js)
- [migration electron-builder.yml](https://github.com/zoeyzhang233666/chemclaw-bot/blob/feat/upstream-v038-migration/app/electron-builder.yml)
