/**
 * s_Neura_Gym - Scripted Bot
 *
 * Responsibility:
 * Manages the environment reset lifecycle for training episodes.
 * Cleans up navigation state, resets player metrics, and re-anchors
 * the agent to the designated spawn location.
 */

class EnvironmentReset {
  constructor (options = {}) {
    this.client = options.client || null
    this.playerState = options.playerState || null
    this.spawnManager = options.spawnManager || null
    this.movement = options.movement || null
    this.telemetry = options.telemetry || null
    this.episodeCount = 0
  }

  setClient (client) {
    this.client = client
  }

  resetEpisode (reason = 'manual_reset') {
    this.episodeCount += 1

    if (this.movement) {
      this.movement.stopAll()
    }

    const spawn = this.spawnManager ? this.spawnManager.getSpawn() : { x: 79, y: 63, z: 1251 }

    // If client is dead and connected, send respawn packet to server
    if (this.client && this.playerState && !this.playerState.isAlive) {
      try {
        const state = this.playerState.getSnapshot()
        if (state.runtimeEntityId !== null) {
          this.client.queue('respawn', {
            position: { x: spawn.x, y: spawn.y, z: spawn.z },
            state: 2, // SearchingForSpawn / ClientReadyToSpawn
            runtime_entity_id: BigInt(state.runtimeEntityId)
          })
        }
      } catch (err) {
        // Fallback if queue fails
      }
    }

    if (this.movement && typeof this.movement.teleportTo === 'function') {
      this.movement.teleportTo(spawn.x, spawn.y, spawn.z)
    }

    if (this.playerState) {
      this.playerState.reset(spawn)
    }

    if (this.telemetry) {
      this.telemetry.emit('environment_reset', {
        episode: this.episodeCount,
        reason,
        spawnPosition: spawn
      })
    }

    return {
      episode: this.episodeCount,
      reason,
      spawn
    }
  }

  getEpisodeCount () {
    return this.episodeCount
  }
}

module.exports = EnvironmentReset
