# ChemClaw

English | [简体中文](README.zh.md)

ChemClaw is an AI team for chemical-industry work: finding customers, sourcing suppliers, checking prices and futures context, studying markets, and turning answers into reports and spreadsheets you can actually use.

Think of it as a ready-made desk of specialists. After install, the sidebar already lists professional Bots and collaboration groups—open one and start chatting. No need to build a team from scratch.

## What you get

- **50 specialist Bots and 15 collaboration groups** for domestic sales, procurement, trade, industry research, futures-style research, production support, and delivery roles (reports, tables, slides).
- **100+ business skills** for common chemical tasks (downstream leads, supplier checks, market reads, regional maps, price attribution, and more). Each Bot or group shows what it is for, what you should provide, and example prompts.
- **Evidence-minded answers**: can connect to your company data hub and public chemistry / web search. Prices should carry date, spec, region, tax basis and source; gaps are called out instead of inventing numbers.
- **Files, not only chat**: research notes, lead lists and comparisons can be saved as files you preview beside the chat or open on your computer.

## Which file format to ask for

Pick the format that fits the job:

| What you need | Prefer |
|---------------|--------|
| Price trends, filterable tables, charts you can explore in the page | **HTML** (interactive) |
| A client or management slide deck without interactive trends (cards, bullet pages) | **PPT** (including ppt-master / editable PPTX) |
| Row-level detail or a data backing sheet | **Excel as well—required** |

Short rule: **trends or interaction → HTML first; static briefing → PPT is fine; any data workbook → always include Excel.**

## Two ways to use it (pick one)

### 1. Standalone Windows app (best for most people)

1. Download the installer from [GitHub Releases](https://github.com/zoeyzhang233666/chemclaw-bot/releases) (for example `ChemClaw-0.2.0-win-x64.exe`) and install it.
2. Open ChemClaw → **Settings → Models**, paste your model Key (APIHub is listed first: https://apihub.chem-cloud.cn/ , endpoint https://apihub.chem-cloud.cn/v1 ).
3. For company chemical data: **Settings → Connectors → Chemcloud Data Hub**, paste only the Key from https://mcp.chem-cloud.cn/ . Never put Keys in chat.
4. Pick a Bot or group in the sidebar and ask in plain language, e.g. “East China methanol prices over the last month for procurement talks; mark gaps and sources; deliver HTML and Excel.”

Public chemistry lookups and keyless web search usually need no company Key. Trust the Connectors status for whether data services are connected.

**Settings → Skill library** lists the complete skill collection by business category, with Chinese names, purposes and deliverables. Search by task or keyword, then choose **Use** to return to your current conversation with the skill selected. Write your request in the normal composer and send when ready; existing draft text, attachments and regular Bot skills are preserved. In groups, the admin executes it unless you @ another member. **Install a skill** accepts ZIP files, folders, SKILL.md and public GitHub links, preserves scripts and templates, and lets you choose a group before installation. Tool services and credentials remain in **Connectors**.

### 2. Plugin for official DeepSeek Harness (DSH) Desktop

If you already use official DSH:

1. Git must be installed on your PC.
2. In DSH go to **Plugins → Add plugin** and enter:

   ```text
   github:zoeyzhang233666/chemclaw-bot#v0.2.0&path:/chemclaw-bot
   ```

3. Install, enable, and restart if asked. You can also install from a `chemclaw-bot-0.2.0.tgz` path on the same Release.
4. Configure model and connector Keys the same way, then start from the sidebar.

Existing chats and custom roles stay; missing presets are filled in without wiping your work.

## Easy first prompts

- “Find domestic producers for this product and give me a filterable list.”
- “East China soda ash last three months for negotiation—HTML plus Excel.”
- “Turn this conclusion into a client PPT (no interactive charts); attach Excel for the numbers.”
- “Why did methanol move recently? Separate evidence from unknowns.”

## Please keep in mind

- ChemClaw **helps research and packaging**—it does not auto-trade or control plants.
- Sample prices, customers and maps in examples are demos, not live business data.
- Model Keys and company data Keys are different: Models page vs Connectors page.

## License

Apache-2.0. Based on Fei2411’s DS Bot and DeepSeek Harness; see `NOTICE`. Cloud and lobster artwork is original.
