"""Entidades e modelos de dados do Slither.io (Snake, Segment, Food)."""

from dataclasses import dataclass, field
import math
from typing import List, Optional

from ..config import SlitherConfig


@dataclass
class SnakePoint:
    """Ponto de histórico do rastro da cabeça (SnakePoint de Main.as)."""

    x: float
    y: float


@dataclass
class Segment:
    """Segmento/nó do corpo da cobra."""

    x: float
    y: float
    radius: float = SlitherConfig.BODY_RADIUS_BASE


@dataclass
class Food:
    """Esfera de comida na arena (Food de gaim.Food)."""

    id: int
    x: float
    y: float
    value: float = 1.0
    radius: float = 3.5
    is_eaten: bool = False
    is_poop: bool = False  # se foi gerado por perda de massa no boost


class Snake:
    """Representação física da cobra com histórico de pontos e dinâmica corporal."""

    def __init__(
        self,
        snake_id: int,
        name: str = "Snake",
        x: float = 0.0,
        y: float = 0.0,
        angle: float = 0.0,
        initial_score: float = SlitherConfig.INITIAL_BODY_LENGTH,
        is_bot: bool = False,
    ):
        self.id = snake_id
        self.name = name
        self.x = x
        self.y = y
        self.angle = angle
        self.target_angle = angle
        
        self.speed = SlitherConfig.SPEED_NORMAL
        self.target_speed = SlitherConfig.SPEED_NORMAL
        self.is_boosting = False
        
        self.score = max(initial_score, SlitherConfig.INITIAL_BODY_LENGTH)
        self.is_alive = True
        self.is_bot = is_bot
        
        # Histórico de rastros e nós
        self.history_points: List[SnakePoint] = []
        self.segments: List[Segment] = []
        
        # Inicializa nós em linha reta atrás da cabeça
        self._initialize_body()

        # Temporizador para queima de massa (poop)
        self.time_since_last_poop = 0.0

        # Estados de IA (idênticos a gaim.Snake)
        self.avoidance_dir = 1
        self.last_avoidance_dir_change_time = 0.0
        self.avoidance_point: Optional[SnakePoint] = None
        self.violent = False
        self.stop_violence_time = 0.0
        self.excited = False
        self.stop_excitement_time = 0.0
        self.target_food: Optional[Food] = None
        self.change_target_time = 0.0
        self.kills = 0

    @property
    def segment_count(self) -> int:
        """Quantidade de nós do corpo (calculado a partir da massa/score)."""
        return int(self.score)

    @property
    def radius(self) -> float:
        """Raio da cabeça da cobra com escala suave pelo tamanho."""
        # Escala logarítmica/raiz suave idêntica ao Slither original (scang)
        scale = 1.0 + 0.18 * math.log(max(1.0, self.score / SlitherConfig.INITIAL_BODY_LENGTH))
        return SlitherConfig.HEAD_RADIUS_BASE * min(2.5, scale)

    @property
    def segment_radius(self) -> float:
        """Raio dos segmentos do corpo."""
        scale = 1.0 + 0.15 * math.log(max(1.0, self.score / SlitherConfig.INITIAL_BODY_LENGTH))
        return SlitherConfig.BODY_RADIUS_BASE * min(2.4, scale)

    def _initialize_body(self):
        """Cria os segmentos iniciais espaçados uniformemente atrás da cabeça."""
        self.history_points.clear()
        self.segments.clear()
        
        cos_back = math.cos(self.angle + math.pi)
        sin_back = math.sin(self.angle + math.pi)
        
        # Gera histórico inicial
        dist_step = SlitherConfig.SEGMENT_DISTANCE
        total_pts = self.segment_count * 3
        for i in range(total_pts):
            px = self.x + cos_back * (i * (dist_step / 3.0))
            py = self.y + sin_back * (i * (dist_step / 3.0))
            self.history_points.append(SnakePoint(px, py))

        # Gera nós
        for i in range(self.segment_count):
            idx = min(len(self.history_points) - 1, (i + 1) * 3)
            pt = self.history_points[idx]
            self.segments.append(Segment(pt.x, pt.y, self.segment_radius))

    def update_body_segments(self):
        """Atualiza a posição de cada segmento ao longo do histórico de pontos da cabeça."""
        rad = self.segment_radius
        needed_segments = self.segment_count
        
        # Ajusta quantidade de nós se cresceu ou encolheu
        while len(self.segments) < needed_segments:
            last = self.segments[-1] if self.segments else Segment(self.x, self.y, rad)
            self.segments.append(Segment(last.x, last.y, rad))
        while len(self.segments) > needed_segments and len(self.segments) > 2:
            self.segments.pop()

        # Cada segmento i busca seu ponto proporcional no rastro
        dist_step = SlitherConfig.SEGMENT_DISTANCE
        step_index_multiplier = 3
        
        for i, seg in enumerate(self.segments):
            seg.radius = rad
            pt_idx = min(len(self.history_points) - 1, (i + 1) * step_index_multiplier)
            pt = self.history_points[pt_idx]
            seg.x = pt.x
            seg.y = pt.y
