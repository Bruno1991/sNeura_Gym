/**
 * s_Neura_Gym - Scripted Bot
 *
 * Responsibility:
 * Autonomous Decision Engine & Behavior State Machine.
 * Executes the continuous perceive-decide-act loop:
 *
 * States:
 * - INITIALIZING: Waiting for spawn and client readiness.
 * - IDLE: Pausing between goals, surveying environment.
 * - CHOOSING_GOAL: Generating valid waypoints within environment bounds.
 * - NAVIGATING: Actively steering and walking towards waypoint.
 * - ARRIVED: Successfully reached waypoint.
 * - STUCK_RECOVERY: Multi-stage obstacle avoidance (jump, backtrack, steer away).
 * - RETURNING_TO_BOUNDS: Enforces perimeter return when approaching borders.
 * - RESPAWNING: Handles death and respawn re-anchoring.
 */

class AutonomousBrain {
  constructor (options = {}) {
    this.playerState = options.playerState
    this.movement = options.movement
    this.spawnManager = options.spawnManager
    this.environmentRules = options.environmentRules
    this.environmentReset = options.environmentReset
    this.telemetry = options.telemetry
    this.config = options.config || {}

    // State machine
    this.state = 'INITIALIZING'
    this.timer = null
    this.decisionTickMs = this.config.decisionTickMs || 100

    // Goal & Navigation
    this.currentGoal = null
    this.lastStateTransition = Date.now()
    this.pauseUntil = 0
    this.waypointsReached = 0

    // Stuck detection
    this.lastPositionCheck = null
    this.lastPositionCheckTime = Date.now()
    this.stuckAttempts = 0
    this.stuckRecoveryPhase = 0
    this.stuckRecoveryUntil = 0

    // Head surveying
    this.lastSurveyTime = Date.now()
    this.surveyIntervalMs = this.config.headSurvey?.intervalMs || 2500

    // Cumulative stats
    this.totalStuckEvents = 0
    this.mode = this.config.mode || 'wander'
    this.paused = false
  }

  start () {
    if (this.timer !== null) return

    this.timer = setInterval(() => {
      if (!this.paused) {
        this.think()
      }
    }, this.decisionTickMs)

    if (this.telemetry) {
      this.telemetry.emit('brain_started', {
        mode: this.mode,
        decisionTickMs: this.decisionTickMs
      })
    }
  }

  stop () {
    if (this.timer === null) return

    clearInterval(this.timer)
    this.timer = null

    if (this.movement) {
      this.movement.stopAll()
    }

    if (this.telemetry) {
      this.telemetry.emit('brain_stopped', {
        finalState: this.state,
        waypointsReached: this.waypointsReached,
        totalStuckEvents: this.totalStuckEvents
      })
    }
  }

  pause () {
    this.paused = true
    if (this.movement) this.movement.stopAll()
  }

  resume () {
    this.paused = false
  }

  setMode (mode) {
    this.mode = mode
    this.currentGoal = null
    this.transitionTo('CHOOSING_GOAL')
  }

  setGoal (x, z, y = null) {
    this.currentGoal = { x, y, z }
    this.transitionTo('NAVIGATING')
  }

  transitionTo (newState, reason = '') {
    const oldState = this.state
    this.state = newState
    this.lastStateTransition = Date.now()

    if (this.telemetry) {
      this.telemetry.emit('state_transition', {
        from: oldState,
        to: newState,
        reason,
        position: this.playerState ? this.playerState.position : null,
        goal: this.currentGoal
      })
    }
  }

  think () {
    const snapshot = this.playerState ? this.playerState.getSnapshot() : null

    if (!snapshot || !snapshot.initialized || snapshot.position.x === null) {
      if (this.state !== 'INITIALIZING') {
        this.transitionTo('INITIALIZING', 'Awaiting player position')
      }
      return
    }

    // 1. High-priority safety checks: Death, Void, Bounds
    if (this.environmentRules) {
      const evaluation = this.environmentRules.evaluate(snapshot)

      if (!evaluation.compliant) {
        for (const violation of evaluation.violations) {
          if (violation.type === 'PLAYER_DEAD') {
            this.handleDeath()
            return
          }
          if (violation.type === 'VOID_FALL') {
            this.handleVoidFall()
            return
          }
          if (violation.type === 'OUT_OF_BOUNDS') {
            if (this.state !== 'RETURNING_TO_BOUNDS') {
              this.transitionTo('RETURNING_TO_BOUNDS', violation.message)
            }
          }
        }
      }
    }

    // 2. State-specific decision logic
    switch (this.state) {
      case 'INITIALIZING':
        this.handleInitializing(snapshot)
        break

      case 'IDLE':
        this.handleIdle(snapshot)
        break

      case 'CHOOSING_GOAL':
        this.handleChoosingGoal(snapshot)
        break

      case 'NAVIGATING':
        this.handleNavigating(snapshot)
        break

      case 'ARRIVED':
        this.handleArrived(snapshot)
        break

      case 'STUCK_RECOVERY':
        this.handleStuckRecovery(snapshot)
        break

      case 'RETURNING_TO_BOUNDS':
        this.handleReturningToBounds(snapshot)
        break

      case 'RESPAWNING':
        this.handleRespawning(snapshot)
        break

      default:
        this.transitionTo('IDLE', 'Unknown state fallback')
        break
    }
  }

