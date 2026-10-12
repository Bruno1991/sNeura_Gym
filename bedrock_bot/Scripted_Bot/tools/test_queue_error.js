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
  console.log('Testing packet serialization for player_auth_input and move_player...')
  
  const tick = BigInt(packet.current_tick || 100)
  const pos = packet.player_position
  const runtimeEntityId = packet.runtime_entity_id

  try {
    console.log('Testing player_auth_input...')
    client.queue('player_auth_input', {
      pitch: 0,
      yaw: 0,
      position: { x: pos.x, y: pos.y, z: pos.z },
      move_vector: { x: 0, z: 1 },
      head_yaw: 0,
      input_data: ['up'],
      input_mode: 'mouse',
      play_mode: 'normal',
      interaction_model: 'crosshair',
      interact_rotation: { x: 0, y: 0 },
      tick: tick,
      delta: { x: 0, y: 0, z: 0.2 },
      analogue_move_vector: { x: 0, z: 1 },
      camera_orientation: { x: 0, y: 0, z: 1 },
      raw_move_vector: { x: 0, z: 1 }
    })
    console.log('[OK] player_auth_input queued successfully!')
  } catch (err) {
    console.error('[ERROR in player_auth_input]:', err)
  }

  try {
    console.log('Testing move_player...')
    client.queue('move_player', {
      runtime_id: Number(runtimeEntityId),
      position: { x: pos.x, y: pos.y, z: pos.z },
      pitch: 0,
      yaw: 0,
      head_yaw: 0,
      mode: 'normal',
      on_ground: true,
      ridden_runtime_id: 0,
      teleport: null,
      tick: tick
    })
    console.log('[OK] move_player queued successfully!')
  } catch (err) {
    console.error('[ERROR in move_player]:', err)
  }

  setTimeout(() => {
    client.disconnect()
    process.exit(0)
  }, 1000)
})

client.on('error', (err) => {
  console.error('Client error:', err)
})
