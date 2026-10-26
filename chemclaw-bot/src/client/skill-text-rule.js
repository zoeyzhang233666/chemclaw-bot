import { isUserSkill } from '../shared/skills.js'

// ChemClaw skill IDs are often absent from DSH message skillNames facts, so the
// native `skill` text rule never fires. This set feeds a public userText rule.
const userSkillNames = new Set()

export function syncSkillTextNames(capabilities) {
  userSkillNames.clear()
  for (const item of capabilities ?? []) if (isUserSkill(item)) userSkillNames.add(item.name)
}

// Public uiConversation.userText API: own rule id, never patches DSH.
export function installSkillTextRule(uiConversation) {
  return uiConversation.userText.register({
    id: 'chemclaw-skill',
    order: 19,
    match(text, from) {
      // Native skill rules require whitespace before `/`. Composer drafts often
      // serialize as `中文。/id` with no space, so allow any non-name boundary.
      const tokens = /(?<![\w/-])\/([\w-]+)(?![\w-])/gu
      tokens.lastIndex = from
      for (let token = tokens.exec(text); token !== null; token = tokens.exec(text)) {
        const name = token[1]
        if (userSkillNames.has(name)) {
          return { id: 'chemclaw-skill', start: token.index, end: token.index + token[0].length, data: { name } }
        }
      }
    },
  })
}
