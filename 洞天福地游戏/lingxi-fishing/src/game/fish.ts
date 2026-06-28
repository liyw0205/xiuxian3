import { Fish, FishType, GameScene } from './types';
import {
  FISH_TYPES,
  TOTAL_SPAWN_WEIGHT,
  MAX_FISHES,
  SPEED_INCREASE_PER_SECOND,
} from './constants';

let fishIdCounter = 0;

function pickFishType(): FishType {
  const r = Math.random() * TOTAL_SPAWN_WEIGHT;
  let acc = 0;
  for (const type of FISH_TYPES) {
    acc += type.spawnWeight;
    if (r <= acc) return type;
  }
  return FISH_TYPES[0];
}

export function spawnFish(scene: GameScene): Fish | null {
  if (scene.fishes.length >= MAX_FISHES) return null;

  const type = pickFishType();
  const direction: 1 | -1 = Math.random() < 0.5 ? 1 : -1;
  const speedMultiplier = 1 + scene.gameTime * SPEED_INCREASE_PER_SECOND;
  const baseSpeed = type.speedMin + Math.random() * (type.speedMax - type.speedMin);
  const speed = baseSpeed * speedMultiplier;

  const waterTop = scene.waterLevel;
  const waterBottom = scene.canvasHeight - 40;
  const waterDepth = waterBottom - waterTop;
  const depthMin = waterTop + waterDepth * type.depthMin + type.radius;
  const depthMax = waterTop + waterDepth * type.depthMax - type.radius;
  const y = depthMin + Math.random() * Math.max(0, depthMax - depthMin);

  const x = direction === 1 ? -type.width : scene.canvasWidth + type.width;

  const fish: Fish = {
    id: ++fishIdCounter,
    type,
    x,
    y,
    speed,
    direction,
    waveOffset: Math.random() * Math.PI * 2,
    alive: true,
    caught: false,
    tailPhase: Math.random() * Math.PI * 2,
  };

  return fish;
}

export function updateFish(fish: Fish, dt: number): void {
  if (!fish.alive || fish.caught) return;

  fish.x += fish.speed * fish.direction * dt;
  fish.waveOffset += fish.type.waveFrequency * dt;
  fish.y += Math.sin(fish.waveOffset) * fish.type.waveAmplitude * dt;
  fish.tailPhase += 8 * dt;
}

export function isFishOffScreen(fish: Fish, canvasWidth: number): boolean {
  if (fish.direction === 1 && fish.x > canvasWidth + fish.type.width + 10) return true;
  if (fish.direction === -1 && fish.x < -fish.type.width - 10) return true;
  return false;
}

export function checkHookCollision(
  fish: Fish,
  hookX: number,
  hookY: number,
  hookRadius: number
): boolean {
  if (!fish.alive || fish.caught) return false;
  const dx = fish.x - hookX;
  const dy = fish.y - hookY;
  const dist = Math.sqrt(dx * dx + dy * dy);
  return dist < fish.type.radius + hookRadius;
}
