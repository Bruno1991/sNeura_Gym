/**
 * SlitherAI Simulation & Physics Engine
 * Complete Slither 2D dynamics with multi-agent neuroevolution
 */

import { FoodOrb, GameMode, Point, Snake, SnakeSegment } from './types';
import { computeSnakeSensors } from '../ai/sensors';
import { EvolutionManager } from '../ai/evolution';
import { NeuralNetwork } from '../ai/neuralNetwork';

export const ARENA_RADIUS = 2200;
const AMBIENT_FOOD_TARGET = 650;
const INITIAL_SNAKE_MASS = 15;

const SNAKE_COLORS = [
  { main: '#10B981', secondary: '#059669', name: 'Emerald' },   // Green
  { main: '#06B6D4', secondary: '#0891B2', name: 'Cyan' },      // Cyan
  { main: '#3B82F6', secondary: '#2563EB', name: 'Azure' },     // Blue
  { main: '#8B5CF6', secondary: '#7C3AED', name: 'Violet' },    // Purple
  { main: '#EC4899', secondary: '#DB2777', name: 'Rose' },      // Pink
  { main: '#F97316', secondary: '#EA580C', name: 'Amber' },     // Orange
  { main: '#EAB308', secondary: '#CA8A04', name: 'Gold' },      // Yellow
  { main: '#EF4444', secondary: '#DC2626', name: 'Crimson' },   // Red
  { main: '#14B8A6', secondary: '#0D9488', name: 'Teal' },      // Teal
  { main: '#6366F1', secondary: '#4F46E5', name: 'Indigo' },    // Indigo
];

const BOT_NAMES = [
  'Viper_AI', 'Naga_01', 'Ouroboros', 'PythonX', 'Cobra_Gen', 'Apex_Serpent',
  'TitanBoa', 'Hydra_Node', 'Basilisk', 'Mamba_Core', 'NeuroCoil', 'AnacondAI',
  'Synapse_Worm', 'Gluon_Snake', 'Vector_Fang', 'Zenith_AI', 'Krait_99', 'Rattler',
  'Quetzal', 'Dendro_AI', 'CyberSerpent', 'Helix_Bot', 'Spectre_AI', 'Leviathan'
];

export class SlitherEngine {
  public snakes: Snake[] = [];
  public foodOrbs: FoodOrb[] = [];
  public arenaRadius: number = ARENA_RADIUS;
  public evolution: EvolutionManager;
  public mode: GameMode = 'TRAINING';
  public isRunning: boolean = true;
  public simSpeed: number = 1; // 1x, 2x, 5x, 10x, 20x
  public isGpuOverdrive: boolean = true; // Automated continuous maximum GPU & CPU throughput
  public adaptiveSubsteps: number = 32; // Uncapped high-throughput parallel sub-steps for training saturation
  public populationSize: number = 36; // Maximum competitive population size for rich multi-agent training
  public ticksPerSec: number = 0;
  public turboMode: boolean = false;
  public selectedSnakeId: string | null = null;
  public playerSnakeId: string | null = null;
  public generationTimer: number = 0;
  public maxGenerationTicks: number = 60 * 35; // 35 seconds per gen to accelerate evolution
  public onGenerationEvolve?: () => void;
  public onPlayerDeath?: (stats: { mass: number; kills: number; timeAlive: number }) => void;
  public isCudaConnected: boolean = false;
  public cudaTelemetry: any = null;
  public activeInstanceId: number = 0;
  private cudaSnakeMap: Map<string, Snake> = new Map();

  private nextFoodId: number = 1;
  private deadPerformances: any[] = [];
  private tickCounter: number = 0;
  private lastSecTimestamp: number = Date.now();

  constructor() {
    this.evolution = new EvolutionManager();
    this.initFood();
    this.initPopulation(this.populationSize);
  }

  /**
   * Initializes ambient food orbs distributed across the circle
   */
  public initFood(): void {
    this.foodOrbs = [];
    for (let i = 0; i < AMBIENT_FOOD_TARGET; i++) {
      this.spawnRandomFoodOrb();
    }
  }

