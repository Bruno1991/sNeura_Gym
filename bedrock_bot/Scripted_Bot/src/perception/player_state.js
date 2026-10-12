/**
 * s_Neura_Gym - Scripted Bot
 *
 * Responsibility:
 * Observes, maintains, and normalizes the state of the local player.
 *
 * Tracks:
 * - Position (X, Y, Z) and Delta Displacement
 * - Rotation (Pitch, Yaw, HeadYaw)
 * - Ground & Physics state (onGround, vertical velocity)
 * - Health, Hunger, and Survival status (isAlive, damageTaken)
 * - Entity identity & Server tick
 * - Cumulative statistics (distance traveled, steps, deaths)
 *
 * Does NOT execute movement or make autonomous decisions.
 */

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

class PlayerState {
  constructor () {
    this.runtimeEntityId = null

    this.position = {
      x: null,
      y: null,
      z: null
    }

    this.lastPosition = {
      x: null,
      y: null,
      z: null
    }

    this.rotation = {
      pitch: 0,
      yaw: 0,
      headYaw: 0
    }

    this.velocity = {
      x: 0,
      y: 0,
      z: 0
    }

    this.onGround = true
    this.tick = 0n
    this.initialized = false

    // Survival attributes
    this.health = 20
    this.maxHealth = 20
    this.hunger = 20
    this.maxHunger = 20
    this.isAlive = true

    // Metrics
    this.totalDistanceTraveled = 0
    this.deathsCount = 0
    this.damageEventsCount = 0
  }

  initFromStartGame (packet) {
    if (!packet) return false

    if (packet.runtime_entity_id !== undefined) {
      this.runtimeEntityId = toBigIntSafe(packet.runtime_entity_id)
    }

    if (packet.current_tick !== undefined) {
      this.tick = toBigIntSafe(packet.current_tick)
    }

    if (packet.player_position) {
      this.position = {
        x: packet.player_position.x,
        y: packet.player_position.y,
        z: packet.player_position.z
      }
      this.lastPosition = { ...this.position }
    }

    if (packet.rotation) {
      // In Bedrock start_game, rotation is { x: pitch, z: yaw }
      const pitch = packet.rotation.x ?? 0
      const yaw = packet.rotation.z ?? 0
      this.rotation = {
        pitch,
        yaw: ((yaw % 360) + 360) % 360,
        headYaw: ((yaw % 360) + 360) % 360
      }
    }

    this.initialized = true
    return true
  }

  updateFromMovePlayer (packet) {
    if (!packet || !packet.position) {
      return false
    }

    if (this.runtimeEntityId === null && packet.runtime_id !== undefined) {
      this.runtimeEntityId = toBigIntSafe(packet.runtime_id)
    }

    if (this.runtimeEntityId !== null && packet.runtime_id !== undefined) {
      if (toBigIntSafe(packet.runtime_id) !== this.runtimeEntityId) {
        return false
      }
    }

    if (packet.tick !== undefined) {
      this.tick = toBigIntSafe(packet.tick)
    }

    this.onGround = packet.on_ground ?? this.onGround

    const isTeleportOrReset = packet.mode === 'teleport' || packet.mode === 'reset'
    const notSet = this.position.x === null

    let largeDesync = false
    if (!notSet) {
      const dist = Math.hypot(packet.position.x - this.position.x, packet.position.z - this.position.z)
      if (dist > 5.0) {
        largeDesync = true
      }
    }

    if (notSet || isTeleportOrReset || largeDesync) {
      this.lastPosition = { ...this.position }
      this.position = {
        x: packet.position.x,
        y: packet.position.y,
        z: packet.position.z
      }

      this.rotation = {
        pitch: packet.pitch ?? this.rotation.pitch,
        yaw: packet.yaw ?? this.rotation.yaw,
        headYaw: packet.head_yaw ?? packet.yaw ?? this.rotation.headYaw
      }
    }

    this.initialized = true
    return true
  }

