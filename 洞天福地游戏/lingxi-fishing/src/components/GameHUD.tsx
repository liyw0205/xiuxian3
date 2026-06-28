import { Clock3, Flame, Trophy } from 'lucide-react';
import { useGameStore } from '@/store/gameStore';

export default function GameHUD() {
  const { score, timeLeft, combo } = useGameStore();

  const minutes = Math.floor(timeLeft / 60);
  const seconds = Math.floor(timeLeft % 60);
  const timeStr = `${minutes}:${seconds.toString().padStart(2, '0')}`;
  const comboMultiplier = combo > 0 ? (1 + (combo - 1) * 0.5).toFixed(1) : '1.0';
  const isUrgent = timeLeft <= 10;

  return (
    <div className="pointer-events-none absolute left-0 right-0 top-0 z-10 flex items-start justify-between gap-2 px-3 py-3 text-white md:px-6 md:py-4">
      <div className="flex min-w-[112px] items-center gap-2 rounded-lg border border-white/20 bg-slate-950/32 px-3 py-2 shadow-[0_12px_35px_rgba(2,6,23,0.22)] backdrop-blur-md md:min-w-[152px] md:px-4">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-amber-300/20 text-amber-200">
          <Trophy className="h-4 w-4" strokeWidth={2.5} />
        </span>
        <div className="min-w-0">
          <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-amber-100/75">分数</div>
          <div className="tabular-nums text-xl font-black leading-tight md:text-2xl">{score}</div>
        </div>
      </div>

      <div className="flex flex-1 justify-center">
        {combo > 0 && (
          <div className="flex items-center gap-2 rounded-full border border-orange-200/30 bg-orange-500/32 px-4 py-2 shadow-[0_12px_35px_rgba(249,115,22,0.2)] backdrop-blur-md">
            <Flame className="h-4 w-4 text-orange-100" fill="currentColor" strokeWidth={2.4} />
            <span className="text-sm font-black md:text-lg">x{comboMultiplier}</span>
            <span className="text-xs font-bold text-orange-100/80">连击 {combo}</span>
          </div>
        )}
      </div>

      <div
        className={`flex min-w-[112px] items-center justify-end gap-2 rounded-lg border px-3 py-2 shadow-[0_12px_35px_rgba(2,6,23,0.22)] backdrop-blur-md md:min-w-[152px] md:px-4 ${
          isUrgent
            ? 'animate-pulse border-red-200/35 bg-red-500/42'
            : 'border-white/20 bg-slate-950/32'
        }`}
      >
        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${isUrgent ? 'bg-red-200/20 text-red-100' : 'bg-cyan-200/18 text-cyan-100'}`}>
          <Clock3 className="h-4 w-4" strokeWidth={2.5} />
        </span>
        <div className="text-right">
          <div className={`text-[10px] font-bold uppercase tracking-[0.18em] ${isUrgent ? 'text-red-100/80' : 'text-cyan-100/75'}`}>
            时间
          </div>
          <div className={`tabular-nums text-xl font-black leading-tight md:text-2xl ${isUrgent ? 'text-red-50' : 'text-white'}`}>
            {timeStr}
          </div>
        </div>
      </div>
    </div>
  );
}
