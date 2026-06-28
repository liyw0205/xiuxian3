import { useState } from 'react';
import { Anchor, Flame, Fish, Play, Sparkles, Waves } from 'lucide-react';
import { prepareFishingRound } from '@/api/dongtian';
import { useGameStore } from '@/store/gameStore';

const fishPreview = [
  { emoji: '🐠', name: '赤纹小鱼', score: 10 },
  { emoji: '🐟', name: '青鳞鲫', score: 20 },
  { emoji: '🐡', name: '鼓灵河豚', score: 40 },
  { emoji: '🦈', name: '沧牙鲨', score: 150 },
  { emoji: '🐉', name: '金鳞龙鱼', score: 200 },
];

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
    <div className="absolute inset-0 z-20 overflow-y-auto overscroll-contain bg-gradient-to-b from-cyan-950/5 via-sky-950/10 to-slate-950/45 px-3 py-3 md:py-4">
      <div className="mx-auto flex min-h-full w-full max-w-3xl items-start justify-center py-2 text-center text-white md:items-center md:py-4">
        <div className="w-full">
        <div className="mb-4 space-y-2 md:mb-6 md:space-y-3">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-white/35 bg-white/18 shadow-[0_12px_40px_rgba(14,116,144,0.35)] backdrop-blur-md md:h-16 md:w-16">
            <Anchor className="h-6 w-6 text-cyan-100 md:h-8 md:w-8" strokeWidth={2.4} />
          </div>
          <h1
            className="text-4xl font-black leading-none drop-shadow-[0_6px_0_rgba(6,78,100,0.55)] md:text-7xl"
            style={{ fontFamily: '"Fredoka", "Microsoft YaHei", sans-serif' }}
          >
            灵溪垂钓
          </h1>
          <p className="mx-auto max-w-xl text-sm font-medium text-cyan-50/90 md:text-lg">
            洞天福地开了一条异世灵溪，收竿后可带回十分钟有效的洞天兑换码。
          </p>
        </div>

        <div className="mx-auto grid max-w-2xl gap-3 rounded-lg border border-white/25 bg-slate-950/28 p-3 text-left shadow-[0_24px_80px_rgba(2,6,23,0.38)] backdrop-blur-md md:grid-cols-[1.08fr_0.92fr] md:gap-4 md:p-5">
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-[0.18em] text-cyan-100/80">
              <Sparkles className="h-4 w-4" />
              入溪须知
            </div>
            <div className="grid gap-2">
              {tips.map(({ icon: Icon, label }) => (
                <div key={label} className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/10 px-3 py-2">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-cyan-200/18 text-cyan-50 md:h-8 md:w-8">
                    <Icon className="h-4 w-4" strokeWidth={2.4} />
                  </span>
                  <span className="text-sm font-medium text-slate-50">{label}</span>
                </div>
              ))}
            </div>
            <div className="inline-flex items-center gap-2 rounded-md border border-white/15 bg-black/18 px-3 py-2 text-xs font-semibold text-cyan-50/85">
              <kbd className="rounded bg-white/20 px-2 py-1 font-mono text-[11px] text-white">Space</kbd>
              键盘也可以直接下钩
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5 md:grid-cols-1">
            {fishPreview.map((fish) => (
              <div
                key={fish.name}
                className="flex min-w-0 flex-col items-center justify-center rounded-lg border border-white/12 bg-white/12 p-2 text-center md:flex-row md:justify-between md:px-3"
              >
                <div className="flex flex-col items-center gap-0.5 md:flex-row md:gap-2">
                  <span className="text-xl leading-none md:text-2xl">{fish.emoji}</span>
                  <span className="text-[11px] font-bold text-white md:text-sm">{fish.name}</span>
                </div>
                <span className="mt-1 text-[11px] font-black text-amber-200 md:mt-0 md:text-sm">{fish.score}分</span>
              </div>
            ))}
          </div>
        </div>

        <button
          onClick={handleStart}
          disabled={starting}
          className="mt-4 inline-flex items-center gap-3 rounded-full bg-gradient-to-r from-amber-300 via-orange-400 to-rose-400 px-8 py-3 text-base font-black text-slate-900 shadow-[0_18px_45px_rgba(251,146,60,0.36)] transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_22px_55px_rgba(251,146,60,0.44)] active:translate-y-0 disabled:cursor-wait disabled:opacity-70 md:mt-6 md:px-10 md:py-4 md:text-lg"
          style={{ fontFamily: '"Fredoka", "Microsoft YaHei", sans-serif' }}
        >
          <Play className="h-5 w-5 fill-slate-900" strokeWidth={2.6} />
          {starting ? '溪口开局中' : '入溪垂钓'}
        </button>
        {startError && (
          <div className="mx-auto mt-3 max-w-lg rounded-lg border border-rose-100/25 bg-rose-950/34 px-3 py-2 text-sm font-semibold text-rose-50">
            {startError}
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
