// The first start: where the app keeps its data and the Bots' files, and whether it copies the
// Bot team of the user's own DSH. The answers are kept in the app's own data.
import { app, dialog } from 'electron'
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'
import { real } from './copy-tree.mjs'
import { findTeam, newerSessions, teamInUse, userDshHome, within } from './import.mjs'
import { installFolder } from './move-data.mjs'
import { editLocations } from './locations-dialog.mjs'

const TEXT = {
  en: {
    welcome: 'Welcome to ChemClaw',
    places: (data, workspace) => `Data folder:\n${data}\n\nTeam workspace (files Bots read/write):\n${workspace}\n\nThese must be two separate folders — neither inside the other.`,
    start: 'Start', change: 'Change folders…',
    pickData: 'ChemClaw data folder (chats, keys, settings)',
    pickWorkspace: 'Team workspace folder (files for Bots — not inside the data folder)',
    dataInWorkspace: 'The data folder cannot be inside the team workspace (or the same folder).\n\nPick two separate folders, for example:\n• Data:  C:\\Users\\You\\.chemclaw\n• Workspace:  C:\\Users\\You\\ChemClaw',
    workspaceInData: 'The team workspace cannot be inside the data folder (or the same folder).\n\nPick two separate folders, for example:\n• Data:  C:\\Users\\You\\.chemclaw\n• Workspace:  C:\\Users\\You\\ChemClaw',
    inDsh: home => `Choose a folder outside the DeepSeek Harness data (${home}).`,
    inProgram: 'Choose a folder outside the program folder: uninstalling removes it.',
    pickMove: 'New folder for ChemClaw data',
    moveDrive: 'Choose a folder, not a whole drive.',
    moveNested: 'Choose a folder outside the current data folder.',
    moveWorkspace: 'The data folder and the team workspace cannot hold each other.',
    moveNotEmpty: 'Choose an empty folder or a new one.',
    moveConfirm: to => `Move ChemClaw's data to ${to}?`,
    moveDetail: from => `ChemClaw copies its data there and starts again. ${from} stays as it is; you can delete it once everything works.`,
    move: 'Move and restart', cancel: 'Cancel',
    moving: 'Copying ChemClaw\'s data…',
    starting: 'Starting ChemClaw…',
    moveInUse: 'Another DeepSeek Harness is using this data, so it was not moved. Close it, then try again.',
    moveFailed: message => `The data could not be copied: ${message}\n\nChemClaw goes on with its data where it was.`,
    found: (bots, rooms) => `DeepSeek Harness has a Bot team: ${bots} Bot${bots === 1 ? '' : 's'}${rooms > 0 ? `, ${rooms} group${rooms === 1 ? '' : 's'}` : ''}. Copy it into ChemClaw?`,
    foundDetail: home => `The copy takes the Bots, groups, memories, chats, files, keys and model settings. Nothing in ${home} changes, and the two teams do not stay in step.`,
    copy: 'Copy', skip: 'Do not copy',
    inUse: 'DeepSeek Harness is using this team. Close it, then try again.', retry: 'Try again',
    newer: count => `${count} chat${count === 1 ? ' was' : 's were'} written by a newer DeepSeek Harness than this ChemClaw can read. Update ChemClaw, then start it again to copy the team.`,
    quit: 'Quit', startEmpty: 'Start without the team',
    whichModels: 'Which model settings should ChemClaw use?',
    failed: message => `The team could not be copied: ${message}\n\nChemClaw starts with a new team. The team in DeepSeek Harness is unchanged.`,
    notStarted: 'ChemClaw could not start.',
    tryAgain: 'Choose folders again',
  },
  zh: {
    welcome: '欢迎使用 ChemClaw',
    places: (data, workspace) => `数据目录（对话、密钥、配置）：\n${data}\n\n团队工作文件夹（Bot 读写文件用）：\n${workspace}\n\n必须是两个互不包含的文件夹。`,
    start: '开始使用', change: '更改文件夹…',
    pickData: '选择 ChemClaw 数据目录（对话 / 密钥 / 配置）',
    pickWorkspace: '选择团队工作文件夹（Bot 读写文件；不能放在数据目录里）',
    dataInWorkspace: '数据目录不能放在团队工作文件夹里面（也不能选成同一个文件夹）。\n\n请选两个互不包含的文件夹，例如：\n• 数据：C:\\Users\\你\\.chemclaw\n• 工作区：C:\\Users\\你\\ChemClaw',
    workspaceInData: '团队工作文件夹不能放在数据目录里面（也不能选成同一个文件夹）。\n\n请选两个互不包含的文件夹，例如：\n• 数据：C:\\Users\\你\\.chemclaw\n• 工作区：C:\\Users\\你\\ChemClaw',
    inDsh: home => `请选择 DeepSeek Harness 数据（${home}）以外的文件夹。`,
    inProgram: '请选择程序文件夹以外的位置：卸载时会删掉程序文件夹。',
    pickMove: '选择 ChemClaw 数据的新文件夹',
    moveDrive: '请选择一个文件夹，不要选整个磁盘。',
    moveNested: '请选择现在的数据文件夹以外的位置。',
    moveWorkspace: '数据文件夹和总工作区不能互相包含。',
    moveNotEmpty: '请选择一个空文件夹，或者新建一个。',
    moveConfirm: to => `把 ChemClaw 的数据移到 ${to} 吗？`,
    moveDetail: from => `ChemClaw 会把数据复制过去，然后重新启动。${from} 会原样保留，确认一切正常后可以自己删掉。`,
    move: '移动并重启', cancel: '取消',
    moving: '正在复制 ChemClaw 的数据…',
    starting: '正在启动 ChemClaw…',
    moveInUse: '另一个 DeepSeek Harness 正在使用这份数据，所以没有移动。请先关掉它，再重试。',
    moveFailed: message => `数据没有复制成功：${message}\n\nChemClaw 会继续使用原来位置的数据。`,
    found: (bots, rooms) => `DeepSeek Harness 里有一个 Bot 团队：${bots} 个 Bot${rooms > 0 ? `、${rooms} 个群` : ''}。要复制到 ChemClaw 吗？`,
    foundDetail: home => `会复制 Bot、群、记忆、对话、文件、密钥和模型设置。${home} 里的内容不会改变；复制以后两个团队各自独立。`,
    copy: '复制', skip: '不复制',
    inUse: 'DeepSeek Harness 正在使用这个团队。请先关掉它，再重试。', retry: '重试',
    newer: count => `有 ${count} 段对话是更新版本的 DeepSeek Harness 写的，这个版本的 ChemClaw 读不了。请先更新 ChemClaw，再打开它来复制团队。`,
    quit: '退出', startEmpty: '不带团队开始',
    whichModels: 'ChemClaw 用哪一份模型设置？',
    failed: message => `团队没有复制成功：${message}\n\nChemClaw 会用一个新团队开始。DeepSeek Harness 里的团队没有变化。`,
    notStarted: 'ChemClaw 没能启动。',
    tryAgain: '重新选择文件夹',
  },
}
export const localeText = table => (app.getLocale().toLowerCase().startsWith('zh') ? table.zh : table.en)
export const text = () => localeText(TEXT)