  private spawnRandomFoodOrb(isRemnant: boolean = false): FoodOrb {
    // Uniform random distribution in circle
    const r = Math.sqrt(Math.random()) * (this.arenaRadius - 40);
    const theta = Math.random() * Math.PI * 2;
    const x = Math.cos(theta) * r;
    const y = Math.sin(theta) * r;

    const mass = isRemnant ? 2 + Math.random() * 3 : 1 + Math.random() * 2;
    const radius = Math.max(3, Math.min(8, 2.5 + Math.sqrt(mass) * 1.5));
    const colorTheme = SNAKE_COLORS[Math.floor(Math.random() * SNAKE_COLORS.length)];

    const orb: FoodOrb = {
      id: this.nextFoodId++,
      x,
      y,
      mass,
      radius,
      color: colorTheme.main,
      glowColor: colorTheme.secondary,
      isRemnant,
    };
    this.foodOrbs.push(orb);
    return orb;
  }

  /**
   * Spawns food particles when a snake drops mass while boosting or dies
   */
  public spawnOrbAt(x: number, y: number, mass: number, color: string): void {
    const orb: FoodOrb = {
      id: this.nextFoodId++,
      x: x + (Math.random() * 8 - 4),
      y: y + (Math.random() * 8 - 4),
      mass,
      radius: Math.max(3.5, Math.min(9, 2.8 + Math.sqrt(mass) * 1.6)),
      color,
      glowColor: color,
      isRemnant: true,
    };
    this.foodOrbs.push(orb);
  }

  /**
   * Initializes training population
   */
  public initPopulation(
    size: number = 24,
    useSeed: boolean = true,
    preserveHistory: boolean = true
  ): void {
    this.populationSize = size;
    this.snakes = [];
    this.deadPerformances = [];
    this.generationTimer = 0;

    const brains = this.evolution.reset(useSeed, size, preserveHistory);

    for (let i = 0; i < size; i++) {
      const isChamp = i === 0;
      const snake = this.createSnake(
        `bot_${i}`,
        isChamp ? '🏆 Campeão Genética' : (BOT_NAMES[i % BOT_NAMES.length] + `_${i}`),
        false,
        isChamp,
        brains[i],
        i
      );
      this.snakes.push(snake);
    }

    this.selectedSnakeId = this.snakes[0].id;
  }

  /**
   * Adjusts population size without resetting current generation progress or history
   */
  public setPopulationSize(newSize: number): void {
    this.populationSize = newSize;
    if (this.mode !== 'TRAINING') return;

    if (this.snakes.length < newSize) {
      // Add more snakes cloned/mutated from current champion
      const champ = this.evolution.bestChampionBrain;
      const toAdd = newSize - this.snakes.length;
      for (let i = 0; i < toAdd; i++) {
        const brain = champ.clone();
        brain.mutate(this.evolution.mutationRate, this.evolution.mutationMagnitude);
        const snake = this.createSnake(
          `bot_add_${Date.now()}_${i}`,
          BOT_NAMES[Math.floor(Math.random() * BOT_NAMES.length)],
          false,
          false,
          brain,
          (this.snakes.length + i) % 10
        );
        this.snakes.push(snake);
      }
    } else if (this.snakes.length > newSize) {
      // Keep champion and top snakes, trim excess
      const champ = this.snakes.find((s) => s.isChampion) || this.snakes[0];
      const others = this.snakes.filter((s) => s !== champ).slice(0, newSize - 1);
      this.snakes = [champ, ...others];
    }
  }

  /**
   * Starts Player vs AI mode
   */
  public startPlayerVsAIMode(): void {
    this.mode = 'PLAYER_VS_AI';
    this.snakes = [];
    this.deadPerformances = [];

    // Spawn player snake
    const playerSnake = this.createSnake('player_1', 'Você (Jogador)', true, false, undefined, 0);
    playerSnake.color = '#38BDF8';
    playerSnake.secondaryColor = '#0284C7';
    this.snakes.push(playerSnake);
    this.playerSnakeId = playerSnake.id;
    this.selectedSnakeId = playerSnake.id;

    // Spawn AI bots using champion brain variants
    const champBrain = this.evolution.bestChampionBrain;
    const botCount = 18;

    for (let i = 1; i <= botCount; i++) {
      const isLeadChamp = i === 1;
      const botBrain = champBrain.clone();
      if (!isLeadChamp) {
        botBrain.mutate(0.15, 0.3); // slight individual diversity
      }
      const bot = this.createSnake(
        `ai_bot_${i}`,
        isLeadChamp ? '⭐ Campeão da IA' : BOT_NAMES[(i - 1) % BOT_NAMES.length],
        false,
        isLeadChamp,
        botBrain,
        i
      );
      this.snakes.push(bot);
    }
  }

