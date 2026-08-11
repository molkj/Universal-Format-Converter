"""万能文件格式转换器 - PySide6 图形界面（现代优化版）"""
from __future__ import annotations

import os
import sys
import threading
import time

from PySide6.QtCore import Qt, QThread, Signal, QSize, QUrl, QPoint, QRect, QEvent, QObject, QRunnable, QThreadPool
from PySide6.QtGui import (
    QColor, QFont, QDesktopServices, QDragEnterEvent, QDropEvent, QAction,
    QIcon, QPixmap, QShortcut, QKeySequence, QPen, QBrush, QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
    QProgressBar, QTextEdit, QFileDialog, QMessageBox, QHeaderView,
    QAbstractItemView, QFrame, QMenu, QLineEdit, QDialog, QListWidget,
    QDialogButtonBox, QSizePolicy, QGraphicsDropShadowEffect,
)

from converter import get_available_targets, convert_file, SUPPORTED_SUMMARY
from converter.utils import ConverterError, CancelledError, ensure_dir

APP_NAME = "万能格式转换器"
APP_VERSION = "1.2.0"


def resource_path(rel: str) -> str:
    """资源路径：兼容开发模式与 PyInstaller 打包模式"""
    if getattr(sys, "_MEIPASS", None):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)

# ------------------------- 主题配色 -------------------------
C_PRIMARY = "#4f6df5"       # 主蓝
C_PRIMARY_HOVER = "#3d5bd9"
C_BG = "#f7f8fa"            # 窗口背景
C_CARD = "#ffffff"          # 卡片
C_BORDER = "#e5e7eb"        # 边框
C_TEXT = "#1f2937"          # 主文字
C_TEXT_SUB = "#6b7280"      # 次要文字
C_OK = "#16a34a"
C_OK_BG = "#e7f6ec"
C_FAIL = "#dc2626"
C_FAIL_BG = "#fdecec"
C_DOING_BG = "#e8f0fe"
C_WAIT_BG = "#eef1f6"
C_CANCEL = "#d97706"
C_CANCEL_BG = "#fef7e6"

# 文件类型 -> 图标与颜色
TYPE_STYLE = {
    "PDF": ("📕", "#e74c3c"), "DOCX": ("📘", "#2f6fed"), "DOC": ("📘", "#2f6fed"),
    "XLSX": ("📗", "#16a34a"), "XLS": ("📗", "#16a34a"), "CSV": ("📊", "#16a34a"),
    "TXT": ("📄", "#64748b"), "MD": ("📝", "#64748b"), "HTML": ("🌐", "#f59e0b"),
    "PPTX": ("📙", "#ea580c"), "PPT": ("📙", "#ea580c"),
    "PNG": ("🖼", "#8b5cf6"), "JPG": ("🖼", "#8b5cf6"), "JPEG": ("🖼", "#8b5cf6"),
    "WEBP": ("🖼", "#8b5cf6"), "GIF": ("🖼", "#8b5cf6"), "BMP": ("🖼", "#8b5cf6"),
    "TIFF": ("🖼", "#8b5cf6"), "ICO": ("🖼", "#8b5cf6"), "SVG": ("🖼", "#8b5cf6"),
    "MP4": ("🎬", "#0ea5e9"), "MKV": ("🎬", "#0ea5e9"), "AVI": ("🎬", "#0ea5e9"),
    "MOV": ("🎬", "#0ea5e9"), "WEBM": ("🎬", "#0ea5e9"), "FLV": ("🎬", "#0ea5e9"),
    "WMV": ("🎬", "#0ea5e9"), "M4V": ("🎬", "#0ea5e9"), "MTS": ("🎬", "#0ea5e9"),
    "MP3": ("🎵", "#ec4899"), "WAV": ("🎵", "#ec4899"), "AAC": ("🎵", "#ec4899"),
    "FLAC": ("🎵", "#ec4899"), "OGG": ("🎵", "#ec4899"), "M4A": ("🎵", "#ec4899"),
    "WMA": ("🎵", "#ec4899"),
    "ZIP": ("📦", "#a16207"), "7Z": ("📦", "#a16207"), "TAR": ("📦", "#a16207"),
    "GZ": ("📦", "#a16207"), "TGZ": ("📦", "#a16207"),
    "文件夹": ("📁", "#ca8a04"),
}


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024.0 or unit == "TB":
            return f"{num:.1f}{unit}" if unit != "B" else f"{int(num)}B"
        num /= 1024.0
    return f"{num:.1f}TB"


# ---------------------------------------------------------------------------
# 小部件
# ---------------------------------------------------------------------------

class StatusBadge(QLabel):
    """圆角彩色状态徽章"""
    KIND = {
        "等待中": (C_WAIT_BG, C_TEXT_SUB),
        "转换中": (C_DOING_BG, C_PRIMARY),
        "成功": (C_OK_BG, C_OK),
        "失败": (C_FAIL_BG, C_FAIL),
        "已取消": (C_CANCEL_BG, C_CANCEL),
    }

    def __init__(self, text: str):
        super().__init__(text)
        bg, fg = self.KIND.get(text, (C_WAIT_BG, C_TEXT_SUB))
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(22)
        self.setStyleSheet(
            f"background:{bg}; color:{fg}; border-radius:11px;"
            f"padding:0 12px; font-weight:bold; font-size:12px;")


class InlineProgress(QWidget):
    """行内进度条（转换中显示在状态列）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(14)
        self.bar.setStyleSheet(
            "QProgressBar{border:none;background:#e8f0fe;border-radius:7px;}"
            "QProgressBar::chunk{background:#4f6df5;border-radius:7px;}")
        lay.addWidget(self.bar)

    def set(self, pct: int):
        self.bar.setValue(max(0, min(100, pct)))


class TypeChip(QLabel):
    """类型小徽章（图标 + 扩展名）"""

    def __init__(self, ext: str):
        icon, color = TYPE_STYLE.get(ext, ("📎", "#64748b"))
        super().__init__(f"{icon} {ext}")
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(22)
        self.setStyleSheet(
            f"color:{color}; font-weight:bold; font-size:12px;")


class DropOverlay(QFrame):
    """拖拽文件时的全窗口提示层"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropOverlay")
        self.setVisible(False)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        t = QLabel("📂")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("font-size:52px;")
        sub = QLabel("松开鼠标，添加文件或文件夹")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(
            f"color:{C_PRIMARY}; font-size:20px; font-weight:bold; margin-top:8px;")
        lay.addWidget(t)
        lay.addWidget(sub)
        self.setStyleSheet(
            f"#dropOverlay{{background:rgba(79,109,245,0.08);"
            f"border:2px dashed {C_PRIMARY}; border-radius:12px;}}")


