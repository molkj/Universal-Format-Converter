"""通用工具函数"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import shutil


def get_ext(path: str) -> str:
    """返回小写且不带点的扩展名，例如 'PDF' -> 'pdf'"""
    return os.path.splitext(path)[1].lstrip(".").lower()


def stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def unique_path(directory: str, name: str, ext: str) -> str:
    """生成不冲突的输出路径：name.ext / name (1).ext ..."""
    ext = ext.lstrip(".")
    candidate = os.path.join(directory, f"{name}.{ext}")
    i = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{name} ({i}).{ext}")
        i += 1
    return candidate


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


class ConverterError(Exception):
    """转换失败时抛出，message 会直接展示给用户"""


class CancelledError(Exception):
    """用户取消转换"""


class Progress:
    """简单进度回调封装：progress(done, total, message)"""

    def __init__(self, cb=None):
        self._cb = cb
        self._cancelled = False
        self._external = None  # threading.Event：外部取消源（如用户点取消）

    def set_external_cancel(self, evt):
        """绑定外部取消事件：一旦 set，下次 report 时标记取消"""
        self._external = evt

    def cancel(self):
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def report(self, done: int, total: int, message: str = ""):
        if self._external is not None and self._external.is_set():
            # 只标记不抛：让 run_subprocess/_run_ffmpeg 的循环在下一次迭代检查
            # progress.cancelled 并执行 kill，避免中断循环导致 ffmpeg 变孤儿进程
            self.cancel()
            return
        if self._cancelled:
            raise CancelledError("转换已取消")
        if self._cb:
            try:
                self._cb(done, total, message)
            except CancelledError:
                raise
            except Exception:
                pass


def find_ffmpeg() -> str | None:
    """查找 ffmpeg.exe：先查程序自带资源目录，再查系统 PATH"""
    candidates = []

    # 打包后的资源目录（PyInstaller _MEIPASS）
    if getattr(sys, "_MEIPASS", None):
        candidates.append(os.path.join(sys._MEIPASS, "ffmpeg", "ffmpeg.exe"))

    # 脚本同级的 build/ffmpeg（开发调试用）
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "..", "build", "ffmpeg", "bin", "ffmpeg.exe"))
    candidates.append(os.path.join(here, "..", "build", "ffmpeg", "ffmpeg.exe"))

    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)

    # PATH 中的 ffmpeg
    which = shutil.which("ffmpeg")
    return which


def run_subprocess(cmd: list[str], progress: Progress, total=100, msg=""):
    """运行子进程并逐行回调进度，同时检查取消"""
    import subprocess

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert proc.stdout is not None
    for line in iter(proc.stdout.readline, ""):
        if progress.cancelled:
            proc.kill()
            proc.wait()  # 等进程完全退出、释放文件句柄，避免残留半成品删不掉
            raise CancelledError("转换已取消")
        line = line.strip()
        if line:
            progress.report(0, total, msg or line)
    proc.wait()
    if proc.returncode != 0:
        raise ConverterError(f"子进程执行失败，退出码 {proc.returncode}")


def parse_ffmpeg_time(line: str) -> float | None:
    """从 ffmpeg 输出行中解析 time=HH:MM:SS.xx，返回秒数"""
    m = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line)
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def parse_ffmpeg_duration(line: str) -> float | None:
    """从 Duration: 00:00:10.00 解析总时长"""
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", line)
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)
