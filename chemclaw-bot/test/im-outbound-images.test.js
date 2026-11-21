import assert from 'node:assert/strict'
import { createDecipheriv } from 'node:crypto'
import { createServer } from 'node:http'
import { test } from 'node:test'
import { extractLocalMarkdownImages, prepareOutboundReply } from '../src/host/im/outbound-images.js'
import feishu from '../src/host/im/platforms/feishu.js'
import weixin from '../src/host/im/platforms/weixin.js'
import telegram from '../src/host/im/platforms/telegram.js'
import discord from '../src/host/im/platforms/discord.js'
import slack from '../src/host/im/platforms/slack.js'
import dingtalk from '../src/host/im/platforms/dingtalk.js'
import { fakeWsServer } from './fake-ws.js'

const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52])

const until = async (fn, tries = 80) => {
  for (let at = 0; at < tries; at += 1) {
    const value = await fn()
    if (value !== undefined && value !== false) return value
    await new Promise(done => setTimeout(done, 25))
  }
  return undefined
}

test('extractLocalMarkdownImages handles CRLF fences, indented code, quoted fences, escaped destinations, and skips remote URLs (#1761)', () => {
  const md = [
    'Here is the shot:',
    '![Shot 1](./output/shot.png "title")',
    '![Paren](./output/paren.png (my caption))',
    '![Escaped](./output/plot\\(1\\).png)',
    '![Win](C:\\Users\\_team\\chart.png)',
    '![With spaces](<./my charts/plot (1).png>)',
    '![Remote](https://example.com/a.png)',
    '![Data](data:image/png;base64,AAAA)',
    '```code``` ![AfterInline](./inline-ok.png)',
    '``a ``` b`` ![AfterDouble](./double-ok.png)',
    'Inline example: `![Code](./ignored.png)`',
    '',
    '    ![IndentedCode](./indented-ignored.png)',
    '\t![TabCode](./tab-ignored.png)',
    '',
    '> ~~~md',
    '> ![QuotedFence](./quoted-ignored.png)',
    '> ~~~',
    '> ![AfterQuotedFence](./after-quoted.png)',
    '```md',
    '![Fence](./also-ignored.png)',
    '```',
    '![AfterCrlfFence](./after-crlf.png)',
    '![FileUrl](file:///tmp/demo.jpg)',
  ].join('\r\n')
  const links = extractLocalMarkdownImages(md)
  assert.deepEqual(links.map(item => [item.alt, item.path]), [
    ['Shot 1', './output/shot.png'],
    ['Paren', './output/paren.png'],
    ['Escaped', './output/plot(1).png'],
    ['Win', 'C:\\Users\\_team\\chart.png'],
    ['With spaces', './my charts/plot (1).png'],
    ['AfterInline', './inline-ok.png'],
    ['AfterDouble', './double-ok.png'],
    ['AfterQuotedFence', './after-quoted.png'],
    ['AfterCrlfFence', './after-crlf.png'],
    ['FileUrl', 'file:///tmp/demo.jpg'],
  ])
})

test('extractLocalMarkdownImages preserves loose/nested list images and respects fence quote depth (#1761)', () => {
  const md = [
    '- Chart:',
    '',
    '    ![LooseBullet](./loose-bullet.png)',
    '',
    '      ![ListIndentedCode](./list-code-ignored.png)',
    '',
    '1. Step:',
    '',
    '    ![LooseOrdered](./loose-ordered.png)',
    '',
    '- Outer',
    '  - Inner',
    '',
    '      ![NestedList](./nested-list.png)',
    '',
    '        ![NestedCode](./nested-code-ignored.png)',
    '',
    '- Fenced inside list:',
    '  ```md',
    '  ![ListFence](./list-fence-ignored.png)',
    '  ```',
    '  ![AfterListFence](./after-list-fence.png)',
    '',
    '10. Outer',
    '    - Inner A',
    '    - Inner B',
    '    ```md',
    '    ![DeepFence](./deep-fence-ignored.png)',
    '    ```',
    '    ![AfterDeepFence](./after-deep-fence.png)',
    '',
    'Paragraph after list.',
    '',
    '    ![TopIndentedCode](./top-code-ignored.png)',
    '',
    '```markdown',
    '> ```',
    '![UnquotedExample](./unquoted-example-ignored.png)',
    '```',
    '![UnquotedActual](./unquoted-actual.png)',
    '',
    '> ```markdown',
    '> > ```',
    '> ![QuotedExample](./quoted-example-ignored.png)',
    '> ```',
    '> ![QuotedActual](./quoted-actual.png)',
    '',
    '> ```md',
    '> ![UnclosedQuoteFence](./unclosed-q-ignored.png)',
    '![AfterQuoteExit](./after-q-exit.png)',
  ].join('\n')
  const links = extractLocalMarkdownImages(md)
  assert.deepEqual(links.map(item => [item.alt, item.path]), [
    ['LooseBullet', './loose-bullet.png'],
    ['LooseOrdered', './loose-ordered.png'],
    ['NestedList', './nested-list.png'],
    ['AfterListFence', './after-list-fence.png'],
    ['AfterDeepFence', './after-deep-fence.png'],
    ['UnquotedActual', './unquoted-actual.png'],
    ['QuotedActual', './quoted-actual.png'],
    ['AfterQuoteExit', './after-q-exit.png'],
  ])
})

