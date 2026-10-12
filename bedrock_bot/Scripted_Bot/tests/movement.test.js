const { describe, it } = require('node:test')
const assert = require('node:assert')
const Movement = require('../src/action/movement')
const PlayerState = require('../src/perception/player_state')

describe('Movement & Kinematics', () => {
  function createSetup () {
    const playerState = new PlayerState()
    playerState.position = { x: 0, y: 64, z: 0 }
    playerState.rotation = { yaw: 0, pitch: 0, headYaw: 0 }
    playerState.initialized = true

    const queuedPackets = []
    const mockClient = {
      queue: (name, params) => {
        queuedPackets.push({ name, params })
      }
    }

    const movement = new Movement(mockClient, playerState, { tickRateMs: 50 })
    return { playerState, mockClient, movement, queuedPackets }
  }

  it('calculates correct Bedrock yaw orientations with lookAt', () => {
    const { playerState, movement } = createSetup()

    // South (+Z): dx=0, dz=10 -> yaw = 0
    movement.lookAt(0, 10)
    assert.strictEqual(Math.round(movement.targetYaw), 0)

    // West (-X): dx=-10, dz=0 -> yaw = 90
    movement.lookAt(-10, 0)
    assert.strictEqual(Math.round(movement.targetYaw), 90)

    // North (-Z): dx=0, dz=-10 -> yaw = 180
    movement.lookAt(0, -10)
    assert.strictEqual(Math.round(movement.targetYaw), 180)

    // East (+X): dx=10, dz=0 -> yaw = 270
    movement.lookAt(10, 0)
    assert.strictEqual(Math.round(movement.targetYaw), 270)
  })

  it('displaces position along yaw when walking forward', () => {
    const { playerState, movement, queuedPackets } = createSetup()

    // Facing South (yaw = 0): forward is +Z
    movement.setRotation(0, 0)
    movement.walkForward()

    movement.update()

    assert.strictEqual(queuedPackets.length, 1)
    const pkt = queuedPackets[0]

    assert.strictEqual(pkt.name, 'player_auth_input')
    assert.ok(pkt.params.input_data.includes('up'))
    assert.strictEqual(pkt.params.move_vector.z, 1)

    // Check position moved positive in Z, zero in X
    assert.strictEqual(playerState.position.x, 0)
    assert.ok(playerState.position.z > 0, `Expected Z > 0, got ${playerState.position.z}`)
    assert.strictEqual(pkt.params.delta.x, 0)
    assert.ok(pkt.params.delta.z > 0, `Expected delta.z > 0, got ${pkt.params.delta.z}`)
  })

  it('displaces position west (-X) when yaw is 90', () => {
    const { playerState, movement, queuedPackets } = createSetup()

    movement.setRotation(90, 0)
    movement.walkForward()

    movement.update()

    assert.ok(playerState.position.x < 0, `Expected X < 0, got ${playerState.position.x}`)
    assert.strictEqual(Math.round(playerState.position.z), 0)
  })

  it('handles jump vertical kinematics and packet flags', () => {
    const { playerState, movement, queuedPackets } = createSetup()

    movement.setRotation(0, 0)
    movement.walkForward()
    movement.jump()

    movement.update()

    const pkt = queuedPackets[0]
    assert.ok(pkt.params.input_data.includes('jumping'))
    assert.ok(pkt.params.input_data.includes('start_jumping'))
    assert.ok(playerState.position.y > 64.0, `Expected Y > 64, got ${playerState.position.y}`)
  })

  it('adjusts displacement according to sprinting and sneaking speeds', () => {
    const setupWalk = createSetup()
    setupWalk.movement.setRotation(0, 0)
    setupWalk.movement.walkForward()
    setupWalk.movement.update()
    const walkDeltaZ = setupWalk.queuedPackets[0].params.delta.z

    const setupSprint = createSetup()
    setupSprint.movement.setRotation(0, 0)
    setupSprint.movement.walkForward()
    setupSprint.movement.sprint(true)
    setupSprint.movement.update()
    const sprintDeltaZ = setupSprint.queuedPackets[0].params.delta.z

    const setupSneak = createSetup()
    setupSneak.movement.setRotation(0, 0)
    setupSneak.movement.walkForward()
    setupSneak.movement.sneak(true)
    setupSneak.movement.update()
    const sneakDeltaZ = setupSneak.queuedPackets[0].params.delta.z

    assert.ok(sprintDeltaZ > walkDeltaZ, `Sprint (${sprintDeltaZ}) should exceed walk (${walkDeltaZ})`)
    assert.ok(sneakDeltaZ < walkDeltaZ, `Sneak (${sneakDeltaZ}) should be less than walk (${walkDeltaZ})`)
  })

  it('stops all locomotion when stopAll is called', () => {
    const { movement } = createSetup()

    movement.walkForward()
    movement.sprint(true)
    movement.jump()
    assert.strictEqual(movement.isMoving(), true)

    movement.stopAll()
    assert.strictEqual(movement.isMoving(), false)
    assert.strictEqual(movement.sprinting, false)
    assert.strictEqual(movement.isJumping, false)
  })

  it('queues authoritative tp commands when authoritativeDriver is active', () => {
    const { playerState, mockClient, queuedPackets } = createSetup()
    const movement = new Movement(mockClient, playerState, {
      tickRateMs: 50,
      authoritativeDriver: true
    })

    movement.setRotation(0, 0)
    movement.walkForward()

    // Tick 1: suppresses feedback and accumulates delta
    movement.update()
    const feedbackPkt = queuedPackets.find(p => p.name === 'command_request' && p.params.command.includes('sendcommandfeedback'))
    assert.ok(feedbackPkt, 'Should suppress command feedback')

    // Tick 2: reaches accumulated distance threshold and dispatches /tp
    movement.update()
    const tpPkt = queuedPackets.find(p => p.name === 'command_request' && p.params.command.startsWith('/tp @s ~'))
    assert.ok(tpPkt, 'Should dispatch /tp command on accumulated delta')
  })

  it('dispatches direct teleport command with teleportTo', () => {
    const { playerState, mockClient, queuedPackets } = createSetup()
    const movement = new Movement(mockClient, playerState, {
      tickRateMs: 50,
      authoritativeDriver: true
    })

    movement.teleportTo(87, 63, 1251, 90, 0)
    const tpPkt = queuedPackets.find(p => p.name === 'command_request' && p.params.command === '/tp @s 87.00 63.00 1251.00 90 0')
    assert.ok(tpPkt, 'Should dispatch exact absolute /tp command')
  })
})

