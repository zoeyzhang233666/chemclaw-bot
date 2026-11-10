export async function checkTeamReady(ctx) {
  const team = ctx.get('chemclawReady')
  if (typeof team?.check !== 'function' || await team.check() !== true) {
    throw new Error('The required ChemClaw team plugin did not start. Check the ChemClaw plugin and profile configuration before restarting.')
  }
}
