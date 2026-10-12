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

console.log('Connecting bot for physics test...')
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
})

client.on('spawn', () => {
  console.log('Initial BDS pos:', getBdsPos())
  console.log('Starting Minecraft standard acceleration physics loop...')

  // Minecraft standard ground acceleration physics
  let vx = 0
  let vz = 0
  const slipperiness = 0.6
  const friction = 0.91 * slipperiness // 0.546
  // Acceleration factor for walking on ground
  const accel = 0.1 * Math.pow(0.6 / (0.91 * slipperiness), 3) // ~0.098

  // We want to walk East (yaw = 270 deg -> -sin(270) = +1 in X)
  const yaw = 270
  const yawRad = (yaw * Math.PI) / 180

  let count = 0
  const interval = setInterval(() => {
    count++
    tick += 1n

    // In Minecraft:
    // Move vector is normalized input
    // vx += -sin(yaw) * accel
    vx += -Math.sin(yawRad) * accel
    vz += Math.cos(yawRad) * accel

    pos.x += vx
    pos.z += vz

    // Apply friction for next tick
    vx *= friction
    vz *= friction

    client.queue('player_auth_input', {
      pitch: 0,
      yaw: yaw,
      position: { x: pos.x, y: pos.y, z: pos.z },
      move_vector: { x: 0, z: 1 },
      head_yaw: yaw,
      input_data: ['up'],
      input_mode: 'mouse',
      play_mode: 'normal',
      interaction_model: 'crosshair',
      interact_rotation: { x: 0, y: 0 },
      tick: tick,
      delta: { x: vx, y: 0, z: vz },
      analogue_move_vector: { x: 0, z: 1 },
      camera_orientation: { x: 1, y: 0, z: 0 },
      raw_move_vector: { x: 0, z: 1 }
    })

    if (count % 20 === 0) {
      console.log(`Tick ${count}: client pos (${pos.x.toFixed(2)}, ${pos.z.toFixed(2)})`)
    }

    if (count >= 60) {
      clearInterval(interval)
      setTimeout(() => {
        console.log('Final BDS pos:', getBdsPos())
        client.disconnect()
        process.exit(0)
      }, 1000)
    }
  }, 50)
})

client.on('error', (e) => console.error(e))
