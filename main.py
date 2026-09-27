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
COOLDOWN_TECLAS = 1.0        # segundos de espera entre acionar M / I / F (evita clique duplo/simultaneo)
POPUP_DURACAO_INICIAL = 2.0  # segundos que o popup de comandos fica visivel sozinho, antes de sumir
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
    atualizar_indicador_campo()


def ativar_circuito():
    global sistema_atual
    sistema_circuito.set_ativo(True)
    sistema_atual = sistema_circuito
    atualizar_indicador_campo()


def flip_ima():
    """Tomba o ima (troca qual polo aponta pra placa) -- se no seu modelo o
    eixo N/S estiver alinhado com X ou Y em vez de Z, troca aqui embaixo."""
    global magneto_invertido
    magneto_invertido = not magneto_invertido
    ima.animate_rotation_z(ima.rotation_z + 180, duration=0.6)
    invoke(atualizar_indicador_campo, delay=0.6)  # espera a animacao terminar


# ---- indicador de campo B espalhado pela placa: uma grade de aneis (so ligam
# com o ima), cada um com um simbolo que troca conforme a polaridade ----
Y_MARCADOR = 0.25  # bem rente a placa
GRADE_CAMPO_COLUNAS = 3
GRADE_CAMPO_LINHAS = 2
MARGEM_GRADE = 0.15  # afasta a grade um pouco das bordas da placa


def _gerar_pontos_grade(x_min, x_max, z_min, z_max, colunas, linhas, margem):
    pontos = []
    largura = max(x_max - x_min - 2 * margem, 0.01)
    profundidade = max(z_max - z_min - 2 * margem, 0.01)
    for c in range(colunas):
        for l in range(linhas):
            tx = (c + 0.5) / colunas
            tz = (l + 0.5) / linhas
            x = x_min + margem + tx * largura
            z = z_min + margem + tz * profundidade
            pontos.append((x, z))
    return pontos


def _criar_com_pivo_proprio(caminho_modelo, x, z, escala=0.02):
    """Cria a Entity e recentraliza o pivo dela (nao confia no y/origem que
    veio da exportacao -- cada peca pode ter um offset diferente)."""
    e = Entity(model=caminho_modelo, scale=escala, position=(x, Y_MARCADOR, z), enabled=False)
    b = e.model.getTightBounds()
    if b:
        c = (b[0] + b[1]) / 2
        e.model.setPos(-c)
    return e


_pontos_grade_campo = _gerar_pontos_grade(
    PLACA_X_MIN, PLACA_X_MAX, PLACA_Z_MIN, PLACA_Z_MAX,
    GRADE_CAMPO_COLUNAS, GRADE_CAMPO_LINHAS, MARGEM_GRADE
)

ESCALA_INDICADOR_CAMPO = 0.012  # era 0.02 (mesma escala do resto) -- ajusta aqui se quiser maior/menor

aneis_campo_b = [_criar_com_pivo_proprio('models/anel_b.glb', x, z, ESCALA_INDICADOR_CAMPO) for x, z in _pontos_grade_campo]
marcadores_positivos = [_criar_com_pivo_proprio('models/mais.glb', x, z, ESCALA_INDICADOR_CAMPO) for x, z in _pontos_grade_campo]
marcadores_negativos = [_criar_com_pivo_proprio('models/bola.glb', x, z, ESCALA_INDICADOR_CAMPO) for x, z in _pontos_grade_campo]

# ---- espacinho pra calibrar a rotacao do anel na mao -- mexe nos 3 numeros
# abaixo (em graus) e testa ate o anel ficar do jeito certo ----
ANGULO_ANEL_X = 0
ANGULO_ANEL_Y = 90
ANGULO_ANEL_Z = 0
for _anel in aneis_campo_b:
    _anel.rotation = (ANGULO_ANEL_X, ANGULO_ANEL_Y, ANGULO_ANEL_Z)


def atualizar_indicador_campo():
    ativo = magneto_baixo
    for anel in aneis_campo_b:
        anel.enabled = ativo
    for m in marcadores_positivos:
        m.enabled = ativo and not magneto_invertido
    for m in marcadores_negativos:
        m.enabled = ativo and magneto_invertido


# ---- setas de corrente, uma em cada quina do FIO (nao da placa) ----
Y_SETA = 0.4  # separado do Y_MARCADOR do campo -- nao precisam estar na mesma altura

