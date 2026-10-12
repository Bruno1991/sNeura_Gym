const { describe, it } = require('node:test')
const assert = require('node:assert')
const fs = require('fs')
const path = require('path')
const os = require('os')
const { Telemetry } = require('../src/telemetry')

describe('Telemetry Service', () => {
  it('emits structured records with sequence numbers and timestamps', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'telemetry-test-'))
    const t = new Telemetry({
      console: false,
      saveToFile: true,
      logDir: tmpDir
    })

    const record1 = t.emit('test_event_1', { foo: 'bar' })
    assert.strictEqual(record1.sequence, 1)
    assert.strictEqual(record1.event, 'test_event_1')
    assert.strictEqual(record1.data.foo, 'bar')
    assert.ok(record1.timestamp)

    const record2 = t.emit('test_event_2', { count: 42 })
    assert.strictEqual(record2.sequence, 2)

    const summary = t.emitSummary({ state: 'IDLE' })
    assert.strictEqual(summary.event, 'agent_summary')
    assert.strictEqual(summary.data.state, 'IDLE')

    t.close()

    // Verify file content was written
    const files = fs.readdirSync(tmpDir)
    assert.strictEqual(files.length, 1)
    const fileContent = fs.readFileSync(path.join(tmpDir, files[0]), 'utf-8')
    const lines = fileContent.trim().split('\n')
    assert.strictEqual(lines.length, 3)

    const parsed1 = JSON.parse(lines[0])
    assert.strictEqual(parsed1.event, 'test_event_1')

    // Clean up
    fs.rmSync(tmpDir, { recursive: true, force: true })
  })
})
