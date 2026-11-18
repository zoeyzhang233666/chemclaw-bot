# Classic Agent branding

The plugin and the ChemClaw desktop app keep the ChemClaw identity when the user
switches to classic Agent mode. Native DSH session, workspace, composer, model
and permission controls retain their own behavior. The footer opens ChemClaw's
shared settings directly; its Models page puts APIHub first. Native advanced
settings remain accessible through the Harness settings link.

## Public integration

Register the sidebar name and mark and `conversation.hero.brand.mark` outside the
Bot-only surface groups. Use the existing original cloud artwork as inline SVG,
respecting the hero's requested size and class. Keep theme CSS and public
`theme.overrideTokens` active for the plugin lifetime, including the selected
accent's light/dark variants. Remove all registrations and overrides on unload.
Both distribution forms load the same client; no Electron injection or engine
changes are required. Preserve the user's saved theme and appearance choices.
The team return entry reads “ChemClaw专家团” in Chinese and “ChemClaw expert team”
in English. The classic footer launcher reads Settings rather than opening an
account menu, so it contains no sign-in or Feedback action.

Shared component styles and the settings overlay follow the plugin lifetime.
Bot-only native-sidebar layout overrides remain a separate stylesheet, withdrawn
in classic mode. This preserves native New Session, panel navigation and footer
geometry while keeping every ChemClaw settings page styled. The native elevated
surface tokens also follow the selected palette, including native advanced
settings reached from ChemClaw.

## Upstream boundary

DSH 0.2.1-rc.3 exposes the hero mark, workspace and preset slots, but no separate
headline/badge slot. The user requested a complete “ChemClaw” welcome wordmark
and no preview badge. Render that wordmark in the public hero-brand slot and
hide the native title group using plugin-owned theme CSS, following the existing
skin's CSS-module suffix convention. Scope this rule to a hero containing our
wordmark, so unloading ChemClaw restores native presentation. No DOM text
mutation, locale dictionary replacement, private component imports or engine
file changes are involved.

This styling has a compatibility dependency on DSH's `_titleGroup` class suffix.
A future public headline slot should replace that selector. The previous note
overstated the limitation: absence of that slot does not forbid presentation-only
CSS from a normal plugin client entry. Validate title and badge visibility on
every engine upgrade.

References inspected (patterns only; no third-party code or artwork copied):

- Harness official identity package README (`packages/client/ui-brand-official`)
- [Slot hierarchy](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/slots.md)
- [DSH Claude Style hero treatment](https://github.com/Nwflower/dsh-claude-style/blob/master/packages/client/src/theme/hero.css)
- [Dream Skin theme tokens](https://github.com/RevolutionLA/dsh-dream-skin/blob/main/docs/themes-spec.md)
- [Wallpaper Engine](https://github.com/elysia395/dsh-wallpaper-engine)

## Background approval

No new background ships with this change. Original chemical-industry vector
concepts are review-only previews; integrate a background only after the user
selects and confirms one. Do not package a new EXE as part of this source review.

## Verification

- `npm test`: 1,261 passed, one Windows-specific skip, no failures.
- Generated client check and `npm run lint`: passed (existing lint warnings).
- Isolated mock-model Web profile: checked classic entry, Bot/Agent round trip,
  reload, system light/dark appearance, direct settings opening, Escape close,
  540px settings and APIHub-first ordering. The old title and badge are invisible,
  the new wordmark remains visible and native workspace and composer controls
  remain mounted. No browser script errors. Bench and mock processes stopped afterwards.
- The desktop app consumes this same plugin client; a new EXE has not been built
  or installed as part of this change.
