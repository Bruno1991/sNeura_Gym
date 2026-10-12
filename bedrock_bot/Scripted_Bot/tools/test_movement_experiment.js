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

console.log('1. Connecting bot...')
const client = bedrock.createClient({
  host: config.server.host,
  port: config.server.port,
  version: config.server.version,
  username: config.player.username,
  offline: config.player.offline
})

let runtimeEntityId = null
let tick = 0n
let pos = null

client.on('start_game', (packet) => {
  runtimeEntityId = packet.runtime_entity_id
  tick = BigInt(packet.current_tick || 0)
  pos = { ...packet.player_position }
  console.log(`[START_GAME] ID: ${runtimeEntityId}, Tick: ${tick}, Pos: (${pos.x}, ${pos.y}, ${pos.z})`)
})

client.on('spawn', () => {
  console.log('[SPAWN] Checking initial BDS pos...')
  console.log('BDS initial pos:', getBdsPos())

  console.log('Testing sending dual movement packets under new server configuration...')
  let count = 0
  const interval = setInterval(() => {
    count++
    tick += 1n
    pos.x += 0.2

    client.queue('player_auth_input', {
      pitch: 0,
      yaw: 270,
      position: { x: pos.x, y: pos.y, z: pos.z },
      move_vector: { x: 0, z: 1 },
      head_yaw: 270,
      input_data: ['up'],
      input_mode: 'mouse',
      play_mode: 'normal',
      interaction_model: 'crosshair',
      interact_rotation: { x: 0, y: 0 },
      tick: tick,
      delta: { x: 0.2, y: 0, z: 0 },
      analogue_move_vector: { x: 0, z: 1 },
      camera_orientation: { x: 1, y: 0, z: 0 },
      raw_move_vector: { x: 0, z: 1 }
    })

    client.queue('move_player', {
      runtime_id: Number(runtimeEntityId),
      position: { x: pos.x, y: pos.y, z: pos.z },
      pitch: 0,
      yaw: 270,
      head_yaw: 270,
      mode: 'normal',
      on_ground: true,
      ridden_runtime_id: 0,
      teleport: null,
      tick: tick
    })

    if (count >= 40) {
      clearInterval(interval)
      setTimeout(() => {
        console.log('BDS pos after dual movement:', getBdsPos())
        client.disconnect()
        process.exit(0)
      }, 1000)
    }
  }, 50)
})

client.on('error', (e) => console.error('Error:', e))
