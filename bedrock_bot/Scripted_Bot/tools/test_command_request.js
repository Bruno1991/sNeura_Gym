const bedrock = require('bedrock-protocol')
const config = require('../src/config')
const { execSync } = require('child_process')

function getBdsPos() {
  execSync('python c:\\dev\\s_Bedrock_Server\\windows\\bds_cmd.py "execute at @e[name=x12ultimatepass] run spawnpoint x12ultimatepass ~ ~ ~"')
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
  console.log('Bot spawned. Initial BDS pos:', getBdsPos())
  console.log('Sending command_request: /tp @s 90 64 1251...')

  try {
    client.queue('command_request', {
      command: '/tp @s 90 64 1251',
      origin: {
        type: 'player',
        uuid: client.profile?.uuid || '00000000-0000-0000-0000-000000000000',
        request_id: 'test_cmd_1'
      },
      internal: false,
      version: '1.26.51'
    })
    console.log('[OK] command_request queued!')
  } catch (err) {
    console.error('Error queueing command_request:', err)
  }

  setTimeout(() => {
    console.log('BDS pos after command_request:', getBdsPos())
    client.disconnect()
    process.exit(0)
  }, 1500)
})

client.on('error', (e) => console.error(e))
