/**
 * Sensory Raycasting and Perception System for Slither Bots
 */

import { FoodOrb, Point, SensoryRay, Snake } from '../game/types';

export const NUM_RAYS = 12;
export const RAY_MAX_DIST = 550;

/**
 * Calculates sensor inputs for a snake
 * Returns sensory array and normalized input vector of length 28:
 * - 0..11: Food proximity per ray (0 = none, 1 = touching head)
 * - 12..23: Danger proximity per ray (0 = clear, 1 = collision threat)
 * - 24: Current speed ratio (0 = normal, 1 = boost)
 * - 25: Mass ratio (0 to 1)
 * - 26: Relative angle to map center (-1 to 1)
 * - 27: Proximity to circular arena boundary (0 = safe center, 1 = touching border)
 */
export function computeSnakeSensors(
  snake: Snake,
  otherSnakes: Snake[],
  foodOrbs: FoodOrb[],
  arenaRadius: number
): { rays: SensoryRay[]; inputs: number[] } {
  const headX = snake.x;
  const headY = snake.y;
  const headAngle = snake.angle;
  const rays: SensoryRay[] = [];

  const foodProximities: number[] = new Array(NUM_RAYS).fill(0);
  const dangerProximities: number[] = new Array(NUM_RAYS).fill(0);

  // Fast pre-filter of food orbs within max ray distance
  const nearbyFood: FoodOrb[] = [];
  const maxDistSq = RAY_MAX_DIST * RAY_MAX_DIST;
  for (let i = 0; i < foodOrbs.length; i++) {
    const f = foodOrbs[i];
    const dx = f.x - headX;
    const dy = f.y - headY;
    if (dx * dx + dy * dy < maxDistSq) {
      nearbyFood.push(f);
    }
  }

  // Fast pre-filter of enemy segments within max ray distance
  interface ObstacleCircle {
    x: number;
    y: number;
    radius: number;
  }
  const obstacles: ObstacleCircle[] = [];

  for (let s = 0; s < otherSnakes.length; s++) {
    const other = otherSnakes[s];
    if (!other.alive || other.id === snake.id) continue;

    // Check if other snake is anywhere near
    const sDx = other.x - headX;
    const sDy = other.y - headY;
    if (sDx * sDx + sDy * sDy > (RAY_MAX_DIST + 400) * (RAY_MAX_DIST + 400)) {
      continue;
    }

    // Add head and body segments (stride sample segments for performance)
    obstacles.push({ x: other.x, y: other.y, radius: other.headRadius });
    const stride = Math.max(1, Math.floor(other.segments.length / 25));
    for (let segIdx = 0; segIdx < other.segments.length; segIdx += stride) {
      const seg = other.segments[segIdx];
      obstacles.push({ x: seg.x, y: seg.y, radius: other.bodyRadius });
    }
  }

  // Cast each ray
  for (let r = 0; r < NUM_RAYS; r++) {
    const relAngle = (r / NUM_RAYS) * Math.PI * 2;
    // Align ray 0 to forward heading
    let normalizedRel = relAngle;
    if (normalizedRel > Math.PI) normalizedRel -= Math.PI * 2;

    const worldAngle = headAngle + normalizedRel;
    const rayDirX = Math.cos(worldAngle);
    const rayDirY = Math.sin(worldAngle);

    let minDangerDist = RAY_MAX_DIST;
    let dangerHitPoint: Point | undefined;

    let minFoodDist = RAY_MAX_DIST;
    let foodHitPoint: Point | undefined;

    // 1. Raycast against arena perimeter (circle of radius arenaRadius centered at 0,0)
    // Ray: P(t) = (headX + t*rayDirX, headY + t*rayDirY)
    // |P(t)|^2 = arenaRadius^2
    const b = 2 * (headX * rayDirX + headY * rayDirY);
    const c = headX * headX + headY * headY - arenaRadius * arenaRadius;
    const disc = b * b - 4 * c;
    if (disc >= 0) {
      const t = (-b + Math.sqrt(disc)) / 2;
      if (t > 0 && t < minDangerDist) {
        minDangerDist = t;
        dangerHitPoint = { x: headX + rayDirX * t, y: headY + rayDirY * t };
      }
    }

    // 2. Raycast against enemy snake segments
    for (let o = 0; o < obstacles.length; o++) {
      const obs = obstacles[o];
      // Vector from head to obstacle center
      const toObsX = obs.x - headX;
      const toObsY = obs.y - headY;

      // Project onto ray direction
      const proj = toObsX * rayDirX + toObsY * rayDirY;
      if (proj <= 0 || proj >= minDangerDist + obs.radius) continue;

      // Perpendicular distance squared
      const perpSq = (toObsX * toObsX + toObsY * toObsY) - proj * proj;
      const rSq = obs.radius * obs.radius;
      if (perpSq < rSq) {
        // Hit!
        const hitDist = proj - Math.sqrt(Math.max(0, rSq - perpSq));
        if (hitDist > 0 && hitDist < minDangerDist) {
          minDangerDist = hitDist;
          dangerHitPoint = { x: headX + rayDirX * hitDist, y: headY + rayDirY * hitDist };
        }
      }
    }

    // 3. Raycast against nearby food
    for (let f = 0; f < nearbyFood.length; f++) {
      const food = nearbyFood[f];
      const toFoodX = food.x - headX;
      const toFoodY = food.y - headY;

      const proj = toFoodX * rayDirX + toFoodY * rayDirY;
      if (proj <= 0 || proj >= minFoodDist + food.radius * 2) continue;

      const perpSq = (toFoodX * toFoodX + toFoodY * toFoodY) - proj * proj;
      // Food interaction tolerance radius (wider beam so snakes notice food)
      const detectRadius = Math.max(16, food.radius * 2.5);
      if (perpSq < detectRadius * detectRadius) {
        if (proj < minFoodDist) {
          minFoodDist = proj;
          foodHitPoint = { x: food.x, y: food.y };
        }
      }
    }

    // Proximity value: 1 = touching head, 0 = far away
    const dangerProx = minDangerDist < RAY_MAX_DIST ? 1 - minDangerDist / RAY_MAX_DIST : 0;
    const foodProx = minFoodDist < RAY_MAX_DIST ? 1 - minFoodDist / RAY_MAX_DIST : 0;

    dangerProximities[r] = dangerProx;
    foodProximities[r] = foodProx;

    rays.push({
      angle: normalizedRel,
      worldAngle,
      dangerDist: minDangerDist,
      foodDist: minFoodDist,
      dangerHitPoint,
      foodHitPoint,
    });
  }

  // Proprioceptive inputs
  const speedRatio = snake.isBoosting ? 1.0 : 0.0;
  const massRatio = Math.min(1.0, (snake.mass - 10) / 400);

  // Angle to arena center (0,0)
  const angleToCenter = Math.atan2(-headY, -headX);
  let centerAngleDiff = angleToCenter - headAngle;
  while (centerAngleDiff > Math.PI) centerAngleDiff -= Math.PI * 2;
  while (centerAngleDiff < -Math.PI) centerAngleDiff += Math.PI * 2;
  const normalizedCenterAngle = centerAngleDiff / Math.PI; // -1 to 1

  // Distance to border (0 = center, 1 = border)
  const distFromCenter = Math.sqrt(headX * headX + headY * headY);
  const borderProximity = Math.min(1.0, distFromCenter / arenaRadius);

  // Combine into single input vector
  const inputs: number[] = [
    ...foodProximities,     // 0..11
    ...dangerProximities,   // 12..23
    speedRatio,             // 24
    massRatio,              // 25
    normalizedCenterAngle,  // 26
    borderProximity,        // 27
  ];

  return { rays, inputs };
}
