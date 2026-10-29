# ChemClaw

English | [简体中文](README.zh.md)

ChemClaw is an AI team for chemical-industry work: finding customers, sourcing suppliers, checking prices and futures context, studying markets, and turning answers into reports and spreadsheets you can actually use.

Think of it as a ready-made desk of specialists. After install, the sidebar already lists professional Bots and collaboration groups—open one and start chatting.

This folder is the `chemclaw-bot` plugin for official DeepSeek Harness (DSH). The standalone Windows app uses the same plugin capabilities.

Inline replies support seven additional chart types: scatter, radar, heatmap, funnel, treemap, Sankey and gauge. Their renderer loads locally on demand; the existing five SVG charts keep their lightweight path. Turn off Advanced charts in Appearance to see their full data as tables.

The bundle also loads the complete upstream [GenUI plugin](https://github.com/omdsh-dev/dsh-genui), pinned to 0.15.0: timelines, steps, diagrams/Mermaid, ECharts, function plots, 3D scenes, searchable tables, forms and other components. Bot and group replies use inline `dsh-ui` fences with ChemClaw theme colors and conversation-scoped actions; the original `show_view` views remain compatible. Bots choose a view from the answer's structure without requiring a component name. Local table filtering/sorting and controls without actions need no model round trip. Native `/panel` remains a native DSH conversation feature; use inline output in Bot/group replies. The Advanced charts preference controls ChemClaw's seven additional charts, independently of GenUI. For an existing `link:` install, refresh/reinstall that bundle in DSH's plugin manager so its new dependency and bundle patch are applied, then restart/reload DSH; rebuilding `client.js` alone does not install a new plugin dependency.

Every user-facing final answer defaults to an inline view, including explanations and short confirmations: existing charts/cards first, GenUI for richer content. This global delivery rule automatically covers existing, imported and future skills; their HTML/file reports supplement the chat view. An explicit text-only request overrides it. A documented DSH stop-boundary check adds at most one same-turn reminder if a final answer has no view; answers that already include a view add no correction call. Internal delegation, progress, cancelled turns and subagents are excluded. This reduces missed views but does not guarantee model compliance or constant latency. Native Agent mode can render the bundled GenUI components and panel; ChemClaw's `show_view` tool remains scoped to Bot chats.

## What you get

- **50 specialist Bots and 15 collaboration groups** for sales, procurement, trade, industry and futures-style research, production support, and delivery roles.
- **100+ business skills** for common chemical tasks. Each Bot or group shows purpose, inputs and example prompts.
- **Evidence-minded answers** via company data hub and public chemistry / web search, with sources and gaps called out.
- **Files, not only chat**—preview beside the conversation or open on your computer.

## Which file format to ask for

| What you need | Prefer |
|---------------|--------|
| Price trends, filterable tables, in-page charts | **HTML** |
| Slide deck without interactive trends | **PPT** (including ppt-master) |
| Row-level detail or a data backing sheet | **Excel as well—required** |

**Trends or interaction → HTML first; static briefing → PPT is fine; any data workbook → always include Excel.**

## Install this plugin

In official DSH Desktop: **Plugins → Add plugin** (Git required on your PC):

```text
github:zoeyzhang233666/chemclaw-bot#v0.2.0&path:/chemclaw-bot
```

Install, enable, and restart if asked. Or use the full path to `chemclaw-bot-0.2.0.tgz` from the Release.

For the standalone app, models, connectors and first prompts, see the repository root [README.md](../README.md).

## Side chats

Use `/side <question>` in a Bot chat, or choose **Side chat** in the details menu,
to ask about progress without interrupting its main task. Follow-ups stay in a
separate tab and cannot run tools. Closing the panel keeps the history; closing
a side-chat tab deletes that chat.

## Bot browsers

The ChemClaw desktop app gives each Bot a separate browser with saved login state.
Ask it to research a website: it can navigate, read pages, click and fill forms.
Open the Bot's details and choose **Open browser** to follow its work. **Take over**
revokes Bot control; **Give back** permits it again. **Stop** also cancels the Bot's work.
Posting, uploading, downloading and deleting request approval. Complete logins,
payments and captchas yourself when the Bot hands over the browser.

This uses Electron's existing Chromium; no second browser download is required.
Official DSH keeps its existing defaults. Advanced external hosts can set
`browserPlugin: refs` (individual actions), `script` (one JavaScript body), or
`task` (one goal), plus `browserExecutablePath` for a compatible local Chromium.
See the [browser design](../docs/plans/2026-10-27-browser-automation.md).

## Market data environment

Release installers and plugin packages bundle private Python and AKShare archives.
First launch unpacks the matching platform archive locally; users do not install
Python or download runtime dependencies. Market queries still need access to the
data source. Source installations without an archive prepare the market components
automatically. `npm run pack:dist` prepares the current platform's archive, and
desktop packaging does the same. The release pipeline includes all supported
platform archives in the plugin package.

Local molecule analysis, advanced statistics and scientific plotting libraries are
optional and are not installed by default. Huagongshe and PubChem APIs do not need
these libraries. Interactive previews follow the host's sandbox settings.

## License

Apache-2.0. See the repository root `NOTICE`.

General settings offer bubble or flat messages, independent bubble/text widths, and an optional thinking display. On touch screens, tap a message to open its actions.
