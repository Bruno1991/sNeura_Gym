const { describe, it } = require('node:test')
const assert = require('node:assert')
const AutonomousBrain = require('../src/decision/autonomous_brain')
const PlayerState = require('../src/perception/player_state')
const Movement = require('../src/action/movement')
const SpawnManager = require('../src/environment/spawn')
const EnvironmentRules = require('../src/environment/rules')
const EnvironmentReset = require('../src/environment/reset')

describe('AutonomousBrain State Machine', () => {
  function createBrainSetup () {
    const playerState = new PlayerState()
    playerState.position = { x: 100, y: 64, z: 200 }
    playerState.rotation = { yaw: 0, pitch: 0, headYaw: 0 }
    playerState.initialized = true

    const mockClient = { queue: () => {} }
    const movement = new Movement(mockClient, playerState)
    const spawnManager = new SpawnManager({
      spawn: { x: 100, y: 64, z: 200 },
      maxRadius: 30
    })
    const environmentRules = new EnvironmentRules({ minY: -64, maxRadius: 30 }, spawnManager)
    const environmentReset = new EnvironmentReset({
      playerState,
      spawnManager,
      movement
    })

    const brain = new AutonomousBrain({
      playerState,
      movement,
      spawnManager,
      environmentRules,
      environmentReset,
      config: {
        mode: 'wander',
        decisionTickMs: 50,
        wander: {
          minDistance: 4,
          maxDistance: 10,
          arrivalRadius: 1.5,
          pauseMinMs: 100,
          pauseMaxMs: 200
        },
        obstacleAvoidance: {
          stuckThreshold: 0.15,
          stuckWindowMs: 200,
          turnAngleDeg: 90
        }
      }
    })

    return { playerState, movement, spawnManager, environmentRules, environmentReset, brain }
  }

  it('starts at INITIALIZING and transitions to IDLE on first valid think', () => {
    const { brain } = createBrainSetup()
    assert.strictEqual(brain.state, 'INITIALIZING')

    brain.think()
    assert.strictEqual(brain.state, 'IDLE')
  })

  it('transitions from IDLE to CHOOSING_GOAL and then NAVIGATING', () => {
    const { brain } = createBrainSetup()
    brain.think() // -> IDLE
    brain.pauseUntil = Date.now() - 10 // expire idle pause

    brain.think() // -> transitions to NAVIGATING
    assert.strictEqual(brain.state, 'NAVIGATING')
    assert.ok(brain.currentGoal !== null, 'Goal should be populated')

    brain.think() // executes handleNavigating, activates movement.walkForward()
    assert.ok(brain.movement.walkingForward, 'Should be walking forward towards goal')
  })

  it('transitions to ARRIVED and back to IDLE when reaching target waypoint', () => {
    const { brain, playerState } = createBrainSetup()
    brain.think() // -> IDLE
    brain.pauseUntil = Date.now() - 10
    brain.think() // -> NAVIGATING

    // Teleport player right next to the current goal
    playerState.position = {
      x: brain.currentGoal.x + 0.5,
      y: brain.currentGoal.y,
      z: brain.currentGoal.z + 0.5
    }

    brain.think() // -> ARRIVED -> IDLE
    assert.strictEqual(brain.state, 'IDLE')
    assert.strictEqual(brain.waypointsReached, 1)
    assert.strictEqual(brain.movement.walkingForward, false)
  })

  it('detects stuck condition and initiates multi-phase recovery', async () => {
    const { brain, playerState, movement } = createBrainSetup()
    brain.think() // -> IDLE
    brain.pauseUntil = Date.now() - 10
    brain.think() // -> NAVIGATING
    brain.think() // executes handleNavigating, activates movement.walkForward()

    // Simulate agent trying to walk forward but coordinates remain unchanged for stuck window
    brain.lastPositionCheck = { ...playerState.position }
    brain.lastPositionCheckTime = Date.now() - 300 // exceeded 200ms window

    brain.think()
    assert.strictEqual(brain.state, 'STUCK_RECOVERY')
    assert.strictEqual(brain.totalStuckEvents, 1)

    // Phase 1: Jump attempt
    brain.stuckRecoveryUntil = 0
    brain.think()
    assert.strictEqual(brain.stuckRecoveryPhase, 1)
    assert.strictEqual(movement.isJumping, true)

    // Phase 2: Backtrack
    brain.stuckRecoveryUntil = 0
    brain.think()
    assert.strictEqual(brain.stuckRecoveryPhase, 2)
    assert.strictEqual(movement.walkingBackward, true)

    // Phase 3: Steer away and pick fresh goal
    brain.stuckRecoveryUntil = 0
    brain.think()
    assert.strictEqual(brain.state, 'NAVIGATING')
    assert.strictEqual(brain.stuckRecoveryPhase, 0)
  })

  it('transitions to RETURNING_TO_BOUNDS when position exceeds maxRadius', () => {
    const { brain, playerState } = createBrainSetup()
    brain.think() // -> IDLE

    // Place player far outside boundary (spawn is at 100, 200; maxRadius is 30)
    playerState.position = { x: 150, y: 64, z: 200 }

    brain.think()
    assert.strictEqual(brain.state, 'RETURNING_TO_BOUNDS')
    assert.strictEqual(brain.movement.walkingForward, true)
  })

  it('handles player death by transitioning to RESPAWNING and resetting episode', () => {
    const { brain, playerState, environmentReset } = createBrainSetup()
    brain.think() // -> IDLE

    playerState.health = 0
    playerState.isAlive = false

    brain.think()
    assert.strictEqual(brain.state, 'RESPAWNING')
    assert.strictEqual(environmentReset.getEpisodeCount(), 1)
  })
})
