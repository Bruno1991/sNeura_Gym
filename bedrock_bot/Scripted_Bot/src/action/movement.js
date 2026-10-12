/**
 * s_Neura_Gym - Scripted Bot
 *
 * Responsibility:
 * Controls the local player's physical locomotion and generates the Bedrock
 * PlayerAuthInput protocol stream with accurate kinematics, displacement deltas,
 * heading trigonometry, and jump dynamics.
 *
 * Primitives:
 * - walkForward, walkBackward, strafeLeft, strafeRight, stopWalking
 * - jump, sprint, sneak
 * - lookAt, setRotation, rotateToward
 * - stopAll
 */

const { randomUUID } = require('crypto')

class Movement {
  constructor (client, playerState, options = {}) {
    this.client = client
    this.playerState = playerState

    this.tick = 0n
    this.timer = null
    this.tickRateMs = options.tickRateMs || 50

    // Locomotion flags
    this.walkingForward = false
    this.walkingBackward = false
    this.strafingLeft = false
    this.strafingRight = false
    this.sprinting = false
    this.sneaking = false

    // Jump dynamics
    this.isJumping = false
    this.jumpTicksRemaining = 0
    this.verticalVelocity = 0
    this.groundY = 63

    // Speeds (blocks per tick at 20 ticks/sec)
    this.BASE_WALK_SPEED = 0.2158
    this.SPRINT_SPEED = 0.2806
    this.SNEAK_SPEED = 0.065

    // Rotation interpolation
    this.targetYaw = null
    this.targetPitch = null
    this.turnRateDegPerTick = 25

    // Authoritative locomotion driver for BDS Dedicated Server
    this.authoritativeDriver = options.authoritativeDriver ?? false
    this.pendingDeltaX = 0
    this.pendingDeltaZ = 0
    this.pendingDeltaY = 0
    this.accumulatedTicks = 0
    this.lastDispatchedYaw = null
    this.feedbackSuppressed = false
  }

  enableAuthoritativeLocomotion (enable = true) {
    this.authoritativeDriver = enable
  }

  sendCommand (command) {
    if (!this.client || typeof this.client.queue !== 'function') return
    try {
      this.client.queue('command_request', {
        command,
        origin: {
          type: 'player',
          uuid: randomUUID(),
          request_id: '',
          player_entity_id: 0n
        },
        internal: false,
        version: 'latest'
      })
    } catch (e) {
      // client error or disconnected
    }
  }

  initAuthoritative () {
    if (!this.feedbackSuppressed) {
      this.sendCommand('/gamerule sendcommandfeedback false')
      this.feedbackSuppressed = true
    }
  }

  flushAuthoritativeMovement (currentRotation) {
    const dx = this.pendingDeltaX.toFixed(3)
    const dy = Math.abs(this.pendingDeltaY) > 0.05 ? this.pendingDeltaY.toFixed(3) : ''
    const dz = this.pendingDeltaZ.toFixed(3)
    const yaw = (currentRotation.yaw ?? 0).toFixed(1)
    const pitch = (currentRotation.pitch ?? 0).toFixed(1)

    this.sendCommand(`/tp @s ~${dx} ~${dy} ~${dz} ${yaw} ${pitch}`)
    this.lastDispatchedYaw = currentRotation.yaw

    this.pendingDeltaX = 0
    this.pendingDeltaZ = 0
    this.pendingDeltaY = 0
    this.accumulatedTicks = 0
  }

  teleportTo (x, y, z, yaw = 0, pitch = 0) {
    if (this.authoritativeDriver && this.client) {
      this.sendCommand(`/tp @s ${x.toFixed(2)} ${y.toFixed(2)} ${z.toFixed(2)} ${yaw} ${pitch}`)
      this.pendingDeltaX = 0
      this.pendingDeltaZ = 0
      this.pendingDeltaY = 0
      this.accumulatedTicks = 0
    }
  }

  setClient (client) {
    this.client = client
  }

  start () {
    if (this.timer !== null) {
      return
    }

    this.timer = setInterval(() => {
      this.update()
    }, this.tickRateMs)
  }

  stop () {
    if (this.timer === null) {
      return
    }

    clearInterval(this.timer)
    this.timer = null
    this.stopAll()
  }

  walkForward () {
    this.walkingForward = true
    this.walkingBackward = false
  }

  walkBackward () {
    this.walkingBackward = true
    this.walkingForward = false
  }

  strafeLeft () {
    this.strafingLeft = true
    this.strafingRight = false
  }

  strafeRight () {
    this.strafingRight = true
    this.strafingLeft = false
  }

  stopWalking () {
    this.walkingForward = false
    this.walkingBackward = false
    this.strafingLeft = false
    this.strafingRight = false
  }

  sprint (enable = true) {
    this.sprinting = enable
    if (enable) this.sneaking = false
  }

  sneak (enable = true) {
    this.sneaking = enable
    if (enable) this.sprinting = false
  }

