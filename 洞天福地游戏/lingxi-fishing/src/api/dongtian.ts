import type { CaughtFishRecord } from '@/game/types';

export interface FishingGameConfig {
  game_key: string;
  game_title: string;
  game_token: string;
  token_expires_at: string;
  config: {
    game_duration?: number;
    score_cap?: number;
    fish_count_cap?: number;
    round_ttl_minutes?: number;
    round_min_seconds?: number;
  };
}

export interface FishingRoundStart {
  game_key: string;
  session_id: string;
  round_token: string;
  issued_at: string;
  expires_at: string;
}

export interface FishingSessionPayload {
  gameToken: string;
  sessionId: string;
  roundToken: string;
}

export interface PreparedFishingRound {
  config: FishingGameConfig;
  round: FishingRoundStart;
}

export interface DongtianRewardPreview {
  type: string;
  key?: string;
  quantity: number;
}

export interface FishingFinishResponse {
  code: string;
  game_key: string;
  game_title: string;
  expires_at: string;
  rewards: DongtianRewardPreview[];
  reward_preview?: string[];
  accepted_score?: number;
  caught_count?: number;
  message?: string;
}

export interface FishingFinishError {
  detail?: string;
}

type FishingRoute = 'config' | 'start' | 'finish';

function endpoint(route: FishingRoute) {
  const apiPath = `/xiuxian/dongtian/lingxi-fishing/${route}`;
  const path = window.location.pathname;
  const marker = '/static/dongtian/';
  if (path.includes(marker)) {
    return apiPath;
  }
  const base = (import.meta.env.VITE_XIUXIAN_API_BASE || 'http://127.0.0.1:8443').replace(/\/+$/, '');
  return `${base}${apiPath}`;
}

export async function getFishingConfig(): Promise<FishingGameConfig> {
  return fetchJson<FishingGameConfig>(endpoint('config'));
}

export async function startFishingRound(gameToken: string): Promise<FishingRoundStart> {
  return fetchJson<FishingRoundStart>(endpoint('start'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ gameToken }),
  });
}

export async function prepareFishingRound(): Promise<PreparedFishingRound> {
  const config = await getFishingConfig();
  const round = await startFishingRound(config.game_token);
  return { config, round };
}

export async function submitFishingResult(
  score: number,
  caughtFish: CaughtFishRecord[],
  session: FishingSessionPayload
): Promise<FishingFinishResponse> {
  if (!session.gameToken || !session.sessionId || !session.roundToken) {
    throw new Error('本局凭证缺失，请回主页重新开局。');
  }
  const payload = {
    gameToken: session.gameToken,
    sessionId: session.sessionId,
    roundToken: session.roundToken,
    score: Math.max(0, Math.floor(score || 0)),
    caughtFish: caughtFish.map((fish) => ({
      typeName: fish.typeName,
      typeNameEn: fish.typeNameEn,
      score: Math.max(0, Math.floor(fish.score || 0)),
      timestamp: fish.timestamp,
    })),
  };

  return fetchJson<FishingFinishResponse>(endpoint('finish'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = '洞天溪口暂时没有回应。';
    try {
      const error = (await response.json()) as FishingFinishError;
      detail = error.detail || detail;
    } catch {
      // Keep the generic message when the backend returns non-JSON text.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}
