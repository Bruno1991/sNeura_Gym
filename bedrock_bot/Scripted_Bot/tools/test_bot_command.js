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

let entityId = 0n

client.on('start_game', (packet) => {
  entityId = packet.entity_id || 0n
})

client.on('spawn', () => {
  console.log('Bot spawned. BDS pos before command:', getBdsPos())
  console.log('Bot sending command_request /tp @s 82 64 1251...')

  try {
    client.queue('command_request', {
      command: '/tp @s 82 64 1251',
      origin: {
        type: 'player',
        uuid: '00000000-0000-0000-0000-000000000000',
        request_id: 'cmd_1',
        player_entity_id: entityId
      },
      internal: false,
      version: '1.26.51'
    })
    console.log('[OK] command_request queued without error!')
  } catch (err) {
    console.error('Queue error:', err)
  }

  setTimeout(() => {
    console.log('BDS pos after bot command:', getBdsPos())
    client.disconnect()
    process.exit(0)
  }, 2000)
})

client.on('error', (e) => console.error(e))
