# -*- mode: python -*-

block_cipher = None

a = Analysis(['turtleHelper.py'],
             pathex=['C:\\Users\\Andy\\Documents\\projects\\turtle-bot-github'],
             binaries=[],
             datas=[('turtle.ico', '.')],
             hiddenimports=['PyQt5'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='turtle_helper',
          debug=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=False , icon='turtle.ico')