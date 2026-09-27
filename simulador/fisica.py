from ursina import Vec3

from .config import CARGA_ELETRON, N_PORTADORES_COBRE, PLACA


# region Tensao Hall: V_H = I B / (n e t)
# Converte mA e mT para SI. Retorna volts; corrente e polos definem o sinal.
def calcular_tensao_hall(corrente_ma, campo_mt, sentido_corrente, sinal_polo):
    corrente_a = corrente_ma / 1000 * sentido_corrente
    campo_t = campo_mt / 1000 * sinal_polo
    return corrente_a * campo_t / (N_PORTADORES_COBRE * CARGA_ELETRON * PLACA.espessura)
# endregion


# region Forca magnetica sobre o eletron
# A placa esta em XZ e B aponta para -Y no estado inicial. Como q < 0, F se opoe a v x B.
def direcoes_vetores_eletron(sentido_movimento, sinal_polo):
    velocidade = Vec3(0, 0, sentido_movimento)
    campo = Vec3(0, -sinal_polo, 0)
    forca = -velocidade.cross(campo)
    return velocidade, campo, forca
# endregion
