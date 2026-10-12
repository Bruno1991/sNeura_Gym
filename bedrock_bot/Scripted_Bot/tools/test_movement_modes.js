const bedrock = require('bedrock-protocol')
const config = require('../src/config')
const fs = require('fs')

async function run() {
  console.log('[TEST] Conectando bot para teste comparativo de movimento...')
  const client = bedrock.createClient({
    host: config.server.host,
    port: config.server.port,
    version: config.server.version,
    username: config.player.username,
    offline: config.player.offline
  })

  let runtimeId = null
  let tick = 0n
  let pos = null

  client.on('start_game', (packet) => {
    runtimeId = packet.runtime_entity_id
    tick = BigInt(packet.current_tick || 0)
    pos = { ...packet.player_position }
    console.log(`[START_GAME] ID: ${runtimeId}, Tick: ${tick}, Pos: (${pos.x}, ${pos.y}, ${pos.z})`)
  })

  client.on('spawn', () => {
    console.log('[SPAWN] Inicializado. Aguardando 1s...')
    client.queue('set_local_player_as_initialized', {
      runtime_entity_id: runtimeId
    })

    setTimeout(() => {
      console.log('[WALK] Testando 60 ticks com Y fixo no solo (64.62)...')
      // Set feet on ground Y=63.0 -> Eye Y=64.62
      pos.y = 64.62
      let t = 0
      const startX = pos.x

      const interval = setInterval(() => {
        t++
        tick += 1n
        const dx = 0.15
        pos.x += dx

        // Queue player_auth_input
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
          delta: { x: dx, y: 0, z: 0 },
          analogue_move_vector: { x: 0, z: 1 },
          camera_orientation: { x: 1, y: 0, z: 0 },
          raw_move_vector: { x: 0, z: 1 }
        })

        if (t % 20 === 0) {
          console.log(`[CLIENT WALK ${t}] Pos: (${pos.x.toFixed(2)}, ${pos.y.toFixed(2)}, ${pos.z.toFixed(2)})`)
        }

        if (t >= 60) {
          clearInterval(interval)
          console.log(`[CLIENT DONE] Pos final: (${pos.x.toFixed(2)}, ${pos.y.toFixed(2)}, ${pos.z.toFixed(2)})`)
          console.log('Mantendo conectado por mais 5s para checagem do BDS...')
          setTimeout(() => {
            client.disconnect()
            process.exit(0)
          }, 5000)
        }
      }, 50)
    }, 1000)
  })

  client.on('error', (e) => console.error('[ERROR]', e.message))
}

run()
