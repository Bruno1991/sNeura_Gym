const bedrock = require('bedrock-protocol')
const config = require('../src/config')

const client = bedrock.createClient({
  host: config.server.host,
  port: config.server.port,
  version: config.server.version,
  username: config.player.username,
  offline: config.player.offline
})

client.on('start_game', (packet) => {
  console.log('client.startGameData runtime_entity_id:', client.startGameData?.runtime_entity_id)
  console.log('packet keys:', Object.keys(packet).join(', '))
  setTimeout(() => {
    client.disconnect()
    process.exit(0)
  }, 500)
})
