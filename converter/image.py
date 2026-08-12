"""图片格式转换（基于 Pillow）：PNG / JPG / WebP / GIF / BMP / TIFF / ICO 等"""
from __future__ import annotations

import os

from .utils import ConverterError, Progress, stem, unique_path

# 支持的源格式 -> 可选目标格式
IMAGE_TARGETS = {
    "png": ["jpg", "webp", "bmp", "tiff", "gif", "ico"],
    "jpg": ["png", "webp", "bmp", "tiff", "gif", "ico"],
    "jpeg": ["png", "webp", "bmp", "tiff", "gif", "ico"],
    "webp": ["png", "jpg", "bmp", "tiff", "gif", "ico"],
    "gif": ["png", "jpg", "webp", "bmp", "tiff", "ico"],
    "bmp": ["png", "jpg", "webp", "tiff", "gif", "ico"],
    "tiff": ["png", "jpg", "webp", "bmp", "gif", "ico"],
    "ico": ["png", "jpg", "webp", "bmp", "tiff", "gif"],
    "svg": ["png", "jpg", "webp", "bmp", "ico"],
}

PIL_FORMAT = {
    "png": "PNG",
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tiff": "TIFF",
    "gif": "GIF",
    "ico": "ICO",
}


def _prepare_image(img, target_fmt: str):
    """针对目标格式调整图像模式（JPG 不支持透明，ICO 需要特定尺寸）"""
    from PIL import Image

    if target_fmt in ("jpg", "jpeg"):
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
    elif target_fmt == "ico":
        img = img.convert("RGBA")
        # ICO 标准尺寸
        img.thumbnail((256, 256), Image.LANCZOS)
    else:
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
    return img


def convert_image(src: str, target_ext: str, out_path: str, progress: Progress):
    from PIL import Image, UnidentifiedImageError

    fmt = PIL_FORMAT.get(target_ext)
    if fmt is None:
        raise ConverterError(f"不支持的图片目标格式：{target_ext}")

    progress.report(10, 100, "正在读取图片…")
    try:
        img = Image.open(src)
        img.load()
    except UnidentifiedImageError:
        # SVG 需要通过 cairosvg 或 svglib；没有时给出友好提示
        if get_ext(src) == "svg":
            raise ConverterError(
                "SVG → 位图转换需要额外的渲染库（cairosvg），当前未安装。"
            )
        raise ConverterError("无法识别该图片文件，可能已损坏或格式不支持。")

    if getattr(img, "n_frames", 1) > 1 and target_ext == "gif" and get_ext(src) != "gif":
        img.seek(0)  # 多帧源图只取第一帧

    if target_ext == "gif" and getattr(img, "is_animated", False):
        # GIF -> GIF 直接复制
        img.save(out_path, format="GIF", save_all=True)
        progress.report(100, 100, "图片转换完成")
        return out_path

    img = _prepare_image(img, target_ext)
    progress.report(60, 100, "正在保存…")
    kwargs = {"quality": 92} if fmt in ("JPEG", "WEBP") else {}
    img.save(out_path, format=fmt, **kwargs)
    progress.report(100, 100, "图片转换完成")
    return out_path


def merge_images_to_pdf(src_paths: list[str], out_path: str,
                        progress=None) -> str:
    """把多张图片按顺序合并为一个 PDF。

    src_paths: 图片路径列表（按此顺序排列）
    out_path: 输出 PDF 路径
    progress: 进度回调 (done, total, message)
    返回输出路径。"""
    from PIL import Image

    progress = Progress(progress)
    if not src_paths:
        raise ConverterError("没有可合并的图片。")
    images = []
    try:
        for i, p in enumerate(src_paths):
            progress.report(i, len(src_paths), f"读取 {os.path.basename(p)}")
            img = Image.open(p)
            # 统一转 RGB（PDF 不支持 RGBA/P 模式）
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            images.append(img)
        progress.report(len(src_paths), len(src_paths), "生成 PDF…")
        if len(images) == 1:
            images[0].save(out_path, "PDF", resolution=100.0)
        else:
            first, rest = images[0], images[1:]
            first.save(out_path, "PDF", resolution=100.0, save_all=True,
                       append_images=rest)
        progress.report(100, 100, "PDF 已生成")
        return out_path
    except ConverterError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ConverterError(f"合并 PDF 失败：{e}") from e
    finally:
        for im in images:
            try:
                im.close()
            except Exception:  # noqa: BLE001
                pass


def register(registry):
    for src_ext, targets in IMAGE_TARGETS.items():
        for tgt in targets:
            def make(src, tgt=tgt):
                def fn(src_path, target_ext, out_dir, progress, opts):
                    out = unique_path(out_dir, stem(src_path), tgt)
                    return [convert_image(src_path, tgt, out, progress)]

                return fn

            registry.register("图片", src_ext, tgt, make(tgt))
    return IMAGE_TARGETS
