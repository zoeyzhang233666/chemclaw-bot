export const CHEMCLAW_UI_CSS = `
.bt-team-intro{max-width:var(--dsh-chat-content-width,748px);width:100%;box-sizing:border-box;margin:0 auto 18px;padding:0 8px;max-height:34vh;overflow:auto;scrollbar-width:thin;color:var(--bt-ink)}
.bt-team-intro h2{font:600 23px/1.4 system-ui,sans-serif;margin:0 0 10px;letter-spacing:-.025em}
.bt-team-intro p{font-size:13px;line-height:1.8;margin:0 0 10px;overflow-wrap:anywhere}
.bt-team-shortcuts{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}.bt-team-shortcuts button{border:1px solid var(--bt-line-2);border-radius:10px;background:var(--bt-card);color:var(--bt-ink);padding:8px 11px;font:12px/1.5 system-ui,sans-serif;cursor:pointer}.bt-team-shortcuts button:hover{background:var(--bt-hover);border-color:var(--bt-accent)}
.bt-team-example{border-left:2px solid var(--bt-accent);padding:3px 0 3px 13px;margin:12px 0}.bt-team-example>span{font-size:10px;color:var(--bt-accent);font-weight:600}.bt-team-example p{margin:4px 0 0;font-size:12px}
.bt-directory-label{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:17px 10px 7px;color:var(--bt-ink-3);font:500 11px/1.5 system-ui,sans-serif;letter-spacing:.04em}
.bt-directory-label[data-drop]{box-shadow:inset 0 1px 0 var(--bt-line-2)}
.bt-directory-toggle{display:inline-flex;align-items:center;gap:4px;min-width:0;padding:0;border:0;background:none;color:inherit;font:inherit;letter-spacing:inherit;cursor:pointer;text-align:left}
.bt-directory-toggle:hover{color:var(--bt-ink-2)}
.bt-directory-caret{display:inline-flex;flex:none;opacity:.7;transition:transform .14s ease}
.bt-directory-caret[data-open]{transform:rotate(90deg)}
.bt-directory-caret svg{width:12px;height:12px}
.bt-directory-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bt-directory-count{flex:none;font-size:10px;letter-spacing:0;opacity:.8}
.bt-row-drag{position:relative;display:flex;align-items:stretch}
.bt-row-drag>.bt-row{flex:1 1 auto;min-width:0;padding-left:18px}
.bt-row-drag[data-drop]{box-shadow:inset 0 1px 0 var(--bt-line-2)}
.bt-row-handle{position:absolute;left:2px;top:50%;transform:translateY(-50%);z-index:1;width:14px;height:28px;display:inline-flex;align-items:center;justify-content:center;border-radius:4px;color:var(--bt-ink-3);font-size:9px;letter-spacing:-1px;line-height:1;opacity:0;cursor:grab;user-select:none}
.bt-row-drag:hover .bt-row-handle,.bt-row-handle:focus-visible{opacity:.7}
.bt-row-handle:active{cursor:grabbing;opacity:1}
.bt-focus-chips{display:flex;flex-wrap:wrap;gap:6px;max-width:280px;justify-content:flex-end}
.bt-focus-chip{font:inherit;font-size:12px;line-height:18px;padding:4px 9px;border-radius:8px;border:1px solid var(--bt-line);background:none;color:var(--bt-ink-2);cursor:pointer}
.bt-focus-chip:hover{background:var(--bt-hover);color:var(--bt-ink)}
.bt-focus-chip[aria-pressed=true]{background:var(--bt-bubble);border-color:var(--bt-line-2);color:var(--bt-ink)}
.bt-side>button.bt-row{min-height:34px;padding:6px 8px;font-size:13px}.bt-tile-wrap{padding:8px 0}.bt-tile{gap:3px}
.bt-head{min-width:0}.bt-pill{max-width:100%;min-width:0}.bt-panel{max-width:calc(100vw - 32px)}
.bt-settings{--bt-set-w:min(1050px,calc(100vw - 32px));--bt-set-h:min(800px,calc(100vh - 48px))}
.bt-settings-scroll{gap:24px;padding:20px 24px 28px}
.bt-set-section h3{letter-spacing:.01em}
.bt-set-card{box-shadow:0 1px 2px color-mix(in srgb,var(--bt-ink) 3%,transparent);overflow:hidden}
.bt-library-heading{display:flex;flex-direction:column;align-items:flex-start;gap:16px}
.bt-library-heading .bt-seg button{white-space:nowrap;min-width:92px;padding:0 15px}
.bt-connectors-page{display:flex;flex-direction:column;gap:20px}.bt-connectors-page>p{margin:0}.bt-connectors-page>h3{margin:8px 0 -6px}.bt-connectors-page>.bt-soft{align-self:flex-start}
.bt-eyebrow{font-size:10px!important;font-weight:600;letter-spacing:.12em;color:var(--bt-ink-3);margin:0;text-transform:uppercase;line-height:18px}
.bt-library-intro{font-size:17px;line-height:1.6;margin:6px 0 0;font-weight:500;letter-spacing:-.02em}
.bt-expert-library>.bt-library-intro{max-width:40em;margin:0 0 4px;font-size:14px;font-weight:400;line-height:1.75;letter-spacing:.01em;color:var(--bt-ink-2)}
.bt-bot-directory{display:flex;flex-direction:column;gap:22px}
.bt-expert-library{display:flex;flex-direction:column;gap:14px}
.bt-catalog-search{display:flex;align-items:center;gap:9px;background:var(--bt-card);border:1px solid var(--bt-line-2);border-radius:12px;padding:10px 13px;color:var(--bt-ink-3)}
.bt-catalog-search input{font:inherit;font-size:13px;outline:none;color:var(--bt-ink);background:none;border:0;width:100%}
.bt-catalog-search input::placeholder{color:var(--bt-ink-3)}
.bt-catalog-categories{display:flex;gap:6px;flex-wrap:wrap}
.bt-catalog-categories button{font:inherit;font-size:11px;border:1px solid transparent;background:none;color:var(--bt-ink-2);border-radius:8px;padding:5px 9px;cursor:pointer;transition:background .15s}
.bt-catalog-categories button:hover{background:var(--bt-hover)}
.bt-catalog-categories button[aria-pressed=true]{color:var(--bt-ink);background:var(--bt-bubble);border-color:var(--bt-line)}
.bt-expert-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.bt-expert-card{display:flex;flex-direction:column;gap:14px;padding:18px;border:1px solid var(--bt-line-2);border-radius:16px;background:var(--bt-card);box-shadow:0 2px 5px color-mix(in srgb,var(--bt-ink) 3%,transparent);min-width:0;transition:border-color .18s,box-shadow .18s}
.bt-expert-card:hover{border-color:color-mix(in srgb,var(--bt-accent) 35%,var(--bt-line));box-shadow:0 4px 14px color-mix(in srgb,var(--bt-ink) 5%,transparent)}
.bt-expert-card header{display:flex;gap:12px;align-items:center}
.bt-expert-card header>div{min-width:0}.bt-expert-card h3{font-size:14px;line-height:1.5;margin:0 0 4px;padding:0;font-weight:600}
.bt-expert-card p{margin:0;overflow-wrap:anywhere}
.bt-expert-description{font-size:12px;line-height:1.8;color:var(--bt-ink-2)}
.bt-expert-example{padding:11px 12px;border-radius:10px;background:color-mix(in srgb,var(--bt-main) 64%,var(--bt-bubble));font-size:12px;line-height:1.8}
.bt-expert-example>span{display:block;color:var(--bt-accent);font-size:10px;font-weight:600;margin-bottom:4px;letter-spacing:.04em}
.bt-expert-card details{border-top:1px solid var(--bt-line);padding-top:10px;font-size:11px;color:var(--bt-ink-2)}
.bt-expert-card summary{cursor:pointer;display:flex;align-items:center;justify-content:space-between;list-style:none;gap:8px}
.bt-expert-card summary::-webkit-details-marker{display:none}.bt-expert-card summary svg{width:12px;height:12px;transition:rotate .15s}.bt-expert-card details[open] summary svg{rotate:90deg}
.bt-expert-card dl{margin:12px 0 0}.bt-expert-card dl>div{margin:10px 0}.bt-expert-card dt{color:var(--bt-ink);font-weight:500;margin-bottom:3px}.bt-expert-card dd{margin:0;line-height:1.8;overflow-wrap:anywhere}
.bt-expert-card footer{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:auto;padding-top:4px}.bt-expert-card footer .bt-set-hint{font-size:10px}
.bt-advanced{padding:15px 17px;border:1px solid var(--bt-line);border-radius:12px;background:color-mix(in srgb,var(--bt-card) 65%,var(--bt-main));font-size:12px;color:var(--bt-ink-2)}
.bt-advanced>summary{cursor:pointer;color:var(--bt-ink);font-weight:500}.bt-advanced[open]>summary{margin-bottom:16px}.bt-advanced textarea{font:12px/1.8 ui-monospace,Consolas,monospace;box-sizing:border-box;resize:vertical;min-height:160px;width:100%;padding:14px;border:1px solid var(--bt-line-2);border-radius:10px;background:var(--bt-main);color:var(--bt-ink);outline:none}.bt-advanced textarea:focus{border-color:var(--bt-accent)}
.bt-connector{padding:18px;gap:14px}.bt-connector-mark{width:42px;height:42px;border-radius:12px;background:color-mix(in srgb,var(--bt-main) 70%,var(--bt-bubble));color:var(--bt-accent);box-shadow:0 1px 2px color-mix(in srgb,var(--bt-ink) 4%,transparent)}
.bt-connector-name{font-weight:600}.bt-connector-status{line-height:1.65;white-space:normal;color:var(--bt-ink-2);font-size:11px;margin-top:2px}.bt-connector-form{padding:14px 0 0;border-top:1px solid var(--bt-line)}
.bt-connector-form .bt-secret-field{background:var(--bt-main);border:1px solid var(--bt-line-2);border-radius:10px;padding:9px 12px;min-height:40px}
.bt-connector-error{padding-left:0}.bt-connector-link{color:var(--bt-accent);text-underline-offset:3px}.bt-connector-actions .bt-soft{border:1px solid var(--bt-line);background:var(--bt-main)}
.bt-data-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.bt-data-card{border:1px solid var(--bt-line);border-radius:16px;background:var(--bt-card);padding:16px;display:flex;flex-direction:column;gap:12px;min-width:0}.bt-data-card header{display:flex;align-items:center;gap:10px}.bt-data-card header strong{font-weight:600;font-size:13px}.bt-data-card p{font-size:11px;line-height:1.8;margin:0;color:var(--bt-ink-2)}.bt-data-card .bt-connector-mark{width:34px;height:34px;border-radius:10px}.bt-data-state{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:10px;color:var(--bt-ink-3)}.bt-data-card[data-state=ready] .bt-data-state>span{color:var(--bt-green)}.bt-data-card[data-state=error] .bt-data-state>span{color:var(--bt-danger)}
.bt-runtime-card{padding:18px;border-radius:16px;border:1px solid var(--bt-line);background:var(--bt-card)}.bt-runtime-card h3{margin:0 0 8px;font-size:13px}.bt-runtime-card p{margin:8px 0 14px}.bt-runtime-card .bt-actions{flex-wrap:wrap}
.bt-q.bt-secret-card{background:var(--bt-card);border:1px solid var(--bt-line-2);box-shadow:0 4px 18px color-mix(in srgb,var(--bt-ink) 5%,transparent);padding:20px;border-radius:18px}.bt-secret-head .bt-q-title{font-size:14px;font-weight:600}.bt-secret-card .bt-q-field{background:var(--bt-main);border-radius:10px;border-color:var(--bt-line-2)}
.bt-apihub{border:1px solid color-mix(in srgb,var(--bt-accent) 28%,var(--bt-line))!important;border-radius:16px;background:linear-gradient(120deg,color-mix(in srgb,var(--bt-accent) 5%,var(--bt-card)),var(--bt-card));padding:20px;display:flex;flex-direction:column;gap:15px}.bt-apihub>header{display:flex;align-items:center;gap:12px}.bt-apihub h3{font-size:16px;margin:0 0 3px}.bt-apihub .bt-eyebrow{color:var(--bt-accent)}.bt-apihub p{margin:0;font-size:12px;line-height:1.8;color:var(--bt-ink-2)}.bt-apihub a{color:var(--bt-accent);font-size:12px;text-underline-offset:3px}.bt-apihub .bt-secret-field{background:var(--bt-main);border:1px solid var(--bt-line-2);border-radius:10px;padding:10px 12px}.bt-apihub .bt-provider-found{display:flex;flex-wrap:wrap;gap:6px}.bt-apihub .bt-provider-found button{white-space:normal;height:auto;min-height:28px;text-align:left}.bt-models-note{margin:0;font-size:12px;color:var(--bt-ink-2);line-height:1.8}
.bt-chemcloud{border:1px solid color-mix(in srgb,var(--bt-accent) 28%,var(--bt-line));border-radius:16px;background:linear-gradient(135deg,color-mix(in srgb,var(--bt-accent) 6%,var(--bt-card)),var(--bt-card) 55%);padding:20px;display:flex;flex-direction:column;gap:12px}.bt-chemcloud>header{display:flex;align-items:flex-start;gap:12px;min-width:0}.bt-chemcloud-title{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}.bt-chemcloud-title h3{margin:0;font-size:16px;line-height:24px;font-weight:600}.bt-chemcloud .bt-eyebrow{color:var(--bt-accent)}.bt-chemcloud .bt-connector-actions{flex:none;margin-left:auto;padding-top:2px}.bt-chemcloud-intro{margin:0;font-size:12px;line-height:1.8;color:var(--bt-ink-2)}.bt-chemcloud-chips{display:flex;flex-wrap:wrap;gap:6px}.bt-chemcloud-chip{display:inline-flex;align-items:center;padding:4px 9px;border-radius:8px;border:1px solid color-mix(in srgb,var(--bt-accent) 22%,var(--bt-line));background:color-mix(in srgb,var(--bt-main) 55%,transparent);color:var(--bt-ink);font-size:11px;line-height:16px;letter-spacing:.01em}.bt-chemcloud-status{margin:0;font-size:11px;line-height:1.65;color:var(--bt-ink-3)}.bt-chemcloud[data-state=ready] .bt-chemcloud-status{color:var(--bt-ink-2)}.bt-chemcloud[data-state=error] .bt-chemcloud-status{color:var(--bt-danger)}.bt-chemcloud-key{display:flex;flex-direction:column;gap:10px;padding-top:12px;border-top:1px solid var(--bt-line)}.bt-chemcloud-key .bt-secret-field{background:var(--bt-main);border:1px solid var(--bt-line-2);border-radius:10px;padding:10px 12px}.bt-chemcloud-key-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.bt-chemcloud-key-row .bt-connector-link{font-size:12px;color:var(--bt-accent);text-underline-offset:3px}.bt-chemcloud-portal{flex:1;min-width:0;font-size:11px;line-height:16px;color:var(--bt-ink-3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.bt-chemcloud-key-row .bt-soft{margin-left:auto}
[data-presented-files-row]{grid-template-columns:minmax(0,1fr)!important;max-width:550px}
[data-presented-file]{background:var(--bt-card)!important;border:1px solid var(--bt-line-2)!important;border-radius:16px!important;box-shadow:0 2px 7px color-mix(in srgb,var(--bt-ink) 4%,transparent)!important;padding:14px!important;gap:12px!important;color:var(--bt-ink)!important;font-family:inherit}
[data-presented-file]>span:first-of-type{background:color-mix(in srgb,var(--bt-main) 70%,var(--bt-bubble))!important;border-color:var(--bt-line)!important;color:var(--bt-accent)!important;border-radius:12px!important}
[data-presented-file] button{color:var(--bt-ink-2)}
@media(max-width:760px){.bt-expert-grid,.bt-data-grid{grid-template-columns:minmax(0,1fr)}.bt-settings-scroll{padding:16px}.bt-connector-head{gap:9px}.bt-connector-actions{flex-wrap:wrap;justify-content:flex-end}.bt-chemcloud>header{flex-wrap:wrap}.bt-chemcloud .bt-connector-actions{margin-left:0;width:100%;justify-content:flex-end}}
`
