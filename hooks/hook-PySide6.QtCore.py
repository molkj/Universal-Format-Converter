# -*- coding: utf-8 -*-
# 自定义 hook-PySide6.QtCore.py：覆盖内置 hook，排除用不到的 Qt 翻译文件
# （界面文字为硬编码中文，无需任何 .qm 翻译文件，可省约 59MB）

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)

# 排除 Qt translations（qtbase_*.qm 等全部语言文件）
datas = [d for d in datas if "translations" not in d[0].replace("\\", "/")]
