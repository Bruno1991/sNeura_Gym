"""Funções matemáticas auxiliares de geometria, trigonometria e conversão de ângulos."""

import math
from ..config import SlitherConfig


def normalize_angle_two_pi(rad: float) -> float:
    """Normaliza o ângulo para o intervalo [0, 2*pi)."""
    val = rad % SlitherConfig.TWO_PI
    if val < 0.0:
        val += SlitherConfig.TWO_PI
    return val


def normalize_angle_pi(rad: float) -> float:
    """Normaliza o ângulo para o intervalo [-pi, +pi]."""
    val = (rad + math.pi) % SlitherConfig.TWO_PI - math.pi
    return val


def shortest_angular_difference(target_angle: float, current_angle: float) -> float:
    """Retorna a menor diferença angular no intervalo [-pi, +pi].
    
    Positivo = girar no sentido anti-horário; Negativo = sentido horário.
    """
    diff = (target_angle - current_angle) % SlitherConfig.TWO_PI
    if diff < 0.0:
        diff += SlitherConfig.TWO_PI
    if diff > math.pi:
        diff -= SlitherConfig.TWO_PI
    return diff


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Distância euclidiana entre dois pontos."""
    return math.hypot(x2 - x1, y2 - y1)


def distance_sq(x1: float, y1: float, x2: float, y2: float) -> float:
    """Quadrado da distância euclidiana (evita math.sqrt para alta performance)."""
    dx = x2 - x1
    dy = y2 - y1
    return dx * dx + dy * dy


def angle_to(x1: float, y1: float, x2: float, y2: float) -> float:
    """Ângulo em radianos de (x1, y1) apontando para (x2, y2)."""
    return math.atan2(y2 - y1, x2 - x1)


def angle_to_protocol_byte(angle: float) -> int:
    """Converte um ângulo em radianos [0, 2*pi) para 1 byte do protocolo Slither [0, 251]."""
    ang = normalize_angle_two_pi(angle)
    byte_val = int(ang * SlitherConfig.RAD_TO_BYTE)
    return max(0, min(251, byte_val))


def protocol_byte_to_angle(byte_val: int) -> float:
    """Converte 1 byte do protocolo Slither [0, 251] para radianos [0, 2*pi)."""
    clamped = max(0, min(251, byte_val))
    return clamped * SlitherConfig.BYTE_TO_RAD
