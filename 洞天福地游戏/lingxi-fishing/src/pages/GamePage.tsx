import { useEffect } from 'react';
import { Anchor } from 'lucide-react';
import GameCanvas from '@/components/GameCanvas';
import GameHUD from '@/components/GameHUD';
import StartScreen from '@/components/StartScreen';
import ResultScreen from '@/components/ResultScreen';
import { useGameStore } from '@/store/gameStore';

export default function GamePage() {
  const { gameState, requestFinish } = useGameStore();

  useEffect(() => {
    const setViewportHeight = () => {
      const height = Math.max(320, Math.round(window.visualViewport?.height ?? window.innerHeight));
      document.documentElement.style.setProperty('--fishing-game-height', `${height}px`);
    };

    setViewportHeight();
    window.addEventListener('resize', setViewportHeight);
    window.addEventListener('orientationchange', setViewportHeight);
    window.visualViewport?.addEventListener('resize', setViewportHeight);
    window.visualViewport?.addEventListener('scroll', setViewportHeight);

    return () => {
      window.removeEventListener('resize', setViewportHeight);
      window.removeEventListener('orientationchange', setViewportHeight);
      window.visualViewport?.removeEventListener('resize', setViewportHeight);
      window.visualViewport?.removeEventListener('scroll', setViewportHeight);
    };
  }, []);

  return (
    <div className="relative h-[var(--fishing-game-height)] min-h-[var(--fishing-game-height)] w-screen max-w-full overflow-hidden overscroll-none bg-sky-950">
      <GameCanvas />

      {gameState === 'playing' && <GameHUD />}
      {gameState === 'idle' && <StartScreen />}
      {gameState === 'ended' && <ResultScreen />}

      {/* Mobile touch control */}
      {gameState === 'playing' && (
        <div className="absolute bottom-0 left-0 right-0 z-10 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] md:hidden">
          <div className="mx-auto grid max-w-md grid-cols-[minmax(0,1fr)_auto] gap-2">
          <button
            className="inline-flex min-h-12 select-none items-center justify-center gap-2 rounded-lg border border-white/25 bg-slate-950/40 px-4 py-3 text-sm font-black text-white shadow-[0_12px_35px_rgba(2,6,23,0.28)] backdrop-blur-md active:scale-[0.99] active:bg-white/22"
            onTouchStart={(e) => {
              e.preventDefault();
              window.dispatchEvent(new KeyboardEvent('keydown', { code: 'Space' }));
            }}
            onTouchEnd={(e) => {
              e.preventDefault();
              window.dispatchEvent(new KeyboardEvent('keyup', { code: 'Space' }));
            }}
          >
            <Anchor className="h-4 w-4 text-cyan-100" strokeWidth={2.4} />
            按住下钩
          </button>
          <button
            type="button"
            onClick={requestFinish}
            className="inline-flex min-h-12 items-center justify-center rounded-lg border border-white/25 bg-slate-950/40 px-3 py-3 text-xs font-black text-white shadow-[0_12px_35px_rgba(2,6,23,0.28)] backdrop-blur-md active:scale-[0.99] active:bg-white/22"
          >
            收竿
          </button>
          </div>
        </div>
      )}
    </div>
  );
}
