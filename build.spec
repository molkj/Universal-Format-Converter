# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：文件转换助手

import os

block_cipher = None

# 项目根目录
ROOT = os.path.abspath(SPECPATH)

a = Analysis(
    ["main.py"],
    pathex=[ROOT],
    binaries=[],
    datas=[
        # 捆绑 ffmpeg（音视频转换引擎）
        (os.path.join(ROOT, "build", "ffmpeg", "bin", "ffmpeg.exe"), "ffmpeg"),
        # 应用图标
        (os.path.join(ROOT, "assets", "app.ico"), "assets"),
        (os.path.join(ROOT, "assets", "app.png"), "assets"),
    ],
    hiddenimports=[
        "win32com", "win32com.client", "win32com.client.gencache",
        "pythoncom",
        "PIL._tkinter_finder",
        "openpyxl", "openpyxl.cell._writer",
    ],
    hookspath=[os.path.join(ROOT, "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    # 排除用不到的 Qt 模块与标准库，进一步瘦身
    excludes=[
        # 体积大头：cv2/numpy 已被 PDF→DOCX 轻量实现移除（原 pdf2docx 依赖，约 100MB）
        "cv2", "numpy", "scipy", "pdf2docx", "opencv",
        "PySide6.QtNetwork", "PySide6.QtNetworkAuth",
        "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
        "PySide6.QtSql", "PySide6.QtXml", "PySide6.QtDBus",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.QtPdf", "PySide6.QtPdfWidgets",
        "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtSvg", "PySide6.QtSvgWidgets",
        "PySide6.QtTest", "PySide6.QtDesigner",
        "tkinter", "test", "unittest", "pydoc", "doctest",
        "curses", "turtle", "lib2to3", "ensurepip", "venv",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---------------------------------------------------------------------------
# 体积优化：排除用不到的二进制（不影响任何已支持的功能）
# ---------------------------------------------------------------------------
_EXCLUDE_BIN_MARKERS = [
    "opengl32sw",                 # Qt 软件 OpenGL 渲染器（界面用 raster 渲染）
    "Qt6Quick", "Qt6Qml", "Qt6Pdf",  # 用不到的 QML/PDF 模块
    "_avif",                      # Pillow 的 AVIF 编码支持（未列入转换格式）
]
if hasattr(a, "binaries"):
    _before = len(a.binaries)
    a.binaries = TOC([
        b for b in a.binaries
        if not any(m in b[0].replace("\\", "/") for m in _EXCLUDE_BIN_MARKERS)
    ])
    print(f"[体积优化] 二进制过滤：{_before} → {len(a.binaries)} 项")

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="文件转换助手",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "assets", "app.ico"),
)
