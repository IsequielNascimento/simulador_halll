import math
import sys
from pathlib import Path
from ursina import *
from ursina.prefabs.slider import Slider

# quando rodar como .exe gerado pelo PyInstaller, os arquivos (inclusive os .glb)
# ficam descompactados numa pasta temporaria (sys._MEIPASS) em vez da pasta do
# projeto -- sem isso o Ursina nao acha os modelos e o exe abre com tela preta
if hasattr(sys, '_MEIPASS'):
    application.asset_folder = Path(sys._MEIPASS)

# ---- constantes ajustaveis ----
FATOR_DEFLEXAO_VISUAL = 2  # exagero de proposito pra ficar visivel; 1.0 = fisicamente "correto"
MARCADORES_POR_FAIXA = 3     # quantas bolinhas novas liberam a cada faixa de corrente atingida
FAIXA_CORRENTE_MA = 20       # tamanho de cada faixa de corrente, em mA
CORRENTE_MIN_MA = 2          # espelha o min do slider de corrente (definido mais abaixo)
CORRENTE_MAX_MA = 100        # espelha o max do slider de corrente (definido mais abaixo)
# pool de marcadores pre-criado pro maior numero possivel (corrente no maximo)
# ---- constantes fisicas pro calculo real da tensao Hall (V_H = I*B / (n*e*t)) ----
N_PORTADORES_COBRE = 8.49e28   # densidade de portadores de carga do cobre, em 1/m^3
CARGA_ELETRON = 1.6e-19        # C
ESPESSURA_PLACA_M = 1.5e-4     # espessura da placa (m) -- AJUSTA aqui se o grupo definiu outro valor
MAX_MARCADORES_POSSIVEL = (CORRENTE_MAX_MA // FAIXA_CORRENTE_MA) * MARCADORES_POR_FAIXA


app = Ursina()
EditorCamera()

modelo = Entity(
    model='models/placa_bateria_fio.glb',
    scale=0.02,
    position=(0, 0, 0)
)

Entity(model='plane', scale=20, color=color.dark_gray, y=-1)


class SistemaBolinhasCircuito:
    """Bolinhas seguindo o laço reto do circuito (sem efeito do ímã)."""

    def __init__(self, caminho, espacamento=0.25, cor=color.red):
        self.caminho = caminho
        self.ativo = True
        self.progresso = 0

        self.segmentos = []
        self.comprimento_total = 0
        for i in range(len(caminho)):
            p1 = caminho[i]
            p2 = caminho[(i + 1) % len(caminho)]
            d = (p2 - p1).length()
            self.segmentos.append((p1, p2, d))
            self.comprimento_total += d

        n_bolinhas = max(1, int(self.comprimento_total / espacamento))
        self.bolinhas = []
        for i in range(n_bolinhas):
            offset = i * espacamento
            b = Entity(model='sphere', scale=0.10, color=cor,
                       position=self._posicao_no_caminho(offset))
            self.bolinhas.append({'entity': b, 'offset': offset})

    def _posicao_no_caminho(self, distancia):
        distancia = distancia % self.comprimento_total
        acumulado = 0
        for p1, p2, d in self.segmentos:
            if acumulado + d >= distancia:
                t = (distancia - acumulado) / d if d > 0 else 0
                return p1 + (p2 - p1) * t
            acumulado += d
        return self.caminho[0]

    def set_ativo(self, ativo):
        self.ativo = ativo
        for b in self.bolinhas:
            b['entity'].enabled = ativo

    def update(self, velocidade):
        if not self.ativo:
            return
        self.progresso += velocidade * time.dt
        for b in self.bolinhas:
            b['entity'].position = self._posicao_no_caminho(self.progresso + b['offset'])


class SistemaBolinhasHall:
    """Bolinhas atravessando a placa com desvio lateral proporcional a I*B
    (V_H ~ I*B, entao frac_hall usa a raiz do produto das duas fracoes).

    FATOR_DEFLEXAO_VISUAL exagera o efeito de proposito pra ficar visivel
    num experimento de bancada (fisicamente o desvio real seria bem menor).

    A curva de deflexao usa saturacao exponencial (1 - e^-k*t) em vez de
    crescimento linear: na fisica real o portador desvia rapido no comeco
    e depois so desliza em equilibrio perto da borda pelo resto do trajeto
    -- entao aqui ele passa a maior parte do percurso proximo da parede,
    nao so no instante final."""

    K_SATURACAO = 4.0
    MARGEM_PAREDE = 0.98  # o clamp final (x_min/x_max) ja protege 100% do fisico

    def __init__(self, caminho, indice_segmento_placa, x_centro, x_min, x_max,
                 z_min, z_max, b_max_mt, espacamento=0.25, cor=color.red):
        self.caminho = caminho
        self.indice_segmento_placa = indice_segmento_placa
        self.x_centro = x_centro
        self.x_min = x_min
        self.x_max = x_max
        self.b_max_mt = b_max_mt
        self.campo_b_mt = 0       # ja vem com sinal (polo invertido = negativo)
        self.frac_corrente = 0    # 0 a 1, proporcao da corrente atual
        self.sentido = 1          # 1 = corrente normal, -1 = invertida
        self.ativo = False
        self.progresso = 0

        # marcadores fixos de acumulacao: ate max_acumulados_atual vermelhos na parede
        # que o feixe atinge, e o mesmo tanto de azuis na parede oposta (o teto cresce
        # MARCADORES_POR_FAIXA a cada FAIXA_CORRENTE_MA de corrente)
        self.lado_atual = None       # 'max' ou 'min' -- qual parede esta acumulando agora
        self.contagem_acumulada = 0
        self.corrente_mA = 20        # espelha o default do slider; atualizado a cada frame
        self.max_acumulados_atual = self._calcular_max_acumulados()
        self.marcador_zs = [z_min + (i + 1) * (z_max - z_min) / (MAX_MARCADORES_POSSIVEL + 1)
                            for i in range(MAX_MARCADORES_POSSIVEL)]
        self.marcadores_vermelhos = [Entity(model='sphere', scale=0.09, color=color.red, enabled=False)
                                      for _ in range(MAX_MARCADORES_POSSIVEL)]
        self.marcadores_azuis = [Entity(model='sphere', scale=0.09, color=color.blue, enabled=False)
                                  for _ in range(MAX_MARCADORES_POSSIVEL)]

        self.segmentos = []
        acumulado = 0
        for i in range(len(caminho)):
            p1 = caminho[i]
            p2 = caminho[(i + 1) % len(caminho)]
            d = (p2 - p1).length()
            self.segmentos.append((p1, p2, d))
            if i == indice_segmento_placa:
                self.dist_inicio_placa = acumulado
                self.dist_fim_placa = acumulado + d
            acumulado += d
        self.comprimento_total = acumulado

        n_bolinhas = max(1, int(self.comprimento_total / espacamento))
        self.bolinhas = []
        for i in range(n_bolinhas):
            offset = i * espacamento
            b = Entity(model='sphere', scale=0.10, color=cor,
                       position=self._posicao_no_caminho(offset))
            b.enabled = False
            self.bolinhas.append({'entity': b, 'progresso': offset})

    def _posicao_no_caminho(self, distancia):
        distancia = distancia % self.comprimento_total

        if self.dist_inicio_placa <= distancia <= self.dist_fim_placa:
            t = (distancia - self.dist_inicio_placa) / (self.dist_fim_placa - self.dist_inicio_placa)
            t_local = t if self.sentido > 0 else (1 - t)

            p1, p2, _ = self.segmentos[self.indice_segmento_placa]
            z = p1.z + (p2.z - p1.z) * t

            frac_b = self.campo_b_mt / self.b_max_mt
            frac_hall = (abs(frac_b) * self.frac_corrente) ** 0.5
            if frac_b < 0:
                frac_hall = -frac_hall
            frac_hall *= FATOR_DEFLEXAO_VISUAL

            curva = 1 - math.exp(-self.K_SATURACAO * t_local)  # satura rapido, "cola" na parede

            alcance_max = self.MARGEM_PAREDE * (self.x_max - self.x_centro)
            desvio = self.sentido * frac_hall * curva * alcance_max
            x = clamp(self.x_centro + desvio, self.x_min, self.x_max)
            return Vec3(x, p1.y, z)

        acumulado = 0
        for p1, p2, d in self.segmentos:
            if acumulado + d >= distancia:
                t = (distancia - acumulado) / d if d > 0 else 0
                return p1 + (p2 - p1) * t
            acumulado += d
        return self.caminho[0]

    def _calcular_max_acumulados(self):
        # 1 faixa (MARCADORES_POR_FAIXA marcadores) garantida mesmo com pouca corrente;
        # a cada FAIXA_CORRENTE_MA adicionais, libera mais MARCADORES_POR_FAIXA
        faixas = max(1, int(self.corrente_mA // FAIXA_CORRENTE_MA))
        return faixas * MARCADORES_POR_FAIXA

    def _atualizar_marcadores(self):
        y = self.segmentos[self.indice_segmento_placa][0].y
        x_vermelho = self.x_max if self.lado_atual == 'max' else self.x_min
        x_azul = self.x_min if self.lado_atual == 'max' else self.x_max
        for i in range(len(self.marcadores_vermelhos)):
            ativo = i < self.contagem_acumulada
            self.marcadores_vermelhos[i].enabled = ativo
            self.marcadores_azuis[i].enabled = ativo
            if ativo:
                self.marcadores_vermelhos[i].position = Vec3(x_vermelho, y, self.marcador_zs[i])
                self.marcadores_azuis[i].position = Vec3(x_azul, y, self.marcador_zs[i])

    def set_ativo(self, ativo):
        self.ativo = ativo
        for b in self.bolinhas:
            b['entity'].enabled = ativo
        if not ativo:
            # desligou o sistema (ima subiu) -- zera o acumulo tambem
            self.lado_atual = None
            self.contagem_acumulada = 0
            for m in self.marcadores_vermelhos + self.marcadores_azuis:
                m.enabled = False

    def update(self, velocidade):
        if not self.ativo:
            return
        self.sentido = 1 if velocidade >= 0 else -1

        novo_max = self._calcular_max_acumulados()
        if novo_max != self.max_acumulados_atual:
            self.max_acumulados_atual = novo_max
            self.contagem_acumulada = min(self.contagem_acumulada, self.max_acumulados_atual)
            self._atualizar_marcadores()

        # sem campo B (ou sem corrente) nao existe efeito Hall de verdade --
        # zera na hora qualquer marcador que tenha ficado acumulado de antes,
        # em vez de deixar bolinha "fantasma" grudada na parede
        if self.campo_b_mt == 0 or self.frac_corrente == 0 or self.corrente_mA < 20:
            if self.lado_atual is not None or self.contagem_acumulada != 0:
                self.lado_atual = None
                self.contagem_acumulada = 0
                self._atualizar_marcadores()

        for bola in self.bolinhas:
            bola['progresso'] += velocidade * time.dt
            pos = self._posicao_no_caminho(bola['progresso'])

            # bateu na parede de verdade (x_min ou x_max) -> volta pra parte_preta
            bateu_na_parede = (math.isclose(pos.x, self.x_min, abs_tol=1e-3)
                                or math.isclose(pos.x, self.x_max, abs_tol=1e-3))
            if bateu_na_parede:
                lado = 'max' if math.isclose(pos.x, self.x_max, abs_tol=1e-3) else 'min'
                if lado != self.lado_atual:
                    self.lado_atual = lado
                    self.contagem_acumulada = 0
                self.contagem_acumulada = min(self.max_acumulados_atual, self.contagem_acumulada + 1)
                self._atualizar_marcadores()

                bola['progresso'] = 0
                pos = self.caminho[0]  # parte_preta

            bola['entity'].position = pos


caminho = [
    Vec3(-1.001, 0.2, -0.255),   # parte_preta
    Vec3(-1.001, 0.2, -1.367),   # quina1 (fio)
    Vec3(0.811,  0.2, -1.367),   # quina2 (fio)
    Vec3(0.811,  0.2, -0.739),   # entra na placa
    Vec3(0.811,  0.2,  0.994),   # sai da placa
    Vec3(0.811,  0.2,  1.433),   # quina3 (fio)
    Vec3(-1.007, 0.2,  1.415),   # quina4 (fio)
    Vec3(-1.007, 0.2,  0.336),   # parte_laranja
]

# placa tratada como plano (y constante), cantos reais definem limites em x/z
PLACA_QUINA1 = Vec3(0.208, 0.2, 0.906)
PLACA_QUINA2 = Vec3(1.346, 0.2, 0.906)
PLACA_QUINA3 = Vec3(1.346, 0.2, -0.637)
PLACA_QUINA4 = Vec3(0.211, 0.2, -0.637)

PLACA_X_MIN = min(PLACA_QUINA1.x, PLACA_QUINA2.x, PLACA_QUINA3.x, PLACA_QUINA4.x)
PLACA_X_MAX = max(PLACA_QUINA1.x, PLACA_QUINA2.x, PLACA_QUINA3.x, PLACA_QUINA4.x)
PLACA_Z_MIN = min(PLACA_QUINA1.z, PLACA_QUINA2.z, PLACA_QUINA3.z, PLACA_QUINA4.z)
PLACA_Z_MAX = max(PLACA_QUINA1.z, PLACA_QUINA2.z, PLACA_QUINA3.z, PLACA_QUINA4.z)
PLACA_CENTRO_X = (PLACA_X_MIN + PLACA_X_MAX) / 2
PLACA_CENTRO_Z = (PLACA_Z_MIN + PLACA_Z_MAX) / 2

X_CENTRO_CAMINHO = 0.811  # x do trecho reto de entrada/saida da corrente na placa
B_MIN, B_MAX = 0, 200     # mT -- ordem de grandeza de um ima de neodimio pequeno perto da superficie

sistema_circuito = SistemaBolinhasCircuito(caminho)
sistema_hall = SistemaBolinhasHall(
    caminho,
    indice_segmento_placa=3,
    x_centro=X_CENTRO_CAMINHO,
    x_min=PLACA_X_MIN,
    x_max=PLACA_X_MAX,
    z_min=PLACA_Z_MIN,
    z_max=PLACA_Z_MAX,
    b_max_mt=B_MAX,
)
sistema_atual = sistema_circuito

# ---- ima, centralizado sobre a placa ----
ima = Entity(
    model='models/ima.glb',   # <- troca pelo nome real do seu arquivo
    scale=0.02,
    position=(PLACA_CENTRO_X, 2.5, PLACA_CENTRO_Z),
)

# recentraliza o pivo de rotacao no centro visual real do modelo -- sem isso,
# ele gira em torno do canto onde o Tinkercad colocou a origem da malha, e
# "voa" pra outro lugar (ex: pro meio da placa) toda vez que voce roda
_bounds = ima.model.getTightBounds()
if _bounds:
    _centro_local = (_bounds[0] + _bounds[1]) / 2
    ima.model.setPos(-_centro_local)

Y_IMA_CIMA = 2.7
Y_IMA_BAIXO = 0.8
magneto_baixo = False
magneto_invertido = False  # False = polo original embaixo, True = tombado (N/S trocados)


def acionar_ima():
    global magneto_baixo
    magneto_baixo = not magneto_baixo

    if magneto_baixo:
        ima.animate_position((PLACA_CENTRO_X, Y_IMA_BAIXO, PLACA_CENTRO_Z), duration=1)
        sistema_circuito.set_ativo(False)
        invoke(ativar_hall, delay=1)
    else:
        ima.animate_position((PLACA_CENTRO_X, Y_IMA_CIMA, PLACA_CENTRO_Z), duration=1)
        sistema_hall.set_ativo(False)
        invoke(ativar_circuito, delay=1)


def ativar_hall():
    global sistema_atual
    sistema_hall.set_ativo(True)
    sistema_atual = sistema_hall


def ativar_circuito():
    global sistema_atual
    sistema_circuito.set_ativo(True)
    sistema_atual = sistema_circuito


def flip_ima():
    """Tomba o ima (troca qual polo aponta pra placa) -- se no seu modelo o
    eixo N/S estiver alinhado com X ou Y em vez de Z, troca aqui embaixo."""
    global magneto_invertido
    magneto_invertido = not magneto_invertido
    ima.animate_rotation_z(ima.rotation_z + 180, duration=0.6)


# ---- sentido da corrente ----
sentido_corrente = 1
texto_sentido = Text(text='Sentido: normal', position=(-0.08, -0.15), scale=1.2)


def inverter_corrente():
    global sentido_corrente
    sentido_corrente *= -1
    texto_sentido.text = 'Sentido: normal' if sentido_corrente > 0 else 'Sentido: invertido'


def input(key):
    if key == 'm':
        acionar_ima()
    if key == 'i':
        inverter_corrente()
    if key == 'f':
        flip_ima()


# ---- controles, parte inferior da tela ----
corrente_slider = Slider(min=CORRENTE_MIN_MA, max=CORRENTE_MAX_MA, default=20, step=1, dynamic=True)
corrente_slider.x = 0
corrente_slider.y = -0.35
texto_corrente = Text(text='Corrente: 20 mA', position=(-0.08, -0.28), scale=1.3)

b_slider = Slider(min=B_MIN, max=B_MAX, default=50, step=10, dynamic=True)
b_slider.x = 0
b_slider.y = -0.48
texto_b = Text(text='Campo B: 50 mT', position=(-0.08, -0.41), scale=1.3)

texto_voltimetro = Text(text='Voltimetro (V_H): 0 nV', position=(-0.15, 0.46), scale=1.5, origin=(0, 0))


def formatar_tensao(v_volts):
    """Escolhe a unidade (nV/uV/mV) automaticamente conforme a ordem de grandeza."""
    v_abs = abs(v_volts)
    if v_abs < 1e-6:
        return f'{v_volts * 1e9:.2f} nV'
    elif v_abs < 1e-3:
        return f'{v_volts * 1e6:.2f} uV'
    else:
        return f'{v_volts * 1e3:.2f} mV'

VELOCIDADE_MIN = 0.5
VELOCIDADE_MAX = 3.0


def update():
    corrente_mA = corrente_slider.value
    texto_corrente.text = f'Corrente: {corrente_mA:.0f} mA'
    frac = (corrente_mA - CORRENTE_MIN_MA) / (CORRENTE_MAX_MA - CORRENTE_MIN_MA)
    velocidade = (VELOCIDADE_MIN + frac * (VELOCIDADE_MAX - VELOCIDADE_MIN)) * sentido_corrente

    campo_mt = b_slider.value
    texto_b.text = f'Campo B: {campo_mt:.0f} mT'
    sinal_polo = -1 if magneto_invertido else 1
    sistema_hall.campo_b_mt = campo_mt * sinal_polo
    sistema_hall.frac_corrente = frac
    sistema_hall.corrente_mA = corrente_mA

    # V_H = I*B / (n*e*t), com sinal de corrente e de polo do ima ja embutidos
    # -- se o ima nao esta abaixado sobre a placa, nao ha campo B atuando de verdade
    corrente_A_sinal = (corrente_mA / 1000) * sentido_corrente
    campo_mt_efetivo = campo_mt if magneto_baixo else 0
    campo_T_sinal = (campo_mt_efetivo / 1000) * sinal_polo
    v_hall = (corrente_A_sinal * campo_T_sinal) / (N_PORTADORES_COBRE * CARGA_ELETRON * ESPESSURA_PLACA_M)
    texto_voltimetro.text = f'Voltimetro (V_H): {formatar_tensao(v_hall)}'

    sistema_atual.update(velocidade)


app.run()