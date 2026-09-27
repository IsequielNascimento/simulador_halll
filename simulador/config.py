"""Parametros visuais, fisicos e geometria dos modelos 3D."""
from dataclasses import dataclass

from ursina import Vec3, color

# Animacao e controles
FATOR_DEFLEXAO_VISUAL = 2  # amplifica o desvio esquematico para facilitar a visualizacao
COOLDOWN_TECLAS = 1.0  # segundos entre os comandos M, I e F
MARCADORES_POR_FAIXA = 3
FAIXA_CORRENTE_MA = 20
CORRENTE_MIN_MA = 2
CORRENTE_MAX_MA = 100
MAX_MARCADORES_POSSIVEL = (CORRENTE_MAX_MA // FAIXA_CORRENTE_MA) * MARCADORES_POR_FAIXA
VELOCIDADE_MIN = 0.5  # velocidade visual em unidades da cena por segundo
VELOCIDADE_MAX = 3.0
Y_IMA_CIMA = 2.7
Y_IMA_BAIXO = 0.8
B_MIN, B_MAX = 0, 200  # limites do controle de campo, em mT

# Constantes para V_H = I*B / (n*e*t), em unidades SI
N_PORTADORES_COBRE = 8.49e28  # 1/m^3
CARGA_ELETRON = 1.6e-19  # C (modulo)

# Geometria do circuito e da placa no modelo GLB
CAMINHO = [
    Vec3(-1.001, 0.2, -0.255),   # parte_preta
    Vec3(-1.001, 0.2, -1.367),   # quina1 (fio)
    Vec3(0.811,  0.2, -1.367),   # quina2 (fio)
    Vec3(0.811,  0.2, -0.739),   # entra na placa
    Vec3(0.811,  0.2,  0.994),   # sai da placa
    Vec3(0.811,  0.2,  1.433),   # quina3 (fio)
    Vec3(-1.007, 0.2,  1.415),   # quina4 (fio)
    Vec3(-1.007, 0.2,  0.336),   # parte_laranja
]

@dataclass(frozen=True)
class Placa:
    minimo: Vec3
    maximo: Vec3
    espessura: float = 1.5e-4  # metros
    eixo_corrente: float = 0.811  
    segmento_caminho: int = 3

    @property
    def centro_x(self):
        return (self.minimo.x + self.maximo.x) / 2

    @property
    def centro_z(self):
        return (self.minimo.z + self.maximo.z) / 2


PLACA = Placa(Vec3(0.208, 0.2, -0.637), Vec3(1.346, 0.2, 0.906))

# Chave: (rotulo, descricao, cor).
# A ordem define a legenda e as linhas da coluna de vetores na tela.
VETORES = {
    'velocidade': ('v_e', 'velocidade', color.lime),
    'forca': ('F_B', 'forca magnetica', color.orange),
    'campo': ('B', 'campo magnetico', color.azure),
}
