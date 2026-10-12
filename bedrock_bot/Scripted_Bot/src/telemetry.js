/**
 * s_Neura_Gym - Scripted Bot
 *
 * Responsibility:
 * Provides structured telemetry and observability for the autonomous agent.
 * Supports console output and immediate JSONL file appending for downstream
 * Gym analytics and baseline benchmarking.
 */

const fs = require('fs')
const path = require('path')

class Telemetry {
  constructor (config = {}) {
    this.consoleEnabled = config.console !== false
    this.saveToFile = config.saveToFile === true
    this.logDir = config.logDir || path.resolve(__dirname, '../telemetry')
    this.sessionId = `session_${Date.now()}`
    this.filePath = null
    this.sequence = 0

    if (this.saveToFile) {
      this._initFileLogging()
    }
  }

  _initFileLogging () {
    try {
      if (!fs.existsSync(this.logDir)) {
        fs.mkdirSync(this.logDir, { recursive: true })
      }
      this.filePath = path.join(this.logDir, `${this.sessionId}.jsonl`)
    } catch (err) {
      console.error(`[TELEMETRY] Failed to initialize file logging: ${err.message}`)
    }
  }

  timestamp () {
    return new Date().toISOString()
  }

  _safeStringify (obj) {
    return JSON.stringify(obj, (_k, v) => (typeof v === 'bigint' ? v.toString() : v))
  }

  emit (event, data = {}) {
    this.sequence += 1

    const record = {
      sessionId: this.sessionId,
      sequence: this.sequence,
      timestamp: this.timestamp(),
      event,
      data
    }

    if (this.consoleEnabled) {
      console.log(`[TELEMETRY] [${record.event}] ${this._safeStringify(record.data)}`)
    }

    if (this.saveToFile && this.filePath) {
      try {
        fs.appendFileSync(this.filePath, `${this._safeStringify(record)}\n`, 'utf-8')
      } catch (err) {
        console.error(`[TELEMETRY] Write error: ${err.message}`)
      }
    }

    return record
  }

  emitSummary (summaryData = {}) {
    return this.emit('agent_summary', {
      ...summaryData,
      uptimeSeconds: Math.floor(process.uptime())
    })
  }

  close () {
    // No open file descriptors to close with sync append
  }
}

// Export singleton instance initialized with default config, plus class for testing
const config = require('./config')
const defaultInstance = new Telemetry(config.telemetry)

module.exports = defaultInstance
module.exports.Telemetry = Telemetry