test('extractLocalMarkdownImages closes list containers interrupted by blockquotes while preserving list-nested blockquotes (#1761)', () => {
  const md = [
    '- item',
    '',
    '> quote',
    '',
    '    ![AfterTopQuote](./after-top-quote-ignored.png)',
    '',
    '- item without blank',
    '> quote interrupts list',
    '',
    '    ![AfterNoBlankQuote](./after-noblank-quote-ignored.png)',
    '',
    '- item with nested quote',
    '',
    '  > nested quote',
    '',
    '    ![InListAfterNestedQuote](./in-list-after-nested-quote.png)',
    '',
    '      ![CodeInListAfterNestedQuote](./code-in-list-ignored.png)',
    '',
    '> - quoted item',
    '>',
    '> > outer quote interrupts inner list',
    '>',
    '>     ![CodeInOuterQuote](./code-in-outer-quote-ignored.png)',
    '',
    '> - quoted item with nested quote',
    '>',
    '>   > nested quote inside quoted list',
    '>',
    '>     ![ImgInQuotedList](./img-in-quoted-list.png)',
    '',
    '- list with fenced nested quote',
    '  > ```md',
    '  > ![InNestedQuoteFence](./nested-q-fence-ignored.png)',
    '    ![AfterNestedQuoteExit](./after-nested-q-exit.png)',
  ].join('\n')
  const links = extractLocalMarkdownImages(md)
  assert.deepEqual(links.map(item => [item.alt, item.path]), [
    ['InListAfterNestedQuote', './in-list-after-nested-quote.png'],
    ['ImgInQuotedList', './img-in-quoted-list.png'],
    ['AfterNestedQuoteExit', './after-nested-q-exit.png'],
  ])
})

test('extractLocalMarkdownImages follows CommonMark paragraph-interruption rules for ordered lists and Setext underlines (#1761)', () => {
  const md = [
    'See version',
    '2. foo ![InlineAfterTwoDot](./inline-after-2dot.png)',
    '',
    '    ![CodeAfterTwoDot](./after-2dot-ignored.png)',
    '',
    'Heading with dash',
    '-',
    '',
    '    ![CodeAfterDashSetext](./after-dash-setext-ignored.png)',
    '',
    'Heading with dashes',
    '---',
    '    ![CodeDirectAfterSetext](./after-direct-setext-ignored.png)',
    '',
    'Heading with equals',
    '===',
    '    ![CodeAfterEqSetext](./after-eq-setext-ignored.png)',
    '',
    'Paragraph before empty markers',
    '*',
    '',
    '    ![CodeAfterEmptyStar](./after-empty-star-ignored.png)',
    '',
    'Paragraph before empty ordered',
    '1.',
    '',
    '    ![CodeAfterEmptyOne](./after-empty-one-ignored.png)',
    '',
    'Paragraph interrupted by 1.',
    '1. First item',
    '2. Second item',
    '',
    '    ![InSiblingTwoDot](./in-sibling-2dot.png)',
    '',
    '-',
    '  ![InEmptyBullet](./in-empty-bullet.png)',
    '',
    '-',
    '',
    '    ![CodeAfterTwoBlankBullet](./after-two-blank-bullet-ignored.png)',
  ].join('\n')
  const links = extractLocalMarkdownImages(md)
  assert.deepEqual(links.map(item => [item.alt, item.path]), [
    ['InlineAfterTwoDot', './inline-after-2dot.png'],
    ['InSiblingTwoDot', './in-sibling-2dot.png'],
    ['InEmptyBullet', './in-empty-bullet.png'],
  ])
})

