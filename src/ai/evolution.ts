/**
 * Neuroevolution Engine: Genetic Algorithm for Slither Bots
 */

import { NeuralNetwork, SerializedNetwork } from './neuralNetwork';
import { EvolutionStats } from '../game/types';

export interface AgentPerformance {
  id: string;
  name: string;
  brain: NeuralNetwork;
  fitness: number;
  mass: number;
  kills: number;
  age: number;
  foodEaten: number;
}

const STORAGE_KEY = 'slitherai_best_champion_weights';
const STATS_STORAGE_KEY = 'slitherai_training_history_stats';

export class EvolutionManager {
  public generation: number = 1;
  public bestChampionBrain: NeuralNetwork;
  public bestAllTimeFitness: number = 185;
  public stats: EvolutionStats;
  public mutationRate: number = 0.12;
  public mutationMagnitude: number = 0.35;
  public elitismCount: number = 4;
  public autoSavedAt?: string;

  constructor() {
    this.bestChampionBrain = NeuralNetwork.createTrainedChampion();
    
    // Baseline seed history so learning curve is never blank or failing to load
    const defaultHistory = [
      { generation: 0, best: 80, avg: 45 },
      { generation: 1, best: 185, avg: 95 },
    ];

    this.stats = {
      generation: 1,
      bestFitness: 185,
      avgFitness: 95,
      bestMass: 42,
      bestKills: 1,
      bestAliveTime: 220,
      fitnessHistory: defaultHistory,
    };

    // Auto-restore previous champion and history if stored in browser
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && parsed.layers && parsed.weights) {
          this.bestChampionBrain = NeuralNetwork.fromJSON(parsed);
          this.autoSavedAt = 'Restaurado do Navegador';
        }
      }

      const savedStats = localStorage.getItem(STATS_STORAGE_KEY);
      if (savedStats) {
        const parsedStats = JSON.parse(savedStats);
        if (parsedStats && Array.isArray(parsedStats.fitnessHistory) && parsedStats.fitnessHistory.length > 0) {
          this.stats = { ...this.stats, ...parsedStats };
          this.generation = parsedStats.generation || 1;
          this.bestAllTimeFitness = Math.max(this.bestAllTimeFitness, parsedStats.bestFitness || 0);
        }
      }
    } catch {
      // ignore
    }
  }

  /**
   * Calculates fitness score for a snake agent
   */
  public calculateFitness(perf: {
    mass: number;
    initialMass: number;
    foodEaten: number;
    kills: number;
    age: number;
  }): number {
    const massGain = Math.max(0, perf.mass - perf.initialMass);
    // Rewarding mass gain, aggressive kills, food collection, and tactical survival
    const score =
      massGain * 3.0 +
      perf.foodEaten * 1.5 +
      perf.kills * 400 +
      Math.min(perf.age * 0.15, 200);

    return Math.max(1, Math.round(score));
  }

  /**
   * Evolves current generation into next generation
   */
  public evolve(
    performances: AgentPerformance[],
    targetPopulationSize: number
  ): { nextBrains: NeuralNetwork[]; champion: NeuralNetwork } {
    if (performances.length === 0) {
      const fallback = Array.from({ length: targetPopulationSize }, () =>
        this.bestChampionBrain.clone()
      );
      return { nextBrains: fallback, champion: this.bestChampionBrain };
    }

    // Sort descending by fitness
    performances.sort((a, b) => b.fitness - a.fitness);

    const best = performances[0];
    const totalFitness = performances.reduce((sum, p) => sum + p.fitness, 0);
    const avgFitness = Math.round(totalFitness / performances.length);

    if (best.fitness > this.bestAllTimeFitness) {
      this.bestAllTimeFitness = best.fitness;
      this.bestChampionBrain = best.brain.clone();
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.bestChampionBrain.toJSON()));
        this.autoSavedAt = new Date().toLocaleTimeString();
      } catch {
        // ignore
      }
    }

    // Record stats
    this.stats.generation = this.generation;
    this.stats.bestFitness = best.fitness;
    this.stats.avgFitness = avgFitness;
    this.stats.bestMass = Math.max(...performances.map((p) => p.mass));
    this.stats.bestKills = Math.max(...performances.map((p) => p.kills));
    this.stats.bestAliveTime = Math.max(...performances.map((p) => p.age));

    this.stats.fitnessHistory.push({
      generation: this.generation,
      best: best.fitness,
      avg: avgFitness,
    });
    // Keep last 40 data points for UI chart clarity
    if (this.stats.fitnessHistory.length > 40) {
      this.stats.fitnessHistory.shift();
    }

    try {
      localStorage.setItem(STATS_STORAGE_KEY, JSON.stringify(this.stats));
    } catch {
      // ignore
    }

    const nextBrains: NeuralNetwork[] = [];

    // 1. Elitism: Keep top performers unaltered
    const eliteCount = Math.max(2, Math.min(this.elitismCount, Math.floor(performances.length * 0.2)));
    for (let i = 0; i < eliteCount; i++) {
      nextBrains.push(performances[i].brain.clone());
    }

    // Always include our best all-time champion
    nextBrains.push(this.bestChampionBrain.clone());

    // 2. Tournament selection helper
    const selectParent = (): NeuralNetwork => {
      const tournamentSize = 3;
      let selectedBest = performances[Math.floor(Math.random() * performances.length)];
      for (let t = 1; t < tournamentSize; t++) {
        const contestant = performances[Math.floor(Math.random() * performances.length)];
        if (contestant.fitness > selectedBest.fitness) {
          selectedBest = contestant;
        }
      }
      return selectedBest.brain;
    };

    // 3. Fill the rest through Crossover and Mutation
    while (nextBrains.length < targetPopulationSize) {
      const parentA = selectParent();
      const parentB = selectParent();
      const child = parentA.crossover(parentB);
      child.mutate(this.mutationRate, this.mutationMagnitude);
      nextBrains.push(child);
    }

    this.generation++;
    return {
      nextBrains,
      champion: best.brain.clone(),
    };
  }

  /**
   * Reset evolution with fresh random networks or seeded champion
   */
  public reset(
    useSeedChampion: boolean = true,
    popSize: number = 24,
    preserveHistory: boolean = false
  ): NeuralNetwork[] {
    if (!preserveHistory) {
      this.generation = 1;
      this.bestAllTimeFitness = 185;
      this.stats.generation = 1;
      this.stats.bestFitness = 185;
      this.stats.avgFitness = 95;
      this.stats.fitnessHistory = [
        { generation: 0, best: 80, avg: 45 },
        { generation: 1, best: 185, avg: 95 },
      ];
      try {
        localStorage.removeItem(STATS_STORAGE_KEY);
      } catch {
        // ignore
      }
    }

    if (useSeedChampion) {
      if (!preserveHistory) {
        this.bestChampionBrain = NeuralNetwork.createTrainedChampion();
      }
      return Array.from({ length: popSize }, (_, i) => {
        if (i === 0) return this.bestChampionBrain.clone();
        const clone = this.bestChampionBrain.clone();
        clone.mutate(0.2, 0.4);
        return clone;
      });
    } else {
      this.bestChampionBrain = new NeuralNetwork();
      return Array.from({ length: popSize }, () => new NeuralNetwork());
    }
  }

  /**
   * Export champion brain as JSON string
   */
  public exportChampionJSON(): string {
    return JSON.stringify(this.bestChampionBrain.toJSON(), null, 2);
  }

  /**
   * Import brain from JSON string
   */
  public importBrainJSON(jsonStr: string): boolean {
    try {
      const data = JSON.parse(jsonStr) as SerializedNetwork;
      if (Array.isArray(data.layers) && Array.isArray(data.weights)) {
        this.bestChampionBrain = NeuralNetwork.fromJSON(data);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }
}
