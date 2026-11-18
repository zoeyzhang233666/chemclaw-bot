export const MAC_INSTALL_TEXT = {
  en: {
    message: 'Install ChemClaw in Applications before starting.',
    detail: 'Quit ChemClaw, then drag ChemClaw.app onto Applications in the disk image window. If you downloaded a ZIP, drag the extracted app to Applications in Finder. Open the installed copy there. Quit any older copy before replacing it. Your team has not started; saved conversations and settings stay in their data folder.',
    quit: 'Quit',
  },
  zh: {
    message: '请先将 ChemClaw 安装到“应用程序”。',
    detail: '请先退出 ChemClaw，再在安装盘窗口中将 ChemClaw.app 拖到“应用程序”。如果下载的是 ZIP，请将解压后的应用拖到访达的“应用程序”。然后从“应用程序”打开已安装的副本。替换旧版前，请先将旧版完全退出。团队尚未启动，已有对话和设置仍保存在原来的数据目录。',
    quit: '退出',
  },
}

export async function prepareMacInstall({ app, dialog, messages, platform = process.platform,
  isolated = Boolean(process.env.DS_BOT_HOME),
}) {
  if (platform !== 'darwin' || !app.isPackaged || isolated || app.isInApplicationsFolder()) return true
  const t = messages
  // Moving a running bundle can invalidate Electron's cached Helper path.
  try {
    await dialog.showMessageBox({ type: 'info', title: 'ChemClaw', message: t.message, detail: t.detail, buttons: [t.quit], defaultId: 0, cancelId: 0, noLink: true })
  } finally { app.quit() }
  return false
}
