# Classic Agent branding

The plugin and the ChemClaw desktop app keep the ChemClaw identity when the user
switches to classic Agent mode. Native DSH session, workspace, composer, model,
permission and settings controls retain their own behavior.

## Public integration

Register the sidebar name and mark and `conversation.hero.brand.mark` outside the
Bot-only surface groups. Use the existing original cloud artwork as inline SVG,
respecting the hero's requested size and class. Keep theme CSS and public
`theme.overrideTokens` active for the plugin lifetime, including the selected
accent's light/dark variants. Remove all registrations and overrides on unload.
Both distribution forms load the same client; no Electron injection or engine
changes are required. Preserve the user's saved theme and appearance choices.

## Upstream boundary

DSH 0.2.1-rc.3 exposes the hero mark, workspace and preset slots, but no slot for
the headline or preview badge. The locale registry rejects duplicate namespace
dictionaries. Do not replace the `conversation` dictionary, edit engine files,
mutate host DOM, hide the headline with CSS, or import private hero components.
Replacing “探索未知之境” and the preview badge needs a public headline/badge seam
from DSH. This portion remains blocked pending that API.

References inspected (patterns only; no third-party code or artwork copied):

- [Official branding contract](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/client/ui-brand-official/README.md)
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
  reload, and system light/dark appearance. Both cloud SVGs and the wordmark
  remain visible; native workspace/composer controls remain mounted. No browser
  script errors. Bench and mock processes stopped after verification.
- The desktop app consumes this same plugin client; a new EXE has not been built
  or installed as part of this change.
