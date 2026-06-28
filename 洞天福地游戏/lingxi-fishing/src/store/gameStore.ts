import { create } from 'zustand';
import { GameState, CaughtFishRecord } from '@/game/types';
import type { FishingGameConfig, FishingRoundStart } from '@/api/dongtian';

interface GameStore {
  gameState: GameState;
  score: number;
  timeLeft: number;
  combo: number;
  caughtFish: CaughtFishRecord[];
  lastCatchScore: number;
  lastCatchCombo: number;
  gameToken: string;
  gameTokenExpiresAt: string;
  sessionId: string;
  roundToken: string;
  roundExpiresAt: string;

  setGameState: (state: GameState) => void;
  setScore: (score: number) => void;
  setTimeLeft: (time: number) => void;
  addCombo: () => void;
  resetCombo: () => void;
  addCaughtFish: (record: CaughtFishRecord) => void;
  setLastCatch: (score: number, combo: number) => void;
  setGameConfig: (config: FishingGameConfig) => void;
  setRound: (round: FishingRoundStart) => void;
  clearRound: () => void;
  resetGame: () => void;
}

export const useGameStore = create<GameStore>((set) => ({
  gameState: 'idle',
  score: 0,
  timeLeft: 90,
  combo: 0,
  caughtFish: [],
  lastCatchScore: 0,
  lastCatchCombo: 0,
  gameToken: '',
  gameTokenExpiresAt: '',
  sessionId: '',
  roundToken: '',
  roundExpiresAt: '',

  setGameState: (gameState) => set({ gameState }),
  setScore: (score) => set({ score }),
  setTimeLeft: (timeLeft) => set({ timeLeft }),
  addCombo: () => set((s) => ({ combo: s.combo + 1 })),
  resetCombo: () => set({ combo: 0 }),
  addCaughtFish: (record) =>
    set((s) => ({ caughtFish: [...s.caughtFish, record] })),
  setLastCatch: (score, combo) => set({ lastCatchScore: score, lastCatchCombo: combo }),
  setGameConfig: (config) =>
    set({
      gameToken: config.game_token,
      gameTokenExpiresAt: config.token_expires_at,
    }),
  setRound: (round) =>
    set({
      sessionId: round.session_id,
      roundToken: round.round_token,
      roundExpiresAt: round.expires_at,
    }),
  clearRound: () => set({ sessionId: '', roundToken: '', roundExpiresAt: '' }),
  resetGame: () =>
    set((s) => ({
      gameState: 'idle',
      score: 0,
      timeLeft: 90,
      combo: 0,
      caughtFish: [],
      lastCatchScore: 0,
      lastCatchCombo: 0,
      sessionId: '',
      roundToken: '',
      roundExpiresAt: '',
      gameToken: s.gameToken,
      gameTokenExpiresAt: s.gameTokenExpiresAt,
    })),
}));
