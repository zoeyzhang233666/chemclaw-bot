export const MAC_INSTALL_TEXT = {
  en: {
    message: 'Install ChemClaw in Applications before starting.',
    detail: 'ChemClaw will move to Applications and restart before starting your team. Keep the app in place while it is running. Your conversations and settings stay in their current data folder.',
    install: 'Move to Applications', quit: 'Quit',
    conflict: 'ChemClaw is already in Applications.',
    conflictDetail: 'No application was replaced. Quit ChemClaw, then use Finder to replace the old app before opening the installed copy.',
    failed: 'ChemClaw could not move to Applications.',
    failedDetail: 'No team was started. Quit, move ChemClaw.app to Applications in Finder, then open it there.',
  },
  zh: {
    message: '请先将 ChemClaw 安装到“应用程序”。',
    detail: 'ChemClaw 将移到“应用程序”并重启，然后才启动团队。运行期间请保持应用位置不变。对话和设置仍保存在原来的数据目录。',
    install: '移到“应用程序”', quit: '退出',
    conflict: '“应用程序”中已经有 ChemClaw。',
    conflictDetail: '没有替换已有应用。请退出 ChemClaw，再通过访达替换旧应用，然后打开已安装的副本。',
    failed: '无法将 ChemClaw 移到“应用程序”。',
    failedDetail: '团队尚未启动。请退出，在访达中将 ChemClaw.app 移到“应用程序”，然后从那里打开。',
  },
}

export async function prepareMacInstall({ app, dialog, messages, platform = process.platform,
  isolated = Boolean(process.env.DS_BOT_HOME),
}) {
  if (platform !== 'darwin' || !app.isPackaged || isolated || app.isInApplicationsFolder()) return true
  const t = messages
  const { response } = await dialog.showMessageBox({ type: 'info', title: 'ChemClaw', message: t.message, detail: t.detail, buttons: [t.install, t.quit], defaultId: 0, cancelId: 1, noLink: true })
  if (response !== 0) { app.quit(); return false }
  let conflict = false
  try {
    const moved = app.moveToApplicationsFolder({ conflictHandler: () => { conflict = true; return false } })
    // The official API quits and relaunches on success; this process must not boot DSH.
    if (moved) return false
  } catch { /* The native message below also covers a cancelled or failed move. */ }
  await dialog.showMessageBox({ type: 'warning', title: 'ChemClaw', message: conflict ? t.conflict : t.failed, detail: conflict ? t.conflictDetail : t.failedDetail, buttons: [t.quit], defaultId: 0, cancelId: 0, noLink: true })
  app.quit()
  return false
}