  /**
   * Creates a single snake instance
   */
  public createSnake(
    id: string,
    name: string,
    isPlayer: boolean,
    isChampion: boolean,
    brain?: NeuralNetwork,
    colorIndex: number = 0
  ): Snake {
    // Spawn in ring at radius 300 to (arenaRadius - 300)
    const spawnAngle = Math.random() * Math.PI * 2;
    const spawnDist = 200 + Math.random() * (this.arenaRadius * 0.7);
    const x = Math.cos(spawnAngle) * spawnDist;
    const y = Math.sin(spawnAngle) * spawnDist;

    // Head pointing toward center with slight variance
    const angleToCenter = Math.atan2(-y, -x) + (Math.random() * 0.8 - 0.4);

    const theme = isChampion
      ? { main: '#F59E0B', secondary: '#D97706', name: 'Champion Gold' }
      : SNAKE_COLORS[colorIndex % SNAKE_COLORS.length];

    const initialSegments: SnakeSegment[] = [];
    const segmentCount = 14;
    const segmentSpacing = 9;

    for (let s = 0; s < segmentCount; s++) {
      initialSegments.push({
        x: x - Math.cos(angleToCenter) * s * segmentSpacing,
        y: y - Math.sin(angleToCenter) * s * segmentSpacing,
      });
    }

    return {
      id,
      name,
      isPlayer,
      isChampion,
      color: theme.main,
      secondaryColor: theme.secondary,
      x,
      y,
      angle: angleToCenter,
      targetAngle: angleToCenter,
      speed: 4.0,
      baseSpeed: 4.0,
      boostSpeed: 7.8,
      isBoosting: false,
      mass: INITIAL_SNAKE_MASS,
      score: INITIAL_SNAKE_MASS,
      kills: 0,
      alive: true,
      segments: initialSegments,
      segmentSpacing,
      headRadius: 10,
      bodyRadius: 8.5,
      age: 0,
      foodEaten: 0,
      fitness: 0,
      brain: brain || (isPlayer ? undefined : new NeuralNetwork()),
    };
  }

  /**
   * Respawn single player snake after death
   */
  public respawnPlayer(): void {
    if (this.mode !== 'PLAYER_VS_AI') return;
    const newPlayer = this.createSnake('player_1', 'Você (Jogador)', true, false, undefined, 0);
    newPlayer.color = '#38BDF8';
    newPlayer.secondaryColor = '#0284C7';
    // Replace old player
    this.snakes = this.snakes.filter((s) => s.id !== 'player_1');
    this.snakes.push(newPlayer);
    this.playerSnakeId = newPlayer.id;
    this.selectedSnakeId = newPlayer.id;
  }

