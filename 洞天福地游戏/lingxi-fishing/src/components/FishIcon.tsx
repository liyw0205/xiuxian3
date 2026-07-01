import { useEffect, useRef } from 'react';
import { drawFishIcon } from '@/game/renderer';
import type { FishType } from '@/game/types';

interface FishIconProps {
  fish: FishType;
  width?: number;
  height?: number;
  className?: string;
}

export default function FishIcon({ fish, width = 54, height = 32, className = '' }: FishIconProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const dpr = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const scale = Math.min(
      (width - 12) / Math.max(1, fish.width + 30),
      (height - 6) / Math.max(1, fish.height + 16)
    );
    drawFishIcon(ctx, fish, width / 2, height / 2, scale, 1, 0.85);
  }, [fish, height, width]);

  return (
    <canvas
      ref={canvasRef}
      className={`block shrink-0 ${className}`}
      role="img"
      aria-label={fish.name}
    />
  );
}
