import sys
from pathlib import Path

from ursina import Ursina, application

from .simulacao import SimulacaoHall


# region Recursos e janela
# No executavel, os modelos ficam em _MEIPASS; no fonte, na raiz do projeto.
def criar_aplicacao(**opcoes):
    raiz = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    application.asset_folder = raiz
    opcoes.setdefault('development_mode', False)
    app = Ursina(**opcoes)
    simulacao = SimulacaoHall()
    return app, simulacao
# endregion


# region Execucao
# Inicia o loop de eventos do Ursina.
def executar():
    app, _ = criar_aplicacao()
    app.run()
# endregion
