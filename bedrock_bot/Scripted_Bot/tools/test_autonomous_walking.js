const bedrock = require('bedrock-protocol')
const config = require('../src/config')
const { randomUUID } = require('crypto')

console.log('[TEST] Iniciando teste de navegação autônoma contínua...')

const client = bedrock.createClient({
  host: config.server.host,
  port: config.server.port,
  version: config.server.version,
  username: config.player.username,
  offline: config.player.offline
})

function sendCommand (cmd) {
  client.queue('command_request', {
    command: cmd,
    origin: {
      type: 'player',
      uuid: randomUUID(),
      request_id: '',
      player_entity_id: 0n
    },
    internal: false,
    version: 'latest'
  })
}

let runtimeEntityId = null
let currentPos = null
let waypoints = [
  { x: 92, y: 63, z: 1251 },
  { x: 92, y: 63, z: 1256 },
  { x: 88, y: 63, z: 1256 },
  { x: 88, y: 63, z: 1251 }
]
let currentWpIndex = 0
let stepTimer = null

client.on('start_game', (packet) => {
  runtimeEntityId = packet.runtime_entity_id
  currentPos = {
    x: packet.player_position.x,
    y: packet.player_position.y,
    z: packet.player_position.z
  }
  console.log(`[START_GAME] Pos inicial do servidor: (${currentPos.x.toFixed(2)}, ${currentPos.y.toFixed(2)}, ${currentPos.z.toFixed(2)})`)
})

client.on('move_player', (packet) => {
  if (packet.mode === 'teleport' || packet.mode === 'normal') {
    currentPos = {
      x: packet.position.x,
      y: packet.position.y,
      z: packet.position.z
    }
  }
})

client.on('spawn', () => {
  console.log('[SPAWN] Conectado e spawnado!')

  client.queue('set_local_player_as_initialized', {
    runtime_entity_id: runtimeEntityId
  })

  // Desativa feedback no chat
  sendCommand('/gamerule sendcommandfeedback false')

  setTimeout(() => {
    navigateWaypoints()
  }, 1000)
})

function navigateWaypoints () {
  console.log('[NAV] Iniciando circuito de waypoints...')

  stepTimer = setInterval(() => {
    if (currentWpIndex >= waypoints.length) {
      clearInterval(stepTimer)
      console.log('[NAV] Circuito completo! Todas as waypoints foram visitadas com sucesso!')
      console.log(`[NAV] Posição final confirmada: (${currentPos.x.toFixed(2)}, ${currentPos.y.toFixed(2)}, ${currentPos.z.toFixed(2)})`)
      setTimeout(() => {
        client.disconnect()
        process.exit(0)
      }, 1000)
      return
    }

    const target = waypoints[currentWpIndex]
    const dx = target.x - currentPos.x
    const dz = target.z - currentPos.z
    const dist = Math.hypot(dx, dz)

    // Heading angle
    let yaw = Math.atan2(-dx, dz) * (180 / Math.PI)
    yaw = ((yaw % 360) + 360) % 360

    if (dist <= 0.6) {
      console.log(`[WAYPOINT ${currentWpIndex + 1}] ALCANÇADA! (${currentPos.x.toFixed(2)}, ${currentPos.z.toFixed(2)})`)
      currentWpIndex++
      return
    }

    // Step size 0.35m per 100ms (~3.5 blocks/sec, normal player running/walking speed)
    const stepSpeed = Math.min(0.35, dist)
    const stepX = (dx / dist) * stepSpeed
    const stepZ = (dz / dist) * stepSpeed

    sendCommand(`/tp @s ~${stepX.toFixed(3)} ~ ~${stepZ.toFixed(3)} ${yaw.toFixed(1)} 0`)

    // Envia player_auth_input para animação
    client.queue('player_auth_input', {
      pitch: 0,
      yaw: yaw,
      position: { x: currentPos.x + stepX, y: currentPos.y, z: currentPos.z + stepZ },
      move_vector: { x: 0, z: 1 },
      head_yaw: yaw,
      input_data: ['up'],
      input_mode: 'mouse',
      play_mode: 'normal',
      interaction_model: 'crosshair',
      interact_rotation: { x: 0, y: 0 },
      tick: 0n,
      delta: { x: stepX, y: 0, z: stepZ },
      analogue_move_vector: { x: 0, z: 1 },
      camera_orientation: { x: 0, y: 0, z: 1 },
      raw_move_vector: { x: 0, z: 1 }
    })
  }, 100)
}

client.on('error', (err) => console.error('[ERROR]', err))
