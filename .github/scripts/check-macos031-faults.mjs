import assert from 'node:assert/strict'
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { spawn, spawnSync } from 'node:child_process'
import { homedir } from 'node:os'
import { basename, dirname, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { setTimeout as sleep } from 'node:timers/promises'
import { inside, crashSignature } from './check-macos-helper-path.mjs'

const modes = new Set(['create', 'html-frame', 'cdp', 'idle'])

// Runs only in the copied checker. The inspector observes the official dialog and
// CDP endpoint; it never supplies a path check, shutdown or app.quit implementation.
export async function observeMain() {
  const config = JSON.parse(process.env.CHEMCLAW_NATIVE_CONFIG)
  const response = await fetch('http://127.0.0.1:' + config.inspectPort + '/json/list')
  const target = (await response.json()).find(target => target.webSocketDebuggerUrl)
  if (!target) throw new Error('No owned main-process inspector')
  const socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((done, reject) => { socket.addEventListener('open', done, { once: true }); socket.addEventListener('error', reject, { once: true }) })
  const expression = '(' + (async config => {
    const require = process.getBuiltinModule('module').createRequire(process.execPath)
    const electron = require('electron')
    const fs = require('node:fs')
    const cp = require('node:child_process')
    const hosts = () => cp.execFileSync('/bin/ps', ['-axo', 'pid=,ppid=,command='], { encoding: 'utf8' }).split('\n').flatMap(line => {
      const match = /^\s*(\d+)\s+(\d+)\s+(.*)$/.exec(line)
      return match && Number(match[2]) === process.pid && /\/host\.mjs(?:\s|$)/.test(match[3]) ? [Number(match[1])] : []
    })
    const state = { pid: process.pid, hostPids: hosts(), notices: [] }
    if (!state.hostPids.length) throw new Error('No owned DSH Host before experiment')
    globalThis.__chemclawNativeAudit = state
    fs.writeFileSync(config.notice, JSON.stringify(state, null, 2))
    const original = electron.dialog.showMessageBox.bind(electron.dialog)
    electron.dialog.showMessageBox = async (...args) => {
      const options = args.at(-1)
      if (!/ChemClaw was moved or replaced|ChemClaw 在运行期间被移动或替换/.test(options?.message || '')) return original(...args)
      const remaining = state.hostPids.filter(pid => { try { process.kill(pid, 0); return true } catch { return false } })
      state.notices.push({ message: options.message, remainingHostPids: remaining, at: Date.now() })
      fs.writeFileSync(config.notice, JSON.stringify(state, null, 2))
      return { response: 0 }
    }
    const { BotViews } = require(electron.app.getAppPath() + '/src/bot-views.mjs')
    const endpoint = BotViews.prototype.endpoint
    BotViews.prototype.endpoint = async function(...args) {
      const value = await endpoint.apply(this, args)
      globalThis.__chemclawNativeEndpoint = value
      return value
    }
    return { pid: state.pid, hostPids: state.hostPids }
  }).toString() + ')(' + JSON.stringify(config) + ')'
  try {
    const result = await new Promise((done, reject) => {
      const timer = setTimeout(() => reject(new Error('Main inspector observer timed out')), 15000)
      socket.addEventListener('message', event => {
        const message = JSON.parse(String(event.data))
        if (message.id !== 1) return
        clearTimeout(timer)
        if (message.error || message.result.exceptionDetails) reject(new Error('Main inspector observer failed: ' + JSON.stringify(message.error || message.result.exceptionDetails)))
        else done(message.result.result.value)
      })
      socket.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression, awaitPromise: true, returnByValue: true } }))
    })
    if (!result.hostPids?.length) throw new Error('Observer did not identify DSH')
    console.log('native-path-audit: observer armed for PID ' + result.pid)
  } finally { socket.close(); await new Promise(done => setTimeout(done, 100)) }
}

