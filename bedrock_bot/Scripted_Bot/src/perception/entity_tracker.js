/**
 * s_Neura_Gym - Scripted Bot
 *
 * Responsibility:
 * Tracks surrounding entities (players, mobs, items) observed via
 * Bedrock protocol packets.
 *
 * Provides proximity information to the autonomous decision engine.
 */

class EntityTracker {
  constructor () {
    this.entities = new Map()
  }

  addEntity (packet) {
    if (!packet || packet.runtime_entity_id === undefined) {
      return
    }

    const id = String(packet.runtime_entity_id)
    this.entities.set(id, {
      id,
      type: packet.entity_type || packet.type || 'entity',
      position: packet.position ? { ...packet.position } : { x: 0, y: 0, z: 0 },
      pitch: packet.pitch || 0,
      yaw: packet.yaw || 0,
      headYaw: packet.head_yaw || 0,
      lastSeen: Date.now()
    })
  }

  addPlayer (packet) {
    if (!packet || packet.runtime_id === undefined) {
      return
    }

    const id = String(packet.runtime_id)
    this.entities.set(id, {
      id,
      username: packet.username,
      type: 'player',
      position: packet.position ? { ...packet.position } : { x: 0, y: 0, z: 0 },
      pitch: packet.pitch || 0,
      yaw: packet.yaw || 0,
      headYaw: packet.head_yaw || 0,
      lastSeen: Date.now()
    })
  }

  updateEntity (packet) {
    if (!packet || packet.runtime_entity_id === undefined) {
      return
    }

    const id = String(packet.runtime_entity_id)
    const existing = this.entities.get(id)
    if (existing) {
      if (packet.position) {
        existing.position = { ...packet.position }
      }
      if (packet.pitch !== undefined) existing.pitch = packet.pitch
      if (packet.yaw !== undefined) existing.yaw = packet.yaw
      if (packet.head_yaw !== undefined) existing.headYaw = packet.head_yaw
      existing.lastSeen = Date.now()
    }
  }

  removeEntity (packet) {
    if (!packet || packet.entity_id_self === undefined) {
      return
    }
    const id = String(packet.entity_id_self)
    this.entities.delete(id)
  }

  getNearbyEntities (myPos, maxDistance = 20) {
    if (!myPos || myPos.x === null) {
      return []
    }

    const nearby = []
    for (const entity of this.entities.values()) {
      const dist = Math.hypot(entity.position.x - myPos.x, entity.position.z - myPos.z)
      if (dist <= maxDistance) {
        nearby.push({
          ...entity,
          distance: Number(dist.toFixed(2))
        })
      }
    }

    nearby.sort((a, b) => a.distance - b.distance)
    return nearby
  }

  clear () {
    this.entities.clear()
  }
}

module.exports = EntityTracker
