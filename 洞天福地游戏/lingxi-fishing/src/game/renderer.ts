import { GameScene, Fish, Bubble, Seaweed } from './types';
import { COLORS, HOOK_X_RATIO } from './constants';

export function render(ctx: CanvasRenderingContext2D, scene: GameScene): void {
  const { canvasWidth: W, canvasHeight: H, waterLevel: WL } = scene;

  ctx.clearRect(0, 0, W, H);

  drawSky(ctx, W, WL);
  drawSun(ctx, W, WL, scene.gameTime);
  drawClouds(ctx, W, WL, scene.gameTime);
  drawDistantIslands(ctx, W, WL);
  drawWater(ctx, W, H, WL);
  drawUnderwaterTexture(ctx, W, H, WL, scene.gameTime);
  drawLightRays(ctx, W, H, WL, scene.gameTime);
  drawSandBottom(ctx, W, H, scene.gameTime);
  drawReefDetails(ctx, W, H);
  drawSeaweeds(ctx, scene.seaweeds, H);
  drawBubbles(ctx, scene.bubbles);
  drawFishes(ctx, scene.fishes);
  drawFishingLine(ctx, scene);
  drawWaterSurface(ctx, W, WL, scene.gameTime);
  drawPier(ctx, W, WL);
  drawScorePopups(ctx, scene);
  drawVignette(ctx, W, H);
}

function drawSky(ctx: CanvasRenderingContext2D, W: number, WL: number): void {
  const grad = ctx.createLinearGradient(0, 0, 0, WL);
  grad.addColorStop(0, COLORS.skyTop);
  grad.addColorStop(0.55, COLORS.skyMid);
  grad.addColorStop(1, COLORS.skyBottom);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, WL);

  const glow = ctx.createRadialGradient(W * 0.78, WL * 0.75, 10, W * 0.78, WL * 0.75, W * 0.38);
  glow.addColorStop(0, COLORS.horizonGlow);
  glow.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, W, WL);
}

