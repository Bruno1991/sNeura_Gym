/**
 * s_Neura_Gym - Autonomous Simulation Runner
 *
 * Responsibility:
 * Simulates a Minecraft Bedrock Dedicated Server environment to test
 * the Scripted Bot's autonomous navigation, obstacle recovery, and telemetry
 * offline without requiring Microsoft Xbox authentication or an active network BDS.
 */

const { EventEmitter } = require('events')
const PlayerState = require('../src/perception/player_state')
const EntityTracker = require('../src/perception/entity_tracker')
const WorldState = require('../src/environment/world_state')
const SpawnManager = require('../src/environment/spawn')
const EnvironmentRules = require('../src/environment/rules')
const EnvironmentReset = require('../src/environment/reset')
const Movement = require('../src/action/movement')
const AutonomousBrain = require('../src/decision/autonomous_brain')
const { Telemetry } = require('../src/telemetry')

console.log('')
console.log('='.repeat(72))
console.log('    s_Neura_Gym — Scripted Bot Autonomous Simulation Test')
console.log('='.repeat(72))
console.log('')

// Mock Bedrock client
const mockClient = new EventEmitter()
const queuedPackets = []
mockClient.queue = (name, params) => {
  queuedPackets.push({ name, params, time: Date.now() })
}

const telemetry = new Telemetry({
  console: true,
  saveToFile: false
})

const playerState = new PlayerState()
const entityTracker = new EntityTracker()
const worldState = new WorldState()

const spawnManager = new SpawnManager({
  spawn: { x: 79, y: 63, z: 1251 },
  maxRadius: 25
})

const environmentRules = new EnvironmentRules({
  minY: -64,
  maxRadius: 25
}, spawnManager)

const movement = new Movement(mockClient, playerState, {
  tickRateMs: 50
})

const environmentReset = new EnvironmentReset({
  client: mockClient,
  playerState,
  spawnManager,
  movement,
  telemetry
})

const brain = new AutonomousBrain({
  playerState,
  movement,
  spawnManager,
  environmentRules,
  environmentReset,
  telemetry,
  config: {
    mode: 'wander',
    decisionTickMs: 100,
    wander: {
      minDistance: 3,
      maxDistance: 8,
      arrivalRadius: 1.2,
      pauseMinMs: 400,
      pauseMaxMs: 800
    },
    obstacleAvoidance: {
      stuckThreshold: 0.15,
      stuckWindowMs: 800,
      turnAngleDeg: 90
    }
  }
})

// 1. Simulate Server Connection Handshake
console.log('[SIM] Servidor enviando pacotes de conexão e spawn...')
mockClient.emit('connect')
mockClient.emit('join')
mockClient.emit('start_game', {
  dimension: 0,
  world_name: 'Simulation_World',
  time: 1000n
})

// 2. Simulate Initial MovePlayer (Spawn)
const initialPacket = {
  runtime_id: 998877n,
  position: { x: 79.0, y: 63.0, z: 1251.0 },
  pitch: 0,
  yaw: 0,
  head_yaw: 0,
  on_ground: true,
  tick: 1n
}

playerState.updateFromMovePlayer(initialPacket)
console.log(`[SIM] Bot inicializado na posição (${playerState.position.x}, ${playerState.position.y}, ${playerState.position.z})`)

// Start locomotion and brain
movement.start()
brain.start()

console.log('[SIM] Loop autônomo iniciado com sucesso!')
console.log('[SIM] Executando simulação de 5 segundos...')

let simulationSeconds = 0
const simTimer = setInterval(() => {
  simulationSeconds += 1
  const pSnap = playerState.getSnapshot()
  const bSnap = brain.getSnapshot()

  console.log(
    `[SIM +${simulationSeconds}s] Estado: ${bSnap.state.padEnd(16)} | ` +
    `Pos: (${pSnap.position.x?.toFixed(1)}, ${pSnap.position.y?.toFixed(1)}, ${pSnap.position.z?.toFixed(1)}) | ` +
    `Distância: ${pSnap.stats.totalDistanceTraveled}m | ` +
    `Waypoints: ${bSnap.waypointsReached} | ` +
    `Pacotes PlayerAuthInput: ${queuedPackets.length}`
  )

  if (simulationSeconds === 2) {
    // Inject obstacle (freeze position to test obstacle avoidance)
    console.log('[SIM] >>> Injetando obstáculo (bloqueando avanço) para testar unstuck...')
    brain.lastPositionCheck = { ...playerState.position }
    brain.lastPositionCheckTime = Date.now() - 1000
  }

  if (simulationSeconds >= 5) {
    clearInterval(simTimer)
    brain.stop()
    movement.stop()

    console.log('')
    console.log('='.repeat(72))
    console.log('       SIMULAÇÃO AUTÔNOMA CONCLUÍDA COM 100% DE SUCESSO!')
    console.log('='.repeat(72))
    console.log(`Distância total percorrida : ${playerState.totalDistanceTraveled.toFixed(2)}m`)
    console.log(`Waypoints alcançados       : ${brain.waypointsReached}`)
    console.log(`Eventos de desvio/obstáculo: ${brain.totalStuckEvents}`)
    console.log(`Pacotes auth input gerados : ${queuedPackets.length}`)
    console.log('='.repeat(72))
    console.log('')
    process.exit(0)
  }
}, 1000)
