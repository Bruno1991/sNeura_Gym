const bedrock = require('bedrock-protocol')
const config = require('../src/config')

console.log('[INSPECT] Conectando para inspecionar resposta do servidor ao movimento...')

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
let walking = false
let packetLog = []

client.on('start_game', (packet) => {
  runtimeEntityId = packet.runtime_entity_id
  tick = BigInt(packet.current_tick || 0)
  pos = { ...packet.player_position }
  console.log(`[START_GAME] ID: ${runtimeEntityId} | Tick: ${tick} | Pos: (${pos.x.toFixed(2)}, ${pos.y.toFixed(2)}, ${pos.z.toFixed(2)})`)
})

client.on('packet', (packet) => {
  const name = packet.data.name
  const params = packet.data.params
  // Log packets related to player, movement, corrections, entities, physics
  if (
    name.includes('move') ||
    name.includes('auth') ||
    name.includes('correct') ||
    name.includes('sync') ||
    name.includes('teleport') ||
    name.includes('motion') ||
    name.includes('tick') ||
    name.includes('play_status')
  ) {
    console.log(`[RECV from SERVER] ${name}:`, JSON.stringify(params, (k, v) => typeof v === 'bigint' ? v.toString() : v))
  }
})

client.on('spawn', () => {
  console.log('[SPAWN] Evento spawn!')
  setTimeout(() => {
    startMoving()
  }, 1000)
})

function startMoving() {
  if (walking) return
  walking = true
  console.log('[INSPECT] Enviando 30 ticks de player_auth_input e move_player...')

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

    if (count >= 30) {
      clearInterval(interval)
      console.log('[INSPECT] Envio concluído. Aguardando 3s por respostas do servidor...')
      setTimeout(() => {
        client.disconnect()
        process.exit(0)
      }, 3000)
    }
  }, 50)
}

client.on('error', (err) => {
  console.error('[CLIENT ERROR]:', err.message)
})
