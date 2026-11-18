import { prepareMacInstall as prepare } from '../../src/mac-install.mjs'
export { MAC_INSTALL_TEXT } from '../../src/mac-install.mjs'

export const prepareMacInstall = options => prepare({ ...options, platform: 'darwin', isolated: false,
  app: { isPackaged: true, isInApplicationsFolder: () => false, quit: () => options.app.quit() },
})
