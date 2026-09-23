/**
 * SlitherAI Types and Interfaces
 */

export interface Point {
  x: number;
  y: number;
}

export interface FoodOrb {
  id: number;
  x: number;
  y: number;
  mass: number;
  radius: number;
  color: string;
  glowColor: string;
  isRemnant?: boolean; // Dropped by speed boost or dead snake
}

export interface SnakeSegment {
  x: number;
  y: number;
}

export interface SensoryRay {
  angle: number;       // relative angle to head (radians)
  worldAngle: number;  // absolute angle in world space
  foodDist: number;    // 0 = touching head, 1 = far or nothing (inverted for NN: 1 = close, 0 = far)
  dangerDist: number;  // 0 = touching head, 1 = far or nothing (inverted for NN: 1 = immediate collision)
  foodHitPoint?: Point;
  dangerHitPoint?: Point;
}

export interface SnakeBrainActivations {
  inputs: number[];
  hidden1: number[];
  hidden2: number[];
  outputs: number[];
}

export interface Snake {
  id: string;
  name: string;
  isPlayer: boolean;
  isChampion: boolean;
  color: string;
  secondaryColor: string;
  x: number;
  y: number;
  angle: number;
  targetAngle: number;
  speed: number;
  baseSpeed: number;
  boostSpeed: number;
  isBoosting: boolean;
  mass: number;
  score: number;
  kills: number;
  alive: boolean;
  segments: SnakeSegment[];
  segmentSpacing: number;
  headRadius: number;
  bodyRadius: number;
  age: number; // ticks survived
  foodEaten: number;
  fitness: number;
  brain?: any; // NeuralNetwork instance
  lastActivations?: SnakeBrainActivations;
  sensors?: SensoryRay[];
}

export type GameMode = 'TRAINING' | 'PLAYER_VS_AI' | 'INSPECTOR' | 'CUDA_GPU';

export interface EvolutionStats {
  generation: number;
  bestFitness: number;
  avgFitness: number;
  bestMass: number;
  bestKills: number;
  bestAliveTime: number;
  fitnessHistory: { generation: number; best: number; avg: number }[];
}

export interface SimulationConfig {
  arenaRadius: number;
  populationSize: number;
  mutationRate: number;
  mutationMagnitude: number;
  ambientFoodCount: number;
  simSpeed: number; // 1, 2, 5, 10
  turboMode: boolean;
  rayCount: number;
  rayLength: number;
  generationDurationSeconds: number;
}

export interface CudaInstanceInfo {
  id: number;
  name: string;
  generation: number;
  best_fitness: number;
  avg_fitness: number;
}
