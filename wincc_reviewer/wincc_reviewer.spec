# -*- mode: python ; coding: utf-8 -*-
# WinCC OA Code Reviewer — PyInstaller 배포 스펙
# 빌드 명령: pyinstaller wincc_reviewer.spec --noconfirm
# 출력물: dist/WinCC_OA_Code_Reviewer/ (폴더 배포) 또는 dist/WinCC_OA_Code_Reviewer.exe (단일 파일)

import sys
from os import path

block_cipher = None

# 번들링 대상 데이터 파일 목록
# (소스 경로 패턴, 번들 내 대상 디렉터리)
added_files = [
    ('../config/*.xlsx', 'config'),
    ('../config/*.yaml', 'config'),
    ('../config/legacy_mapping/*.yaml', 'config/legacy_mapping'),
    ('app/ui/index.html', 'app/ui'),
    ('schemas/*.json', 'schemas'),
]

a = Analysis(
    ['app/main.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'openpyxl',
        'openpyxl.cell',
        'openpyxl.styles',
        'openpyxl.reader.excel',
        'webview',
        'webview.platforms.winforms',
        'httpx',
        'yaml',
        'json',
        'logging',
        'concurrent.futures',
        'threading',
        'shutil',
        'hashlib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter._test', 'test', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 폴더 배포 방식 EXE (권장: 빠른 시작, 소용량 단위 파일 공유 가능)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WinCC_OA_Code_Reviewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # 현장 배포 시 터미널 창 미표시
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WinCC_OA_Code_Reviewer',
)
