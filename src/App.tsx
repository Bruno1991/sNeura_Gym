/**
 * SlitherAI - Interactive Neural Network & Neuroevolution Studio for Slither.io
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { SlitherEngine } from './game/engine';
import { GameMode, Snake } from './game/types';
import { TopBar } from './components/TopBar';
import { SlitherCanvas } from './components/SlitherCanvas';
import { NeuralVisualizer } from './components/NeuralVisualizer';
import { TrainingPanel } from './components/TrainingPanel';
import { PlayerHUD } from './components/PlayerHUD';
import { IntegrationGuideModal } from './components/IntegrationGuideModal';
import { GpuAccelerationModal } from './components/GpuAccelerationModal';
import { Eye, EyeOff, ChevronRight, ChevronLeft, Sparkles, BrainCircuit } from 'lucide-react';

export default function App() {
  const engineRef = useRef<SlitherEngine | null>(null);
  if (!engineRef.current) {
    engineRef.current = new SlitherEngine();
    engineRef.current.mode = 'CUDA_GPU';
  }
  const engine = engineRef.current;

  const [mode, setMode] = useState<GameMode>('CUDA_GPU');
  const [isRunning, setIsRunning] = useState<boolean>(true);
  const [showSensors, setShowSensors] = useState<boolean>(true);
  const [isGuideOpen, setIsGuideOpen] = useState<boolean>(false);
  const [isGpuModalOpen, setIsGpuModalOpen] = useState<boolean>(false);
  const [isHeadlessRunning, setIsHeadlessRunning] = useState<boolean>(false);
  const [selectedSnake, setSelectedSnake] = useState<Snake | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [isGameOver, setIsGameOver] = useState<boolean>(false);
  const [lastPlayerStats, setLastPlayerStats] = useState<{ mass: number; kills: number; timeAlive: number } | undefined>();
  const [isCudaOnline, setIsCudaOnline] = useState<boolean>(false);
  const [cudaData, setCudaData] = useState<any>(null);
  const [, setTick] = useState<number>(0);

  // Sync callbacks with engine
  useEffect(() => {
    engine.onGenerationEvolve = () => {
      setTick((t) => t + 1);
    };

    engine.onPlayerDeath = (stats) => {
      setIsGameOver(true);
      setLastPlayerStats(stats);
      setTick((t) => t + 1);
    };
  }, [engine]);

  // Real-time synchronization with PyTorch CUDA Tensor Engine (train_slither_cuda.py)
  useEffect(() => {
    let isMounted = true;
    const pollCuda = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8765/telemetry', { signal: AbortSignal.timeout(1200) });
        if (res.ok) {
          const data = await res.json();
          if (isMounted) {
            setIsCudaOnline(true);
            setCudaData(data);
            engine.updateFromCuda(data);
            setTick((t) => t + 1);
          }
        } else {
          if (isMounted) setIsCudaOnline(false);
        }
      } catch {
        if (isMounted) setIsCudaOnline(false);
      }
    };

    pollCuda();
    const interval = setInterval(pollCuda, 120);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [engine]);

  // Periodic telemetry state refresh (at ~6-10Hz) to keep UI meters in sync without lagging 60Hz canvas
  useEffect(() => {
    const timer = setInterval(() => {
      const tracked = engine.getTrackedSnake();
      setSelectedSnake(tracked);
      setTick((t) => t + 1);
    }, 150);
    return () => clearInterval(timer);
  }, [engine]);

  // Mode switching
  const handleSelectMode = useCallback(
    (newMode: GameMode) => {
      setMode(newMode);
      engine.mode = newMode;
      setIsGameOver(false);

      if (newMode === 'CUDA_GPU') {
        engine.mode = 'CUDA_GPU';
        setShowSensors(true);
      } else if (newMode === 'PLAYER_VS_AI') {
        engine.startPlayerVsAIMode();
        setShowSensors(false);
      } else if (newMode === 'TRAINING') {
        engine.initPopulation(24, true);
        setShowSensors(true);
      } else if (newMode === 'INSPECTOR') {
        setShowSensors(true);
      }
      setTick((t) => t + 1);
    },
    [engine]
  );

  const handleTogglePlay = useCallback(() => {
    engine.isRunning = !engine.isRunning;
    setIsRunning(engine.isRunning);
    setTick((t) => t + 1);
  }, [engine]);

  const handleReset = useCallback(() => {
    setIsGameOver(false);
    if (mode === 'PLAYER_VS_AI') {
      engine.startPlayerVsAIMode();
    } else {
      engine.initPopulation(24, true);
    }
    setTick((t) => t + 1);
  }, [engine, mode]);

  const handleTurbo = useCallback(() => {
    engine.runTurboGenerations(3);
    setTick((t) => t + 1);
  }, [engine]);

  const handleRunHeadlessGenerations = useCallback(
    async (gens: number) => {
      setIsHeadlessRunning(true);
      try {
        await engine.runHeadlessBatchAsync(gens, () => {
          setTick((t) => t + 1);
        });
      } finally {
        setIsHeadlessRunning(false);
        setTick((t) => t + 1);
      }
    },
    [engine]
  );

  const handleRespawn = useCallback(() => {
    setIsGameOver(false);
    engine.respawnPlayer();
    setTick((t) => t + 1);
  }, [engine]);

  const handleSelectInstance = useCallback(async (instanceId: number) => {
    try {
      await fetch(`http://127.0.0.1:8765/set_instance?id=${instanceId}`);
      if (engineRef.current) {
        engineRef.current.activeInstanceId = instanceId;
      }
      setTick((t) => t + 1);
    } catch {
      // ignore
    }
  }, []);

  const playerSnake = engine.snakes.find((s) => s.id === engine.playerSnakeId) || null;
  const aliveCount = engine.snakes.filter((s) => s.alive).length;

  return (
    <div className="flex flex-col w-screen h-screen overflow-hidden bg-slate-950 text-slate-100">
      {/* 1. Header Navigation */}
      <TopBar
        mode={mode}
        onSelectMode={handleSelectMode}
        isRunning={isRunning}
        onTogglePlay={handleTogglePlay}
        onReset={handleReset}
        onTurbo={handleTurbo}
        onOpenGuide={() => setIsGuideOpen(true)}
        onOpenGpuModal={() => setIsGpuModalOpen(true)}
        generation={engine.evolution.generation}
        isCudaOnline={isCudaOnline}
        cudaTelemetry={cudaData}
        activeInstance={cudaData?.active_instance ?? engine.activeInstanceId}
        onSelectInstance={handleSelectInstance}
      />

      {/* 2. Main Arena & Side Panels */}
      <div className="relative flex-1 flex overflow-hidden">
        {/* Slither Canvas Stage */}
        <div className="relative flex-1 h-full overflow-hidden">
          <SlitherCanvas
            engine={engine}
            showSensors={showSensors}
            onSelectSnake={(snake) => setSelectedSnake(snake)}
          />

          {/* Player HUD & Leaderboard */}
          <PlayerHUD
            snakes={engine.snakes}
            playerSnake={playerSnake}
            onRespawn={handleRespawn}
            isGameOver={isGameOver}
            lastStats={lastPlayerStats}
          />

          {/* Quick HUD controls overlay (Top Left) */}
          <div className="absolute top-4 left-4 z-20 flex items-center gap-2">
            <button
              onClick={() => setShowSensors(!showSensors)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold backdrop-blur-md border transition-all shadow-md ${
                showSensors
                  ? 'bg-emerald-950/80 border-emerald-500/50 text-emerald-300'
                  : 'bg-slate-900/80 border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {showSensors ? <Eye className="w-3.5 h-3.5 text-emerald-400" /> : <EyeOff className="w-3.5 h-3.5" />}
              <span>Raios de Visão</span>
            </button>

            {/* In Training mode: Generation Pill */}
            {mode === 'TRAINING' && (
              <>
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono bg-slate-900/80 backdrop-blur-md border border-slate-800 text-slate-300 shadow-md">
                  <BrainCircuit className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Gen #{engine.evolution.generation}</span>
                  <span className="text-slate-500">·</span>
                  <span className="text-emerald-400 font-bold">{aliveCount}/{engine.populationSize} Vivas</span>
                </div>

                {engine.isGpuOverdrive && (
                  <button
                    onClick={() => setIsGpuModalOpen(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono bg-gradient-to-r from-emerald-950/90 to-slate-900/90 backdrop-blur-md border border-emerald-500/50 text-emerald-300 shadow-md hover:border-emerald-400 transition-all cursor-pointer"
                    title="Clique para abrir detalhes da Aceleração GPU"
                  >
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
                    </span>
                    <span className="font-bold text-white">GPU Overdrive</span>
                    <span className="text-slate-500">·</span>
                    <span className="text-emerald-300 font-bold">
                      {engine.ticksPerSec > 0 ? `${engine.ticksPerSec.toLocaleString()} t/s` : `${engine.adaptiveSubsteps}x Substeps`}
                    </span>
                  </button>
                )}
              </>
            )}
          </div>

          {/* Floating Sidebar Toggle Button (when closed) */}
          {!isSidebarOpen && (
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="absolute top-4 right-4 z-20 flex items-center gap-1.5 px-3 py-1.5 bg-slate-900/90 hover:bg-slate-800 border border-slate-700 text-slate-200 rounded-lg text-xs font-semibold shadow-xl transition-all"
            >
              <ChevronLeft className="w-4 h-4 text-emerald-400" />
              <span>Painel IA</span>
            </button>
          )}
        </div>

        {/* 3. Right Drawer: Neural Visualizer & Training Telemetry */}
        {isSidebarOpen && (
          <aside className="w-full sm:w-[420px] lg:w-[460px] h-full bg-slate-900/95 backdrop-blur-md border-l border-slate-800 flex flex-col z-20 shrink-0 shadow-2xl transition-all">
            {/* Drawer Header */}
            <div className="h-11 px-4 border-b border-slate-800 flex items-center justify-between text-xs font-bold text-slate-200 bg-slate-950/40">
              <div className="flex items-center gap-2">
                <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                <span className="font-['Outfit'] uppercase tracking-wider text-[11px]">
                  {mode === 'TRAINING'
                    ? 'Laboratório de Neuroevolução'
                    : mode === 'PLAYER_VS_AI'
                    ? 'Cérebro dos Oponentes'
                    : 'Inspeção Detalhada do Bot'}
                </span>
              </div>
              <button
                onClick={() => setIsSidebarOpen(false)}
                className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800 transition-colors"
                title="Minimizar painel"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            {/* Scrollable Panel Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Real-time Synaptic Neural Network Architecture */}
              <NeuralVisualizer
                snake={selectedSnake}
                championBrain={engine.evolution.bestChampionBrain}
              />

              {/* Training Stats and Genetic Sliders (in Training or CUDA_GPU mode) */}
              {(mode === 'TRAINING' || mode === 'CUDA_GPU') && (
                <TrainingPanel
                  engine={engine}
                  stats={engine.evolution.stats}
                  aliveCount={mode === 'CUDA_GPU' ? (cudaData?.live_snakes?.length || 500) : aliveCount}
                  totalPopulation={mode === 'CUDA_GPU' ? (cudaData?.total_bots || 2500) : 24}
                  onRefresh={() => setTick((t) => t + 1)}
                  onOpenGpuModal={() => setIsGpuModalOpen(true)}
                  isCudaOnline={isCudaOnline}
                  cudaTelemetry={cudaData}
                  isCudaMode={mode === 'CUDA_GPU'}
                  activeInstance={cudaData?.active_instance ?? engine.activeInstanceId}
                  onSelectInstance={handleSelectInstance}
                />
              )}

              {/* Information Card if in Player or Inspector Mode */}
              {mode !== 'TRAINING' && mode !== 'CUDA_GPU' && (
                <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 space-y-2 text-xs">
                  <span className="font-semibold text-white block">Como a IA joga agora:</span>
                  <p className="text-slate-400 leading-relaxed">
                    O cérebro visualizado acima toma 60 decisões por segundo calculando a trajetória de menor perigo e maior concentração de alimento.
                  </p>
                  <div className="pt-2 border-t border-slate-800 flex justify-between items-center">
                    <span className="text-slate-500 font-mono text-[11px]">
                      Abates do Campeão: {engine.evolution.stats.bestKills}
                    </span>
                    <button
                      onClick={() => setIsGuideOpen(true)}
                      className="text-amber-400 hover:underline font-semibold"
                    >
                      Exportar para Slither.io →
                    </button>
                  </div>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>

      {/* 4. Integration Guide & Script Export Modal */}
      <IntegrationGuideModal
        isOpen={isGuideOpen}
        onClose={() => setIsGuideOpen(false)}
        championBrain={engine.evolution.bestChampionBrain}
      />

      {/* 5. GPU RTX 3060 CUDA Acceleration Modal */}
      <GpuAccelerationModal
        isOpen={isGpuModalOpen}
        onClose={() => setIsGpuModalOpen(false)}
        onRunHeadlessGenerations={handleRunHeadlessGenerations}
        isHeadlessRunning={isHeadlessRunning}
      />
    </div>
  );
}
