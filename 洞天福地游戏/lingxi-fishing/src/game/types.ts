export type GameState = 'idle' | 'playing' | 'ended';

export interface FishType {
  name: string;
  nameEn: string;
  radius: number;
  width: number;
  height: number;
  speedMin: number;
  speedMax: number;
  score: number;
  color: string;
  bodyColor: string;
  finColor: string;
  spawnWeight: number;
  waveAmplitude: number;
  waveFrequency: number;
  depthMin: number; // 0-1, 深度范围最小值（相对水深比例）
  depthMax: number; // 0-1, 深度范围最大值
  glow?: boolean;
}

export interface Fish {
  id: number;
  type: FishType;
  x: number;
  y: number;
  speed: number;
  direction: 1 | -1;
  waveOffset: number;
  alive: boolean;
  caught: boolean;
  tailPhase: number;
}

export interface HookState {
  x: number;
  y: number;
  depth: number;
  maxDepth: number;
  speed: number;
  isDropping: boolean;
  hasCatch: Fish | false;
}

export interface Bubble {
  x: number;
  y: number;
  radius: number;
  speed: number;
  opacity: number;
}

export interface Seaweed {
  x: number;
  height: number;
  phase: number;
  color: string;
}

export interface ScorePopup {
  x: number;
  y: number;
  score: number;
  combo: number;
  depthBonus: number;
  opacity: number;
  offsetY: number;
  createdAt: number;
}

export interface GameScene {
  fishes: Fish[];
  hook: HookState;
  bubbles: Bubble[];
  seaweeds: Seaweed[];
  scorePopups: ScorePopup[];
  waterLevel: number;
  canvasWidth: number;
  canvasHeight: number;
  gameTime: number;
  nextFishSpawn: number;
}

export interface CaughtFishRecord {
  typeName: string;
  typeNameEn: string;
  score: number;
  timestamp: number;
}
