const bedrock = require('bedrock-protocol')
const config = require('../src/config')

console.log('[TEST] Conectando ao BDS para teste de locomoção real...')

const client = bedrock.createClient({
  host: config.server.host,
  port: config.server.port,
  version: config.server.version,
  username: config.player.username,
  offline: config.player.offline
})

let runtimeEntityId = null
let serverTick = 0n
let pos = null
let currentYaw = 0
let walking = false
let tickCount = 0

client.on('start_game', (packet) => {
  console.log('[TEST] start_game recebido.')
  if (packet.time !== undefined) {
    serverTick = BigInt(packet.time)
  }
})

client.on('spawn', () => {
  console.log('[TEST] client emitiu spawn!')
})

client.on('move_player', (packet) => {
  if (runtimeEntityId === null) {
    runtimeEntityId = Number(packet.runtime_id)
    serverTick = BigInt(packet.tick)
    pos = { ...packet.position }
    currentYaw = packet.yaw || 0
    console.log(`[TEST] Spawn inicial em (${pos.x.toFixed(2)}, ${pos.y.toFixed(2)}, ${pos.z.toFixed(2)}) | Tick: ${serverTick}`)

    startWalking()
  } else {
    // Only log if mode is not normal or if position differs significantly
    const dist = Math.hypot(packet.position.x - pos.x, packet.position.z - pos.z)
    if (packet.mode !== 'normal' || dist > 1.0) {
      console.log(`[SERVER SYNC] mode=${packet.mode} serverPos=(${packet.position.x.toFixed(2)}, ${packet.position.z.toFixed(2)}) dist=${dist.toFixed(2)}m`)
    }
  }
})

function startWalking () {
  if (walking) return
  walking = true

  console.log('[TEST] Iniciando caminhada de 4 segundos para o Leste (+X)...')
  // In Bedrock: East (+X) is yaw = 270
  currentYaw = 270

  const interval = setInterval(() => {
    tickCount++
    serverTick += 1n

    // Speed: ~0.215 blocks per tick
    const speed = 0.215
    const dx = speed
    const dz = 0
    pos.x += dx

    // Queue player_auth_input
    client.queue('player_auth_input', {
      pitch: 0,
      yaw: currentYaw,
      position: { x: pos.x, y: pos.y, z: pos.z },
      move_vector: { x: 0, z: 1 },
      head_yaw: currentYaw,
      input_data: ['up'],
      input_mode: 'mouse',
      play_mode: 'normal',
      interaction_model: 'crosshair',
      interact_rotation: { x: 0, y: 0 },
      tick: serverTick,
      delta: { x: dx, y: 0, z: dz },
      analogue_move_vector: { x: 0, z: 1 },
      camera_orientation: { x: 0, y: 0, z: 0 },
      raw_move_vector: { x: 0, z: 1 }
    })

    // Also queue move_player
    client.queue('move_player', {
      runtime_id: runtimeEntityId,
      position: { x: pos.x, y: pos.y, z: pos.z },
      pitch: 0,
      yaw: currentYaw,
      head_yaw: currentYaw,
      mode: 'normal',
      on_ground: true,
      ridden_runtime_id: 0,
      teleport: null,
      tick: serverTick
    })

    if (tickCount % 20 === 0) {
      console.log(`[WALK TICK ${tickCount}] Posição cliente: (${pos.x.toFixed(2)}, ${pos.y.toFixed(2)}, ${pos.z.toFixed(2)})`)
    }

    if (tickCount >= 80) { // 4 seconds at 20 ticks/sec
      clearInterval(interval)
      console.log(`[TEST] Caminhada concluída. Posição final: (${pos.x.toFixed(2)}, ${pos.y.toFixed(2)}, ${pos.z.toFixed(2)})`)
      setTimeout(() => {
        client.disconnect()
        process.exit(0)
      }, 1000)
    }
  }, 50)
}

setTimeout(() => {
  console.log('[TIMEOUT] Encerrando teste.')
  client.disconnect()
  process.exit(0)
}, 10000)
