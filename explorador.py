from ursina import *

app = Ursina()
EditorCamera()

modelo = Entity(
    model='models/placa_bateria_fio.glb',
    scale=0.02,
    position=(0,0,0)
)

Entity(model='plane', scale=20, color=color.dark_gray, y=-1)

bola = Entity(model='sphere', scale=0.10, color=color.blue, position=(0, 0.2, 0))

velocidade = 1.0

def subir():
    bola.y += 0.05

def descer():
    bola.y -= 0.05

# Botões na tela para subir/descer
botao_subir = Button(
    text='▲ Subir',
    color=color.azure,
    scale=(0.15, 0.06),
    position=(0.7, 0.4),
    on_click=subir
)

botao_descer = Button(
    text='▼ Descer',
    color=color.orange,
    scale=(0.15, 0.06),
    position=(0.7, 0.3),
    on_click=descer
)

# Texto fixo mostrando as coordenadas da bola (no meio da tela)
texto_coordenadas = Text(
    text='',
    origin=(0, 0),
    position=(0, 0),
    scale=2
)

# Popup com os controles, some após 2 segundos
popup_controles = Text(
    text=(
        'Controles:\n'
        'Setas: mover (X/Z)\n'
        'Page Up / Page Down ou botões: subir/descer\n'
        'Espaço: mostrar posição'
    ),
    origin=(0, 0),
    position=(0, 0.3),
    scale=1.2
)

def esconder_popup():
    popup_controles.enabled = False

invoke(esconder_popup, delay=2)

def update():
    if held_keys['left arrow']:
        bola.x -= velocidade * time.dt
    if held_keys['right arrow']:
        bola.x += velocidade * time.dt
    if held_keys['up arrow']:
        bola.z += velocidade * time.dt
    if held_keys['down arrow']:
        bola.z -= velocidade * time.dt

    # Atualiza o texto com a posição atual da bola
    texto_coordenadas.text = f'x: {bola.x:.3f}   y: {bola.y:.3f}   z: {bola.z:.3f}'

def input(key):
    if key == 'space':
        print(f'posição: x={bola.x:.3f}  y={bola.y:.3f}  z={bola.z:.3f}')
    if key == 'page up':
        subir()
    if key == 'page down':
        descer()

app.run()