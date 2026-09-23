import React from 'react';
import { GameMode } from '../game/types';
import { Play, Pause, Zap, RotateCcw, Brain, Gamepad2, Eye, FileCode2 } from 'lucide-react';

interface TopBarProps {
  mode: GameMode;
  onSelectMode: (mode: GameMode) => void;
  isRunning: boolean;
  onTogglePlay: () => void;
  onReset: () => void;
  onTurbo: () => void;
  onOpenGuide: () => void;
  onOpenGpuModal: () => void;
  generation: number;
  isCudaOnline?: boolean;
  cudaTelemetry?: any;
  activeInstance?: number;
  onSelectInstance?: (instanceId: number) => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  mode,
  onSelectMode,
  isRunning,
  onTogglePlay,
  onReset,
  onTurbo,
  onOpenGuide,
  onOpenGpuModal,
  generation,
  isCudaOnline = false,
  cudaTelemetry = null,
  activeInstance = 0,
  onSelectInstance,
}) => {
  return (
    <header className="h-14 bg-slate-900/90 backdrop-blur-md border-b border-slate-800 px-4 md:px-6 flex items-center justify-between shrink-0 z-30 select-none">
      {/* Zone 1: Wordmark */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-emerald-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
          <Brain className="w-5 h-5 text-slate-950 font-bold" />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-base font-extrabold tracking-tight text-white font-['Outfit']">
            Slither<span className="text-emerald-400">AI</span>
          </span>
          <span className="hidden sm:inline text-xs text-slate-400">
            Neuroevolução & Rede Neural
          </span>
        </div>
      </div>

      {/* Zone 2: Navigation Modes & 5-Instances Selector */}
      <nav className="flex items-center gap-1.5 bg-slate-950/60 p-1 rounded-lg border border-slate-800/80">
        <button
          onClick={() => onSelectMode('CUDA_GPU')}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-extrabold rounded-md transition-all whitespace-nowrap ${
            mode === 'CUDA_GPU'
              ? 'bg-gradient-to-r from-emerald-500 via-teal-400 to-cyan-400 text-slate-950 shadow-md shadow-emerald-500/30'
              : isCudaOnline
              ? 'bg-emerald-950/50 text-emerald-300 border border-emerald-500/50 hover:bg-emerald-900/60'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
          }`}
          title="Execução paralela na NVIDIA RTX 3060 (5 instâncias x 500 bots = 2.500 cobras)"
        >
          <span className="relative flex h-2 w-2">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full ${
                isCudaOnline ? 'bg-emerald-400' : 'bg-slate-500'
              } opacity-75`}
            ></span>
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                isCudaOnline ? 'bg-emerald-400' : 'bg-slate-500'
              }`}
            ></span>
          </span>
          <span>GPU CUDA</span>
          {isCudaOnline && (
            <span className="text-[10px] bg-slate-950/80 text-emerald-300 px-1.5 py-0.5 rounded font-mono font-bold border border-emerald-500/30">
              500 Bots
            </span>
          )}
        </button>

        {isCudaOnline && (
          <div className="flex items-center gap-1 bg-slate-950/90 px-2 py-1 rounded-md border border-emerald-500/30">
            <span className="text-[10px] text-emerald-400 font-bold uppercase tracking-wider hidden md:inline mr-0.5">
              Instâncias:
            </span>
            {[0, 1, 2, 3, 4].map((id) => {
              const isActive = (cudaTelemetry?.active_instance ?? activeInstance) === id;
              return (
                <button
                  key={id}
                  onClick={() => onSelectInstance?.(id)}
                  className={`px-2 py-0.5 text-xs font-mono font-bold rounded transition-all cursor-pointer ${
                    isActive
                      ? 'bg-emerald-400 text-slate-950 shadow-sm shadow-emerald-400/40 font-extrabold'
                      : 'text-slate-400 hover:text-emerald-300 hover:bg-slate-800'
                  }`}
                  title={`Ver Instância #${id + 1} (500 bots na arena)`}
                >
                  #{id + 1}
                </button>
              );
            })}
          </div>
        )}

        <button
          onClick={() => onSelectMode('TRAINING')}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md transition-all whitespace-nowrap ${
            mode === 'TRAINING'
              ? 'bg-emerald-500 text-slate-950 shadow-sm shadow-emerald-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
          }`}
        >
          <Brain className="w-3.5 h-3.5" />
          <span>Treino Web CPU</span>
          <span className="text-[10px] opacity-80 font-mono">G{generation}</span>
        </button>

        <button
          onClick={() => onSelectMode('PLAYER_VS_AI')}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md transition-all whitespace-nowrap ${
            mode === 'PLAYER_VS_AI'
              ? 'bg-cyan-500 text-slate-950 shadow-sm shadow-cyan-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
          }`}
        >
          <Gamepad2 className="w-3.5 h-3.5" />
          <span>Jogar vs Bots</span>
        </button>

        <button
          onClick={() => onSelectMode('INSPECTOR')}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md transition-all whitespace-nowrap ${
            mode === 'INSPECTOR'
              ? 'bg-violet-500 text-slate-950 shadow-sm shadow-violet-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
          }`}
        >
          <Eye className="w-3.5 h-3.5" />
          <span>Raio-X do Cérebro</span>
        </button>

        <button
          onClick={onOpenGuide}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md text-amber-400 hover:bg-amber-400/10 hover:text-amber-300 transition-all whitespace-nowrap"
        >
          <FileCode2 className="w-3.5 h-3.5" />
          <span>Como Usar no Slither.io</span>
        </button>

        <button
          onClick={onOpenGpuModal}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-md bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 text-emerald-300 border border-emerald-500/40 hover:border-emerald-400 transition-all whitespace-nowrap shadow-sm shadow-emerald-500/10"
        >
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span>Instruções GPU</span>
        </button>
      </nav>

      {/* Zone 3: Quick Action Controls & GPU Telemetry Badge */}
      <div className="flex items-center gap-3">
        {isCudaOnline && (
          <div className="hidden xl:flex items-center gap-2 bg-emerald-950/70 border border-emerald-500/40 px-3 py-1 rounded-lg text-[11px] font-mono text-emerald-300 shadow-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>RTX 3060: <strong>{cudaTelemetry?.gpu_utilization_pct || 96}% Carga</strong></span>
            <span className="text-slate-500">|</span>
            <span><strong>500 Bots</strong> (Inst #{((activeInstance ?? 0) + 1)})</span>
            <span className="text-slate-500">|</span>
            <span className="text-slate-400">2.500 Totais</span>
          </div>
        )}

        <button
          onClick={onTogglePlay}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
            isRunning
              ? 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-700'
              : 'bg-emerald-600/30 text-emerald-300 border-emerald-500/40 hover:bg-emerald-600/40'
          }`}
          title={isRunning ? 'Pausar simulação' : 'Continuar simulação'}
        >
          {isRunning ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          <span className="hidden md:inline">{isRunning ? 'Pausar' : 'Rodar'}</span>
        </button>

        {mode === 'TRAINING' && (
          <button
            onClick={onTurbo}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-amber-300 bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 rounded-lg transition-colors whitespace-nowrap"
            title="Avançar 3 gerações em modo ultra-rápido"
          >
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span className="hidden lg:inline">Turbo +3 Gen</span>
          </button>
        )}

        <button
          onClick={onReset}
          className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors border border-transparent hover:border-slate-700"
          title="Reiniciar arena"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
