"""Detecção geométrica e espacial de colisões (Comida, Arena e Corpos de Cobras)."""

import math
from typing import List, Set, Tuple

from ..config import SlitherConfig
from ..utils.math_helpers import distance_sq
from .entities import Food, Snake


class SlitherCollision:
    """Calculador de colisões com suporte a detecção exata circular."""

    @staticmethod
    def check_boundary_collision(snake: Snake, arena_radius: float) -> bool:
        """Verifica se a cabeça da cobra atingiu a borda circular da arena."""
        if not snake.is_alive:
            return False
        dist_sq = snake.x * snake.x + snake.y * snake.y
        # Colisão quando a borda da cabeça ultrapassa o raio do mapa
        limit = arena_radius - snake.radius
        return dist_sq >= (limit * limit)

    @staticmethod
    def check_food_consumption(snake: Snake, foods: List[Food]) -> List[Food]:
        """Detecta alimentos interceptados pela cabeça da cobra e aplica crescimento."""
        if not snake.is_alive:
            return []

        eaten: List[Food] = []
        head_r = snake.radius
        sx, sy = snake.x, snake.y
        box_limit = head_r + 15.0

        for food in foods:
            if food.is_eaten:
                continue

            # Bounding Box pré-rejeição de alta velocidade
            if abs(food.x - sx) > box_limit or abs(food.y - sy) > box_limit:
                continue

            # Raio combinado de contato (cabeça + orb)
            max_dist = head_r + food.radius + 6.0  # pequeno raio magnético de sucção
            max_dist_sq = max_dist * max_dist
            dx = sx - food.x
            dy = sy - food.y

            if (dx * dx + dy * dy) <= max_dist_sq:
                food.is_eaten = True
                snake.score += food.value
                eaten.append(food)

        return eaten

    @staticmethod
    def check_snake_collisions(snakes: List[Snake]) -> List[Tuple[Snake, Snake]]:
        """Verifica colisões fatais entre a cabeça de cada cobra e os corpos das outras.
        
        Retorna lista de tuplas: (cobra_morta, cobra_assassina).
        """
        deaths: List[Tuple[Snake, Snake]] = []
        dead_ids: Set[int] = set()

        # Compara cada cobra ativa
        for a in snakes:
            if not a.is_alive or a.id in dead_ids:
                continue

            head_a_r = a.radius
            ax, ay = a.x, a.y

            for b in snakes:
                if not b.is_alive:
                    continue

                # 1. Colisão Cabeça-com-Cabeça
                if a.id != b.id and b.id not in dead_ids:
                    head_limit = head_a_r + b.radius
                    if abs(ax - b.x) <= head_limit and abs(ay - b.y) <= head_limit:
                        head_dist_sq = (ax - b.x) ** 2 + (ay - b.y) ** 2
                        if head_dist_sq < (head_limit * head_limit):
                            # A menor cobra morre; se iguais, ambas morrem
                            if a.score < b.score:
                                deaths.append((a, b))
                                dead_ids.add(a.id)
                                break
                            elif b.score < a.score:
                                deaths.append((b, a))
                                dead_ids.add(b.id)
                            else:
                                deaths.append((a, b))
                                deaths.append((b, a))
                                dead_ids.add(a.id)
                                dead_ids.add(b.id)
                                break

                # 2. Colisão Cabeça de A com Corpo de B (apenas com OUTRAS cobras)
                if a.id == b.id:
                    continue  # No Slither.io, uma cobra nunca morre colidindo consigo mesma

                # Bounding box pré-rejeição de cobra distante
                if abs(ax - b.x) > 650.0 or abs(ay - b.y) > 650.0:
                    continue

                collision_found = False
                for seg in b.segments:
                    comb_r = head_a_r + seg.radius - 2.0  # pequena tolerância suave
                    if abs(ax - seg.x) > comb_r or abs(ay - seg.y) > comb_r:
                        continue
                    dx = ax - seg.x
                    dy = ay - seg.y
                    if (dx * dx + dy * dy) <= (comb_r * comb_r):
                        deaths.append((a, b))
                        dead_ids.add(a.id)
                        collision_found = True
                        break

                if collision_found:
                    break

        return deaths

    @staticmethod
    def spawn_death_food(dead_snake: Snake, start_id: int) -> List[Food]:
        """Gera orbs de comida ao longo dos segmentos do corpo da cobra morta."""
        corpse_foods: List[Food] = []
        cur_id = start_id
        
        # Cada segmento da cobra morta gera comida rica em massa
        food_per_seg = max(1.2, dead_snake.score / max(1, len(dead_snake.segments)))
        
        for seg in dead_snake.segments:
            corpse_foods.append(
                Food(
                    id=cur_id,
                    x=seg.x,
                    y=seg.y,
                    value=food_per_seg,
                    radius=5.5,
                    is_poop=True,
                )
            )
            cur_id += 1

        return corpse_foods
