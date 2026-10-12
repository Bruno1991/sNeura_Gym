const bedrock = require('bedrock-protocol')
const config = require('../src/config')

function toBigIntSafe (val, fallback = 0n) {
  if (val === undefined || val === null) return fallback
  if (typeof val === 'bigint') return val
  if (Array.isArray(val)) {
    if (val.length === 2) {
      return (BigInt(val[0] >>> 0) << 32n) | BigInt(val[1] >>> 0)
    }
    if (val.length === 1) {
      try { return BigInt(val[0]) } catch { return fallback }
    }
    return fallback
  }
  try {
    return BigInt(val)
  } catch {
    return fallback
  }
}

async function run() {
  console.log('[TEST] Conectando bot para teste com TICK SINCRONIZADO...')
  const client = bedrock.createClient({
    host: config.server.host,
    port: config.server.port,
    version: config.server.version,
    username: config.player.username,
    offline: config.player.offline
  })

  let runtimeId = null
  let serverTick = 0n
  let pos = null

  client.on('start_game', (packet) => {
    runtimeId = packet.runtime_entity_id
    serverTick = toBigIntSafe(packet.current_tick)
    pos = { ...packet.player_position }
    console.log(`[START_GAME] ID: ${runtimeId}, SyncTick: ${serverTick}, Pos: (${pos.x}, ${pos.y}, ${pos.z})`)
  })

  client.on('correct_player_move_prediction', (packet) => {
    console.log('[SERVER CORRECTION]', packet)
  })

  client.on('spawn', () => {
    console.log(`[SPAWN] Inicializado com serverTick=${serverTick}. Aguardando 1s...`)
    client.queue('set_local_player_as_initialized', {
      runtime_entity_id: runtimeId
    })

    setTimeout(() => {
      console.log('[WALK] Iniciando caminhada de 80 ticks sincronizada com o servidor...')
      let t = 0
      const startX = pos.x

      const interval = setInterval(() => {
        t++
        serverTick += 1n
        const dx = 0.15
        pos.x += dx

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
          tick: serverTick,
          delta: { x: dx, y: 0, z: 0 },
          analogue_move_vector: { x: 0, z: 1 },
          camera_orientation: { x: 1, y: 0, z: 0 },
          raw_move_vector: { x: 0, z: 1 }
        })

        if (t % 20 === 0) {
          console.log(`[CLIENT WALK ${t}] Tick: ${serverTick} | Pos: (${pos.x.toFixed(2)}, ${pos.y.toFixed(2)}, ${pos.z.toFixed(2)})`)
        }

        if (t >= 80) {
          clearInterval(interval)
          console.log(`[CLIENT DONE] Pos final: (${pos.x.toFixed(2)}, ${pos.y.toFixed(2)}, ${pos.z.toFixed(2)})`)
          console.log('Mantendo conectado por 6s para verificação do BDS...')
          setTimeout(() => {
            client.disconnect()
            process.exit(0)
          }, 6000)
        }
      }, 50)
    }, 1000)
  })

  client.on('error', (e) => console.error('[ERROR]', e.message))
}

run()
