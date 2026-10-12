const bedrock = require('bedrock-protocol')
const config = require('../src/config')

console.log('Connecting to observe AerialTuba9051...')
const client = bedrock.createClient({
  host: config.server.host,
  port: config.server.port,
  version: config.server.version,
  username: config.player.username,
  offline: config.player.offline
})

client.on('packet', (packet) => {
  const name = packet.data.name
  const p = packet.data.params
  if (name.includes('move') || name.includes('auth') || name.includes('motion')) {
    const s = JSON.stringify(p, (k, v) => typeof v === 'bigint' ? v.toString() : v)
    if (s.includes('29') || name === 'player_auth_input' || name === 'move_player') {
      console.log(`[PACKET ${name}]:`, s)
    }
  }
})

setTimeout(() => {
  client.disconnect()
  process.exit(0)
}, 8000)
