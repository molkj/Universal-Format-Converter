"""音视频格式转换（基于 ffmpeg）：视频互转 / 音频互转 / 提取音频 / 提取封面"""
from __future__ import annotations

import os
import subprocess

from .utils import (
    ConverterError,
    Progress,
    find_ffmpeg,
    parse_ffmpeg_duration,
    parse_ffmpeg_time,
    stem,
    unique_path,
)

# 视频源格式 -> 目标格式
VIDEO_TARGETS = {
    "mp4": ["mkv", "avi", "mov", "webm", "flv", "wmv", "gif", "mp3", "wav", "m4a", "jpg"],
    "mkv": ["mp4", "avi", "mov", "webm", "flv", "wmv", "gif", "mp3", "wav", "m4a", "jpg"],
    "avi": ["mp4", "mkv", "mov", "webm", "flv", "wmv", "gif", "mp3", "wav", "m4a", "jpg"],
    "mov": ["mp4", "mkv", "avi", "webm", "flv", "wmv", "gif", "mp3", "wav", "m4a", "jpg"],
    "webm": ["mp4", "mkv", "avi", "mov", "flv", "wmv", "gif", "mp3", "wav", "m4a", "jpg"],
    "flv": ["mp4", "mkv", "avi", "mov", "webm", "wmv", "gif", "mp3", "wav", "m4a", "jpg"],
    "wmv": ["mp4", "mkv", "avi", "mov", "webm", "gif", "mp3", "wav", "m4a", "jpg"],
    "m4v": ["mp4", "mkv", "avi", "mov", "webm", "wmv", "gif", "mp3", "wav", "m4a", "jpg"],
    "mts": ["mp4", "mkv", "avi", "mov", "webm", "wmv"],
}

# 音频源格式 -> 目标格式
AUDIO_TARGETS = {
    "mp3": ["wav", "aac", "flac", "ogg", "m4a", "wma"],
    "wav": ["mp3", "aac", "flac", "ogg", "m4a", "wma"],
    "aac": ["mp3", "wav", "flac", "ogg", "m4a", "wma"],
    "flac": ["mp3", "wav", "aac", "ogg", "m4a", "wma"],
    "ogg": ["mp3", "wav", "aac", "flac", "m4a", "wma"],
    "m4a": ["mp3", "wav", "aac", "flac", "ogg", "wma"],
    "wma": ["mp3", "wav", "aac", "flac", "ogg", "m4a"],
}

_AUDIO_CODECS = {
    "mp3": "libmp3lame",
    "wav": "pcm_s16le",
    "aac": "aac",
    "flac": "flac",
    "ogg": "libvorbis",
    "m4a": "aac",
    "wma": "wmav2",
}

_VIDEO_CONTAINERS = {
    "mp4": ("libx264", "aac", "mp4"),
    "mkv": ("libx264", "aac", "matroska"),
    "avi": ("mpeg4", "libmp3lame", "avi"),
    "mov": ("libx264", "aac", "mov"),
    "webm": ("libvpx", "libvorbis", "webm"),
    "flv": ("libx264", "aac", "flv"),
    "wmv": ("wmv2", "wmav2", "asf"),
    "m4v": ("libx264", "aac", "mp4"),
}


def _ffmpeg() -> str:
    path = find_ffmpeg()
    if not path:
        raise ConverterError(
            "未找到 ffmpeg.exe。请将 ffmpeg 放入程序目录或添加到系统 PATH 中。"
        )
    return path