  /**
   * Synchronizes simulation state from the PyTorch CUDA Tensor Engine (NVIDIA RTX 3060)
   */
  public updateFromCuda(data: any): void {
    if (!data) return;
    this.isCudaConnected = true;
    this.cudaTelemetry = data;

    if (data.generation) {
      this.evolution.generation = data.generation;
      this.evolution.stats.generation = data.generation;
    }
    if (data.best_fitness !== undefined) {
      this.evolution.stats.bestFitness = data.best_fitness;
      if (data.best_fitness > this.evolution.bestAllTimeFitness) {
        this.evolution.bestAllTimeFitness = data.best_fitness;
      }
    }
    if (data.avg_fitness !== undefined) {
      this.evolution.stats.avgFitness = data.avg_fitness;
    }
    if (data.history && data.history.length > 0) {
      this.evolution.stats.fitnessHistory = data.history;
    }

    // In CUDA_GPU mode, render the actual 500-population actors from the GPU
    if (this.mode === 'CUDA_GPU') {
      this.arenaRadius = 2800;
      if (data.active_instance !== undefined && this.activeInstanceId !== data.active_instance) {
        this.activeInstanceId = data.active_instance;
        this.cudaSnakeMap.clear();
        this.snakes = [];
      }

      if (data.live_snakes && data.live_snakes.length > 0) {
        const liveList: any[] = data.live_snakes;
        const updatedSnakes: Snake[] = [];

        for (let i = 0; i < liveList.length; i++) {
          const item = liveList[i];
          let existing = this.cudaSnakeMap.get(item.id);

          if (!existing) {
            existing = this.createSnake(
              item.id,
              item.name,
              false,
              item.isChampion,
              undefined,
              i
            );
            this.cudaSnakeMap.set(item.id, existing);
          }

          existing.x = item.x;
          existing.y = item.y;
          existing.angle = item.angle;
          existing.targetAngle = item.angle;
          existing.mass = item.mass;
          existing.isBoosting = item.isBoosting;
          existing.alive = item.alive;
          existing.isChampion = item.isChampion;

          if (item.isChampion && data.champion_activations) {
            const act = data.champion_activations;
            existing.lastActivations = {
              inputs: act.inputs || [],
              hidden1: act.hidden1 || [],
              hidden2: act.hidden2 || [],
              outputs: act.outputs || [0, 0],
            };
            if (!this.selectedSnakeId || this.selectedSnakeId !== existing.id) {
              this.selectedSnakeId = existing.id;
            }
          }

          const segCount = existing.isChampion ? 14 : 9;
          if (existing.segments.length === 0) {
            for (let s = 0; s < segCount; s++) {
              existing.segments.push({ x: existing.x, y: existing.y });
            }
          } else {
            existing.segments[0] = { x: existing.x, y: existing.y };
            const segDist = existing.isChampion ? 7.5 : 6.0;
            for (let s = 1; s < existing.segments.length; s++) {
              const prev = existing.segments[s - 1];
              const curr = existing.segments[s];
              const dx = curr.x - prev.x;
              const dy = curr.y - prev.y;
              const d = Math.hypot(dx, dy) || 1;
              curr.x = prev.x + (dx / d) * segDist;
              curr.y = prev.y + (dy / d) * segDist;
            }
          }

          updatedSnakes.push(existing);
        }

        this.snakes = updatedSnakes;
      }

      if (data.live_foods && data.live_foods.length > 0) {
        this.foodOrbs = data.live_foods.map((coord: number[], idx: number) => ({
          id: idx + 1,
          x: coord[0],
          y: coord[1],
          mass: 2.0,
          radius: 4.5,
          color: idx % 3 === 0 ? '#10B981' : idx % 3 === 1 ? '#06B6D4' : '#F59E0B',
          glowColor: idx % 3 === 0 ? '#059669' : idx % 3 === 1 ? '#0891B2' : '#D97706',
        }));
      }
    }
  }

