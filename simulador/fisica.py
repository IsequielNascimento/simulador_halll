"""Calculos e convencoes fisicas; nenhuma entidade visual e criada aqui."""
from ursina import Vec3

from .config import CARGA_ELETRON, N_PORTADORES_COBRE, PLACA


def calcular_tensao_hall(corrente_ma, campo_mt, sentido_corrente, sinal_polo):
    """Retorna V_H em volts, mantendo a convencao de sinais do simulador."""
    corrente_a = corrente_ma / 1000 * sentido_corrente
    campo_t = campo_mt / 1000 * sinal_polo
    return corrente_a * campo_t / (N_PORTADORES_COBRE * CARGA_ELETRON * PLACA.espessura)


def direcoes_vetores_eletron(sentido_movimento, sinal_polo):
    """Direcoes na placa XZ; o polo N original aponta para baixo (-Y)."""
    velocidade = Vec3(0, 0, sentido_movimento)
    campo = Vec3(0, -sinal_polo, 0)
    forca = -velocidade.cross(campo)  # carga negativa do eletron
    return velocidade, campo, forca

