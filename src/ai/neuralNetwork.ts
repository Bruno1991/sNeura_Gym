/**
 * Neural Network Engine for Autonomous Slither Bots
 * Multi-layer Perceptron (MLP) with Neuroevolution support
 */

export interface SerializedNetwork {
  layers: number[];
  weights: number[][][]; // weights[layerIndex][fromNeuron][toNeuron]
  biases: number[][];    // biases[layerIndex][toNeuron]
}

export class NeuralNetwork {
  public layers: number[];
  public weights: number[][][]; // [layer][from][to]
  public biases: number[][];    // [layer][to]

  constructor(layers: number[] = [28, 24, 16, 2]) {
    this.layers = [...layers];
    this.weights = [];
    this.biases = [];

    // Initialize layers
    for (let l = 0; l < this.layers.length - 1; l++) {
      const fromSize = this.layers[l];
      const toSize = this.layers[l + 1];

      // Xavier/He-like initialization
      const stdDev = Math.sqrt(2 / (fromSize + toSize));
      const layerWeights: number[][] = [];

      for (let i = 0; i < fromSize; i++) {
        const row: number[] = [];
        for (let j = 0; j < toSize; j++) {
          row.push((Math.random() * 2 - 1) * stdDev);
        }
        layerWeights.push(row);
      }
      this.weights.push(layerWeights);

      const layerBiases: number[] = [];
      for (let j = 0; j < toSize; j++) {
        layerBiases.push((Math.random() * 2 - 1) * 0.1);
      }
      this.biases.push(layerBiases);
    }
  }

  /**
   * Forward propagation
   * Returns final outputs and all intermediate activations for real-time visualization
   */
  public feedForward(inputs: number[]): { outputs: number[]; activations: number[][] } {
    const activations: number[][] = [];
    let current = [...inputs];
    activations.push(current);

    for (let l = 0; l < this.weights.length; l++) {
      const next: number[] = [];
      const toSize = this.layers[l + 1];
      const fromSize = this.layers[l];
      const isLastLayer = l === this.weights.length - 1;

      for (let j = 0; j < toSize; j++) {
        let sum = this.biases[l][j];
        for (let i = 0; i < fromSize; i++) {
          sum += current[i] * this.weights[l][i][j];
        }

        if (isLastLayer) {
          // Output 0: Steering (-1 to 1) -> Tanh
          // Output 1: Boost (0 to 1) -> Sigmoid
          if (j === 0) {
            next.push(Math.tanh(sum));
          } else {
            next.push(1 / (1 + Math.exp(-sum)));
          }
        } else {
          // Hidden layers: Leaky ReLU or Tanh
          next.push(Math.tanh(sum));
        }
      }

      current = next;
      activations.push(current);
    }

    return {
      outputs: current,
      activations,
    };
  }

  /**
   * Clone network architecture and weights
   */
  public clone(): NeuralNetwork {
    const copy = new NeuralNetwork(this.layers);
    for (let l = 0; l < this.weights.length; l++) {
      for (let i = 0; i < this.weights[l].length; i++) {
        for (let j = 0; j < this.weights[l][i].length; j++) {
          copy.weights[l][i][j] = this.weights[l][i][j];
        }
      }
      for (let j = 0; j < this.biases[l].length; j++) {
        copy.biases[l][j] = this.biases[l][j];
      }
    }
    return copy;
  }

  /**
   * Mutate weights and biases with Gaussian disturbance
   */
  public mutate(rate: number, magnitude: number): void {
    for (let l = 0; l < this.weights.length; l++) {
      for (let i = 0; i < this.weights[l].length; i++) {
        for (let j = 0; j < this.weights[l][i].length; j++) {
          if (Math.random() < rate) {
            // Gaussian perturbation
            const delta = (Math.random() * 2 - 1) * magnitude;
            this.weights[l][i][j] = Math.max(-4, Math.min(4, this.weights[l][i][j] + delta));
          }
        }
      }

      for (let j = 0; j < this.biases[l].length; j++) {
        if (Math.random() < rate) {
          const delta = (Math.random() * 2 - 1) * (magnitude * 0.5);
          this.biases[l][j] = Math.max(-2, Math.min(2, this.biases[l][j] + delta));
        }
      }
    }
  }

