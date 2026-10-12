const bedrock = require('bedrock-protocol')
const config = require('../src/config')

console.log('Connecting to inspect start_game packet...')
const client = bedrock.createClient({
  host: config.server.host,
  port: config.server.port,
  version: config.server.version,
  username: config.player.username,
  offline: config.player.offline
})

client.on('start_game', (packet) => {
  console.log('--- START_GAME RECEIVED ---')
  console.log('entity_id:', packet.entity_id)
  console.log('runtime_entity_id:', packet.runtime_entity_id)
  console.log('player_position:', packet.player_position)
  console.log('rotation:', packet.rotation)
  console.log('server_authoritative_movement_mode:', packet.server_authoritative_movement_mode)
  console.log('server_authoritative_block_breaking:', packet.server_authoritative_block_breaking)
  console.log('rewind_history_size:', packet.rewind_history_size)
  console.log('server_authoritative_sound:', packet.server_authoritative_sound)
  console.log('time:', packet.time)
  console.log('current_tick:', packet.current_tick)
  setTimeout(() => {
    client.disconnect()
    process.exit(0)
  }, 500)
})

client.on('error', (err) => {
  console.error('Error:', err.message)
  process.exit(1)
})
