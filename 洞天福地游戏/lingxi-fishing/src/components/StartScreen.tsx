import { useState } from 'react';
import { Anchor, Flame, Fish, Play, Sparkles, Waves } from 'lucide-react';
import { prepareFishingRound } from '@/api/dongtian';
import FishIcon from '@/components/FishIcon';
import { FISH_TYPES } from '@/game/constants';
import { useGameStore } from '@/store/gameStore';

const tips = [
  { icon: Anchor, label: '按住空格下钩，松开收回' },
  { icon: Fish, label: '钓起灵鱼后会带回洞天兑换码' },
  { icon: Flame, label: '连续命中会提升连击倍率' },
  { icon: Waves, label: '下潜越深，深度加成越高' },
];

export default function StartScreen() {
  const setGameState = useGameStore((s) => s.setGameState);
  const setGameConfig = useGameStore((s) => s.setGameConfig);
  const setRound = useGameStore((s) => s.setRound);
  const resetGame = useGameStore((s) => s.resetGame);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');

  const handleStart = async () => {
    if (starting) return;
    setStarting(true);
    setStartError('');
    try {
      const prepared = await prepareFishingRound();
      resetGame();
      setGameConfig(prepared.config);
      setRound(prepared.round);
      setGameState('playing');
    } catch (error) {
      setStartError(error instanceof Error ? error.message : '洞天溪口暂时没有回应。');
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="absolute inset-0 z-20 grid overflow-hidden bg-gradient-to-b from-cyan-950/5 via-sky-950/10 to-slate-950/45 px-3 py-[max(0.75rem,env(safe-area-inset-top))] pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      <div className="mx-auto grid h-full min-h-0 w-full max-w-3xl content-center text-center text-white">
        <div className="grid min-h-0 gap-3">
        <div className="space-y-2 md:space-y-3">
          <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full border border-white/35 bg-white/18 shadow-[0_12px_40px_rgba(14,116,144,0.35)] backdrop-blur-md md:h-16 md:w-16">
            <Anchor className="h-6 w-6 text-cyan-100 md:h-8 md:w-8" strokeWidth={2.4} />
          </div>
          <h1
            className="text-4xl font-black leading-none drop-shadow-[0_6px_0_rgba(6,78,100,0.55)] md:text-7xl"
            style={{ fontFamily: '"Fredoka", "Microsoft YaHei", sans-serif' }}
          >
            灵溪垂钓
          </h1>
          <p className="mx-auto max-w-xl text-xs font-semibold leading-snug text-cyan-50/90 md:text-lg">
            90 秒一局，收竿带回洞天兑换码。
          </p>
        </div>

        <div className="mx-auto grid w-full max-w-2xl gap-2 rounded-lg border border-white/25 bg-slate-950/28 p-2.5 text-left shadow-[0_24px_80px_rgba(2,6,23,0.38)] backdrop-blur-md md:grid-cols-[1.08fr_0.92fr] md:gap-4 md:p-5">
          <div className="space-y-2 md:space-y-3">
            <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-[0.18em] text-cyan-100/80">
              <Sparkles className="h-4 w-4" />
              入溪须知
            </div>
            <div className="grid grid-cols-2 gap-1.5 md:grid-cols-1 md:gap-2">
              {tips.map(({ icon: Icon, label }) => (
                <div key={label} className="flex min-h-12 items-center gap-2 rounded-lg border border-white/10 bg-white/10 px-2 py-1.5 md:min-h-11 md:gap-3 md:px-3 md:py-2">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-cyan-200/18 text-cyan-50 md:h-8 md:w-8">
                    <Icon className="h-4 w-4" strokeWidth={2.4} />
                  </span>
                  <span className="text-[11px] font-bold leading-snug text-slate-50 md:text-sm">{label}</span>
                </div>
              ))}
            </div>
            <div className="hidden items-center gap-2 rounded-md border border-white/15 bg-black/18 px-2.5 py-1.5 text-xs font-semibold text-cyan-50/85 md:inline-flex md:px-3 md:py-2">
              <kbd className="rounded bg-white/20 px-2 py-1 font-mono text-[11px] text-white">Space</kbd>
              键盘也可以直接下钩
            </div>
          </div>

          <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-7 md:grid-cols-1 md:gap-2">
            {FISH_TYPES.map((fish) => (
              <div
                key={fish.nameEn}
                className="flex min-h-12 min-w-0 flex-col items-center justify-center rounded-lg border border-white/12 bg-white/12 p-1.5 text-center md:min-h-0 md:flex-row md:justify-between md:px-3 md:py-2"
              >
                <div className="flex flex-col items-center gap-0.5 md:flex-row md:gap-2">
                  <FishIcon fish={fish} width={46} height={28} />
                  <span className="hidden text-[11px] font-bold text-white sm:inline md:text-sm">{fish.name}</span>
                </div>
                <span className="mt-1 text-[10px] font-black text-amber-200 md:mt-0 md:text-sm">{fish.score}</span>
              </div>
            ))}
          </div>
        </div>

        <button
          onClick={handleStart}
          disabled={starting}
          className="mx-auto inline-flex min-h-11 items-center gap-3 rounded-lg bg-gradient-to-r from-amber-300 via-orange-400 to-rose-400 px-7 py-2.5 text-base font-black text-slate-900 shadow-[0_18px_45px_rgba(251,146,60,0.36)] transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_22px_55px_rgba(251,146,60,0.44)] active:translate-y-0 disabled:cursor-wait disabled:opacity-70 md:min-h-14 md:px-10 md:py-4 md:text-lg"
          style={{ fontFamily: '"Fredoka", "Microsoft YaHei", sans-serif' }}
        >
          <Play className="h-5 w-5 fill-slate-900" strokeWidth={2.6} />
          {starting ? '溪口开局中' : '入溪垂钓'}
        </button>
        {startError && (
          <div className="mx-auto max-w-lg rounded-lg border border-rose-100/25 bg-rose-950/34 px-3 py-2 text-sm font-semibold text-rose-50">
            {startError}
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