  /**
   * Crossover with another network
   */
  public crossover(other: NeuralNetwork): NeuralNetwork {
    const child = this.clone();
    for (let l = 0; l < child.weights.length; l++) {
      for (let i = 0; i < child.weights[l].length; i++) {
        for (let j = 0; j < child.weights[l][i].length; j++) {
          if (Math.random() < 0.5) {
            child.weights[l][i][j] = other.weights[l][i][j];
          }
        }
      }
      for (let j = 0; j < child.biases[l].length; j++) {
        if (Math.random() < 0.5) {
          child.biases[l][j] = other.biases[l][j];
        }
      }
    }
    return child;
  }

  /**
   * Serialize network to JSON
   */
  public toJSON(): SerializedNetwork {
    return {
      layers: [...this.layers],
      weights: JSON.parse(JSON.stringify(this.weights)),
      biases: JSON.parse(JSON.stringify(this.biases)),
    };
  }

  /**
   * Deserialize network from JSON
   */
  public static fromJSON(data: SerializedNetwork): NeuralNetwork {
    const net = new NeuralNetwork(data.layers);
    net.weights = JSON.parse(JSON.stringify(data.weights));
    net.biases = JSON.parse(JSON.stringify(data.biases));
    return net;
  }

  /**
   * Pre-trained / Heuristic seed weights for an effective Scavenger / Hunter bot
   * This gives users a high-fitness starting point if desired!
   */
  public static createTrainedChampion(layers: number[] = [28, 24, 16, 2]): NeuralNetwork {
    const net = new NeuralNetwork(layers);
    
    // Wire strong heuristic instincts into initial weights:
    // Left rays steer right, right rays steer left if danger;
    // Food rays pull toward food;
    // Boost fires when dense food is directly ahead or fleeing imminent danger
    const numRays = 12; // 12 directional rays: 0 is straight ahead, 1..5 right, 7..11 left, 6 behind
    
    for (let l = 0; l < net.weights.length; l++) {
      for (let i = 0; i < net.weights[l].length; i++) {
        for (let j = 0; j < net.weights[l][i].length; j++) {
          // Slight background noise
          net.weights[l][i][j] = (Math.random() * 2 - 1) * 0.15;
        }
      }
    }

    // Connect layer 0 (sensors) to layer 1
    // inputs: [0..11 food rays, 12..23 danger rays, 24 speed, 25 mass, 26 centerAngle, 27 borderDist]
    for (let r = 0; r < numRays; r++) {
      const rayAngle = (r / numRays) * Math.PI * 2;
      const lateralBias = Math.sin(rayAngle); // >0 if on right side, <0 if on left side

      // Food attraction:
      // If food on right, turn right (positive steer); if on left, turn left
      net.weights[0][r][0] = lateralBias * 1.8;
      // Danger repulsion:
      // If danger on right, turn LEFT (-lateralBias); if danger on left, turn RIGHT
      net.weights[0][numRays + r][0] = -lateralBias * 3.5;

      // Forward danger (rays 0, 1, 11): trigger boost escape or avoidance
      if (r === 0 || r === 1 || r === 11) {
        net.weights[0][numRays + r][1] = 2.5; // push boost signal
        net.weights[0][numRays + r][0] = (r === 1 ? -3.0 : r === 11 ? 3.0 : 2.5);
      }
    }

    // Border avoidance: input 27 is close to border
    net.weights[0][27][0] = 3.0; // avoid borders

    // Connect hidden layers to output layer
    // Hidden1 -> Hidden2 pass-through
    for (let i = 0; i < Math.min(net.layers[1], net.layers[2]); i++) {
      net.weights[1][i][i] = 1.4;
    }
    // Hidden2 -> Output
    net.weights[2][0][0] = 1.6; // steer channel
    net.weights[2][1][1] = 1.5; // boost channel

    return net;
  }
}
