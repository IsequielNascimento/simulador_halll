"""Indicadores dos vetores e projecao dependente da camera."""
import math

from ursina import Entity, Text, Vec4, camera, clamp, color, load_model, scene, window

from .config import PLACA, VETORES
from .fisica import direcoes_vetores_eletron


class IndicadorVetor:
    """GLBs pequenos na UI, orientados pela projecao de uma direcao 3D."""

    def __init__(self, nome, posicao, cor):
        self.nome = nome
        self.ancora = Entity(position=posicao)
        self.grupo = Entity(parent=camera.ui)
        self.giro = Entity(parent=self.grupo)
        self.seta = self._modelo('Arrow', self.giro, cor, 0.045)
        # A ponta importada e -Z. Deitada em XY, passa a apontar para +Y.
        self.seta.rotation_x = 90
        self.entrada = self._modelo('VectorIn', self.grupo, cor, 0.030)
        self.saida = self._modelo('VectorOut', self.grupo, cor, 0.030)
        self.fundo = Entity(parent=self.grupo, model='quad',
                            position=(0.079, 0, 0.01), scale=(0.105, 0.035),
                            color=Vec4(0.047, 0.063, 0.086, 0.96))
        Entity(parent=self.grupo, model='quad', position=(0.028, 0, -0.01),
               scale=(0.003, 0.035), color=cor)
        self.rotulo = Text(parent=self.grupo, text=nome, color=color.white,
                           position=(0.079, 0, -0.02), origin=(0, 0), scale=0.85)
        self.modo = 'seta'

    @staticmethod
    def _modelo(nome, pai, cor, tamanho):
        entidade = Entity(parent=pai,
                          model=load_model(f'models/{nome}.glb', use_deepcopy=True),
                          color=cor, unlit=True, double_sided=True)
        minimo, maximo = entidade.model.getTightBounds()
        entidade.model.setPos(-(minimo + maximo) / 2)
        entidade.scale = tamanho / max(maximo - minimo)
        return entidade

    def update(self, direcao, ativo):
        local = camera.getRelativeVector(scene, direcao).normalized()
        # Histerese: entra no modo ponto/cruz a ~28 graus do eixo visual,
        # e so volta a seta alem de ~35 graus, evitando piscadas no limite.
        limite = 0.82 if self.modo in ('entrada', 'saida') else 0.88
        if abs(local.z) >= limite:
            self.modo = 'entrada' if local.z > 0 else 'saida'
        else:
            self.modo = 'seta'
            self.giro.rotation_z = math.degrees(math.atan2(local.x, local.y))
        self.seta.enabled = ativo and self.modo == 'seta'
        self.entrada.enabled = ativo and self.modo == 'entrada'
        self.saida.enabled = ativo and self.modo == 'saida'
        texto = self.nome if ativo else f'{self.nome} = 0'
        if self.rotulo.text != texto:
            self.rotulo.text = texto
        self.grupo.enabled = camera.getRelativePoint(scene, self.ancora.position).z > 0
        self.grupo.position = self.ancora.screen_position


class VetoresEletron:
    """Tres indicadores ancorados a placa, legiveis de qualquer angulo."""

    def __init__(self):
        self.indicadores = {
            chave: IndicadorVetor(rotulo, (PLACA.maximo.x + 0.48, PLACA.minimo.y + 0.16, z), cor)
            for chave, (rotulo, descricao, cor, z) in VETORES.items()
        }

    def _separar_indicadores(self):
        # Na vista lateral as ancoras podem se projetar sobre o mesmo ponto.
        # Separa os conjuntos icone/rotulo sem alterar as direcoes fisicas.
        visiveis = [v.grupo for v in self.indicadores.values() if v.grupo.enabled]
        for grupo in visiveis:
            grupo.x = clamp(grupo.x, -window.aspect_ratio / 2 + 0.04,
                            window.aspect_ratio / 2 - 0.15)
            grupo.y = clamp(grupo.y, -0.08, 0.38)
        posicionados = []
        for grupo in sorted(visiveis, key=lambda g: g.y, reverse=True):
            for anterior in posicionados:
                if abs(grupo.x - anterior.x) < 0.16 and abs(grupo.y - anterior.y) < 0.06:
                    grupo.y = anterior.y - 0.06
            posicionados.append(grupo)
        if visiveis:
            deslocamento = max(0, -0.08 - min(g.y for g in visiveis))
            for grupo in visiveis:
                grupo.y += deslocamento

    def update(self, sentido_movimento, sinal_polo, campo_ativo):
        direcoes = direcoes_vetores_eletron(sentido_movimento, sinal_polo)
        for chave, direcao in zip(('velocidade', 'campo', 'forca'), direcoes):
            self.indicadores[chave].update(direcao, chave == 'velocidade' or campo_ativo)
        self._separar_indicadores()
