"""压缩包处理：ZIP / 7Z / TAR.GZ 的创建、解压与互转"""
from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import zipfile

from .utils import (
    ConverterError,
    Progress,
    ensure_dir,
    stem,
    unique_path,
)

ARCHIVE_EXTS = ("zip", "7z", "gz", "tar", "tgz")
PACK_EXTS = ("zip", "7z", "tar.gz", "tar")

# 压缩包 -> 可解压为文件夹（输出目录）
EXTRACT_TARGETS = {
    "zip": ["文件夹"],
    "7z": ["文件夹"],
    "gz": ["文件夹"],
    "tar": ["文件夹"],
    "tgz": ["文件夹"],
}

# 压缩包互转
CONVERT_TARGETS = {
    "zip": ["7z", "tar.gz"],
    "7z": ["zip", "tar.gz"],
    "tar": ["zip", "7z", "tar.gz"],
    "tgz": ["zip", "7z"],
    "gz": ["zip", "7z"],
}


def extract_archive(src: str, out_dir: str, progress: Progress) -> list[str]:
    """解压压缩包，返回解压后的顶层路径列表"""
    ext = src.rsplit(".", 1)[-1].lower()
    progress.report(5, 100, "正在解压…")

    if ext == "zip":
        with zipfile.ZipFile(src) as zf:
            _safe_extract_zip(zf, out_dir, progress)
    elif ext == "7z":
        try:
            import py7zr
        except ImportError:
            raise ConverterError("解压 7z 需要 py7zr 库。")
        with py7zr.SevenZipFile(src) as z:
            names = z.getnames()
            for i, name in enumerate(names):
                if progress.cancelled:
                    raise InterruptedError
                progress.report(5 + int(i / max(1, len(names)) * 90), 100,
                                f"解压 {name}…")
            z.extractall(path=out_dir)
    else:
        # tar / tar.gz / tgz
        with tarfile.open(src) as tf:
            members = tf.getmembers()
            for i, m in enumerate(members):
                if progress.cancelled:
                    raise InterruptedError
                progress.report(5 + int(i / max(1, len(members)) * 90), 100,
                                f"解压 {m.name}…")
            tf.extractall(path=out_dir)

    progress.report(100, 100, "解压完成")
    return [os.path.join(out_dir, n) for n in os.listdir(out_dir)]


def _safe_extract_zip(zf, out_dir, progress):
    """安全解压：防止路径穿越"""
    names = zf.namelist()
    for i, name in enumerate(names):
        if progress.cancelled:
            raise InterruptedError
        dest = os.path.normpath(os.path.join(out_dir, name))
        if not dest.startswith(os.path.normpath(out_dir) + os.sep) and dest != os.path.normpath(out_dir):
            raise ConverterError(f"压缩包包含非法路径：{name}")
        progress.report(5 + int(i / max(1, len(names)) * 90), 100, f"解压 {name}…")
    zf.extractall(out_dir)


def _archive_entries(src: str) -> list[tuple[str, str]]:
    """收集要打包的 (磁盘绝对路径, 归档内相对路径)"""
    if os.path.isfile(src):
        return [(src, os.path.basename(src))]
    base = os.path.dirname(src.rstrip("/\\"))
    entries = []
    for root, dirs, files in os.walk(src):
        for name in dirs + files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, base)
            entries.append((full, rel))
    return entries


def pack_archive(src: str, fmt: str, out_path: str, progress: Progress) -> str:
    """将文件或文件夹打包为 fmt（zip/7z/tar.gz）"""
    entries = _archive_entries(src)
    total = len(entries)
    progress.report(2, 100, f"开始打包为 {fmt}…")

    if fmt == "zip":
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, (full, rel) in enumerate(entries):
                if progress.cancelled:
                    raise InterruptedError
                zf.write(full, rel)
                progress.report(2 + int(i / max(1, total) * 96), 100, f"压缩 {rel}…")
    elif fmt == "7z":
        try:
            import py7zr
        except ImportError:
            raise ConverterError("打包 7z 需要 py7zr 库。")
        with py7zr.SevenZipFile(out_path, "w") as z:
            for i, (full, rel) in enumerate(entries):
                if progress.cancelled:
                    raise InterruptedError
                z.write(full, rel)
                progress.report(2 + int(i / max(1, total) * 96), 100, f"压缩 {rel}…")
    elif fmt == "tar.gz":
        with tarfile.open(out_path, "w:gz") as tf:
            for i, (full, rel) in enumerate(entries):
                if progress.cancelled:
                    raise InterruptedError
                tf.add(full, rel)
                progress.report(2 + int(i / max(1, total) * 96), 100, f"压缩 {rel}…")
    else:
        raise ConverterError(f"不支持的打包格式：{fmt}")

    progress.report(100, 100, f"打包为 {fmt} 完成")
    return out_path


def convert_archive(src: str, target_ext: str, out_path: str, progress: Progress) -> str:
    """压缩包互转：解压到临时目录后重新打包"""
    tmp = tempfile.mkdtemp(prefix="fc_conv_")
    try:
        extract_archive(src, tmp, progress)
        # 若只有一个条目且为文件，直接打包该文件
        entries = os.listdir(tmp)
        if len(entries) == 1 and os.path.isfile(os.path.join(tmp, entries[0])):
            src2 = os.path.join(tmp, entries[0])
        else:
            src2 = tmp
        pack_archive(src2, target_ext, out_path, progress)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out_path


def register(registry):
    targets = {}

    for ext, tgts in EXTRACT_TARGETS.items():
        targets[ext] = tgts
        for tgt in tgts:
            def make_extract(ext=ext):
                def fn(src_path, target_ext, out_dir, progress, opts):
                    folder = unique_path(out_dir, stem(src_path), "文件夹") if False else None
                    # 输出目录：out_dir / 原名
                    out_folder = os.path.join(out_dir, stem(src_path) + "_解压")
                    i = 1
                    while os.path.exists(out_folder):
                        out_folder = os.path.join(out_dir, f"{stem(src_path)}_解压{i}")
                        i += 1
                    ensure_dir(out_folder)
                    results = extract_archive(src_path, out_folder, progress)
                    return [f"{out_folder}（解压 {len(results)} 项）"]

                return fn

            registry.register("压缩包", ext, tgt, make_extract(ext))

    for ext, tgts in CONVERT_TARGETS.items():
        targets[ext] = targets.get(ext, []) + tgts
        for tgt in tgts:
            def make_convert(tgt=tgt):
                def fn(src_path, target_ext, out_dir, progress, opts):
                    out = unique_path(out_dir, stem(src_path), tgt)
                    return [convert_archive(src_path, tgt, out, progress)]

                return fn

            registry.register("压缩包", ext, tgt, make_convert(tgt))

    targets["文件夹"] = ["zip", "7z", "tar.gz"]
    for tgt in ("zip", "7z", "tar.gz"):
        def make_pack(tgt=tgt):
            def fn(src_path, target_ext, out_dir, progress, opts):
                out = unique_path(out_dir, stem(src_path), tgt)
                return [pack_archive(src_path, tgt, out, progress)]

            return fn

        registry.register("压缩包", "文件夹", tgt, make_pack(tgt))
    return targets
