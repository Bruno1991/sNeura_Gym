"""Motor de simulação de alta performance do Slither.io (SlitherEngine)."""

import math
import random
from typing import Dict, List, Optional, Tuple

from ..config import SlitherConfig
from .collision import SlitherCollision
from .entities import Food, Snake
from .expert_bot import SlitherNativeBot
from .physics import SlitherPhysics


class SlitherEngine:
    """Orquestrador do mundo Slither: entidades, física, bots e colisões."""

    def __init__(
        self,
        arena_radius: float = SlitherConfig.ARENA_RADIUS_TRAIN,
        num_bots: int = SlitherConfig.NUM_BOTS_TRAIN,
        num_foods: int = SlitherConfig.NUM_FOOD_TRAIN,
    ):
        self.arena_radius = arena_radius
        self.target_num_bots = num_bots
        self.target_num_foods = num_foods
        
        self.snakes: List[Snake] = []
        self.bot_brains: Dict[int, SlitherNativeBot] = {}
        self.foods: List[Food] = []
        
        self.current_time_sec = 0.0
        self.next_snake_id = 1
        self.next_food_id = 1

        # Inicializa o mundo
        self.reset()

    def reset(self):
        """Reinicia o mundo da arena."""
        self.snakes.clear()
        self.bot_brains.clear()
        self.foods.clear()
        self.current_time_sec = 0.0
        
        # Popula alimentos iniciais
        self.spawn_initial_foods(self.target_num_foods)
        
        # Popula bots iniciais
        for i in range(self.target_num_bots):
            self.spawn_bot(f"Bot_{i+1}")

    def spawn_initial_foods(self, count: int):
        """Gera alimentos distribuídos uniformemente pelo círculo da arena."""
        for _ in range(count):
            # Amostragem em disco polar uniforme: r = R * sqrt(random)
            r = (self.arena_radius - 80.0) * math.sqrt(random.random())
            theta = random.uniform(0.0, SlitherConfig.TWO_PI)
            fx = r * math.cos(theta)
            fy = r * math.sin(theta)
            val = random.choices([1.0, 2.0, 3.5, 6.0], weights=[0.65, 0.22, 0.10, 0.03])[0]
            
            self.foods.append(
                Food(
                    id=self.next_food_id,
                    x=fx,
                    y=fy,
                    value=val,
                    radius=3.0 + val * 0.4,
                )
            )
            self.next_food_id += 1

    def spawn_bot(self, name: str) -> Snake:
        """Gera um novo bot com IA nativa e adiciona à arena."""
        r = (self.arena_radius - 300.0) * math.sqrt(random.random())
        theta = random.uniform(0.0, SlitherConfig.TWO_PI)
        bx = r * math.cos(theta)
        by = r * math.sin(theta)
        b_ang = random.uniform(0.0, SlitherConfig.TWO_PI)
        
        score = random.uniform(10.0, 35.0)
        bot_snake = Snake(
            snake_id=self.next_snake_id,
            name=name,
            x=bx,
            y=by,
            angle=b_ang,
            initial_score=score,
            is_bot=True,
        )
        self.next_snake_id += 1
        
        self.snakes.append(bot_snake)
        self.bot_brains[bot_snake.id] = SlitherNativeBot(bot_snake)
        return bot_snake

    def add_player_snake(self, name: str = "Player") -> Snake:
        """Adiciona uma cobra controlada externamente (pelo agente ou usuário)."""
        r = (self.arena_radius * 0.4) * math.sqrt(random.random())
        theta = random.uniform(0.0, SlitherConfig.TWO_PI)
        px = r * math.cos(theta)
        py = r * math.sin(theta)
        p_ang = random.uniform(0.0, SlitherConfig.TWO_PI)

        player_snake = Snake(
            snake_id=self.next_snake_id,
            name=name,
            x=px,
            y=py,
            angle=p_ang,
            initial_score=SlitherConfig.INITIAL_BODY_LENGTH,
            is_bot=False,
        )
        self.next_snake_id += 1
        self.snakes.append(player_snake)
        return player_snake

    def step(self, dt: float = 0.033) -> Dict[str, any]:
        """Avança o mundo por um intervalo dt (~33ms / 30Hz).
        
        Retorna estatísticas do tick.
        """
        self.current_time_sec += dt
        deaths_this_tick: List[Tuple[Snake, Snake]] = []

        # 1. Decisão dos Bots Nativos
        for snake in self.snakes:
            if snake.is_alive and snake.is_bot and snake.id in self.bot_brains:
                self.bot_brains[snake.id].update_decision(
                    all_snakes=self.snakes,
                    foods=self.foods,
                    current_time_sec=self.current_time_sec,
                    arena_radius=self.arena_radius,
                )

        # 2. Atualização Física de Movimento
        new_poop_foods: List[Food] = []
        for snake in self.snakes:
            if snake.is_alive:
                poop = SlitherPhysics.update_snake_motion(snake, dt)
                if poop:
                    poop.id = self.next_food_id
                    self.next_food_id += 1
                    new_poop_foods.append(poop)

        self.foods.extend(new_poop_foods)

        # 3. Colisões com a Borda da Arena
        for snake in self.snakes:
            if snake.is_alive and SlitherCollision.check_boundary_collision(snake, self.arena_radius):
                snake.is_alive = False
                deaths_this_tick.append((snake, None))

        # 4. Colisões Fatais entre Cobras
        snake_deaths = SlitherCollision.check_snake_collisions(self.snakes)
        for victim, killer in snake_deaths:
            if victim.is_alive:
                victim.is_alive = False
                if killer and killer.is_alive:
                    killer.kills += 1
                deaths_this_tick.append((victim, killer))

        # 5. Cobras mortas geram banquetes de comida (corpse foods)
        for dead_snake, _ in deaths_this_tick:
            corpse_foods = SlitherCollision.spawn_death_food(dead_snake, self.next_food_id)
            self.next_food_id += len(corpse_foods)
            self.foods.extend(corpse_foods)

        # 6. Consumo de Comida
        for snake in self.snakes:
            if snake.is_alive:
                SlitherCollision.check_food_consumption(snake, self.foods)

        # 7. Limpeza de comidas devoradas e respawn orgânico
        self.foods = [f for f in self.foods if not f.is_eaten]
        if len(self.foods) < self.target_num_foods:
            needed = self.target_num_foods - len(self.foods)
            self.spawn_initial_foods(needed)

        # 8. Respawn de Bots mortos para manter ecossistema ativo
        active_bots = sum(1 for s in self.snakes if s.is_alive and s.is_bot)
        while active_bots < self.target_num_bots:
            self.spawn_bot(f"Bot_{self.next_snake_id}")
            active_bots += 1

        return {
            "current_time": self.current_time_sec,
            "deaths_count": len(deaths_this_tick),
            "snakes_count": len(self.snakes),
            "foods_count": len(self.foods),
        }
