/**
 * s_Neura_Gym - Scripted Bot
 *
 * Responsibility:
 * Enforces environmental safety constraints, perimeter boundaries,
 * void hazards, and episode evaluation rules.
 */

class EnvironmentRules {
  constructor (config = {}, spawnManager) {
    this.spawnManager = spawnManager
    this.minY = config.minY ?? -64
    this.maxRadius = config.maxRadius ?? 35
  }

  evaluate (playerSnapshot) {
    const violations = []

    if (!playerSnapshot || !playerSnapshot.initialized) {
      return {
        compliant: true,
        violations: []
      }
    }

    const pos = playerSnapshot.position

    // 1. Void violation
    if (pos.y !== null && pos.y < this.minY) {
      violations.push({
        type: 'VOID_FALL',
        severity: 'CRITICAL',
        message: `Player fell below minimum Y (${pos.y} < ${this.minY})`
      })
    }

    // 2. Boundary violation
    if (pos.x !== null && pos.z !== null && this.spawnManager) {
      const dist = this.spawnManager.getDistanceToSpawn(pos)
      if (dist > this.maxRadius) {
        violations.push({
          type: 'OUT_OF_BOUNDS',
          severity: 'HIGH',
          distance: Number(dist.toFixed(2)),
          maxRadius: this.maxRadius,
          message: `Player exceeded boundary radius (${dist.toFixed(2)} > ${this.maxRadius})`
        })
      }
    }

    // 3. Health / Dead check
    if (!playerSnapshot.isAlive || (playerSnapshot.health !== null && playerSnapshot.health <= 0)) {
      violations.push({
        type: 'PLAYER_DEAD',
        severity: 'CRITICAL',
        message: 'Player health depleted to 0'
      })
    }

    return {
      compliant: violations.length === 0,
      violations
    }
  }

  isOutOfBounds (pos) {
    if (!this.spawnManager) return false
    return !this.spawnManager.isWithinBounds(pos)
  }

  isDeadOrVoid (playerSnapshot) {
    if (!playerSnapshot) return false
    if (!playerSnapshot.isAlive) return true
    if (playerSnapshot.position.y !== null && playerSnapshot.position.y < this.minY) return true
    return false
  }
}

module.exports = EnvironmentRules
