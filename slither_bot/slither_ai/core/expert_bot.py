"""IA especialista nativa 100% fiel à lógica descompilada de gaim.Main (linhas 11090-11250)."""

import math
import random
from typing import List, Optional

from ..config import SlitherConfig
from ..utils.math_helpers import (
    angle_to,
    distance_sq,
    normalize_angle_two_pi,
)
from .entities import Food, Snake, SnakePoint


class SlitherNativeBot:
    """Implementa o cérebro da IA dos bots originais do Slither.io."""

    AVOIDANCE_DETECTION_DIST = 140.0  # distância de detecção de perigo
    AVOIDANCE_DETECTION_SQ = AVOIDANCE_DETECTION_DIST * AVOIDANCE_DETECTION_DIST
    INTERCEPT_LEAD_DIST = 95.0        # avanço predatório na frente do oponente (Main.as)

    def __init__(self, snake: Snake):
        self.snake = snake

    def update_decision(
        self,
        all_snakes: List[Snake],
        foods: List[Food],
        current_time_sec: float,
        arena_radius: float = SlitherConfig.GAME_RADIUS,
    ):
        """Executa um ciclo da árvore de decisão da IA original."""
        if not self.snake.is_alive:
            return

        sk = self.snake
        ctm = current_time_sec

        # 1. Detecção de Borda da Arena (Prioridade Máxima)
        dist_from_center_sq = sk.x * sk.x + sk.y * sk.y
        border_warning = arena_radius - 220.0
        if dist_from_center_sq > (border_warning * border_warning):
            # Retorna em direção ao centro da arena (0, 0)
            sk.target_angle = angle_to(sk.x, sk.y, 0.0, 0.0)
            sk.is_boosting = False
            return

        # 2. Varredura de Obstáculos Próximos (Avoidance Steering)
        closest_obstacle: Optional[SnakePoint] = None
        min_obst_dist_sq = self.AVOIDANCE_DETECTION_SQ

        for other in all_snakes:
            if not other.is_alive or other.id == sk.id:
                continue

            for seg in other.segments:
                d_sq = distance_sq(sk.x, sk.y, seg.x, seg.y)
                if d_sq < min_obst_dist_sq:
                    min_obst_dist_sq = d_sq
                    closest_obstacle = SnakePoint(seg.x, seg.y)

        # Alternância periódica da direção de desvio (Main.as l. 11100-11114)
        if ctm - sk.last_avoidance_dir_change_time > 2.0:
            if closest_obstacle is None:
                sk.last_avoidance_dir_change_time = ctm
                sk.avoidance_dir = 2 if sk.avoidance_dir == 1 else 1

        # 3. Execução da Decisão
        # A) Evitação de Colisão Ativa
        if closest_obstacle is not None:
            # Desvio tangencial a +/- 15 graus (+/- 0.26 radianos) da colisão
            tangent = 0.26 if sk.avoidance_dir == 1 else -0.26
            away_angle = math.atan2(sk.y - closest_obstacle.y, sk.x - closest_obstacle.x)
            sk.target_angle = normalize_angle_two_pi(away_angle + tangent)
            sk.is_boosting = False
            return

        # B) Modo Predatório / Violência (Main.as l. 11163-11184)
        target_player: Optional[Snake] = None
        for other in all_snakes:
            if other.id != sk.id and other.is_alive and not other.is_bot:
                target_player = other
                break
        if target_player is None:
            for other in all_snakes:
                if other.id != sk.id and other.is_alive:
                    target_player = other
                    break

        if sk.violent:
            if ctm > sk.stop_violence_time:
                sk.violent = False
        elif sk.segment_count > 10 and target_player and target_player.segment_count > 7:
            # 30% de chance periódica de ativar ataque contra alvo próximo
            d_sq = distance_sq(sk.x, sk.y, target_player.x, target_player.y)
            if d_sq < (600.0 * 600.0) and random.random() < 0.15:
                sk.violent = True
                sk.stop_violence_time = ctm + 4.0 + random.uniform(0.0, 6.0)

        if sk.violent and target_player and target_player.is_alive:
            # Interceptação preditiva a 95 pixels à frente da cabeça da vítima
            lead_x = target_player.x + math.cos(target_player.angle) * self.INTERCEPT_LEAD_DIST
            lead_y = target_player.y + math.sin(target_player.angle) * self.INTERCEPT_LEAD_DIST
            sk.target_angle = angle_to(sk.x, sk.y, lead_x, lead_y)
            sk.is_boosting = True
            return

        # C) Modo Empolgado (Burst aleatório de velocidade)
        if sk.excited:
            if ctm > sk.stop_excitement_time:
                sk.excited = False
        elif sk.segment_count > 10 and random.random() < 0.005:
            sk.excited = True
            sk.stop_excitement_time = ctm + 0.5 + random.uniform(0.0, 2.5)

        sk.is_boosting = sk.excited

        # D) Busca e Coleta de Comida (Foraging Behavior)
        if ctm > sk.change_target_time or sk.target_food is None or sk.target_food.is_eaten:
            best_food: Optional[Food] = None
            min_food_dist_sq = 800.0 * 800.0  # campo de busca visual

            for fo in foods:
                if fo.is_eaten:
                    continue
                d_sq = distance_sq(sk.x, sk.y, fo.x, fo.y)
                if d_sq < min_food_dist_sq:
                    min_food_dist_sq = d_sq
                    best_food = fo

            if best_food is not None:
                sk.target_food = best_food
                sk.change_target_time = ctm + 3.0 + random.uniform(0.0, 0.5)

        if sk.target_food is not None and not sk.target_food.is_eaten:
            sk.target_angle = angle_to(sk.x, sk.y, sk.target_food.x, sk.target_food.y)
        else:
            # Caso não haja comida no radar, segue vagando suavemente
            if random.random() < 0.03:
                sk.target_angle = normalize_angle_two_pi(sk.angle + random.uniform(-0.6, 0.6))
