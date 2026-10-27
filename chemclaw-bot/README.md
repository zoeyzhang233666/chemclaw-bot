# ChemClaw

English | [简体中文](README.zh.md)

ChemClaw is an AI team for chemical-industry work: finding customers, sourcing suppliers, checking prices and futures context, studying markets, and turning answers into reports and spreadsheets you can actually use.

Think of it as a ready-made desk of specialists. After install, the sidebar already lists professional Bots and collaboration groups—open one and start chatting.

This folder is the `chemclaw-bot` plugin for official DeepSeek Harness (DSH). The standalone Windows app uses the same plugin capabilities.

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

## Bot browsers

The ChemClaw desktop app gives each Bot a separate browser with saved login state.
Ask it to research a website: it can navigate, read pages, click and fill forms.
Open the Bot's details and choose **Open browser** to follow its work. **Take over**
revokes Bot control; **Give back** permits it again. **Stop** also cancels the Bot's work.
Posting, uploading, downloading and deleting request approval. Complete logins,
payments and captchas yourself when the Bot hands over the browser.

This uses Electron's existing Chromium; no second browser download is required.
Official DSH keeps its existing defaults. Advanced external hosts can set
`browserPlugin: refs` (individual actions) or `task` (one goal), plus
`browserExecutablePath` for a compatible local Chromium. See the
[browser design](../docs/plans/2026-10-27-browser-automation.md).

## License

Apache-2.0. See the repository root `NOTICE`.