export async function faultProbe(evaluate, port) {
  const fs = await import('node:fs')
  const { randomUUID } = await import('node:crypto')
  const { setTimeout: pause } = await import('node:timers/promises')
  const config = JSON.parse(process.env.CHEMCLAW_NATIVE_CONFIG)
  const state = { mode: config.mode, stage: 'baseline' }
  const save = () => fs.writeFileSync(config.checkpoint, JSON.stringify(state, null, 2))
  const call = (endpoint, payload) => evaluate('fetch("api/bot",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(' + JSON.stringify({endpoint,payload}) + ')}).then(r=>r.json()).then(r=>{if(!r.ok)throw Error(r.error.message);return r.value})')
  const team = await call('state', {})
  const bot = team.bots.find(bot => bot.id === team.mainBotId)
  if (!bot) throw new Error('No synthetic main Bot')
  const chat = JSON.stringify(await call('chat', { botId: bot.id }))
  if (!chat.includes('收到：packaged app check')) throw new Error('Synthetic history baseline missing')
  state.history = { botId: bot.id, sessionId: bot.sessionId, bots: team.bots.length, reply: '收到：packaged app check' }
  save()
  let cdp, next = 0
  const request = (method, params = {}, sessionId) => new Promise((done, reject) => {
    const id = ++next
    const timer = setTimeout(() => { cdp.removeEventListener('message', receive); reject(new Error('Owned bridge request timed out: ' + method)) }, 15000)
    const receive = event => {
      const message = JSON.parse(String(event.data))
      if (message.id !== id) return
      clearTimeout(timer); cdp.removeEventListener('message', receive)
      if (message.error) reject(new Error(message.error.message)); else done(message.result)
    }
    cdp.addEventListener('message', receive)
    cdp.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }))
  })
  let sessionId
  if (config.mode === 'cdp') {
    // Read the transient endpoint only into memory; never log or persist its token.
    const targets = await (await fetch('http://127.0.0.1:' + config.inspectPort + '/json/list')).json()
    const socket = new WebSocket(targets[0].webSocketDebuggerUrl)
    await new Promise((done, reject) => { socket.addEventListener('open', done, { once: true }); socket.addEventListener('error', reject, { once: true }) })
    const endpoint = await new Promise((done, reject) => {
      const timer = setTimeout(() => reject(new Error('No recorded bridge endpoint')),15000)
      socket.addEventListener('message', event => {
        const message=JSON.parse(String(event.data)); if(message.id!==1)return; clearTimeout(timer)
        if(message.result?.result?.value)done(message.result.result.value);else reject(new Error('No recorded bridge endpoint'))
      })
      socket.send(JSON.stringify({id:1,method:'Runtime.evaluate',params:{expression:'globalThis.__chemclawNativeEndpoint',returnByValue:true}}))
    }).finally(() => socket.close())
    cdp = new WebSocket(endpoint)
    await new Promise((done, reject) => { cdp.addEventListener('open', done, { once: true }); cdp.addEventListener('error', reject, { once: true }) })
    const targetsBefore = await request('Target.getTargets')
    const target = targetsBefore.targetInfos.find(target => target.type === 'page')
    if (!target) throw new Error('No existing Bot browser target')
    sessionId = (await request('Target.attachToTarget',{targetId:target.targetId,flatten:true})).sessionId
    await pause(100)
  }
  if (!fs.existsSync(config.appFrom) || fs.existsSync(config.appTo)) throw new Error('Unexpected move fixture')
  fs.renameSync(config.appFrom, config.appTo)
  state.stage = 'fault-injected'; save()
  try {
    if (config.mode === 'create') await evaluate('window.dsBotApp.browser.views.create(' + [bot.id,randomUUID(),'http://localhost:'+port+'/after-move'].map(value => JSON.stringify(value)).join(',') + ')')
    if (config.mode === 'html-frame') await evaluate('(()=>{const frame=document.querySelector("iframe[data-html-preview]");if(!frame)throw Error("No tested HTML iframe");frame.src=URL.createObjectURL(new Blob(["<!doctype html><h1>after move</h1>"],{type:"text/html"}))})()')
    if (config.mode === 'cdp') await request('Page.navigate', { url:'http://localhost:'+port+'/after-move' }, sessionId)
  } catch (error) { state.operationError = String(error.message).slice(0,500) }
  finally { cdp?.close(); save() }
  const end = Date.now() + 30000
  while (Date.now() < end && !fs.existsSync(config.exited)) await pause(100)
  state.stage = fs.existsSync(config.exited) ? 'owned-main-exited' : 'exit-not-observed'; save()
  throw new Error('native-path-audit: fault phase ended; inspect the strict shutdown oracle')
}

