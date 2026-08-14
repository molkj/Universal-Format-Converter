"""全局转换注册表：统一管理所有 (源格式, 目标格式) -> 转换函数"""
from __future__ import annotations

import os

from . import utils

# 内部结构：
# _TABLE[src_ext][target_ext] = callable(src, target_ext, out_dir, progress, opts) -> [输出...]
# _CATEGORY[(src, tgt)] = 类别名
# _TARGETS[src_ext] = [(target_ext, 描述)]
_TABLE: dict[str, dict[str, callable]] = {}
_CATEGORY: dict[tuple[str, str], str] = {}
_TARGETS: dict[str, list[tuple[str, str]]] = {}


def register(category: str, src_ext: str, target_ext: str, fn: callable):
    src_ext = src_ext.lower()
    target_ext = target_ext.lower()
    _TABLE.setdefault(src_ext, {})[target_ext] = fn
    _CATEGORY[(src_ext, target_ext)] = category
    _TARGETS.setdefault(src_ext, [])
    if not any(t[0] == target_ext for t in _TARGETS[src_ext]):
        _TARGETS[src_ext].append((target_ext, target_ext))


class _RegistryHelper:
    """让各模块的 register() 能注入本模块的注册表"""

    def register(self, category, src, tgt, fn):
        register(category, src, tgt, fn)


# 导入各模块并注册
from . import archive, document, image, media  # noqa: E402

document.register(_RegistryHelper())
image.register(_RegistryHelper())
media.register(_RegistryHelper())
archive.register(_RegistryHelper())

# 展示用的格式说明
FORMAT_DESC = {
    "pdf": "PDF 文档", "docx": "Word 文档", "doc": "Word 97-2003",
    "xlsx": "Excel 工作簿", "xls": "Excel 97-2003", "csv": "CSV 表格",
    "txt": "纯文本", "md": "Markdown", "html": "网页 HTML",
    "utf8": "UTF-8 编码", "gbk": "GBK 编码",
    "pptx": "PPT 演示", "ppt": "PPT 97-2003",
    "png": "PNG 图片", "jpg": "JPG 图片", "jpeg": "JPEG 图片",
    "webp": "WebP 图片", "gif": "GIF 图片", "bmp": "BMP 图片",
    "tiff": "TIFF 图片", "ico": "ICO 图标", "svg": "SVG 矢量图",
    "mp4": "MP4 视频", "mkv": "MKV 视频", "avi": "AVI 视频",
    "mov": "MOV 视频", "webm": "WebM 视频", "flv": "FLV 视频",
    "wmv": "WMV 视频", "m4v": "M4V 视频", "mts": "MTS 视频",
    "mp3": "MP3 音频", "wav": "WAV 音频", "aac": "AAC 音频",
    "flac": "FLAC 音频", "ogg": "OGG 音频", "m4a": "M4A 音频",
    "wma": "WMA 音频",
    "zip": "ZIP 压缩包", "7z": "7Z 压缩包", "tar": "TAR 压缩包",
    "gz": "GZ 压缩包", "tgz": "TGZ 压缩包", "rar": "RAR 压缩包",
    "文件夹": "解压为文件夹",
}

# 扩展名 -> 类别（用于界面分组与图标）
EXT_CATEGORY: dict[str, str] = {}
for _ext in ("pdf", "docx", "doc", "xlsx", "xls", "csv", "txt", "md", "html", "pptx", "ppt"):
    EXT_CATEGORY[_ext] = "文档"
for _ext in ("png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff", "ico", "svg"):
    EXT_CATEGORY[_ext] = "图片"
for _ext in ("mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", "m4v", "mts",
             "mp3", "wav", "aac", "flac", "ogg", "m4a", "wma"):
    EXT_CATEGORY[_ext] = "音视频"
for _ext in ("zip", "7z", "tar", "gz", "tgz", "rar"):
    EXT_CATEGORY[_ext] = "压缩包"


def get_available_targets(src: str) -> list[tuple[str, str]]:
    """返回 [(目标扩展名, 描述)]，按类别排序、类别内保持注册顺序（常用优先）

    编码转换目标（utf8/gbk）按源文件实际编码动态过滤：
    已是 UTF-8 的文件不显示「转为 UTF-8」，避免选了报错。"""
    if os.path.isdir(src):
        src_ext = "文件夹"
    else:
        src_ext = utils.get_ext(src)
    if not src_ext:
        return []
    # 源文件当前编码（仅文本类需要）
    src_enc = None
    if src_ext in ("txt", "csv") and os.path.isfile(src):
        try:
            from .document import detect_encoding
            src_enc = detect_encoding(src)
        except Exception:  # noqa: BLE001
            src_enc = None
    order = {"文档": 0, "图片": 1, "音视频": 2, "压缩包": 3}
    items = []
    for tgt, _desc in _TARGETS.get(src_ext, []):
        # 编码目标按当前编码过滤：已是 UTF-8 只显示 GBK，反之亦然
        if src_enc is not None and tgt in ("utf8", "gbk"):
            is_utf8 = src_enc in ("utf-8", "utf-8-sig")
            if (tgt == "utf8" and is_utf8) or (tgt == "gbk" and not is_utf8):
                continue  # 已是该编码，隐藏此选项
        cat = _CATEGORY.get((src_ext, tgt), "")
        label = FORMAT_DESC.get(tgt, tgt.upper())
        items.append((order.get(cat, 9), len(items), tgt, label))
    items.sort(key=lambda x: (x[0], x[1]))
    return [(t, d) for _, _, t, d in items]


def convert_file(src: str, target_ext: str, out_dir: str,
                 progress=None, opts: dict | None = None,
                 cancel_event=None) -> list[str]:
    """执行转换，返回输出路径列表。

    src: 源文件或文件夹路径
    target_ext: 目标扩展名
    out_dir: 输出目录
    progress: 进度回调 (done, total, message)
    opts: 额外选项
    cancel_event: threading.Event，外部取消源（设置后转换将被终止）
    """
    progress_obj = utils.Progress(progress)
    if cancel_event is not None:
        progress_obj.set_external_cancel(cancel_event)
    if not os.path.exists(src):
        raise utils.ConverterError("源文件或文件夹不存在，可能已被移动或删除。")
    src_ext = utils.get_ext(src) if os.path.isfile(src) else "文件夹"
    fn = _TABLE.get(src_ext, {}).get(target_ext)
    if fn is None:
        raise utils.ConverterError(
            f"暂不支持 {src_ext.upper() or '该文件'} → {target_ext.upper()} 的转换。"
        )
    utils.ensure_dir(out_dir)
    return fn(src, target_ext, out_dir, progress_obj, opts)


SUPPORTED_SUMMARY = {
    "文档": "PDF / Word / Excel / PPT / TXT / MD / HTML",
    "图片": "PNG / JPG / WebP / GIF / BMP / TIFF / ICO",
    "音视频": "MP4 / MKV / AVI / MOV / WEBM / FLV / MP3 / WAV / AAC / FLAC / OGG / M4A",
    "压缩包": "ZIP / 7Z / TAR.GZ 创建、解压与互转",
}
