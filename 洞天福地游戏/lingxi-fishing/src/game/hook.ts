import { HookState } from './types';
import { HOOK_DROP_SPEED, HOOK_RETRACT_SPEED } from './constants';

export function createHook(x: number, waterLevel: number, canvasHeight: number): HookState {
  return {
    x,
    y: waterLevel,
    depth: 0,
    maxDepth: canvasHeight - 20,
    speed: HOOK_DROP_SPEED,
    isDropping: false,
    hasCatch: false,
  };
}

export function updateHook(hook: HookState, waterLevel: number, spacePressed: boolean, dt: number): void {
  if (hook.hasCatch) {
    // Retracting with a catch - slower
    hook.y -= HOOK_RETRACT_SPEED * 0.7 * dt;
    hook.isDropping = false;
    if (hook.y <= waterLevel) {
      hook.y = waterLevel;
    }
    return;
  }

  if (spacePressed) {
    hook.isDropping = true;
    hook.y += HOOK_DROP_SPEED * dt;
    if (hook.y > hook.maxDepth) {
      hook.y = hook.maxDepth;
    }
  } else {
    hook.isDropping = false;
    hook.y -= HOOK_RETRACT_SPEED * dt;
    if (hook.y <= waterLevel) {
      hook.y = waterLevel;
    }
  }
}

export function isHookAtSurface(hook: HookState, waterLevel: number): boolean {
  return hook.y <= waterLevel + 5;
}

export function getHookDepthRatio(hook: HookState, waterLevel: number, canvasHeight: number): number {
  const maxDepth = canvasHeight - waterLevel;
  if (maxDepth <= 0) return 0;
  const currentDepth = hook.y - waterLevel;
  return Math.max(0, Math.min(1, currentDepth / maxDepth));
}
