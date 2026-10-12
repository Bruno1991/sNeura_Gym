/**
 * s_Neura_Gym - Scripted Bot
 *
 * Responsibility:
 * Starts the external Minecraft Bedrock client, coordinates perception,
 * action, environment rules, and the autonomous decision engine.
 *
 * Manages connection lifecycle and automatic reconnection.
 */

const bedrock = require('bedrock-protocol')

const config = require('./config')
const telemetry = require('./telemetry')
const PlayerState = require('./perception/player_state')
const EntityTracker = require('./perception/entity_tracker')
const WorldState = require('./environment/world_state')
const SpawnManager = require('./environment/spawn.js')
const EnvironmentRules = require('./environment/rules.js')
const EnvironmentReset = require('./environment/reset.js')
const Movement = require('./action/movement')
const AutonomousBrain = require('./decision/autonomous_brain')

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

class ScriptedBotApp {
  constructor (appConfig = config) {
    this.config = appConfig
    this.client = null
    this.reconnectAttempts = 0
    this.reconnectTimer = null
    this.summaryTimer = null
    this.isShuttingDown = false
    this.initialized = false

    // Instantiate core modules
    this.playerState = new PlayerState()
    this.entityTracker = new EntityTracker()
    this.worldState = new WorldState()
    this.spawnManager = new SpawnManager({
      spawn: this.config.environment.spawn,
      maxRadius: this.config.environment.maxRadius
    })
    this.environmentRules = new EnvironmentRules({
      minY: this.config.environment.minY,
      maxRadius: this.config.environment.maxRadius
    }, this.spawnManager)

    this.movement = new Movement(null, this.playerState, {
      tickRateMs: this.config.autonomy.movementTickMs,
      authoritativeDriver: true
    })

    this.environmentReset = new EnvironmentReset({
      client: null,
      playerState: this.playerState,
      spawnManager: this.spawnManager,
      movement: this.movement,
      telemetry: telemetry
    })

    this.brain = new AutonomousBrain({
      playerState: this.playerState,
      movement: this.movement,
      spawnManager: this.spawnManager,
      environmentRules: this.environmentRules,
      environmentReset: this.environmentReset,
      telemetry: telemetry,
      config: this.config.autonomy
    })
  }

  printBanner () {
    console.log('')
    console.log('='.repeat(72))
    console.log('         s_Neura_Gym — Scripted Bot (Autonomous Baseline)')
    console.log('='.repeat(72))
    console.log(`Servidor    : ${this.config.server.host}:${this.config.server.port}`)
    console.log(`Versão BDS  : ${this.config.server.version}`)
    console.log(`Jogador     : ${this.config.player.username} (Offline: ${this.config.player.offline})`)
    console.log(`Spawn       : X=${this.config.environment.spawn.x} Y=${this.config.environment.spawn.y} Z=${this.config.environment.spawn.z}`)
    console.log(`Raio Máx    : ${this.config.environment.maxRadius} blocos`)
    console.log(`Autonomia   : Modo '${this.config.autonomy.mode}' (Tick: ${this.config.autonomy.decisionTickMs}ms)`)
    console.log('='.repeat(72))
    console.log('')
  }

  start () {
    this.printBanner()

    telemetry.emit('bot_start', {
      server: this.config.server,
      username: this.config.player.username,
      environment: this.config.environment,
      autonomy: this.config.autonomy
    })

    this.connect()
    this._startSummaryReporting()
    this._setupSignalHandlers()
  }

  connect () {
    if (this.isShuttingDown) return

    console.log(`[CLIENT] Conectando a ${this.config.server.host}:${this.config.server.port}...`)

    try {
      this.client = bedrock.createClient({
        host: this.config.server.host,
        port: this.config.server.port,
        version: this.config.server.version,
        username: this.config.player.username,
        offline: this.config.player.offline,

        onMsaCode: (data) => {
          console.log('')
          console.log('[AUTH] Autenticação Microsoft necessária.')
          console.log(`[AUTH] Código: ${data.user_code}`)
          console.log(`[AUTH] URL   : ${data.verification_uri}`)
          console.log('')
          console.log('[AUTH] Abra a URL acima e informe o código.')
          console.log('')
        }
      })

      this.movement.setClient(this.client)
      this.environmentReset.setClient(this.client)

      this._bindPacketHandlers(this.client)
    } catch (err) {
      console.error(`[CLIENT] Falha ao criar conexão: ${err.message}`)
      this._scheduleReconnect()
    }
  }