test('extractLocalMarkdownImages bounds inline code spans to a single block while allowing same-paragraph wraps (#1761)', async () => {
  const md = [
    'Paragraph one with stray ` backtick',
    '',
    '![BetweenStrays](./between-strays.png)',
    '   ',
    'Paragraph three with stray ` backtick',
    '',
    '> Quote para with stray ` backtick',
    '>',
    '> ![InQuoteBetween](./in-quote-between.png)',
    '>',
    '> Quote para three with ` backtick',
    '',
    '# Heading with stray ` backtick',
    '![AfterHeadingStray](./after-heading-stray.png)',
    'Footer with stray ` backtick',
    '',
    'Para with stray ` backtick',
    '- ![InListAfterStray](./in-list-after-stray.png)',
    '- item with stray ` backtick',
    '',
    'Wrapped `inline',
    '![IgnoredInMultilineCode](./multiline-code-ignored.png)',
    'code` and ![AfterMultilineCode](./after-multiline-code.png)',
    '',
    '> Wrapped `inline',
    '> ![IgnoredInQuoteMultiline](./q-multiline-ignored.png)',
    '> code` and ![AfterQuoteMultiline](./after-q-multiline.png)',
  ].join('\r\n')
  const links = extractLocalMarkdownImages(md)
  assert.deepEqual(links.map(item => [item.alt, item.path]), [
    ['BetweenStrays', './between-strays.png'],
    ['InQuoteBetween', './in-quote-between.png'],
    ['AfterHeadingStray', './after-heading-stray.png'],
    ['InListAfterStray', './in-list-after-stray.png'],
    ['AfterMultilineCode', './after-multiline-code.png'],
    ['AfterQuoteMultiline', './after-q-multiline.png'],
  ])

  // Verify exact source-offset rewriting through prepareOutboundReply on CRLF + multi-line block.
  const out = await prepareOutboundReply(
    'Stray ` tick\r\n\r\n> Keep ![Shot](./shot.png) here\r\n\r\nAnother ` tick',
    { resolveImage: async () => ({ mime: 'image/png', bytes: PNG.toString('base64') }) },
  )
  assert.equal(out.images.length, 1)
  assert.equal(out.images[0].name, 'shot.png')
  assert.equal(out.text, 'Stray ` tick\n\n> Keep  here\n\nAnother ` tick')
})

test('prepareOutboundReply deduplicates repeated paths and surfaces unavailable/unsupported images (#1761)', async () => {
  let calls = 0
  const out = await prepareOutboundReply(
    'First:\n![A](./a.png)\nAgain:\n![A2](./a.png)\nBad:\n![Secret](../secret.png)\nVector:\n![Logo](./logo.svg)',
    {
      resolveImage: async (path) => {
        calls += 1
        if (path === './a.png') return { mime: 'image/png', bytes: PNG.toString('base64') }
        if (path === './logo.svg') return { mime: 'image/svg+xml', bytes: Buffer.from('<svg/>').toString('base64') }
        throw new Error('Image outside workspace')
      },
    },
  )
  assert.equal(calls, 3, 'duplicate ./a.png resolved once')
  assert.equal(out.images.length, 1)
  assert.equal(out.images[0].name, 'a.png')
  assert.deepEqual(out.images[0].data, PNG)
  assert.equal(out.failed.length, 2)
  assert.match(out.text, /\[Image unavailable: Secret\]/)
  assert.match(out.text, /\[Image unavailable: Logo\]/)
  assert.ok(!out.text.includes('./a.png'))
})

