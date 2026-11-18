# ChemClaw ↔ DS-Bot main 能力完整性审计（dry run）

日期：2026-10-28。  
性质：**审计报告 + 最小补齐计划**。未改 `main`、未合 PR、未打包、未发 Release。

## 基准

| 侧 | Revision | 版本 |
| --- | --- | --- |
| 上游 DS-Bot `origin/main` | [`4a7b55069ad300eae8be42a74f31bc170b40ead7`](https://github.com/Fei2411/DS-Bot/commit/4a7b55069ad300eae8be42a74f31bc170b40ead7)（tag `v0.2.3`） | 0.2.3 |
| ChemClaw `chemclaw/main` | `e0160fefda85484b0c05bde8688b3cea83743bc2` | 包版本仍标 **0.2.2**（功能已吸收大量 0.2.3） |
| 本地工作区 `HEAD`（审计时） | `fe1c15bb` | 落后 `chemclaw/main` 约 60 commits |

审计结论以 **`chemclaw/main` tip** 对照上游正式 main 为准，不以本地落后工作区冒称 ChemClaw 现状。

上游产品与说明：[Fei2411/DS-Bot](https://github.com/Fei2411/DS-Bot)、[v0.2.3 CHANGELOG](https://github.com/Fei2411/DS-Bot/blob/main/CHANGELOG.md)。

## 硬约束（全程）

- 不得覆盖 ChemClaw 的 50 Bot、15 群聊、Skills、MCP、APIHub、品牌与 ChemClaw 发布源/更新账号。
- 不将文件同名或已有调用接口当成完整功能已实现。
- 不以测试文件存在当作实际功能已通过；unit / mock smoke ≠ 真实 UI / 多平台人工验收。
- DSH 固定既有 pin（rc.3）；不 patch DSH。
- 本文件是 dry run 产物；补齐须另开分支，整批验收前不合 `main`、不发版。

相关历史文档（时点不同，以本文为准核对最新 tip）：

- [2026-10-26-upstream-audit.md](2026-10-26-upstream-audit.md)
- `chemclaw/main` 上的 `2026-10-27-upstream-status.md`、`2026-10-28-upstream-023.md`、`2026-10-28-upstream-023-batch-verify.md`（本地工作区可能尚未检出）

---

## 八项重点审计

每项字段：上游位置 → ChemClaw 位置 → 状态 → 回归证据 → 是否需同步与风险。

状态枚举：**完整具备** / **有替代实现** / **部分具备** / **缺失**。

### 1. 浏览器 refs、task、script 三种执行模式

| 字段 | 结论 |
| --- | --- |
| **上游** | 宿主：`ds-bot/src/host/browser/{refs,task,script}.js`；`ds-bot/src/host/browser-plugins.js` 导出 `{ refs, script, task }`，配置 `browserPlugin`。独立包与 bench：`browser-plugins/{refs,task,script}/`（见该目录 README）。会话：`browser/session.js` 的 `runScript` 等。 |
| **ChemClaw** | `chemclaw-bot/src/host/browser/{refs,task}.js`；`browser-plugins.js` 仅 `{ refs, task }`。**无** `browser/script.js`。**无** 顶层 `browser-plugins/`。IPC 前缀为 `chemclaw:browser-endpoint`（与上游 `ds-bot:` 分叉，应保留）。 |
| **状态** | **部分具备**（refs + task 有；script 缺失；独立插件包/bench 缺失） |
| **回归测试** | 有 `browser-plugins.test.js`、`browser-handoff.test.js`、`browser-plugin-output.test.js` 等（refs/task）。**无** script 专项；顶层 isolation / write-safety **未**移植。 |
| **需同步** | **是**。风险：低–中。优先复用上游 `script.js`（约 34 行）并入 `browserPlugins`；保持 ChemClaw IPC 与 profile 路径。勿引入第二套 Playwright。顶层 `browser-plugins/` 可后置作 bench。 |

### 2. 浏览器授权管理页面和操作审批

| 字段 | 结论 |
| --- | --- |
| **上游** | UI：`ds-bot/src/client/browser-settings.js`（`BrowserPage`），Settings → Browser。宿主：`browser-plugins.js` 的 `GRANT_KINDS` + `browserGrants`；`approvals.js`；客户端 `approval-notices.js`。 |
| **ChemClaw** | 宿主授权与审批逻辑在（`browserGrants` / `GRANT_KINDS` / `roster` 清洗；`approvals.js`；`approval-notices.js`）。**无** `browser-settings.js`。Settings **无** Browser 页。i18n 已有「Allowed actions」等**孤儿文案**。 |
| **状态** | **部分具备**（运行时审批 + grants 模型有；用户可管理授权页缺失） |
| **回归测试** | host / approval 有测。**无** Browser 设置页 UI 测。 |
| **需同步** | **是（P0）**。风险：低。整文件移植 `browser-settings.js` 并挂 Settings；保留「Skill library」与 About ChemClaw。不碰 connectors / APIHub。 |

### 3. 密钥用途编辑及清空

| 字段 | 结论 |
| --- | --- |
| **上游** | `ds-bot/src/client/secret-card.js`：`PurposeEditor`、`SecretsPage`；Settings → Secrets。`secrets.js` 的 `secret-update` 可改 `purpose`（空串清空）。 |
| **ChemClaw** | `secret-card.js` 明显短于上游（约少 150 行）：仅请求卡 / Dock。**无** PurposeEditor、SecretsPage。Settings **无** Secrets 页。`secret-update` **只改 scope**，忽略 purpose；`secret-set` 空用途保留旧值。 |
| **状态** | **缺失**（相对上游完整「事后编辑/清空用途」路径；请求时填用途 ≠ 设置页管理） |
| **回归测试** | secrets host 测有。**无** 用途编辑/清空 UI+API 回归。 |
| **需同步** | **是（P0）**。风险：中。须同时改 host 与客户端；避免与连接器凭据流混放；不恢复旧「模型/MCP 密钥塞 Secrets」路径。 |

### 4. Bot 详情抽屉与 DSH 右侧面板互斥

| 字段 | 结论 |
| --- | --- |
| **上游** | `ds-bot/src/client/right-panel.js`（`RIGHTBAR_ATTRIBUTES`、`rightColumnOpen`、`drawerOpened`、`columnOpened`、`createSwitchWindow`）；`index.js` MutationObserver 接线。测：`right-panel.test.js`（公开 #456 / #470）。 |
| **ChemClaw** | **无** `right-panel.js`；`index.js` **无** RIGHTBAR 互斥接线。仅有 `browser-overlap.js`（矩形重叠，≠ 面板互斥）。技能报告 HTML 内的 `close-drawer` **不算**产品互斥。 |
| **状态** | **缺失** |
| **回归测试** | **无** |
| **需同步** | **是（P0）**。风险：低–中。几乎可原样移植 + 接线；需桌面/窄屏 fullscreen 实测。不改 DSH。 |

### 5. 字体、长文、附件排版和键盘操作

| 子项 | 上游 | ChemClaw | 子状态 |
| --- | --- | --- | --- |
| 桌面中文系统字体 | `app/src/fonts.css` + `main.mjs` 注入 | **无** `fonts.css`；插件 `runtime/fonts/NotoSansSC` 为另一路径 | 有替代 / 不等价 |
| 长文行距/列表/行内代码 | styles：`+10px`、`li+li`、`box-decoration-break`、`text-autospace` | 气泡仍 `+8px`；缺列表与 code 行盒修复 | 部分具备 |
| 代码围栏折叠 | `fold.js` 空 fence 拉正文、剥语言标签（#579） | 旧 `foldPreview`，缺 0.2.3 fence 修复 | 部分具备 |
| 输入框附件独立行 | styles 对 `conversation.input.attachments` `_rail` 全宽置顶 | 有 attachments `order:0`，缺 `_rail` 细则 | 部分具备 |
| 卡片键盘 focus ring | #614 含 `bt-q-submit` / `bt-q-btn` 等 | 有部分 `:focus-visible`；缺 submit/btn 一组 | 部分具备 |
| 插话「未读」 | `header.js` + `[data-pending-steering]` | **已有** | 完整具备（代码） |

| 字段 | 结论 |
| --- | --- |
| **总状态** | **部分具备** |
| **回归测试** | fold / 样式多依赖视觉；ChemClaw 未对齐上游 fence 用例。 |
| **需同步** | **是（P1）**。风险：低。差分合并；勿覆盖 ChemClaw 中文主题与 skill 菜单样式。 |

### 6. 自动搜索插件禁用后的联网回归

| 字段 | 结论 |
| --- | --- |
| **上游** | `app/src/search-patch.mjs`：`web-search-auto` disabled 且 `web.searchProvider === auto` 时写 `search-selector.patch.yml`；`host.mjs` 调用 `reconcileSearchSelector`。测：`app/test/search-patch.test.mjs`（#128 / #436）。 |
| **ChemClaw** | **无** `search-patch.mjs`；`app/src/host.mjs` 固定 `patchFiles: []`。有 `chemclaw-bot/web-search.js` 与 `dev/verify-search.mjs`（验证搜索可用 ≠ 禁用 auto 后的修复）。 |
| **状态** | **缺失** |
| **回归测试** | **无** search-patch 测。 |
| **需同步** | **是（P1）**。风险：中。适配时包名过滤改为 `chemclaw-bot`；勿覆盖公司数据 / Chemcloud 路由。 |

### 7. 0.2.3 所有新增功能和修复项

对照上游 [CHANGELOG 0.2.3](https://github.com/Fei2411/DS-Bot/blob/main/CHANGELOG.md) 与 `chemclaw/main` 合入历史：

| 0.2.3 项 | ChemClaw | 状态 | 证据性质 |
| --- | --- | --- | --- |
| 托盘后台 (#500/#549) | `app/src/tray.mjs` + lifecycle | 完整具备（代码） | lifecycle 测；≠ 全平台人工验收 |
| 头像库 (#484/#491) | `avatar-library.js`（#61） | 完整具备（代码） | unit；≠ UI 全路径验收声明 |
| 浏览器交接卡 (#591) | `handoff-card.js` | 完整具备（代码） | `browser-handoff.test.js` |
| 插话未读 (#581/#598) | header + CSS | 完整具备（代码） | 缺专项视觉回归记录 |
| 旧 /btw 可删 (#550/#555) | `btw.js` / side-chat 栈 | 有替代实现 | 需确认旧卡 dismiss |
| 长文/字体/附件/焦点 | 见第 5 项 | 部分具备 | — |
| `list_bot_models` (#568/#575) | host/constants（#60） | 完整具备（代码） | — |
| 默认思考继承 (#525/#586) | #60 | 完整具备（代码） | batch-verify；≠ 实源业务 |
| 角色指令通知 (#535/#584) | #56 栈 | 完整具备（代码） | 同上 |
| 管理员 PASS 提示 (#512/#605) | `groups.js` + cells + 测 | 完整具备（代码） | `tool-cells.test.js` |
| 截图附件/旧段可读等 | #52 栈 | 完整具备（代码） | unit；需真机抽检 |
| 群导入 Session 等可靠性 | 多批已合 | 大体具备 | 可靠性文档；持续抽检 |
| 包版本号 0.2.3 | 仍标 0.2.2 | 版本未对齐 | — |

**总判**：0.2.3 主干能力大多已在 `chemclaw/main` 以独立 PR 适配；缺口集中在第 1–6 项的设置面 / script / 互斥 / 字体搜索 / 排版差分，以及真实 UI / 多平台验收不足。既有 batch-verify 明确：不合 `main`、不冒称实源业务通过。

### 8. Linux 发布资产和多平台更新流程

| 字段 | 结论 |
| --- | --- |
| **上游** | `app/electron-builder.yml`：AppImage + deb；`release.yml` `app-linux` + 资产门禁；AppImage 用 `latest-linux.yml`；deb / mac 指引下载。 |
| **ChemClaw** | 同类目标已有（`executableName: chemclaw`）；Linux 使用 sharp **WASM** 特判（必要分叉）；release 校验含 AppImage / deb / `latest-linux.yml`；发布到 `zoeyzhang233666/chemclaw-bot`。 |
| **状态** | **完整具备（流水线/配置）**，含 ChemClaw 必要分叉 |
| **回归测试** | lifecycle / packed / update 测有；Linux 真机有记录型 commit，**≠** 每次 release 人工跑通。 |
| **需同步** | **基本否**。风险：盲合上游 native sharp / asar 规则会破坏 Linux 图像。保持 WASM 与 ChemClaw 发布源。 |

---

## 差距总表（优先级）

| 优先级 | 缺口 | 状态 | 建议动作 |
| --- | --- | --- | --- |
| P0 | Settings → Browser 授权页 | 缺失 UI | 移植 `browser-settings.js` |
| P0 | Secrets 用途编辑/清空 | 缺失 | host `secret-update` + SecretsPage |
| P0 | 抽屉 ↔ DSH 右栏互斥 | 缺失 | 移植 `right-panel.js` + index 接线 |
| P1 | browser **script** 模式 | 缺失 | 移植 `script.js` 并注册 |
| P1 | `search-patch.mjs` | 缺失 | 适配包名后接入 host |
| P1 | `fonts.css` + 长文 / fold / 附件 CSS | 部分 | 差分合并，保留 ChemClaw 主题 |
| P2 | 顶层 `browser-plugins/` bench | 缺失 | 非主路径；后置 |
| P2 | 版本号 0.2.3 / Release | 未发 | 缺口补齐并验收后再升版 |
| — | Linux 包与更新 | 已具备分叉 | 勿回退 WASM / sharp |
| — | 托盘 / 头像库 / 交接卡 / list_bot_models 等 | 代码已有 | 补真实 UI 抽检，不重复移植 |

---

## 最小改动补齐计划（仍为计划，未执行）

原则：按模块独立分支 / PR；优先复用上游已验证文件；ChemClaw 前缀 / 品牌 / 种子 / 技能库不动；每模块自带回归后再叠下一项；**整批完成前不合 `main`、不发 Release**。

实现起点：从最新 **`chemclaw/main`** 开分支（勿从落后本地 `main` 起步）。

### Batch A — 设置面与安全（P0）

1. 移植 `browser-settings.js`；Settings 增加 `browser` 页（保留 Skill library / About ChemClaw）。
2. `secrets.js`：`secret-update` 支持 `purpose`（含清空）；`secret-card.js` 补 `PurposeEditor` / `SecretsPage`；Settings 增加 `secrets` 页。
3. 测：host secrets 用途清空；设置页冒烟（mock，不用真实密钥）。

### Batch B — 面板互斥（P0）

1. 移植 `right-panel.js` + `right-panel.test.js`。
2. `index.js` 按上游接线 MutationObserver / Session switch window。
3. 测：unit + 桌面 / 窄屏手工：抽屉与文件树 / 子 Agent 列互斥。

### Batch C — 浏览器第三模式（P1）

1. 移植 `browser/script.js`；`browserPlugins = { refs, script, task }`。
2. 配置 / Browser 设置页可选三模式。
3. 测：script 工具注册与拒绝未知名；顶层 bench 包可选后置。

### Batch D — 桌面联网与阅读体验（P1）

1. `search-patch.mjs`（过滤 `chemclaw-bot`）+ host `patchFiles` + 单测。
2. `fonts.css` 注入；styles / fold 与上游 0.2.3 差分合并。
3. 测：search-patch 单测；fold fence 单测；中文长文 / 附件行视觉抽检。

### Batch E — 验收与升版（需显式批准）

1. 对已合入的托盘 / 交接卡 / 头像库等做真实 UI 清单抽检。
2. Linux AppImage 更新 + deb 下载指引回归。
3. 全部通过后一次性升 `0.2.3`、写 Changelog、再谈 Release。

### 推荐推进方式

1. **推荐**：Batch A→B→C→D 独立分支，复用上游文件 + ChemClaw 适配。  
2. **不推荐**：一次性大 diff 对齐整个 `ds-bot` 客户端/host（易误伤 Skill library / APIHub / 品牌）。  
3. **仅文档**：本文已落盘；暂不写代码直至人工批准某一 Batch。

---

## Dry-run 边界声明

本审计执行期间：

- 未修改 `chemclaw/main` / 本地 `main` 产品代码意图交付。
- 未创建或合并补齐用 PR。
- 未执行打包或 Release。
- 未触碰用户真实 `~/.dsh` 或桌面生产数据。

源码对照手段：`git show` / `git grep` / `git cat-file` 对 `origin/main` 与 `chemclaw/main`；不以网页文件列表或同名路径单独定论。
