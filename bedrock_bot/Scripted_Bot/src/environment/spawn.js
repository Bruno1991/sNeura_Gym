/**
 * s_Neura_Gym - Scripted Bot
 *
 * Responsibility:
 * Manages the agent's spawn location and navigation bounds.
 * Generates valid exploration waypoints within the allowed perimeter.
 */

class SpawnManager {
  constructor (config = {}) {
    this.spawn = config.spawn || { x: 79, y: 63, z: 1251 }
    this.maxRadius = config.maxRadius || 35
  }

  getSpawn () {
    return { ...this.spawn }
  }

  getDistanceToSpawn (pos) {
    if (!pos || pos.x === null || pos.z === null) {
      return Infinity
    }
    return Math.hypot(pos.x - this.spawn.x, pos.z - this.spawn.z)
  }

  isWithinBounds (pos, tolerance = 0) {
    const dist = this.getDistanceToSpawn(pos)
    return dist <= (this.maxRadius + tolerance)
  }

  /**
   * Generates a random waypoint within the allowable radius around spawn.
   * Can be anchored near current position to generate natural wandering steps.
   */
  generateRandomWaypoint (currentPos = null, minStep = 4, maxStep = 14) {
    const anchor = currentPos && currentPos.x !== null ? currentPos : this.spawn

    for (let attempts = 0; attempts < 10; attempts++) {
      const angle = Math.random() * 2 * Math.PI
      const distance = minStep + Math.random() * (maxStep - minStep)

      const candidateX = Number((anchor.x + Math.cos(angle) * distance).toFixed(2))
      const candidateZ = Number((anchor.z + Math.sin(angle) * distance).toFixed(2))

      // Check if candidate is within overall spawn radius
      const distFromSpawn = Math.hypot(candidateX - this.spawn.x, candidateZ - this.spawn.z)
      if (distFromSpawn <= this.maxRadius) {
        return {
          x: candidateX,
          y: currentPos && currentPos.y !== null ? currentPos.y : this.spawn.y,
          z: candidateZ
        }
      }
    }

    // Fallback: pick a point directly inside the spawn circle
    const angle = Math.random() * 2 * Math.PI
    const distance = Math.random() * (this.maxRadius * 0.75)
    return {
      x: Number((this.spawn.x + Math.cos(angle) * distance).toFixed(2)),
      y: currentPos && currentPos.y !== null ? currentPos.y : this.spawn.y,
      z: Number((this.spawn.z + Math.sin(angle) * distance).toFixed(2))
    }
  }

  getReturnToSpawnWaypoint () {
    return {
      x: this.spawn.x,
      y: this.spawn.y,
      z: this.spawn.z
    }
  }
}

module.exports = SpawnManager
