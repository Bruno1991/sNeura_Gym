import React, { useMemo } from 'react';
import { Snake } from '../game/types';
import { NeuralNetwork } from '../ai/neuralNetwork';
import { Compass, Gauge, Zap } from 'lucide-react';

interface NeuralVisualizerProps {
  snake: Snake | null;
  championBrain?: NeuralNetwork;
}

export const NeuralVisualizer: React.FC<NeuralVisualizerProps> = ({ snake, championBrain }) => {
  const brain: NeuralNetwork | undefined = snake?.brain || championBrain;
  const activations = snake?.lastActivations;

  // Layer layout geometry
  const layers = brain?.layers || [28, 24, 16, 2];

  // We sample representative nodes from large layers so the SVG stays ultra crisp and fast
  const sampledLayers = useMemo(() => {
    // Show top inputs: 4 key food rays, 4 danger rays, speed, mass, center, border (12 display nodes)
    return [
      { name: 'Entradas (Sensores)', size: Math.min(14, layers[0]), actualSize: layers[0] },
      { name: 'Oculta 1', size: Math.min(10, layers[1]), actualSize: layers[1] },
      { name: 'Oculta 2', size: Math.min(8, layers[2]), actualSize: layers[2] },
      { name: 'Saídas (Ação)', size: layers[3], actualSize: layers[3] },
    ];
  }, [layers]);

  // Read current output values
  const steerVal = activations?.outputs?.[0] ?? 0; // -1 to 1
  const boostVal = activations?.outputs?.[1] ?? 0; // 0 to 1
  const isBoosting = boostVal > 0.52;

  // Steering direction description
  const steerLabel =
    steerVal < -0.3
      ? 'Virando à Esquerda'
      : steerVal > 0.3
      ? 'Virando à Direita'
      : 'Seguindo Reto';

  const svgWidth = 440;
  const svgHeight = 240;
  const colSpacing = svgWidth / (sampledLayers.length + 0.3);

  // Compute node positions
  const nodePositions = useMemo(() => {
    return sampledLayers.map((layer, colIdx) => {
      const x = 35 + colIdx * colSpacing;
      const count = layer.size;
      const rowSpacing = (svgHeight - 40) / Math.max(1, count - 1);
      return Array.from({ length: count }, (_, rowIdx) => {
        const y = 20 + rowIdx * rowSpacing;
        return { x, y };
      });
    });
  }, [sampledLayers, colSpacing, svgHeight]);

  return (
    <div className="bg-slate-900/95 border border-slate-800 rounded-xl p-4 shadow-xl flex flex-col gap-3 text-slate-200">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs font-bold text-white uppercase tracking-wider font-mono">
            Rede Neural: {snake ? snake.name : 'Campeão'}
          </span>
        </div>
        <span className="text-[11px] font-mono text-slate-400">
          28 Sensores → 24 → 16 → 2 Ações
        </span>
      </div>

      {/* SVG Synapse and Node Diagram */}
      <div className="relative w-full h-[240px] bg-slate-950/70 rounded-lg border border-slate-800/80 overflow-hidden flex items-center justify-center">
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full h-full">
          {/* Synapses (Lines between layers) */}
          {nodePositions.map((layerNodes, lIdx) => {
            if (lIdx === nodePositions.length - 1) return null;
            const nextLayerNodes = nodePositions[lIdx + 1];

            return layerNodes.map((fromNode, fIdx) => {
              // Draw sample of connections to avoid visual mud
              return nextLayerNodes.map((toNode, tIdx) => {
                if ((fIdx + tIdx) % 2 !== 0 && lIdx < 2) return null; // sample thinning

                // Weight estimate
                const w = brain?.weights?.[lIdx]?.[fIdx]?.[tIdx] ?? 0;
                const isPositive = w >= 0;
                const strokeColor = isPositive
                  ? `rgba(6, 182, 212, ${Math.min(0.65, Math.abs(w) * 0.4)})`
                  : `rgba(239, 68, 68, ${Math.min(0.65, Math.abs(w) * 0.4)})`;

                return (
                  <line
                    key={`syn_${lIdx}_${fIdx}_${tIdx}`}
                    x1={fromNode.x}
                    y1={fromNode.y}
                    x2={toNode.x}
                    y2={toNode.y}
                    stroke={strokeColor}
                    strokeWidth={Math.min(2.5, Math.max(0.6, Math.abs(w) * 0.8))}
                  />
                );
              });
            });
          })}

          {/* Nodes */}
          {nodePositions.map((layerNodes, lIdx) => {
            const isInput = lIdx === 0;
            const isOutput = lIdx === nodePositions.length - 1;

            return layerNodes.map((node, nIdx) => {
              // Determine activation value if available
              let act = 0;
              if (activations) {
                if (isInput) act = activations.inputs[nIdx] || 0;
                else if (lIdx === 1) act = activations.hidden1[nIdx] || 0;
                else if (lIdx === 2) act = activations.hidden2[nIdx] || 0;
                else if (isOutput) act = activations.outputs[nIdx] || 0;
              }

              const absAct = Math.min(1, Math.abs(act));
              const fillColor = isOutput
                ? nIdx === 0
                  ? '#38BDF8' // Steer
                  : '#F59E0B' // Boost
                : isInput
                ? nIdx < 6
                  ? '#10B981' // Food rays
                  : '#EF4444' // Danger rays
                : `rgba(16, 185, 129, ${0.3 + absAct * 0.7})`;

              return (
                <g key={`node_${lIdx}_${nIdx}`}>
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={isOutput ? 6 : isInput ? 4.5 : 4}
                    fill={fillColor}
                    stroke="#0F172A"
                    strokeWidth={1.5}
                    className="transition-colors duration-100"
                  />
                  {absAct > 0.4 && (
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={isOutput ? 9 : 6.5}
                      fill="none"
                      stroke={fillColor}
                      strokeWidth={1}
                      opacity={absAct * 0.6}
                    />
                  )}
                </g>
              );
            });
          })}
        </svg>

        {/* Legend labels */}
        <div className="absolute bottom-1.5 left-2 flex items-center gap-3 text-[10px] text-slate-400 font-mono">
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span>Alimento</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-400" />
            <span>Perigo / Corpo</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span>Ação</span>
          </div>
        </div>
      </div>

      {/* Real-time Decisional Gauges */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        {/* Output 1: Steering */}
        <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-slate-400">
            <span className="flex items-center gap-1 font-medium">
              <Compass className="w-3.5 h-3.5 text-cyan-400" />
              Direção (Steering)
            </span>
            <span className="font-mono text-cyan-300 font-bold tabular-nums">
              {(steerVal * 100).toFixed(0)}%
            </span>
          </div>
          {/* Steer Bar */}
          <div className="relative h-2 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="absolute top-0 bottom-0 bg-cyan-400 rounded-full transition-all duration-75"
              style={{
                left: steerVal < 0 ? `${50 + steerVal * 50}%` : '50%',
                width: `${Math.abs(steerVal) * 50}%`,
              }}
            />
            {/* Center zero mark */}
            <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-slate-600" />
          </div>
          <div className="flex justify-between text-[10px] text-slate-500 font-medium">
            <span>← Esquerda</span>
            <span className="text-slate-300">{steerLabel}</span>
            <span>Direita →</span>
          </div>
        </div>

        {/* Output 2: Boost */}
        <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-slate-400">
            <span className="flex items-center gap-1 font-medium">
              <Zap className={`w-3.5 h-3.5 ${isBoosting ? 'text-amber-400 animate-bounce' : 'text-slate-500'}`} />
              Turbo (Boost)
            </span>
            <span
              className={`font-mono font-bold tabular-nums ${
                isBoosting ? 'text-amber-400' : 'text-slate-500'
              }`}
            >
              {(boostVal * 100).toFixed(0)}%
            </span>
          </div>
          {/* Boost Progress Bar */}
          <div className="relative h-2 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-75 ${
                isBoosting ? 'bg-amber-400 shadow-sm shadow-amber-400/50' : 'bg-slate-600'
              }`}
              style={{ width: `${Math.min(100, boostVal * 100)}%` }}
            />
            {/* Activation threshold marker at 52% */}
            <div className="absolute left-[52%] top-0 bottom-0 w-0.5 bg-amber-500/80" />
          </div>
          <div className="flex justify-between text-[10px] text-slate-500 font-medium">
            <span>Normal</span>
            <span className={isBoosting ? 'text-amber-300 font-semibold' : 'text-slate-400'}>
              {isBoosting ? 'TURBO ATIVADO' : 'Econômico'}
            </span>
            <span>Gasto de Massa</span>
          </div>
        </div>
      </div>
    </div>
  );
};