  _bindPacketHandlers (client) {
    client.on('connect', () => {
      console.log('[CLIENT] Conexão de transporte estabelecida.')
      this.reconnectAttempts = 0
      telemetry.emit('transport_connected')
    })

    client.on('join', () => {
      console.log('[CLIENT] Bot ingressou na sessão do servidor.')
      telemetry.emit('player_joined')
    })

    client.on('spawn', () => {
      console.log('[CLIENT] Pacote de spawn recebido.')
      telemetry.emit('player_spawned')

      const state = this.playerState.getSnapshot()
      if (state.runtimeEntityId !== null) {
        try {
          client.queue('set_local_player_as_initialized', {
            runtime_entity_id: toBigIntSafe(state.runtimeEntityId)
          })
        } catch (e) {}
      }

      if (!this.initialized && state.position.x !== null) {
        this.initialized = true

        telemetry.emit('player_initialized', {
          runtimeEntityId: state.runtimeEntityId,
          spawnPosition: state.position
        })

        console.log(`[CLIENT] Jogador inicializado em (${state.position.x.toFixed(2)}, ${state.position.y.toFixed(2)}, ${state.position.z.toFixed(2)})`)

        // Start locomotion and autonomous decision loop
        this.movement.start()
        this.brain.start()

        console.log(`[AUTONOMY] Cérebro autônomo iniciado em modo '${this.brain.mode}'.`)
      }
    })

    client.on('start_game', (packet) => {
      this.worldState.updateFromStartGame(packet)
      this.playerState.initFromStartGame(packet)
      telemetry.emit('world_start_game', this.worldState.getSnapshot())
    })

    client.on('set_time', (packet) => {
      this.worldState.updateFromSetTime(packet)
    })

    client.on('level_event', (packet) => {
      this.worldState.updateFromLevelEvent(packet)
    })

    client.on('add_player', (packet) => {
      this.entityTracker.addPlayer(packet)
    })

    client.on('add_entity', (packet) => {
      this.entityTracker.addEntity(packet)
    })

    client.on('move_entity', (packet) => {
      this.entityTracker.updateEntity(packet)
    })

    client.on('remove_entity', (packet) => {
      this.entityTracker.removeEntity(packet)
    })

    client.on('update_attributes', (packet) => {
      this.playerState.updateFromAttributes(packet)
    })

    client.on('entity_event', (packet) => {
      const event = this.playerState.updateFromEntityEvent(packet)
      if (event) {
        telemetry.emit('player_entity_event', event)
      }
    })

    client.on('respawn', (packet) => {
      this.playerState.updateFromRespawn(packet)
      telemetry.emit('player_respawned', { position: this.playerState.position })
    })

    client.on('move_player', (packet) => {
      this.playerState.updateFromMovePlayer(packet)
    })

    client.on('correct_player_move_prediction', (packet) => {
      if (packet.position) {
        this.playerState.updateKinematics(packet.position, null)
      }
      if (packet.tick !== undefined) {
        this.playerState.tick = toBigIntSafe(packet.tick)
      }
    })

    client.on('text', (packet) => {
      if (packet.message) {
        telemetry.emit('chat_message', {
          type: packet.type,
          sourceName: packet.source_name,
          message: packet.message
        })
      }
    })

    client.on('move_player', (packet) => {
      const updated = this.playerState.updateFromMovePlayer(packet)
      if (!updated) return

      const state = this.playerState.getSnapshot()

      if (!this.initialized && state.runtimeEntityId !== null && state.position.x !== null) {
        this.initialized = true

        try {
          client.queue('set_local_player_as_initialized', {
            runtime_entity_id: toBigIntSafe(state.runtimeEntityId)
          })
        } catch (e) {}

        telemetry.emit('player_initialized', {
          runtimeEntityId: state.runtimeEntityId,
          spawnPosition: state.position
        })

        console.log(`[CLIENT] Jogador inicializado em (${state.position.x.toFixed(2)}, ${state.position.y.toFixed(2)}, ${state.position.z.toFixed(2)})`)

        // Start locomotion and autonomous decision loop
        this.movement.start()
        this.brain.start()

        console.log(`[AUTONOMY] Cérebro autônomo iniciado em modo '${this.brain.mode}'.`)
      }
    })

    client.on('disconnect', (packet) => {
      const reason = packet ? (packet.reason || packet.message || JSON.stringify(packet)) : 'Desconexão do servidor'
      console.log(`[CLIENT] Desconectado. Motivo: ${reason}`)

      this._handleDisconnection(reason)
    })

    client.on('error', (error) => {
      console.error(`[CLIENT] Erro de rede/protocolo: ${error.message}`)
      telemetry.emit('client_error', {
        message: error.message,
        stack: error.stack
      })
      this._handleDisconnection(error.message)
    })
  }

