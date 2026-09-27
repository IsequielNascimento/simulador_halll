from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# region Recursos do executavel
# Inclui os modelos GLB e as dependencias do Ursina e do Panda3D.
project_dir = Path(SPECPATH)
datas = [(str(project_dir / 'models'), 'models')]
binaries = []
hiddenimports = []
for package in ('panda3d', 'direct', 'ursina'):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_imports)
# endregion


# region Codigo Python
# Empacota main.py e seus modulos, sem a pasta de testes.
a = Analysis(
    [str(project_dir / 'main.py')],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
# endregion

# region Arquivo final
# Gera main.exe com codigo, bibliotecas e modelos no mesmo arquivo.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
# endregion
