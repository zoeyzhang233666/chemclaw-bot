# ChemClaw 种子包（基于 DeepSeek-Bot）

把 [DeepSeek-Bot](https://github.com/Fei2411/DeepSeek-Bot) 配成化工垂直团队：业务专岗 + 交付岗 + 质询/流程岗，挂载已跑通的场景 Skills、公司 MCP 模板与公开 API 说明。

**阶段 1**：本目录（能力包 / 种子团队）。**阶段 2**（未做）：桌面端重品牌为 ChemClaw。

## 快速安装

1. 安装并打开 **DeepSeek Bot**（或 dsh + ds-bot 插件），配置好模型。
2. 在本仓库执行：

```bash
node chemclaw/scripts/install-seed.mjs
```

可选：`node chemclaw/scripts/install-seed.mjs --force` 覆盖已有同名 Capability。

3. 脚本会：
   - 生成 `bots/*/IDENTITY.md` 与 playbooks
   - 生成 `seed/capabilities-library.json`
   - 若存在 `%USERPROFILE%\.dsh\bot\state.json`（或 `$DSH_HOME/bot`），合并 MCP/Skill/Pack（**不写密钥**）
   - 写出 [`SETUP_FOR_CHIEF.md`](SETUP_FOR_CHIEF.md)

4. 把 `SETUP_FOR_CHIEF.md` 贴给 Main Bot（或已改名的 ChemClaw），让它创建 Bot 与群聊并 `attach_capability`。
5. **Settings → Connectors** 配置公司数据连接（名称需与模板一致）：
   - `CHEM_DATA_HUB`
   - `CHEM_BIZ_SCOPE`
   - `QCC`

## 团队一览

约 23 个 Bot（见 `seed/bots.json`）+ 5 个群聊：客户开发作战室、采购寻源台、期现研究台、进出口协作、交付工坊。

流程岗：**质询官**（grill-me / grilling）、**流程参谋**（superpowers 子集）。

## Skill 原则

见 [`docs/skill-quality-policy.md`](docs/skill-quality-policy.md)：

- **L1** = `skills/domain`（指向你本机已跑通的场景包）
- **L2** = community process/delivery
- 跟流程不跟像素；强模型可超越 Flash 示例版式

## 目录

| 路径 | 说明 |
|------|------|
| `bots/` | 每岗 IDENTITY / ROUTING / playbooks / skills.lock |
| `capabilities/mcp/` | 公司 MCP URL 模板（`$DSH_SECRET_*`） |
| `skills/domain` | junction → 场景 skills |
| `skills/community/` | grill / superpowers / PPT |
| `scripts/install-seed.mjs` | 一键生成并合并 Capability |
| `SETUP_FOR_CHIEF.md` | 安装后给主控的建队指令 |

## 许可

上游 DeepSeek-Bot 为 Apache-2.0。第三方 skill 见 `skills/index/THIRD_PARTY_SKILLS.md`（含 AGPL 的归藏 PPT，分发时请遵守）。