  /**
   * Main game step tick
   */
  public update(playerInputAngle?: number, playerBoost?: boolean): void {
    if (!this.isRunning) return;

    // In CUDA_GPU mode, dynamics and neural feedforward are powered by the RTX 3060 Tensor Engine
    if (this.mode === 'CUDA_GPU') {
      this.tickCounter++;
      const now = Date.now();
      if (now - this.lastSecTimestamp >= 1000) {
        this.ticksPerSec = Math.round((this.tickCounter * 1000) / (now - this.lastSecTimestamp));
        this.tickCounter = 0;
        this.lastSecTimestamp = now;
      }
      return;
    }

    // Track throughput (ticks per second)
    this.tickCounter++;
    const now = Date.now();
    if (now - this.lastSecTimestamp >= 1000) {
      this.ticksPerSec = Math.round((this.tickCounter * 1000) / (now - this.lastSecTimestamp));
      this.tickCounter = 0;
      this.lastSecTimestamp = now;
    }

    // Handle bot decision making
    for (let i = 0; i < this.snakes.length; i++) {
      const snake = this.snakes[i];
      if (!snake.alive) continue;

      if (snake.isPlayer) {
        // Player inputs from mouse/touch
        if (playerInputAngle !== undefined) {
          snake.targetAngle = playerInputAngle;
        }
        snake.isBoosting = !!playerBoost && snake.mass > 12;
      } else if (snake.brain) {
        // Bot: Run sensory raycaster and feed-forward through neural network
        const sensorResult = computeSnakeSensors(
          snake,
          this.snakes,
          this.foodOrbs,
          this.arenaRadius
        );
        snake.sensors = sensorResult.rays;

        const { outputs, activations } = snake.brain.feedForward(sensorResult.inputs);

        // Store activations for live visualizer
        snake.lastActivations = {
          inputs: sensorResult.inputs,
          hidden1: activations[1] || [],
          hidden2: activations[2] || [],
          outputs,
        };

        // Output 0: Steer (-1 to 1) -> relative turning angle
        const steerOutput = outputs[0]; // -1 (sharp left) to +1 (sharp right)
        const turnRate = 0.085;
        snake.targetAngle = snake.angle + steerOutput * turnRate * 3.5;

        // Output 1: Boost (0 to 1) -> threshold > 0.52
        const boostOutput = outputs[1];
        snake.isBoosting = boostOutput > 0.52 && snake.mass > 14;
      }
    }

    // Update kinematics, food consumption, and boost physics
    for (let i = 0; i < this.snakes.length; i++) {
      const snake = this.snakes[i];
      if (!snake.alive) continue;

      snake.age++;

      // Radii scale dynamically with mass
      snake.headRadius = Math.max(9, Math.min(22, 8 + Math.sqrt(snake.mass) * 0.7));
      snake.bodyRadius = Math.max(7.5, Math.min(19, 6.8 + Math.sqrt(snake.mass) * 0.6));

      // Turning physics (lerp towards targetAngle)
      let angleDiff = snake.targetAngle - snake.angle;
      while (angleDiff > Math.PI) angleDiff -= Math.PI * 2;
      while (angleDiff < -Math.PI) angleDiff += Math.PI * 2;

      // Larger snakes turn slightly slower (tactical inertia)
      const maxTurn = Math.max(0.045, 0.12 - (snake.mass / 2000) * 0.04);
      const turnStep = Math.max(-maxTurn, Math.min(maxTurn, angleDiff));
      snake.angle += turnStep;

      // Speed physics
      if (snake.isBoosting && snake.mass > 12) {
        snake.speed = snake.boostSpeed;
        // Shed mass when boosting
        snake.mass -= 0.035;
        // Drop food remnant occasionally
        if (snake.age % 6 === 0) {
          const tail = snake.segments[snake.segments.length - 1] || { x: snake.x, y: snake.y };
          this.spawnOrbAt(tail.x, tail.y, 1.2, snake.color);
        }
      } else {
        snake.speed = snake.baseSpeed;
      }

      // Move head
      snake.x += Math.cos(snake.angle) * snake.speed;
      snake.y += Math.sin(snake.angle) * snake.speed;

      // Multi-joint segment constraint (smooth snake kinematics)
      const desiredSegments = Math.floor(12 + Math.sqrt(snake.mass) * 4);
      const spacing = snake.segmentSpacing;

      let prevX = snake.x;
      let prevY = snake.y;

      for (let s = 0; s < snake.segments.length; s++) {
        const seg = snake.segments[s];
        const dx = seg.x - prevX;
        const dy = seg.y - prevY;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist > spacing) {
          const ratio = spacing / dist;
          seg.x = prevX + dx * ratio;
          seg.y = prevY + dy * ratio;
        }

        prevX = seg.x;
        prevY = seg.y;
      }

      // Add or trim segments to match desired length
      while (snake.segments.length < desiredSegments) {
        const last = snake.segments[snake.segments.length - 1] || { x: snake.x, y: snake.y };
        snake.segments.push({ x: last.x, y: last.y });
      }
      while (snake.segments.length > desiredSegments && snake.segments.length > 5) {
        snake.segments.pop();
      }

      // Food eating collision (Optimized with fast AABB filter)
      const headRange = snake.headRadius + 8;
      const headSq = headRange * headRange;
      for (let f = this.foodOrbs.length - 1; f >= 0; f--) {
        const food = this.foodOrbs[f];
        const fDx = food.x - snake.x;
        if (fDx > headRange || fDx < -headRange) continue;
        const fDy = food.y - snake.y;
        if (fDy > headRange || fDy < -headRange) continue;
        if (fDx * fDx + fDy * fDy < headSq) {
          // Eat food
          snake.mass += food.mass;
          snake.foodEaten++;
          snake.score = Math.floor(snake.mass);
          this.foodOrbs.splice(f, 1);
        }
      }
    }

