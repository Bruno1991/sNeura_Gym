const bedrock = require('bedrock-protocol')
const config = require('../src/config')
const { execSync } = require('child_process')

function runCmd(cmd) {
  return execSync(`python c:\\dev\\s_Bedrock_Server\\windows\\bds_cmd.py "${cmd}"`).toString()
}

function getBdsPos() {
  runCmd('execute at @e[name=x12ultimatepass] run spawnpoint x12ultimatepass ~ ~ ~')
  const output = execSync('python c:\\dev\\s_Bedrock_Server\\windows\\read_bds_console.py').toString()
  const match = output.match(/Set x12ultimatepass's spawn point to \(([^)]+)\)/g)
  if (match && match.length > 0) {
    return match[match.length - 1]
  }
  return 'unknown'
}

console.log('Connecting bot...')
const client = bedrock.createClient({
  host: config.server.host,
  port: config.server.port,
  version: config.server.version,
  username: config.player.username,
  offline: config.player.offline
})

client.on('spawn', () => {
  console.log('Bot spawned. Current BDS pos:', getBdsPos())
  console.log('Executing /tp x12ultimatepass 87 64 1251 from console...')
  runCmd('tp x12ultimatepass 87 64 1251')
  setTimeout(() => {
    console.log('BDS pos after /tp:', getBdsPos())
    client.disconnect()
    process.exit(0)
  }, 1000)
})

client.on('error', (e) => console.error(e))
