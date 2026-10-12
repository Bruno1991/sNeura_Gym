const bedrock = require('bedrock-protocol')
const config = require('../src/config')
const { randomUUID } = require('crypto')

console.log('[TEST] Testando caminhada passo-a-passo com command_request...')

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
  // console.log('[OUTPUT]', packet.output)
})

client.on('spawn', () => {
  console.log('[SPAWN] Inicializado!')

  // Desativa feedback no chat para nao poluir a tela do jogador
  sendCommand('/gamerule sendcommandfeedback false')

  let step = 0
  const interval = setInterval(() => {
    step++
    // Anda 0.25 blocos por tick na direcao +X
    sendCommand('/tp @s ~0.25 ~ ~ 270 0')

    if (step % 10 === 0) {
      console.log(`[WALK] Passo ${step} executado (+${(step * 0.25).toFixed(2)}m)`)
    }

    if (step >= 20) {
      clearInterval(interval)
      console.log('[WALK] Finalizado 5 metros de caminhada!')
      setTimeout(() => {
        client.disconnect()
        process.exit(0)
      }, 500)
    }
  }, 100) // 10 passos por segundo = 2.5 blocos por segundo (velocidade real de corrida/caminhada)
})