  jump () {
    if (this.isJumping) return

    this.isJumping = true
    this.jumpTicksRemaining = 7
    this.verticalVelocity = 0.42
  }

  stopAll () {
    this.stopWalking()
    this.sprinting = false
    this.sneaking = false
    this.isJumping = false
    this.jumpTicksRemaining = 0
    this.verticalVelocity = 0

    if (this.authoritativeDriver && this.client && Math.hypot(this.pendingDeltaX, this.pendingDeltaZ) > 0.01) {
      const state = this.playerState ? this.playerState.getSnapshot() : null
      const rot = state ? state.rotation : { yaw: 0, pitch: 0 }
      this.flushAuthoritativeMovement(rot)
    }
  }

  isMoving () {
    return this.walkingForward || this.walkingBackward || this.strafingLeft || this.strafingRight
  }

  setRotation (yaw, pitch = 0, headYaw = null) {
    const normalizedYaw = ((yaw % 360) + 360) % 360
    this.targetYaw = normalizedYaw
    this.targetPitch = pitch

    const currentRotation = {
      pitch,
      yaw: normalizedYaw,
      headYaw: headYaw !== null ? headYaw : normalizedYaw
    }

    const state = this.playerState.getSnapshot()
    this.playerState.updateKinematics(state.position, null, currentRotation)
  }

  lookAt (targetX, targetZ, targetY = null) {
    const state = this.playerState.getSnapshot()
    if (state.position.x === null || state.position.z === null) {
      return
    }

    const dx = targetX - state.position.x
    const dz = targetZ - state.position.z

    // Minecraft Bedrock rotation formula:
    // 0 is South (+Z), 90 is West (-X), 180 is North (-Z), 270 is East (+X)
    let yaw = Math.atan2(-dx, dz) * (180 / Math.PI)
    yaw = ((yaw % 360) + 360) % 360

    let pitch = 0
    if (targetY !== null && state.position.y !== null) {
      const dy = targetY - state.position.y
      const horizontalDist = Math.hypot(dx, dz)
      pitch = Math.atan2(-dy, horizontalDist) * (180 / Math.PI)
    }

    this.targetYaw = yaw
    this.targetPitch = pitch
  }

  rotateToward (targetYaw, maxStep = null) {
    this.targetYaw = ((targetYaw % 360) + 360) % 360
    if (maxStep) {
      this.turnRateDegPerTick = maxStep
    }
  }

  _interpolateRotation (currentRotation) {
    let yaw = currentRotation.yaw ?? 0
    let pitch = currentRotation.pitch ?? 0

    if (this.targetYaw !== null) {
      let diff = this.targetYaw - yaw
      // Find shortest turn direction on circle [-180, 180]
      while (diff < -180) diff += 360
      while (diff > 180) diff -= 360

      if (Math.abs(diff) <= this.turnRateDegPerTick) {
        yaw = this.targetYaw
      } else {
        yaw += Math.sign(diff) * this.turnRateDegPerTick
      }
      yaw = ((yaw % 360) + 360) % 360
    }

    if (this.targetPitch !== null) {
      const pDiff = this.targetPitch - pitch
      if (Math.abs(pDiff) <= 5) {
        pitch = this.targetPitch
      } else {
        pitch += Math.sign(pDiff) * 5
      }
    }

    return {
      yaw,
      pitch,
      headYaw: yaw
    }
  }

