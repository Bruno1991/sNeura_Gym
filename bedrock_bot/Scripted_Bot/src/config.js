/**
 * s_Neura_Gym - Scripted Bot
 *
 * Responsibility:
 * Centralizes configuration for the Bedrock client, perception,
 * movement physics, environment boundaries, autonomous decision engine,
 * resilience, and telemetry.
 *
 * Follows the s_Neura_Gym deterministic baseline architecture.
 */

const path = require('path')

module.exports = {
  server: {
    host: process.env.BDS_HOST || '10.9.21.15',
    port: parseInt(process.env.BDS_PORT || '19132', 10),
    version: process.env.BDS_VERSION || '1.26.51'
  },

  player: {
    username: process.env.BOT_USERNAME || 'Saile_ScriptedBot',
    offline: process.env.BOT_OFFLINE === 'true' || false
  },

  environment: {
    spawn: {
      x: 79,
      y: 63,
      z: 1251
    },
    // Maximum allowable horizontal exploration radius from spawn (blocks)
    maxRadius: 35,
    // Void height threshold
    minY: -64,
    // Auto reset if agent falls into void or critical state
    autoResetOnVoid: true
  },

  autonomy: {
    enabled: true,
    // Operational mode: 'wander' | 'patrol' | 'idle'
    mode: 'wander',
    // Brain thinking interval in milliseconds (10 Hz)
    decisionTickMs: 100,
    // Movement simulation tick in milliseconds (20 Hz - standard Minecraft tick)
    movementTickMs: 50,
    // Waypoint navigation settings
    wander: {
      minDistance: 4,
      maxDistance: 16,
      arrivalRadius: 1.5,
      pauseMinMs: 1000,
      pauseMaxMs: 3000
    },
    // Obstacle and collision resolution
    obstacleAvoidance: {
      stuckThreshold: 0.15, // moved less than 0.15 blocks
      stuckWindowMs: 1500,  // over 1.5 seconds while attempting to walk
      maxJumpAttempts: 2,   // attempt jumping up to 2 times
      backtrackDurationMs: 1000, // back up for 1 second if jumps fail
      turnAngleDeg: 90      // angle to turn away from blocked obstacle
    },
    // Head looking & surveying
    headSurvey: {
      enabled: true,
      intervalMs: 2500,
      maxPitchVariation: 15,
      maxYawVariation: 30
    }
  },

  resilience: {
    autoReconnect: true,
    initialDelayMs: 2000,
    maxDelayMs: 30000,
    backoffMultiplier: 1.5,
    maxReconnectAttempts: 20
  },

  telemetry: {
    console: true,
    saveToFile: true,
    logDir: path.resolve(__dirname, '../telemetry'),
    summaryIntervalMs: 10000
  }
}