export async function reopenHistory(cdp) {
  const fs = await import('node:fs')
  const config = JSON.parse(process.env.CHEMCLAW_NATIVE_CONFIG)
  const baseline = JSON.parse(fs.readFileSync(config.baseline)).history
  const evaluate = async expression => {
    const answer = await cdp.call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})
    if(answer.exceptionDetails)throw new Error('Reopen evaluation failed')
    return answer.result.value
  }
  const end = Date.now()+90000
  let restored
  while(Date.now()<end){
    try {
      const team = await evaluate('fetch("api/bot",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({endpoint:"state",payload:{}})}).then(r=>r.json()).then(r=>r.value)')
      const bot = team?.bots.find(bot=>bot.id===baseline.botId)
      if(!bot || bot.sessionId!==baseline.sessionId || team.bots.length!==baseline.bots)throw new Error('Saved Bot/session identity changed')
      const chat = await evaluate('fetch("api/bot",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({endpoint:"chat",payload:{botId:'+JSON.stringify(baseline.botId)+'}})}).then(r=>r.json()).then(r=>r.value)')
      if(!JSON.stringify(chat).includes(baseline.reply))throw new Error('Saved reply missing')
      await evaluate('document.querySelector('+JSON.stringify('[data-bot-id="'+baseline.botId+'"]')+').click()')
      if(!await evaluate('document.body.innerText.includes('+JSON.stringify(baseline.reply)+')'))throw new Error('Saved reply not visible')
      restored={sameBot:true,sameSession:true,sameBotCount:true,savedReplyVisible:true}; break
    } catch { await new Promise(done=>setTimeout(done,250)) }
  }
  if(!restored)throw new Error('Same-profile history did not reappear')
  fs.writeFileSync(config.reopened,JSON.stringify(restored,null,2))
  console.log('native-path-audit: same-profile saved reply is visible after reopening')
}

export function instrument(source) {
  const patch=(before,after)=>{assert.equal(source.split(before).length,2,'Unexpected checker anchor: '+before.slice(0,80));source=source.replace(before,after)}
  patch("const work = realpathSync.native(mkdtempSync(join(realpathSync.native(tmpdir()), 'ds-bot-packed-')))","const nativeConfig = JSON.parse(process.env.CHEMCLAW_NATIVE_CONFIG)\nconst work = nativeConfig.reuseWork || realpathSync.native(mkdtempSync(join(realpathSync.native(tmpdir()), 'ds-bot-packed-')))")
  for(const folder of ['home','workspace','shell'])patch("mkdirSync(join(work, '"+folder+"'))","mkdirSync(join(work, '"+folder+"'), {recursive:true})")
  patch('async function chat(cdp, auditPort) {','async function chat(cdp, auditPort) {\n  if (nativeConfig.reopen) return ('+reopenHistory.toString()+')(cdp)\n  await ('+observeMain.toString()+')()')
  patch('...(source ? [root] : []), ...graphics,','...(source ? [root] : []), "--inspect=127.0.0.1:" + nativeConfig.inspectPort, ...graphics,')
  patch('  children.push(app)','  children.push(app)\n  writeFileSync(nativeConfig.owned,JSON.stringify({pid:app.pid,executable:packedApp,work}))\n  app.once("exit",(code,signal)=>writeFileSync(nativeConfig.exited,JSON.stringify({pid:app.pid,code,signal})))')
  const browser="  console.log('check-packed: browser tool, native bridge, takeover and give-back passed')"
  patch(browser,browser+'\n  if (problems.length) throw new Error("Page errors before fault injection")\n  if (nativeConfig.mode !== "html-frame") await ('+faultProbe.toString()+')(evaluate,browserFixture.address().port)')
  const html='  await auditHtmlFrame(cdp, auditPort, evaluate, shotFile)'
  patch(html,html+'\n  if (problems.length) throw new Error("Page errors before HTML fault injection")\n  if (nativeConfig.mode === "html-frame") await ('+faultProbe.toString()+')(evaluate,browserFixture.address().port)')
  patch('    }, 90_000)','    }, 15_000)')
  const purpose="    await until(\"document.querySelector('.bt-skill-library .bt-skill-detail')\", 'the skill details panel')"
  patch(purpose,purpose+'\n    await until("Boolean(document.querySelector(\'.bt-skill-detail .bt-skill-purpose\')?.textContent.trim())", "populated skill purpose")')
  patch('rmSync(work, { recursive: true, force: true, maxRetries: 10, retryDelay: 500 })','// Preserve this synthetic profile for same-profile reopening; runner disposal removes it.')
  return source
}