const PROFILE_NAMES = { desktop: 'DSH Desktop', web: 'DSH Web' }
const locationsFile = () => join(app.getPath('userData'), 'locations.json')

// A quit request while a first-run dialog is open stops the first run right after that dialog.
class Quit extends Error {}

async function ask(options, signal) {
  const { response } = await dialog.showMessageBox({ title: 'ChemClaw', noLink: true, ...options, signal })
  // A quit that arrived while a synchronous macOS box was open gets to run first.
  await new Promise(resolve => setImmediate(resolve))
  if (signal.aborted) throw new Quit()
  return response
}

async function pick(title, current, signal) {
  const { canceled, filePaths } = await dialog.showOpenDialog({ title, defaultPath: existsSync(current) ? current : dirname(current), properties: ['openDirectory', 'createDirectory', 'promptToCreate'] })
  await new Promise(resolve => setImmediate(resolve))
  if (signal.aborted) throw new Quit()
  return canceled ? current : filePaths[0]
}

export const programFolder = () => installFolder(app.getPath('exe'))

function placeProblem(t, dataDir, workspace) {
  if (!dataDir || !workspace || !/^(?:[A-Za-z]:[\\/]|\/|\\\\)/u.test(dataDir) || !/^(?:[A-Za-z]:[\\/]|\/|\\\\)/u.test(workspace)) return '请选择两个完整的文件夹路径。'
  const data = real(dataDir)
  const work = real(workspace)
  const dsh = real(userDshHome())
  const program = real(programFolder())
  if (within(data, work)) return t.dataInWorkspace
  if (within(work, data)) return t.workspaceInData
  for (const path of [data, work]) {
    if (within(path, dsh) || within(dsh, path)) return t.inDsh(userDshHome())
    if (app.isPackaged && within(path, program)) return t.inProgram
  }
  return undefined
}