test('Feishu sendImage uploads multipart to /open-apis/im/v1/images and delivers msg_type=image (#1761)', async (t) => {
  const calls = []
  const wss = await fakeWsServer({ onSocket() {} })
  const http = createServer((req, res) => {
    const chunks = []
    req.on('data', chunk => chunks.push(chunk))
    req.on('end', () => {
      const buf = Buffer.concat(chunks)
      calls.push({ method: req.method, path: req.url, headers: req.headers, buf })
      if (req.url === '/open-apis/auth/v3/tenant_access_token/internal') {
        res.writeHead(200, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ code: 0, tenant_access_token: 'fs-tok', expire: 7200 }))
        return
      }
      if (req.url === '/open-apis/bot/v3/info') {
        res.writeHead(200, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ code: 0, bot: { open_id: 'ou_bot' } }))
        return
      }
      if (req.url === '/callback/ws/endpoint') {
        res.writeHead(200, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ code: 0, data: { URL: wss.url } }))
        return
      }
      if (req.url === '/open-apis/im/v1/images') {
        res.writeHead(200, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ code: 0, data: { image_key: 'img_v3_key1' } }))
        return
      }
      res.writeHead(200, { 'content-type': 'application/json' })
      res.end(JSON.stringify({ code: 0, data: { message_id: 'om_img1' } }))
    })
  })
  await new Promise(resolve => http.listen(0, '127.0.0.1', resolve))
  const api = `http://127.0.0.1:${http.address().port}`
  const handle = feishu.connect({ appId: 'cli_1', appSecret: 'sec_1' }, {
    fetch: globalThis.fetch, WebSocket: globalThis.WebSocket, config: { api }, runtime: { get: () => ({}), set: () => {} }, log: { warn: () => {} },
  }, { onMessage: () => {}, onAction: () => {}, onStatus: () => {} })
  t.after(() => { handle.stop(); wss.close(); http.closeAllConnections?.(); http.close() })
  await until(() => calls.some(c => c.path === '/callback/ws/endpoint'))
  const sent = await handle.sendImage({ key: 'oc_1', kind: 'direct' }, { data: PNG, mediaType: 'image/png', name: 'shot.png' })
  assert.equal(sent.messageId, 'om_img1')
  const up = calls.find(c => c.path === '/open-apis/im/v1/images')
  assert.ok(up)
  assert.equal(up.headers.authorization, 'Bearer fs-tok')
  assert.match(String(up.headers['content-type']), /^multipart\/form-data/)
  assert.ok(up.buf.includes(Buffer.from('image_type')))
  assert.ok(up.buf.includes(Buffer.from('message')))
  assert.ok(up.buf.includes(PNG))
  const msg = calls.find(c => c.path === '/open-apis/im/v1/messages?receive_id_type=chat_id')
  const payload = JSON.parse(msg.buf.toString('utf8'))
  assert.equal(payload.receive_id, 'oc_1')
  assert.equal(payload.msg_type, 'image')
  assert.deepEqual(JSON.parse(payload.content), { image_key: 'img_v3_key1' })
})

