import { BrowserWindow, dialog, ipcMain } from 'electron'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { randomUUID } from 'node:crypto'

export function editLocations(initial, validate, signal, { workspaceReadOnly = false } = {}) {
  return new Promise(resolve => {
    const channel = `chemclaw:locations:${randomUUID()}`
    const win = new BrowserWindow({ width: 780, height: 570, title: 'ChemClaw · 文件夹设置', autoHideMenuBar: true, resizable: true, backgroundColor: '#f5f4ef', webPreferences: { preload: join(dirname(fileURLToPath(import.meta.url)), 'locations-preload.cjs'), sandbox: true, contextIsolation: true, additionalArguments: [`--locations-channel=${channel}`] } })
    let value = { ...initial }
    let accepted = false
    const handle = async (event, request) => {
      if (event.sender !== win.webContents) throw new Error('Unexpected settings window')
      if (request.action === 'read') return { ...value, error: validate(value) ?? '' }
      if (request.action === 'pick') {
        const key = request.key === 'dataDir' ? 'dataDir' : 'workspace'
        if (workspaceReadOnly && key === 'workspace') return { ...value, error: validate(value) ?? '' }
        const result = await dialog.showOpenDialog(win, { defaultPath: value[key], properties: ['openDirectory', 'createDirectory'] })
        if (!result.canceled) value[key] = result.filePaths[0]
      } else if (request.action === 'edit') {
        value = { dataDir: String(request.dataDir ?? '').trim(), workspace: workspaceReadOnly ? initial.workspace : String(request.workspace ?? '').trim() }
      } else if (request.action === 'save' && !validate(value)) { accepted = true; win.close() }
      else if (request.action === 'cancel') win.close()
      return { ...value, error: validate(value) ?? '' }
    }
    ipcMain.handle(channel, handle)
    win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
    win.webContents.on('will-navigate', event => event.preventDefault())
    const abort = () => win.close()
    signal?.addEventListener('abort', abort, { once: true })
    win.once('closed', () => { ipcMain.removeHandler(channel); signal?.removeEventListener('abort', abort); resolve(accepted ? value : initial) })
    const html = `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"><style>body{font:15px 'Microsoft YaHei',sans-serif;background:#f5f4ef;color:#183049;margin:30px;line-height:1.8}input{width:calc(100% - 90px);box-sizing:border-box;font:inherit;padding:8px;border:1px solid #b3c7d6;border-radius:6px}button{font:inherit;padding:8px 15px;margin-left:8px;border:1px solid #b3c7d6;border-radius:6px;background:white;cursor:pointer}label{display:block;margin:18px 0 4px}#error{color:#a12d20;min-height:70px;white-space:pre-wrap}footer{text-align:right}small{color:#60758a}</style><h2>ChemClaw 文件夹设置</h2><p>数据与工作文件分开保存；取消会保留原设置。</p><label for="data">数据目录：对话、密钥与配置</label><input id="data"><button id="pickData">选择</button><label for="work">工作区：Bot 生成和读取的文件</label><input id="work"><button id="pickWork">选择</button><small>建议：数据放在用户目录的 .chemclaw；工作区放在同级 ChemClaw 文件夹。</small><p id="error" role="alert"></p><footer><button id="cancel">取消</button><button id="save">保存设置</button></footer><script>const data=document.getElementById('data'),work=document.getElementById('work'),error=document.getElementById('error'),save=document.getElementById('save');const send=async request=>{const value=await window.locations.request(request);data.value=value.dataDir;work.value=value.workspace;error.textContent=value.error;save.disabled=Boolean(value.error)};document.getElementById('pickData').onclick=()=>send({action:'pick',key:'dataDir'});document.getElementById('pickWork').onclick=()=>send({action:'pick',key:'workspace'});for(const input of [data,work])input.onchange=()=>send({action:'edit',dataDir:data.value,workspace:work.value});save.onclick=()=>send({action:'save'});document.getElementById('cancel').onclick=()=>send({action:'cancel'});work.readOnly=${workspaceReadOnly};document.getElementById('pickWork').disabled=${workspaceReadOnly};send({action:'read'});</script></html>`
    void win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`)
  })
}
