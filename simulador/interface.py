"""Controles, ajuda e leituras da simulacao."""
from ursina import Entity, Text, Vec4, camera, color
from ursina.prefabs.slider import Slider

from .config import B_MAX, B_MIN, CORRENTE_MAX_MA, CORRENTE_MIN_MA


def formatar_tensao(v_volts):
    """Escolhe a unidade (nV/uV/mV) automaticamente conforme a ordem de grandeza."""
    v_abs = abs(v_volts)
    if v_abs < 1e-6:
        return f'{v_volts * 1e9:.2f} nV'
    elif v_abs < 1e-3:
        return f'{v_volts * 1e6:.2f} uV'
    else:
        return f'{v_volts * 1e3:.2f} mV'


class InterfaceSimulador:
    def __init__(self):
        self.texto_sentido = Text(text='Sentido: normal', position=(-0.08, -0.15), scale=1.2)
        self.texto_cooldown = Text(text='', position=(-0.85, -0.47), scale=1.1, color=color.yellow)
        self.corrente_slider = Slider(min=CORRENTE_MIN_MA, max=CORRENTE_MAX_MA,
                                      default=20, step=1, dynamic=True, x=0, y=-0.35)
        self.texto_corrente = Text(text='Corrente: 20 mA', position=(-0.08, -0.28), scale=1.3)
        self.b_slider = Slider(min=B_MIN, max=B_MAX, default=50, step=10,
                               dynamic=True, x=0, y=-0.48)
        self.texto_b = Text(text='Campo B: 50 mT', position=(-0.08, -0.41), scale=1.3)
        self.texto_voltimetro = Text(text='Voltimetro (V_H): 0 nV', position=(-0.15, 0.46),
                                    scale=1.5, origin=(0, 0))
        self._criar_ajuda()
        self._criar_legenda()

    @property
    def corrente_ma(self):
        return self.corrente_slider.value

    @property
    def campo_mt(self):
        return self.b_slider.value

    def alternar_ajuda(self):
        self.popup_comandos.enabled = not self.popup_comandos.enabled

    def atualizar(self, tensao, sentido, cooldown):
        self.texto_corrente.text = f'Corrente: {self.corrente_ma:.0f} mA'
        self.texto_b.text = f'Campo B: {self.campo_mt:.0f} mT'
        self.texto_voltimetro.text = f'Voltimetro (V_H): {formatar_tensao(tensao)}'
        self.texto_sentido.text = 'Sentido: normal' if sentido > 0 else 'Sentido: invertido'
        self.texto_cooldown.text = f'Cooldown: {cooldown:.1f}s' if cooldown > 0 else ''

    def _criar_ajuda(self):
        self.popup_comandos = Entity(parent=camera.ui, enabled=True)
        Entity(parent=self.popup_comandos, model='quad', scale=(0.6, 0.42),
               color=Vec4(0, 0, 0, 210 / 255), z=0.1)
        Text(parent=self.popup_comandos,
             text=('COMANDOS\n\n'
                   'M - descer / subir o ima\n'
                   'I - inverter sentido da corrente\n'
                   'F - virar o ima (troca N/S)\n\n'
                   'H - mostrar / esconder esta ajuda'),
             position=(-0.26, 0.17), scale=1.2, line_height=1.7)

    def _criar_legenda(self):
        Text(text='Vetores do eletron (e-)', position=(-0.85, 0.40), scale=1.05)
        Text(text='v_e: velocidade', position=(-0.85, 0.36), color=color.lime)
        Text(text='F_B: forca magnetica', position=(-0.85, 0.32), color=color.orange)
        Text(text='B: campo magnetico', position=(-0.85, 0.28), color=color.azure)
        Text(text='Cruz: entrando no plano | Ponto: saindo do plano',
             position=(-0.85, 0.20), scale=0.75)
