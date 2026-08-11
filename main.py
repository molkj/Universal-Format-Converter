"""万能文件格式转换器 - 程序入口"""
import multiprocessing
import os
import sys

# 确保能导入 converter 包（开发模式 & 打包模式）
if getattr(sys, "frozen", False):
    _BASE = os.path.dirname(sys.executable)
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)


def main():
    # Windows 打包环境需要
    multiprocessing.freeze_support()
    from gui import main as gui_main
    gui_main()


if __name__ == "__main__":
    main()