test('WeChat sends images and original file attachments through the encrypted CDN', async (t) => {
  const calls = []
  let uploadedCipher = null
  const http = createServer((req, res) => {
    const chunks = []
    req.on('data', chunk => chunks.push(chunk))
    req.on('end', () => {
      const buf = Buffer.concat(chunks)
      calls.push({ method: req.method, path: req.url, buf })
      if (req.url === '/ilink/bot/getuploadurl') {
        res.writeHead(200, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ ret: 0, upload_param: 'up-p1' }))
        return
      }
      if (req.url.startsWith('/cdn/upload?')) {
        uploadedCipher = buf
        res.writeHead(200, { 'x-encrypted-param': 'dl-param-99' })
        res.end('ok')
        return
      }
      res.writeHead(200, { 'content-type': 'application/json' })
      res.end(JSON.stringify({ ret: 0, msgs: [], get_updates_buf: 'c1' }))
    })
  })
  await new Promise(resolve => http.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${http.address().port}/`
  const handle = weixin.connect({ token: 'wx-tok', baseUrl: '' }, {
    fetch: globalThis.fetch, WebSocket: globalThis.WebSocket,
    config: { api: base, qr: base, cdn: `${base}cdn` },
    runtime: { get: () => ({ contextTokens: { u1: 'ctx-1' } }), set: () => {} },
    log: { warn: () => {} },
  }, { onMessage: () => {}, onAction: () => {}, onStatus: () => {} })
  t.after(() => { handle.stop(); http.closeAllConnections?.(); http.close() })
  await until(() => calls.some(c => c.path === '/ilink/bot/getupdates'))
  const sent = await handle.sendImage({ key: 'u1', kind: 'direct' }, { data: PNG, mediaType: 'image/png', name: 'shot.png' })
  assert.ok(sent.messageId.startsWith('ds-bot-'))
  const upReq = JSON.parse(calls.find(c => c.path === '/ilink/bot/getuploadurl').buf.toString('utf8'))
  assert.equal(upReq.media_type, 1)
  assert.ok(uploadedCipher && uploadedCipher.byteLength >= PNG.byteLength)
  // Verify ciphertext decrypts cleanly back to exact PNG bytes using the announced AES key.
  const decipher = createDecipheriv('aes-128-ecb', Buffer.from(upReq.aeskey, 'hex'), null)
  const decrypted = Buffer.concat([decipher.update(uploadedCipher), decipher.final()])
  assert.deepEqual(decrypted, PNG)
  const sendReq = JSON.parse(calls.find(c => c.path === '/ilink/bot/sendmessage').buf.toString('utf8'))
  assert.equal(sendReq.msg.context_token, 'ctx-1')
  assert.equal(sendReq.msg.item_list[0].type, 2)
  assert.equal(sendReq.msg.item_list[0].image_item.mid_size, uploadedCipher.byteLength)
  assert.equal(sendReq.msg.item_list[0].image_item.media.encrypt_query_param, 'dl-param-99')

  for (const [name, source] of [
    ['趋势图.svg', '<svg xmlns="http://www.w3.org/2000/svg"><text>示例</text></svg>'],
    ['报告.html', '<!doctype html><meta charset="utf-8"><p>原始报告</p>'],
  ]) {
    const data = Buffer.from(source)
    const chat = { key: 'u1', kind: 'direct' }
    const sent = await handle.sendFile(chat, { data, name })
    const upload = JSON.parse(calls.findLast(call => call.path === '/ilink/bot/getuploadurl').buf)
    const { msg } = JSON.parse(calls.findLast(call => call.path === '/ilink/bot/sendmessage').buf)
    const item = msg.item_list[0]
    assert.equal(upload.media_type, 3)
    assert.equal(upload.rawsize, data.length)
    assert.equal(upload.filesize, uploadedCipher.length)
    assert.equal(msg.client_id, sent.messageId)
    assert.equal(msg.context_token, 'ctx-1')
    assert.equal(item.type, 4)
    assert.equal(item.file_item.file_name, name)
    assert.equal(item.file_item.len, String(data.length))
    assert.equal(item.file_item.media.encrypt_query_param, 'dl-param-99')
    const key = Buffer.from(item.file_item.media.aes_key, 'base64').toString()
    assert.equal(key, upload.aeskey)
    const decrypt = createDecipheriv('aes-128-ecb', Buffer.from(key, 'hex'), null)
    assert.deepEqual(Buffer.concat([decrypt.update(uploadedCipher), decrypt.final()]), data)
  }
})

test('Telegram, Discord, Slack, and DingTalk sendImage hit their native upload/send endpoints', async (t) => {
  const calls = []
  const wss = await fakeWsServer({ onSocket() {} })
  const http = createServer((req, res) => {
    const chunks = []
    req.on('data', chunk => chunks.push(chunk))
    req.on('end', () => {
      const buf = Buffer.concat(chunks)
      calls.push({ method: req.method, path: req.url, headers: req.headers, buf })
      if (req.url.endsWith('/getMe')) { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ ok: true, result: { id: 1, username: 'tg' } })); return }
      if (req.url.endsWith('/getUpdates')) { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ ok: true, result: [] })); return }
      if (req.url.endsWith('/sendPhoto')) { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ ok: true, result: { message_id: 77 } })); return }
      if (req.url === '/gateway/bot') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ url: wss.url })); return }
      if (req.url === '/channels/ch1/messages') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ id: 'dc-1' })); return }
      if (req.url === '/auth.test') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ ok: true, user_id: 'U1' })); return }
      if (req.url === '/apps.connections.open') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ ok: true, url: wss.url })); return }
      if (req.url === '/files.getUploadURLExternal') {
        res.writeHead(200, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ ok: true, upload_url: `${base}/slack-upload`, file_id: 'F123' }))
        return
      }
      if (req.url === '/slack-upload') { res.writeHead(200); res.end('ok'); return }
      if (req.url === '/files.completeUploadExternal') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ ok: true })); return }
      if (req.url.startsWith('/gettoken')) { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ errcode: 0, access_token: 'dt-tok', expires_in: 7200 })); return }
      if (req.url === '/v1.0/gateway/connections/open') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ endpoint: wss.url, ticket: 'tk' })); return }
      if (req.url.startsWith('/media/upload')) { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ errcode: 0, media_id: '@lADP_media1' })); return }
      res.writeHead(200, { 'content-type': 'application/json' })
      res.end(JSON.stringify({ processQueryKey: 'dt-q1' }))
    })
  })
  await new Promise(resolve => http.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${http.address().port}`
  const common = { fetch: globalThis.fetch, WebSocket: globalThis.WebSocket, runtime: { get: () => ({}), set: () => {} }, log: { warn: () => {} } }
  const noop = { onMessage: () => {}, onAction: () => {}, onStatus: () => {} }

  const tg = telegram.connect({ token: 't1' }, { ...common, config: { api: base } }, noop)
  const dc = discord.connect({ token: 'd1' }, { ...common, config: { api: base, gateway: wss.url } }, noop)
  const sl = slack.connect({ botToken: 'xoxb-1', appToken: 'xapp-1' }, { ...common, config: { api: `${base}/` } }, noop)
  const dt = dingtalk.connect({ clientId: 'c1', clientSecret: 's1' }, { ...common, config: { api: base, gateway: base, oapi: base } }, noop)
  t.after(() => { tg.stop(); dc.stop(); sl.stop(); dt.stop(); wss.close(); http.closeAllConnections?.(); http.close() })

  const img = { data: PNG, mediaType: 'image/png', name: 'shot.png', alt: 'Shot' }
  assert.equal((await tg.sendImage({ key: '100', kind: 'direct' }, img)).messageId, 77)
  assert.equal((await dc.sendImage({ key: 'ch1', kind: 'group' }, img)).messageId, 'dc-1')
  assert.equal((await sl.sendImage({ key: 'C1', kind: 'group' }, img)).messageId, 'F123')
  assert.equal((await dt.sendImage({ key: 'g1', kind: 'group' }, img)).messageId, 'dt-q1')

  assert.ok(calls.some(c => c.path === '/bott1/sendPhoto' && c.buf.includes(PNG)))
  assert.ok(calls.some(c => c.path === '/channels/ch1/messages' && c.headers.authorization === 'Bot d1' && c.buf.includes(PNG)))
  assert.ok(calls.some(c => c.path === '/slack-upload' && c.buf.equals(PNG)))
  assert.ok(calls.some(c => c.path === '/files.completeUploadExternal' && JSON.parse(c.buf.toString('utf8')).channel_id === 'C1'))
  const dtSend = calls.find(c => c.path === '/v1.0/robot/groupMessages/send')
  assert.equal(JSON.parse(dtSend.buf.toString('utf8')).msgKey, 'sampleImageMsg')
  assert.deepEqual(JSON.parse(JSON.parse(dtSend.buf.toString('utf8')).msgParam), { photoURL: '@lADP_media1' })
})

