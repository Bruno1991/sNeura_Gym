/**
 * s_Neura_Gym - Protocol Test
 *
 * Responsibility:
 * Verifies how bedrock-protocol/protodef serializes
 * the player_auth_input packet for Bedrock 1.26.51.
 *
 * This file is a diagnostic tool only.
 * It does not connect to Minecraft.
 */

const { createSerializer } = require('bedrock-protocol/src/transforms/serializer')

const serializer = createSerializer('1.26.51')

const base = {
  pitch: 0,
  yaw: 0,

  position: {
    x: 0,
    y: 63,
    z: 0
  },

  move_vector: {
    x: 0,
    z: 1
  },

  head_yaw: 0,

  input_mode: 'mouse',
  play_mode: 'normal',

  interaction_model: 'crosshair',

  interact_rotation: {
    x: 0,
    y: 0
  },

  tick: 0n,

  delta: {
    x: 0,
    y: 0,
    z: 0
  },

  analogue_move_vector: {
    x: 0,
    z: 1
  },

  camera_orientation: {
    x: 0,
    y: 0,
    z: 0
  },

  raw_move_vector: {
    x: 0,
    z: 1
  }
}

const candidates = [
  {
    name: 'string_up',
    input_data: ['up']
  },

  {
    name: 'number_10',
    input_data: [10]
  },

  {
    name: 'object_up',
    input_data: {
      up: true
    }
  },

  {
    name: 'empty',
    input_data: []
  }
]

for (const candidate of candidates) {
  console.log('')
  console.log('='.repeat(72))
  console.log(`TESTE: ${candidate.name}`)
  console.log('='.repeat(72))

  try {
    const packet = {
      name: 'player_auth_input',
      params: {
        ...base,
        input_data: candidate.input_data
      }
    }

    const buffer = serializer.createPacketBuffer(packet)

    console.log('[OK] Serialização realizada.')
    console.log(`[OK] Bytes: ${buffer.length}`)
    console.log(`[HEX] ${buffer.toString('hex')}`)
  } catch (error) {
    console.log('[ERRO] Falha na serialização.')
    console.log(error.message)
  }
}
