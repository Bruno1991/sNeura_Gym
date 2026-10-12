const { describe, it } = require('node:test')
const assert = require('node:assert')
const PlayerState = require('../src/perception/player_state')

describe('PlayerState', () => {
  it('initializes with default values', () => {
    const state = new PlayerState()
    const snap = state.getSnapshot()

    assert.strictEqual(snap.runtimeEntityId, null)
    assert.strictEqual(snap.position.x, null)
    assert.strictEqual(snap.initialized, false)
    assert.strictEqual(snap.health, 20)
    assert.strictEqual(snap.maxHealth, 20)
    assert.strictEqual(snap.isAlive, true)
    assert.strictEqual(snap.stats.totalDistanceTraveled, 0)
  })

  it('updates state from move_player packet', () => {
    const state = new PlayerState()
    const packet = {
      runtime_id: 12345n,
      position: { x: 79.5, y: 64.0, z: 1251.2 },
      pitch: 10.5,
      yaw: 180.0,
      head_yaw: 180.0,
      on_ground: true,
      tick: 500n
    }

    const updated = state.updateFromMovePlayer(packet)
    assert.strictEqual(updated, true)

    const snap = state.getSnapshot()
    assert.strictEqual(snap.runtimeEntityId, 12345n)
    assert.strictEqual(snap.position.x, 79.5)
    assert.strictEqual(snap.position.y, 64.0)
    assert.strictEqual(snap.position.z, 1251.2)
    assert.strictEqual(snap.rotation.pitch, 10.5)
    assert.strictEqual(snap.rotation.yaw, 180.0)
    assert.strictEqual(snap.onGround, true)
    assert.strictEqual(snap.initialized, true)
  })

  it('rejects move_player for different runtimeEntityId once established', () => {
    const state = new PlayerState()
    state.updateFromMovePlayer({
      runtime_id: 100n,
      position: { x: 0, y: 0, z: 0 }
    })

    const rejected = state.updateFromMovePlayer({
      runtime_id: 999n,
      position: { x: 10, y: 10, z: 10 }
    })
    assert.strictEqual(rejected, false)
    assert.strictEqual(state.position.x, 0)
  })

  it('updates health and hunger from attributes', () => {
    const state = new PlayerState()
    state.runtimeEntityId = 100n

    const packet = {
      runtime_entity_id: 100n,
      attributes: [
        { name: 'minecraft:health', current: 14.5, max: 20 },
        { name: 'minecraft:player.hunger', current: 18, max: 20 }
      ]
    }

    const updated = state.updateFromAttributes(packet)
    assert.strictEqual(updated, true)

    const snap = state.getSnapshot()
    assert.strictEqual(snap.health, 14.5)
    assert.strictEqual(snap.hunger, 18)
    assert.strictEqual(snap.isAlive, true)
  })

  it('detects death when health is 0', () => {
    const state = new PlayerState()
    state.runtimeEntityId = 100n

    state.updateFromAttributes({
      runtime_entity_id: 100n,
      attributes: [{ name: 'minecraft:health', current: 0, max: 20 }]
    })

    const snap = state.getSnapshot()
    assert.strictEqual(snap.health, 0)
    assert.strictEqual(snap.isAlive, false)
  })

  it('handles entity events: hurt, death, respawn', () => {
    const state = new PlayerState()
    state.runtimeEntityId = 100n

    // Hurt
    const hurtRes = state.updateFromEntityEvent({
      runtime_entity_id: 100n,
      event_id: 'hurt_animation'
    })
    assert.deepStrictEqual(hurtRes, { type: 'hurt' })
    assert.strictEqual(state.damageEventsCount, 1)

    // Death
    const deathRes = state.updateFromEntityEvent({
      runtime_entity_id: 100n,
      event_id: 'death_animation'
    })
    assert.deepStrictEqual(deathRes, { type: 'death' })
    assert.strictEqual(state.isAlive, false)
    assert.strictEqual(state.deathsCount, 1)

    // Respawn
    const respawnRes = state.updateFromEntityEvent({
      runtime_entity_id: 100n,
      event_id: 'respawn'
    })
    assert.deepStrictEqual(respawnRes, { type: 'respawn' })
    assert.strictEqual(state.isAlive, true)
    assert.strictEqual(state.health, 20)
  })

  it('accumulates distance traveled during kinematics updates', () => {
    const state = new PlayerState()
    state.position = { x: 0, y: 64, z: 0 }

    state.updateKinematics({ x: 3, y: 64, z: 4 }, { x: 3, y: 0, z: 4 })
    assert.strictEqual(state.totalDistanceTraveled, 5.0)

    state.updateKinematics({ x: 3, y: 64, z: 9 }, { x: 0, y: 0, z: 5 })
    assert.strictEqual(state.totalDistanceTraveled, 10.0)
  })

  it('resets state for new episode', () => {
    const state = new PlayerState()
    state.position = { x: 50, y: 64, z: 50 }
    state.health = 5
    state.isAlive = false

    state.reset({ x: 79, y: 63, z: 1251 })
    const snap = state.getSnapshot()

    assert.strictEqual(snap.position.x, 79)
    assert.strictEqual(snap.position.y, 63)
    assert.strictEqual(snap.position.z, 1251)
    assert.strictEqual(snap.health, 20)
    assert.strictEqual(snap.isAlive, true)
  })

  it('initializes from start_game packet', () => {
    const state = new PlayerState()
    const packet = {
      runtime_entity_id: 488n,
      current_tick: 340000n,
      player_position: { x: 79.5, y: 64.62, z: 1251.5 },
      rotation: { x: 15.0, z: -90.0 }
    }

    const res = state.initFromStartGame(packet)
    assert.strictEqual(res, true)
    assert.strictEqual(state.runtimeEntityId, 488n)
    assert.strictEqual(state.tick, 340000n)
    assert.strictEqual(state.position.x, 79.5)
    assert.strictEqual(state.rotation.pitch, 15.0)
    assert.strictEqual(state.rotation.yaw, 270.0)
    assert.strictEqual(state.initialized, true)
  })

  it('preserves local kinematics position against normal move_player server echoes', () => {
    const state = new PlayerState()
    state.initFromStartGame({
      runtime_entity_id: 500n,
      current_tick: 1000n,
      player_position: { x: 10, y: 64, z: 10 },
      rotation: { x: 0, z: 0 }
    })

    // Local client moved forward to x=10.5
    state.updateKinematics({ x: 10.5, y: 64, z: 10 }, { x: 0.5, y: 0, z: 0 })

    // Server echoes slightly older position in mode=normal
    const echoPacket = {
      runtime_id: 500n,
      mode: 'normal',
      position: { x: 10.1, y: 64, z: 10 },
      tick: 1002n
    }
    state.updateFromMovePlayer(echoPacket)

    // Should preserve client position 10.5
    assert.strictEqual(state.position.x, 10.5)
    assert.strictEqual(state.tick, 1002n)

    // But if server teleports player to x=100
    const teleportPacket = {
      runtime_id: 500n,
      mode: 'teleport',
      position: { x: 100, y: 64, z: 100 },
      tick: 1005n
    }
    state.updateFromMovePlayer(teleportPacket)
    assert.strictEqual(state.position.x, 100)
    assert.strictEqual(state.position.z, 100)
  })

  it('safely parses 64-bit split array ticks from start_game without throwing', () => {
    const state = new PlayerState()
    const packet = {
      runtime_entity_id: '302',
      current_tick: [0, 654711],
      player_position: { x: 87.5, y: 64.62, z: 1251.5 },
      rotation: { x: 0, z: 0 }
    }

    const res = state.initFromStartGame(packet)
    assert.strictEqual(res, true)
    assert.strictEqual(state.runtimeEntityId, 302n)
    assert.strictEqual(state.tick, 654711n)
    assert.strictEqual(state.position.x, 87.5)
  })
})