class HeaderButton(QPushButton):
    """顶部工具按钮"""

    def __init__(self, text, primary=False):
        super().__init__(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        if primary:
            self.setStyleSheet(
                f"QPushButton{{background:{C_PRIMARY}; color:white; border:none;"
                f"border-radius:6px; padding:0 16px; font-weight:bold;}}"
                f"QPushButton:hover{{background:{C_PRIMARY_HOVER};}}"
                f"QPushButton:disabled{{background:#c3ccf0;}}")
        else:
            self.setStyleSheet(
                f"QPushButton{{background:white; color:{C_TEXT};"
                f"border:1px solid {C_BORDER}; border-radius:6px; padding:0 14px;}}"
                f"QPushButton:hover{{background:#f1f3f7; border-color:#c9cfd9;}}"
                f"QPushButton:disabled{{color:#9ca3af;}}")


# ---------------------------------------------------------------------------
# 批量设置目标格式对话框
# ---------------------------------------------------------------------------

class BatchTargetDialog(QDialog):
    """批量设置目标格式：列出选中任务公共支持的目标格式"""

    def __init__(self, targets: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量设置目标格式")
        self.setFixedWidth(320)
        self.choice: str | None = None
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"为选中的任务统一选择目标格式（{len(targets)} 个可选项）："))
        self.list = QListWidget()
        for ext, desc in targets:
            self.list.addItem(f"{desc}（.{ext}）")
        self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        lay.addWidget(self.list)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def accept(self):
        item = self.list.currentItem()
        if item:
            # 从文本中解析扩展名
            text = item.text()
            self.choice = text[text.rfind("（.") + 2:-1]
        super().accept()


# ---------------------------------------------------------------------------
# 自定义表头：自绘首列勾选框（避免 Qt 把图片拉伸成椭圆）
# ---------------------------------------------------------------------------

class CheckableHeader(QHeaderView):
    """首列自绘 18px 勾选框，与行内 CheckBoxCell 共享同一绘制函数，外观像素级一致。"""

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self._checked = False
        self.setSectionsClickable(True)

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self.viewport().update()

    def isChecked(self) -> bool:
        return self._checked

    def paintSection(self, painter, rect, logicalIndex):
        if logicalIndex == 0:
            _paint_check(painter, rect, self._checked)
            # 底部分隔线
            painter.setPen(QPen(QColor(229, 231, 235), 2))
            painter.drawLine(rect.x(), rect.bottom(), rect.right(), rect.bottom())
        else:
            super().paintSection(painter, rect, logicalIndex)


class CheckBoxCell(QWidget):
    """行内/底部通用勾选框 widget：完全自绘，避免 QSS image/indicator 渲染问题。

    外观：18x18 白底圆角、2px 边框（灰/蓝）、checked 时加粗蓝勾。"""

    checkedChanged = Signal(bool)

    def __init__(self, checked: bool = False, size: QSize = None, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.setCursor(Qt.PointingHandCursor)
        # Fixed policy：widget 不被父布局拉伸，但允许 setGeometry 设置大小
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        if size:
            self._size_hint = size
        else:
            self._size_hint = QSize(44, 36)

    def sizeHint(self):
        return self._size_hint

    def minimumSizeHint(self):
        return self.sizeHint()

    def setChecked(self, c: bool):
        if self._checked != c:
            self._checked = c
            self.update()
            self.checkedChanged.emit(c)

    def isChecked(self) -> bool:
        return self._checked

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            self.update()
            self.checkedChanged.emit(self._checked)

    def mouseDoubleClickEvent(self, event):
        # Qt 双击会触发两次 mousePressEvent（toggle 回到原状），再翻一次使 = 单击一次
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            self.update()
            self.checkedChanged.emit(self._checked)

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # 居中绘制 18x18（widget 可能大于 18，因父布局拉伸）
        rect = self.rect()
        # 计算 device pixel ratio，确保在高分屏下渲染清晰
        dpr = self.devicePixelRatioF()
        size = 18
        x = rect.x() + (rect.width() - size) // 2
        y = rect.y() + (rect.height() - size) // 2
        cb_rect = QRect(x, y, size, size)
        radius = 4

        # 白底
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(255, 255, 255)))
        p.drawRoundedRect(cb_rect, radius, radius)
        # 边框
        border_color = QColor(79, 109, 245) if self._checked else QColor(195, 202, 214)
        p.setBrush(Qt.NoBrush)
        # 高 DPR 下用稍粗的线
        pen_w = 2.0 if dpr <= 1.0 else 2.5
        p.setPen(QPen(border_color, pen_w))
        p.drawRoundedRect(cb_rect, radius, radius)
        # 蓝勾
        if self._checked:
            pen = QPen(QColor(79, 109, 245), pen_w + 0.5)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p1_x = cb_rect.x() + cb_rect.width() * 0.24
            p1_y = cb_rect.y() + cb_rect.height() * 0.54
            p2_x = cb_rect.x() + cb_rect.width() * 0.42
            p2_y = cb_rect.y() + cb_rect.height() * 0.74
            p3_x = cb_rect.x() + cb_rect.width() * 0.78
            p3_y = cb_rect.y() + cb_rect.height() * 0.28
            p.drawLine(int(p1_x), int(p1_y), int(p2_x), int(p2_y))
            p.drawLine(int(p2_x), int(p2_y), int(p3_x), int(p3_y))
        p.end()