def _probe_duration(ffmpeg: str, src: str) -> float | None:
    try:
        out = subprocess.run(
            [ffmpeg, "-i", src],
            capture_output=True,
            text=True,
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return parse_ffmpeg_duration(out.stderr)
    except Exception:
        return None


def _run_ffmpeg(cmd: list[str], src: str, progress: Progress, label: str):
    duration = _probe_duration(cmd[0], src)
    progress.report(2, 100, f"开始：{label}")
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
            proc.wait()  # 等进程退出、释放文件句柄，避免残留半成品删不掉
            raise InterruptedError
        t = parse_ffmpeg_time(line)
        if t is not None and duration:
            pct = min(99, int(t / duration * 100))
            progress.report(pct, 100, f"{label}（{pct}%）")
    proc.wait()
    if proc.returncode != 0:
        raise ConverterError(f"ffmpeg 转换失败，退出码 {proc.returncode}。请检查源文件是否损坏。")
    progress.report(100, 100, f"{label} 完成")


def convert_media(src: str, target_ext: str, out_path: str, progress: Progress,
                  opts: dict | None = None):
    opts = opts or {}
    ffmpeg = _ffmpeg()
    src_ext = src.rsplit(".", 1)[-1].lower()
    label = f"{src_ext.upper()} → {target_ext.upper()}"

    # 视频 -> 图片（提取封面帧）
    if target_ext in ("jpg", "jpeg", "png"):
        cmd = [
            ffmpeg, "-y", "-i", src, "-frames:v", "1",
            "-vf", "thumbnail", "-q:v", "2",
        ]
        if target_ext in ("jpg", "jpeg"):
            cmd.append("-f")
            cmd.append("image2")
        cmd.append(out_path)
        _run_ffmpeg(cmd, src, progress, label)
        return out_path

    # 视频 -> GIF
    if target_ext == "gif":
        fps = opts.get("gif_fps", 10)
        cmd = [ffmpeg, "-y", "-i", src, "-vf", f"fps={fps},scale=480:-1:flags=lanczos",
               "-loop", "0", out_path]
        _run_ffmpeg(cmd, src, progress, label)
        return out_path

    if src_ext in VIDEO_TARGETS:
        if target_ext in AUDIO_TARGETS:
            # 视频 -> 音频：提取音轨
            cmd = [ffmpeg, "-y", "-i", src, "-vn",
                   "-c:a", _AUDIO_CODECS[target_ext], "-q:a", "4" if target_ext == "mp3" else "0"]
            if target_ext == "wav":
                cmd = [ffmpeg, "-y", "-i", src, "-vn", "-c:a", "pcm_s16le"]
            cmd.append(out_path)
            _run_ffmpeg(cmd, src, progress, label)
            return out_path
        if target_ext in VIDEO_TARGETS and target_ext not in VIDEO_TARGETS.get(src_ext, []):
            pass
        # 视频容器互转
        vcodec, acodec, _ = _VIDEO_CONTAINERS.get(target_ext, ("libx264", "aac", "mp4"))
        cmd = [ffmpeg, "-y", "-i", src, "-c:v", vcodec]
        if acodec:
            cmd += ["-c:a", acodec]
        cmd += ["-movflags", "+faststart", "-preset", "medium", "-crf", "21", out_path]
        _run_ffmpeg(cmd, src, progress, label)
        return out_path

    if src_ext in AUDIO_TARGETS:
        # 音频互转
        if target_ext in VIDEO_TARGETS or target_ext == "gif":
            raise ConverterError("纯音频文件不能转换为视频格式。")
        codec = _AUDIO_CODECS.get(target_ext)
        if not codec:
            raise ConverterError(f"不支持的音频目标格式：{target_ext}")
        cmd = [ffmpeg, "-y", "-i", src, "-vn", "-c:a", codec]
        if target_ext == "mp3":
            cmd += ["-q:a", "4"]
        cmd.append(out_path)
        _run_ffmpeg(cmd, src, progress, label)
        return out_path

    raise ConverterError(f"暂不支持 {src_ext} → {target_ext} 的转换。")


def register(registry):
    all_targets = {}

    def make(src_ext, tgt):
        def fn(src_path, target_ext, out_dir, progress, opts):
            out = unique_path(out_dir, stem(src_path), tgt)
            return [convert_media(src_path, tgt, out, progress, opts)]

        return fn

    for src_ext, targets in VIDEO_TARGETS.items():
        all_targets[src_ext] = targets
        for tgt in targets:
            registry.register("音视频", src_ext, tgt, make(src_ext, tgt))
    for src_ext, targets in AUDIO_TARGETS.items():
        all_targets[src_ext] = targets
        for tgt in targets:
            registry.register("音视频", src_ext, tgt, make(src_ext, tgt))
    return all_targets
