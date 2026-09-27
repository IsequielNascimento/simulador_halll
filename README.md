# Simulador de efeito Hall

Simulação didática em Python/Ursina com circuito, ímã, tensão Hall e vetores de
velocidade, força magnética e campo magnético. As trajetórias das partículas e
os tamanhos das setas são representações visuais; não estão em escala física.

## Executar

Use Python 3.12 ou superior. Na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

| Comando | Ação |
| --- | --- |
| `M` | Aproximar ou afastar o ímã |
| `I` | Inverter a corrente e girar a pilha |
| `F` | Inverter os polos do ímã |
| `H` | Mostrar ou esconder a ajuda |
| Botão `Sair` | Encerrar o simulador |
| Botão direito do mouse | Girar a câmera |
| Roda do mouse | Aproximar ou afastar a câmera |

Os controles na tela ajustam a corrente e o campo magnético. Os três vetores
alternam entre seta, cruz e ponto conforme a orientação da câmera.
A ajuda inicia fechada; pressione `H` para consultar os comandos. Os sliders
ficam juntos na faixa inferior, com os valores exibidos apenas nos rótulos.
Os indicadores ficam em uma coluna fixa à direita, na ordem da legenda,
sem trocar de posição ao girar ou aproximar a câmera. Apenas a orientação
das setas e os símbolos de entrada/saída acompanham o ângulo observado.
A pilha usa um modelo independente e gira 180° no eixo Y ao inverter a corrente
com `I`. Um giro compensatorio no eixo longitudinal do corpo mantém os sinais
`+` e `-` voltados para dentro do circuito. Uma nova inversão restaura a orientação inicial.
O circuito usa `circuito_sem_pilha.glb`, e a pilha usa `pilha.glb`.

## Organização

| Arquivo | Responsabilidade |
| --- | --- |
| `main.py` | Ponto de entrada |
| `simulador/aplicacao.py` | Inicialização do Ursina e localização dos recursos |
| `simulador/simulacao.py` | Cena, estado, comandos e atualização por quadro |
| `simulador/config.py` | Parâmetros físicos, ajustes visuais e coordenadas da placa |
| `simulador/fisica.py` | Cálculo da tensão Hall e direções dos vetores |
| `simulador/particulas.py` | Movimento das partículas e marcadores de acúmulo |
| `simulador/vetores.py` | Modelos dos vetores, projeção e posicionamento dos rótulos |
| `simulador/interface.py` | Sliders, leituras, legenda e ajuda |
| `models/` | Modelos GLB usados pela cena |
| `main.spec` | Configuração de geração do executável |

Importar `main` não abre a janela. O loop começa apenas ao executar o programa.
Para mudar textos e controles, edite `interface.py`; para ajustar parâmetros,
edite `config.py`.

Em `config.py`, `PLACA` reúne os limites, a espessura e o eixo da corrente;
`VETORES` define os rótulos, descrições, cores e ordem usados pelos indicadores
e pela legenda. Os dois sistemas de partículas compartilham um `Percurso` e a
mesma criação e atualização das bolinhas; o sistema Hall acrescenta o desvio e
o acúmulo nas bordas.

## Gerar o executável

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller main.spec
```

O executável é gerado em `dist/main.exe`. O arquivo `main.spec` inclui os modelos
GLB; `build/` e `dist/` são saídas descartáveis e não devem ser versionadas.

A pasta `tests/` fica somente na máquina local e é ignorada pelo Git, assim como
caches, ambientes virtuais e arquivos temporários.