class CheckBoxWithLabel(QWidget):
    """底部选项：自绘 CheckBoxCell + 文字标签，彻底统一外观，避免 QCheckBox QSS 渲染问题。"""

    changed = Signal(bool)

    def __init__(self, label_text: str = "", checked: bool = True, parent=None):
        super().__init__(parent)
        # 紧凑尺寸的勾选框（22x22），checkbox 与文字紧贴
        from PySide6.QtCore import QSize
        self.cb = CheckBoxCell(checked, size=QSize(22, 22))
        self.label = QLabel(label_text)
        from PySide6.QtWidgets import QHBoxLayout, QSizePolicy
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(self.cb)
        lay.addWidget(self.label)
        # 不强制固定高度，让其与 label 文字基线对齐
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        self.cb.checkedChanged.connect(self.changed.emit)

    def isChecked(self) -> bool:
        return self.cb.isChecked()

    def setChecked(self, c: bool):
        self.cb.setChecked(c)


def _paint_check(painter, rect, checked: bool):
    """统一的勾选框绘制函数（表头、行内 cellWidget 共用）。

    rect: 单元格 rect，绘制时 18x18 居中。
    checked: 是否勾选。"""
    size = 18
    x = rect.x() + (rect.width() - size) // 2
    y = rect.y() + (rect.height() - size) // 2
    cb_rect = QRect(x, y, size, size)
    radius = 4

    painter.save()
    # 白底
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(QColor(255, 255, 255)))
    painter.drawRoundedRect(cb_rect, radius, radius)
    # 边框
    border_color = QColor(79, 109, 245) if checked else QColor(195, 202, 214)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(border_color, 2))
    painter.drawRoundedRect(cb_rect, radius, radius)
    # 蓝勾
    if checked:
        pen = QPen(QColor(79, 109, 245), 2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        p1_x = cb_rect.x() + cb_rect.width() * 0.26
        p1_y = cb_rect.y() + cb_rect.height() * 0.55
        p2_x = cb_rect.x() + cb_rect.width() * 0.42
        p2_y = cb_rect.y() + cb_rect.height() * 0.72
        p3_x = cb_rect.x() + cb_rect.width() * 0.76
        p3_y = cb_rect.y() + cb_rect.height() * 0.30
        painter.drawLine(int(p1_x), int(p1_y), int(p2_x), int(p2_y))
        painter.drawLine(int(p2_x), int(p2_y), int(p3_x), int(p3_y))
    painter.restore()


# ---------------------------------------------------------------------------
# 任务与线程
# ---------------------------------------------------------------------------

class TaskItem:
    def __init__(self, src: str, target: str):
        self.src = src
        self.target = target
        self.status = "等待中"
        self.message = ""
        self.outputs: list[str] = []
        self.checked = True   # 是否参与本次转换


class _TaskSignals(QObject):
    """线程桥接：QRunnable 不能直接发信号，借助 QObject 转发（queued 到主线程）"""
    task_started = Signal(int)
    task_finished = Signal(int, bool, str)
    progress = Signal(int, int, int, str)   # row, done, total, message
    pool_done = Signal(int, int)              # ok, fail


class _TaskRunner(QRunnable):
    """单个任务的可运行单元，由 QThreadPool 调度执行"""

    def __init__(self, signals: _TaskSignals, task: TaskItem, row: int,
                 out_dir: str, cancel_event: threading.Event):
        super().__init__()
        self.signals = signals
        self.task = task
        self.row = row
        self.out_dir = out_dir
        self.cancel_event = cancel_event

    def run(self):
        if self.cancel_event.is_set():
            self.signals.task_finished.emit(self.row, False, "已取消")
            return
        self.signals.task_started.emit(self.row)
        try:
            outputs = convert_file(
                self.task.src, self.task.target, self.out_dir,
                progress=lambda d, t, m: self.signals.progress.emit(
                    self.row, d, t, m),
                opts={"gif_fps": 10})
            self.task.outputs = outputs
            self.signals.task_finished.emit(self.row, True, "完成")
        except (CancelledError, InterruptedError):
            self.signals.task_finished.emit(self.row, False, "已取消")
        except ConverterError as e:
            self.signals.task_finished.emit(self.row, False, str(e))
        except Exception as e:  # noqa: BLE001
            self.signals.task_finished.emit(self.row, False, f"未知错误：{e}")


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    COL_CHECK, COL_NAME, COL_SIZE, COL_TYPE, COL_TARGET, COL_STATUS = 0, 1, 2, 3, 4, 5

    def __init__(self):
        super().__init__()
        self.tasks: list[TaskItem] = []
        self._signals: _TaskSignals | None = None
        self._cancel_event: threading.Event | None = None
        self._pool: QThreadPool | None = None
        self._tasks_total: int = 0
        self._tasks_done: int = 0
        self.out_dir = os.path.join(os.path.expanduser("~"), "Documents", "格式转换输出")
        self.log_lines = 0
        self._current_row = -1
        self._inline_progress: InlineProgress | None = None

        self.setWindowTitle(APP_NAME)
        icon_file = resource_path("assets/app.png")
        if os.path.exists(icon_file):
            self.setWindowIcon(QIcon(icon_file))
        self.setMinimumSize(960, 660)
        self.resize(1040, 740)
        self.setAcceptDrops(True)

        self._build_ui()
        self._apply_style()
        self._setup_shortcuts()
        self._refresh_table()  # 初始空列表状态（隐藏/居中拖拽提示）
        self.statusBar().showMessage("把文件或文件夹拖入窗口，勾选要转换的项目，点击「开始转换」")
        self.log(f"欢迎使用 {APP_NAME} v{APP_VERSION}")
        for cat, desc in SUPPORTED_SUMMARY.items():
            self.log(f"  · {cat}：{desc}")

    # ------------------------- UI 构建 -------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)

        # ---- 标题区 ----
        title_card = QFrame()
        title_card.setObjectName("card")
        tlay = QHBoxLayout(title_card)
        tlay.setContentsMargins(16, 10, 16, 10)
        icon_file = resource_path("assets/app.png")
        if os.path.exists(icon_file):
            logo = QLabel()
            logo.setPixmap(QPixmap(icon_file).scaled(
                38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo.setStyleSheet("background: transparent;")
            tlay.addWidget(logo)
        left = QVBoxLayout()
        left.setSpacing(1)
        name = QLabel(APP_NAME)
        name.setStyleSheet(f"font-size:18px; font-weight:bold; color:{C_TEXT};")
        sub = QLabel("文档 · 图片 · 音视频 · 压缩包，一键批量转换，纯本地更安全")
        sub.setStyleSheet(f"font-size:12px; color:{C_TEXT_SUB};")
        left.addWidget(name)
        left.addWidget(sub)
        tlay.addLayout(left)
        tlay.addSpacing(6)
        tlay.addStretch(1)
        tlay.addWidget(QLabel("输出到："))
        self.out_dir_edit = QLineEdit(self.out_dir)
        self.out_dir_edit.setMinimumWidth(240)
        self.out_dir_edit.setReadOnly(True)
        self.out_dir_edit.setFixedHeight(32)
        btn_pick = HeaderButton("更改…")
        btn_pick.clicked.connect(self._pick_out_dir)
        btn_open = HeaderButton("📂 打开目录")
        btn_open.clicked.connect(self._open_out_dir)
        tlay.addWidget(self.out_dir_edit)
        tlay.addWidget(btn_pick)
        tlay.addWidget(btn_open)
        root.addWidget(title_card)

        # ---- 工具栏 ----
        toolbar = QHBoxLayout()
        self.btn_add_files = HeaderButton("＋ 添加文件", primary=True)
        self.btn_add_folder = HeaderButton("＋ 添加文件夹")
        self.btn_batch = HeaderButton("⚙ 批量设置格式")
        self.btn_clear = HeaderButton("🗑 清空")
        self.btn_add_files.clicked.connect(self._add_files)
        self.btn_add_folder.clicked.connect(self._add_folder)
        self.btn_batch.clicked.connect(self._batch_set_target)
        self.btn_clear.clicked.connect(self._clear_tasks)
        toolbar.addWidget(self.btn_add_files)
        toolbar.addWidget(self.btn_add_folder)
        toolbar.addWidget(self.btn_batch)
        toolbar.addWidget(self.btn_clear)
        toolbar.addStretch(1)
        self.lbl_summary = QLabel("共 0 个任务")
        self.lbl_summary.setStyleSheet(f"color:{C_TEXT_SUB}; font-size:12px;")
        toolbar.addWidget(self.lbl_summary)
        root.addLayout(toolbar)

        # ---- 文件表格 ----
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["", "文件", "大小", "类型", "转换为", "状态"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)  # 去掉丑丑的虚线焦点框
        # 用普通 header，表头首列放一个真正的 CheckBoxCell widget（与行内同源，外观彻底统一）
        self.header = QHeaderView(Qt.Horizontal, self.table)
        self.header.setFixedHeight(34)
        self.table.setHorizontalHeader(self.header)
        # 首列 widget（真正的 CheckBoxCell，与行内 100% 一致）
        self.header_cb = CheckBoxCell(False, size=QSize(36, 28))
        self.header_cb.checkedChanged.connect(self._on_header_check_changed)
        self.header_cb.setParent(self.header.viewport())
        self.header_cb.show()
        # header 几何变化时同步 widget 位置
        self.header.sectionResized.connect(self._update_header_cb_geometry)
        header = self.header
        header.setSectionResizeMode(self.COL_CHECK, QHeaderView.Fixed)
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_SIZE, QHeaderView.Fixed)
        header.setSectionResizeMode(self.COL_TYPE, QHeaderView.Fixed)
        header.setSectionResizeMode(self.COL_TARGET, QHeaderView.Fixed)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.Fixed)
        header.setFixedHeight(34)
        self.table.setColumnWidth(self.COL_CHECK, 44)
        self.table.setColumnWidth(self.COL_SIZE, 96)
        self.table.setColumnWidth(self.COL_TYPE, 96)
        self.table.setColumnWidth(self.COL_TARGET, 160)
        self.table.setColumnWidth(self.COL_STATUS, 100)
        # 点击表头首列 = 全选/全不选
        header.sectionClicked.connect(self._header_check_clicked)
        header_item = self.table.horizontalHeaderItem(self.COL_CHECK)
        if header_item:
            header_item.setToolTip("点击：全选 / 全不选")
        # 勾选列用 cellWidget 信号（itemChanged 不再需要）
        self.table.cellDoubleClicked.connect(self._open_row_location)
        # 选中行时在底部状态栏显示完整信息
        self.table.itemSelectionChanged.connect(self._update_status_bar)
        self.statusBar().setStyleSheet(
            f"QStatusBar{{background:{C_CARD}; border-top:1px solid {C_BORDER};"
            f"color:{C_TEXT_SUB}; font-size:12px; padding:2px 8px;}}")
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_menu)
        root.addWidget(self.table, 1)

        # 空列表提示
        self.drag_hint = QLabel(
            "📂  把文件或文件夹拖到这里\n\n支持批量转换 · 全部在本地完成", self.table)
        self.drag_hint.setAlignment(Qt.AlignCenter)
        self.drag_hint.setWordWrap(True)
        self.drag_hint.setStyleSheet(
            f"color:#9ca3af; font-size:15px; border:2px dashed #d1d5db;"
            f"border-radius:12px; background:{C_CARD}; padding:40px;")
        self.drag_hint.setGeometry(30, 50, 360, 150)

        # 拖拽 overlay
        self.overlay = DropOverlay(central)

        # ---- 进度区 ----
        self.progress_label = QLabel("就绪，等待添加文件")
        self.progress_label.setStyleSheet(f"color:{C_TEXT_SUB}; font-size:12px;")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        root.addWidget(self.progress_label)
        root.addWidget(self.progress)

        # ---- 操作按钮行 ----
        ctrl = QHBoxLayout()
        self.btn_start = QPushButton("▶  开始转换")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setMinimumHeight(42)
        self.btn_start.setStyleSheet(
            f"QPushButton{{background:{C_PRIMARY}; color:white; border:none;"
            f"border-radius:8px; font-size:15px; font-weight:bold; padding:0 36px;}}"
            f"QPushButton:hover{{background:{C_PRIMARY_HOVER};}}"
            f"QPushButton:disabled{{background:#c3ccf0;}}")
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setMinimumHeight(42)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(
            f"QPushButton{{background:white; color:{C_TEXT};"
            f"border:1px solid {C_BORDER}; border-radius:8px; padding:0 22px;}}"
            f"QPushButton:hover{{background:#f1f3f7;}}"
            f"QPushButton:disabled{{color:#9ca3af;}}")
        self.btn_cancel.clicked.connect(self._cancel)
        ctrl.addWidget(self.btn_start)
        ctrl.addSpacing(8)
        ctrl.addWidget(self.btn_cancel)
        # 转换完成后自动打开输出目录（自绘 CheckBoxWithLabel，避免 QCheckBox QSS 渲染问题）
        self.chk_auto_open = CheckBoxWithLabel("完成后自动打开输出目录", checked=False)
        self.chk_auto_open.setCursor(Qt.PointingHandCursor)
        ctrl.addSpacing(16)
        ctrl.addWidget(self.chk_auto_open)
        ctrl.addStretch(1)
        self.btn_log_toggle = QPushButton("📋 显示日志")
        self.btn_log_toggle.setCheckable(True)
        self.btn_log_toggle.setStyleSheet(
            f"QPushButton{{background:white; color:{C_TEXT_SUB}; border:1px solid {C_BORDER};"
            f"border-radius:6px; padding:6px 14px;}}"
            f"QPushButton:checked{{background:{C_DOING_BG}; color:{C_PRIMARY};}}")
        self.btn_log_toggle.toggled.connect(self._toggle_log)
        ctrl.addWidget(self.btn_log_toggle)
        root.addLayout(ctrl)

        # ---- 日志（默认收起） ----
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setVisible(False)
        self.log_view.setMaximumHeight(140)
        self.log_view.setFont(QFont("Microsoft YaHei UI", 9))
        self.log_view.setStyleSheet(
            f"background:#1f2937; color:#d1d5db; border:none; border-radius:8px;"
            f"padding:8px; font-family:'Cascadia Mono','Microsoft YaHei UI',monospace;")
        root.addWidget(self.log_view)

    def _apply_style(self):
        self.setStyleSheet(self._build_qss())

    def _build_qss(self) -> str:
        # 行内勾选列已改为 cellWidget 自绘（CheckBoxCell），不依赖 QSS image；
        # 底部 QCheckBox 也不设 image，用 Qt 默认指示器。
        return f"""
            QMainWindow {{ background: {C_BG}; }}
            QWidget {{ font-family: "Microsoft YaHei UI"; font-size: 13px; color: {C_TEXT}; }}
            QFrame#card {{
                background: {C_CARD};
                border: 1px solid {C_BORDER};
                border-radius: 10px;
            }}
            QLineEdit {{
                background: {C_CARD}; border: 1px solid {C_BORDER};
                border-radius: 6px; padding: 4px 10px; color: {C_TEXT_SUB};
            }}
            QTableWidget {{
                background: {C_CARD}; border: 1px solid {C_BORDER};
                border-radius: 10px;
            }}
            QTableWidget::item {{ padding: 4px 8px; }}
            QTableWidget::item:selected {{
                background: #f8fafc; color: {C_TEXT};
            }}
            QHeaderView::section:first {{
                background-color: {C_CARD};
                padding-left: 0;
            }}
            QHeaderView::section {{
                background: {C_CARD}; border: none;
                border-bottom: 2px solid {C_BORDER};
                padding: 6px; font-weight: bold; color: {C_TEXT_SUB}; font-size: 12px;
            }}
            QProgressBar {{
                border: none; border-radius: 4px; background: #e5e7eb;
                height: 8px; text-align: center;
            }}
            QProgressBar::chunk {{ background: {C_PRIMARY}; border-radius: 4px; }}
            QComboBox {{
                background: {C_CARD}; border: 1px solid {C_BORDER};
                border-radius: 6px; padding: 4px 8px; min-width: 120px;
            }}
            QComboBox:hover {{ border-color: {C_PRIMARY}; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QToolTip {{ background: {C_TEXT}; color: white; border: none; padding: 6px; }}
        """

    def _sync_header_check(self):
        """同步表头 widget 状态：全部勾选→checked，否则→unchecked"""
        all_checked = bool(self.tasks) and all(t.checked for t in self.tasks)
        self.header_cb.blockSignals(True)
        self.header_cb.setChecked(all_checked)
        self.header_cb.blockSignals(False)

    def _setup_shortcuts(self):
        """快捷键：提升易用性"""
        QShortcut(QKeySequence("Ctrl+A"), self, activated=self._check_all)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, activated=self._check_none)
        QShortcut(QKeySequence("Delete"), self, activated=self._remove_selected)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._add_files)

    def _check_all(self):
        """全选勾选（快捷键 Ctrl+A）"""
        if not self.tasks:
            return
        for t in self.tasks:
            t.checked = True
        self._refresh_table()

    def _check_none(self):
        """全不选（快捷键 Ctrl+Shift+A）"""
        if not self.tasks:
            return
        for t in self.tasks:
            t.checked = False
        self._refresh_table()

    # ------------------------- 拖拽 -------------------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._show_overlay(True)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._show_overlay(False)

    def dropEvent(self, event: QDropEvent):
        self._show_overlay(False)
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self._add_paths(paths)
        event.acceptProposedAction()

    def _show_overlay(self, show: bool):
        self.overlay.setVisible(show)
        if show:
            self.overlay.raise_()

    def showEvent(self, event):
        super().showEvent(event)
        # 首次显示时居中拖拽提示（__init__ 时窗口未显示，geometry 未确定）
        self._center_drag_hint()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.setGeometry(self.centralWidget().geometry())
        self._center_drag_hint()

    def _center_drag_hint(self):
        """空列表拖拽提示居中到表格数据区（垂直水平都精确居中）"""
        w, h = 360, 150
        tw, th = self.table.width(), self.table.height()
        # 表头占的高度（verticalHeader 隐藏，horizontalHeader 占上部）
        header_h = self.table.horizontalHeader().height()
        # 数据区 = 表格总高 - 表头高
        data_h = th - header_h
        x = max(20, (tw - w) // 2)
        y = max(20, header_h + (data_h - h) // 2)
        self.drag_hint.setGeometry(x, y, w, h)

    # ------------------------- 任务管理 -------------------------

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择要转换的文件", "",
            "所有支持的文件 (*.pdf *.docx *.doc *.xlsx *.xls *.csv *.txt *.md *.html "
            "*.pptx *.ppt *.png *.jpg *.jpeg *.webp *.gif *.bmp *.tiff *.ico "
            "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v *.mts "
            "*.mp3 *.wav *.aac *.flac *.ogg *.m4a *.wma *.zip *.7z *.tar *.gz *.tgz);;"
            "所有文件 (*.*)")
        if files:
            self._add_paths(files)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择要打包的文件夹")
        if folder:
            self._add_paths([folder])

    def _add_paths(self, paths: list[str]):
        added = skipped = dup = 0
        # 用绝对路径作为去重 key（防止同文件重复添加，并发写冲突）
        existing = {os.path.abspath(t.src).lower() for t in self.tasks}
        for p in paths:
            if not os.path.exists(p):
                skipped += 1
                continue
            ap = os.path.abspath(p).lower()
            if ap in existing:
                self.log(f"⚠ 已存在，跳过：{os.path.basename(p)}")
                dup += 1
                continue
            targets = get_available_targets(p)
            if not targets:
                ext = os.path.splitext(p)[1].lower().lstrip(".") or "(无扩展名)"
                self.log(f"⚠ 不支持的文件类型 .{ext}：{os.path.basename(p)}")
                skipped += 1
                continue
            self.tasks.append(TaskItem(p, targets[0][0]))
            existing.add(ap)
            added += 1
        self._refresh_table()
        if added:
            self.log(f"✔ 添加 {added} 个任务")
        if dup:
            self.log(f"⚠ 跳过 {dup} 个重复文件")
        if skipped:
            self.log(f"⚠ 跳过 {skipped} 个不支持的项目")

    def _clear_tasks(self):
        if self._is_busy():
            QMessageBox.information(self, "提示", "转换进行中，请先取消或等待完成。")
            return
        self.tasks.clear()
        self._refresh_table()
        self.log("已清空任务列表")

    def _remove_selected(self):
        if self._is_busy():
            return
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            if 0 <= r < len(self.tasks):
                self.tasks.pop(r)
        self._refresh_table()

    def _batch_set_target(self):
        # 优先使用选中行；没有选中行时自动对所有已勾选任务生效
        # （表格大部分区域是下拉框/勾选框 cellWidget，点击不会选中行）
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            rows = [i for i, t in enumerate(self.tasks) if t.checked]
        if not rows:
            QMessageBox.information(
                self, "提示", "请先勾选要设置格式的文件（或直接选中行）。")
            return
        # 计算公共目标格式
        common: set[str] | None = None
        desc_map: dict[str, str] = {}
        for r in rows:
            tgts = {e: d for e, d in get_available_targets(self.tasks[r].src)}
            desc_map.update(tgts)
            s = set(tgts)
            common = s if common is None else common & s
        if not common:
            QMessageBox.information(self, "提示", "选中文件类型没有共同的目标格式。")
            return
        options = sorted(((e, desc_map[e]) for e in common), key=lambda x: x[1])
        dlg = BatchTargetDialog(options, self)
        if dlg.exec() == QDialog.Accepted and dlg.choice:
            for r in rows:
                self.tasks[r].target = dlg.choice
            self._refresh_table()
            self.log(f"⚙ 已为 {len(rows)} 个任务设置目标格式 .{dlg.choice}")

    # ------------------------- 表格 -------------------------

    def _refresh_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.tasks))
        for row, task in enumerate(self.tasks):
            self._fill_row(row, task)
        self.table.blockSignals(False)
        self.drag_hint.setVisible(len(self.tasks) == 0)
        if not self.tasks:
            self._center_drag_hint()
        self._update_summary()
        self._sync_header_check()

    def _fill_row(self, row: int, task: TaskItem):
        # 勾选框：用自绘 CheckBoxCell（避免 QSS image 渲染问题，与表头同源）
        cb = CheckBoxCell(task.checked)
        cb.checkedChanged.connect(
            lambda _s, r=row: self._on_cell_check_changed(r))
        self.table.setCellWidget(row, self.COL_CHECK, cb)

        is_dir = os.path.isdir(task.src)
        name = os.path.basename(task.src)
        name_item = QTableWidgetItem(name)
        name_item.setToolTip(task.src)
        if is_dir:
            name_item.setText("📁 " + name)
        self.table.setItem(row, self.COL_NAME, name_item)

        if is_dir:
            # 文件夹显示内部条目数（顶层，避免深层遍历过慢）
            try:
                size_text = f"{len(os.listdir(task.src))} 项"
            except OSError:
                size_text = "—"
        else:
            try:
                size_text = human_size(os.path.getsize(task.src))
            except OSError:
                size_text = "读取失败"
        size_item = QTableWidgetItem(size_text)
        size_item.setTextAlignment(Qt.AlignCenter)
        size_item.setForeground(QColor(C_TEXT_SUB))
        self.table.setItem(row, self.COL_SIZE, size_item)

        ext = "文件夹" if is_dir else (os.path.splitext(task.src)[1].lstrip(".").upper() or "?")
        self.table.setCellWidget(row, self.COL_TYPE, TypeChip(ext))

        combo = QComboBox()
        combo.setCursor(Qt.PointingHandCursor)
        for tgt, desc in get_available_targets(task.src):
            combo.addItem(desc, tgt)
        idx = combo.findData(task.target)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(
            lambda _i, r=row, c=combo: self._target_changed(r, c))
        # 转换进行中不可改格式，其余状态（等待/成功/失败/已取消）均可修改
        combo.setEnabled(task.status != "转换中")
        self.table.setCellWidget(row, self.COL_TARGET, combo)

        self.table.setCellWidget(row, self.COL_STATUS, StatusBadge(task.status))

    def _on_cell_check_changed(self, row: int):
        """行内 CheckBoxCell 状态变化的回调"""
        if 0 <= row < len(self.tasks):
            cb = self.table.cellWidget(row, self.COL_CHECK)
            if cb:
                self.tasks[row].checked = cb.isChecked()
            self._update_summary()
            self._sync_header_check()

    def _header_check_clicked(self, section: int):
        """保留：兼容 header section 直接点击（widget 未覆盖区域）"""
        if section != self.COL_CHECK or not self.tasks:
            return
        all_checked = all(t.checked for t in self.tasks)
        self._set_all_checked(not all_checked)

    def _on_header_check_changed(self, _checked: bool):
        """表头 widget 自身切换时同步所有行"""
        self._set_all_checked(self.header_cb.isChecked())

    def _set_all_checked(self, new_state: bool):
        """统一处理全选/全不选：更新 task 数据 + 所有行 cellWidget"""
        for t in self.tasks:
            t.checked = new_state
        for row in range(len(self.tasks)):
            cb = self.table.cellWidget(row, self.COL_CHECK)
            if isinstance(cb, CheckBoxCell) and cb.isChecked() != new_state:
                cb.blockSignals(True)
                cb.setChecked(new_state)
                cb.blockSignals(False)
        self._update_summary()

    def _update_header_cb_geometry(self):
        """让表头首列 widget 始终贴齐 section 0 的位置"""
        x = self.header.sectionViewportPosition(0)
        w = self.header.sectionSize(0)
        h = self.header.height()
        self.header_cb.setGeometry(x, 0, w, h)

    def _update_status_bar(self):
        """在底部状态栏显示选中文件的完整信息（解决长文件名截断）"""
        rows = {i.row() for i in self.table.selectedIndexes()}
        if not rows:
            self.statusBar().showMessage("")
            return
        row = sorted(rows)[0]
        if not (0 <= row < len(self.tasks)):
            return
        t = self.tasks[row]
        if os.path.isdir(t.src):
            size_txt = "文件夹"
        else:
            try:
                size_txt = human_size(os.path.getsize(t.src))
            except OSError:
                size_txt = "读取失败"
        self.statusBar().showMessage(
            f"📄 {os.path.basename(t.src)} ｜ 大小 {size_txt} ｜ 目标 {t.target.upper()} ｜ 位置 {t.src}")

    def _target_changed(self, row: int, combo: QComboBox):
        if 0 <= row < len(self.tasks):
            self.tasks[row].target = combo.currentData()

    def _update_summary(self):
        ok = sum(1 for t in self.tasks if t.status == "成功")
        fail = sum(1 for t in self.tasks if t.status == "失败")
        selected = sum(1 for t in self.tasks if t.checked)
        parts = [f"共 {len(self.tasks)} 个任务", f"已选 {selected}"]
        if ok:
            parts.append(f"成功 {ok}")
        if fail:
            parts.append(f"失败 {fail}")
        self.lbl_summary.setText(" · ".join(parts))

    def _open_row_location(self, row: int, col: int):
        if not (0 <= row < len(self.tasks)):
            return
        # 勾选列是 cellWidget，双击由 widget 自己处理翻转（不会触发 cellDoubleClicked）
        if col == self.COL_CHECK:
            return
        path = self.tasks[row].src
        if os.path.exists(path):
            os.startfile(os.path.dirname(path) or ".")  # noqa: PTH206

    def _table_menu(self, pos: QPoint):
        menu = QMenu(self)
        rows = {i.row() for i in self.table.selectedIndexes()}
        act_open = QAction("📂 打开文件位置", self)
        act_open.triggered.connect(
            lambda: self._open_row_location(
                sorted(rows)[0] if rows else -1, self.COL_NAME))
        menu.addAction(act_open)
        act_batch = QAction("⚙ 批量设置目标格式", self)
        act_batch.triggered.connect(self._batch_set_target)
        menu.addAction(act_batch)
        menu.addSeparator()
        act_remove = QAction("✖ 移除选中任务", self)
        act_remove.triggered.connect(self._remove_selected)
        menu.addAction(act_remove)
        act_clear = QAction("🗑 清空列表", self)
        act_clear.triggered.connect(self._clear_tasks)
        menu.addAction(act_clear)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ------------------------- 输出目录 -------------------------

    def _pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录", self.out_dir)
        if d:
            self.out_dir = d
            self.out_dir_edit.setText(d)
            ensure_dir(d)

    def _open_out_dir(self):
        ensure_dir(self.out_dir)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.out_dir))

    # ------------------------- 转换 -------------------------

    def _is_busy(self) -> bool:
        """是否有任务在跑（用于各交互守卫）"""
        return self._pool is not None and self._pool.activeThreadCount() > 0

    def _start(self):
        if self._is_busy():
            return
        if not self.tasks:
            QMessageBox.information(self, "提示", "请先添加要转换的文件。")
            return
        if any(t.status == "转换中" for t in self.tasks):
            return

        # 只处理勾选的行
        run_rows = [i for i, t in enumerate(self.tasks) if t.checked]
        if not run_rows:
            QMessageBox.information(self, "提示", "没有勾选任何要转换的文件。")
            return
        run_tasks = [self.tasks[i] for i in run_rows]

        # 去重：检查输出文件是否会冲突（同一 src 不会出现两次，因为 _add_paths 去重）
        # 但多任务同一 src 的风险仍存在；下面 _add_paths 已保证，所以这里不再额外检查

        ensure_dir(self.out_dir)
        self.progress.setValue(0)
        self.progress.setStyleSheet("")  # 恢复默认蓝
        self.progress_label.setText("准备中…")
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)

        for t in run_tasks:
            if t.status != "成功":
                t.status = "等待中"
                t.message = ""
        self._refresh_table()
        self.log("─" * 44)
        self.log(f"▶ 开始并发转换 {len(run_tasks)} 个任务 → {self.out_dir}")

        # 创建线程池 + 信号桥接 + 取消事件
        self._signals = _TaskSignals()
        self._signals.task_started.connect(self._on_task_started)
        self._signals.task_finished.connect(self._on_task_finished)
        self._signals.progress.connect(self._on_progress)
        self._signals.pool_done.connect(self._on_pool_done)
        self._cancel_event = threading.Event()
        self._tasks_total = len(run_tasks)
        self._tasks_done = 0

        # 限制并发数（避免 CPU 过载/资源耗尽）
        self._pool = QThreadPool.globalInstance()
        max_threads = min(4, self._pool.maxThreadCount(), self._tasks_total)
        self._pool.setMaxThreadCount(max_threads)

        # 提交所有任务
        for task, row in zip(run_tasks, run_rows):
            runner = _TaskRunner(self._signals, task, row,
                                 self.out_dir, self._cancel_event)
            self._pool.start(runner)

    def _cancel(self):
        if self._is_busy():
            self._cancel_event.set()
            self.log("正在取消…")

    def _on_task_started(self, row: int):
        t = self.tasks[row]
        # 行内进度条（每行独立 widget）
        progress = InlineProgress()
        self.table.setCellWidget(row, self.COL_STATUS, progress)
        combo = self.table.cellWidget(row, self.COL_TARGET)
        if combo:
            combo.setEnabled(False)
        # 进度条按已完成任务比例更新（粗粒度）
        done_count = sum(
            1 for x in self.tasks
            if x.status in ("成功", "失败", "已取消")) + 1
        self.progress_label.setText(
            f"并发转换中（{done_count}/{self._tasks_total}）："
            f"{os.path.basename(t.src)} → {t.target.upper()}")
        self.log(f"▶ [{done_count}/{self._tasks_total}] "
                 f"{os.path.basename(t.src)} → {t.target.upper()}")

    def _on_task_finished(self, row: int, ok: bool, msg: str):
        t = self.tasks[row]
        t.status = "成功" if ok else ("已取消" if msg == "已取消" else "失败")
        t.message = msg
        # 恢复徽章
        self.table.removeCellWidget(row, self.COL_STATUS)
        self.table.setCellWidget(row, self.COL_STATUS, StatusBadge(t.status))
        # 任务结束，恢复格式下拉框可编辑（可调整后再次转换）
        combo = self.table.cellWidget(row, self.COL_TARGET)
        if combo:
            combo.setEnabled(True)
        # 转换成功后自动取消勾选（避免下次重复转换）
        if ok:
            t.checked = False
            cb = self.table.cellWidget(row, self.COL_CHECK)
            if isinstance(cb, CheckBoxCell):
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)
        if ok:
            self.log(f"✔ {os.path.basename(t.src)} 完成")
            for out in t.outputs[:3]:
                self.log(f"   ↳ {out}")
            if len(t.outputs) > 3:
                self.log(f"   ↳ …共 {len(t.outputs)} 个输出")
        else:
            self.log(f"✘ {os.path.basename(t.src)}：{msg}")
        self._update_summary()
        self._sync_header_check()
        # 计数 + 触发 pool_done
        self._tasks_done += 1
        if self._tasks_done >= self._tasks_total:
            self._on_pool_done_local()

    def _on_progress(self, row: int, done: int, total: int, message: str):
        total = max(1, total)
        pct = min(100, done)
        # 底部进度条 = 已完成任务比例（粗粒度，不被单任务进度干扰）
        overall = int(self._tasks_done * 100 / max(1, self._tasks_total))
        self.progress.setValue(overall)
        # 行内进度条 = 单任务子进度
        widget = self.table.cellWidget(row, self.COL_STATUS)
        if isinstance(widget, InlineProgress):
            widget.set(pct)
        self.progress_label.setText(message)

    def _on_pool_done_local(self):
        """所有任务完成：汇总 + 恢复 UI"""
        ok = sum(1 for t in self.tasks if t.status == "成功")
        fail = self._tasks_done - ok
        self._on_pool_done(ok, fail)

    def _on_pool_done(self, ok: int, fail: int):
        self.progress.setValue(100)
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self._current_row = -1
        # 完成时进度条变色反馈
        color = "#dc2626" if fail else "#16a34a"
        self.progress.setStyleSheet(
            f"QProgressBar{{border:none;border-radius:4px;background:#e5e7eb;height:8px;}}"
            f"QProgressBar::chunk{{background:{color};border-radius:4px;}}")
        if fail:
            self.progress_label.setText(f"完成：成功 {ok}，失败 {fail}（可双击失败项重新尝试）")
        else:
            self.progress_label.setText(f"全部完成，{ok} 个任务成功 ✅")
        self.log(f"═══ 转换结束：成功 {ok}，失败 {fail} ═══")
        self._update_summary()
        # 按用户预设：全部成功时自动打开输出目录（不弹窗打扰）
        if ok and not fail and self.chk_auto_open.isChecked():
            self._open_out_dir()
        # 清理并发状态
        self._pool = None
        self._signals = None
        self._cancel_event = None

    # ------------------------- 日志 -------------------------

    def _toggle_log(self, show: bool):
        self.log_view.setVisible(show)
        self.btn_log_toggle.setText("📋 收起日志" if show else "📋 显示日志")

    def log(self, text: str):
        ts = time.strftime("%H:%M:%S")
        self.log_view.append(f"[{ts}] {text}")
        self.log_lines += 1
        if self.log_lines > 2000:
            self.log_view.clear()
            self.log_lines = 0

    def closeEvent(self, event):
        if self._is_busy():
            ret = QMessageBox.question(
                self, "确认退出", "转换还在进行中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ret != QMessageBox.Yes:
                event.ignore()
                return
            self._cancel_event.set()
            # 等待线程池完成（最长 5s，防止某些 convert 卡死）
            QThreadPool.globalInstance().wait(5000)
        event.accept()


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
