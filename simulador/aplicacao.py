"""Inicializacao do motor e localizacao dos recursos, inclusive no executavel."""
import sys
from pathlib import Path

from ursina import Ursina, application

from .simulacao import SimulacaoHall


def criar_aplicacao(**opcoes):
    """Cria o motor e a simulacao sem iniciar o loop de eventos."""
    raiz = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    application.asset_folder = raiz
    app = Ursina(**opcoes)
    simulacao = SimulacaoHall()
    return app, simulacao


def executar():
    app, _ = criar_aplicacao()
    app.run()
