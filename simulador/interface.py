"""Controles, ajuda e leituras da simulacao."""
from ursina import Entity, Text, Vec4, camera, color, window
from ursina.prefabs.slider import Slider

from .config import B_MAX, B_MIN, CORRENTE_MAX_MA, CORRENTE_MIN_MA, VETORES


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
        # Uma faixa compacta concentra ajustes e estado, liberando a cena.
        Entity(parent=camera.ui, model='quad', position=(0, -0.385, 0.1),
               scale=(1.12, 0.18), color=Vec4(0.10, 0.11, 0.12, 0.96))
        self.dica_ajuda = Text(text='H - Ajuda', position=(0.39, -0.435), scale=0.75)
        self.texto_sentido = Text(text='Sentido: normal', position=(-0.5, -0.435), scale=0.8)
        self.texto_cooldown = Text(text='', position=(-0.13, -0.435), scale=0.75,
                                  color=color.light_gray)
        self.corrente_slider = Slider(min=CORRENTE_MIN_MA, max=CORRENTE_MAX_MA,
                                      default=20, step=1, dynamic=True,
                                      x=-0.49, y=-0.375, scale=0.82)
        self.texto_corrente = Text(text='Corrente: 20 mA', position=(-0.5, -0.32), scale=0.95)
        self.b_slider = Slider(min=B_MIN, max=B_MAX, default=50, step=10,
                               dynamic=True, x=0.08, y=-0.375, scale=0.82)
        self.texto_b = Text(text='Campo B: 50 mT', position=(0.07, -0.32), scale=0.95)
        for slider in (self.corrente_slider, self.b_slider):
            # Os valores ja aparecem nos rotulos, com suas unidades.
            slider.knob.text_entity.enabled = False
        self.leituras = Entity(parent=camera.ui)
        self.texto_voltimetro = Text(parent=self.leituras, text='Voltimetro (V_H): 0 nV',
                                    y=0.45, scale=1.05)
        self._criar_ajuda()
        self._criar_legenda()
        self._posicionar_leituras()

    def _posicionar_leituras(self):
        self.leituras.x = -window.aspect_ratio / 2 + 0.04

    @property
    def corrente_ma(self):
        return self.corrente_slider.value

    @property
    def campo_mt(self):
        return self.b_slider.value

    def alternar_ajuda(self):
        self.popup_comandos.enabled = not self.popup_comandos.enabled
        self.dica_ajuda.text = 'H - Fechar' if self.popup_comandos.enabled else 'H - Ajuda'

    def atualizar(self, tensao, sentido, cooldown):
        self._posicionar_leituras()
        self.texto_corrente.text = f'Corrente: {self.corrente_ma:.0f} mA'
        self.texto_b.text = f'Campo B: {self.campo_mt:.0f} mT'
        self.texto_voltimetro.text = f'Voltimetro (V_H): {formatar_tensao(tensao)}'
        self.texto_sentido.text = 'Sentido: normal' if sentido > 0 else 'Sentido: invertido'
        self.texto_cooldown.text = f'Aguarde {cooldown:.1f}s' if cooldown > 0 else ''

    def _criar_ajuda(self):
        self.popup_comandos = Entity(parent=camera.ui, enabled=False, z=-1)
        Entity(parent=self.popup_comandos, model='quad', scale=(0.64, 0.38),
               color=Vec4(0.10, 0.11, 0.12, 1), z=0.1)
        Text(parent=self.popup_comandos,
             text=('COMANDOS\n\n'
                   'M - descer / subir o ima\n'
                   'I - inverter a corrente\n'
                   'F - inverter os polos\n\n'
                   'Botao direito - girar a camera\n'
                   'Roda do mouse - aproximar / afastar\n\n'
                   'H - fechar ajuda'),
             position=(-0.27, 0.15), scale=0.85, line_height=1.25)

    def _criar_legenda(self):
        Text(parent=self.leituras, text='Vetores do eletron', y=0.35,
             scale=0.8, color=color.light_gray)
        for i, (rotulo, descricao, cor) in enumerate(VETORES.values()):
            Text(parent=self.leituras, text=f'{rotulo}: {descricao}',
                 y=0.315 - i * 0.033, scale=0.85, color=cor)
        Text(parent=self.leituras,
             text='Cruz: entrando no plano\nPonto: saindo do plano',
             y=0.20, scale=0.7, color=color.light_gray)