    // Check snake-on-snake & arena border fatal collisions
    for (let i = 0; i < this.snakes.length; i++) {
      const snake = this.snakes[i];
      if (!snake.alive) continue;

      // 1. Arena boundary collision
      const distFromCenterSq = snake.x * snake.x + snake.y * snake.y;
      if (distFromCenterSq > this.arenaRadius * this.arenaRadius) {
        this.killSnake(snake, null);
        continue;
      }

      // 2. Snake head colliding with other snake's body
      for (let j = 0; j < this.snakes.length; j++) {
        const other = this.snakes[j];
        if (!other.alive || other.id === snake.id) continue;

        // Fast bounding circle check
        const sDx = other.x - snake.x;
        const sDy = other.y - snake.y;
        if (sDx * sDx + sDy * sDy > 600 * 600) continue;

        // Head vs Head collision: the smaller snake dies, or both if equal
        const headDistSq = sDx * sDx + sDy * sDy;
        const minHeadDist = snake.headRadius + other.headRadius;
        if (headDistSq < minHeadDist * minHeadDist) {
          if (snake.mass <= other.mass) {
            this.killSnake(snake, other);
            break;
          }
        }

        // Head vs Other segments collision (excluding very first neck segment)
        let died = false;
        const hitRadius = snake.headRadius + other.bodyRadius * 0.85;
        const hitRadiusSq = hitRadius * hitRadius;

        for (let segIdx = 2; segIdx < other.segments.length; segIdx++) {
          const seg = other.segments[segIdx];
          const dx = seg.x - snake.x;
          const dy = seg.y - snake.y;
          if (dx * dx + dy * dy < hitRadiusSq) {
            // Snake crashed into other's body!
            this.killSnake(snake, other);
            died = true;
            break;
          }
        }

        if (died) break;
      }
    }

    // Replenish ambient food orbs
    while (this.foodOrbs.length < AMBIENT_FOOD_TARGET) {
      this.spawnRandomFoodOrb();
    }

