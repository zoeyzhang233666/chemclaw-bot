const { contextBridge, ipcRenderer } = require('electron')
// The routing id is not the WebContents id. Main supplies the channel in the
// page-independent command line so the sandbox exposes only this editor's API.
const channel = process.argv.find(value => value.startsWith('--locations-channel='))?.slice('--locations-channel='.length)
contextBridge.exposeInMainWorld('locations', { request: payload => ipcRenderer.invoke(channel, payload) })
