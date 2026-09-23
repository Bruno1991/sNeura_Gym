import React, { useRef, useEffect, useCallback } from 'react';
import { SlitherEngine } from '../game/engine';
import { Snake } from '../game/types';

interface SlitherCanvasProps {
  engine: SlitherEngine;
  showSensors: boolean;
  onSelectSnake: (snake: Snake) => void;
}

export const SlitherCanvas: React.FC<SlitherCanvasProps> = ({
  engine,
  showSensors,
  onSelectSnake,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const mousePosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const isMouseDownRef = useRef<boolean>(false);
  const cameraRef = useRef<{ x: number; y: number; zoom: number }>({ x: 0, y: 0, zoom: 1 });

  // Handle player inputs
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    mousePosRef.current = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (e.button === 0) {
      isMouseDownRef.current = true;
    }

    // In training/inspector mode, check if user clicked on a snake to select it
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const { x: camX, y: camY, zoom } = cameraRef.current;
    const width = canvas.width;
    const height = canvas.height;

    // Convert screen click to world coordinates
    const worldClickX = (clickX - width / 2) / zoom + camX;
    const worldClickY = (clickY - height / 2) / zoom + camY;

    // Find clicked snake
    for (let i = 0; i < engine.snakes.length; i++) {
      const snake = engine.snakes[i];
      if (!snake.alive) continue;
      const dx = snake.x - worldClickX;
      const dy = snake.y - worldClickY;
      if (dx * dx + dy * dy < (snake.headRadius + 20) * (snake.headRadius + 20)) {
        engine.selectedSnakeId = snake.id;
        onSelectSnake(snake);
        break;
      }
    }
  }, [engine, onSelectSnake]);

  const handleMouseUp = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (e.button === 0) {
      isMouseDownRef.current = false;
    }
  }, []);

  // Keyboard boost support (Spacebar)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        isMouseDownRef.current = true;
      }
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        isMouseDownRef.current = false;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  // Main render & update loop
  useEffect(() => {
    let animationFrameId: number;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Resize canvas
    const handleResize = () => {
      if (!canvas) return;
      canvas.width = canvas.parentElement?.clientWidth || window.innerWidth;
      canvas.height = canvas.parentElement?.clientHeight || window.innerHeight;
    };
    handleResize();
    window.addEventListener('resize', handleResize);

    const render = () => {
      // Step simulation: Maximize throughput without arbitrary presets
      const ticks = engine.isGpuOverdrive && engine.mode === 'TRAINING'
        ? Math.max(engine.simSpeed * 4, engine.adaptiveSubsteps)
        : engine.simSpeed;

      const frameStart = performance.now();
      // Allow up to 12ms per animation frame for physics & neural matrix multiplications
      const maxBudgetMs = 12.0;

      for (let t = 0; t < ticks; t++) {
        let playerAngle: number | undefined;
        let playerBoost = isMouseDownRef.current;

        if (engine.mode === 'PLAYER_VS_AI') {
          const player = engine.snakes.find((s) => s.id === engine.playerSnakeId);
          if (player && player.alive) {
            const width = canvas.width;
            const height = canvas.height;
            const { x: camX, y: camY, zoom } = cameraRef.current;
            const worldMouseX = (mousePosRef.current.x - width / 2) / zoom + camX;
            const worldMouseY = (mousePosRef.current.y - height / 2) / zoom + camY;
            playerAngle = Math.atan2(worldMouseY - player.y, worldMouseX - player.x);
          }
        }

        engine.update(playerAngle, playerBoost);

        // Frame-rate protection: if budget exceeded, stop substepping and render immediately
        if (t > 0 && performance.now() - frameStart > maxBudgetMs) {
          break;
        }
      }

      // Smooth camera interpolation
      const trackedSnake = engine.getTrackedSnake();
      if (trackedSnake && trackedSnake.alive) {
        const targetZoom = Math.max(0.45, Math.min(1.05, 1.0 / (1 + (trackedSnake.mass - 10) * 0.0007)));
        cameraRef.current.x += (trackedSnake.x - cameraRef.current.x) * 0.1;
        cameraRef.current.y += (trackedSnake.y - cameraRef.current.y) * 0.1;
        cameraRef.current.zoom += (targetZoom - cameraRef.current.zoom) * 0.05;
      }

      const { x: camX, y: camY, zoom } = cameraRef.current;
      const width = canvas.width;
      const height = canvas.height;

      // Clear Canvas
      ctx.fillStyle = '#090D16';
      ctx.fillRect(0, 0, width, height);

      ctx.save();
      // Apply Camera Transform
      ctx.translate(width / 2, height / 2);
      ctx.scale(zoom, zoom);
      ctx.translate(-camX, -camY);

      // 1. Draw Grid Pattern inside visible viewport
      const gridSize = 100;
      const viewLeft = camX - width / (2 * zoom);
      const viewRight = camX + width / (2 * zoom);
      const viewTop = camY - height / (2 * zoom);
      const viewBottom = camY + height / (2 * zoom);

      ctx.lineWidth = 1;
      ctx.strokeStyle = 'rgba(30, 41, 59, 0.45)';
      ctx.beginPath();
      const startX = Math.floor(viewLeft / gridSize) * gridSize;
      const endX = Math.ceil(viewRight / gridSize) * gridSize;
      for (let x = startX; x <= endX; x += gridSize) {
        ctx.moveTo(x, viewTop);
        ctx.lineTo(x, viewBottom);
      }
      const startY = Math.floor(viewTop / gridSize) * gridSize;
      const endY = Math.ceil(viewBottom / gridSize) * gridSize;
      for (let y = startY; y <= endY; y += gridSize) {
        ctx.moveTo(viewLeft, y);
        ctx.lineTo(viewRight, y);
      }
      ctx.stroke();

      // 2. Draw Arena Boundary (Glowing Circle)
      ctx.beginPath();
      ctx.arc(0, 0, engine.arenaRadius, 0, Math.PI * 2);
      ctx.lineWidth = 12;
      ctx.strokeStyle = 'rgba(239, 68, 68, 0.4)';
      ctx.stroke();

      ctx.lineWidth = 4;
      ctx.strokeStyle = '#EF4444';
      ctx.stroke();

      // Outside boundary dark vignette
      ctx.lineWidth = 60;
      ctx.strokeStyle = 'rgba(15, 23, 42, 0.9)';
      ctx.stroke();

      // 3. Draw Food Orbs
      for (let i = 0; i < engine.foodOrbs.length; i++) {
        const food = engine.foodOrbs[i];
        // Culling
        if (
          food.x + food.radius < viewLeft ||
          food.x - food.radius > viewRight ||
          food.y + food.radius < viewTop ||
          food.y - food.radius > viewBottom
        ) {
          continue;
        }

        ctx.beginPath();
        ctx.arc(food.x, food.y, food.radius, 0, Math.PI * 2);
        ctx.fillStyle = food.color;
        ctx.shadowColor = food.glowColor;
        ctx.shadowBlur = food.isRemnant ? 12 : 6;
        ctx.fill();
        ctx.shadowBlur = 0; // reset
      }

      // 4. Draw Sensory Rays (if enabled or in inspector mode)
      if (showSensors && trackedSnake && trackedSnake.sensors) {
        for (let r = 0; r < trackedSnake.sensors.length; r++) {
          const ray = trackedSnake.sensors[r];

          // Draw Danger line if obstacle detected
          if (ray.dangerHitPoint && ray.dangerDist < 550) {
            ctx.beginPath();
            ctx.moveTo(trackedSnake.x, trackedSnake.y);
            ctx.lineTo(ray.dangerHitPoint.x, ray.dangerHitPoint.y);
            ctx.lineWidth = 1.5;
            ctx.strokeStyle = 'rgba(239, 68, 68, 0.6)';
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(ray.dangerHitPoint.x, ray.dangerHitPoint.y, 4, 0, Math.PI * 2);
            ctx.fillStyle = '#EF4444';
            ctx.fill();
          }

          // Draw Food line if food detected
          if (ray.foodHitPoint && ray.foodDist < 550) {
            ctx.beginPath();
            ctx.moveTo(trackedSnake.x, trackedSnake.y);
            ctx.lineTo(ray.foodHitPoint.x, ray.foodHitPoint.y);
            ctx.lineWidth = 1.2;
            ctx.strokeStyle = 'rgba(16, 185, 129, 0.5)';
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(ray.foodHitPoint.x, ray.foodHitPoint.y, 3, 0, Math.PI * 2);
            ctx.fillStyle = '#10B981';
            ctx.fill();
          }
        }
      }

      // 5. Draw Snakes (Tail to Head)
      for (let s = 0; s < engine.snakes.length; s++) {
        const snake = engine.snakes[s];
        if (!snake.alive) continue;

        const isTracked = trackedSnake?.id === snake.id;

        // Draw Boost Aura
        if (snake.isBoosting) {
          ctx.beginPath();
          ctx.arc(snake.x, snake.y, snake.headRadius + 8, 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
          ctx.fill();
        }

        // Body Segments
        for (let segIdx = snake.segments.length - 1; segIdx >= 0; segIdx--) {
          const seg = snake.segments[segIdx];
          // Culling
          if (
            seg.x + snake.bodyRadius < viewLeft ||
            seg.x - snake.bodyRadius > viewRight ||
            seg.y + snake.bodyRadius < viewTop ||
            seg.y - snake.bodyRadius > viewBottom
          ) {
            continue;
          }

          const ratio = segIdx / Math.max(1, snake.segments.length);
          const currentRadius = snake.bodyRadius * (0.65 + 0.35 * (1 - ratio * 0.3));

          ctx.beginPath();
          ctx.arc(seg.x, seg.y, currentRadius, 0, Math.PI * 2);
          // Alternating skin pattern
          ctx.fillStyle = segIdx % 2 === 0 ? snake.color : snake.secondaryColor;
          ctx.fill();

          if (isTracked && segIdx % 4 === 0) {
            ctx.lineWidth = 1;
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
            ctx.stroke();
          }
        }

        // Head & Labels Culling (Optimizes 500 bots rendering)
        const isOffscreen = (
          snake.x + snake.headRadius + 30 < viewLeft ||
          snake.x - snake.headRadius - 30 > viewRight ||
          snake.y + snake.headRadius + 30 < viewTop ||
          snake.y - snake.headRadius - 30 > viewBottom
        );
        if (isOffscreen && !isTracked) continue;

        // Head
        ctx.save();
        ctx.translate(snake.x, snake.y);
        ctx.rotate(snake.angle);

        // Head Circle
        ctx.beginPath();
        ctx.arc(0, 0, snake.headRadius, 0, Math.PI * 2);
        ctx.fillStyle = snake.color;
        ctx.shadowColor = snake.secondaryColor;
        ctx.shadowBlur = isTracked ? 14 : 6;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Eyes (Slither style)
        const eyeOffset = snake.headRadius * 0.55;
        const eyeForward = snake.headRadius * 0.4;
        const eyeRadius = snake.headRadius * 0.38;
        const pupilRadius = eyeRadius * 0.5;

        // Left Eye
        ctx.beginPath();
        ctx.arc(eyeForward, -eyeOffset, eyeRadius, 0, Math.PI * 2);
        ctx.fillStyle = '#FFFFFF';
        ctx.fill();
        ctx.beginPath();
        ctx.arc(eyeForward + eyeRadius * 0.3, -eyeOffset, pupilRadius, 0, Math.PI * 2);
        ctx.fillStyle = '#0F172A';
        ctx.fill();

        // Right Eye
        ctx.beginPath();
        ctx.arc(eyeForward, eyeOffset, eyeRadius, 0, Math.PI * 2);
        ctx.fillStyle = '#FFFFFF';
        ctx.fill();
        ctx.beginPath();
        ctx.arc(eyeForward + eyeRadius * 0.3, eyeOffset, pupilRadius, 0, Math.PI * 2);
        ctx.fillStyle = '#0F172A';
        ctx.fill();

        ctx.restore();

        // Name tag & mass label
        ctx.font = '600 11px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = isTracked ? '#FDE047' : '#E2E8F0';
        ctx.fillText(
          `${snake.name} (${Math.floor(snake.mass)})`,
          snake.x,
          snake.y - snake.headRadius - 12
        );
      }

      ctx.restore(); // Restore camera transform

      // 6. Draw Minimap Radar (Bottom-Right HUD)
      const miniMapSize = 140;
      const margin = 16;
      const miniMapX = width - miniMapSize - margin;
      const miniMapY = height - miniMapSize - margin;
      const miniMapRadius = miniMapSize / 2;
      const miniMapCenterX = miniMapX + miniMapRadius;
      const miniMapCenterY = miniMapY + miniMapRadius;
      const scale = miniMapRadius / engine.arenaRadius;

      // Minimap Background
      ctx.save();
      ctx.beginPath();
      ctx.arc(miniMapCenterX, miniMapCenterY, miniMapRadius, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(15, 23, 42, 0.88)';
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.4)';
      ctx.stroke();
      ctx.clip();

      // Radar scan circles
      ctx.strokeStyle = 'rgba(51, 65, 85, 0.4)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(miniMapCenterX, miniMapCenterY, miniMapRadius * 0.5, 0, Math.PI * 2);
      ctx.stroke();

      // Camera view box on minimap
      const miniCamX = miniMapCenterX + camX * scale;
      const miniCamY = miniMapCenterY + camY * scale;
      const miniCamW = (width / zoom) * scale;
      const miniCamH = (height / zoom) * scale;
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
      ctx.lineWidth = 1;
      ctx.strokeRect(miniCamX - miniCamW / 2, miniCamY - miniCamH / 2, miniCamW, miniCamH);

      // Snake dots on minimap
      for (let s = 0; s < engine.snakes.length; s++) {
        const snk = engine.snakes[s];
        if (!snk.alive) continue;
        const mx = miniMapCenterX + snk.x * scale;
        const my = miniMapCenterY + snk.y * scale;

        ctx.beginPath();
        const dotRadius = snk.isPlayer ? 4 : snk.isChampion ? 3.5 : 2.2;
        ctx.arc(mx, my, dotRadius, 0, Math.PI * 2);
        ctx.fillStyle = snk.isPlayer ? '#38BDF8' : snk.isChampion ? '#F59E0B' : snk.color;
        ctx.fill();
      }

      ctx.restore();

      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
    };
  }, [engine, showSensors, onSelectSnake]);

  return (
    <div className="relative w-full h-full overflow-hidden bg-slate-950">
      <canvas
        ref={canvasRef}
        onMouseMove={handleMouseMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        className="w-full h-full cursor-crosshair block"
      />
    </div>
  );
};