  _handleDisconnection (reason) {
    this.initialized = false

    if (this.brain) this.brain.stop()
    if (this.movement) this.movement.stop()

    telemetry.emit('player_disconnected', { reason })

    if (this.config.resilience.autoReconnect && !this.isShuttingDown) {
      this._scheduleReconnect()
    }
  }

  _scheduleReconnect () {
    if (this.isShuttingDown || this.reconnectTimer) return

    const resilience = this.config.resilience
    if (this.reconnectAttempts >= resilience.maxReconnectAttempts) {
      console.error(`[RESILIENCE] Limite máximo de tentativas de reconexão atingido (${resilience.maxReconnectAttempts}).`)
      return
    }

    this.reconnectAttempts += 1
    const delay = Math.min(
      resilience.initialDelayMs * Math.pow(resilience.backoffMultiplier, this.reconnectAttempts - 1),
      resilience.maxDelayMs
    )

    console.log(`[RESILIENCE] Tentativa ${this.reconnectAttempts}/${resilience.maxReconnectAttempts} em ${(delay / 1000).toFixed(1)}s...`)

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, delay)
  }

  _startSummaryReporting () {
    const interval = this.config.telemetry.summaryIntervalMs || 10000

    this.summaryTimer = setInterval(() => {
      if (this.initialized) {
        const pSnap = this.playerState.getSnapshot()
        const bSnap = this.brain.getSnapshot()

        telemetry.emitSummary({
          state: bSnap.state,
          mode: bSnap.mode,
          position: pSnap.position,
          health: pSnap.health,
          isAlive: pSnap.isAlive,
          totalDistance: pSnap.stats.totalDistanceTraveled,
          waypointsReached: bSnap.waypointsReached,
          stuckEvents: bSnap.totalStuckEvents,
          currentGoal: bSnap.currentGoal
        })

        console.log(
          `[STATUS] Estado: ${bSnap.state.padEnd(16)} | ` +
          `Pos: (${pSnap.position.x?.toFixed(1)}, ${pSnap.position.y?.toFixed(1)}, ${pSnap.position.z?.toFixed(1)}) | ` +
          `Dist: ${pSnap.stats.totalDistanceTraveled}m | ` +
          `Waypoints: ${bSnap.waypointsReached} | ` +
          `Vida: ${pSnap.health}/${pSnap.maxHealth}`
        )
      }
    }, interval)
  }

  _setupSignalHandlers () {
    const shutdown = (signal) => {
      if (this.isShuttingDown) return
      this.isShuttingDown = true

      console.log('')
      console.log(`[SYSTEM] Sinal ${signal} recebido. Encerrando Scripted Bot...`)

      if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
      if (this.summaryTimer) clearInterval(this.summaryTimer)

      if (this.brain) this.brain.stop()
      if (this.movement) this.movement.stop()

      telemetry.emit('bot_shutdown', { reason: signal })
      telemetry.close()

      if (this.client) {
        try {
          this.client.disconnect('Scripted Bot shutdown')
        } catch (e) {}
      }

      console.log('[SYSTEM] Scripted Bot finalizado com sucesso.')
      process.exit(0)
    }

    process.once('SIGINT', () => shutdown('SIGINT'))
    process.once('SIGTERM', () => shutdown('SIGTERM'))
  }
}

// If invoked directly from CLI, boot the application
if (require.main === module) {
  const app = new ScriptedBotApp()
  app.start()
}

module.exports = ScriptedBotApp
