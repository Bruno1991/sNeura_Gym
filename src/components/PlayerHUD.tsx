import React from 'react';
import { Snake } from '../game/types';
import { Trophy, Crosshair, Zap, RotateCcw } from 'lucide-react';

interface PlayerHUDProps {
  snakes: Snake[];
  playerSnake: Snake | null;
  onRespawn: () => void;
  isGameOver: boolean;
  lastStats?: { mass: number; kills: number; timeAlive: number };
}

export const PlayerHUD: React.FC<PlayerHUDProps> = ({
  snakes,
  playerSnake,
  onRespawn,
  isGameOver,
  lastStats,
}) => {
  // Sort top 8 snakes by mass
  const leaderboard = snakes
    .filter((s) => s.alive)
    .sort((a, b) => b.mass - a.mass)
    .slice(0, 8);

  const playerRank = playerSnake
    ? snakes
        .filter((s) => s.alive)
        .sort((a, b) => b.mass - a.mass)
        .findIndex((s) => s.id === playerSnake.id) + 1
    : 0;

  return (
    <>
      {/* Top Right: Live Leaderboard */}
      <div className="absolute top-16 right-4 z-20 w-56 bg-slate-900/85 backdrop-blur-md border border-slate-800/80 rounded-xl p-3 shadow-lg pointer-events-none select-none">
        <div className="flex items-center gap-1.5 text-xs font-bold text-slate-300 border-b border-slate-800 pb-2 mb-2 font-mono">
          <Trophy className="w-3.5 h-3.5 text-amber-400" />
          <span>PLACAR DE LÍDERES</span>
        </div>
        <div className="flex flex-col gap-1 text-xs font-mono">
          {leaderboard.map((s, idx) => {
            const isSelf = s.isPlayer;
            return (
              <div
                key={s.id}
                className={`flex items-center justify-between py-0.5 px-1.5 rounded transition-colors ${
                  isSelf ? 'bg-cyan-500/20 text-cyan-300 font-bold' : 'text-slate-300'
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <span
                    className={`text-[10px] w-4 ${
                      idx === 0
                        ? 'text-amber-400 font-bold'
                        : idx === 1
                        ? 'text-slate-300'
                        : idx === 2
                        ? 'text-amber-600'
                        : 'text-slate-500'
                    }`}
                  >
                    #{idx + 1}
                  </span>
                  <span className="truncate max-w-[110px]">{s.name}</span>
                </div>
                <span className="text-slate-400 tabular-nums text-[11px] font-semibold">
                  {Math.floor(s.mass)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Bottom Center / Left: Player Status Bar */}
      {playerSnake && playerSnake.alive && (
        <div className="absolute bottom-5 left-1/2 -translate-x-1/2 z-20 flex items-center gap-4 bg-slate-900/90 backdrop-blur-md border border-slate-800 px-5 py-2.5 rounded-full shadow-2xl select-none">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Sua Massa:</span>
            <span className="text-lg font-extrabold text-cyan-400 font-mono tabular-nums">
              {Math.floor(playerSnake.mass)}
            </span>
          </div>

          <div className="h-4 w-px bg-slate-700" />

          <div className="flex items-center gap-2">
            <Crosshair className="w-4 h-4 text-red-400" />
            <span className="text-xs text-slate-400">Abates:</span>
            <span className="text-base font-bold text-white font-mono tabular-nums">
              {playerSnake.kills}
            </span>
          </div>

          <div className="h-4 w-px bg-slate-700" />

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Posição:</span>
            <span className="text-base font-bold text-amber-400 font-mono">
              #{playerRank > 0 ? playerRank : '—'}
            </span>
          </div>

          <div className="h-4 w-px bg-slate-700" />

          <div className="flex items-center gap-1.5 text-xs">
            <Zap className={`w-3.5 h-3.5 ${playerSnake.isBoosting ? 'text-amber-400 animate-pulse' : 'text-slate-500'}`} />
            <span className={playerSnake.isBoosting ? 'text-amber-300 font-semibold' : 'text-slate-400'}>
              {playerSnake.isBoosting ? 'Acelerando!' : 'Espaço / Clique: Turbo'}
            </span>
          </div>
        </div>
      )}

      {/* Controls Hint (Bottom Left) */}
      <div className="hidden lg:block absolute bottom-5 left-5 z-20 text-[11px] text-slate-400 bg-slate-900/80 backdrop-blur-sm border border-slate-800/80 px-3 py-2 rounded-lg pointer-events-none select-none">
        <div className="font-semibold text-slate-300 mb-0.5">Controles de Jogo:</div>
        <div>• Mova o mouse para guiar a serpente</div>
        <div>• Segure o botão esquerdo ou [Espaço] para Acelerar</div>
      </div>

      {/* Game Over / Respawn Modal */}
      {isGameOver && (
        <div className="absolute inset-0 z-40 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-sm w-full shadow-2xl text-center flex flex-col items-center gap-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="w-14 h-14 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-400">
              <RotateCcw className="w-7 h-7" />
            </div>

            <div>
              <h2 className="text-xl font-bold text-white font-['Outfit']">Você foi Eliminado!</h2>
              <p className="text-xs text-slate-400 mt-1">
                Sua serpente colidiu com o corpo de um bot inimigo ou com a borda da arena.
              </p>
            </div>

            {lastStats && (
              <div className="w-full grid grid-cols-3 gap-2 bg-slate-950 p-3 rounded-xl border border-slate-800 text-xs">
                <div>
                  <div className="text-slate-400 text-[10px]">Massa Final</div>
                  <div className="text-base font-bold text-cyan-400 font-mono">
                    {Math.floor(lastStats.mass)}
                  </div>
                </div>
                <div>
                  <div className="text-slate-400 text-[10px]">Abates</div>
                  <div className="text-base font-bold text-amber-400 font-mono">
                    {lastStats.kills}
                  </div>
                </div>
                <div>
                  <div className="text-slate-400 text-[10px]">Tempo Vivo</div>
                  <div className="text-base font-bold text-emerald-400 font-mono">
                    {Math.floor(lastStats.timeAlive / 60)}s
                  </div>
                </div>
              </div>
            )}

            <button
              onClick={onRespawn}
              className="w-full py-3 px-4 bg-gradient-to-r from-cyan-500 to-emerald-500 hover:from-cyan-400 hover:to-emerald-400 text-slate-950 font-extrabold rounded-xl shadow-lg shadow-cyan-500/25 transition-all text-sm flex items-center justify-center gap-2"
            >
              <RotateCcw className="w-4 h-4 font-bold" />
              <span>Jogar Novamente</span>
            </button>
          </div>
        </div>
      )}
    </>
  );
};