  handleInitializing (snapshot) {
    if (snapshot.initialized && snapshot.position.x !== null) {
      if (this.movement) {
        this.movement.groundY = snapshot.position.y
      }
      this.transitionTo('IDLE', 'Player initialized successfully')
    }
  }

  handleIdle (snapshot) {
    // If pause duration expired, proceed to next action
    if (Date.now() >= this.pauseUntil) {
      if (this.mode === 'idle') {
        // Stay idle if explicitly in idle mode
        this.pauseUntil = Date.now() + 5000
        return
      }
      this.handleChoosingGoal(snapshot)
      return
    }

    // While idling, periodically survey the environment with head movement
    if (this.config.headSurvey?.enabled !== false) {
      if (Date.now() - this.lastSurveyTime > this.surveyIntervalMs) {
        this.lastSurveyTime = Date.now()
        this.performHeadSurvey(snapshot)
      }
    }
  }

  performHeadSurvey (snapshot) {
    if (!this.movement) return

    const yawVariation = (Math.random() - 0.5) * (this.config.headSurvey?.maxYawVariation || 40)
    const pitchVariation = (Math.random() - 0.5) * (this.config.headSurvey?.maxPitchVariation || 20)

    const newYaw = (snapshot.rotation.yaw + yawVariation + 360) % 360
    const newPitch = Math.max(-30, Math.min(30, snapshot.rotation.pitch + pitchVariation))

    this.movement.setRotation(newYaw, newPitch)
  }

  handleChoosingGoal (snapshot) {
    if (this.spawnManager) {
      const minStep = this.config.wander?.minDistance || 4
      const maxStep = this.config.wander?.maxDistance || 14
      this.currentGoal = this.spawnManager.generateRandomWaypoint(snapshot.position, minStep, maxStep)
    } else {
      this.currentGoal = {
        x: snapshot.position.x + (Math.random() * 10 - 5),
        y: snapshot.position.y,
        z: snapshot.position.z + (Math.random() * 10 - 5)
      }
    }

    // Reset stuck monitor
    this.lastPositionCheck = { ...snapshot.position }
    this.lastPositionCheckTime = Date.now()
    this.stuckAttempts = 0

    this.transitionTo('NAVIGATING', `Goal selected: (${this.currentGoal.x}, ${this.currentGoal.z})`)
  }

  handleNavigating (snapshot) {
    if (!this.currentGoal) {
      this.transitionTo('CHOOSING_GOAL', 'No current goal')
      return
    }

    const dist = Math.hypot(
      this.currentGoal.x - snapshot.position.x,
      this.currentGoal.z - snapshot.position.z
    )

    const arrivalRadius = this.config.wander?.arrivalRadius || 1.5

    // Check if goal reached
    if (dist <= arrivalRadius) {
      this.handleArrived(snapshot)
      return
    }

    // Steer towards goal
    if (this.movement) {
      this.movement.lookAt(this.currentGoal.x, this.currentGoal.z)
      this.movement.walkForward()
    }

    // Monitor for stuck condition
    this.checkStuckCondition(snapshot)
  }

  checkStuckCondition (snapshot) {
    const windowMs = this.config.obstacleAvoidance?.stuckWindowMs || 1500
    const threshold = this.config.obstacleAvoidance?.stuckThreshold || 0.15

    if (Date.now() - this.lastPositionCheckTime >= windowMs) {
      if (this.lastPositionCheck && this.lastPositionCheck.x !== null) {
        const movedDist = Math.hypot(
          snapshot.position.x - this.lastPositionCheck.x,
          snapshot.position.z - this.lastPositionCheck.z
        )

        // If moving was commanded but actual movement was below threshold -> STUCK!
        if (this.movement && this.movement.isMoving() && movedDist < threshold) {
          this.totalStuckEvents += 1
          this.transitionTo('STUCK_RECOVERY', `Blocked by obstacle (moved ${movedDist.toFixed(3)}m < ${threshold}m)`)
          return
        }
      }

      this.lastPositionCheck = { ...snapshot.position }
      this.lastPositionCheckTime = Date.now()
    }
  }

