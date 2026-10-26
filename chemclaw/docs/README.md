# ChemClaw

English | [简体中文](README.zh.md)

ChemClaw assists chemical production research, sales, procurement, trade, industry research and futures research. Its independent desktop application and official DeepSeek Harness (DSH) plugin share `chemclaw-bot`, without patching DSH.

It includes **50 roles, 15 collaboration scenarios and 108 complete business Skills**, with chemistry, statistics, planning, review and document helpers. All 50 Bots and 15 collaboration groups are created automatically and shown in expanded sidebar categories. Open Bots or Group chats to see purposes, members, inputs and examples, then start a conversation directly. Existing teams receive missing presets without duplicating conversations or replacing custom instructions.

## Use

- Windows: install `app/dist-pack/ChemClaw-0.2.0-win-x64.exe`, then configure your model.
- Official DSH Desktop **0.2.1-rc.3**: Plugins → Add plugin → enter the full path to `chemclaw-bot-0.2.0.tgz`, install and enable. Restart if requested.
- Retired manual seed scripts are unnecessary. Existing teams, chats and custom roles remain intact.

New installations use Simplified Chinese and the paper theme; English remains available. Independent app data defaults to `~/.chemclaw`; work files go in `~/ChemClaw`. Advanced directory editing validates both paths together. Import reads the user's DSH data without writing to it. Updates remain disabled until a ChemClaw feed is configured.

## Preview source without rebuilding the EXE

Install **Node.js 24 LTS**, then double-click **启动 ChemClaw.cmd** at the repository root. It installs dependencies when needed, builds the client, synchronizes the plugin and starts the GUI. Initial setup requires network access.

**开发 ChemClaw.cmd** watches edits and restarts the Host. Development data lives in `.chemclaw-dev`, work files in `.chemclaw-workspace`, separate from the installed application. Let active tasks finish before editing.

With dependencies installed:

```powershell
cd D:\cursor-chembot\app
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
npm start
```

This short command does not synchronize plugin edits; use the root launcher for daily development.

## Connectors and deliverables

In ChemClaw Settings → Connectors, connect **Chemical Data Hub** by pasting a Key from [mcp.chem-cloud.cn](https://mcp.chem-cloud.cn/). Its endpoint is fixed at `https://datahub.chem-cloud.cn/mcp`. Connected means MCP initialization and tool discovery succeeded. Keep credentials out of chat.

Huagongshe public queries are anonymous. PubChem, OPSIN and Chinese/English Wikipedia need no key. Historical daily futures data needs the managed Python environment installed from Connectors (Python 3.11+). Sources, timestamps, conventions and gaps remain explicit; free data is not promised to be real-time. Advanced setup accepts HTTPS `mcpServers` JSON. Incomplete optional services are not automatically connected.

DSH `present` cards preview HTML alongside chat and offer native opening/reveal. Markdown file links are clickable. Interactive HTML follows the host sandbox preference; Connectors provides an enable-preview entry. Moved/deleted files show errors.

Bundled libraries and `chem_deliver` generate ordinary HTML, XLSX, PPTX, DOCX and PDF without Python. Scientific tasks can install optional managed dependencies. Converting existing Office files or recalculating workbooks additionally requires LibreOffice. Examples are references; models may improve analysis and layout.

See `chemclaw/docs/使用指南.md`, `chemclaw/docs/验收记录.md` and `docs/plans/2026-10-22-chemclaw.md` in the repository.

## Checks

In `chemclaw-bot`: `npm ci`, `npm run harness`, `npm run build`, `npm test`, `node scripts/build-client.mjs --check`, `npm run lint`. Windows Host smoke: `node dev/bench-windows.mjs <fresh-name>`. In `app`: `npm test`, `npm run dist`.

Automated checks use isolated data and a mock model; they do not evaluate research quality. Production features assist research and analysis; futures features cover research and backtesting. Users configure their models.

## License

Apache-2.0. Based on Fei2411's DS Bot and DeepSeek Harness; see `NOTICE` for upstream attribution and third-party licenses. Cloud and lobster artwork is original. Retired AGPL presentation Skills are excluded. Community references are pinned and retain their licenses; software-development ceremonies are not imposed on business tasks.


Current review: the UI changes run from source. A new EXE will be built only after the user explicitly confirms the reviewed interface. An older EXE in dist-pack is not this revision.

Models: ChemClaw Settings → Models includes APIHub first. Get a Key at https://apihub.chem-cloud.cn/; the fixed API endpoint is https://apihub.chem-cloud.cn/v1. Paste the Key, fetch models and choose the models to save. Other providers remain available.

Keyless web search is supplied by dsh-free-search 0.9.12, including fallback engines. Search results carry sources; one failed engine does not establish that all networking is unavailable. Huagongshe anonymous chemistry capabilities are listed under Public research data; optional authorization is folded separately.
