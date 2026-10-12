"""Núcleo de física, entidades e simulação do Slither.io."""

from .collision import SlitherCollision
from .engine import SlitherEngine
from .entities import Food, Segment, Snake, SnakePoint
from .expert_bot import SlitherNativeBot
from .physics import SlitherPhysics

__all__ = [
    "Snake",
    "Segment",
    "SnakePoint",
    "Food",
    "SlitherPhysics",
    "SlitherCollision",
    "SlitherNativeBot",
    "SlitherEngine",
]
