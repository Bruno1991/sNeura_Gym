# s_Neura_Gym — Scripted Bot (Autonomous Baseline)

External Minecraft Bedrock agent used as the deterministic baseline for the `s_Neura_Gym` reinforcement learning framework.

## Purpose

The Scripted Bot is an external Bedrock client acting as an autonomous reference agent.
It connects to a Minecraft Bedrock Dedicated Server (BDS) over the network protocol, observing the world and executing autonomous behaviors without server modifications.

## Architecture

The architecture adheres to the production bot standards defined in `engineering-library`:

```text
s_Neura_Gym
└── bedrock_bot
    ├── Neural_Bot
    └── Scripted_Bot
        ├── src
        │   ├── action
        │   │   └── movement.js           # Locomotion kinematics, Bedrock PlayerAuthInput stream
        │   ├── decision
        │   │   └── autonomous_brain.js   # Finite State Machine & autonomous decision engine
        │   ├── environment
        │   │   ├── reset.js              # Environment episode reset & respawn coordination
        │   │   ├── rules.js              # Boundaries, void hazards, and safety constraints
        │   │   ├── spawn.js              # Spawn coordinates and bounded waypoint generation
        │   │   └── world_state.js        # Day/night cycle, dimension, weather observation
        │   ├── perception
        │   │   ├── entity_tracker.js     # Nearby players and entities tracker
        │   │   └── player_state.js       # Player position, kinematics, health, survival state
        │   ├── config.js                 # Central configuration (server, autonomy, resilience)
        │   ├── index.js                  # Master orchestrator & resilient connection manager
        │   └── telemetry.js              # Structured console & persistent JSONL logger
        │
        ├── telemetry/                    # Session JSONL logs for Gym benchmarking
        ├── tests/                        # Automated unit & integration tests (Node native)
        │   ├── autonomous_brain.test.js
        │   ├── movement.test.js
        │   ├── player_state.test.js
        │   ├── spawn_and_rules.test.js
        │   └── telemetry.test.js
        ├── tools/
        │   ├── simulate_autonomy.js      # Offline autonomous loop simulation runner
        │   └── test_player_auth_input.js # Bedrock protocol serialization diagnostic
        ├── package.json
        └── README.md
```

## Autonomous Capabilities

1. **Continuous Cognitive Cycle**:
   - Runs a 10 Hz decision tick (`AutonomousBrain`) and a 20 Hz movement physics tick (`Movement`).
   - Finite State Machine states: `INITIALIZING`, `IDLE`, `CHOOSING_GOAL`, `NAVIGATING`, `ARRIVED`, `STUCK_RECOVERY`, `RETURNING_TO_BOUNDS`, `RESPAWNING`.

2. **Kinematics & Bedrock PlayerAuthInput Protocol**:
   - Calculates realistic displacement deltas (`deltaX`, `deltaY`, `deltaZ`) and updates client coordinates.
   - Bedrock rotation trigonometry (`0° South`, `90° West`, `180° North`, `270° East`) with smooth heading interpolation.
   - Jump dynamics with vertical velocity and gravity simulation.

3. **Obstacle Detection & Multi-Phase Unstuck**:
   - Monitors displacement over a sliding window (`stuckWindowMs`).
   - Phase 1: Jumps over 1-block obstacles while advancing.
   - Phase 2: Backtracks for 1 second if forward path remains obstructed.
   - Phase 3: Turns 90° away and selects an alternative open trajectory.

4. **Perimeter Enforcement**:
   - Prevents the agent from drifting into unloaded chunks by enforcing an allowable radius (`maxRadius`) around `spawn`.
   - Triggers `RETURNING_TO_BOUNDS` when the perimeter is approached.

5. **Survival & Environment Reset**:
   - Monitors health and hunger attributes (`update_attributes` packet).
   - Handles damage events, void falls (`y < -64`), and death with automated respawn and episode reset.

6. **Connection Resilience**:
   - Exponential backoff reconnection loop upon server disconnects or restarts.

## Verification & Execution

### Run Automated Tests (100% pass)
```bash
npm test
```

### Run Offline Autonomous Simulation
```bash
node tools/simulate_autonomy.js
```

### Start Bot Against BDS
```bash
npm start
```