  updateFromAttributes (packet) {
    if (!packet || !Array.isArray(packet.attributes)) {
      return false
    }

    if (this.runtimeEntityId !== null && packet.runtime_entity_id !== undefined) {
      if (toBigIntSafe(packet.runtime_entity_id) !== this.runtimeEntityId) {
        return false
      }
    }

    for (const attr of packet.attributes) {
      if (attr.name === 'minecraft:health') {
        this.health = attr.current ?? this.health
        this.maxHealth = attr.max ?? this.maxHealth
        if (this.health <= 0) {
          this.isAlive = false
        }
      } else if (attr.name === 'minecraft:player.hunger') {
        this.hunger = attr.current ?? this.hunger
        this.maxHunger = attr.max ?? this.maxHunger
      }
    }

    return true
  }

  updateFromEntityEvent (packet) {
    if (!packet) {
      return false
    }

    if (this.runtimeEntityId !== null && packet.runtime_entity_id !== undefined) {
      if (toBigIntSafe(packet.runtime_entity_id) !== this.runtimeEntityId) {
        return false
      }
    }

    const eventId = packet.event_id

    if (eventId === 'hurt_animation' || eventId === 2) {
      this.damageEventsCount += 1
      return { type: 'hurt' }
    }

    if (eventId === 'death_animation' || eventId === 3) {
      this.isAlive = false
      this.deathsCount += 1
      return { type: 'death' }
    }

    if (eventId === 'respawn' || eventId === 18) {
      this.isAlive = true
      this.health = this.maxHealth
      return { type: 'respawn' }
    }

    return false
  }

  updateFromRespawn (packet) {
    if (!packet) {
      return false
    }

    if (packet.position) {
      this.position = {
        x: packet.position.x,
        y: packet.position.y,
        z: packet.position.z
      }
    }

    this.isAlive = true
    this.health = this.maxHealth
    return true
  }

  updateKinematics (newPosition, delta, rotation = null) {
    if (!newPosition) {
      return
    }

    this.lastPosition = { ...this.position }
    this.position = { ...newPosition }

    if (delta) {
      this.velocity = { ...delta }
      const horizontalDist = Math.hypot(delta.x, delta.z)
      this.totalDistanceTraveled += horizontalDist
    }

    if (rotation) {
      this.rotation = {
        pitch: rotation.pitch ?? this.rotation.pitch,
        yaw: rotation.yaw ?? this.rotation.yaw,
        headYaw: rotation.headYaw ?? rotation.yaw ?? this.rotation.headYaw
      }
    }
  }

  getDistanceTo (targetX, targetZ) {
    if (this.position.x === null || this.position.z === null) {
      return Infinity
    }
    return Math.hypot(targetX - this.position.x, targetZ - this.position.z)
  }

  getSnapshot () {
    return {
      runtimeEntityId: this.runtimeEntityId,
      position: { ...this.position },
      lastPosition: { ...this.lastPosition },
      rotation: { ...this.rotation },
      velocity: { ...this.velocity },
      onGround: this.onGround,
      tick: this.tick,
      initialized: this.initialized,
      health: this.health,
      maxHealth: this.maxHealth,
      hunger: this.hunger,
      maxHunger: this.maxHunger,
      isAlive: this.isAlive,
      stats: {
        totalDistanceTraveled: Number(this.totalDistanceTraveled.toFixed(2)),
        deathsCount: this.deathsCount,
        damageEventsCount: this.damageEventsCount
      }
    }
  }

  reset (spawnCoords = null) {
    if (spawnCoords) {
      this.position = {
        x: spawnCoords.x,
        y: spawnCoords.y,
        z: spawnCoords.z
      }
      this.lastPosition = { ...this.position }
    }
    this.velocity = { x: 0, y: 0, z: 0 }
    this.isAlive = true
    this.health = this.maxHealth
    this.onGround = true
  }
}

module.exports = PlayerState