test('WeChat and Slack reject untrusted upload URLs and Telegram falls back to sendDocument on dimension error (#1761)', async (t) => {
  const calls = []
  const wss = await fakeWsServer({ onSocket() {} })
  const http = createServer((req, res) => {
    const chunks = []
    req.on('data', chunk => chunks.push(chunk))
    req.on('end', () => {
      calls.push({ path: req.url, buf: Buffer.concat(chunks) })
      if (req.url === '/ilink/bot/getuploadurl') {
        res.writeHead(200, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ ret: 0, upload_full_url: 'https://evil.example/steal' }))
        return
      }
      if (req.url === '/files.getUploadURLExternal') {
        res.writeHead(200, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ ok: true, upload_url: 'https://evil.example/steal', file_id: 'F9' }))
        return
      }
      if (req.url.endsWith('/sendPhoto')) {
        res.writeHead(400, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ ok: false, error_code: 400, description: 'Bad Request: PHOTO_INVALID_DIMENSIONS' }))
        return
      }
      if (req.url.endsWith('/sendDocument')) {
        res.writeHead(200, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ ok: true, result: { message_id: 88 } }))
        return
      }
      if (req.url.endsWith('/getMe')) { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ ok: true, result: { id: 1, username: 'tg' } })); return }
      if (req.url.endsWith('/getUpdates')) { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ ok: true, result: [] })); return }
      if (req.url === '/auth.test') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ ok: true, user_id: 'U1' })); return }
      if (req.url === '/apps.connections.open') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ ok: true, url: wss.url })); return }
      res.writeHead(200, { 'content-type': 'application/json' })
      res.end(JSON.stringify({ ret: 0, msgs: [], get_updates_buf: 'c1' }))
    })
  })
  await new Promise(resolve => http.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${http.address().port}`
  const common = { fetch: globalThis.fetch, WebSocket: globalThis.WebSocket, runtime: { get: () => ({}), set: () => {} }, log: { warn: () => {} } }
  const noop = { onMessage: () => {}, onAction: () => {}, onStatus: () => {} }
  const wx = weixin.connect({ token: 'wx-tok', baseUrl: '' }, { ...common, config: { api: `${base}/`, qr: `${base}/`, cdn: `${base}/cdn` } }, noop)
  const sl = slack.connect({ botToken: 'xoxb-1', appToken: 'xapp-1' }, { ...common, config: { api: `${base}/` } }, noop)
  const tg = telegram.connect({ token: 't1' }, { ...common, config: { api: base } }, noop)
  t.after(() => { wx.stop(); sl.stop(); tg.stop(); wss.close(); http.closeAllConnections?.(); http.close() })
  const img = { data: PNG, mediaType: 'image/png', name: 'tall.png' }
  await assert.rejects(() => wx.sendImage({ key: 'u1', kind: 'direct' }, img), err => err.permanent === true && /Untrusted upload address/.test(err.message))
  await assert.rejects(() => sl.sendImage({ key: 'C1', kind: 'group' }, img), err => err.permanent === true && /untrusted upload url/i.test(err.message))
  const fallback = await tg.sendImage({ key: '100', kind: 'direct' }, img)
  assert.equal(fallback.messageId, 88)
  assert.ok(calls.some(c => c.path === '/bott1/sendDocument' && c.buf.includes(PNG)))
})

test('Discord and Slack final image-delivery timeouts mark errors unknown so retries do not duplicate images (#1761)', async (t) => {
  const wss = await fakeWsServer({ onSocket() {} })
  const timeoutErr = () => Object.assign(new Error('The operation was aborted due to timeout'), { name: 'TimeoutError' })
  const http = createServer((req, res) => {
    req.resume()
    req.on('end', () => {
      if (req.url === '/gateway/bot') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ url: wss.url })); return }
      if (req.url === '/auth.test') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ ok: true, user_id: 'U1' })); return }
      if (req.url === '/apps.connections.open') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ ok: true, url: wss.url })); return }
      if (req.url === '/files.getUploadURLExternal') {
        res.writeHead(200, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ ok: true, upload_url: `${base}/slack-up`, file_id: 'F77' }))
        return
      }
      res.writeHead(200)
      res.end('ok')
    })
  })
  await new Promise(resolve => http.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${http.address().port}`
  const fetchWithTimeout = async (url, init) => {
    if (String(url).endsWith('/channels/ch1/messages') || String(url).endsWith('/files.completeUploadExternal')) {
      throw timeoutErr()
    }
    return globalThis.fetch(url, init)
  }
  const common = { fetch: fetchWithTimeout, WebSocket: globalThis.WebSocket, runtime: { get: () => ({}), set: () => {} }, log: { warn: () => {} } }
  const noop = { onMessage: () => {}, onAction: () => {}, onStatus: () => {} }
  const dc = discord.connect({ token: 'd1' }, { ...common, config: { api: base, gateway: wss.url } }, noop)
  const sl = slack.connect({ botToken: 'xoxb-1', appToken: 'xapp-1' }, { ...common, config: { api: `${base}/` } }, noop)
  t.after(() => { dc.stop(); sl.stop(); wss.close(); http.closeAllConnections?.(); http.close() })
  const img = { data: PNG, mediaType: 'image/png', name: 'shot.png' }
  await assert.rejects(() => dc.sendImage({ key: 'ch1', kind: 'group' }, img), err => err.unknown === true)
  await assert.rejects(() => sl.sendImage({ key: 'C1', kind: 'group' }, img), err => err.unknown === true)
})
