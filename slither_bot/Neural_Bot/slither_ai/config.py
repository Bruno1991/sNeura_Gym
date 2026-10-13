"""Constantes físicas e de simulação extraídas com 100% de fidelidade do código-fonte do Slither.io."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SlitherConfig:
    """Configurações e parâmetros físicos do Slither.io extraídos de gaim.Main."""

    # Dimensões do mundo
    GAME_RADIUS: float = 21600.0  # grd (raio padrão do mapa circular)
    SECTOR_SIZE: float = 480.0    # setor para particionamento espacial
    
    # Velocidades e inércia (Main.as: nsp1, nsp2, nsp3)
    SPEED_NORMAL: float = 4.25     # nsp1 (velocidade padrão de cruzeiro)
    SPEED_BOOST: float = 12.0      # fsp / nsp3 (velocidade em aceleração turbo)
    ACCEL_RATE: float = 0.6        # aceleração ao ligar boost (Main.as l. 11403)
    DECEL_RATE: float = 0.3        # desaceleração ao soltar boost (Main.as l. 11411)
    
    # Dinâmica angular (giro e curvatura)
    MAX_ANGULAR_MULT: float = 0.033  # mamu (Main.as l. 33776)
    CST: float = 0.43               # cst (turn speed coefficient)
    SPANG_DIVISOR: float = 10.0     # spangdv
    
    # Dimensões geométricas de colisão (pixels)
    HEAD_RADIUS_BASE: float = 14.0
    BODY_RADIUS_BASE: float = 12.0
    SEGMENT_DISTANCE: float = 14.0   # distância base entre nós/segmentos consecutivos
    INITIAL_BODY_LENGTH: float = 10.0 # quantidade inicial de nós (sct)
    
    # Consumo de massa durante aceleração turbo
    BOOST_SCORE_LOSS_PER_SEC: float = 1.8  # perda de massa gerando orbs (poop)
    POOP_COOLDOWN_SEC: float = 0.12        # intervalo entre liberação de orbs
    MIN_SCORE_FOR_BOOST: float = 12.0      # score mínimo para poder queimar boost
    
    # Constantes matemáticas
    TWO_PI: float = 2.0 * math.pi
    RAD_TO_BYTE: float = 251.0 / (2.0 * math.pi)  # 251 / 2PI para protocolo v5+
    BYTE_TO_RAD: float = (2.0 * math.pi) / 251.0

    # Escala para treino local (dimensão reduzida da arena para densidade de interação no RL)
    ARENA_RADIUS_TRAIN: float = 2500.0  # arena de treinamento comprimida para encontros frequentes
    NUM_FOOD_TRAIN: int = 400
    NUM_BOTS_TRAIN: int = 12