  update () {
    const state = this.playerState.getSnapshot()

    if (!state.initialized) {
      return
    }

    if (
      state.position.x === null ||
      state.position.y === null ||
      state.position.z === null
    ) {
      return
    }

    // Synchronize tick with server tick if available
    if (state.tick !== undefined && state.tick > 0n) {
      if (this.tick === 0n || state.tick > this.tick + 20n || this.tick > state.tick + 40n) {
        this.tick = state.tick
      }
    }

    // Set initial ground level if not yet set
    if (this.groundY === null || isNaN(this.groundY)) {
      this.groundY = state.position.y
    }

    // 1. Calculate Rotation
    const currentRotation = this._interpolateRotation(state.rotation)

    // 2. Calculate Horizontal Movement Vectors & Speed
    let currentSpeed = this.BASE_WALK_SPEED
    if (this.sprinting) currentSpeed = this.SPRINT_SPEED
    else if (this.sneaking) currentSpeed = this.SNEAK_SPEED

    let moveX = 0
    let moveZ = 0
    const inputData = []

    if (this.walkingForward) {
      moveZ += 1
      inputData.push('up')
    }
    if (this.walkingBackward) {
      moveZ -= 1
      inputData.push('down')
    }
    if (this.strafingLeft) {
      moveX += 1
      inputData.push('left')
    }
    if (this.strafingRight) {
      moveX -= 1
      inputData.push('right')
    }

    if (this.sprinting && this.walkingForward) {
      inputData.push('sprinting')
      inputData.push('start_sprinting')
    }
    if (this.sneaking) {
      inputData.push('sneaking')
      inputData.push('start_sneaking')
    }

    // Convert analog direction to world displacement based on yaw
    const yawRad = (currentRotation.yaw * Math.PI) / 180
    const pitchRad = (currentRotation.pitch * Math.PI) / 180
    let deltaX = 0
    let deltaZ = 0

    if (moveZ !== 0 || moveX !== 0) {
      // Forward/backward vector
      const forwardX = -Math.sin(yawRad) * moveZ
      const forwardZ = Math.cos(yawRad) * moveZ

      // Strafe vector (perpendicular)
      const strafeX = -Math.cos(yawRad) * moveX
      const strafeZ = -Math.sin(yawRad) * moveX

      // Normalize combined horizontal vector
      const combinedX = forwardX + strafeX
      const combinedZ = forwardZ + strafeZ
      const length = Math.hypot(combinedX, combinedZ)

      if (length > 0) {
        deltaX = (combinedX / length) * currentSpeed
        deltaZ = (combinedZ / length) * currentSpeed
      }
    }

    // 3. Calculate Vertical Jump & Gravity
    let deltaY = 0
    if (this.isJumping) {
      inputData.push('jumping')
      if (this.jumpTicksRemaining === 7) {
        inputData.push('start_jumping')
      }

      deltaY = this.verticalVelocity
      this.verticalVelocity = (this.verticalVelocity - 0.08) * 0.98
      this.jumpTicksRemaining -= 1

      if (this.jumpTicksRemaining <= 0) {
        this.isJumping = false
        this.verticalVelocity = 0
      }
    }

    let nextY = state.position.y + deltaY
    if (!this.isJumping && this.groundY !== null && nextY < this.groundY) {
      nextY = this.groundY
      deltaY = 0
    }

    // Calculate new position
    const newPos = {
      x: Number((state.position.x + deltaX).toFixed(3)),
      y: Number(nextY.toFixed(3)),
      z: Number((state.position.z + deltaZ).toFixed(3))
    }

    const delta = {
      x: Number(deltaX.toFixed(3)),
      y: Number(deltaY.toFixed(3)),
      z: Number(deltaZ.toFixed(3))
    }

    // Update player state kinematics
    this.playerState.updateKinematics(newPos, delta, currentRotation)

    const moveVector = {
      x: moveX,
      z: moveZ
    }

    // Calculate camera unit direction vector
    const cameraOrientation = {
      x: Number((-Math.sin(yawRad) * Math.cos(pitchRad)).toFixed(4)),
      y: Number((-Math.sin(pitchRad)).toFixed(4)),
      z: Number((Math.cos(yawRad) * Math.cos(pitchRad)).toFixed(4))
    }

    // 4. Send Bedrock PlayerAuthInput & MovePlayer packets
    if (this.client) {
      try {
        this.client.queue('player_auth_input', {
          pitch: currentRotation.pitch,
          yaw: currentRotation.yaw,
          position: newPos,
          move_vector: moveVector,
          head_yaw: currentRotation.headYaw,
          input_data: inputData,
          input_mode: 'mouse',
          play_mode: 'normal',
          interaction_model: 'crosshair',
          interact_rotation: {
            x: 0,
            y: 0
          },
          tick: this.tick,
          delta: delta,
          analogue_move_vector: moveVector,
          camera_orientation: cameraOrientation,
          raw_move_vector: moveVector
        })

        if (state.runtimeEntityId !== null) {
          this.client.queue('move_player', {
            runtime_id: Number(state.runtimeEntityId),
            position: newPos,
            pitch: currentRotation.pitch,
            yaw: currentRotation.yaw,
            head_yaw: currentRotation.headYaw,
            mode: 'normal',
            on_ground: state.onGround ?? true,
            ridden_runtime_id: 0,
            teleport: null,
            tick: this.tick
          })
        }
      } catch (err) {
        // Suppress client disconnect queue error if connection dropped
      }
    }

    // 5. Authoritative locomotion synchronization for BDS Dedicated Server
    if (this.authoritativeDriver && this.client) {
      this.initAuthoritative()

      if (this.isMoving()) {
        this.pendingDeltaX += deltaX
        this.pendingDeltaZ += deltaZ
        this.pendingDeltaY += deltaY
        this.accumulatedTicks += 1

        const horizDist = Math.hypot(this.pendingDeltaX, this.pendingDeltaZ)
        if (horizDist >= 0.25 || this.accumulatedTicks >= 2) {
          this.flushAuthoritativeMovement(currentRotation)
        }
      } else {
        if (Math.hypot(this.pendingDeltaX, this.pendingDeltaZ) > 0.01) {
          this.flushAuthoritativeMovement(currentRotation)
        }

        if (this.lastDispatchedYaw === null || Math.abs(currentRotation.yaw - this.lastDispatchedYaw) >= 15) {
          this.sendCommand(`/tp @s ~ ~ ~ ${currentRotation.yaw.toFixed(1)} ${currentRotation.pitch.toFixed(1)}`)
          this.lastDispatchedYaw = currentRotation.yaw
        }
      }
    }

    this.tick += 1n
  }
}

module.exports = Movement
