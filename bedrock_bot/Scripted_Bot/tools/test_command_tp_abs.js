const bedrock = require('bedrock-protocol')
const config = require('../src/config')
const { randomUUID } = require('crypto')

console.log('[TEST] Testando command_request com coordenadas absolutas e rotação...')

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

client.on('command_output', (packet) => {
  console.log('[COMMAND OUTPUT]', JSON.stringify(packet.output))
})

client.on('spawn', () => {
  console.log('[SPAWN] Conectado!')

  // Desativa feedback no chat
  sendCommand('/gamerule sendcommandfeedback false')

  setTimeout(() => {
    // Test absolute tp with yaw and pitch
    console.log('[TEST] Teleportando para 90.00 63.00 1250.00 com yaw 180 pitch 0...')
    sendCommand('/tp @s 90.00 63.00 1250.00 180 0')

    setTimeout(() => {
      console.log('[TEST] Concluído.')
      client.disconnect()
      process.exit(0)
    }, 1500)
  }, 1000)
})
