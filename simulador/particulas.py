"""Animacao dos portadores no circuito e do acumulo nas bordas da placa."""
import math

from ursina import Entity, Vec3, clamp, color

from .config import (
    FATOR_DEFLEXAO_VISUAL, FAIXA_CORRENTE_MA,
    MARCADORES_POR_FAIXA, MAX_MARCADORES_POSSIVEL,
)


class Percurso:
    """Segmentos e interpolacao de um caminho fechado, compartilhados pelos sistemas."""

    def __init__(self, pontos):
        self.pontos = pontos
        self.segmentos = []
        self.inicios = []
        self.comprimento_total = 0
        for i, p1 in enumerate(pontos):
            p2 = pontos[(i + 1) % len(pontos)]
            comprimento = (p2 - p1).length()
            self.inicios.append(self.comprimento_total)
            self.segmentos.append((p1, p2, comprimento))
            self.comprimento_total += comprimento

    def intervalo(self, indice):
        inicio = self.inicios[indice]
        return inicio, inicio + self.segmentos[indice][2]

    def posicao(self, distancia):
        distancia %= self.comprimento_total
        for inicio, (p1, p2, comprimento) in zip(self.inicios, self.segmentos):
            if inicio + comprimento >= distancia:
                t = (distancia - inicio) / comprimento if comprimento > 0 else 0
                return p1 + (p2 - p1) * t
        return self.pontos[0]


class SistemaBolinhasCircuito:
    """Criacao, visibilidade e movimento comuns aos dois sistemas de particulas."""

    def __init__(self, percurso, espacamento=0.25, cor=color.red, ativo=True):
        self.percurso = percurso
        self.ativo = ativo
        self.progresso = 0
        self.bolinhas = []
        for i in range(max(1, int(percurso.comprimento_total / espacamento))):
            offset = i * espacamento
            entidade = Entity(model='sphere', scale=0.10, color=cor, enabled=ativo,
                              position=self._posicao_no_caminho(offset))
            self.bolinhas.append({'entity': entidade, 'offset': offset, 'progresso': offset})

    def _posicao_no_caminho(self, distancia):
        return self.percurso.posicao(distancia)

    def set_ativo(self, ativo):
        self.ativo = ativo
        for bola in self.bolinhas:
            bola['entity'].enabled = ativo

    def update(self, velocidade, delta_t):
        if not self.ativo:
            return
        deslocamento = velocidade * delta_t
        self.progresso += deslocamento
        for bola in self.bolinhas:
            bola['entity'].position = self._avancar_bola(bola, deslocamento)

    def _avancar_bola(self, bola, deslocamento):
        return self._posicao_no_caminho(self.progresso + bola['offset'])