  handleStuckRecovery (snapshot) {
    const now = Date.now()

    if (now < this.stuckRecoveryUntil) {
      // Still executing current recovery phase
      return
    }

    // Advance recovery phase
    this.stuckRecoveryPhase += 1

    if (this.stuckRecoveryPhase === 1) {
      // Phase 1: Try jumping over the 1-block obstacle while moving forward
      if (this.movement) {
        this.movement.walkForward()
        this.movement.jump()
      }
      this.stuckRecoveryUntil = now + 600
    } else if (this.stuckRecoveryPhase === 2) {
      // Phase 2: Still stuck, back up for 1 second
      if (this.movement) {
        this.movement.walkBackward()
      }
      const backtrackMs = this.config.obstacleAvoidance?.backtrackDurationMs || 1000
      this.stuckRecoveryUntil = now + backtrackMs
    } else {
      // Phase 3: Rotate away from obstacle by 90 degrees and pick a fresh goal
      const turnDeg = (Math.random() > 0.5 ? 1 : -1) * (this.config.obstacleAvoidance?.turnAngleDeg || 90)
      const newYaw = (snapshot.rotation.yaw + turnDeg + 360) % 360

      if (this.movement) {
        this.movement.stopAll()
        this.movement.setRotation(newYaw, 0)
      }

      this.stuckRecoveryPhase = 0
      this.lastPositionCheck = { ...snapshot.position }
      this.lastPositionCheckTime = Date.now()

      // Reset goal and pick new path immediately
      this.handleChoosingGoal(snapshot)
    }
  }

  handleArrived (snapshot) {
    this.waypointsReached += 1

    if (this.movement) {
      this.movement.stopAll()
    }

    const pauseMin = this.config.wander?.pauseMinMs || 1000
    const pauseMax = this.config.wander?.pauseMaxMs || 3000
    const pauseDuration = pauseMin + Math.random() * (pauseMax - pauseMin)
    this.pauseUntil = Date.now() + pauseDuration

    if (this.telemetry) {
      this.telemetry.emit('waypoint_arrived', {
        waypointIndex: this.waypointsReached,
        reachedAt: snapshot.position,
        totalDistance: snapshot.stats.totalDistanceTraveled,
        pauseMs: Math.round(pauseDuration)
      })
    }

    this.transitionTo('IDLE', `Arrived at waypoint #${this.waypointsReached}`)
  }

  handleReturningToBounds (snapshot) {
    if (!this.spawnManager) {
      this.transitionTo('CHOOSING_GOAL', 'No spawn manager to return to')
      return
    }

    const spawn = this.spawnManager.getSpawn()
    const distToSpawn = this.spawnManager.getDistanceToSpawn(snapshot.position)

    // Check if back safely inside bounds
    if (distToSpawn <= (this.spawnManager.maxRadius * 0.7)) {
      if (this.movement) this.movement.stopAll()
      this.transitionTo('IDLE', `Successfully returned inside bounds (dist: ${distToSpawn.toFixed(2)}m)`)
      return
    }

    // Direct movement toward spawn
    if (this.movement) {
      this.movement.lookAt(spawn.x, spawn.z)
      this.movement.walkForward()
    }

    this.checkStuckCondition(snapshot)
  }

  handleDeath () {
    this.transitionTo('RESPAWNING', 'Player died')
    if (this.movement) this.movement.stopAll()

    if (this.environmentReset) {
      this.environmentReset.resetEpisode('player_death')
    }
  }

  handleVoidFall () {
    this.transitionTo('RESPAWNING', 'Fell into the void')
    if (this.movement) this.movement.stopAll()

    if (this.environmentReset) {
      this.environmentReset.resetEpisode('void_fall')
    }
  }

  handleRespawning (snapshot) {
    if (snapshot.isAlive && snapshot.position.y !== null && snapshot.position.y > -60) {
      this.transitionTo('INITIALIZING', 'Respawn confirmed, reinitializing')
    }
  }

  getSnapshot () {
    return {
      state: this.state,
      mode: this.mode,
      currentGoal: this.currentGoal,
      waypointsReached: this.waypointsReached,
      totalStuckEvents: this.totalStuckEvents,
      uptimeSeconds: Math.floor((Date.now() - this.lastStateTransition) / 1000)
    }
  }
}

module.exports = AutonomousBrain
