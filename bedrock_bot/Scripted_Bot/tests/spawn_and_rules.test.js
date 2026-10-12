const { describe, it } = require('node:test')
const assert = require('node:assert')
const SpawnManager = require('../src/environment/spawn')
const EnvironmentRules = require('../src/environment/rules')

describe('SpawnManager & EnvironmentRules', () => {
  const spawnCoords = { x: 100, y: 64, z: 200 }
  const maxRadius = 30

  it('calculates distance to spawn correctly', () => {
    const mgr = new SpawnManager({ spawn: spawnCoords, maxRadius })

    const distAtSpawn = mgr.getDistanceToSpawn({ x: 100, y: 64, z: 200 })
    assert.strictEqual(distAtSpawn, 0)

    const distAway = mgr.getDistanceToSpawn({ x: 103, y: 64, z: 204 })
    assert.strictEqual(distAway, 5)
  })

  it('verifies bounds accurately', () => {
    const mgr = new SpawnManager({ spawn: spawnCoords, maxRadius })

    assert.strictEqual(mgr.isWithinBounds({ x: 120, z: 200 }), true)
    assert.strictEqual(mgr.isWithinBounds({ x: 131, z: 200 }), false)
  })

  it('generates random waypoints always within boundary radius', () => {
    const mgr = new SpawnManager({ spawn: spawnCoords, maxRadius })

    for (let i = 0; i < 20; i++) {
      const wp = mgr.generateRandomWaypoint({ x: 105, y: 64, z: 205 }, 3, 10)
      const dist = Math.hypot(wp.x - spawnCoords.x, wp.z - spawnCoords.z)
      assert.ok(dist <= maxRadius, `Waypoint (${wp.x}, ${wp.z}) distance ${dist} exceeded max radius ${maxRadius}`)
    }
  })

  it('evaluates compliant state with zero violations', () => {
    const mgr = new SpawnManager({ spawn: spawnCoords, maxRadius })
    const rules = new EnvironmentRules({ minY: -64, maxRadius }, mgr)

    const snapshot = {
      initialized: true,
      isAlive: true,
      health: 20,
      position: { x: 110, y: 64, z: 210 }
    }

    const evaluation = rules.evaluate(snapshot)
    assert.strictEqual(evaluation.compliant, true)
    assert.strictEqual(evaluation.violations.length, 0)
  })

  it('detects VOID_FALL violation when y < minY', () => {
    const mgr = new SpawnManager({ spawn: spawnCoords, maxRadius })
    const rules = new EnvironmentRules({ minY: -64, maxRadius }, mgr)

    const snapshot = {
      initialized: true,
      isAlive: true,
      health: 20,
      position: { x: 100, y: -65, z: 200 }
    }

    const evaluation = rules.evaluate(snapshot)
    assert.strictEqual(evaluation.compliant, false)
    assert.ok(evaluation.violations.some(v => v.type === 'VOID_FALL'))
  })

  it('detects OUT_OF_BOUNDS violation when exceeding maxRadius', () => {
    const mgr = new SpawnManager({ spawn: spawnCoords, maxRadius })
    const rules = new EnvironmentRules({ minY: -64, maxRadius }, mgr)

    const snapshot = {
      initialized: true,
      isAlive: true,
      health: 20,
      position: { x: 150, y: 64, z: 200 } // dist = 50 > 30
    }

    const evaluation = rules.evaluate(snapshot)
    assert.strictEqual(evaluation.compliant, false)
    assert.ok(evaluation.violations.some(v => v.type === 'OUT_OF_BOUNDS'))
  })

  it('detects PLAYER_DEAD violation when health is 0', () => {
    const mgr = new SpawnManager({ spawn: spawnCoords, maxRadius })
    const rules = new EnvironmentRules({ minY: -64, maxRadius }, mgr)

    const snapshot = {
      initialized: true,
      isAlive: false,
      health: 0,
      position: { x: 100, y: 64, z: 200 }
    }

    const evaluation = rules.evaluate(snapshot)
    assert.strictEqual(evaluation.compliant, false)
    assert.ok(evaluation.violations.some(v => v.type === 'PLAYER_DEAD'))
  })
})
