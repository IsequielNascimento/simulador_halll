"""Animacao dos portadores no circuito e do acumulo nas bordas da placa."""
import math

from ursina import Entity, Vec3, clamp, color

from .config import (
    FATOR_DEFLEXAO_VISUAL, FAIXA_CORRENTE_MA,
    MARCADORES_POR_FAIXA, MAX_MARCADORES_POSSIVEL,
)


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

    def update(self, velocidade, delta_t):
        if not self.ativo:
            return
        self.progresso += velocidade * delta_t
        for b in self.bolinhas:
            b['entity'].position = self._posicao_no_caminho(self.progresso + b['offset'])


class SistemaBolinhasHall:
    """Trajetorias esquematicas com desvio lateral e marcadores nas bordas.

    O desvio usa a raiz das fracoes de corrente/campo e saturacao exponencial.
    E uma animacao didatica; a tensao Hall e calculada separadamente em fisica.
    """

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
            # Eletron: q < 0. Com v em +Z e B em -Y (N voltado para
            # a placa), q(v x B) aponta para -X.
            desvio = -self.sentido * frac_hall * curva * alcance_max
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

    def update(self, velocidade, delta_t):
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
            bola['progresso'] += velocidade * delta_t
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

