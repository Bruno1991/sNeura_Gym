const bedrock = require('bedrock-protocol')
const config = require('../src/config')

console.log('Connecting to server to listen to incoming packets...')

const client = bedrock.createClient({
  host: config.server.host,
  port: config.server.port,
  version: config.server.version,
  username: config.player.username,
  offline: config.player.offline
})

let packetCount = 0

client.on('packet', (packet) => {
  packetCount++
  const name = packet.data.name
  const params = packet.data.params

  if (name.includes('move') || name.includes('auth') || name.includes('correct') || name.includes('sync') || name.includes('teleport')) {
    const safeStr = JSON.stringify(params, (k, v) => typeof v === 'bigint' ? v.toString() : v)
    console.log(`[PACKET ${packetCount}] ${name}:`, safeStr)
  }
})

client.on('disconnect', (reason) => {
  console.log('Disconnected:', reason)
  process.exit(0)
})

client.on('error', (err) => {
  console.log('Error:', err.message)
})

setTimeout(() => {
  console.log('Done listening.')
  client.disconnect()
  process.exit(0)
}, 5000)