class SistemaBolinhasHall(SistemaBolinhasCircuito):
    """Trajetorias esquematicas com desvio lateral e marcadores nas bordas.

    O desvio usa a raiz das fracoes de corrente/campo e saturacao exponencial.
    E uma animacao didatica; a tensao Hall e calculada separadamente em fisica.
    """

    K_SATURACAO = 4.0
    MARGEM_PAREDE = 0.98  # o clamp final (x_min/x_max) ja protege 100% do fisico

    def __init__(self, percurso, placa, b_max_mt, espacamento=0.25, cor=color.red):
        self.placa = placa
        self.dist_inicio_placa, self.dist_fim_placa = percurso.intervalo(placa.segmento_caminho)
        self.b_max_mt = b_max_mt
        self.campo_b_mt = 0       # ja vem com sinal (polo invertido = negativo)
        self.frac_corrente = 0    # 0 a 1, proporcao da corrente atual
        self.sentido = 1          # 1 = corrente normal, -1 = invertida

        # marcadores fixos de acumulacao: ate max_acumulados_atual vermelhos na parede
        # que o feixe atinge, e o mesmo tanto de azuis na parede oposta (o teto cresce
        # MARCADORES_POR_FAIXA a cada FAIXA_CORRENTE_MA de corrente)
        self.lado_atual = None       # 'max' ou 'min' -- qual parede esta acumulando agora
        self.contagem_acumulada = 0
        self.corrente_mA = 20        # espelha o default do slider; atualizado a cada frame
        self.max_acumulados_atual = self._calcular_max_acumulados()
        self.marcador_zs = [placa.minimo.z + (i + 1) * (placa.maximo.z - placa.minimo.z) / (MAX_MARCADORES_POSSIVEL + 1)
                            for i in range(MAX_MARCADORES_POSSIVEL)]
        self.marcadores_vermelhos = [Entity(model='sphere', scale=0.09, color=color.red, enabled=False)
                                      for _ in range(MAX_MARCADORES_POSSIVEL)]
        self.marcadores_azuis = [Entity(model='sphere', scale=0.09, color=color.blue, enabled=False)
                                  for _ in range(MAX_MARCADORES_POSSIVEL)]

        super().__init__(percurso, espacamento, cor, ativo=False)

    def _posicao_no_caminho(self, distancia):
        distancia_original = distancia
        distancia = distancia % self.percurso.comprimento_total

        if self.dist_inicio_placa <= distancia <= self.dist_fim_placa:
            t = (distancia - self.dist_inicio_placa) / (self.dist_fim_placa - self.dist_inicio_placa)
            t_local = t if self.sentido > 0 else (1 - t)

            p1, p2, _ = self.percurso.segmentos[self.placa.segmento_caminho]
            z = p1.z + (p2.z - p1.z) * t

            frac_b = self.campo_b_mt / self.b_max_mt
            frac_hall = (abs(frac_b) * self.frac_corrente) ** 0.5
            if frac_b < 0:
                frac_hall = -frac_hall
            frac_hall *= FATOR_DEFLEXAO_VISUAL

            curva = 1 - math.exp(-self.K_SATURACAO * t_local)  # satura rapido, "cola" na parede

            alcance_max = self.MARGEM_PAREDE * (self.placa.maximo.x - self.placa.eixo_corrente)
            # Eletron: q < 0. Com v em +Z e B em -Y (N voltado para
            # a placa), q(v x B) aponta para -X.
            desvio = -self.sentido * frac_hall * curva * alcance_max
            x = clamp(self.placa.eixo_corrente + desvio, self.placa.minimo.x, self.placa.maximo.x)
            return Vec3(x, p1.y, z)

        # Normaliza apenas uma vez, preservando o arredondamento no fechamento do circuito.
        return super()._posicao_no_caminho(distancia_original)

    def _calcular_max_acumulados(self):
        # 1 faixa (MARCADORES_POR_FAIXA marcadores) garantida mesmo com pouca corrente;
        # a cada FAIXA_CORRENTE_MA adicionais, libera mais MARCADORES_POR_FAIXA
        faixas = max(1, int(self.corrente_mA // FAIXA_CORRENTE_MA))
        return faixas * MARCADORES_POR_FAIXA

    def _atualizar_marcadores(self):
        y = self.percurso.segmentos[self.placa.segmento_caminho][0].y
        x_vermelho = self.placa.maximo.x if self.lado_atual == 'max' else self.placa.minimo.x
        x_azul = self.placa.minimo.x if self.lado_atual == 'max' else self.placa.maximo.x
        for i in range(len(self.marcadores_vermelhos)):
            ativo = i < self.contagem_acumulada
            self.marcadores_vermelhos[i].enabled = ativo
            self.marcadores_azuis[i].enabled = ativo
            if ativo:
                self.marcadores_vermelhos[i].position = Vec3(x_vermelho, y, self.marcador_zs[i])
                self.marcadores_azuis[i].position = Vec3(x_azul, y, self.marcador_zs[i])

    def set_ativo(self, ativo):
        super().set_ativo(ativo)
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

        super().update(velocidade, delta_t)

    def _avancar_bola(self, bola, deslocamento):
        bola['progresso'] += deslocamento
        pos = self._posicao_no_caminho(bola['progresso'])

        # bateu na parede de verdade (x_min ou x_max) -> volta pra parte_preta
        bateu_na_parede = (math.isclose(pos.x, self.placa.minimo.x, abs_tol=1e-3)
                            or math.isclose(pos.x, self.placa.maximo.x, abs_tol=1e-3))
        if bateu_na_parede:
            lado = 'max' if math.isclose(pos.x, self.placa.maximo.x, abs_tol=1e-3) else 'min'
            if lado != self.lado_atual:
                self.lado_atual = lado
                self.contagem_acumulada = 0
            self.contagem_acumulada = min(self.max_acumulados_atual, self.contagem_acumulada + 1)
            self._atualizar_marcadores()

            bola['progresso'] = 0
            pos = self.percurso.pontos[0]  # parte_preta

        return pos