export function protectedExit(record) {
  return record.checker?.code===1 && record.checker.signal===null
    && record.checkpoint?.stage==='owned-main-exited' && record.exit?.pid===record.owned?.pid
    && record.exit.code===0 && record.exit.signal===null && record.notice?.pid===record.owned.pid
    && record.notice.hostPids?.length>0 && record.notice.notices?.length===1
    && record.notice.notices[0].remainingHostPids?.length===0 && record.native.length===0
}

async function nativeReports(pid,started,folder) {
  const reports=resolve(homedir(),'Library/Logs/DiagnosticReports'), found=[]
  for(let n=0;n<6;n++){
    for(const name of existsSync(reports)?readdirSync(reports):[]){
      if(!name.startsWith('ChemClaw')||!name.endsWith('.ips')||found.some(x=>x.name===name))continue
      const file=resolve(reports,name),stat=statSync(file)
      if(stat.mtimeMs<started||stat.size>4*1024*1024)continue
      const bytes=readFileSync(file,'utf8'); let report
      try{report=JSON.parse(bytes.slice(bytes.indexOf('\n')+1))}catch{continue}
      if(report.pid!==pid && !report.procPath?.startsWith(dirname(folder)+'/'))continue
      writeFileSync(inside(folder,basename(name)),bytes)
      found.push({name,matchingOldSignature:crashSignature(report,pid),signal:report.exception?.signal})
    }
    if(found.length)break
    await sleep(1000)
  }
  return found
}

async function execute(checker,app,root,config) {
  const env={...process.env,CHEMCLAW_NATIVE_CONFIG:JSON.stringify(config),TMPDIR:inside(root,'tmp'),DSH_HOME:inside(root,'unused-user-dsh'),DS_BOT_USER_DSH_HOME:inside(root,'unused-user-dsh')}
  for(const key of Object.keys(env))if(/KEY|TOKEN|PASSWORD|SECRET/i.test(key))delete env[key]
  mkdirSync(env.TMPDIR);mkdirSync(env.DSH_HOME)
  let output=''
  const child=spawn(process.execPath,[checker,app,inside(root,'screen'),'--mac-ui'],{cwd:root,env,stdio:['ignore','pipe','pipe']})
  for(const stream of [child.stdout,child.stderr])stream.on('data',chunk=>{output+=String(chunk);process.stdout.write(chunk)})
  const result=await new Promise((done,reject)=>{child.once('error',reject);child.once('close',(code,signal)=>done({code,signal}))})
  writeFileSync(inside(root,'test.log'),output)
  return result
}

