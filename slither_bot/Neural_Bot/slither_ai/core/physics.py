"""Motor de física e cinemática 100% fiel às fórmulas de gaim.Main."""

import math
from typing import List, Optional

from ..config import SlitherConfig
from ..utils.math_helpers import (
    distance,
    normalize_angle_two_pi,
    shortest_angular_difference,
)
from .entities import Food, Snake, SnakePoint


class SlitherPhysics:
    """Implementa a dinâmica de movimento, giro e consumo de massa."""

    @staticmethod
    def calculate_turn_rate(snake: Snake) -> float:
        """Calcula a taxa máxima de rotação angular por tick (mang em Main.as).
        
        No Slither original:
        mang = mamu * vfr * scang * spang
        onde cobras maiores têm scang menor (curvam mais lentamente).
        """
        # scang diminui suavemente conforme o score cresce
        score_ratio = max(1.0, snake.score / SlitherConfig.INITIAL_BODY_LENGTH)
        scang = 1.0 / (1.0 + 0.12 * math.log(score_ratio))
        
        # spang aumenta com a velocidade
        spang = snake.speed / SlitherConfig.SPEED_NORMAL
        
        turn_rate = SlitherConfig.MAX_ANGULAR_MULT * scang * spang * 2.8
        return max(0.04, min(0.35, turn_rate))

    @classmethod
    def update_snake_motion(cls, snake: Snake, dt: float) -> Optional[Food]:
        """Avança a física da cobra por um intervalo de tempo dt.
        
        Retorna uma instância de Food caso a cobra tenha soltado massa (poop) ao acelerar.
        """
        if not snake.is_alive:
            return None

        # 1. Atualização da velocidade linear (aceleração e frenagem suave)
        can_boost = snake.is_boosting and snake.score > SlitherConfig.MIN_SCORE_FOR_BOOST
        desired_speed = SlitherConfig.SPEED_BOOST if can_boost else SlitherConfig.SPEED_NORMAL
        
        step_factor = dt * 30.0  # normalizado para 30 FPS padrão do servidor Slither
        
        if snake.speed < desired_speed:
            snake.speed = min(desired_speed, snake.speed + SlitherConfig.ACCEL_RATE * step_factor)
        elif snake.speed > desired_speed:
            snake.speed = max(desired_speed, snake.speed - SlitherConfig.DECEL_RATE * step_factor)

        # 2. Atualização do ângulo (giro angular limitado por mang)
        turn_rate = cls.calculate_turn_rate(snake) * step_factor
        diff = shortest_angular_difference(snake.target_angle, snake.angle)
        
        if abs(diff) <= turn_rate:
            snake.angle = snake.target_angle
        else:
            turn_direction = 1.0 if diff > 0 else -1.0
            snake.angle += turn_direction * turn_rate

        snake.angle = normalize_angle_two_pi(snake.angle)

        # 3. Avanço da cabeça
        dist = snake.speed * step_factor
        snake.x += math.cos(snake.angle) * dist
        snake.y += math.sin(snake.angle) * dist

        # 4. Gravação de rastro histórico e segmentos
        # Adiciona ponto na frente do histórico
        snake.history_points.insert(0, SnakePoint(snake.x, snake.y))
        
        # Limita tamanho máximo do histórico para economizar memória
        max_needed_pts = (snake.segment_count + 4) * 4
        if len(snake.history_points) > max_needed_pts:
            del snake.history_points[max_needed_pts:]

        # Atualiza posições físicas dos nós ao longo do rastro
        snake.update_body_segments()

        # 5. Queima de massa durante turbo (poop)
        dropped_food = None
        if can_boost:
            snake.time_since_last_poop += dt
            if snake.time_since_last_poop >= SlitherConfig.POOP_COOLDOWN_SEC:
                snake.time_since_last_poop = 0.0
                mass_loss = SlitherConfig.BOOST_SCORE_LOSS_PER_SEC * SlitherConfig.POOP_COOLDOWN_SEC
                snake.score = max(SlitherConfig.INITIAL_BODY_LENGTH, snake.score - mass_loss)
                
                # Solta orb de massa atrás da cauda da cobra
                if snake.segments:
                    tail = snake.segments[-1]
                    dropped_food = Food(
                        id=0,  # ID será atribuído pela Engine
                        x=tail.x,
                        y=tail.y,
                        value=mass_loss * 0.9,
                        radius=3.0,
                        is_poop=True,
                    )

        return dropped_food