/** Pick one folder; if the pair would be invalid, show why and ask again. */
async function pickUntilOk(t, which, dataDir, workspace, signal) {
  return editLocations({ dataDir, workspace }, value => placeProblem(t, value.dataDir, value.workspace), signal)
}

function hasTeam(dataDir) {
  try {
    const chem = join(dataDir, 'chemclaw', 'state.json')
    const legacy = join(dataDir, 'bot', 'state.json')
    const path = existsSync(chem) ? chem : legacy
    return Object.keys(JSON.parse(readFileSync(path, 'utf8')).bots ?? {}).length > 0
  } catch {
    return false
  }
}

async function offerImport(t, dataDir, signal) {
  const from = userDshHome()
  let found
  try {
    found = hasTeam(dataDir) ? undefined : findTeam(from)
  } catch (error) {
    console.error(error)
  }
  if (found === undefined) return undefined
  if (await ask({ type: 'question', message: t.found(found.bots, found.rooms), detail: t.foundDetail(from), buttons: [t.copy, t.skip], defaultId: 0, cancelId: 1 }, signal) === 1) return undefined
  while (teamInUse(from)) {
    if (await ask({ type: 'warning', message: t.inUse, buttons: [t.retry, t.skip], defaultId: 0, cancelId: 1 }, signal) === 1) return undefined
  }
  const newer = newerSessions(from, found.team)
  if (newer.length > 0) {
    if (await ask({ type: 'warning', message: t.newer(newer.length), buttons: [t.quit, t.startEmpty], defaultId: 0, cancelId: 0 }, signal) === 0) return { quit: true }
    return undefined
  }
  const { profiles } = found
  const profile = profiles.length < 2 ? profiles[0]?.name
    : profiles[await ask({ type: 'question', message: t.whichModels, buttons: profiles.map(entry => PROFILE_NAMES[entry.name] ?? entry.name), defaultId: 0, cancelId: 0 }, signal)].name
  return { from, profile }
}

/** Write the chosen places once the first run is finished; quitting before that asks again. */
export function saveLocations({ dataDir, workspace }) {
  const file = locationsFile()
  mkdirSync(dirname(file), { recursive: true })
  // A write that fails half way leaves the places that were there.
  writeFileSync(`${file}.tmp`, `${JSON.stringify({ dataDir, workspace }, null, 2)}\n`)
  renameSync(`${file}.tmp`, file)
}

/**
 * Where the app keeps its data and the Bots' files, asked at the first start.
 * A run on throwaway folders (DS_BOT_HOME, for development and tests) asks nothing and copies nothing.
 * @returns {Promise<{ dataDir: string, workspace?: string, import?: { from: string, profile?: string }, quit?: true }>}
 */
export async function chooseLocations(signal) {
  if (process.env.DS_BOT_HOME) return { dataDir: process.env.DS_BOT_HOME, workspace: process.env.DS_BOT_WORKSPACE || undefined }
  const file = locationsFile()
  if (existsSync(file)) {
    const saved = JSON.parse(readFileSync(file, 'utf8'))
    return { dataDir: saved.dataDir, workspace: saved.workspace }
  }
  const t = text()
  let dataDir = join(homedir(), '.chemclaw')
  let workspace = join(homedir(), 'ChemClaw')
  let forceChange = process.env.CHEMCLAW_SETUP === '1'
  try {
    for (;;) {
      const choice = forceChange
        ? 1
        : 0
      forceChange = false
      if (choice === 2) return { quit: true }
      if (choice === 1) {
        ;({ dataDir, workspace } = await pickUntilOk(t, 'data', dataDir, workspace, signal))
        continue
      }
      const problem = placeProblem(t, dataDir, workspace)
      if (problem === undefined) break
      const again = await ask({ type: 'warning', message: problem, buttons: [t.tryAgain, t.quit], defaultId: 0, cancelId: 1 }, signal)
      if (again === 1) return { quit: true }
      forceChange = true
    }
    const imported = await offerImport(t, dataDir, signal)
    if (imported?.quit) return { quit: true }
    if (imported !== undefined) return { dataDir, workspace, import: imported }
  } catch (error) {
    if (error instanceof Quit) return { quit: true }
    throw error
  }
  // There is nothing to copy, so the first run ends with the chosen places.
  saveLocations({ dataDir, workspace })
  return { dataDir, workspace }
}