export async function main() {
  assert.equal(process.platform,'darwin');assert.equal(process.arch,'arm64')
  const [mode,input,checkerInput,rootInput]=process.argv.slice(2)
  assert.ok(modes.has(mode),'Unknown native mode')
  const root=resolve(rootInput),app=resolve(input),checker=resolve(checkerInput)
  assert.ok(root.startsWith(resolve(process.env.RUNNER_TEMP)+'/'),'Use runner temporary data')
  assert.equal(basename(app),'ChemClaw.app');assert.ok(!existsSync(root),'Do not overwrite evidence')
  mkdirSync(root,{recursive:true})
  const from=inside(root,'A/ChemClaw.app'),to=inside(root,'B/ChemClaw.app')
  mkdirSync(dirname(from));mkdirSync(dirname(to));cpSync(app,from,{recursive:true,verbatimSymlinks:true})
  const copy=resolve(dirname(checker),'check-packed-native-'+mode+'.mjs')
  assert.ok(!existsSync(copy));writeFileSync(copy,instrument(readFileSync(checker,'utf8')))
  const summary={mode,status:'started',sourceCommit:process.env.CANDIDATE_COMMIT,productFixed:false}
  const save=()=>writeFileSync(inside(root,'summary.json'),JSON.stringify(summary,null,2))
  const read=file=>existsSync(file)?JSON.parse(readFileSync(file,'utf8')):null
  const phase=inside(root,'fault');mkdirSync(phase)
  const config={mode,inspectPort:9700+Math.floor(Math.random()*500),appFrom:from,appTo:to,owned:inside(phase,'owned-process.json'),exited:inside(phase,'main-exit.json'),notice:inside(phase,'notice.json'),checkpoint:inside(phase,'checkpoint.json')}
  save()
  try {
    const started=Date.now()
    const outcome=await execute(copy,resolve(from,'Contents/MacOS/ChemClaw'),phase,config)
    summary.fault={checker:outcome,owned:read(config.owned),exit:read(config.exited),notice:read(config.notice),checkpoint:read(config.checkpoint),native:[]}
    if(summary.fault.owned?.pid)summary.fault.native=await nativeReports(summary.fault.owned.pid,started,phase)
    assert.ok(protectedExit(summary.fault),'Strict protected-exit oracle failed')
    save()
    const reopen=inside(root,'reopen');mkdirSync(reopen)
    const again={...config,reopen:true,reuseWork:summary.fault.owned.work,baseline:config.checkpoint,owned:inside(reopen,'owned-process.json'),exited:inside(reopen,'main-exit.json'),notice:inside(reopen,'notice.json'),reopened:inside(reopen,'history-restored.json')}
    const reopened=await execute(copy,resolve(to,'Contents/MacOS/ChemClaw'),reopen,again)
    summary.reopen={checker:reopened,history:read(again.reopened),exit:read(again.exited)}
    assert.equal(reopened.code,0,'Same-profile reopen checker failed');assert.equal(summary.reopen.exit?.code,0)
    assert.ok(summary.reopen.history?.savedReplyVisible,'Saved reply not visible')
    summary.status='protected-exit-and-history-restored'
  } catch(error){summary.status='failure';summary.error=error.message;process.exitCode=1}
  finally {
    // A timed-out test must not leave an owned app running. Never match by name.
    for(const folder of ['fault','reopen']){
      const owned=read(inside(root,folder+'/owned-process.json'))
      if(!owned?.pid)continue
      const command=spawnSync('/bin/ps',['-p',String(owned.pid),'-o','command='],{encoding:'utf8'}).stdout||''
      if(command.includes(root)&&command.includes('/Contents/MacOS/ChemClaw')){
        summary.status='failure';summary.error='Owned app remained alive after checker'
        try{process.kill(owned.pid,'SIGTERM')}catch{}
      }
      const notice=read(inside(root,folder+'/notice.json'))
      for(const pid of notice?.hostPids??[]){
        const hostCommand=spawnSync('/bin/ps',['-p',String(pid),'-o','command='],{encoding:'utf8'}).stdout||''
        if(hostCommand.includes(root)&&hostCommand.includes('/host.mjs')){
          summary.status='failure';summary.error='Owned DSH remained alive after checker'
          try{process.kill(pid,'SIGTERM')}catch{}
        }
      }
    }
    if(summary.status!=='protected-exit-and-history-restored')process.exitCode=1
    summary.completedAt=new Date().toISOString();save();console.log('native-path-audit summary: '+JSON.stringify(summary))
  }
}

if(process.argv[1]&&pathToFileURL(resolve(process.argv[1])).href===import.meta.url)await main()
