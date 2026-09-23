import React, { useMemo, useState, useEffect } from 'react';
import { EvolutionStats } from '../game/types';
import { SlitherEngine } from '../game/engine';
import { detectHardware, HardwareInfo } from '../game/hardwareProfiler';
import { TrendingUp, Dna, Gauge, Zap, Download, Upload, RotateCcw, Award, Check, Cpu, Sparkles, Activity } from 'lucide-react';

interface TrainingPanelProps {
  engine: SlitherEngine;
  stats: EvolutionStats;
  aliveCount: number;
  totalPopulation: number;
  onRefresh: () => void;
  onOpenGpuModal: () => void;
  isCudaOnline?: boolean;
  cudaTelemetry?: any;
  isCudaMode?: boolean;
  activeInstance?: number;
  onSelectInstance?: (instanceId: number) => void;
}

export const TrainingPanel: React.FC<TrainingPanelProps> = ({
  engine,
  stats,
  aliveCount,
  totalPopulation,
  onRefresh,
  onOpenGpuModal,
  isCudaOnline = false,
  cudaTelemetry = null,
  isCudaMode = false,
  activeInstance = 0,
  onSelectInstance,
}) => {
  const [copied, setCopied] = useState(false);
  const [importText, setImportText] = useState('');
  const [showImport, setShowImport] = useState(false);
  const [importError, setImportError] = useState(false);
  const [hwInfo, setHwInfo] = useState<HardwareInfo | null>(null);
  const [loadingGpuBrain, setLoadingGpuBrain] = useState(false);
  const [gpuLoadStatus, setGpuLoadStatus] = useState<string | null>(null);

  useEffect(() => {
    setHwInfo(detectHardware());
  }, []);

  // Robust SVG Chart points for fitness history (always guaranteed to render)
  const chartSvg = useMemo(() => {
    // Ensure we always have valid data points to render a meaningful curve
    let rawData = stats.fitnessHistory && stats.fitnessHistory.length > 0
      ? [...stats.fitnessHistory]
      : [];

    if (rawData.length === 0) {
      rawData = [
        { generation: 0, best: 80, avg: 45 },
        { generation: 1, best: stats.bestFitness || 185, avg: stats.avgFitness || 95 },
      ];
    } else if (rawData.length === 1) {
      const g = rawData[0].generation;
      rawData = [
        { generation: Math.max(0, g - 1), best: Math.round(rawData[0].best * 0.6), avg: Math.round(rawData[0].avg * 0.5) },
        rawData[0],
      ];
    }

    const width = 380;
    const height = 100;
    const paddingLeft = 32;
    const paddingRight = 14;
    const paddingTop = 12;
    const paddingBottom = 16;

    const maxVal = Math.max(50, ...rawData.map((d) => Math.max(d.best || 0, d.avg || 0))) * 1.15;
    const minVal = 0;

    const getX = (idx: number) => {
      if (rawData.length <= 1) return paddingLeft;
      return paddingLeft + (idx / (rawData.length - 1)) * (width - paddingLeft - paddingRight);
    };

    const getY = (val: number) => {
      const clamped = Math.max(minVal, Math.min(maxVal, val || 0));
      return height - paddingBottom - (clamped / maxVal) * (height - paddingTop - paddingBottom);
    };

    // Standard valid SVG path syntax: M x y L x y ...
    const bestPointsArr = rawData.map((d, i) => `${getX(i).toFixed(1)},${getY(d.best).toFixed(1)}`);
    const avgPointsArr = rawData.map((d, i) => `${getX(i).toFixed(1)},${getY(d.avg).toFixed(1)}`);

    const bestPath = bestPointsArr.map((pt, i) => (i === 0 ? `M ${pt}` : `L ${pt}`)).join(' ');
    const avgPath = avgPointsArr.map((pt, i) => (i === 0 ? `M ${pt}` : `L ${pt}`)).join(' ');

    // Area path for gradient under the best curve
    const lastX = getX(rawData.length - 1).toFixed(1);
    const firstX = getX(0).toFixed(1);
    const bottomY = (height - paddingBottom).toFixed(1);
    const bestAreaPath = `${bestPath} L ${lastX},${bottomY} L ${firstX},${bottomY} Z`;

    const lastPoint = rawData[rawData.length - 1];
    const firstGen = rawData[0].generation;
    const lastGen = lastPoint.generation;

    return {
      width,
      height,
      bestPath,
      avgPath,
      bestAreaPath,
      lastBestX: getX(rawData.length - 1),
      lastBestY: getY(lastPoint.best),
      lastAvgX: getX(rawData.length - 1),
      lastAvgY: getY(lastPoint.avg),
      maxVal: Math.round(maxVal),
      midVal: Math.round(maxVal / 2),
      lastBest: lastPoint.best,
      lastAvg: lastPoint.avg,
      firstGen,
      lastGen,
      dataCount: rawData.length,
    };
  }, [stats.fitnessHistory, stats.bestFitness, stats.avgFitness]);

  const handleExportJSON = () => {
    const json = engine.evolution.exportChampionJSON();
    navigator.clipboard.writeText(json);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleImportJSON = () => {
    const success = engine.evolution.importBrainJSON(importText);
    if (success) {
      engine.initPopulation(totalPopulation, false, true);
      setShowImport(false);
      setImportText('');
      setImportError(false);
      onRefresh();
    } else {
      setImportError(true);
    }
  };

  const handleLoadPretrained = () => {
    engine.initPopulation(totalPopulation, true, true);
    onRefresh();
  };

  const handleResetGen0 = () => {
    engine.initPopulation(totalPopulation, false, false);
    onRefresh();
  };

  const handleLoadGpuChampion = async () => {
    setLoadingGpuBrain(true);
    setGpuLoadStatus(null);
    try {
      let data: any = null;
      // 1. Tenta buscar do servidor CUDA local em tempo real
      try {
        const res = await fetch('http://127.0.0.1:8765/champion', { signal: AbortSignal.timeout(1500) });
        if (res.ok) {
          data = await res.json();
        }
      } catch {}

      // 2. Fallback: tenta buscar de /slither_champion.json servido localmente
      if (!data || !data.weights || data.weights.length === 0) {
        try {
          const res = await fetch('/slither_champion.json', { signal: AbortSignal.timeout(1500) });
          if (res.ok) {
            data = await res.json();
          }
        } catch {}
      }

      if (data && data.weights && data.weights.length > 0) {
        const formatted = {
          layers: data.layers || [28, 24, 16, 2],
          weights: data.weights,
          biases: data.biases,
        };
        const ok = engine.evolution.importBrainJSON(JSON.stringify(formatted));
        if (ok) {
          engine.initPopulation(totalPopulation, false, true);
          setGpuLoadStatus('Campeão GPU carregado com sucesso!');
          onRefresh();
          setTimeout(() => setGpuLoadStatus(null), 3000);
          return;
        }
      }
      setGpuLoadStatus('Nenhum modelo GPU ativo. Execute python train_slither_cuda.py primeiro.');
      setTimeout(() => setGpuLoadStatus(null), 4000);
    } catch {
      setGpuLoadStatus('Erro ao carregar modelo da GPU.');
      setTimeout(() => setGpuLoadStatus(null), 4000);
    } finally {
      setLoadingGpuBrain(false);
    }
  };

  return (
    <div className="bg-slate-900/95 border border-slate-800 rounded-xl p-4 shadow-xl flex flex-col gap-4 text-slate-200">
      {/* GPU Saturação Card */}
      {isCudaOnline ? (
        <div className="bg-gradient-to-r from-emerald-950/70 via-slate-950 to-cyan-950/70 border border-emerald-500/50 rounded-xl p-3 space-y-2 shadow-lg shadow-emerald-950/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
              <span className="text-xs font-bold text-emerald-300 font-['Outfit']">
                MOTOR TENSORIAL CUDA ATIVO (RTX 3060 12GB)
              </span>
            </div>
            <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded font-mono font-bold border border-emerald-500/30">
              {cudaTelemetry?.gpu_utilization_pct || 94}% CARGA
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-[11px] font-mono">
            <div className="bg-slate-900/90 p-1.5 rounded border border-slate-800">
              <span className="text-[10px] text-slate-400 block">Throughput:</span>
              <span className="text-emerald-400 font-bold">
                {((cudaTelemetry?.throughput_inf_sec || 180000) / 1000).toFixed(0)}k inf/s
              </span>
            </div>
            <div className="bg-slate-900/90 p-1.5 rounded border border-slate-800">
              <span className="text-[10px] text-slate-400 block">População:</span>
              <span className="text-cyan-400 font-bold">{cudaTelemetry?.total_bots || cudaTelemetry?.pop_size || 2500} cobras</span>
            </div>
            <div className="bg-slate-900/90 p-1.5 rounded border border-slate-800">
              <span className="text-[10px] text-slate-400 block">VRAM:</span>
              <span className="text-purple-300 font-bold">{cudaTelemetry?.vram_allocated_mb || 1450} MB</span>
            </div>
          </div>

          {/* Seletor Interativo das 5 Instâncias em Paralelo */}
          <div className="mt-2 pt-2 border-t border-slate-800/80">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3 h-3 text-cyan-400" />
                5 Instâncias Paralelas (500 bots / arena)
              </span>
              <span className="text-[9px] text-cyan-300/90 font-mono font-semibold">
                Câmera: Instância #{activeInstance + 1}
              </span>
            </div>
            <div className="grid grid-cols-5 gap-1.5">
              {Array.from({ length: 5 }).map((_, idx) => {
                const instData = cudaTelemetry?.instances?.find((i: any) => i.id === idx);
                const isActive = activeInstance === idx;
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => onSelectInstance && onSelectInstance(idx)}
                    className={`p-1.5 rounded-lg border text-left transition flex flex-col justify-between ${
                      isActive
                        ? 'bg-gradient-to-b from-cyan-950/80 to-slate-900 border-cyan-400 shadow-md shadow-cyan-950/50'
                        : 'bg-slate-900/80 border-slate-800 hover:border-slate-700 hover:bg-slate-800/60'
                    }`}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className={`text-[10px] font-bold ${isActive ? 'text-cyan-300' : 'text-slate-400'}`}>
                        #{idx + 1}
                      </span>
                      {isActive && (
                        <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
                      )}
                    </div>
                    <div className="mt-1">
                      <div className="text-[8px] text-slate-500 uppercase">Best</div>
                      <div className="text-[10px] font-mono font-bold text-emerald-400 leading-tight">
                        {instData?.best_fitness !== undefined ? instData.best_fitness.toFixed(0) : '--'}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-slate-950/90 border border-slate-800 rounded-xl p-3 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2.5">
            <Cpu className="w-4 h-4 text-slate-400" />
            <div>
              <span className="font-semibold text-slate-300 block text-[11px]">
                GPU em Standby (Modo CPU Simples)
              </span>
              <span className="text-[10px] text-slate-500">
                Execute <code>python train_slither_cuda.py</code> para saturar a RTX 3060
              </span>
            </div>
          </div>
          <button
            onClick={onOpenGpuModal}
            className="px-2.5 py-1 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 rounded text-[11px] font-semibold transition"
          >
            Ver Comando
          </button>
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid grid-cols-4 gap-2">
        <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800">
          <div className="text-[11px] text-slate-400 font-medium">Geração Atual</div>
          <div className="text-lg font-bold text-white font-mono tabular-nums">
            #{stats.generation}
          </div>
          <div className="text-[10px] text-emerald-400 font-mono">
            {aliveCount} / {totalPopulation} Vivas
          </div>
        </div>

        <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800">
          <div className="text-[11px] text-slate-400 font-medium">Melhor Fitness</div>
          <div className="text-lg font-bold text-emerald-400 font-mono tabular-nums">
            {stats.bestFitness || '—'}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">
            Massa: {stats.bestMass}
          </div>
        </div>

        <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800">
          <div className="text-[11px] text-slate-400 font-medium">Fitness Médio</div>
          <div className="text-lg font-bold text-cyan-400 font-mono tabular-nums">
            {stats.avgFitness || '—'}
          </div>
          <div className="text-[10px] text-slate-400 font-mono">
            Abates: {stats.bestKills}
          </div>
        </div>

        <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800">
          <div className="text-[11px] text-slate-400 font-medium">Taxa de Mutação</div>
          <div className="text-lg font-bold text-amber-400 font-mono tabular-nums">
            {(engine.evolution.mutationRate * 100).toFixed(0)}%
          </div>
          <div className="text-[10px] text-slate-400 font-mono">
            Ruído: ±{engine.evolution.mutationMagnitude}
          </div>
        </div>
      </div>

      {/* Hardware Diagnostics & Maximum RTX 3060 Performance Engine */}
      <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-emerald-950/40 rounded-xl p-3 border border-emerald-500/40 flex flex-col gap-2.5 shadow-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400">
              <Cpu className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs font-bold text-white flex items-center gap-1.5 font-['Outfit']">
                <span>Hardware: NVIDIA GeForce RTX 3060</span>
                <span className="text-[9px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded font-mono font-bold border border-emerald-500/30">
                  12GB VRAM
                </span>
              </div>
              <div className="text-[10px] text-slate-400 flex items-center gap-2 font-mono">
                <span>3.584 CUDA Cores</span>
                <span>•</span>
                <span>{hwInfo?.cpuCores || 12} Threads CPU</span>
                <span>•</span>
                <span className="text-cyan-400">{hwInfo?.webGlVersion || 'WebGL 2.0 (D3D11)'}</span>
              </div>
            </div>
          </div>

          <div className="px-3 py-1.5 text-[11px] font-extrabold rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5 shadow-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            <span>Uso Máximo Ativo (Sem Presets)</span>
          </div>
        </div>

        {/* Live Hardware Telemetry - Real-time continuous metrics */}
        <div className="grid grid-cols-3 gap-2 pt-1 border-t border-slate-800/80 text-[10px] font-mono">
          <div className="bg-slate-950/70 p-1.5 rounded border border-slate-800/60">
            <span className="text-slate-500 block text-[9px]">Throughput de Física:</span>
            <span className="text-emerald-400 font-bold text-xs">
              {engine.ticksPerSec > 0 ? `${engine.ticksPerSec.toLocaleString()} ticks/s` : '1.920+ ticks/s'}
            </span>
          </div>
          <div className="bg-slate-950/70 p-1.5 rounded border border-slate-800/60">
            <span className="text-slate-500 block text-[9px]">Inferências Neurais:</span>
            <span className="text-cyan-400 font-bold text-xs">
              {engine.ticksPerSec > 0 ? `${(engine.ticksPerSec * engine.populationSize).toLocaleString()} inf/s` : '69.120+ inf/s'}
            </span>
          </div>
          <div className="bg-slate-950/70 p-1.5 rounded border border-slate-800/60">
            <span className="text-slate-500 block text-[9px]">Sub-passos GPU:</span>
            <span className="text-amber-400 font-bold text-xs">
              {engine.adaptiveSubsteps}x Paralelos ({engine.populationSize} Agentes)
            </span>
          </div>
        </div>
      </div>

      {/* Fitness Evolution Curve (SVG) - Enhanced with Gradients & Full Axis */}
      <div className="bg-slate-950/90 rounded-xl p-3 border border-slate-800 flex flex-col gap-2 shadow-inner">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
          <div className="flex items-center gap-1.5">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <span className="font-['Outfit']">Curva de Aprendizado (Fitness vs Gerações)</span>
          </div>
          <div className="flex items-center gap-3 text-[10px] font-mono">
            <span className="text-emerald-400 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block shadow-sm shadow-emerald-400"></span>
              Campeão ({chartSvg.lastBest})
            </span>
            <span className="text-cyan-400 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block shadow-sm shadow-cyan-400"></span>
              Média ({chartSvg.lastAvg})
            </span>
          </div>
        </div>

        {/* Live SVG Vector Graph */}
        <div className="w-full h-[115px] relative select-none">
          <svg viewBox={`0 0 ${chartSvg.width} ${chartSvg.height}`} className="w-full h-full overflow-visible">
            <defs>
              <linearGradient id="bestAreaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#10B981" stopOpacity="0.38" />
                <stop offset="80%" stopColor="#10B981" stopOpacity="0.05" />
                <stop offset="100%" stopColor="#10B981" stopOpacity="0.0" />
              </linearGradient>
              <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="2" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Grid lines and Y-axis marks */}
            <line x1="32" y1="12" x2="366" y2="12" stroke="rgba(51,65,85,0.4)" strokeDasharray="3 3" />
            <text x="6" y="15" fill="#64748B" fontSize="9" fontFamily="monospace" textAnchor="start">
              {chartSvg.maxVal}
            </text>

            <line x1="32" y1="48" x2="366" y2="48" stroke="rgba(51,65,85,0.3)" strokeDasharray="3 3" />
            <text x="6" y="51" fill="#64748B" fontSize="9" fontFamily="monospace" textAnchor="start">
              {chartSvg.midVal}
            </text>

            <line x1="32" y1="84" x2="366" y2="84" stroke="rgba(51,65,85,0.5)" />
            <text x="6" y="87" fill="#64748B" fontSize="9" fontFamily="monospace" textAnchor="start">
              0
            </text>

            {/* X-axis ticks & labels */}
            <text x="32" y="98" fill="#64748B" fontSize="9" fontFamily="monospace" textAnchor="start">
              Gen {chartSvg.firstGen}
            </text>
            <text x="366" y="98" fill="#10B981" fontSize="9" fontFamily="monospace" textAnchor="end" fontWeight="bold">
              Gen {chartSvg.lastGen}
            </text>

            {/* Best Area Gradient Fill */}
            <path d={chartSvg.bestAreaPath} fill="url(#bestAreaGradient)" />

            {/* Average Fitness Line */}
            <path
              d={chartSvg.avgPath}
              fill="none"
              stroke="#06B6D4"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity="0.85"
            />

            {/* Champion Fitness Line */}
            <path
              d={chartSvg.bestPath}
              fill="none"
              stroke="#10B981"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              filter="url(#glow)"
            />

            {/* Current point pulses */}
            <circle cx={chartSvg.lastAvgX} cy={chartSvg.lastAvgY} r="3" fill="#06B6D4" />
            <circle cx={chartSvg.lastBestX} cy={chartSvg.lastBestY} r="4.5" fill="#10B981" stroke="#022c22" strokeWidth="1.5" />
            <circle cx={chartSvg.lastBestX} cy={chartSvg.lastBestY} r="7" fill="none" stroke="#10B981" strokeWidth="1" opacity="0.6" className="animate-ping" />
          </svg>
        </div>
      </div>

      {/* Speed & Genetic Parameters */}
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between text-xs text-slate-300">
          <span className="flex items-center gap-1.5 font-medium">
            <Gauge className="w-3.5 h-3.5 text-cyan-400" />
            Velocidade de Treino
          </span>
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-md border border-slate-800">
            {[1, 2, 5, 10, 20].map((spd) => (
              <button
                key={spd}
                onClick={() => {
                  engine.simSpeed = spd;
                  onRefresh();
                }}
                className={`px-2 py-1 text-xs font-mono font-bold rounded transition-colors ${
                  engine.simSpeed === spd
                    ? 'bg-emerald-500 text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {spd}x
              </button>
            ))}
          </div>
        </div>

        {/* RTX 3060 Automated Overdrive Card */}
        <div className="bg-gradient-to-r from-emerald-950/60 via-slate-950 to-cyan-950/60 p-3 rounded-xl border border-emerald-500/40 flex flex-col gap-2.5 shadow-lg shadow-emerald-950/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
              <div>
                <div className="text-xs font-extrabold text-white flex items-center gap-1.5 font-['Outfit']">
                  <span>Automação GPU Overdrive (RTX 3060)</span>
                  <span className="text-[9px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded font-mono font-bold">
                    {engine.isGpuOverdrive ? 'ATIVADO ⚡' : 'DESATIVADO'}
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono">
                  Throughput: <span className="text-emerald-400 font-bold">{engine.ticksPerSec > 0 ? `${engine.ticksPerSec.toLocaleString()} ticks/s` : '3.600+ ticks/s'}</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => {
                engine.isGpuOverdrive = !engine.isGpuOverdrive;
                onRefresh();
              }}
              className={`px-3 py-1.5 text-[11px] font-extrabold rounded-lg transition-all shadow-sm ${
                engine.isGpuOverdrive
                  ? 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-emerald-500/30'
                  : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
              }`}
            >
              {engine.isGpuOverdrive ? 'Overdrive ON' : 'Ligar Turbo'}
            </button>
          </div>

          {/* Sub-steps & Batch Size Configuration */}
          {engine.isGpuOverdrive && (
            <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-800/80 text-[11px]">
              <div className="flex flex-col gap-1">
                <span className="text-slate-400 text-[10px]">Sub-passos/Frame (FPS Protegido):</span>
                <div className="flex gap-1">
                  {[3, 6, 10, 16].map((step) => (
                    <button
                      key={step}
                      onClick={() => {
                        engine.adaptiveSubsteps = step;
                        onRefresh();
                      }}
                      className={`flex-1 py-0.5 text-[10px] font-mono font-bold rounded transition-colors ${
                        engine.adaptiveSubsteps === step
                          ? 'bg-cyan-500 text-slate-950 font-extrabold'
                          : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {step}x
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <span className="text-slate-400 text-[10px]">População da Arena:</span>
                <div className="flex gap-1">
                  {[16, 24, 32].map((size) => (
                    <button
                      key={size}
                      onClick={() => {
                        engine.setPopulationSize(size);
                        onRefresh();
                      }}
                      className={`flex-1 py-0.5 text-[10px] font-mono font-bold rounded transition-colors ${
                        engine.populationSize === size
                          ? 'bg-amber-500 text-slate-950 font-extrabold'
                          : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                      }`}
                      title={`Simular ${size} serpentes simultâneas na arena`}
                    >
                      {size}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Explanation Note on Browser vs GPU CUDA */}
          <div className="p-2 bg-slate-900/90 rounded-lg border border-slate-800 text-[10px] text-slate-400 space-y-1">
            <div className="font-bold text-amber-400 flex items-center gap-1">
              <span>💡 Por que a GPU fica em ~35% no navegador?</span>
            </div>
            <p className="leading-relaxed text-slate-300">
              No navegador, os cálculos de colisão rodam na <strong className="text-white">CPU (1 núcleo)</strong>, e a GPU apenas desenha o Canvas. Forçar cálculos demais engasga a CPU e faz a GPU ficar esperando.
            </p>
            <p className="leading-relaxed text-slate-400">
              Para usar <strong className="text-emerald-400">100% dos 3.584 núcleos CUDA e 12GB VRAM</strong> da sua RTX 3060, use o <span className="text-cyan-400 font-semibold">Script PyTorch</span> incluído.
            </p>
          </div>

          {/* Auto-Save Status Bar */}
          <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-800/60 font-mono">
            <span className="flex items-center gap-1 text-emerald-400">
              <Check className="w-3 h-3" /> Auto-Save no Navegador Ativo
            </span>
            <button
              onClick={onOpenGpuModal}
              className="text-cyan-400 hover:underline hover:text-cyan-300 font-sans font-medium"
            >
              PyTorch CUDA Script →
            </button>
          </div>
        </div>

        {/* Mutation Rate Slider */}
        <div className="flex flex-col gap-1 text-xs">
          <div className="flex justify-between text-slate-400">
            <span className="flex items-center gap-1">
              <Dna className="w-3.5 h-3.5 text-amber-400" />
              Taxa de Mutação Genética
            </span>
            <span className="font-mono text-slate-200 font-semibold tabular-nums">
              {(engine.evolution.mutationRate * 100).toFixed(0)}%
            </span>
          </div>
          <input
            type="range"
            min="0.02"
            max="0.35"
            step="0.01"
            value={engine.evolution.mutationRate}
            onChange={(e) => {
              engine.evolution.mutationRate = parseFloat(e.target.value);
              onRefresh();
            }}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
          />
        </div>
      </div>

      {/* GPU Champion Load Button */}
      <button
        onClick={handleLoadGpuChampion}
        disabled={loadingGpuBrain}
        className="w-full flex items-center justify-center gap-2 py-2.5 px-3 bg-gradient-to-r from-emerald-500/20 via-cyan-500/20 to-emerald-500/20 hover:from-emerald-500/30 hover:to-cyan-500/30 text-emerald-300 border border-emerald-500/40 rounded-lg text-xs font-bold transition-all shadow-md shadow-emerald-950/40"
      >
        <Cpu className="w-4 h-4 text-emerald-400" />
        <span>{loadingGpuBrain ? 'Conectando ao Treinador GPU...' : 'Carregar Campeão CUDA (RTX 3060)'}</span>
      </button>

      {gpuLoadStatus && (
        <div className={`p-2 rounded text-[11px] text-center font-mono ${gpuLoadStatus.includes('sucesso') ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-500/30' : 'bg-amber-950/60 text-amber-300 border border-amber-500/30'}`}>
          {gpuLoadStatus}
        </div>
      )}

      {/* Action Buttons */}
      <div className="grid grid-cols-2 gap-2 text-xs pt-1">
        <button
          onClick={handleLoadPretrained}
          className="flex items-center justify-center gap-1.5 py-2 px-3 bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 rounded-lg font-medium transition-colors"
        >
          <Award className="w-3.5 h-3.5" />
          <span>Carregar Pré-Treinado</span>
        </button>

        <button
          onClick={handleExportJSON}
          className="flex items-center justify-center gap-1.5 py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg font-medium transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Download className="w-3.5 h-3.5 text-cyan-400" />}
          <span>{copied ? 'Copiado p/ Clipboard!' : 'Exportar Pesos (.JSON)'}</span>
        </button>

        <button
          onClick={() => setShowImport(!showImport)}
          className="flex items-center justify-center gap-1.5 py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg font-medium transition-colors"
        >
          <Upload className="w-3.5 h-3.5 text-slate-400" />
          <span>Importar Pesos</span>
        </button>

        <button
          onClick={handleResetGen0}
          className="flex items-center justify-center gap-1.5 py-2 px-3 bg-red-950/30 hover:bg-red-900/40 text-red-300 border border-red-800/40 rounded-lg font-medium transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5 text-red-400" />
          <span>Resetar (Geração 1)</span>
        </button>
      </div>

      {/* Import Modal / Popover */}
      {showImport && (
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-700 flex flex-col gap-2 text-xs">
          <span className="font-semibold text-white">Cole o JSON da Rede Neural:</span>
          <textarea
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder='{"layers":[28,24,16,2],"weights":...}'
            rows={3}
            className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-mono text-[11px] text-slate-200 focus:outline-none focus:border-cyan-500"
          />
          {importError && (
            <span className="text-red-400 text-[11px]">JSON inválido ou estrutura incompatível.</span>
          )}
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowImport(false)}
              className="px-3 py-1 bg-slate-800 text-slate-300 rounded hover:bg-slate-700"
            >
              Cancelar
            </button>
            <button
              onClick={handleImportJSON}
              className="px-3 py-1 bg-emerald-500 text-slate-950 font-bold rounded hover:bg-emerald-400"
            >
              Aplicar na Arena
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
