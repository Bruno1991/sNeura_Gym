const bedrock = require('bedrock-protocol')
const config = require('../src/config')
const { randomUUID } = require('crypto')

console.log('[TEST] Testando command_request /tp @s no BDS 1.26...')

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

client.on('start_game', (packet) => {
  runtimeEntityId = packet.runtime_entity_id
  pos = {
    x: packet.player_position.x,
    y: packet.player_position.y,
    z: packet.player_position.z
  }
  console.log(`[START_GAME] Pos inicial: (${pos.x.toFixed(2)}, ${pos.y.toFixed(2)}, ${pos.z.toFixed(2)})`)
})

client.on('command_output', (packet) => {
  console.log('[COMMAND OUTPUT]', JSON.stringify(packet.output))
})

client.on('packet_violation_warning', (packet) => {
  console.error('[PACKET VIOLATION WARNING]', packet)
})

client.on('spawn', () => {
  console.log('[SPAWN] Evento spawn recebido!')

  client.queue('set_local_player_as_initialized', {
    runtime_entity_id: runtimeEntityId
  })

  setTimeout(() => {
    // Try sending command_request /tp @s ~1 ~ ~
    const reqUuid = randomUUID()
    console.log('[TEST] Enviando comando: /tp @s ~1 ~ ~')
    client.queue('command_request', {
      command: '/tp @s ~1 ~ ~',
      origin: {
        type: 'player',
        uuid: reqUuid,
        request_id: '',
        player_entity_id: 0n
      },
      internal: false,
      version: 'latest'
    })

    setTimeout(() => {
      console.log('[TEST] Teste concluído, desconectando...')
      client.disconnect()
      process.exit(0)
    }, 2000)
  }, 1000)
})

client.on('error', (err) => {
  console.error('[ERROR]', err)
})
