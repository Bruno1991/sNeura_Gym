/**
 * s_Neura_Gym - Scripted Bot
 *
 * Responsibility:
 * Maintains observation of the global world state:
 * - Day/Night cycle & World time
 * - Dimension
 * - Weather & World events
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

class WorldState {
  constructor () {
    this.time = 0n
    this.dimension = 'overworld'
    this.raining = false
    this.thundering = false
    this.difficulty = 'normal'
    this.levelName = ''
  }

  updateFromStartGame (packet) {
    if (!packet) return

    if (packet.dimension !== undefined) {
      const dimMap = { 0: 'overworld', 1: 'nether', 2: 'the_end' }
      this.dimension = dimMap[packet.dimension] || String(packet.dimension)
    }

    if (packet.world_name) {
      this.levelName = packet.world_name
    }

    if (packet.time !== undefined) {
      this.time = toBigIntSafe(packet.time)
    }
  }

  updateFromSetTime (packet) {
    if (!packet || packet.time === undefined) return
    this.time = toBigIntSafe(packet.time)
  }

  updateFromLevelEvent (packet) {
    if (!packet) return
    // e.g. start/stop rain
    if (packet.event_id === 'start_rain' || packet.event_id === 1051) {
      this.raining = true
    } else if (packet.event_id === 'stop_rain' || packet.event_id === 1052) {
      this.raining = false
    }
  }

  isDay () {
    const cycle = Number(this.time % 24000n)
    return cycle < 12000
  }

  isNight () {
    return !this.isDay()
  }

  getSnapshot () {
    return {
      time: this.time.toString(),
      isDay: this.isDay(),
      dimension: this.dimension,
      raining: this.raining,
      thundering: this.thundering
    }
  }
}

module.exports = WorldState
