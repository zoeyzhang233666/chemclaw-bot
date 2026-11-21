# ChemClaw GUI Preview Launcher

Date: 2026-10-28. Launcher-only change under `scripts/` and `启动 ChemClaw.cmd`.

## What it does

Double-click `启动 ChemClaw.cmd` opens a small Windows picker:

1. **最新功能集成预览** (default) — checked open PRs on latest main. With only PR #64 (which already contains main), reuses `D:/cursor-chembot-batch2-multisession` instead of copying a new tree.
2. **main** — entry checkout.
3. **Each open PR** — reuses or adds a worktree; never checks out into a dirty foreign worktree.
4. **Other local worktrees** — listed with behind-main / already-in-main hints.

Unchecked PRs are excluded from integration. Credentials are **not** copied into isolated profiles unless you tick the checkbox.

The launcher always runs from the entry checkout scripts. Plugin code is built from the selected source and synced into an app host that already has Electron (prefer selected tree, else reuse `D:/cursor-chembot/app`) so PR worktrees do not need a full `npm ci`.

## Data isolation

| Selection | Profile | Data / workspace |
|---|---|---|
| main | `baseline` | `.chemclaw-dev/data`, `.chemclaw-workspace` |
| PR #N | `pr-N` | `.chemclaw-dev/profiles/pr-N/`, `.chemclaw-workspace-profiles/pr-N/` |
| integration | `integration` | `.chemclaw-dev/profiles/integration/`, `.chemclaw-workspace-profiles/integration/` |

Baseline `state.json`, chats, skills, and secrets stay untouched when previewing PRs.

## CLI compatibility

```bat
启动 ChemClaw.cmd
启动 ChemClaw.cmd --no-picker
启动 ChemClaw.cmd --source D:\cursor-chembot-batch2-multisession
启动 ChemClaw.cmd --info
启动 ChemClaw.cmd --sync-only
```

`--source` / `--info` / `--sync-only` / `--no-picker` skip the GUI. Last picker choice is stored in `.chemclaw-dev/launcher-choice.json`.

## Multi-PR note

Only when more than one independent PR is included does the launcher build `cursor-chembot-preview-integration-next`, validate, then swap to `cursor-chembot-preview-integration`. Conflicts keep the previous good entry.

## macOS GitHub source preview

Double-click `启动 ChemClaw 源码.command` in Finder to select an open PR. The newest open PR appears first. The picker also accepts an arbitrary PR number and can preview the GitHub main branch.

```bash
./启动\ ChemClaw\ 源码.command --list
./启动\ ChemClaw\ 源码.command 162 --info
./启动\ ChemClaw\ 源码.command latest
```

Each launch fetches the selected GitHub ref. The launcher uses detached source checkouts and separate data per PR under `~/Documents/Codex/ChemClaw-source-preview`. Set `CHEMCLAW_PREVIEW_DIR` to use a different preview folder. Node.js 24 and npm are needed for a build. The first launch installs the pinned dependencies and prepares the bundled runtime. Keep the Terminal window open while using the app.