# angulo (rotation_y) calibrado manualmente por seta -- o calculo "puro" pela
# direcao do segmento (0=+x, 90=+z, 180=-x, 270=-z) nao bate certinho com o
# jeito que o seta.glb foi exportado, entao cada seta tem seu proprio angulo
# pro estado normal e pro estado invertido (tecla I). Se alguma ainda ficar
# torta, ajusta só o numero dela aqui embaixo.
# ordem: [seta1 (quina1), seta2 (quina2), seta3 (quina3), seta4 (quina4)]
_quinas_fio = [caminho[1], caminho[2], caminho[5], caminho[6]]  # quina1/2/3/4 do fio
ANGULOS_SETAS_NORMAL = [0, 270, 180, 90]
ANGULOS_SETAS_INVERTIDO = [270, 180, 90, 0]

setas_corrente = []
for _q in _quinas_fio:
    _seta = Entity(model='models/seta.glb', scale=0.02, position=(_q.x, Y_SETA, _q.z))
    # cada seta recentraliza o proprio pivo (nao confia no y/origem que o
    # Tinkercad gravou na malha -- cada peca pode ter um offset diferente,
    # igual aconteceu com o ima)
    _b = _seta.model.getTightBounds()
    if _b:
        _c = (_b[0] + _b[1]) / 2
        _seta.model.setPos(-_c)
    setas_corrente.append(_seta)


def atualizar_setas_corrente():
    angulos = ANGULOS_SETAS_NORMAL if sentido_corrente > 0 else ANGULOS_SETAS_INVERTIDO
    for _seta, _angulo in zip(setas_corrente, angulos):
        _seta.rotation_y = _angulo


# ---- sentido da corrente ----
sentido_corrente = 1
texto_sentido = Text(text='Sentido: normal', position=(-0.08, -0.15), scale=1.2)


def inverter_corrente():
    global sentido_corrente
    sentido_corrente *= -1
    texto_sentido.text = 'Sentido: normal' if sentido_corrente > 0 else 'Sentido: invertido'
    atualizar_setas_corrente()


atualizar_setas_corrente()  # orientacao inicial das setas, condizente com sentido_corrente = 1


# ---- popup de comandos (H mostra/esconde -- some sozinho depois de POPUP_DURACAO_INICIAL) ----
popup_comandos = Entity(parent=camera.ui, enabled=True)
popup_tempo_restante = POPUP_DURACAO_INICIAL
Entity(parent=popup_comandos, model='quad', scale=(0.6, 0.42),
       color=color.rgba(0, 0, 0, 210), z=0.1)
Text(
    parent=popup_comandos,
    text=('COMANDOS\n\n'
          'M - descer / subir o ima\n'
          'I - inverter sentido da corrente\n'
          'F - virar o ima (troca N/S)\n\n'
          'H - mostrar / esconder esta ajuda'),
    position=(-0.26, 0.17), scale=1.2, line_height=1.7
)

# ---- cooldown das teclas M/I/F, mostrado no canto inferior esquerdo ----
cooldown_restante = 0.0
texto_cooldown = Text(text='', position=(-0.85, -0.47), scale=1.1, color=color.yellow)


def pode_acionar():
    return cooldown_restante <= 0


def iniciar_cooldown():
    global cooldown_restante
    cooldown_restante = COOLDOWN_TECLAS


def input(key):
    if key == 'h':
        popup_comandos.enabled = not popup_comandos.enabled
        return

    if key in ('m', 'i', 'f') and not pode_acionar():
        return  # ainda em cooldown -- ignora, impede acionar mais de um por vez

    if key == 'm':
        acionar_ima()
        iniciar_cooldown()
    if key == 'i':
        inverter_corrente()
        iniciar_cooldown()
    if key == 'f':
        flip_ima()
        iniciar_cooldown()


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
    global cooldown_restante, popup_tempo_restante
    if popup_tempo_restante > 0:
        popup_tempo_restante -= time.dt
        if popup_tempo_restante <= 0:
            popup_comandos.enabled = False

    if cooldown_restante > 0:
        cooldown_restante = max(0.0, cooldown_restante - time.dt)
    texto_cooldown.text = f'Cooldown: {cooldown_restante:.1f}s' if cooldown_restante > 0 else ''

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