function drawSun(ctx: CanvasRenderingContext2D, W: number, WL: number, time: number): void {
  const x = W * 0.82;
  const y = Math.max(46, WL * 0.34);
  const pulse = Math.sin(time * 0.7) * 2;
  const halo = ctx.createRadialGradient(x, y, 8, x, y, 74 + pulse);
  halo.addColorStop(0, 'rgba(255,255,255,0.95)');
  halo.addColorStop(0.26, COLORS.sunCore);
  halo.addColorStop(0.56, 'rgba(255,231,136,0.38)');
  halo.addColorStop(1, 'rgba(255,231,136,0)');
  ctx.fillStyle = halo;
  ctx.beginPath();
  ctx.arc(x, y, 76 + pulse, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = COLORS.sunColor;
  ctx.beginPath();
  ctx.arc(x, y, 30 + pulse * 0.3, 0, Math.PI * 2);
  ctx.fill();
}

function drawClouds(ctx: CanvasRenderingContext2D, W: number, WL: number, time: number): void {
  const clouds = [
    { x: 96, y: WL * 0.26, s: 1.05, speed: 7 },
    { x: 346, y: WL * 0.39, s: 0.72, speed: 5 },
    { x: 628, y: WL * 0.22, s: 0.92, speed: 8 },
    { x: 920, y: WL * 0.46, s: 0.62, speed: 4 },
  ];

  for (const c of clouds) {
    const cx = ((c.x + time * c.speed) % (W + 180)) - 90;
    drawCloud(ctx, cx, c.y, c.s);
  }
}

function drawCloud(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  ctx.save();
  ctx.fillStyle = COLORS.cloudShade;
  roundedBlob(ctx, x + 5 * s, y + 6 * s, s);
  ctx.fillStyle = COLORS.cloudColor;
  roundedBlob(ctx, x, y, s);
  ctx.restore();
}

function roundedBlob(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  ctx.beginPath();
  ctx.arc(x, y, 16 * s, 0, Math.PI * 2);
  ctx.arc(x + 19 * s, y - 8 * s, 22 * s, 0, Math.PI * 2);
  ctx.arc(x + 44 * s, y - 1 * s, 17 * s, 0, Math.PI * 2);
  ctx.arc(x + 22 * s, y + 7 * s, 16 * s, 0, Math.PI * 2);
  ctx.fill();
}

function drawDistantIslands(ctx: CanvasRenderingContext2D, W: number, WL: number): void {
  const y = WL - 13;
  ctx.save();
  ctx.globalAlpha = 0.5;

  const islandGrad = ctx.createLinearGradient(0, y - 38, 0, y + 8);
  islandGrad.addColorStop(0, '#58B48B');
  islandGrad.addColorStop(1, '#237A77');
  ctx.fillStyle = islandGrad;

  ctx.beginPath();
  ctx.moveTo(W * 0.05, y + 6);
  ctx.quadraticCurveTo(W * 0.14, y - 38, W * 0.25, y + 4);
  ctx.quadraticCurveTo(W * 0.34, y - 18, W * 0.42, y + 6);
  ctx.lineTo(W * 0.05, y + 6);
  ctx.fill();

  ctx.beginPath();
  ctx.moveTo(W * 0.66, y + 7);
  ctx.quadraticCurveTo(W * 0.74, y - 28, W * 0.82, y + 5);
  ctx.quadraticCurveTo(W * 0.88, y - 14, W * 0.96, y + 7);
  ctx.lineTo(W * 0.66, y + 7);
  ctx.fill();

  ctx.restore();
}

function drawWater(ctx: CanvasRenderingContext2D, W: number, H: number, WL: number): void {
  const grad = ctx.createLinearGradient(0, WL, 0, H);
  grad.addColorStop(0, COLORS.waterTop);
  grad.addColorStop(0.35, COLORS.waterMid);
  grad.addColorStop(0.72, COLORS.waterDeep);
  grad.addColorStop(1, COLORS.waterBottom);
  ctx.fillStyle = grad;
  ctx.fillRect(0, WL, W, H - WL);
}

function drawUnderwaterTexture(
  ctx: CanvasRenderingContext2D,
  W: number,
  H: number,
  WL: number,
  time: number
): void {
  ctx.save();

  ctx.globalAlpha = 0.08;
  ctx.strokeStyle = '#B8F7FF';
  ctx.lineWidth = 1;
  for (let y = WL + 34; y < H - 28; y += 42) {
    ctx.beginPath();
    for (let x = 0; x <= W; x += 14) {
      const wave = Math.sin(x * 0.024 + time * 1.4 + y * 0.01) * 5;
      if (x === 0) ctx.moveTo(x, y + wave);
      else ctx.lineTo(x, y + wave);
    }
    ctx.stroke();
  }

  ctx.globalAlpha = 0.13;
  ctx.fillStyle = '#D7FCFF';
  for (let i = 0; i < 30; i++) {
    const x = ((i * 97 + time * 9) % (W + 40)) - 20;
    const y = WL + 24 + ((i * 53 + time * 17) % Math.max(1, H - WL - 90));
    const r = 0.8 + (i % 4) * 0.35;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();
}

function drawLightRays(ctx: CanvasRenderingContext2D, W: number, H: number, WL: number, time: number): void {
  ctx.save();
  ctx.globalCompositeOperation = 'screen';
  for (let i = 0; i < 6; i++) {
    const x = W * (0.08 + i * 0.17);
    const sway = Math.sin(time * 0.45 + i * 1.7) * 24;
    const ray = ctx.createLinearGradient(x + sway, WL, x + sway, H);
    ray.addColorStop(0, 'rgba(255,255,255,0.16)');
    ray.addColorStop(0.48, 'rgba(255,255,255,0.035)');
    ray.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = ray;
    ctx.beginPath();
    ctx.moveTo(x + sway - 16, WL + 4);
    ctx.lineTo(x + sway + 22, WL + 4);
    ctx.lineTo(x + sway + 76 + i * 7, H);
    ctx.lineTo(x + sway - 70 - i * 4, H);
    ctx.closePath();
    ctx.fill();
  }
  ctx.restore();
}

function drawSandBottom(ctx: CanvasRenderingContext2D, W: number, H: number, time: number): void {
  const top = H - 42;
  const grad = ctx.createLinearGradient(0, top, 0, H);
  grad.addColorStop(0, COLORS.sandColor);
  grad.addColorStop(1, COLORS.sandShadow);

  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.moveTo(0, H);
  for (let x = 0; x <= W + 20; x += 24) {
    const y = top + Math.sin(x * 0.022 + time * 0.24) * 7 + Math.sin(x * 0.061) * 3;
    ctx.lineTo(x, y);
  }
  ctx.lineTo(W, H);
  ctx.closePath();
  ctx.fill();

  ctx.save();
  ctx.globalAlpha = 0.16;
  ctx.strokeStyle = '#7C5422';
  ctx.lineWidth = 1;
  for (let x = 18; x < W; x += 70) {
    const y = H - 22 - Math.sin(x * 0.08) * 4;
    ctx.beginPath();
    ctx.ellipse(x, y, 16, 3, -0.18, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
}

function drawReefDetails(ctx: CanvasRenderingContext2D, W: number, H: number): void {
  const baseY = H - 28;
  const reefs = [
    { x: W * 0.1, s: 0.9, c: COLORS.coralPink },
    { x: W * 0.78, s: 1.1, c: COLORS.coralOrange },
    { x: W * 0.9, s: 0.74, c: COLORS.coralPink },
  ];

  for (const reef of reefs) {
    ctx.save();
    ctx.translate(reef.x, baseY);
    ctx.scale(reef.s, reef.s);
    ctx.strokeStyle = reef.c;
    ctx.lineWidth = 4;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(0, -28);
    ctx.moveTo(0, -14);
    ctx.lineTo(-12, -24);
    ctx.moveTo(0, -18);
    ctx.lineTo(13, -32);
    ctx.stroke();
    ctx.restore();
  }

  drawShell(ctx, W * 0.18, H - 17, 0.86);
  drawShell(ctx, W * 0.62, H - 16, 0.7);
  drawRock(ctx, W * 0.3, H - 15, 1.2);
  drawRock(ctx, W * 0.52, H - 14, 0.82);
}

function drawShell(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(s, s);
  ctx.fillStyle = COLORS.shellColor;
  ctx.strokeStyle = 'rgba(126, 87, 42, 0.25)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.ellipse(0, 0, 14, 8, 0, Math.PI, 0);
  ctx.lineTo(14, 0);
  ctx.closePath();
  ctx.fill();
  for (let i = -2; i <= 2; i++) {
    ctx.beginPath();
    ctx.moveTo(0, -8);
    ctx.lineTo(i * 5, 0);
    ctx.stroke();
  }
  ctx.restore();
}

function drawRock(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(s, s);
  const grad = ctx.createLinearGradient(-18, -14, 14, 8);
  grad.addColorStop(0, '#8BA1A0');
  grad.addColorStop(1, '#4D6A70');
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.moveTo(-20, 2);
  ctx.quadraticCurveTo(-12, -16, 5, -12);
  ctx.quadraticCurveTo(20, -7, 18, 4);
  ctx.lineTo(-20, 4);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function drawSeaweeds(ctx: CanvasRenderingContext2D, seaweeds: Seaweed[], H: number): void {
  for (const sw of seaweeds) {
    const baseY = H - 19;
    const sway = Math.sin(sw.phase) * 12;

    ctx.save();
    ctx.strokeStyle = sw.color;
    ctx.lineWidth = 4;
    ctx.lineCap = 'round';
    ctx.shadowColor = 'rgba(5, 55, 47, 0.25)';
    ctx.shadowBlur = 5;
    ctx.beginPath();
    ctx.moveTo(sw.x, baseY);
    ctx.bezierCurveTo(
      sw.x + sway * 0.18,
      baseY - sw.height * 0.28,
      sw.x + sway * 0.8,
      baseY - sw.height * 0.58,
      sw.x + sway * 1.35,
      baseY - sw.height
    );
    ctx.stroke();

    ctx.shadowBlur = 0;
    ctx.fillStyle = sw.color;
    for (let j = 0.25; j <= 0.86; j += 0.2) {
      const lx = sw.x + sway * j;
      const ly = baseY - sw.height * j;
      const side = j % 0.4 < 0.2 ? 1 : -1;
      ctx.beginPath();
      ctx.ellipse(lx + side * 9, ly, 9, 3.8, side * 0.55, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }
}

function drawBubbles(ctx: CanvasRenderingContext2D, bubbles: Bubble[]): void {
  for (const b of bubbles) {
    ctx.save();
    ctx.globalAlpha = b.opacity;
    const grad = ctx.createRadialGradient(
      b.x - b.radius * 0.35,
      b.y - b.radius * 0.35,
      1,
      b.x,
      b.y,
      b.radius
    );
    grad.addColorStop(0, 'rgba(255,255,255,0.92)');
    grad.addColorStop(0.35, 'rgba(255,255,255,0.25)');
    grad.addColorStop(1, 'rgba(255,255,255,0.05)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(b.x, b.y, b.radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.48)';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.restore();
  }
}

function drawFishShape(ctx: CanvasRenderingContext2D, fish: Fish): void {
  const { x, y, type, direction, tailPhase } = fish;
  const w = type.width;
  const h = type.height;
  const tailWag = Math.sin(tailPhase) * 6;

  ctx.save();
  ctx.translate(x, y);
  ctx.scale(direction, 1);

  if (type.glow) {
    ctx.shadowColor = '#FFE56E';
    ctx.shadowBlur = 18 + Math.sin(tailPhase) * 5;
  } else {
    ctx.shadowColor = 'rgba(0, 20, 45, 0.26)';
    ctx.shadowBlur = 8;
    ctx.shadowOffsetY = 3;
  }

  drawTail(ctx, w, h, tailWag, type.finColor);
  drawFins(ctx, w, h, type.finColor, tailWag);
  drawFishBody(ctx, w, h, type.bodyColor, type.nameEn);
  drawFishDetails(ctx, w, h, type.nameEn, type.finColor);

  ctx.restore();
}

function drawTail(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  tailWag: number,
  color: string
): void {
  ctx.fillStyle = color;
  ctx.strokeStyle = 'rgba(255,255,255,0.24)';
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(-w / 2 + 2, 0);
  ctx.quadraticCurveTo(-w / 2 - 18, -h * 0.72 + tailWag, -w / 2 - 14, 0);
  ctx.quadraticCurveTo(-w / 2 - 18, h * 0.72 + tailWag, -w / 2 + 2, 0);
  ctx.fill();
  ctx.stroke();
}

function drawFins(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  color: string,
  tailWag: number
): void {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(-w * 0.12, -h / 2 + 2);
  ctx.quadraticCurveTo(w * 0.08, -h / 2 - 12, w * 0.24, -h / 2 + 3);
  ctx.closePath();
  ctx.fill();

  ctx.globalAlpha = 0.86;
  ctx.beginPath();
  ctx.moveTo(-w * 0.05, h * 0.18);
  ctx.quadraticCurveTo(w * 0.09, h * 0.58 + tailWag * 0.15, w * 0.22, h * 0.22);
  ctx.quadraticCurveTo(w * 0.1, h * 0.14, -w * 0.05, h * 0.18);
  ctx.fill();
  ctx.globalAlpha = 1;
}

function drawFishBody(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  bodyColor: string,
  nameEn: string
): void {
  const bodyGrad = ctx.createLinearGradient(-w / 2, -h / 2, w / 2, h / 2);
  bodyGrad.addColorStop(0, shadeColor(bodyColor, -14));
  bodyGrad.addColorStop(0.42, bodyColor);
  bodyGrad.addColorStop(1, shadeColor(bodyColor, 18));
  ctx.fillStyle = bodyGrad;

  ctx.beginPath();
  if (nameEn === 'shark') {
    ctx.moveTo(-w / 2, 0);
    ctx.quadraticCurveTo(-w * 0.18, -h * 0.62, w * 0.48, -h * 0.22);
    ctx.quadraticCurveTo(w * 0.64, 0, w * 0.48, h * 0.2);
    ctx.quadraticCurveTo(-w * 0.18, h * 0.62, -w / 2, 0);
  } else if (nameEn === 'pufferfish') {
    ctx.arc(0, 0, h * 0.58, 0, Math.PI * 2);
  } else {
    ctx.ellipse(0, 0, w / 2, h / 2, 0, 0, Math.PI * 2);
  }
  ctx.fill();

  ctx.strokeStyle = 'rgba(255,255,255,0.28)';
  ctx.lineWidth = 1.3;
  ctx.stroke();

  ctx.globalAlpha = 0.18;
  ctx.fillStyle = '#FFFFFF';
  ctx.beginPath();
  ctx.ellipse(w * 0.1, -h * 0.2, w * 0.28, h * 0.15, -0.12, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
}

function drawFishDetails(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  nameEn: string,
  finColor: string
): void {
  if (nameEn === 'clownfish') {
    drawClownfishStripes(ctx, w, h);
  }

  if (nameEn === 'pufferfish') {
    drawPufferfishSpots(ctx, h);
  }

  if (nameEn === 'swordfish') {
    ctx.fillStyle = finColor;
    ctx.beginPath();
    ctx.moveTo(w / 2 - 2, 0);
    ctx.lineTo(w / 2 + 25, -2);
    ctx.lineTo(w / 2 + 25, 2);
    ctx.closePath();
    ctx.fill();
  }

  if (nameEn === 'goldenDragon') {
    ctx.strokeStyle = 'rgba(255,255,255,0.42)';
    ctx.lineWidth = 1;
    for (let i = -2; i <= 2; i++) {
      ctx.beginPath();
      ctx.arc(i * 8, 0, 4, -0.5, Math.PI + 0.5);
      ctx.stroke();
    }
  }

  ctx.fillStyle = '#FFFFFF';
  ctx.beginPath();
  ctx.arc(w / 4, -h / 7, Math.max(3.3, h * 0.18), 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#08233A';
  ctx.beginPath();
  ctx.arc(w / 4 + 1.2, -h / 7, Math.max(1.8, h * 0.09), 0, Math.PI * 2);
  ctx.fill();
}

function drawClownfishStripes(ctx: CanvasRenderingContext2D, w: number, h: number): void {
  ctx.save();
  ctx.strokeStyle = '#FFFFFF';
  ctx.lineWidth = 5;
  ctx.lineCap = 'round';
  for (const x of [-w * 0.12, w * 0.22]) {
    ctx.beginPath();
    ctx.moveTo(x, -h * 0.43);
    ctx.lineTo(x + 2, h * 0.43);
    ctx.stroke();
  }
  ctx.strokeStyle = 'rgba(24,31,45,0.45)';
  ctx.lineWidth = 1.3;
  for (const x of [-w * 0.12, w * 0.22]) {
    ctx.beginPath();
    ctx.moveTo(x - 3, -h * 0.42);
    ctx.lineTo(x - 1, h * 0.42);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x + 4, -h * 0.42);
    ctx.lineTo(x + 6, h * 0.42);
    ctx.stroke();
  }
  ctx.restore();
}

function drawPufferfishSpots(ctx: CanvasRenderingContext2D, h: number): void {
  ctx.fillStyle = 'rgba(255,255,255,0.45)';
  const spots = [
    [-7, -4, 2.2],
    [6, 3, 2.1],
    [-2, 7, 1.8],
    [3, -8, 1.6],
  ];
  for (const [x, y, r] of spots) {
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.strokeStyle = 'rgba(255,255,255,0.32)';
  ctx.lineWidth = 1;
  for (let a = 0; a < Math.PI * 2; a += Math.PI / 5) {
    ctx.beginPath();
    ctx.moveTo(Math.cos(a) * h * 0.52, Math.sin(a) * h * 0.52);
    ctx.lineTo(Math.cos(a) * h * 0.68, Math.sin(a) * h * 0.68);
    ctx.stroke();
  }
}

function drawFishes(ctx: CanvasRenderingContext2D, fishes: Fish[]): void {
  for (const fish of fishes) {
    if (fish.alive) {
      drawFishShape(ctx, fish);
    }
  }
}

function drawFishingLine(ctx: CanvasRenderingContext2D, scene: GameScene): void {
  const { hook, waterLevel } = scene;
  const startX = hook.x;
  const startY = waterLevel - 34;
  const endX = hook.x;
  const endY = hook.y;

  ctx.save();

  ctx.strokeStyle = 'rgba(28, 52, 65, 0.28)';
  ctx.lineWidth = 3.2;
  ctx.beginPath();
  ctx.moveTo(startX + 1.5, startY);
  ctx.lineTo(endX + 1.5, endY);
  ctx.stroke();

  ctx.strokeStyle = COLORS.lineColor;
  ctx.lineWidth = 1.7;
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.moveTo(startX, startY);
  ctx.lineTo(endX, endY);
  ctx.stroke();

  ctx.strokeStyle = COLORS.hookShadow;
  ctx.lineWidth = 4.2;
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(endX, endY);
  ctx.lineTo(endX, endY + 10);
  ctx.arc(endX + 5, endY + 10, 5, Math.PI, 0, true);
  ctx.lineTo(endX + 10, endY + 5);
  ctx.stroke();

  ctx.strokeStyle = COLORS.hookColor;
  ctx.lineWidth = 2.4;
  ctx.beginPath();
  ctx.moveTo(endX, endY);
  ctx.lineTo(endX, endY + 10);
  ctx.arc(endX + 5, endY + 10, 5, Math.PI, 0, true);
  ctx.lineTo(endX + 10, endY + 5);
  ctx.stroke();

  ctx.fillStyle = COLORS.hookColor;
  ctx.beginPath();
  ctx.arc(endX + 10, endY + 4, 1.7, 0, Math.PI * 2);
  ctx.fill();

  ctx.restore();
}

function drawWaterSurface(ctx: CanvasRenderingContext2D, W: number, WL: number, time: number): void {
  ctx.save();

  const foam = ctx.createLinearGradient(0, WL - 8, 0, WL + 12);
  foam.addColorStop(0, 'rgba(255,255,255,0)');
  foam.addColorStop(0.5, 'rgba(255,255,255,0.24)');
  foam.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = foam;
  ctx.fillRect(0, WL - 8, W, 20);

  ctx.strokeStyle = 'rgba(255,255,255,0.72)';
  ctx.lineWidth = 2;
  drawWaveLine(ctx, W, WL, time, 3.8, 0.032, 2.1);
  ctx.strokeStyle = 'rgba(186,245,255,0.58)';
  ctx.lineWidth = 1.2;
  drawWaveLine(ctx, W, WL + 7, time, 2.6, 0.05, 2.7);

  ctx.restore();
}

function drawWaveLine(
  ctx: CanvasRenderingContext2D,
  W: number,
  yBase: number,
  time: number,
  amp: number,
  freq: number,
  speed: number
): void {
  ctx.beginPath();
  for (let x = 0; x <= W; x += 4) {
    const y = yBase + Math.sin(x * freq + time * speed) * amp + Math.sin(x * 0.011 + time * 1.3) * 2;
    if (x === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

function drawPier(ctx: CanvasRenderingContext2D, W: number, WL: number): void {
  const pierX = W * 0.26;
  const pierW = Math.max(110, W * 0.16);
  const pierTop = WL - 28;

  ctx.save();

  ctx.fillStyle = 'rgba(15,36,41,0.18)';
  ctx.beginPath();
  ctx.ellipse(pierX + pierW * 0.5, WL + 8, pierW * 0.6, 8, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = COLORS.pierDark;
  for (const x of [pierX + 12, pierX + pierW - 18]) {
    ctx.fillRect(x, pierTop - 1, 8, 44);
    ctx.fillStyle = 'rgba(255,255,255,0.12)';
    ctx.fillRect(x + 1, pierTop, 2, 43);
    ctx.fillStyle = COLORS.pierDark;
  }

  const platformGrad = ctx.createLinearGradient(0, pierTop - 9, 0, pierTop + 8);
  platformGrad.addColorStop(0, COLORS.pierLight);
  platformGrad.addColorStop(1, COLORS.pierColor);
  ctx.fillStyle = platformGrad;
  roundRect(ctx, pierX - 10, pierTop - 9, pierW + 20, 18, 6);
  ctx.fill();

  ctx.strokeStyle = COLORS.pierDark;
  ctx.lineWidth = 1.2;
  for (let i = 0; i < 6; i++) {
    const lx = pierX - 2 + i * (pierW / 5);
    ctx.beginPath();
    ctx.moveTo(lx, pierTop - 8);
    ctx.lineTo(lx + 3, pierTop + 8);
    ctx.stroke();
  }

  const rodBaseX = pierX + pierW * 0.48;
  const rodTipX = W * HOOK_X_RATIO;
  ctx.strokeStyle = '#4A2C18';
  ctx.lineWidth = 4;
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(rodBaseX, pierTop - 8);
  ctx.quadraticCurveTo(rodBaseX + 28, pierTop - 64, rodTipX, pierTop - 44);
  ctx.stroke();

  ctx.strokeStyle = '#D2A067';
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.moveTo(rodBaseX + 4, pierTop - 16);
  ctx.quadraticCurveTo(rodBaseX + 30, pierTop - 58, rodTipX - 4, pierTop - 43);
  ctx.stroke();

  drawFisher(ctx, rodBaseX, pierTop - 13);
  ctx.restore();
}

function drawFisher(ctx: CanvasRenderingContext2D, x: number, y: number): void {
  ctx.fillStyle = '#F0B27A';
  ctx.beginPath();
  ctx.arc(x, y - 15, 6, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = '#FFCA63';
  ctx.beginPath();
  ctx.moveTo(x - 10, y - 19);
  ctx.lineTo(x + 10, y - 19);
  ctx.lineTo(x + 5, y - 25);
  ctx.lineTo(x - 3, y - 25);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = '#2563EB';
  roundRect(ctx, x - 6, y - 10, 12, 14, 4);
  ctx.fill();

  ctx.strokeStyle = '#173B72';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x - 4, y + 2);
  ctx.lineTo(x - 13, y + 10);
  ctx.moveTo(x + 4, y + 2);
  ctx.lineTo(x + 14, y + 8);
  ctx.stroke();
}

function drawScorePopups(ctx: CanvasRenderingContext2D, scene: GameScene): void {
  for (const sp of scene.scorePopups) {
    const y = sp.y - sp.offsetY;
    ctx.save();
    ctx.globalAlpha = sp.opacity;
    ctx.textAlign = 'center';
    ctx.font = '800 24px "Fredoka", "Microsoft YaHei", sans-serif';

    const text = `+${sp.score}`;
    ctx.lineWidth = 5;
    ctx.strokeStyle = 'rgba(8, 25, 55, 0.78)';
    ctx.strokeText(text, sp.x, y);
    ctx.fillStyle = '#FFE66D';
    ctx.fillText(text, sp.x, y);

    if (sp.combo > 1) {
      ctx.font = '800 15px "Fredoka", "Microsoft YaHei", sans-serif';
      ctx.fillStyle = '#FF9F1C';
      const comboText = `x${(1 + (sp.combo - 1) * 0.5).toFixed(1)} 连击`;
      ctx.strokeText(comboText, sp.x, y + 23);
      ctx.fillText(comboText, sp.x, y + 23);
    }

    if (sp.depthBonus > 0) {
      ctx.font = '700 13px "Fredoka", "Microsoft YaHei", sans-serif';
      ctx.fillStyle = '#A9F5FF';
      const depthText = `深度 +${sp.depthBonus}`;
      ctx.strokeText(depthText, sp.x, y + 40);
      ctx.fillText(depthText, sp.x, y + 40);
    }

    ctx.restore();
  }
}

function drawVignette(ctx: CanvasRenderingContext2D, W: number, H: number): void {
  const grad = ctx.createRadialGradient(W * 0.5, H * 0.42, H * 0.2, W * 0.5, H * 0.5, H * 0.82);
  grad.addColorStop(0, 'rgba(0,0,0,0)');
  grad.addColorStop(1, 'rgba(1,18,44,0.16)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + w - radius, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
  ctx.lineTo(x + w, y + h - radius);
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
  ctx.lineTo(x + radius, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

function shadeColor(hex: string, amount: number): string {
  const color = hex.replace('#', '');
  const num = parseInt(color.length === 3 ? color.split('').map((c) => c + c).join('') : color, 16);
  const r = clampColor((num >> 16) + amount);
  const g = clampColor(((num >> 8) & 0xff) + amount);
  const b = clampColor((num & 0xff) + amount);
  return `rgb(${r}, ${g}, ${b})`;
}

function clampColor(value: number): number {
  return Math.max(0, Math.min(255, value));
}
