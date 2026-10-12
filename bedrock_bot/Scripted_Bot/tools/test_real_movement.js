const bedrock = require('bedrock-protocol')
const config = require('../src/config')

console.log('[TEST] Iniciando teste de movimento real com runtime_entity_id de start_game...')

const client = bedrock.createClient({
  host: config.server.host,
  port: config.server.port,
  version: config.server.version,
  username: config.player.username,
  offline: config.player.offline
})

let runtimeEntityId = null
let currentTick = 0n
let pos = null
let yaw = 270 // Heading East (+X)
let pitch = 0
let startedWalking = false
let tickCount = 0

client.on('start_game', (packet) => {
  runtimeEntityId = packet.runtime_entity_id
  currentTick = BigInt(packet.current_tick || 0)
  pos = {
    x: packet.player_position.x,
    y: packet.player_position.y,
    z: packet.player_position.z
  }
  console.log(`[START_GAME] ID: ${runtimeEntityId} | Tick: ${currentTick} | Pos: (${pos.x.toFixed(2)}, ${pos.y.toFixed(2)}, ${pos.z.toFixed(2)})`)
})

client.on('packet', (packet) => {
  const name = packet.data.name
  const params = packet.data.params
  if (name === 'correct_player_move_prediction' || name === 'player_auth_input_decrement' || name === 'move_player') {
    if (name === 'move_player' && runtimeEntityId && BigInt(params.runtime_id) === BigInt(runtimeEntityId)) {
      console.log(`[SERVER MOVE_PLAYER for BOT] mode: ${params.mode} pos: (${params.position.x.toFixed(2)}, ${params.position.y.toFixed(2)}, ${params.position.z.toFixed(2)}) tick: ${params.tick}`)
    } else if (name !== 'move_player') {
      console.log(`[SERVER CORRECTION] ${name}:`, params)
    }
  }
})

client.on('spawn', () => {
  console.log('[SPAWN] Evento spawn recebido!')

  client.queue('set_local_player_as_initialized', {
    runtime_entity_id: runtimeEntityId
  })

  setTimeout(() => {
    startMoving()
  }, 1000)
})

function startMoving () {
  if (startedWalking) return
  startedWalking = true

  const startX = pos.x
  const startZ = pos.z
  console.log(`[MOVE] Iniciando caminhada de 60 ticks (~3s). Posição inicial: (${startX.toFixed(2)}, ${pos.y.toFixed(2)}, ${startZ.toFixed(2)})`)

  const interval = setInterval(() => {
    tickCount++
    currentTick += 1n

    const speed = 0.215
    const yawRad = (yaw * Math.PI) / 180
    const pitchRad = (pitch * Math.PI) / 180

    const forwardX = -Math.sin(yawRad) * speed
    const forwardZ = Math.cos(yawRad) * speed

    pos.x += forwardX
    pos.z += forwardZ

    const camX = -Math.sin(yawRad) * Math.cos(pitchRad)
    const camY = -Math.sin(pitchRad)
    const camZ = Math.cos(yawRad) * Math.cos(pitchRad)

    // Send player_auth_input
    client.queue('player_auth_input', {
      pitch: pitch,
      yaw: yaw,
      position: { x: pos.x, y: pos.y, z: pos.z },
      move_vector: { x: 0, z: 1 },
      head_yaw: yaw,
      input_data: ['up'],
      input_mode: 'mouse',
      play_mode: 'normal',
      interaction_model: 'crosshair',
      interact_rotation: { x: 0, y: 0 },
      tick: currentTick,
      delta: { x: forwardX, y: 0, z: forwardZ },
      analogue_move_vector: { x: 0, z: 1 },
      camera_orientation: { x: camX, y: camY, z: camZ },
      raw_move_vector: { x: 0, z: 1 }
    })

    // Also send move_player
    client.queue('move_player', {
      runtime_id: Number(runtimeEntityId),
      position: { x: pos.x, y: pos.y, z: pos.z },
      pitch: pitch,
      yaw: yaw,
      head_yaw: yaw,
      mode: 'normal',
      on_ground: true,
      ridden_runtime_id: 0,
      teleport: null,
      tick: currentTick
    })

    if (tickCount % 20 === 0) {
      const moved = Math.hypot(pos.x - startX, pos.z - startZ)
      console.log(`[TICK ${tickCount}] Posição: (${pos.x.toFixed(2)}, ${pos.y.toFixed(2)}, ${pos.z.toFixed(2)}) | Deslocamento: ${moved.toFixed(2)}m`)
    }

    if (tickCount >= 60) {
      clearInterval(interval)
      const totalMoved = Math.hypot(pos.x - startX, pos.z - startZ)
      console.log(`[MOVE END] Caminhada concluída! Total deslocado: ${totalMoved.toFixed(2)}m`)
      setTimeout(() => {
        client.disconnect()
        console.log('[TEST] Desconectado com sucesso.')
        process.exit(0)
      }, 1000)
    }
  }, 50)
}

client.on('error', (err) => {
  console.error('[ERROR]', err.message)
})