    // Generation / Lifecycle checking in Training mode
    if (this.mode === 'TRAINING') {
      this.generationTimer++;
      const aliveCount = this.snakes.filter((s) => s.alive).length;

      // Advance generation if timer expired OR only <= 2 snakes survive
      if (this.generationTimer >= this.maxGenerationTicks || aliveCount <= 2) {
        this.evolveGeneration();
      }
    } else if (this.mode === 'PLAYER_VS_AI') {
      // In Player vs AI mode, continuously respawn dead AI bots so arena stays populated
      const activeBots = this.snakes.filter((s) => !s.isPlayer && s.alive).length;
      if (activeBots < 15) {
        const champBrain = this.evolution.bestChampionBrain.clone();
        champBrain.mutate(0.15, 0.3);
        const newBot = this.createSnake(
          `ai_bot_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
          BOT_NAMES[Math.floor(Math.random() * BOT_NAMES.length)],
          false,
          false,
          champBrain,
          Math.floor(Math.random() * 10)
        );
        this.snakes.push(newBot);
      }
    }
  }

  /**
   * Kills a snake, drops its remains as massive glowing orbs, and credits the killer
   */
  private killSnake(victim: Snake, killer: Snake | null): void {
    victim.alive = false;

    // Record performance for genetic fitness
    const fitness = this.evolution.calculateFitness({
      mass: victim.mass,
      initialMass: INITIAL_SNAKE_MASS,
      foodEaten: victim.foodEaten,
      kills: victim.kills,
      age: victim.age,
    });
    victim.fitness = fitness;

    if (victim.brain) {
      this.deadPerformances.push({
        id: victim.id,
        name: victim.name,
        brain: victim.brain,
        fitness,
        mass: victim.mass,
        kills: victim.kills,
        age: victim.age,
        foodEaten: victim.foodEaten,
      });
    }

    if (killer) {
      killer.kills++;
      killer.mass += Math.min(25, victim.mass * 0.15); // Instant reward for kill
    }

    // Drop delicious glowing food orbs along entire body!
    const orbsToDrop = Math.min(40, victim.segments.length);
    const stride = Math.max(1, Math.floor(victim.segments.length / orbsToDrop));
    for (let s = 0; s < victim.segments.length; s += stride) {
      const seg = victim.segments[s];
      this.spawnOrbAt(seg.x, seg.y, 3.5, victim.color);
    }
    // Also drop extra cluster at head
    for (let k = 0; k < 4; k++) {
      this.spawnOrbAt(victim.x, victim.y, 4.0, victim.color);
    }

    if (victim.isPlayer && this.onPlayerDeath) {
      this.onPlayerDeath({
        mass: victim.mass,
        kills: victim.kills,
        timeAlive: victim.age,
      });
    }
  }

  /**
   * Evolve current generation in Training Mode
   */
  public evolveGeneration(): void {
    // Add any remaining alive snakes into performances
    for (let i = 0; i < this.snakes.length; i++) {
      const s = this.snakes[i];
      if (s.alive && s.brain) {
        const fitness = this.evolution.calculateFitness({
          mass: s.mass,
          initialMass: INITIAL_SNAKE_MASS,
          foodEaten: s.foodEaten,
          kills: s.kills,
          age: s.age,
        });
        s.fitness = fitness;
        this.deadPerformances.push({
          id: s.id,
          name: s.name,
          brain: s.brain,
          fitness,
          mass: s.mass,
          kills: s.kills,
          age: s.age,
          foodEaten: s.foodEaten,
        });
      }
    }

    const popSize = this.populationSize;
    const { nextBrains, champion } = this.evolution.evolve(this.deadPerformances, popSize);

    // Spawn new generation
    this.snakes = [];
    this.deadPerformances = [];
    this.generationTimer = 0;

    for (let i = 0; i < popSize; i++) {
      const isChamp = i === 0;
      const snake = this.createSnake(
        `bot_gen${this.evolution.generation}_${i}`,
        isChamp ? `🏆 Campeão Gen ${this.evolution.generation}` : BOT_NAMES[i % BOT_NAMES.length],
        false,
        isChamp,
        isChamp ? champion : nextBrains[i],
        i
      );
      this.snakes.push(snake);
    }

    this.selectedSnakeId = this.snakes[0].id;

    if (this.onGenerationEvolve) {
      this.onGenerationEvolve();
    }
  }

  /**
   * Run turbo evolution cycles without rendering
   */
  public runTurboGenerations(generationsToRun: number = 3): void {
    for (let g = 0; g < generationsToRun; g++) {
      let ticks = 0;
      while (ticks < this.maxGenerationTicks) {
        this.update();
        ticks++;
        const aliveCount = this.snakes.filter((s) => s.alive).length;
        if (aliveCount <= 2) break;
      }
      this.evolveGeneration();
    }
  }

  /**
   * Run asynchronous headless generation batch yielding to event loop
   */
  public async runHeadlessBatchAsync(
    generationsToRun: number,
    onProgress?: (current: number, total: number) => void
  ): Promise<void> {
    for (let g = 1; g <= generationsToRun; g++) {
      let ticks = 0;
      while (ticks < this.maxGenerationTicks) {
        this.update();
        ticks++;
        const aliveCount = this.snakes.filter((s) => s.alive).length;
        if (aliveCount <= 2) break;
      }
      this.evolveGeneration();
      if (onProgress) {
        onProgress(g, generationsToRun);
      }
      // Yield to browser event loop
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
  }

  /**
   * Returns current active camera target snake
   */
  public getTrackedSnake(): Snake | null {
    if (this.mode === 'PLAYER_VS_AI') {
      const player = this.snakes.find((s) => s.id === this.playerSnakeId && s.alive);
      if (player) return player;
    }

    if (this.selectedSnakeId) {
      const selected = this.snakes.find((s) => s.id === this.selectedSnakeId && s.alive);
      if (selected) return selected;
    }

    // Default to highest mass alive snake
    const alive = this.snakes.filter((s) => s.alive).sort((a, b) => b.mass - a.mass);
    return alive[0] || null;
  }
}
