"""Cena e estado da simulacao; conecta os controles, particulas e vetores."""
from ursina import EditorCamera, Entity, camera, color, invoke, time

from . import config
from .fisica import calcular_tensao_hall
from .interface import InterfaceSimulador
from .particulas import Percurso, SistemaBolinhasCircuito, SistemaBolinhasHall
from .vetores import VetoresEletron


class SimulacaoHall(Entity):
    """O Ursina chama input e update desta entidade automaticamente."""

    def __init__(self):
        super().__init__()
        self.magneto_baixo = False
        self.magneto_invertido = False
        self.sentido_corrente = 1
        self.cooldown_restante = 0.0

        self._criar_cena()
        self.interface = InterfaceSimulador()
        self.vetores_eletron = VetoresEletron()
        percurso = Percurso(config.CAMINHO)
        self.sistema_circuito = SistemaBolinhasCircuito(percurso)
        self.sistema_hall = SistemaBolinhasHall(percurso, config.PLACA, config.B_MAX)
        self.sistema_atual = self.sistema_circuito

    def _criar_cena(self):
        self.camera_editor = EditorCamera(rotation=(45, 0, 0), position=(0.35, -0.4, 0))
        camera.z = -13
        self.camera_editor.target_z = camera.z
        self.modelo = Entity(model='models/placa_bateria_fio.glb', scale=0.02)
        self.chao = Entity(model='plane', scale=20, color=color.dark_gray, y=-1)
        self.ima = Entity(model='models/ima.glb', scale=0.02,
                          position=(config.PLACA.centro_x, 2.5, config.PLACA.centro_z))
        # Centraliza o pivo para o ima girar sobre si mesmo.
        limites = self.ima.model.getTightBounds()
        if limites:
            self.ima.model.setPos(-(limites[0] + limites[1]) / 2)

    def input(self, key):
        if key == 'h':
            self.interface.alternar_ajuda()
            return
        if self.cooldown_restante > 0:
            return
        if key == 'm':
            self._acionar_ima()
        elif key == 'i':
            self.sentido_corrente *= -1
        elif key == 'f':
            self.magneto_invertido = not self.magneto_invertido
            self.ima.animate_rotation_z(self.ima.rotation_z + 180, duration=0.6)
        else:
            return
        self.cooldown_restante = config.COOLDOWN_TECLAS

    def _acionar_ima(self):
        self.magneto_baixo = not self.magneto_baixo
        altura = config.Y_IMA_BAIXO if self.magneto_baixo else config.Y_IMA_CIMA
        self.ima.animate_position(
            (config.PLACA.centro_x, altura, config.PLACA.centro_z), duration=1)
        if self.magneto_baixo:
            self.sistema_circuito.set_ativo(False)
            invoke(self._ativar_hall, delay=1)
        else:
            self.sistema_hall.set_ativo(False)
            invoke(self._ativar_circuito, delay=1)

    def _ativar_hall(self):
        self.sistema_hall.set_ativo(True)
        self.sistema_atual = self.sistema_hall

    def _ativar_circuito(self):
        self.sistema_circuito.set_ativo(True)
        self.sistema_atual = self.sistema_circuito

    def update(self):
        self.cooldown_restante = max(0.0, self.cooldown_restante - time.dt)
        corrente_ma = self.interface.corrente_ma
        campo_mt = self.interface.campo_mt
        sinal_polo = -1 if self.magneto_invertido else 1
        fracao = ((corrente_ma - config.CORRENTE_MIN_MA)
                  / (config.CORRENTE_MAX_MA - config.CORRENTE_MIN_MA))
        velocidade = (config.VELOCIDADE_MIN
                      + fracao * (config.VELOCIDADE_MAX - config.VELOCIDADE_MIN))
        velocidade *= self.sentido_corrente

        self.sistema_hall.campo_b_mt = campo_mt * sinal_polo
        self.sistema_hall.frac_corrente = fracao
        self.sistema_hall.corrente_mA = corrente_ma
        campo_efetivo = campo_mt if self.magneto_baixo else 0
        tensao = calcular_tensao_hall(
            corrente_ma, campo_efetivo, self.sentido_corrente, sinal_polo)
        self.interface.atualizar(tensao, self.sentido_corrente, self.cooldown_restante)
        self.sistema_atual.update(velocidade, time.dt)
        self.vetores_eletron.update(
            self.sentido_corrente, sinal_polo,
            self.magneto_baixo and self.sistema_hall.ativo and campo_mt > 0,
        )
