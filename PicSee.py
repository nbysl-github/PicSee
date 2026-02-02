import sys

import os
import traceback

import ctypes
import subprocess
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QSplitter,
    QTreeView,
    QFileSystemModel,
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QLabel,
    QHBoxLayout,
    QDialog,
    QStatusBar,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QGroupBox,
    QMessageBox,
    QSizePolicy,
    QScrollBar,
    QStyle,
    QToolButton,
    QSlider,
    QAction,
    QMenu,
    QFileIconProvider,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QSplitterHandle,
    QToolTip,
    QProxyStyle,
    QFileDialog,
    QLineEdit,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
)

from PyQt5.QtCore import (
    Qt,
    QModelIndex,
    QSize,
    QTimer,
    QSettings,
    QLocale,
    QDir,
    QThreadPool,
    QRunnable,
    pyqtSignal,
    QObject,
    QRectF,
    QPoint,
    QPointF,
    QMutex,
    QMutexLocker,
    QEvent,
    QUrl,
    QRect,
    QFileInfo,
    QStorageInfo,
    QStandardPaths,
)
from PyQt5.QtGui import (
    QPixmap,
    QImage,
    QPainter,
    QPainterPath,
    QColor,
    QBrush,
    QPen,
    QCursor,
    QPalette,
    QLinearGradient,
    QKeyEvent,
    QDesktopServices,
    QIcon,
    QColorConstants,
    QImageReader,
    QImageIOHandler,
    QStandardItemModel,
    QStandardItem,
    QTextDocument,
    QAbstractTextDocumentLayout,
    QTextOption,
    QPolygonF,
    QFont,
    QFontDatabase,
)
from PIL import Image, ImageOps, UnidentifiedImageError, ExifTags
import io
import json
import time
import unicodedata
import send2trash
import shutil
import sqlite3
from pathlib import Path

# ===================== 主题颜色配置 =====================
THEME_COLORS = {
    "blue":  {"normal": "#3498db", "hover": "#2980b9"},
    "red":   {"normal": "#e74c3c", "hover": "#c0392b"},
    "green": {"normal": "#2ecc71", "hover": "#27ae60"}
}
CURRENT_THEME_COLOR = "blue"

def get_current_theme_color(is_hovered=False):
    """获取当前选中的皮肤颜色"""
    theme = THEME_COLORS.get(CURRENT_THEME_COLOR, THEME_COLORS["blue"])
    return QColor(theme["hover"] if is_hovered else theme["normal"])

# ===================== Win11 风格菜单 =====================
class Win11Menu(QMenu):
    def __init__(self, title="", parent=None, is_dark=True):
        super().__init__(title, parent)
        self.is_dark = is_dark
        self._setup_menu()

    def _setup_menu(self):
        # 设置无边框和透明背景以实现圆角
        # 注意：在某些系统上，QGraphicsDropShadowEffect 会导致 UpdateLayeredWindowIndirect 失败
        # 因此我们移除自定义阴影，改用系统默认阴影或不使用阴影以保证稳定性
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.apply_style()

    def addMenu(self, *args, **kwargs):
        if len(args) >= 1:
            if isinstance(args[0], QIcon):
                icon = args[0]
                title = args[1] if len(args) > 1 else ""
                submenu = Win11Menu(title, self, is_dark=self.is_dark)
                submenu.setIcon(icon)
                super().addMenu(submenu)
                return submenu
            elif isinstance(args[0], str):
                title = args[0]
                submenu = Win11Menu(title, self, is_dark=self.is_dark)
                super().addMenu(submenu)
                return submenu
        return super().addMenu(*args, **kwargs)

    def apply_style(self):
        if self.is_dark:
            bg_color = "rgba(40, 40, 40, 215)"
            text_color = "#f0f0f0"
            border_color = "rgba(255, 255, 255, 30)"
            hover_bg = "rgba(255, 255, 255, 25)"
            separator_color = "rgba(255, 255, 255, 20)"
        else:
            bg_color = "rgba(255, 255, 255, 215)"
            text_color = "#1a1a1a"
            border_color = "rgba(0, 0, 0, 30)"
            hover_bg = "rgba(0, 0, 0, 15)"
            separator_color = "rgba(0, 0, 0, 15)"

        self.setStyleSheet(f"""
            QMenu {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 12px;
                padding: 6px 0px;
            }}
            QMenu::item {{
                padding: 8px 36px 8px 30px;
                border-radius: 6px;
                margin: 2px 8px;
                background-color: transparent;
            }}
            QMenu::item:selected {{
                background-color: {hover_bg};
            }}
            QMenu::separator {{
                height: 1px;
                background: {separator_color};
                margin: 6px 14px;
            }}
            QMenu::right-arrow {{
                padding-right: 10px;
            }}
        """)

try:
    from PyQt5.QtWebEngineWidgets import (
        QWebEngineView,
        QWebEnginePage,
        QWebEngineContextMenuData,
    )

    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
    QWebEngineView = QWidget  # Mock for fallback
    QWebEnginePage = object
    QWebEngineContextMenuData = object


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)


def _normalize_lang_code(lang):
    if not lang:
        return "zh"
    lang = str(lang).strip().lower().replace("-", "_")
    parts = [p for p in lang.split("_") if p]
    if not parts:
        return "zh"
    if parts[0] == "zh":
        if "hant" in parts:
            return "zh_tw"
        if len(parts) >= 2:
            region = parts[1]
            if region in ("tw", "hk", "mo", "hant"):
                return "zh_tw"
            if region in ("cn", "sg", "hans"):
                return "zh"
        return "zh"
    return parts[0]


def _load_language_pack_from_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    if isinstance(data, dict) and isinstance(data.get("strings"), dict):
        return data["strings"]
    if isinstance(data, dict):
        return data
    return None


def _load_all_language_packs():
    translations = {}
    lang_dir = resource_path("lang")
    if os.path.isdir(lang_dir):
        try:
            for name in os.listdir(lang_dir):
                if not name.lower().endswith(".json"):
                    continue
                code = _normalize_lang_code(os.path.splitext(name)[0])
                file_path = os.path.join(lang_dir, name)
                strings = _load_language_pack_from_file(file_path)
                if strings:
                    translations[code] = strings
        except Exception:
            pass
    return translations


TRANSLATIONS = _load_all_language_packs()
TRANSLATIONS.setdefault("zh", {})
TRANSLATIONS.setdefault("en", dict(TRANSLATIONS["zh"]))


# ===================== 自定义图标生成函数 =====================

def get_sort_icon(is_dark=True, is_hovered=False):
    """生成排序图标 (双箭头) (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # 获取主题颜色
    theme_color = get_current_theme_color(is_hovered)
    if is_hovered:
        painter.translate(0, -2)
    
    # 上箭头 (浅色/白色)
    up_color = QColor("#e0e0e0") if is_dark else QColor("#333333")
    painter.setPen(QPen(up_color, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(10, 24, 10, 8)
    painter.drawLine(10, 8, 6, 12)
    painter.drawLine(10, 8, 14, 12)
    
    # 下箭头 (皮肤色)
    painter.setPen(QPen(theme_color, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(22, 8, 22, 24)
    painter.drawLine(22, 24, 18, 20)
    painter.drawLine(22, 24, 26, 20)
    
    painter.end()
    return QIcon(pixmap)

def get_refresh_icon(is_dark=True, is_hovered=False):
    """生成刷新图标 (圆圈箭头) (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    color = QColor("#e0e0e0") if is_dark else QColor("#333333")
    theme_color = get_current_theme_color(is_hovered)
    
    if is_hovered:
        painter.translate(0, -2)
    
    # 绘制圆弧 (灰色)
    painter.setPen(QPen(color, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    rect = QRectF(7, 7, 18, 18)
    start_angle = 45 * 16
    span_angle = -280 * 16 # 顺时针
    painter.drawArc(rect, start_angle, span_angle)
    
    # 绘制箭头尖端 (皮肤色)
    painter.setPen(QPen(theme_color, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.save()
    painter.translate(22.5, 11)
    painter.rotate(-20)
    path = QPainterPath()
    path.moveTo(-4, 0)
    path.lineTo(0, 0)
    path.lineTo(0, 4)
    painter.drawPath(path)
    painter.restore()
    
    painter.end()
    return QIcon(pixmap)

def get_layout_icon(is_dark=True, is_hovered=False):
    """生成布局图标 (2x2 网格) (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    color_gray = QColor("#e0e0e0") if is_dark else QColor("#333333")
    theme_color = get_current_theme_color(is_hovered)
    if is_hovered:
        painter.translate(0, -2)
    
    pen_width = 2.5
    painter.setPen(QPen(color_gray, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    
    # 绘制四个小方块
    # 左上 (皮肤色)
    painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawRect(7, 7, 7, 7)
    
    # 右下 (皮肤色)
    painter.drawRect(18, 18, 7, 7)
    
    # 右上 (灰色)
    painter.setPen(QPen(color_gray, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawRect(18, 7, 7, 7)
    
    # 左下 (灰色)
    painter.drawRect(7, 18, 7, 7)
    
    painter.end()
    return QIcon(pixmap)

def get_delete_icon(is_dark=True, is_hovered=False):
    """生成删除/移除图标 (垃圾桶) (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    color = QColor("#e0e0e0") if is_dark else QColor("#333333")
    theme_color = get_current_theme_color(is_hovered)
    if is_hovered:
        painter.translate(0, -2)
    pen_width = 2.5
    
    # 盖子 (皮肤色)
    painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(8, 10, 24, 10)
    painter.drawLine(13, 10, 13, 8)
    painter.drawLine(13, 8, 19, 8)
    painter.drawLine(19, 8, 19, 10)
    
    # 桶身 (灰色)
    painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(10, 10, 11, 24)
    painter.drawLine(11, 24, 21, 24)
    painter.drawLine(21, 24, 22, 10)
    
    # 桶内线条
    painter.drawLine(14, 13, 14, 20)
    painter.drawLine(18, 13, 18, 20)
    
    painter.end()
    return QIcon(pixmap)

def get_add_icon(is_dark=True, is_hovered=False):
    """生成添加图标 (加号) (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    color = QColor("#e0e0e0") if is_dark else QColor("#333333")
    theme_color = get_current_theme_color(is_hovered)
    if is_hovered:
        painter.translate(0, -2)
    pen_width = 2.5
    
    # 圆圈 (灰色)
    painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawEllipse(7, 7, 18, 18)
    
    # 加号 (皮肤色)
    painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(16, 11, 16, 21) # 竖线
    painter.drawLine(11, 16, 21, 16) # 横线
    
    painter.end()
    return QIcon(pixmap)

def get_clear_icon(color_str="#e0e0e0", is_hovered=False):
    """生成清除(扫把)图标 (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    color = QColor(color_str)
    theme_color = get_current_theme_color(is_hovered)
    pen_width = 2.5
    
    painter.save()
    if is_hovered:
        painter.translate(0, -2)
    painter.translate(16, 16)
    painter.rotate(-45)
    
    # 刷柄 (灰色)
    painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(0, -12, 0, 0)
    
    # 刷头 (皮肤色线条)
    painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(-6, 0, 6, 0)
    painter.drawLine(-6, 0, -8, 10)
    painter.drawLine(6, 0, 8, 10)
    painter.drawLine(-4, 0, -4, 8)
    painter.drawLine(0, 0, 0, 8)
    painter.drawLine(4, 0, 4, 8)
    
    painter.restore()
    painter.end()
    return QIcon(pixmap)

def get_folder_icon(is_dark=True, is_hovered=False):
    """生成文件夹图标 (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # 获取主题颜色
    theme_color = get_current_theme_color(is_hovered)
    
    # 悬停偏移
    if is_hovered:
        painter.translate(0, -2)
        
    # 放大 1.5 倍逻辑
    painter.translate(16, 16)
    painter.scale(1.5, 1.5)
    painter.translate(-16, -16)
    
    color = QColor("#e0e0e0") if is_dark else QColor("#333333")
    pen_width = 2.0 # 稍微减细画笔
    
    # 文件夹主体 (灰色)
    painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawRoundedRect(7, 11, 18, 12, 2, 2)
    
    # 文件夹标签 (皮肤色)
    painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    path = QPainterPath()
    path.moveTo(7, 11)
    path.lineTo(7, 8)
    path.lineTo(13, 8)
    path.lineTo(15, 11)
    painter.drawPath(path)
    
    painter.end()
    return QIcon(pixmap)

def get_computer_icon(is_dark=True):
    """生成此电脑图标 (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # 获取主题颜色
    theme_color = get_current_theme_color()
    
    # 放大 1.5 倍逻辑
    painter.translate(16, 16)
    painter.scale(1.5, 1.5)
    painter.translate(-16, -16)
    
    color = QColor("#e0e0e0") if is_dark else QColor("#333333")
    pen_width = 2.0
    
    # 屏幕外框 (灰色)
    painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawRoundedRect(6, 6, 20, 14, 2, 2)
    
    # 屏幕内屏 (皮肤色)
    painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawRect(9, 9, 14, 8)
    
    # 底座 (灰色)
    painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(13, 20, 19, 20)
    painter.drawLine(11, 23, 21, 23)
    
    painter.end()
    return QIcon(pixmap)

def get_pin_icon(is_dark=True):
    """生成图钉图标 (收藏 - 支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # 获取主题颜色
    theme_color = get_current_theme_color()
    
    # 放大 1.5 倍逻辑
    painter.translate(16, 16)
    painter.scale(1.5, 1.5)
    painter.translate(-16, -16)
    
    color = QColor("#e0e0e0") if is_dark else QColor("#333333")
    pen_width = 2.0
    
    # 图钉头部 (皮肤色)
    painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(12, 8, 20, 16)
    painter.drawLine(10, 10, 13, 13)
    painter.drawLine(19, 19, 22, 22)
    
    # 图钉身体 (灰色)
    painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(13, 13, 19, 19)
    painter.drawLine(11, 21, 11, 21) # 针尖
    painter.drawLine(11, 21, 15, 17)
    
    painter.end()
    return QIcon(pixmap)

def get_history_icon(is_dark=True):
    """生成历史记录图标 (时钟 - 支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # 获取主题颜色
    theme_color = get_current_theme_color()
    
    # 放大 1.5 倍逻辑
    painter.translate(16, 16)
    painter.scale(1.5, 1.5)
    painter.translate(-16, -16)
    
    color = QColor("#e0e0e0") if is_dark else QColor("#333333")
    pen_width = 2.0
    
    # 时钟外圈 (灰色)
    painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawEllipse(7, 7, 18, 18)
    
    # 指针 (皮肤色)
    painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(16, 16, 16, 11) # 分针
    painter.drawLine(16, 16, 20, 16) # 时针
    
    painter.end()
    return QIcon(pixmap)

def get_rotate_icon(direction="left", is_dark=True, is_hovered=False):
    """生成旋转图标 (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    color = QColor("#e0e0e0") if is_dark else QColor("#333333")
    theme_color = get_current_theme_color(is_hovered)
    
    if is_hovered:
        painter.translate(0, -2)
    
    pen_width = 2.5
    
    # 绘制圆弧箭头 (灰色圆弧)
    painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    rect = QRectF(8, 8, 16, 16)
    if direction == "left":
        start_angle = 45 * 16
        span_angle = 270 * 16
        painter.drawArc(rect, start_angle, span_angle)
        # 皮肤颜色箭头
        painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.save()
        painter.translate(19, 9)
        painter.rotate(30)
        painter.drawLine(0, 0, -4, 0)
        painter.drawLine(0, 0, 0, 4)
        painter.restore()
    else:
        start_angle = 135 * 16
        span_angle = -270 * 16
        painter.drawArc(rect, start_angle, span_angle)
        # 皮肤颜色箭头
        painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.save()
        painter.translate(13, 9)
        painter.rotate(-120)
        painter.drawLine(0, 0, -4, 0)
        painter.drawLine(0, 0, 0, 4)
        painter.restore()
        
    painter.end()
    return QIcon(pixmap)

def get_copy_move_icon(mode="copy", is_dark=True, is_hovered=False):
    """生成复制/移动图标 (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    color = QColor("#e0e0e0") if is_dark else QColor("#333333")
    theme_color = get_current_theme_color(is_hovered)
    
    if is_hovered:
        painter.translate(0, -2)
    
    pen_width = 2.5
    
    if mode == "copy":
        # 两个叠加的方框
        painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawRoundedRect(12, 12, 12, 12, 2, 2)
        painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawRoundedRect(8, 8, 12, 12, 2, 2)
    else:
        # 一个方框加一个皮肤颜色箭头
        painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawRoundedRect(8, 8, 16, 16, 2, 2)
        painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(12, 16, 20, 16)
        painter.drawLine(20, 16, 17, 13)
        painter.drawLine(20, 16, 17, 19)
        
    painter.end()
    return QIcon(pixmap)

def get_asc_desc_icon(mode="asc", is_dark=True, is_selected=False, is_hovered=False):
    """生成升序/降序图标 (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    theme_color = get_current_theme_color(is_hovered)
    
    if is_hovered:
        painter.translate(0, -2)
        
    pen_width = 2.5
    
    # 如果选中，在左侧绘制中点 "·"
    if is_selected:
        painter.setBrush(theme_color)
        painter.setPen(Qt.NoPen)
        # 调整点的位置到 x=4
        painter.drawEllipse(QPointF(4, 16), 2, 2)
    
    painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    # 调整 offset_x=6，使箭头中心位于 22
    # 点(4)到箭头中心(22)距离18px，去掉点半径(2)和箭头半径(4)，间距恰好为12px (约2个字符)
    # 同时右侧留出 32-26=6px，恰好为1个字符的间距
    offset_x = 6 
    if mode == "asc":
        # 上箭头
        painter.drawLine(16 + offset_x, 22, 16 + offset_x, 10)
        painter.drawLine(16 + offset_x, 10, 12 + offset_x, 14)
        painter.drawLine(16 + offset_x, 10, 20 + offset_x, 14)
    else:
        # 下箭头
        painter.drawLine(16 + offset_x, 10, 16 + offset_x, 22)
        painter.drawLine(16 + offset_x, 22, 12 + offset_x, 18)
        painter.drawLine(16 + offset_x, 22, 20 + offset_x, 18)
        
    painter.end()
    return QIcon(pixmap)

def get_scan_mode_icon(mode="single", is_dark=True, is_hovered=False):
    """
    生成扫描模式图标（一级/多级），支持皮肤颜色
    mode: "single" 或 "multi"
    is_hovered: 是否悬停，悬停时会有浮动偏移效果
    """
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # 获取主题颜色
    theme_color = get_current_theme_color(is_hovered)
    
    icon_color = QColor(255, 255, 255)
    
    # 悬停时的浮动效果 (向上偏移 4px)
    offset_y = -4 if is_hovered else 0
    
    # 绘制背景圆角矩形
    rect = QRect(4, 4 + offset_y, 24, 24)
    painter.setBrush(theme_color)
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(rect, 6, 6)

    # 绘制内部图标
    painter.setPen(QPen(icon_color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)

    if mode == "single":
        # 一级：文件夹
        # 绘制文件夹主体
        painter.drawRoundedRect(9, 11 + offset_y, 14, 10, 1, 1)
        # 绘制文件夹顶部边缘
        path = QPainterPath()
        path.moveTo(9, 11 + offset_y)
        path.lineTo(9, 10 + offset_y)
        path.lineTo(12, 10 + offset_y)
        path.lineTo(14, 11 + offset_y)
        painter.drawPath(path)
    else:
        # 多级：层叠效果
        # 后层文件夹
        painter.drawRoundedRect(12, 8 + offset_y, 11, 8, 1, 1)
        # 前层文件夹 (遮盖后层)
        painter.setBrush(theme_color)
        painter.drawRoundedRect(9, 12 + offset_y, 11, 8, 1, 1)
        painter.setBrush(Qt.NoBrush)
        # 顶部边缘
        painter.drawLine(9, 12 + offset_y, 11, 12 + offset_y)

    painter.end()
    return QIcon(pixmap)

def get_clear_action_icon(is_dark=True, is_hovered=False):
    """
    生成清除按钮图标（用于收藏/历史根节点），支持皮肤颜色
    is_hovered: 是否悬停，悬停时会有浮动偏移效果
    """
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # 获取主题颜色
    theme_color = get_current_theme_color(is_hovered)
    
    icon_color = QColor(255, 255, 255)
    
    # 悬停时的浮动效果 (向上偏移 4px)
    offset_y = -4 if is_hovered else 0
    
    # 绘制背景圆角矩形
    rect = QRect(4, 4 + offset_y, 24, 24)
    painter.setBrush(theme_color)
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(rect, 6, 6)

    # 绘制内部图标 (扫把风格，白色)
    painter.setPen(QPen(icon_color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)
    
    painter.save()
    painter.translate(16, 16 + offset_y)
    painter.rotate(-45)
    
    # 刷柄
    painter.drawLine(0, -6, 0, 0)
    # 刷头
    painter.drawLine(-4, 0, 4, 0)
    painter.drawLine(-4, 0, -5, 6)
    painter.drawLine(4, 0, 5, 6)
    painter.drawLine(-2, 0, -2, 5)
    painter.drawLine(0, 0, 0, 5)
    painter.drawLine(2, 0, 2, 5)
    
    painter.restore()

    painter.end()
    return QIcon(pixmap)


def get_sidebar_toggle_icon(is_collapsed=False, is_dark=True, is_hovered=False):
    """
    生成侧边栏切换按钮图标 (支持皮肤颜色)
    is_collapsed: True 为展开箭头（向右），False 为收起箭头（向左）
    is_hovered: 是否悬停，悬停时会有浮动偏移效果和颜色加深
    """
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # 获取主题颜色
    theme_color = get_current_theme_color(is_hovered)
    
    icon_color = QColor(255, 255, 255)
    
    # 悬停时的浮动效果 (向上偏移 4px)
    offset_y = -4 if is_hovered else 0
    
    # 绘制背景圆角矩形
    rect = QRect(4, 4 + offset_y, 24, 24)
    painter.setBrush(theme_color)
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(rect, 6, 6)

    # 绘制内部图标 (三角形箭头，白色)
    painter.setBrush(icon_color)
    
    # 箭头大小参数
    arrow_half_base = 5
    arrow_height = 8
    center_x = 16
    center_y = 16 + offset_y
    
    triangle = QPolygonF()
    if is_collapsed:
        # 向右箭头 (展开)
        triangle.append(QPointF(center_x - arrow_height / 2, center_y - arrow_half_base))
        triangle.append(QPointF(center_x - arrow_height / 2, center_y + arrow_half_base))
        triangle.append(QPointF(center_x + arrow_height / 2, center_y))
    else:
        # 向左箭头 (收起)
        triangle.append(QPointF(center_x + arrow_height / 2, center_y - arrow_half_base))
        triangle.append(QPointF(center_x + arrow_height / 2, center_y + arrow_half_base))
        triangle.append(QPointF(center_x - arrow_height / 2, center_y))
        
    painter.drawPolygon(triangle)
    painter.end()
    return QIcon(pixmap)


def get_layout_type_icon(mode="vertical", is_dark=True, is_selected=False, has_offset=True, is_hovered=False):
    """生成布局类型图标 (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # 获取主题颜色
    theme_color = get_current_theme_color(is_hovered)
    
    # 动态偏移效果
    offset_y = -4 if is_hovered else 0
    
    # 情况 A: 在分栏条中使用 (has_offset=False)，采用与扫描模式一致的圆角风格
    if not has_offset:
        # 绘制背景圆角矩形
        rect = QRect(4, 4 + offset_y, 24, 24)
        painter.setBrush(theme_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 6, 6)
        
        # 内部图标使用白色
        icon_color = QColor(255, 255, 255)
        pen_width = 2.0
        painter.setPen(QPen(icon_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        
        if mode == "vertical":
            painter.drawRoundedRect(10, 9 + offset_y, 5, 14, 1, 1)
            painter.drawRoundedRect(17, 9 + offset_y, 5, 14, 1, 1)
        else:
            painter.drawRoundedRect(9, 10 + offset_y, 14, 5, 1, 1)
            painter.drawRoundedRect(9, 17 + offset_y, 14, 5, 1, 1)
            
    # 情况 B: 在右键菜单中使用 (has_offset=True)，保持原有的线条风格和选中点
    else:
        color = QColor("#e0e0e0") if is_dark else QColor("#333333")
        pen_width = 2.5
        
        # 如果选中，在左侧绘制中点 "·"
        if is_selected:
            painter.setBrush(theme_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(4, 16), 2, 2)
        
        offset_x = 6
        if mode == "vertical":
            painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawRoundedRect(10 + offset_x, 8, 5, 16, 1, 1)
            painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawRoundedRect(17 + offset_x, 8, 5, 16, 1, 1)
        else:
            painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawRoundedRect(8 + offset_x, 10, 16, 5, 1, 1)
            painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawRoundedRect(8 + offset_x, 17, 16, 5, 1, 1)
        
    painter.end()
    return QIcon(pixmap)


def get_format_icon(is_dark=True, is_hovered=False):
    """生成格式筛选图标 (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    color = QColor("#e0e0e0") if is_dark else QColor("#333333")
    theme_color = get_current_theme_color(is_hovered)
    
    if is_hovered:
        painter.translate(0, -2)
        
    pen_width = 2.5
    
    # 绘制三个带圆点的横线
    # 横线 (灰色)
    painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(10, 11, 22, 11)
    painter.drawLine(10, 16, 22, 16)
    painter.drawLine(10, 21, 22, 21)
    
    # 圆点 (皮肤色)
    painter.setPen(Qt.NoPen)
    painter.setBrush(theme_color)
    painter.drawEllipse(QRectF(6.5, 9.5, 3, 3))
    painter.drawEllipse(QRectF(6.5, 14.5, 3, 3))
    painter.drawEllipse(QRectF(6.5, 19.5, 3, 3))
    
    painter.end()
    return QIcon(pixmap)

def get_size_icon(is_dark=True, is_hovered=False):
    """生成尺寸筛选图标 (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    color = QColor("#e0e0e0") if is_dark else QColor("#333333")
    theme_color = get_current_theme_color(is_hovered)
    
    if is_hovered:
        painter.translate(0, -2)
        
    pen_width = 2.5
    
    # 绘制大框 (灰色)
    painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawRoundedRect(8, 8, 16, 16, 2, 2)
    
    # 绘制小框 (皮肤色)
    painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawRoundedRect(12, 12, 8, 8, 1, 1)
    
    painter.end()
    return QIcon(pixmap)

def get_help_icon(is_dark=True, is_hovered=False):
    """生成使用说明图标 (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # 获取主题颜色
    theme_color = get_current_theme_color(is_hovered)
    if is_hovered:
        # 浮动效果：向上偏移 2px
        painter.translate(0, -2)
    
    # 绘制外圆
    pen_width = 2.5
    painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawEllipse(7, 7, 18, 18)
    
    # 绘制问号
    path = QPainterPath()
    path.moveTo(12.5, 13.5)
    path.arcTo(12.5, 11, 7, 6, 180, -180)
    path.lineTo(16, 17)
    painter.drawPath(path)
    
    # 绘制点
    painter.setBrush(theme_color)
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(QRectF(15, 20.5, 2.5, 2.5))
    
    painter.end()
    return QIcon(pixmap)

def get_lang_icon(lang_code="zh", is_dark=True, is_hovered=False):
    """生成语言切换图标 (支持皮肤颜色 - 字符图标: 中/繁/En/ja/de/fr)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    
    # 获取主题颜色
    theme_color = get_current_theme_color(is_hovered)
    if is_hovered:
        painter.translate(0, -2)
        
    # 映射语言代码到显示的文字
    lang_map = {
        "zh": "中",
        "zh_tw": "繁",
        "en": "En",
        "ja": "ja",
        "de": "de",
        "fr": "fr"
    }
    display_text = lang_map.get(_normalize_lang_code(lang_code), "En")
    
    # 绘制文字
    painter.setPen(theme_color)
    # 使用更粗的字体，并显著增大字号
    font = QFont("Arial", 14, QFont.Black) 
    if display_text in ["中", "繁"]:
        font.setPointSize(15)
    painter.setFont(font)
    
    # 在整个画布(32x32)中居中绘制文字
    painter.drawText(QRect(0, 0, 32, 32), Qt.AlignCenter, display_text)
    
    painter.end()
    return QIcon(pixmap)

def get_skin_icon(is_dark=True, is_hovered=False):
    """生成皮肤切换图标 (支持皮肤颜色)"""
    theme_color = get_current_theme_color(is_hovered)
    if is_hovered:
        return _get_tshirt_icon(theme_color.name(), is_hovered=True)
    return _get_tshirt_icon(theme_color.name(), is_hovered=False)

def _get_tshirt_icon(color_hex: str, is_hovered: bool = False):
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    if is_hovered:
        painter.translate(0, -2)
    
    pen_width = 2.5
    painter.setPen(QPen(QColor(color_hex), pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)
    
    path = QPainterPath()
    path.moveTo(12, 7)
    path.lineTo(10, 7)
    path.lineTo(6, 10)
    path.lineTo(8, 14)
    path.lineTo(10, 13)
    path.lineTo(10, 25)
    path.lineTo(22, 25)
    path.lineTo(22, 13)
    path.lineTo(24, 14)
    path.lineTo(26, 10)
    path.lineTo(22, 7)
    path.lineTo(20, 7)
    path.lineTo(18, 9)
    path.lineTo(16, 8)
    path.lineTo(14, 9)
    path.closeSubpath()
    painter.drawPath(path)
    
    painter.end()
    return QIcon(pixmap)

def get_search_btn_icon(is_dark=True, is_hovered=False):
    """生成搜索按钮图标 (支持皮肤颜色)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    color = QColor("#e0e0e0") if is_dark else QColor("#333333")
    theme_color = get_current_theme_color(is_hovered)
    
    if is_hovered:
        painter.translate(0, -2)
        
    pen_width = 2.0
    
    # 绘制搜索放大镜 (灰色)
    painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawEllipse(10, 10, 10, 10)
    painter.drawLine(18, 18, 23, 23)
    
    # 绘制外围的两个圆弧 (皮肤色)
    painter.setPen(QPen(theme_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawArc(6, 6, 20, 20, 45 * 16, 135 * 16)
    painter.drawArc(6, 6, 20, 20, 225 * 16, 135 * 16)
    
    # 在圆弧末端加小圆点 (皮肤色)
    painter.setBrush(theme_color)
    painter.drawEllipse(20, 6, 2, 2)
    painter.drawEllipse(10, 24, 2, 2)
    
    painter.end()
    return QIcon(pixmap)


def _detect_system_lang_code():
    try:
        sys_lang = QLocale.system().name()
    except Exception:
        sys_lang = ""
    code = _normalize_lang_code(sys_lang)
    if code in TRANSLATIONS:
        return code
    if "en" in TRANSLATIONS:
        return "en"
    if "zh" in TRANSLATIONS:
        return "zh"
    for k in TRANSLATIONS.keys():
        if isinstance(TRANSLATIONS.get(k), dict):
            return k
    return "zh"


def _ensure_zoom_defaults(img):
    if isinstance(img, dict):
        img.setdefault("zoom", 1.0)
        img.setdefault("minZoom", 1.0)
        img.setdefault("maxZoom", 4.0)
    return img


# ===================== 自定义 WebEngineView =====================
class FloatingSearchBox(QWidget):
    """居中弹出的搜索框"""
    sig_search = pyqtSignal(str)

    def __init__(self, parent=None, is_dark=True):
        super().__init__(parent)
        self.is_dark = is_dark
        # 增加 Qt.WindowStaysOnTopHint 确保在最前
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 尺寸缩小 20%：1200x160 -> 960x128
        self.setFixedSize(960, 128)
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(32, 16, 32, 16)
        
        # 外层容器
        self.container = QFrame()
        self.container.setObjectName("searchContainer")
        container_layout = QHBoxLayout(self.container)
        container_layout.setContentsMargins(24, 0, 24, 0)
        
        # 输入框
        self.input = QLineEdit()
        self.input.setObjectName("searchInput")
        self.input.setPlaceholderText("搜索图片")
        self.input.returnPressed.connect(self._on_search)
        container_layout.addWidget(self.input)
        
        # 搜索图标
        self.icon_label = QLabel()
        # 图标也相应缩小
        self.icon_label.setPixmap(get_search_btn_icon(self.is_dark).pixmap(50, 50))
        container_layout.addWidget(self.icon_label)
        
        layout.addWidget(self.container)
        self.apply_style()

    def apply_style(self):
        if self.is_dark:
            bg_color = "rgba(30, 34, 40, 0.98)"
            text_color = "#ffffff"
            border_color = "rgba(255, 255, 255, 0.15)"
            placeholder_color = "#888888"
        else:
            bg_color = "rgba(255, 255, 255, 0.98)"
            text_color = "#111111"
            border_color = "rgba(0, 0, 0, 0.1)"
            placeholder_color = "#aaaaaa"

        self.container.setStyleSheet(f"""
            #searchContainer {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 20px;
            }}
        """)
        
        # 字体大小也相应减小
        self.input.setStyleSheet(f"""
            #searchInput {{
                background: transparent;
                border: none;
                color: {text_color};
                font-size: 38px;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
                font-weight: 500;
            }}
            #searchInput::placeholder {{
                color: {placeholder_color};
            }}
        """)

    def _on_search(self):
        self.sig_search.emit(self.input.text())
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self.input.clear()
        self.input.setFocus()
        # 激活窗口以确保能接收到焦点丢失事件
        self.activateWindow()

    def event(self, event):
        # 监听点击外部或焦点丢失
        if event.type() == QEvent.WindowDeactivate:
            self.hide()
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class CustomWebEngineView(QWebEngineView):
    """自定义 WebEngineView 以支持右键菜单"""

    sig_open_explorer = pyqtSignal(str)
    sig_rotate_left = pyqtSignal(str)
    sig_rotate_right = pyqtSignal(str)
    sig_copy_image = pyqtSignal(str)
    sig_move_image = pyqtSignal(str)
    sig_delete_image = pyqtSignal(str)
    sig_refresh = pyqtSignal()
    sig_sort_changed = pyqtSignal(str)  # name, date_asc, date_desc, size
    sig_layout_changed = pyqtSignal(str)  # horizontal, vertical
    sig_format_changed = pyqtSignal(str)
    sig_size_changed = pyqtSignal(str)

    def __init__(self, parent=None, lang='zh'):
        super().__init__(parent)
        self.lang = lang

    def contextMenuEvent(self, event):
        if not WEBENGINE_AVAILABLE:
            return super().contextMenuEvent(event)

        try:
            # 如果没有图片，不显示右键菜单
            main_window = self.window()
            if not getattr(main_window, "current_img_data", None):
                return

            # 获取点击位置的数据
            data = self.page().contextMenuData()

            # 获取翻译
            t = TRANSLATIONS[self.lang]

            # 判断当前是否为暗黑模式
            text_color = self.palette().color(QPalette.Text)
            is_dark = text_color.lightness() > 128

            # 创建自定义菜单
            menu = Win11Menu(parent=self, is_dark=is_dark)

            # 检查是否点击了图片
            if data.mediaType() == QWebEngineContextMenuData.MediaTypeImage:
                url = data.mediaUrl()
                if url.isLocalFile():
                    file_path = url.toLocalFile()

                    # 1. 在资源管理器中打开
                    action_open = QAction(
                        get_folder_icon(is_dark),
                        t['menu_open_explorer'],
                        self,
                    )
                    action_open.triggered.connect(
                        lambda: self.sig_open_explorer.emit(file_path)
                    )
                    menu.addAction(action_open)

                    menu.addSeparator()

                    # 2. 旋转
                    action_left = QAction(
                        get_rotate_icon("left", is_dark), t['menu_rotate_left'], self
                    )
                    action_left.triggered.connect(
                        lambda: self.sig_rotate_left.emit(file_path)
                    )
                    menu.addAction(action_left)

                    action_right = QAction(
                        get_rotate_icon("right", is_dark),
                        t['menu_rotate_right'],
                        self,
                    )
                    action_right.triggered.connect(
                        lambda: self.sig_rotate_right.emit(file_path)
                    )
                    menu.addAction(action_right)

                    menu.addSeparator()

                    # 复制/移动
                    action_copy = QAction(
                        get_copy_move_icon("copy", is_dark),
                        t['menu_copy_to'],
                        self
                    )
                    action_copy.triggered.connect(
                        lambda: self.sig_copy_image.emit(file_path)
                    )
                    menu.addAction(action_copy)

                    action_move = QAction(
                        get_copy_move_icon("move", is_dark),
                        t['menu_move_to'],
                        self
                    )
                    action_move.triggered.connect(
                        lambda: self.sig_move_image.emit(file_path)
                    )
                    menu.addAction(action_move)

                    menu.addSeparator()

                    # 3. 删除
                    action_delete = QAction(
                        get_delete_icon(is_dark), t['menu_delete'], self
                    )
                    action_delete.triggered.connect(
                        lambda: self.sig_delete_image.emit(file_path)
                    )
                    menu.addAction(action_delete)

                    menu.exec_(event.globalPos())
                    return

            # 如果点击的是背景（或非本地图片）
            # 添加通用菜单：刷新、排序

            action_refresh = QAction(
                get_refresh_icon(is_dark), t['menu_refresh'], self
            )
            action_refresh.triggered.connect(self.sig_refresh.emit)
            menu.addAction(action_refresh)

            menu.addSeparator()

            # 排序子菜单
            sort_menu = menu.addMenu(
                get_sort_icon(is_dark),
                t['menu_sort']
            )

            # 获取当前排序模式以显示选中状态
            main_window = self.window()
            current_sort = getattr(main_window, "current_sort_mode", "name_asc")

            def add_sort_action(menu_obj, mode, icon_type, label_key):
                # 获取选中状态
                is_selected = (current_sort == mode)
                # 图标右侧已留出6px(约1个字符)间距，此处前缀设为空
                prefix = ""
                # 为每一项添加图标 (升序/降序)，并传入选中状态以绘制左侧中点
                icon = get_asc_desc_icon(icon_type, is_dark, is_selected=is_selected)
                action = QAction(icon, prefix + t[label_key], self)
                action.triggered.connect(lambda: self.sig_sort_changed.emit(mode))
                menu_obj.addAction(action)

            # 1. 名称排序
            add_sort_action(sort_menu, "name_asc", "asc", "menu_sort_name_asc")
            add_sort_action(sort_menu, "name_desc", "desc", "menu_sort_name_desc")
            
            sort_menu.addSeparator() # 三栏之间要有分隔线
            
            # 2. 日期排序
            add_sort_action(sort_menu, "date_desc", "desc", "menu_sort_date_desc")
            add_sort_action(sort_menu, "date_asc", "asc", "menu_sort_date_asc")
            
            sort_menu.addSeparator() # 三栏之间要有分隔线
            
            # 3. 大小排序
            add_sort_action(sort_menu, "size_desc", "desc", "menu_sort_size_desc")
            add_sort_action(sort_menu, "size_asc", "asc", "menu_sort_size_asc")

            menu.addSeparator()

            # 格式筛选子菜单
            format_menu = menu.addMenu(
                get_format_icon(is_dark),
                t['format_label']
            )
            
            # 获取当前选中的格式
            current_format = getattr(main_window, "current_format_filter", t['all_formats'])
            
            def add_format_action(menu_obj, label):
                # 保持与排序菜单一致：点后面跟2个空格
                prefix = "·  " if current_format == label else "   "
                action = QAction(prefix + label, self)
                action.triggered.connect(lambda: self.sig_format_changed.emit(label))
                menu_obj.addAction(action)
            
            formats = [t['all_formats'], "JPG", "PNG", "GIF", "BMP", "WEBP", "SVG", "RAW"]
            for f in formats:
                add_format_action(format_menu, f)

            # 尺寸筛选子菜单
            size_menu = menu.addMenu(
                get_size_icon(is_dark),
                t['size_label']
            )
            
            # 获取当前选中的尺寸
            current_size = getattr(main_window, "current_size_filter", t['all_sizes'])
            
            def add_size_action(menu_obj, label):
                # 保持与排序菜单一致：点后面跟2个空格
                prefix = "·  " if current_size == label else "   "
                action = QAction(prefix + label, self)
                action.triggered.connect(lambda: self.sig_size_changed.emit(label))
                menu_obj.addAction(action)
                
            sizes = [t['all_sizes'], t['large_img'], t['medium_img'], t['small_img']]
            for s in sizes:
                add_size_action(size_menu, s)

            menu.addSeparator()

            # 布局子菜单
            layout_menu = menu.addMenu(
                get_layout_icon(is_dark),
                t['menu_layout']
            )

            current_layout = getattr(main_window, "current_layout_mode", "vertical")

            def add_layout_action(menu_obj, mode, label_key):
                # 获取选中状态
                is_selected = (current_layout == mode)
                # 图标右侧已留出6px(约1个字符)间距，此处前缀设为空
                prefix = ""
                # 为每一项添加布局图标，并传入选中状态以绘制左侧中点
                icon = get_layout_type_icon(mode, is_dark, is_selected=is_selected)
                action = QAction(icon, prefix + t[label_key], self)
                action.triggered.connect(lambda: self.sig_layout_changed.emit(mode))
                menu_obj.addAction(action)

            add_layout_action(layout_menu, "vertical", "menu_layout_vertical")
            add_layout_action(layout_menu, "horizontal", "menu_layout_horizontal")

            menu.exec_(event.globalPos())

        except Exception as e:
            print(f"ContextMenu Error: {e}")
            super().contextMenuEvent(event)


class LanguageComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_hovered = False
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self.is_hovered = True
        self.update_icon()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update_icon()
        super().leaveEvent(event)

    def update_icon(self):
        is_dark = True
        if hasattr(self.window(), "is_dark_theme"):
            is_dark = self.window().is_dark_theme
        
        # 获取当前项的语言代码
        lang_code = self.itemData(self.currentIndex()) or "zh"
        icon = get_lang_icon(lang_code, is_dark, self.is_hovered)
        self.setItemIcon(self.currentIndex(), icon)

    def mousePressEvent(self, event):
        try:
            self.showPopup()
        except Exception:
            pass
        event.accept()
        return

class HoverButton(QPushButton):
    """支持悬停图标切换和浮动效果的按钮"""
    def __init__(self, icon_func, parent=None):
        super().__init__(parent)
        self.icon_func = icon_func
        self.is_hovered = False
        self.setMouseTracking(True)
        self.setIconSize(QSize(24, 24))
        self.update_icon()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update_icon()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update_icon()
        super().leaveEvent(event)

    def update_icon(self):
        is_dark = True
        if hasattr(self.window(), "is_dark_theme"):
            is_dark = self.window().is_dark_theme
        self.setIcon(self.icon_func(is_dark, self.is_hovered))


# ===================== 自定义 Splitter =====================
class CollapsibleSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.is_hovered = False
        self.button_height = 50  # 增加高度以保持比例 (40 -> 50)
        self.button_width = 32   # 与 handle 宽度一致 (36 -> 32)
        self.setMouseTracking(True)
        self.press_global_pos = None  # 记录按下全局位置，用于区分点击和拖拽

        # 布局切换按钮配置
        self.layout_btn_height = 36  # 增加高度以适应大图标 (24 -> 36)
        self.layout_btn_spacing = 8  # 两个按钮间距

    def _get_button_rects(self):
        h = self.height()
        w = self.width()

        # 1. 布局切换按钮 (放置在顶部)
        # 调整 y 坐标从 10 移至 5，使其与树状图首行图标水平对齐，并向上移动一点
        layout_btn_y = 5
        layout_btn_rect = QRect(0, layout_btn_y, w, self.layout_btn_height)

        # 2. 折叠按钮 (放置在垂直居中位置)
        collapse_btn_y = (h - self.button_height) // 2
        collapse_btn_rect = QRect(0, collapse_btn_y, w, self.button_height)

        return layout_btn_rect, collapse_btn_rect

    def paintEvent(self, event):
        # 绘制默认样式
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 获取主题颜色
        is_dark = True
        if hasattr(self.window(), "is_dark_theme"):
            is_dark = self.window().is_dark_theme

        if is_dark:
            bg_normal = QColor("#333333")
            bg_hover = QColor("#555555")
            icon_color = QColor("#AAAAAA")
        else:
            bg_normal = QColor("#F0F0F0")
            bg_hover = QColor("#D0D0D0")
            icon_color = QColor("#666666")

        layout_btn_rect, collapse_btn_rect = self._get_button_rects()

        mouse_pos = self.mapFromGlobal(QCursor.pos())

        # --- 绘制布局切换按钮 ---
        is_layout_hovered = layout_btn_rect.contains(mouse_pos)
        # 移除底色填充，统一由图标自身处理

        # 获取当前布局模式
        current_mode = "vertical"
        if isinstance(self.parent(), CustomSplitter):
            current_mode = getattr(self.parent(), "current_layout_mode", "vertical")

        # 使用全局 get_layout_type_icon 绘制图标，确保风格统一
        # 设置 has_offset=False 确保在分栏条中左右居中对齐
        icon = get_layout_type_icon(current_mode, is_dark, has_offset=False, is_hovered=is_layout_hovered)
        
        # 计算图标绘制区域
        icon_w = 32  # 图标大小 (30 -> 32)
        icon_h = 32
        icon_x = (self.width() - icon_w) // 2
        icon_y = layout_btn_rect.y() + (self.layout_btn_height - icon_h) // 2
        
        icon_rect = QRect(icon_x, icon_y, icon_w, icon_h)
        icon.paint(painter, icon_rect)

        # --- 绘制折叠按钮 ---
        is_collapse_hovered = collapse_btn_rect.contains(mouse_pos)
        
        # 根据当前状态决定箭头方向
        is_collapsed = False
        if isinstance(self.parent(), QSplitter):
            sizes = self.parent().sizes()
            if sizes and sizes[0] < 10:  # 左侧栏宽度很小
                is_collapsed = True
        
        # 使用统一的蓝色风格绘制折叠按钮图标
        collapse_icon = get_sidebar_toggle_icon(is_collapsed, is_dark, is_hovered=is_collapse_hovered)
        
        # 计算图标绘制区域
        collapse_icon_w = 32  # 图标大小 (30 -> 32)
        collapse_icon_h = 32
        collapse_icon_x = (self.width() - collapse_icon_w) // 2
        collapse_icon_y = collapse_btn_rect.y() + (self.button_height - collapse_icon_h) // 2
        
        collapse_icon_rect = QRect(collapse_icon_x, collapse_icon_y, collapse_icon_w, collapse_icon_h)
        collapse_icon.paint(painter, collapse_icon_rect)

    def mouseMoveEvent(self, event):
        # 如果已经按下了按钮（正在进行点击操作判定），则屏蔽移动事件
        # 防止鼠标移出按钮区域后触发 super().mouseMoveEvent 导致 Splitter 变动
        if self.press_global_pos is not None:
            return

        layout_btn_rect, collapse_btn_rect = self._get_button_rects()

        if layout_btn_rect.contains(event.pos()):
            self.setCursor(Qt.PointingHandCursor)

            # 设置 Tooltip
            current_mode = "vertical"
            lang = 'zh'
            if isinstance(self.parent(), CustomSplitter):
                current_mode = getattr(self.parent(), "current_layout_mode", "vertical")
                lang = getattr(self.parent(), "lang", "zh")
            
            t = TRANSLATIONS[lang]
            mode_text = t['layout_vertical'] if current_mode == "vertical" else t['layout_horizontal']
            QToolTip.showText(event.globalPos(), mode_text)

        elif collapse_btn_rect.contains(event.pos()):
            self.setCursor(Qt.PointingHandCursor)
            lang = 'zh'
            if isinstance(self.parent(), CustomSplitter):
                lang = getattr(self.parent(), "lang", "zh")
            t = TRANSLATIONS[lang]
            QToolTip.showText(event.globalPos(), t['sidebar_toggle'])
        else:
            self.setCursor(Qt.SplitHCursor)
            QToolTip.hideText()
            super().mouseMoveEvent(event)

        # 触发重绘以更新悬停效果
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            layout_btn_rect, collapse_btn_rect = self._get_button_rects()
            if layout_btn_rect.contains(event.pos()) or collapse_btn_rect.contains(
                event.pos()
            ):
                self.press_global_pos = event.globalPos()
                return  # 不调用 super，拦截拖动开始

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            hasattr(self, "press_global_pos")
            and self.press_global_pos
            and event.button() == Qt.LeftButton
        ):
            moved = (event.globalPos() - self.press_global_pos).manhattanLength()

            # 转换为本地坐标
            local_pos = self.mapFromGlobal(self.press_global_pos)
            layout_btn_rect, collapse_btn_rect = self._get_button_rects()

            if moved < 5:
                if layout_btn_rect.contains(local_pos):
                    if isinstance(self.parent(), CustomSplitter):
                        self.parent().toggle_layout_mode()
                elif collapse_btn_rect.contains(local_pos):
                    if isinstance(self.parent(), CustomSplitter):
                        self.parent().toggle_left_panel()

            # 如果我们拦截了按下事件，就不应该调用父类的释放事件，
            # 否则可能会导致 QSplitter 误判为拖动结束，导致布局异常
            self.press_global_pos = None
            return

        self.press_global_pos = None
        super().mouseReleaseEvent(event)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()


class ClickableLabel(QLabel):
    """可点击的标签"""
    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class CustomSplitter(QSplitter):
    sig_toggle_layout = pyqtSignal()  # 新增信号

    def __init__(self, orientation, parent=None, lang='zh'):
        super().__init__(orientation, parent)
        self.lang = lang
        self.setHandleWidth(32)  # 调整宽度以适应图标 (36 -> 32)
        self.last_left_width = 300  # 默认展开宽度
        self.current_layout_mode = "vertical"  # 默认为垂直模式
        # 启用实时重绘，以便拖动时能看到布局变化，但我们会节流通知 JS
        self.setOpaqueResize(True)

    def set_layout_mode(self, mode):
        """设置布局模式并刷新 Handle"""
        self.current_layout_mode = mode
        self.update()
        # 同时也需要刷新 handle
        for i in range(self.count()):
            handle = self.handle(i)
            if handle:
                handle.update()
        # self.setCollapsible(0, False) # 移至 addWidget 后调用，避免 Index out of range

    def refresh_icons(self):
        """刷新 Handle 中的所有图标"""
        for i in range(self.count()):
            handle = self.handle(i)
            if handle:
                handle.update()

    def createHandle(self):
        return CollapsibleSplitterHandle(self.orientation(), self)

    def toggle_layout_mode(self):
        """切换布局模式"""
        self.sig_toggle_layout.emit()

    def toggle_left_panel(self):
        # 假设左侧面板是第一个 widget (index 0)
        if self.count() < 2:
            return

        current_sizes = self.sizes()
        if not current_sizes:
            return

        left_width = current_sizes[0]

        if left_width > 10:
            # 收起
            # 【修复】防止记录过大的宽度
            if left_width > 600:
                left_width = 600

            self.last_left_width = left_width
            # 必须允许折叠才能设为0
            self.setCollapsible(0, True)
            self.widget(0).setMinimumWidth(0)
            self.widget(0).setMaximumWidth(0)  # 强制最大宽度为0，确保完全隐藏内容
            self.setSizes([0, sum(current_sizes)])
        else:
            # 展开
            self.widget(0).setVisible(True)  # 确保可见
            self.setCollapsible(0, False)  # 暂时禁止折叠，防止 QSplitter 自动隐藏
            self.widget(0).setMaximumWidth(16777215)  # 恢复最大宽度

            # 【修复】先强制设置最小宽度为目标宽度，确保 Splitter 必须让出空间
            target_width = int(
                self.last_left_width if self.last_left_width > 50 else 250
            )

            # 【安全限制】防止宽度过大 (限制为 800px 或更小)
            if target_width > 800:
                target_width = 800

            self.widget(0).setMinimumWidth(target_width)

            # 设置尺寸 (总和必须等于当前宽度)
            total_width = sum(current_sizes)
            self.setSizes([target_width, total_width - target_width])

            # 强制刷新布局
            QApplication.processEvents()

            # 延时恢复可折叠属性，防止立即回弹
            QTimer.singleShot(100, lambda: self._restore_collapsible())

    def _restore_collapsible(self):
        """恢复左侧栏可折叠属性"""
        if self.count() > 0:
            self.widget(0).setMinimumWidth(50)
            self.setCollapsible(0, True)

        # 再次强制刷新布局状态
        QApplication.processEvents()


# ===================== 核心配置 =====================
VERSION = "1.0.3"  # 版本标记
FIXED_COLUMN_COUNT = 4  # 固定列数为4
COLUMN_SPACING = 10  # 列间距
ITEM_SPACING = 10  # 项间距
WIDGET_MARGINS = (15, 15, 15, 15)  # 边距
MAX_HISTORY_DIRS = 25  # 历史目录数
# 窗口默认尺寸（可调整）
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 800
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
# 性能配置
MAX_THREADS = 2  # 降低线程数，减少崩溃
# 滚动加载阈值（距离底部多少像素触发加载）
SCROLL_THRESHOLD = 100
# 图片质量配置（核心优化：最高质量小图）
IMAGE_QUALITY_SCALE = 2.0  # 缩放系数提升至2.0，预加载更高清小图
# 预览方式配置
USE_SYSTEM_VIEWER = False  # 使用优化后的内置查看器
# 内置预览窗口配置
PREVIEW_SCREEN_HEIGHT_RATIO = 1.0  # 窗口高度为屏幕高度的100%
PREVIEW_MAX_WIDTH_RATIO = 0.95  # 窗口最大宽度为屏幕宽度的95%
PREVIEW_MIN_SIZE = (400, 300)  # 窗口最小尺寸
# 翻页按钮配置
BUTTON_SIZE = 60  # 圆形按钮尺寸
BUTTON_RADIUS = 30  # 按钮圆角半径
BUTTON_SPACING = 20  # 按钮与图片间距（增大至20px）
# 配置文件相关
APP_COMPANY = "ImageViewer"
APP_NAME = "WaterfallImageViewer"
# =====================================================


# 解决中文路径问题（增强版）
def fix_chinese_path():
    try:
        # 控制台编码修复
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
        # Qt路径编码修复
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = ""
        os.environ["PYTHONIOENCODING"] = "utf-8"
        os.environ["QT_CHARSET"] = "utf-8"

        # 强制启用 WebEngine GPU 加速
    # 移除可能导致不稳定的 native-gpu-memory-buffers
    # os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--ignore-gpu-blacklist --enable-gpu-rasterization"
    except Exception as e:
        print(f"修复中文路径失败: {e}")


# 路径转义处理（兼容特殊符号）
def safe_path(path):
    """安全处理路径，确保中文/特殊符号正常识别"""
    if not path:
        return ""
    # 转换为绝对路径并标准化
    path = os.path.abspath(path)
    # 处理Windows长路径
    if sys.platform == "win32" and not path.startswith("\\\\?\\"):
        path = f"\\\\?\\{path}"
    return path


# 全局线程锁
g_mutex = QMutex()


# 信号发射器
class WorkerSignals(QObject):
    # path, pixmap, width, height
    finished = pyqtSignal(str, QPixmap, int, int)


class ImageLoadTask(QRunnable):
    def __init__(self, path, col_width, task_id):
        super().__init__()
        self.path = safe_path(path)
        self.col_width = col_width
        self.task_id = task_id
        self.signals = WorkerSignals()
        self.setAutoDelete(True)
        self.is_finished = False

    def cancel(self):
        self.is_finished = True

    def run(self):
        if self.is_finished:
            return

        try:
            # 检查文件是否存在
            if not os.path.exists(self.path):
                self.is_finished = True
                return

            # 使用 Pillow 加载并处理图片
            with Image.open(self.path) as img:
                # 处理 EXIF 旋转
                img = ImageOps.exif_transpose(img)
                orig_w, orig_h = img.size

                # 计算目标高度，保持比例
                scale = self.col_width / orig_w
                target_h = int(orig_h * scale)

                # 高质量缩放
                resample_method = getattr(Image.Resampling, "LANCZOS", Image.LANCZOS)
                img = img.resize((self.col_width, target_h), resample_method)

                # 转换为 RGB/RGBA
                if img.mode not in ["RGB", "RGBA"]:
                    img = img.convert("RGB")

                # 转换为 QImage
                img_data = img.tobytes()
                q_format = (
                    QImage.Format_RGBA8888
                    if img.mode == "RGBA"
                    else QImage.Format_RGB888
                )
                q_img = QImage(
                    img_data,
                    self.col_width,
                    target_h,
                    self.col_width * len(img.mode),
                    q_format,
                ).copy()

                # 在主线程中创建 QPixmap 是最安全的，但为了兼容现有代码逻辑，
                # 我们先在这里生成 QPixmap。注意：在某些环境下这可能导致不稳定。
                # 如果出现崩溃，应改为在信号中传递 QImage。
                pixmap = QPixmap.fromImage(q_img)

                if not self.is_finished:
                    # 还原原始路径用于匹配
                    original_path = (
                        self.path.replace("\\\\?\\", "")
                        if sys.platform == "win32"
                        else self.path
                    )
                    self.signals.finished.emit(
                        original_path, pixmap, self.col_width, target_h
                    )

        except Exception as e:
            print(f"ImageLoadTask error: {e}")
        finally:
            self.is_finished = True


# ===================== 元数据缓存 (SQLite) =====================
class MetadataCache:
    def __init__(self):
        # 获取系统数据目录
        data_dir = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        
        self.db_path = os.path.join(data_dir, "metadata_cache.db")
        self._lock = QMutex()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL") # 使用 WAL 模式提升并发读写性能
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS image_metadata (
                    path TEXT PRIMARY KEY,
                    width INTEGER,
                    height INTEGER,
                    size INTEGER,
                    mtime REAL
                )
            """)
            # 为路径建立索引以加快查询
            conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON image_metadata(path)")

    def get_metadata_batch(self, paths):
        """批量获取元数据，极大提升扫描性能"""
        if not paths:
            return {}
        
        results = {}
        try:
            # 使用上下文管理器确保连接关闭
            with sqlite3.connect(self.db_path) as conn:
                # SQLite 默认一次最多处理 999 个变量，我们分片处理
                for i in range(0, len(paths), 900):
                    chunk = paths[i:i+900]
                    placeholders = ",".join(["?"] * len(chunk))
                    cursor = conn.execute(
                        f"SELECT path, width, height, size, mtime FROM image_metadata WHERE path IN ({placeholders})",
                        chunk
                    )
                    for row in cursor.fetchall():
                        results[row[0]] = (row[1], row[2], row[3], row[4])
        except Exception as e:
            print(f"Error fetching metadata batch: {e}")
        return results

    def save_metadata_batch(self, items):
        """批量保存元数据，提升性能"""
        if not items:
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO image_metadata (path, width, height, size, mtime) VALUES (?, ?, ?, ?, ?)",
                    [(item['path'], item['w'], item['h'], item['size'], item['mtime']) for item in items]
                )
        except Exception as e:
            print(f"Error saving metadata batch: {e}")

# 全局缓存实例
g_metadata_cache = MetadataCache()


class ScanSignals(QObject):
    finished = pyqtSignal(list, int)
    batch_ready = pyqtSignal(list, int)  # 新增信号：分批发送数据


class ScanWorker(QRunnable):
    def __init__(self, dir_path, scan_id, recursive=False):
        super().__init__()
        self.dir_path = dir_path
        self.scan_id = scan_id
        self.recursive = recursive
        self.signals = ScanSignals()
        self.setAutoDelete(True)
        self.is_aborted = False

    def abort(self):
        self.is_aborted = True

    def run(self):
        img_data = []
        batch_data = []  # 临时存储当前批次
        cache_save_batch = [] # 待写入缓存的批次
        current_batch_size = 10  # 初始批次较小，以便快速看到第一批图
        max_batch_size = 100    # 随着加载进行，增加批次大小以提高效率

        img_extensions = (
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".webp",
            ".ico",
        )
        try:
            # os.walk works with \\\\?\\ paths on Windows
            scan_path = self.dir_path

            # Print scan path for debug

            # Ensure scan_path exists and is a directory
            if not os.path.exists(scan_path):
                self.signals.finished.emit([], self.scan_id)
                return

            if self.recursive:
                walker = os.walk(scan_path)
            else:
                # Non-recursive: only scan the current directory
                try:
                    all_files = os.listdir(scan_path)
                    files = [
                        f
                        for f in all_files
                        if os.path.isfile(os.path.join(scan_path, f))
                    ]
                    walker = [(scan_path, [], files)]
                except Exception as e:
                    walker = []

            count = 0
            for root, _, files in walker:
                if self.is_aborted:
                    return
                
                # 过滤出图片文件
                img_files = [f for f in files if f.lower().endswith(img_extensions)]
                if not img_files:
                    continue
                
                # 构建完整路径并获取文件状态（用于校验缓存是否失效）
                file_info_list = []
                for f in img_files:
                    if self.is_aborted: return
                    f_path = os.path.join(root, f)
                    try:
                        st = os.stat(f_path)
                        file_info_list.append({
                            'path': f_path,
                            'size': st.st_size,
                            'mtime': st.st_mtime
                        })
                    except:
                        continue
                
                # 1. 批量从缓存读取元数据
                all_paths = [info['path'] for info in file_info_list]
                cached_data = g_metadata_cache.get_metadata_batch(all_paths)
                
                for info in file_info_list:
                    if self.is_aborted:
                        return
                    
                    file_path = info['path']
                    size_val = info['size']
                    mtime_val = info['mtime']
                    
                    # 检查缓存命中且未过期
                    hit = False
                    if file_path in cached_data:
                        c_w, c_h, c_size, c_mtime = cached_data[file_path]
                        if c_size == size_val and abs(c_mtime - mtime_val) < 0.01:
                            w, h = c_w, c_h
                            item = {
                                "path": file_path,
                                "w": w,
                                "h": h,
                                "size": size_val,
                                "mtime": mtime_val,
                            }
                            img_data.append(item)
                            batch_data.append(item)
                            count += 1
                            hit = True
                    
                    if hit:
                        # 如果批次满了，立即发送
                        if len(batch_data) >= current_batch_size:
                            self.signals.batch_ready.emit(batch_data, self.scan_id)
                            batch_data = []
                            if current_batch_size < max_batch_size:
                                current_batch_size = min(max_batch_size, current_batch_size + 10)
                        continue

                    # 2. 缓存失效或不存在，使用 Pillow 解析
                    try:
                        # Use Pillow instead of QImageReader
                        with Image.open(file_path) as img:
                            w, h = img.size
                            # Handle EXIF Orientation
                            try:
                                exif = img._getexif()
                                if exif:
                                    orientation = exif.get(274)  # 274 is Orientation
                                    if orientation in (5, 6, 7, 8):
                                        w, h = h, w
                            except:
                                pass

                        item = {
                            "path": file_path,
                            "w": w,
                            "h": h,
                            "size": size_val,
                            "mtime": mtime_val,
                        }
                        img_data.append(item)
                        batch_data.append(item)
                        cache_save_batch.append(item)
                        count += 1

                        # 定期保存到缓存数据库
                        if len(cache_save_batch) >= 50:
                            g_metadata_cache.save_metadata_batch(cache_save_batch)
                            cache_save_batch = []

                        # 发送批次数据
                        if len(batch_data) >= current_batch_size:
                            self.signals.batch_ready.emit(batch_data, self.scan_id)
                            batch_data = []
                            if current_batch_size < max_batch_size:
                                current_batch_size = min(max_batch_size, current_batch_size + 10)

                    except Exception:
                        pass

            # 发送剩余的批次数据
            if batch_data:
                self.signals.batch_ready.emit(batch_data, self.scan_id)

            # 保存剩余的缓存数据
            if cache_save_batch:
                g_metadata_cache.save_metadata_batch(cache_save_batch)

            self.signals.finished.emit(img_data, self.scan_id)
        except Exception as e:
            traceback.print_exc()
            self.signals.finished.emit([], self.scan_id)

    def _safe_read_size(self, reader):
        try:
            return reader.size()
        except Exception:
            return QSize(0, 0)


# 图像处理函数（仅缩放，移除增强）
def process_enhanced_image(pil_image, target_w, target_h):
    """
    仅执行缩放，不进行图像增强（锐化、对比度等）
    """
    try:
        # 使用 Lanczos (兰索斯) 算法进行高质量缩放
        resample_method = getattr(Image.Resampling, "LANCZOS", Image.LANCZOS)
        hq_img = pil_image.resize((target_w, target_h), resample_method)
        return hq_img
    except Exception as e:
        print(f"图像处理失败: {e}")
        return pil_image.resize((target_w, target_h))


# 扩展 WorkerSignals 以支持预览加载
class PreviewWorkerSignals(QObject):
    # path, q_img, scale_factor, pil_image
    result = pyqtSignal(str, QImage, float, object)


class PreviewLoadTask(QRunnable):
    def __init__(self, path, view_width, view_height):
        super().__init__()
        self.path = safe_path(path)
        self.view_width = view_width
        self.view_height = view_height
        self.signals = PreviewWorkerSignals()
        self.setAutoDelete(True)

    def run(self):
        try:
            if not os.path.exists(self.path):
                return

            pil_image = Image.open(self.path)
            pil_image = ImageOps.exif_transpose(pil_image)
            if pil_image.mode not in ["RGB", "RGBA"]:
                pil_image = pil_image.convert(
                    "RGB" if pil_image.mode != "RGBA" else "RGBA"
                )

            available_w = max(100, self.view_width - 160)
            available_h = max(100, self.view_height - 60)

            scale_w = available_w / pil_image.width
            scale_h = available_h / pil_image.height
            scale_factor = min(scale_w, scale_h, 1.0)

            target_w = int(pil_image.width * scale_factor)
            target_h = int(pil_image.height * scale_factor)

            enhanced_img = process_enhanced_image(pil_image, target_w, target_h)

            img_data = enhanced_img.tobytes()
            q_format = (
                QImage.Format_RGBA8888
                if enhanced_img.mode == "RGBA"
                else QImage.Format_RGB888
            )
            q_img = QImage(
                img_data,
                target_w,
                target_h,
                target_w * len(enhanced_img.mode),
                q_format,
            ).copy()
            # Do NOT create QPixmap here. It is unsafe in threads.

            # 还原原始路径（去掉 \\?\ 前缀用于匹配）
            original_path = (
                self.path.replace("\\\\?\\", "")
                if sys.platform == "win32"
                else self.path
            )
            self.signals.result.emit(original_path, q_img, scale_factor, pil_image)

        except Exception as e:
            print(f"后台加载预览失败: {e}")


# 圆角图片标签
class RoundedImageLabel(QLabel):
    def __init__(self, radius=12, parent=None):
        super().__init__(parent)
        self.radius = radius
        self.img_pixmap = None
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QLabel { background-color: transparent; border: none; }")
        
        # 添加渐现效果支持
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(300)
        self.fade_animation.setStartValue(0)
        self.fade_animation.setEndValue(1)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)

    def start_fade_in(self):
        self.fade_animation.start()

    def setPixmap(self, pixmap):
        self.img_pixmap = pixmap
        # 保持缩放比例
        if pixmap and not pixmap.isNull():
            super().setPixmap(
                pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            super().setPixmap(pixmap)
        self.update()

    def paintEvent(self, event):
        if not self.img_pixmap or self.img_pixmap.isNull():
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.HighQualityAntialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        rect_f = QRectF(rect)
        path = QPainterPath()
        path.addRoundedRect(rect_f, self.radius, self.radius)

        # 绘制阴影
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 30))
        shadow_rect = self.rect().adjusted(2, 2, -1, -1)
        painter.drawRoundedRect(QRectF(shadow_rect), self.radius, self.radius)

        # 绘制图片
        painter.setClipPath(path)

        # 重新计算缩放后的绘制区域，以保持比例居中
        if self.img_pixmap:
            scaled_pixmap = self.img_pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            x = (self.width() - scaled_pixmap.width()) // 2
            y = (self.height() - scaled_pixmap.height()) // 2
            painter.drawPixmap(x, y, scaled_pixmap)


class HTMLDelegate(QStyledItemDelegate):
    sig_scan_mode_changed = pyqtSignal(bool)
    sig_toggle_theme = pyqtSignal()
    sig_clear_root = pyqtSignal(str)

    def __init__(self, parent=None, lang='zh'):
        super().__init__(parent)
        self.lang = lang
        self.hover_index = QModelIndex()
        self.hover_pos = QPoint()
        
        # 启用鼠标追踪以支持悬停效果
        if parent:
            parent.setMouseTracking(True)

    def paint(self, painter, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)

        painter.save()

        # 加载自定义字体 SourceHanSans-Bold
        font_id = QFontDatabase.addApplicationFont(resource_path("resources/SourceHanSans-Bold.ttc"))
        custom_font_family = "SimHei" # Default fallback
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                custom_font_family = families[0]
        
        # 检查是否为根节点 ("root_computer", "root_favorites", "root_history")
        item_type = index.data(Qt.UserRole)
        is_root_node = item_type in ["root_computer", "root_favorites", "root_history"]

        doc = QTextDocument()
        text_option = QTextOption()
        text_option.setWrapMode(QTextOption.NoWrap)
        doc.setDefaultTextOption(text_option)
        
        # 如果是根节点，注入字体样式
        html_content = options.text
        if is_root_node:
            # 替换现有的 font-family 或在 style 中添加
            # 简单起见，直接包裹一层 span 设置字体
            html_content = f'<span style="font-family: \'{custom_font_family}\'; font-weight: bold;">{html_content}</span>'

        doc.setHtml(html_content)

        # 计算文本区域（在清空文本之前）
        style = options.widget.style()
        text_rect = style.subElementRect(
            QStyle.SE_ItemViewItemText, options, options.widget
        )

        # 清空原文本，由 drawContents 绘制
        options.text = ""
        style.drawControl(QStyle.CE_ItemViewItem, options, painter)

        # 移动到文本区域起点
        painter.translate(text_rect.left(), text_rect.top())

        # 垂直居中偏移
        height = doc.size().height()
        y_offset = (text_rect.height() - height) / 2

        if y_offset > 0:
            painter.translate(0, y_offset)

        # 绘制HTML文本
        painter.setClipRect(QRectF(0, 0, text_rect.width(), text_rect.height()))
        doc.drawContents(painter)

        # 【新增】如果是“此电脑”节点，绘制切换按钮（scan_single/scan_multi 图标）
        if index.data(Qt.UserRole) == "root_computer":
            is_recursive = index.data(Qt.UserRole + 10) or False

            painter.restore()
            painter.save()

            # 判断当前是否为暗黑模式
            text_color = option.palette.color(QPalette.Text)
            is_dark = text_color.lightness() > 128
            
            # 计算位置：向右对齐
            icon_size = 27  # 放大1.5倍 (18 -> 27)
            icon_x = option.rect.right() - 35
            icon_y = text_rect.top() + (text_rect.height() - icon_size) / 2
            
            # 计算交互/悬停区域
            hover_rect = QRectF(icon_x - 5, icon_y - 5, icon_size + 10, icon_size + 10)
            is_hovered = False
            if self.hover_index == index:
                if hover_rect.contains(self.hover_pos.x(), self.hover_pos.y()):
                    is_hovered = True

            # 使用全局 get_scan_mode_icon 绘制图标
            mode = "multi" if is_recursive else "single"
            icon = get_scan_mode_icon(mode, is_dark, is_hovered)
            
            # 绘制图标
            icon_rect = QRect(int(icon_x), int(icon_y), icon_size, icon_size)
            # 设置绘制质量
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            icon.paint(painter, icon_rect, Qt.AlignCenter)

        # 【新增】如果是“收藏目录”或“历史目录”，绘制“清除”按钮
        elif index.data(Qt.UserRole) in ["root_favorites", "root_history"]:
            painter.restore()
            painter.save()

            # 判断当前是否为暗黑模式
            text_color = option.palette.color(QPalette.Text)
            is_dark = text_color.lightness() > 128
            
            # 计算位置：向右对齐
            icon_size = 27  # 保持与切换按钮一致
            icon_x = option.rect.right() - 35
            icon_y = text_rect.top() + (text_rect.height() - icon_size) / 2
            
            # 计算交互/悬停区域
            hover_rect = QRectF(icon_x - 5, icon_y - 5, icon_size + 10, icon_size + 10)
            is_hovered = False
            if self.hover_index == index:
                if hover_rect.contains(self.hover_pos.x(), self.hover_pos.y()):
                    is_hovered = True

            # 使用全局 get_clear_action_icon 绘制图标
            icon = get_clear_action_icon(is_dark, is_hovered)
            
            # 绘制图标
            icon_rect = QRect(int(icon_x), int(icon_y), icon_size, icon_size)
            # 设置绘制质量
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            icon.paint(painter, icon_rect, Qt.AlignCenter)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        # 处理鼠标移动事件以更新悬停状态
        if event.type() == QEvent.MouseMove:
            self.hover_index = index
            self.hover_pos = event.pos()
            # 触发重绘
            if option.widget:
                option.widget.update(index)
            return False # 继续传递事件，不要吞掉

        # 处理点击事件
        item_role = index.data(Qt.UserRole)
        
        if item_role == "root_computer":
            if (
                event.type() == QEvent.MouseButtonRelease
                and event.button() == Qt.LeftButton
            ):
                # 0. 检查是否点击了左侧的“此电脑”图标 (主题切换)
                options = QStyleOptionViewItem(option)
                self.initStyleOption(options, index)
                style = options.widget.style()

                # 获取标准图标区域 (decoration)
                decoration_rect = style.subElementRect(
                    QStyle.SE_ItemViewItemDecoration, options, options.widget
                )
                if decoration_rect.contains(event.pos()):
                    self.sig_toggle_theme.emit()
                    return True

                # 计算点击区域是否在图标上
                # 必须重新计算布局位置
                options = QStyleOptionViewItem(option)
                self.initStyleOption(options, index)
                style = options.widget.style()
                text_rect = style.subElementRect(
                    QStyle.SE_ItemViewItemText, options, options.widget
                )

                doc = QTextDocument()
                doc.setHtml(options.text)

                # 图标区域 (向右对齐)
                # 使用 option.rect.right() 获取右边界
                icon_x = options.rect.right() - 35
                # 扩大点击区域，使其更容易点击
                icon_rect = QRect(
                    int(icon_x) - 10, text_rect.top(), 50, text_rect.height()
                )

                if icon_rect.contains(event.pos()):
                    current_state = index.data(Qt.UserRole + 10) or False
                    new_state = not current_state
                    self.sig_scan_mode_changed.emit(new_state)
                    return True  # 消费事件，阻止默认行为（如选中）

        elif item_role in ["root_favorites", "root_history"]:
            if (
                event.type() == QEvent.MouseButtonRelease
                and event.button() == Qt.LeftButton
            ):
                # 检查是否点击了清除按钮区域
                options = QStyleOptionViewItem(option)
                self.initStyleOption(options, index)
                style = options.widget.style()
                text_rect = style.subElementRect(
                    QStyle.SE_ItemViewItemText, options, options.widget
                )
                
                # 图标区域 (向右对齐，与 paint 中一致)
                icon_x = options.rect.right() - 35
                # 扩大点击区域
                icon_rect = QRect(
                    int(icon_x) - 10, text_rect.top(), 50, text_rect.height()
                )

                if icon_rect.contains(event.pos()):
                    # 判断当前是否为暗黑模式
                    text_color = options.palette.color(QPalette.Text)
                    is_dark = text_color.lightness() > 128
                    
                    # 弹出菜单
                    menu = Win11Menu(parent=None, is_dark=is_dark)
                    
                    # 使用统一的蓝色风格清除图标
                    icon = get_clear_action_icon(is_dark, is_hovered=False)
                    t = TRANSLATIONS[self.lang]
                    clear_action = QAction(icon, t['menu_clear'], menu)
                    
                    # 触发清除信号
                    clear_action.triggered.connect(lambda: self.sig_clear_root.emit(item_role))
                    menu.addAction(clear_action)
                    
                    menu.exec_(event.globalPos())
                    return True

        return super().editorEvent(event, model, option, index)

    def helpEvent(self, event, view, option, index):
        item_role = index.data(Qt.UserRole)
        if (
            event.type() == QEvent.ToolTip
            and item_role == "root_computer"
        ):
            # 计算点击区域是否在图标上 (复用逻辑)
            options = QStyleOptionViewItem(option)
            self.initStyleOption(options, index)
            style = options.widget.style()
            text_rect = style.subElementRect(
                QStyle.SE_ItemViewItemText, options, options.widget
            )

            doc = QTextDocument()
            doc.setHtml(options.text)

            # 图标区域 (向右对齐)
            icon_x = options.rect.right() - 35
            icon_rect = QRect(int(icon_x) - 10, text_rect.top(), 50, text_rect.height())

            if icon_rect.contains(event.pos()):
                t = TRANSLATIONS[self.lang]
                is_recursive = index.data(Qt.UserRole + 10) or False
                if is_recursive:
                    QToolTip.showText(
                        event.globalPos(),
                        t['tooltip_scan_multi'],
                    )
                else:
                    QToolTip.showText(
                        event.globalPos(),
                        t['tooltip_scan_single'],
                    )
                return True

        elif item_role in ["root_favorites", "root_history"]:
            # ToolTip 处理
            if event.type() == QEvent.ToolTip:
                t = TRANSLATIONS[self.lang]
                options = QStyleOptionViewItem(option)
                self.initStyleOption(options, index)
                style = options.widget.style()
                text_rect = style.subElementRect(
                    QStyle.SE_ItemViewItemText, options, options.widget
                )
                
                # 图标区域 (向右对齐，与 paint 中一致)
                icon_x = options.rect.right() - 25
                # 扩大点击区域
                icon_rect = QRect(
                    int(icon_x) - 10, text_rect.top(), 40, text_rect.height()
                )

                if icon_rect.contains(event.pos()):
                    QToolTip.showText(event.globalPos(), t['tooltip_clear'])
                    return True

        return super().helpEvent(event, view, option, index)

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        doc = QTextDocument()
        text_option = QTextOption()
        text_option.setWrapMode(QTextOption.NoWrap)
        doc.setDefaultTextOption(text_option)
        doc.setHtml(options.text)

        return QSize(int(doc.idealWidth()), int(doc.size().height()))


# 自定义文件系统模型（用于修改列头）
class CustomFileSystemModel(QFileSystemModel):
    def __init__(self, parent=None, lang='zh'):
        super().__init__(parent)
        self.lang = lang

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if section == 0 and orientation == Qt.Horizontal and role == Qt.DisplayRole:
            t = TRANSLATIONS[self.lang]
            return t['my_computer']
        return super().headerData(section, orientation, role)


# 自定义树视图样式 (用于绘制可见的折叠箭头)
class TreeStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PE_IndicatorBranch:
            painter.save()

            # 获取颜色 (适配暗黑模式)
            color = option.palette.text().color()
            painter.setRenderHint(QPainter.Antialiasing, True)

            rect = option.rect
            cx = rect.center().x()
            cy = rect.center().y()

            # 等边三角形尺寸
            side = 10
            h = side * 0.866  # ~8.66

            path = QPainterPath()

            # 判断是否有子节点 (实心/空心)
            has_children = option.state & QStyle.State_Children
            is_open = option.state & QStyle.State_Open

            # 确定所属根节点 (此电脑 / 收藏目录 / 历史目录)
            is_favorites_or_history = False
            is_root_itself = False

            if widget:
                # 通过位置获取当前项的索引
                index = widget.indexAt(rect.center())
                if index.isValid():
                    # 检查是否是根节点本身
                    if index.data(Qt.UserRole) in ["root_favorites", "root_history"]:
                        is_root_itself = True

                    # 向上追溯到根节点
                    temp = index
                    while temp.parent().isValid():
                        temp = temp.parent()

                    # 检查根节点标识
                    root_data = temp.data(Qt.UserRole)
                    if root_data in ["root_favorites", "root_history"]:
                        is_favorites_or_history = True

            # 绘制逻辑分流
            # 如果是收藏/历史目录的子节点 (非根节点本身)
            if is_favorites_or_history and not is_root_itself:
                if has_children:
                    # 有子目录 -> 实心三角形
                    if is_open:  # 向下
                        p1 = QPointF(cx - side / 2, cy - h / 2)
                        p2 = QPointF(cx + side / 2, cy - h / 2)
                        p3 = QPointF(cx, cy + h / 2)
                        path.moveTo(p1)
                        path.lineTo(p2)
                        path.lineTo(p3)
                    else:  # 向右
                        p1 = QPointF(cx - h / 2, cy - side / 2)
                        p2 = QPointF(cx - h / 2, cy + side / 2)
                        p3 = QPointF(cx + h / 2, cy)
                        path.moveTo(p1)
                        path.lineTo(p2)
                        path.lineTo(p3)

                    path.closeSubpath()
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(color)
                    painter.drawPath(path)
                else:
                    # 无子目录时不绘制
                    pass

            else:
                # 其他区域 (此电脑) 以及 收藏/历史的根节点 -> 实心三角形
                if has_children:
                    if is_open:  # 向下
                        p1 = QPointF(cx - side / 2, cy - h / 2)
                        p2 = QPointF(cx + side / 2, cy - h / 2)
                        p3 = QPointF(cx, cy + h / 2)
                        path.moveTo(p1)
                        path.lineTo(p2)
                        path.lineTo(p3)
                    else:  # 向右
                        p1 = QPointF(cx - h / 2, cy - side / 2)
                        p2 = QPointF(cx - h / 2, cy + side / 2)
                        p3 = QPointF(cx + h / 2, cy)
                        path.moveTo(p1)
                        path.lineTo(p2)
                        path.lineTo(p3)

                    path.closeSubpath()
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(color)
                    painter.drawPath(path)
                # 无子目录时不绘制

            painter.restore()
            return

        super().drawPrimitive(element, option, painter, widget)


# 带翻页功能的高清预览窗口（最终优化版）
class PreviewWebEngineView(QWebEngineView):
    """用于图片预览的专用 WebEngineView，拦截滚轮事件以驱动 PhotoSwipe"""

    def contextMenuEvent(self, event):
        # 禁用默认右键菜单，防止干扰
        pass

    def install_proxy_filter(self):
        """安装事件过滤器到 focusProxy (渲染部件)"""
        if self.focusProxy():
            self.focusProxy().removeEventFilter(self)
            self.focusProxy().installEventFilter(self)

    def eventFilter(self, obj, event):
        """核心：拦截渲染部件的滚轮事件"""
        # if obj == self.focusProxy() and event.type() == QEvent.Wheel:
        #     # 捕获滚轮事件
        #     delta = event.angleDelta().y()
        #     pos = event.pos() # 相对于 focusProxy 的坐标，通常等同于 web_view 坐标
        #
        #     print(f"Python Wheel Captured: delta={delta}, pos={pos}")
        #
        #     if self.page():
        #         self.page().runJavaScript(f"if(window.externalZoom) window.externalZoom({delta}, {pos.x()}, {pos.y()});")
        #
        #     # 必须返回 True 以阻止 WebEngine 默认处理（缩放页面/滚动）
        #     return True

        return super().eventFilter(obj, event)

    def wheelEvent(self, event):
        """备用：如果事件冒泡到了 View 本身"""
        if not WEBENGINE_AVAILABLE:
            return super().wheelEvent(event)

        # delta = event.angleDelta().y()
        # pos = event.pos()
        #
        # print(f"Python Wheel Event: delta={delta}, pos={pos}")
        #
        # if self.page():
        #     self.page().runJavaScript(f"if(window.externalZoom) window.externalZoom({delta}, {pos.x()}, {pos.y()});")
        #
        # event.accept()
        super().wheelEvent(event)


class HighQualityImagePreviewDialog(QDialog):
    def __init__(
        self, img_path="", img_list=None, parent=None, thumb_rect_callback=None, lang='zh'
    ):
        super().__init__(parent)
        self.lang = lang
        t = TRANSLATIONS[self.lang]

        self.thumb_rect_callback = thumb_rect_callback

        # 初始化状态变量
        self.valid_img_list = []
        self.valid_img_path = ""
        self.img_list = []
        self.current_index = 0
        self.original_image = QImage()
        self.scale_factor = 1.0
        self.min_scale_factor = 0.1
        self.is_dragging = False
        self.last_mouse_pos = QPoint(0, 0)
        self.pil_image = None  # 保存原始PIL对象用于高质量缩放
        self.is_dark = True

        # 窗口基础设置
        self.setWindowTitle(t['preview_title'].format(""))
        self.setModal(True)
        # 全屏无边框，背景透明
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 核心属性
        self.parent_window = parent
        self.screen_geo = QApplication.desktop().screenGeometry()
        self.resize(self.screen_geo.width(), self.screen_geo.height())

        # 线程池
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(2)

        # 应用全屏半透明遮罩样式
        self.setStyleSheet(f"""
            QDialog {{
                background-color: rgba(0, 0, 0, 220);
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QLabel {{
                background-color: transparent;
            }}
        """)

        # 滚动区域（图片显示）- 铺满全屏
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setFocusPolicy(Qt.StrongFocus)  # 确保接收键盘事件
        # 恢复默认视口，移除 QOpenGLWidget 以避免兼容性问题
        self.scroll_area.viewport().setFocusPolicy(Qt.StrongFocus)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setAlignment(Qt.AlignCenter)  # 居中显示
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar { height: 0px; width: 0px; background: transparent; }
        """)

        # 预览标签
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setText(
            t['loading_original'] if self.valid_img_path else t['no_valid_image']
        )
        self.preview_label.setMouseTracking(True)
        # 启用右键菜单
        self.preview_label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.preview_label.customContextMenuRequested.connect(self._show_context_menu)

        # 渲染模式选择：WebEngine > QLabel
        self.use_web = WEBENGINE_AVAILABLE

        # Web模式下背景设为透明，由PhotoSwipe控制背景和动画
        if self.use_web:
            self.setStyleSheet("QDialog { background-color: transparent; }")

        self.web_view = None

        # ScrollArea 设置 (适用于非Web模式)
        self.scroll_area.setAlignment(Qt.AlignCenter)  # 确保内容小于窗口时居中

        if self.use_web:
            self.web_view = PreviewWebEngineView(self)
            self.web_view.setAttribute(Qt.WA_TranslucentBackground)
            self.web_view.page().setBackgroundColor(Qt.transparent)

            # 加载本地 HTML
        html_path = resource_path("preview.html").replace("\\", "/")
        if not os.path.exists(html_path):
            t = TRANSLATIONS[self.lang]
            QMessageBox.critical(
                self, t['error'], f"preview.html not found at: {html_path}"
            )

            # 使用 fromLocalFile 处理路径中的空格和特殊字符
            import time

            qurl = QUrl.fromLocalFile(html_path)
            qurl.setQuery(f"t={int(time.time())}")
            self.web_view.load(qurl)

            # 监听标题变化以处理关闭请求
            self.web_view.titleChanged.connect(self._on_web_title_changed)

            # 页面加载状态追踪
            self.is_web_loaded = False
            self.pending_image_data = None
            self.web_view.loadFinished.connect(self._on_web_load_finished)

            # 使用布局管理 WebEngineView，使其填满窗口
            if not self.layout():
                layout = QVBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                self.setLayout(layout)
            self.layout().addWidget(self.web_view)

            self.scroll_area.hide()  # Web模式不需要 ScrollArea
            self.preview_label.hide()

            # 安装事件过滤器以拦截按键
            self.web_view.installEventFilter(self)
            if self.web_view.focusProxy():
                self.web_view.focusProxy().installEventFilter(self)

        else:
            self.scroll_area.setWidget(self.preview_label)

        # 左右翻页按钮 - 悬浮在顶层
        self.btn_prev = self._create_round_button("<")
        self.btn_prev.setParent(self)
        self.btn_prev.clicked.connect(self.show_prev_image)

        self.btn_next = self._create_round_button(">")
        self.btn_next.setParent(self)
        self.btn_next.clicked.connect(self.show_next_image)

        # 图片计数标签
        self.count_label = QLabel(self)
        self.count_label.setAlignment(Qt.AlignCenter)
        self.count_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 100);
                color: white;
                border-radius: 10px;
                padding: 5px 15px;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        self.count_label.hide()

        # 文件名标签 (左上角)
        self.filename_label = QLabel(self)
        self.filename_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.filename_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 100);
                color: white;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 14px;
            }
        """)
        self.filename_label.hide()

        # ========== 自动播放控制 ==========
        self.is_playing = False
        self.play_timer = QTimer(self)
        self.play_timer.setInterval(1000)  # 默认1秒
        self.play_timer.timeout.connect(self.show_next_image)

        # 高质量渲染防抖定时器
        self.hq_timer = QTimer(self)
        self.hq_timer.setSingleShot(True)
        self.hq_timer.setInterval(200)  # 停止操作200ms后触发HQ渲染
        self.hq_timer.timeout.connect(self._render_high_quality)

        # 播放按钮
        self.btn_play = QPushButton("▶", self)
        self.btn_play.setFixedSize(40, 40)
        self.btn_play.setToolTip(t['play_tooltip'])
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 30);
                color: white;
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 50);
                font-size: 20px;
                padding-bottom: 3px; /* 修正符号垂直居中 */
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 60);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 90);
            }
        """)
        self.btn_play.clicked.connect(self._toggle_play)

        # 事件绑定
        self.setFocusPolicy(Qt.StrongFocus)
        self.installEventFilter(self)  # 监听 Dialog 自身事件
        self.scroll_area.installEventFilter(self)  # 监听 ScrollArea 事件
        self.scroll_area.viewport().installEventFilter(self)  # 监听 Viewport 事件
        self.preview_label.installEventFilter(
            self
        )  # 恢复Label的事件过滤器，但逻辑中允许右键穿透

        self.btn_prev.installEventFilter(self)  # 监听按钮事件
        self.btn_next.installEventFilter(self)  # 监听按钮事件
        self.btn_play.installEventFilter(self)

        # 加载初始图片
        if img_path or img_list:
            self.load_image(img_path, img_list)

    def load_image(self, img_path, img_list):
        """重置状态并加载新图片"""
        # 安全路径处理
        self.valid_img_list = [
            safe_path(p)
            for p in (img_list or [])
            if os.path.exists(safe_path(p)) and os.path.isfile(safe_path(p))
        ]
        self.valid_img_path = (
            safe_path(img_path)
            if safe_path(img_path) in self.valid_img_list
            else (self.valid_img_list[0] if self.valid_img_list else "")
        )
        self.img_list = self.valid_img_list
        self.current_index = (
            self.img_list.index(self.valid_img_path)
            if self.valid_img_path and self.img_list
            else 0
        )

        # 重置显示状态
        t = TRANSLATIONS[self.lang]
        self.original_image = QImage()
        self.scale_factor = 1.0
        self.pil_image = None
        self.preview_label.setText(
            t['loading_original'] if self.valid_img_path else t['no_valid_image']
        )
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.adjustSize()

        # 更新UI
        if self.valid_img_path:
            original_path = (
                self.valid_img_path.replace("\\\\?\\", "")
                if sys.platform == "win32"
                else self.valid_img_path
            )
            self.setWindowTitle(t['preview_title'].format(os.path.basename(original_path)))
            # 延迟加载，确保UI先渲染
            QTimer.singleShot(10, self._load_original_image)
            # 确保获得焦点以响应键盘
            self.activateWindow()
            self.setFocus()
            self.scroll_area.setFocus()
        else:
            self.setWindowTitle(t['preview_title'].format(""))

        # 隐藏浮层
        self.count_label.hide()
        self.filename_label.hide()

        # 停止播放
        if self.is_playing:
            self._toggle_play()

    def closeEvent(self, event):
        """关闭窗口时停止播放和渲染"""
        # 恢复主窗口状态栏
        if self.parent_window and hasattr(self.parent_window, "status_bar"):
            self.parent_window.status_bar.show()

        parent = self.parent()
        while parent:
            if hasattr(parent, "status_bar"):
                parent.status_bar.show()
                break
            parent = parent.parent()

        self.play_timer.stop()
        self.hq_timer.stop()
        if self.is_playing:
            self.is_playing = False
            self.btn_play.setText("▶")
            t = TRANSLATIONS[self.lang]
            self.btn_play.setToolTip(t['play_tooltip'])
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        # 隐藏主窗口状态栏以防止文字重叠
        # 1. 尝试直接通过 self.parent_window 获取
        if self.parent_window and hasattr(self.parent_window, "status_bar"):
            self.parent_window.status_bar.hide()
            print("DEBUG: Status bar hidden via parent_window")

        # 2. 尝试通过 self.parent() 获取
        parent = self.parent()
        found_status_bar = False
        while parent:
            if hasattr(parent, "status_bar"):
                parent.status_bar.hide()
                print("DEBUG: Status bar hidden via traversal")
                found_status_bar = True
                break
            parent = parent.parent()

        # 3. 强力模式：延时再次隐藏，防止被其他事件恢复
        def force_hide():
            if self.parent_window and hasattr(self.parent_window, "status_bar"):
                self.parent_window.status_bar.hide()
                print("DEBUG: Status bar hidden via force_hide (delayed)")

        QTimer.singleShot(100, force_hide)

        # 4. 打印调试信息确认父窗口类型
        print(
            f"DEBUG: Preview Dialog Parent: {self.parent_window}, Type: {type(self.parent_window)}"
        )

        if not found_status_bar and not (
            self.parent_window and hasattr(self.parent_window, "status_bar")
        ):
            print("DEBUG: Main Window Status Bar NOT FOUND")

        # 再次确保左上角冲突解决
        if self.use_web:
            self.filename_label.setVisible(False)

        self.activateWindow()
        self.setFocus()

    def resizeEvent(self, event):
        self.scroll_area.resize(self.size())
        self._update_button_positions()
        super().resizeEvent(event)

    def paintEvent(self, event):
        """绘制半透明背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(0, 0, 0, 220))  # 黑色背景，约85%不透明度
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

    def eventFilter(self, obj, event):
        """事件过滤器：处理缩放、拖拽和背景点击"""
        try:
            # 键盘事件拦截 (ScrollArea/Viewport)
            if event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self.close()
                    return True
                elif event.key() == Qt.Key_Left and len(self.img_list) > 1:
                    self.show_prev_image()
                    return True
                elif event.key() == Qt.Key_Right and len(self.img_list) > 1:
                    self.show_next_image()
                    return True
                # 其他按键交由 keyPressEvent 处理或忽略

            # 滚轮缩放 (Viewport)
            # WebEngine 模式下现在由 PreviewWebEngineView.wheelEvent 直接处理
            # 这里不需要再做任何拦截，保留代码结构但直接跳过
            if self.use_web and (
                obj == self.web_view
                or (
                    hasattr(self.web_view, "focusProxy")
                    and obj == self.web_view.focusProxy()
                )
                or obj == self
            ):
                pass

            if obj == self.scroll_area.viewport() and event.type() == QEvent.Wheel:
                if self.use_web:
                    return False  # Web模式下不拦截，让WebEngine处理

                # 获取鼠标相对于 content widget 的位置比例，用于保持缩放中心
                content_widget = self.scroll_area.widget()
                cursor_pos = event.pos()
                rx, ry = 0.5, 0.5  # 默认中心

                if content_widget:
                    content_pos = content_widget.mapFrom(
                        self.scroll_area.viewport(), cursor_pos
                    )
                    if content_widget.width() > 0 and content_widget.height() > 0:
                        rx = content_pos.x() / content_widget.width()
                        ry = content_pos.y() / content_widget.height()

                delta = event.angleDelta().y()
                # 无论是 Ctrl+滚轮 还是 直接滚轮，都执行缩放（符合看图习惯）
                if delta > 0:
                    self.scale_factor = min(self.scale_factor * 1.1, 5.0)
                else:
                    self.scale_factor = max(
                        self.scale_factor * 0.9, self.min_scale_factor
                    )

                self._update_preview()

                # 调整滚动条位置以保持鼠标下的点不变
                if content_widget:
                    new_content_x = content_widget.width() * rx
                    new_content_y = content_widget.height() * ry

                    h_bar = self.scroll_area.horizontalScrollBar()
                    v_bar = self.scroll_area.verticalScrollBar()

                    h_bar.setValue(int(new_content_x - cursor_pos.x()))
                    v_bar.setValue(int(new_content_y - cursor_pos.y()))

                return True

            # 背景点击关闭 (Viewport)
            # 只有当点击事件没有被 Label 捕获时（例如图片比窗口小，点击了外部区域）才会触发这里
            if (
                obj == self.scroll_area.viewport()
                and event.type() == QEvent.MouseButtonPress
            ):
                if event.button() == Qt.LeftButton:
                    self.close()
                    return True
                elif event.button() == Qt.RightButton:
                    return True  # 拦截背景右键，防止意外关闭

            # 图片拖拽与背景点击区分
            if obj == self.preview_label:
                if event.type() == QEvent.MouseButtonPress:
                    if event.button() == Qt.LeftButton:
                        # 判断点击位置是否在图片内容上
                        can_drag = False
                        if self.preview_label.pixmap():
                            pixmap_size = self.preview_label.pixmap().size()
                            label_size = self.preview_label.size()
                            # 计算图片在 Label 中的居中位置
                            x_offset = (label_size.width() - pixmap_size.width()) // 2
                            y_offset = (label_size.height() - pixmap_size.height()) // 2
                            img_rect = QRect(
                                x_offset,
                                y_offset,
                                pixmap_size.width(),
                                pixmap_size.height(),
                            )
                            if img_rect.contains(event.pos()):
                                can_drag = True

                        if can_drag:
                            # 点击在图片上 -> 拖拽
                            self.is_dragging = True
                            self.last_mouse_pos = event.globalPos()
                            self.setCursor(Qt.ClosedHandCursor)
                            return True
                        else:
                            # 点击在 Label 的空白区域 -> 关闭
                            self.close()
                            return True
                    elif event.button() == Qt.RightButton:
                        # 使用QTimer延迟调用菜单，防止事件阻塞或冲突导致关闭
                        QTimer.singleShot(
                            0, lambda: self._show_context_menu(QCursor.pos())
                        )
                        return True

                elif event.type() == QEvent.MouseMove:
                    if self.is_dragging:
                        delta = event.globalPos() - self.last_mouse_pos
                        self.last_mouse_pos = event.globalPos()
                        h_bar = self.scroll_area.horizontalScrollBar()
                        v_bar = self.scroll_area.verticalScrollBar()
                        h_bar.setValue(h_bar.value() - delta.x())
                        v_bar.setValue(v_bar.value() - delta.y())
                        return True
                elif event.type() == QEvent.MouseButtonRelease:
                    if self.is_dragging:
                        self.is_dragging = False
                        self.setCursor(Qt.ArrowCursor)
                        return True

        except Exception as e:
            print(f"事件过滤失败: {e}")
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        # 仅响应左键点击进行关闭操作
        if event.button() != Qt.LeftButton:
            return  # 明确忽略非左键

        # 点击背景（非按钮区域）关闭窗口
        child = self.childAt(event.pos())

        # 如果点击的是按钮，不关闭
        if child in [self.btn_prev, self.btn_next, self.btn_play]:
            super().mousePressEvent(event)
            return

        self.close()
        super().mousePressEvent(event)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        if not self.valid_img_path:
            return

        menu = Win11Menu(parent=self, is_dark=True)
        t = TRANSLATIONS[self.lang]

        # 1. 在资源管理器中打开
        open_folder_action = QAction(
            get_folder_icon(is_dark=True),
            t['menu_open_explorer'],
            self
        )
        open_folder_action.triggered.connect(self._open_in_explorer)
        menu.addAction(open_folder_action)

        menu.addSeparator()

        # 2. 旋转
        action_left = QAction(
            get_rotate_icon("left", is_dark=True), 
            t['menu_rotate_left'], 
            self
        )
        action_left.triggered.connect(lambda: self._rotate_image("left"))
        menu.addAction(action_left)

        action_right = QAction(
            get_rotate_icon("right", is_dark=True),
            t['menu_rotate_right'],
            self,
        )
        action_right.triggered.connect(lambda: self._rotate_image("right"))
        menu.addAction(action_right)

        menu.addSeparator()

        # 3. 复制/移动
        action_copy = QAction(
            get_copy_move_icon("copy", is_dark=True),
            t['menu_copy_to'],
            self
        )
        action_copy.triggered.connect(self._copy_image)
        menu.addAction(action_copy)

        action_move = QAction(
            get_copy_move_icon("move", is_dark=True),
            t['menu_move_to'],
            self
        )
        action_move.triggered.connect(self._move_image)
        menu.addAction(action_move)

        menu.addSeparator()

        # 4. 删除
        action_delete = QAction(
            get_delete_icon(is_dark=True), 
            t['menu_delete'], 
            self
        )
        action_delete.triggered.connect(self._delete_image)
        menu.addAction(action_delete)

        menu.exec_(pos)

    def _rotate_image(self, direction):
        """旋转图片并更新预览"""
        if not self.valid_img_path: return
        if self.parent_window:
            if direction == "left":
                self.parent_window.sig_rotate_left.emit(self.valid_img_path)
            else:
                self.parent_window.sig_rotate_right.emit(self.valid_img_path)
            # 重新加载图片以显示旋转效果
            QTimer.singleShot(500, self._load_original_image)

    def _copy_image(self):
        """复制图片"""
        if not self.valid_img_path: return
        if self.parent_window:
            self.parent_window.sig_copy_image.emit(self.valid_img_path)

    def _move_image(self):
        """移动图片"""
        if not self.valid_img_path: return
        if self.parent_window:
            self.parent_window.sig_move_image.emit(self.valid_img_path)
            # 移动后关闭预览
            self.close()

    def _delete_image(self):
        """删除图片"""
        if not self.valid_img_path: return
        if self.parent_window:
            self.parent_window.sig_delete_image.emit(self.valid_img_path)
            # 删除后关闭预览
            self.close()

    def _open_in_explorer(self):
        """在资源管理器中选中当前文件"""
        if not self.valid_img_path:
            return

        try:
            path = os.path.abspath(self.valid_img_path)
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", path])
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", path])
            else:
                subprocess.run(["xdg-open", os.path.dirname(path)])
        except Exception as e:
            print(f"打开资源管理器失败: {e}")

    def _toggle_play(self):
        self.is_playing = not self.is_playing
        t = TRANSLATIONS[self.lang]
        if self.is_playing:
            self.play_timer.start()
            self.btn_play.setText("⏸")
            self.btn_play.setToolTip(t['pause_tooltip'])
        else:
            self.play_timer.stop()
            self.btn_play.setText("▶")
            self.btn_play.setToolTip(t['play_tooltip'])

    def _auto_play_next(self):
        """自动播放下一张（支持循环）"""
        if self.current_index < len(self.img_list) - 1:
            self.show_next_image()
        else:
            # 循环播放：回到第一张
            self.current_index = 0
            self.valid_img_path = self.img_list[0]
            self._load_original_image()

    def _create_round_button(self, text):
        """创建圆形按钮（半透明悬浮风格）"""
        btn = QPushButton(text)
        btn.setFocusPolicy(Qt.NoFocus)  # 防止按钮抢夺焦点
        btn.setAutoDefault(False)
        btn.setDefault(False)
        btn.setFixedSize(60, 60)
        btn_style = f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 30);
                color: rgba(255, 255, 255, 180);
                border-radius: 30px;
                border: 1px solid rgba(255, 255, 255, 50);
                font-size: 28px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 60);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 100);
            }}
            QPushButton:pressed {{
                background-color: rgba(255, 255, 255, 90);
            }}
            QPushButton:disabled {{
                background-color: transparent;
                color: rgba(255, 255, 255, 30);
                border: none;
            }}
        """
        btn.setStyleSheet(btn_style)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def _load_original_image(self):
        """加载原图（使用后台线程进行加载和增强，避免界面卡顿和视觉跳变）"""
        try:
            path = self.valid_img_path if isinstance(self.valid_img_path, str) else ""
            path = safe_path(path)
            if not path or not os.path.exists(path) or not os.path.isfile(path):
                t = TRANSLATIONS[self.lang]
                self.preview_label.setText(t['invalid_image_path'])
                return

            # 保存规范化路径到当前实例
            self.valid_img_path = path

            # 显示加载状态
            t = TRANSLATIONS[self.lang]
            self.preview_label.setText(t['loading_original'])
            self.preview_label.setPixmap(QPixmap())  # 清空旧图
            self.original_image = QImage()  # 重置
            self.pil_image = None

            # 启动后台加载任务
            task = PreviewLoadTask(self.valid_img_path, self.width(), self.height())
            task.signals.result.connect(self._on_preview_loaded)
            self.thread_pool.start(task)

        except Exception as e:
            t = TRANSLATIONS[self.lang]
            error_msg = f"{t['error']}: {str(e)[:50]}"
            self.preview_label.setText(error_msg)
            print(f"预览加载失败: {error_msg}")
            traceback.print_exc()

    def _on_preview_loaded(
        self, path, q_img=None, scale_factor=1.0, pil_image=None, *args, **kwargs
    ):
        """预览图加载完成回调（增强健壮性，兼容不同参数签名）"""
        try:
            # 校验是否是当前需要显示的图片（防止快速翻页导致的错乱）
            current_path = (
                self.valid_img_path.replace("\\\\?\\", "")
                if sys.platform == "win32" and self.valid_img_path
                else self.valid_img_path
            )
            if path != current_path:
                return

            self.scale_factor = float(scale_factor)
            if pil_image is not None:
                self.pil_image = pil_image

            # Convert q_img to pixmap in a safe way
            enhanced_pixmap = QPixmap()
            if isinstance(q_img, QPixmap):
                enhanced_pixmap = q_img
            elif isinstance(q_img, QImage):
                enhanced_pixmap = QPixmap.fromImage(q_img)

            if self.use_web and self.web_view:
                js_path = path.replace("\\", "/") if path else ""
                if not js_path.startswith("file:///"):
                    js_path = "file:///" + js_path
                w = (
                    pil_image.width
                    if pil_image and hasattr(pil_image, "width")
                    else enhanced_pixmap.width()
                )
                h = (
                    pil_image.height
                    if pil_image and hasattr(pil_image, "height")
                    else enhanced_pixmap.height()
                )

                if self.is_web_loaded:
                    self._trigger_web_image(js_path, w, h)
                else:
                    self.pending_image_data = (js_path, w, h)

                self._update_buttons()
                QTimer.singleShot(0, self._update_button_positions)
                return

            # 直接显示增强后的图片
            self.preview_label.setPixmap(enhanced_pixmap)
            self.preview_label.adjustSize()

            self._update_buttons()
            QTimer.singleShot(0, self._update_button_positions)

            # 异步加载 original_image 用于后续缩放（如果需要）
            QTimer.singleShot(
                100, lambda: self._lazy_load_original_image(self.valid_img_path)
            )
        except Exception as e:
            print(f"Error in _on_preview_loaded: {e}")

    def _lazy_load_original_image(self, path):
        if self.valid_img_path == path:
            if path and os.path.exists(path):
                self.original_image = QImage(path)

    def _update_preview(self):
        """更新预览图片及按钮位置"""
        try:
            if (
                not hasattr(self, "valid_img_path")
                or not self.valid_img_path
                or (
                    isinstance(self.valid_img_path, str)
                    and not os.path.exists(self.valid_img_path)
                )
            ):
                return
            # Ensure there is a valid PIL image and a valid original image before updating
            if (
                not self.pil_image
                or not hasattr(self, "original_image")
                or self.original_image is None
                or self.original_image.isNull()
            ):
                return
            if self.pil_image:
                # D2D 纹理尺寸限制 (防止超出 GPU 纹理最大尺寸导致渲染失败/黑屏/透明)
                # Direct3D 11 Feature Level 11_0 支持 16384，为了安全我们限制在 16000
                MAX_TEXTURE_SIZE = 16000

                current_w = self.pil_image.width * self.scale_factor
                current_h = self.pil_image.height * self.scale_factor

                if current_w > MAX_TEXTURE_SIZE or current_h > MAX_TEXTURE_SIZE:
                    scale_w = MAX_TEXTURE_SIZE / self.pil_image.width
                    scale_h = MAX_TEXTURE_SIZE / self.pil_image.height
                    self.scale_factor = min(scale_w, scale_h)

                # 计算目标尺寸 (基于 pil_image，比 original_image 更准)
                target_w = int(self.pil_image.width * self.scale_factor)
                target_h = int(self.pil_image.height * self.scale_factor)

            if self.original_image.isNull():
                return

            # 缩放图片
            # 强制使用平滑缩放，确保在放大时也保持清晰（无锯齿）
            transform_flag = Qt.SmoothTransformation
            scaled_w = int(self.original_image.width() * self.scale_factor)
            scaled_h = int(self.original_image.height() * self.scale_factor)

            # 只有当尺寸变化显著时才重新缩放，避免频繁重绘（可选优化，暂略）
            scaled_image = self.original_image.scaled(
                scaled_w, scaled_h, Qt.KeepAspectRatio, transform_flag
            )

            self.preview_label.setPixmap(QPixmap.fromImage(scaled_image))
            self.preview_label.adjustSize()

            # 更新按钮状态和位置
            self._update_buttons()

            # 强制更新布局位置
            QTimer.singleShot(0, self._update_button_positions)

            # 触发HQ渲染定时器（如果有PIL对象）
            if self.pil_image:
                self.hq_timer.start()

        except Exception as e:
            print(f"更新预览失败: {e}")

    def _render_high_quality(self):
        """使用Pillow Lanczos算法进行高质量渲染（静止时触发）"""
        if not self.pil_image or self.original_image.isNull():
            return

        try:
            # 计算目标尺寸
            target_w = int(self.pil_image.width * self.scale_factor)
            target_h = int(self.pil_image.height * self.scale_factor)

            # 避免无效尺寸
            if target_w <= 0 or target_h <= 0:
                return

            # 使用 Lanczos (兰索斯) 算法，这是通常认为最好的软件重采样算法，比 Bicubic 更清晰
            # 配合锐化处理
            # 注意：对于非常大的图片，这一步可能耗时，所以只在静止时触发
            # 兼容不同Pillow版本
            # 使用公共的增强函数
            hq_img = process_enhanced_image(self.pil_image, target_w, target_h)

            # 转换为QPixmap
            img_data = hq_img.tobytes()
            q_format = (
                QImage.Format_RGBA8888
                if hq_img.mode == "RGBA"
                else QImage.Format_RGB888
            )
            q_img = QImage(
                img_data, target_w, target_h, target_w * len(hq_img.mode), q_format
            ).copy()
            hq_pixmap = QPixmap.fromImage(q_img)

            # 替换当前显示
            self.preview_label.setPixmap(hq_pixmap)
            # print("HQ渲染完成") # 调试用

        except Exception as e:
            print(f"HQ渲染失败: {e}")

    def _update_buttons(self):
        self.btn_prev.setEnabled(self.current_index > 0)
        self.btn_next.setEnabled(self.current_index < len(self.img_list) - 1)
        # 按钮始终显示（除非禁用样式变透明），位置在 _update_button_positions 更新
        self.btn_prev.setVisible(True)
        self.btn_next.setVisible(True)
        self.btn_prev.raise_()
        self.btn_next.raise_()

        # 更新计数标签
        if self.img_list:
            # 计算文件大小
            try:
                size_bytes = os.path.getsize(self.valid_img_path)
                if size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.1f}KB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024):.1f}MB"
            except:
                size_str = "Unknown"

            self.count_label.setText(
                f"{self.current_index + 1} / {len(self.img_list)}  {size_str}"
            )
            self.count_label.adjustSize()
            self.count_label.setVisible(True)
            self.count_label.raise_()

            # 更新文件名标签
            # 如果是 Web 模式，左上角已有 PhotoSwipe 的信息，隐藏 PyQt 的标签以防重叠
            if not self.use_web:
                self.filename_label.setText(os.path.basename(self.valid_img_path))
                self.filename_label.adjustSize()
                self.filename_label.setVisible(True)
                self.filename_label.raise_()
            else:
                self.filename_label.setVisible(False)
        else:
            self.count_label.setVisible(False)
            self.filename_label.setVisible(False)

    def _update_button_positions(self):
        """让按钮紧贴图片边缘"""
        if not self.isVisible():
            return

        if self.use_web:
            # Web模式：按钮固定在屏幕两侧
            btn_w = self.btn_prev.width()
            margin = 20
            center_y = (self.height() - self.btn_prev.height()) // 2

            self.btn_prev.move(margin, int(center_y))
            self.btn_next.move(self.width() - btn_w - margin, int(center_y))

        elif self.original_image.isNull():
            return

        else:
            # 确定目标控件
            target_widget = self.preview_label

            # 获取图片在窗口中的位置
            # preview_label 在 scroll_area 中，可能被滚动
            # mapToGlobal 再 mapFromGlobal 获取相对于 Dialog 的位置
            label_pos = target_widget.mapToGlobal(QPoint(0, 0))
            local_pos = self.mapFromGlobal(label_pos)

            img_rect = QRect(local_pos, target_widget.size())

            # 按钮尺寸
            btn_w = self.btn_prev.width()
            margin = 20  # 按钮与图片的间距

            # 计算左按钮位置
            # 默认在图片左侧
            prev_x = img_rect.left() - btn_w - margin
            # 限制在屏幕边缘内
            prev_x = max(20, prev_x)

            # 垂直居中
            center_y = self.height() // 2 - self.btn_prev.height() // 2

            self.btn_prev.move(int(prev_x), int(center_y))

            # 计算右按钮位置
            next_x = img_rect.right() + margin
            # 限制在屏幕边缘内
            next_x = min(self.width() - btn_w - 20, next_x)

            self.btn_next.move(int(next_x), int(center_y))

        # 更新计数标签位置 (屏幕底部居中，位于播放控件上方)
        if self.count_label.isVisible():
            count_w = self.count_label.width()
            count_h = self.count_label.height()
            count_x = (self.width() - count_w) // 2
            count_y = self.height() - count_h - 80  # 距离底部80px，留出播放控件位置
            self.count_label.move(int(count_x), int(count_y))

        # 更新播放控制栏位置 (屏幕底部居中)
        # 布局：[播放按钮]

        # 确保控件在最上层
        self.btn_play.raise_()
        self.btn_prev.raise_()
        self.btn_next.raise_()
        self.count_label.raise_()
        self.filename_label.raise_()

        total_ctrl_w = self.btn_play.width()

        start_x = (self.width() - total_ctrl_w) // 2
        ctrl_y = self.height() - 50  # 距离底部50px中心

        # 播放按钮
        self.btn_play.move(int(start_x), int(ctrl_y - self.btn_play.height() // 2))

        # 文件名标签位置 (左上角)
        if self.filename_label.isVisible():
            self.filename_label.adjustSize()
            self.filename_label.move(20, 20)

    def show_prev_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.valid_img_path = self.img_list[self.current_index]
            self._load_original_image()

    def show_next_image(self):
        if self.current_index < len(self.img_list) - 1:
            self.current_index += 1
            self.valid_img_path = self.img_list[self.current_index]
            self._load_original_image()

    def _on_web_load_finished(self, success):
        if not success:
            t = TRANSLATIONS[self.lang]
            QMessageBox.warning(self, t['load_error'], t['preview_load_fail'])

        self.is_web_loaded = True
        theme_info = THEME_COLORS.get(CURRENT_THEME_COLOR, THEME_COLORS["blue"])
        skin_color = theme_info["normal"]
        if self.web_view and self.web_view.page():
            self.web_view.page().runJavaScript(
                f"if (typeof setSkinColor === 'function') {{ setSkinColor('{skin_color}'); }}"
            )

        # Ensure event filter is installed on focus proxy (in case it was created late)
        if hasattr(self.web_view, "install_proxy_filter"):
            self.web_view.install_proxy_filter()

        if self.pending_image_data:
            self._trigger_web_image(*self.pending_image_data)
            self.pending_image_data = None

    def _trigger_web_image(self, js_path, w, h):
        if self.web_view:
            thumb_rect_json = "null"
            if self.thumb_rect_callback:
                try:
                    # Call callback with current valid image path
                    rect = self.thumb_rect_callback(self.valid_img_path)
                    if rect:
                        thumb_rect_json = (
                            f"{{x: {rect['x']}, y: {rect['y']}, w: {rect['w']}}}"
                        )
                except Exception as e:
                    print(f"Error getting thumb rect: {e}")

            # Add default zoom parameter (1.00x) to fix magnifier display
            js_code = f"if(window.openImage) openImage('{js_path}', {w}, {h}, {thumb_rect_json}, 1.0);"
            self.web_view.page().runJavaScript(js_code)

    def _on_web_title_changed(self, title):
        if title == "action:close":
            self.close()

    def keyPressEvent(self, event):
        """统一键盘事件处理"""
        try:
            if event.key() == Qt.Key_Escape:
                self.close()
            elif event.key() == Qt.Key_Left and len(self.img_list) > 1:
                self.show_prev_image()
            elif event.key() == Qt.Key_Right and len(self.img_list) > 1:
                self.show_next_image()
            elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
                if self.use_web and self.web_view:
                    self.web_view.page().runJavaScript(
                        "if(window.zoomIn) window.zoomIn();"
                    )
                else:
                    self.scale_factor = min(self.scale_factor * 1.1, 5.0)
                    self._update_preview()
            elif event.key() == Qt.Key_Minus:
                if self.use_web and self.web_view:
                    self.web_view.page().runJavaScript(
                        "if(window.zoomOut) window.zoomOut();"
                    )
                else:
                    self.scale_factor = max(
                        self.scale_factor * 0.9, self.min_scale_factor
                    )
                    self._update_preview()
            elif event.key() == Qt.Key_Space:  # 空格键切换播放/暂停
                self._toggle_play()
        except Exception as e:
            print(f"键盘事件处理失败: {e}")


# 打开系统查看器（兼容中文路径）
def open_with_system_viewer(img_path):
    try:
        # 安全路径处理
        safe_p = safe_path(img_path)
        original_p = (
            safe_p.replace("\\\\?\\", "") if sys.platform == "win32" else safe_p
        )
        if sys.platform == "win32":
            os.startfile(original_p)
        elif sys.platform == "darwin":
            subprocess.run(["open", original_p], encoding="utf-8")
        else:
            subprocess.run(["xdg-open", original_p], encoding="utf-8")
    except Exception as e:
        QDesktopServices.openUrl(QUrl.fromLocalFile(img_path))


# 瀑布流控件（固定4列）
class AdaptiveWaterfallWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.columns = []
        self.col_widgets = []
        self.col_heights = []
        self.col_width = 200
        self.last_width = 0  # 记录上一次宽度
        self.all_img_paths = []  # 存储所有图片路径，供预览翻页使用
        self.loaded_idx = 0
        self.image_cache = {}
        self.is_loading = False
        self.screen_load_count = 0
        self.current_task_id = 0
        self.pending_tasks = []
        self.is_dark_theme = (
            parent.is_dark_theme if hasattr(parent, "is_dark_theme") else False
        )
        self.preview_dialog = None  # 缓存预览窗口实例
        self.path_to_widget = {}  # Path -> Widget mapping for animation

        # 布局初始化
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.waterfall_container = QWidget()
        self.set_dark_theme(self.is_dark_theme)
        self.horizontal_layout = QHBoxLayout(self.waterfall_container)
        self.horizontal_layout.setSpacing(COLUMN_SPACING)
        self.horizontal_layout.setContentsMargins(*WIDGET_MARGINS)
        self.main_layout.addWidget(self.waterfall_container)

        # 线程池
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(MAX_THREADS)

        # 调整大小防抖动定时器
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(50)  # 50ms 延迟，实现“立即”响应的感觉
        self.resize_timer.timeout.connect(self._delayed_resize_update)

        # 初始化4列
        self._init_fixed_columns()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_dark_theme(self, is_dark):
        bg_color = "#1e1e1e" if is_dark else "#f8f9fa"
        self.setStyleSheet(f"background-color: {bg_color};")
        self.waterfall_container.setStyleSheet(f"background-color: {bg_color};")
        if self.col_widgets:
            for w in self.col_widgets:
                w.setStyleSheet("background-color: transparent;")

    def _init_fixed_columns(self, count=None):
        self._cancel_all_tasks()
        self.path_to_widget.clear()  # Clear mapping
        for w in self.col_widgets:
            w.deleteLater()
        self.columns.clear()
        self.col_widgets.clear()
        self.col_heights.clear()
        while self.horizontal_layout.count() > 0:
            item = self.horizontal_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 使用传入的列数，否则使用全局定义的列数
        current_column_count = count if count is not None else FIXED_COLUMN_COUNT
        
        for _ in range(current_column_count):
            col_widget = QWidget()
            col_layout = QVBoxLayout(col_widget)
            col_layout.setSpacing(ITEM_SPACING)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setAlignment(Qt.AlignTop)
            self.columns.append(col_layout)
            self.col_widgets.append(col_widget)
            self.col_heights.append(0)
            self.horizontal_layout.addWidget(col_widget)

    def _cancel_all_tasks(self):
        for task in self.pending_tasks:
            task.cancel()
        self.pending_tasks.clear()
        self.thread_pool.waitForDone(1000)
        self.is_loading = False

    def resizeEvent(self, event):
        """窗口宽度变化，触发防抖更新"""
        self.resize_timer.start()
        super().resizeEvent(event)

    def _delayed_resize_update(self):
        """执行实际的刷新逻辑"""
        try:
            # 使用父窗口(Viewport)的宽度作为基准，因为当窗口变小时，
            # self.width() 可能会因为内部固定大小的图片而被撑大，导致无法检测到缩小
            parent_widget = self.parent()
            current_width = parent_widget.width() if parent_widget else self.width()

            # 如果瀑布流区域宽度没有变化，则不刷新
            if current_width == self.last_width:
                return

            self.last_width = current_width

            available_width = current_width - WIDGET_MARGINS[0] - WIDGET_MARGINS[2]
            if available_width <= 0:
                return

            # 获取屏幕总宽度用于判断是否需要重置列数
            screen_width = QApplication.desktop().screenGeometry().width()
            main_window_width = self.window().width()
            
            # 响应式逻辑：当窗口宽度小于屏幕总宽度的 2/3 时，自动重置为 3 列
            if main_window_width < (screen_width * 2 / 3):
                target_column_count = 3
            else:
                # 增强的响应式断点逻辑
                if available_width < 480:
                    target_column_count = 1
                elif available_width < 768:
                    target_column_count = 2
                elif available_width < 1024:
                    target_column_count = 3
                elif available_width < 1440:
                    target_column_count = 4
                else:
                    target_column_count = 4

            total_spacing = (target_column_count - 1) * COLUMN_SPACING
            # 允许更小的列宽，避免在窗口较小时无法继续缩放
            new_col_width = max(
                50, int((available_width - total_spacing) / target_column_count)
            )

            # 只有当列数发生变化时才重新初始化列布局，否则只更新宽度
            column_count_changed = target_column_count != len(self.columns)
            self.col_width = new_col_width
            
            if column_count_changed:
                self._cancel_all_tasks()
                self.image_cache.clear()
                self._init_fixed_columns(target_column_count)
            else:
                # 列数没变，只停止当前任务并清空部分状态
                self._cancel_all_tasks()
                # 注意：这里不清空 image_cache，允许复用（虽然尺寸可能略有偏差，但能减少闪烁）
                # 清空现有控件，准备重新填充
                for col_layout in self.columns:
                    for i in reversed(range(col_layout.count())):
                        widget = col_layout.itemAt(i).widget()
                        if widget:
                            widget.deleteLater()
                self.col_heights = [0] * len(self.col_heights)
                self.path_to_widget.clear()

            self._calculate_screen_load_count()
            if self.all_img_paths:
                self.loaded_idx = 0
                self.current_task_id += 1
                # 重新加载第一屏图片
                self._load_batch(0, self.screen_load_count)
        except Exception as e:
            print(f"调整尺寸失败: {e}")

    def clear_waterfall(self):
        self._cancel_all_tasks()
        self.image_cache.clear()
        self.path_to_widget.clear()  # Clear mapping
        for col_layout in self.columns:
            for i in reversed(range(col_layout.count())):
                col_layout.itemAt(i).widget().deleteLater()
        self.col_heights = [0] * len(self.col_heights)
        self.all_img_paths = []
        self.loaded_idx = 0
        self.is_loading = False
        self.update()

    def set_all_images(self, paths):
        self.clear_waterfall()
        # 安全路径处理+过滤有效文件
        valid_paths = [
            safe_path(p)
            for p in paths
            if os.path.exists(safe_path(p)) and os.path.isfile(safe_path(p))
        ]
        self.all_img_paths = valid_paths  # 保存路径列表供预览翻页使用
        self.loaded_idx = 0
        self.current_task_id += 1
        self._calculate_screen_load_count()
        if valid_paths:
            self._load_batch(0, self.screen_load_count)

    def _calculate_screen_load_count(self):
        try:
            visible_height = self.parent().parent().viewport().height()
            avg_img_height = 150 + ITEM_SPACING
            self.screen_load_count = len(self.columns) * (
                visible_height // avg_img_height
            )
            self.screen_load_count = max(8, min(30, self.screen_load_count))
        except:
            self.screen_load_count = 10

    def _load_batch(self, start_idx, count):
        if (
            self.is_loading
            or not self.all_img_paths
            or start_idx >= len(self.all_img_paths)
        ):
            return
        self.is_loading = True
        end_idx = min(start_idx + count, len(self.all_img_paths))
        current_task_id = self.current_task_id
        self.pending_tasks.clear()
        for i in range(start_idx, end_idx):
            path = self.all_img_paths[i]
            if path in self.image_cache:
                pixmap, w, h = self.image_cache[path]
                self._add_image_to_column(path, pixmap, w, h)
                continue
            task = ImageLoadTask(path, self.col_width, current_task_id)

            def on_finished(p, pm, w, h, tid=current_task_id):
                if tid != self.current_task_id:
                    return
                self._on_image_loaded(p, pm, w, h)

            task.signals.finished.connect(on_finished)
            self.pending_tasks.append(task)
            self.thread_pool.start(task)
        self.loaded_idx = end_idx
        if len(self.pending_tasks) == 0:
            self.is_loading = False

    def _on_image_loaded(self, path, pixmap, w, h):
        if pixmap.isNull():
            self._check_load_complete()
            return
        self.image_cache[path] = (pixmap, w, h)
        self._add_image_to_column(path, pixmap, w, h)
        self._check_load_complete()

    def _check_load_complete(self):
        self.pending_tasks = [t for t in self.pending_tasks if not t.is_finished]
        if len(self.pending_tasks) == 0 and self.thread_pool.activeThreadCount() == 0:
            self.is_loading = False

    def _add_image_to_column(self, path, pixmap, w, h):
        if not self.columns:
            return
        min_idx = self.col_heights.index(min(self.col_heights))
        label = RoundedImageLabel(12, self)
        label.setFixedSize(w, h)
        label.setCursor(Qt.PointingHandCursor)

        # Store for animation
        self.path_to_widget[path] = label

        # 传递所有图片路径到预览窗口（防崩溃包装）
        def safe_show_preview(p):
            try:
                if USE_SYSTEM_VIEWER:
                    open_with_system_viewer(p)
                else:
                    # 使用 self.window() 获取顶层主窗口，确保居中计算基于主窗口而非子控件
                    # 每次创建新的 Dialog 实例，避免旧状态残留，或者改进 HighQualityImagePreviewDialog 支持重用
                    # 鉴于当前修改较大，建议每次新建以保证状态干净
                    self.preview_dialog = HighQualityImagePreviewDialog(
                        p,
                        self.all_img_paths,
                        self.window(),
                        thumb_rect_callback=self.get_thumb_rect,
                    )
                    self.preview_dialog.exec_()
            except Exception as e:
                t = TRANSLATIONS[getattr(self.window(), 'lang', 'zh')]
                error_msg = t['open_preview_fail'].format(str(e)[:50])
                print(error_msg)
                QMessageBox.warning(self.parent(), t['preview_fail'], error_msg)

        label.mousePressEvent = lambda e, p=path: safe_show_preview(p)
        label.setPixmap(pixmap)
        self.columns[min_idx].addWidget(label)
        self.col_heights[min_idx] += h + ITEM_SPACING
        
        # 启动渐现动画
        label.start_fade_in()

    def get_thumb_rect(self, path):
        """Get the global screen rectangle of the thumbnail for animation"""
        if path in self.path_to_widget:
            widget = self.path_to_widget[path]
            try:
                # Check if widget is visible and valid
                if widget.isVisible():
                    global_pos = widget.mapToGlobal(QPoint(0, 0))
                    return {
                        "x": global_pos.x(),
                        "y": global_pos.y(),
                        "w": widget.width(),
                        "h": widget.height(),
                    }
            except:
                pass
        return None

    def load_more_images(self):
        if self.is_loading or self.loaded_idx >= len(self.all_img_paths):
            return
        self._load_batch(self.loaded_idx, self.screen_load_count)


# 主窗口（带历史目录持久化）
class ImageViewerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(APP_COMPANY, APP_NAME)
        
        # 加载皮肤颜色
        global CURRENT_THEME_COLOR
        saved_theme = self.settings.value("theme_color", "blue", type=str)
        if saved_theme in THEME_COLORS:
            CURRENT_THEME_COLOR = saved_theme
            
        saved_lang = self.settings.value("language", "", type=str)
        self.lang = _normalize_lang_code(saved_lang) if saved_lang else _detect_system_lang_code()
        if self.lang not in TRANSLATIONS:
            self.lang = _detect_system_lang_code()
        t = TRANSLATIONS.get(self.lang, TRANSLATIONS["zh"])

        # Determine if running in headless/offscreen and thus WebEngine should be disabled
        self._headless = (
            os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"
            or os.environ.get("QT_OPENGL", "").lower() == "software"
        )
        self.setWindowTitle(t["app_title"])
        self.setWindowIcon(QIcon(resource_path("resources/icon.png")))
        fix_chinese_path()

        # 检测系统主题
        self.is_dark_theme = self._detect_dark_theme()

        # 初始化核心变量
        self.history_dirs = []
        self.is_scanning = False
        self.scan_id = 0
        self.current_worker = None
        self.current_dir = ""
        self.is_recursive_mode = False  # 默认为一级目录模式
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(MAX_THREADS)

        # 用于节流通知 Web 端宽度变化的定时器
        self._splitter_timer = QTimer()
        self._splitter_timer.setSingleShot(True)
        self._splitter_timer.timeout.connect(self._do_notify_splitter_move)
        self._last_notified_width = -1

        # 加载历史目录（程序启动时先不检查存在性，加快启动）
        self._load_history_from_settings(check_exists=False)
        self._load_favorites_from_settings(check_exists=False)

        # 延迟 500ms 后再检查目录存在性
        QTimer.singleShot(500, self._deferred_startup_checks)

        # 窗口基础设置
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        # 启用所有标准窗口按钮（最小化、最大化、关闭）
        # self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)

        # 获取屏幕尺寸并设置窗口大小
        screen = QApplication.desktop().availableGeometry()
        new_width = int(screen.width() * 0.7)
        new_height = int(screen.height() * 0.85)
        self.resize(new_width, new_height)
        # 屏幕居中
        self.move(
            screen.x() + (screen.width() - new_width) // 2,
            screen.y() + (screen.height() - new_height) // 2,
        )

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # Main vertical layout (Toolbar at top, then Splitter)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 0. 顶部工具栏
        self.toolbar = QWidget()
        self.toolbar.setFixedHeight(40)
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)
        toolbar_layout.setSpacing(10)
        
        toolbar_layout.addStretch()

        # 皮肤切换按钮
        self.skin_btn = HoverButton(get_skin_icon)
        self.skin_btn.setFixedSize(30, 30)
        self.skin_btn.setToolTip(t.get('theme_skin', '皮肤颜色'))
        self.skin_btn.setCursor(Qt.PointingHandCursor)
        self.skin_btn.clicked.connect(self._on_skin_clicked)
        toolbar_layout.addWidget(self.skin_btn)

        # 语言切换下拉框
        self.lang_combo = LanguageComboBox()
        self.lang_combo.setObjectName("langCombo")
        self.lang_combo.setFixedSize(30, 30)
        self.lang_combo.setCursor(Qt.PointingHandCursor)
        self.lang_combo.setFocusPolicy(Qt.NoFocus)
        self.lang_combo.currentIndexChanged.connect(self._on_language_combo_changed)
        toolbar_layout.addWidget(self.lang_combo)

        # 使用说明按钮
        self.help_btn = HoverButton(get_help_icon)
        self.help_btn.setFixedSize(30, 30)
        self.help_btn.setToolTip(t['use_guide'])
        self.help_btn.setCursor(Qt.PointingHandCursor)
        self.help_btn.clicked.connect(self._on_help_clicked)
        toolbar_layout.addWidget(self.help_btn)

        # 添加到主布局
        main_layout.addWidget(self.toolbar)

        # 分割窗口
        self.splitter = CustomSplitter(Qt.Horizontal, lang=self.lang)
        main_layout.addWidget(self.splitter)

        # 左侧目录面板
        self.left_widget = QWidget()
        self.left_widget.setMinimumWidth(50)  # 允许缩小到50px
        self.left_layout = QVBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(5, 5, 5, 5)
        self.left_layout.setSpacing(5)

        # 左侧垂直布局 (不再使用 Splitter)
        self.left_v_layout = QVBoxLayout()
        self.left_v_layout.setContentsMargins(0, 0, 0, 0)
        self.left_v_layout.setSpacing(0)
        self.left_layout.addLayout(self.left_v_layout)

        # 1. 统一目录树 (包含 此电脑、收藏、历史)
        self._init_file_tree()
        self._set_tree_view_style()

        # 使用自定义 Delegate 包含扫描模式切换逻辑
        self.tree_delegate = HTMLDelegate(self.tree_view, lang=self.lang)
        self.tree_delegate.sig_scan_mode_changed.connect(self._on_scan_mode_changed)
        self.tree_delegate.sig_toggle_theme.connect(self._toggle_theme)
        self.tree_delegate.sig_clear_root.connect(self._on_clear_root_requested)
        self.tree_view.setItemDelegate(self.tree_delegate)

        # 设置内边距，使内容下移 10px
        self.tree_view.setStyleSheet(
            self.tree_view.styleSheet() + "QTreeView { padding-top: 10px; }"
        )

        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.left_v_layout.addWidget(self.tree_view)

        self.splitter.addWidget(self.left_widget)

        # 右侧瀑布流区域 (WebEngine) - headless gating
        headless = (
            os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"
            or os.environ.get("QT_OPENGL", "").lower() == "software"
        )
        if WEBENGINE_AVAILABLE and not headless:
            self.web_view = CustomWebEngineView(lang=self.lang)
            self.web_view.page().setBackgroundColor(Qt.transparent)

            # 连接右键菜单信号
            self.web_view.sig_open_explorer.connect(self._open_in_explorer)
            self.web_view.sig_rotate_left.connect(
                lambda path: self._rotate_image(path, "left")
            )
            self.web_view.sig_rotate_right.connect(
                lambda path: self._rotate_image(path, "right")
            )
            self.web_view.sig_copy_image.connect(self._copy_image)
            self.web_view.sig_move_image.connect(self._move_image)
            self.web_view.sig_delete_image.connect(self._delete_image)
            self.web_view.sig_refresh.connect(self._refresh_images)
            self.web_view.sig_sort_changed.connect(self._change_sort_order)
            self.web_view.sig_layout_changed.connect(self._change_layout_mode)
            self.web_view.sig_format_changed.connect(self._change_format_filter)
            self.web_view.sig_size_changed.connect(self._change_size_filter)

            # 加载本地 HTML
            html_path = resource_path("waterfall.html").replace("\\", "/")
            qurl = QUrl.fromLocalFile(html_path)
            qurl.setQuery(f"lang={self.lang}")
            self.web_view.load(qurl)

            # 传递主题设置
            self.web_view.loadFinished.connect(self._on_web_loaded)

            self.is_web_loaded = False  # 标记 Web 是否加载完成
            self.splitter.splitterMoved.connect(self._on_splitter_moved)

            self.splitter.addWidget(self.web_view)
        else:
            self.web_view = None
        # self.splitter.setCollapsible(0, False) # 允许拖拽调整

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 扫描模式标签（最左侧）
        t = TRANSLATIONS[self.lang]
        self.scan_mode_label = ClickableLabel(t['scan_mode_single'])
        self.scan_mode_label.setToolTip(t['scan_mode_tooltip'].format(t['scan_mode_single']))
        self.scan_mode_label.setStyleSheet("padding: 0 10px;")
        self.scan_mode_label.clicked.connect(self._toggle_scan_mode)
        self.status_bar.addWidget(self.scan_mode_label)

        self.progress_label = QLabel(t['ready'])
        self.count_label = QLabel(t['image_count'].format(0, 0))
        self.status_bar.addWidget(self.progress_label)

        self.image_count = 0  # 记录当前图片总数
        self.original_img_data = [] # 原始图片数据（用于过滤）
        self.current_img_data = []  # 当前图片数据（过滤后）
        self.current_sort_mode = "name_asc"  # 当前排序模式
        self.current_layout_mode = "vertical"  # 当前布局模式
        
        t = TRANSLATIONS[self.lang]
        self.current_format_filter = t['all_formats']
        self.current_size_filter = t['all_sizes']
        self.current_search_text = ""  # 保存搜索关键字

        # 浮动搜索框
        self.floating_search = FloatingSearchBox(self, is_dark=self.is_dark_theme)
        self.floating_search.sig_search.connect(self._on_floating_search)
        self.last_ctrl_press_time = 0

        # 图片大小标签 (居中显示)
        self.size_label = QLabel("")
        self.size_label.setAlignment(Qt.AlignCenter)
        self.size_label.setStyleSheet(
            "padding: 0 10px; color: #e0e0e0;"
        )  # 确保文本可见
        # 使用 stretch 让它占据中间空间
        self.status_bar.addWidget(QWidget(), 1)  # 占位符
        self.status_bar.addWidget(self.size_label)
        self.status_bar.addWidget(QWidget(), 1)  # 占位符

        self.status_bar.addPermanentWidget(self.count_label)

        # 事件绑定
        if self.web_view:
            self.web_view.titleChanged.connect(self._on_web_title_changed)
        self.tree_view.clicked.connect(self._safe_dir_click)
        self.splitter.setSizes([300, DEFAULT_WIDTH - 300])  # 初始宽度300px
        # 设置拉伸因子：index 0 (左侧) 为 0 (固定)，index 1 (右侧) 为 1 (可拉伸)
        # 这样调整窗口大小时，只有右侧 Web 视图会改变大小，左侧保持不变
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(0, False)
        self.splitter.sig_toggle_layout.connect(self._toggle_layout_from_splitter)

        # 应用全局主题 (必须在所有UI初始化完成后调用)
        self._populate_language_combo()
        self._apply_complete_theme()
        self._retranslate_ui()

    def _get_ordered_lang_codes(self):
        preferred = ["zh", "zh_tw", "en", "ja", "fr", "de"]
        available = [c for c in TRANSLATIONS.keys() if isinstance(TRANSLATIONS.get(c), dict)]
        available = sorted(set(_normalize_lang_code(c) for c in available))
        ordered = [c for c in preferred if c in available]
        ordered.extend([c for c in available if c not in ordered])
        return ordered

    def _populate_language_combo(self):
        if not hasattr(self, "lang_combo") or self.lang_combo is None:
            return

        self.lang_combo.blockSignals(True)
        self.lang_combo.clear()
        self.lang_combo.setIconSize(QSize(24, 24))

        for code in self._get_ordered_lang_codes():
            pack = TRANSLATIONS.get(code) or {}
            name = pack.get("language_name") or code
            
            # 为每种语言生成对应的字符图标
            lang_icon = get_lang_icon(code, self.is_dark_theme)
            
            self.lang_combo.addItem(lang_icon, "", code)
            i = self.lang_combo.count() - 1
            self.lang_combo.setItemData(i, name, Qt.ToolTipRole)

        idx = self.lang_combo.findData(self.lang)
        if idx < 0:
            self.lang = _detect_system_lang_code()
            idx = self.lang_combo.findData(self.lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)

        self.lang_combo.blockSignals(False)

    def _update_language_combo_icons(self):
        if not hasattr(self, "lang_combo") or self.lang_combo is None:
            return

        for i in range(self.lang_combo.count()):
            code = self.lang_combo.itemData(i)
            lang_icon = get_lang_icon(code, self.is_dark_theme)
            self.lang_combo.setItemIcon(i, lang_icon)

    def _on_language_combo_changed(self, index):
        if not hasattr(self, "lang_combo") or self.lang_combo is None:
            return
        code = self.lang_combo.itemData(index)
        code = _normalize_lang_code(code)
        if not code:
            return
        if code == self.lang:
            return
        self.lang = code if code in TRANSLATIONS else "zh"
        self.settings.setValue("language", self.lang)
        self._retranslate_ui()
        self._apply_complete_theme()

    def _toggle_language(self):
        self.lang = _normalize_lang_code("en" if self.lang == "zh" else "zh")
        if self.lang not in TRANSLATIONS:
            self.lang = "zh"
        self.settings.setValue("language", self.lang)
        self._populate_language_combo()
        self._retranslate_ui()
        self._apply_complete_theme()

    def _retranslate_ui(self):
        """更新界面所有文本"""
        t = TRANSLATIONS[self.lang]
        self.setWindowTitle(t['app_title'])
        
        # 工具栏
        if hasattr(self, "floating_search"):
            self.floating_search.input.setPlaceholderText(t['search_placeholder'])
        
        # 扫描模式和工具提示
        mode_text = t['scan_mode_multi'] if self.is_recursive_mode else t['scan_mode_single']
        self.scan_mode_label.setText(mode_text)
        self.scan_mode_label.setToolTip(t['scan_mode_tooltip'].format(mode_text))
        
        if hasattr(self, "lang_combo"):
            self.lang_combo.setToolTip(t['lang_tooltip'])
        
        self.help_btn.setToolTip(t['use_guide'])
        self.help_btn.setIcon(get_help_icon(self.is_dark_theme))

        # 格式和尺寸筛选文本更新
        self.current_format_filter = t['all_formats']
        self.current_size_filter = t['all_sizes']
        
        # 状态栏
        if not self.is_scanning:
            self.progress_label.setText(t['ready'])
        
        # 更新目录树根节点文本
        if hasattr(self, "computer_item"):
            self.computer_item.setText(t['this_pc'])
        if hasattr(self, "favorites_item"):
            self.favorites_item.setText(t['favorites'])
        if hasattr(self, "history_item"):
            self.history_item.setText(t['history'])

        # 更新 WebEngineView 语言并重新加载以应用 HTML 翻译
        if hasattr(self, "web_view") and self.web_view:
            self.web_view.lang = self.lang
            html_path = resource_path("waterfall.html").replace("\\", "/")
            qurl = QUrl.fromLocalFile(html_path)
            qurl.setQuery(f"lang={self.lang}")
            self.web_view.load(qurl)
        
        # 更新 Splitter 语言
        if hasattr(self, "splitter") and self.splitter:
            self.splitter.lang = self.lang
            
        # 更新树代理语言
        if hasattr(self, "tree_delegate"):
            self.tree_delegate.lang = self.lang

    def _send_exif_info(self, path):
        """读取 EXIF 并发送给 Web"""
        try:
            info = {}
            # 1. 基本文件信息
            info['filename'] = os.path.basename(path)
            stat = os.stat(path)
            size_mb = stat.st_size / (1024 * 1024)
            info['filesize'] = f"{size_mb:.2f} MB"
            info['created'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_ctime))
            info['modified'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))

            # 2. 图片尺寸
            try:
                with Image.open(path) as img:
                    info['width'] = img.width
                    info['height'] = img.height
                    info['format'] = img.format
                    
                    # 3. EXIF 数据
                    exif_data = img._getexif()
                    if exif_data:
                        for tag, value in exif_data.items():
                            tag_name = ExifTags.TAGS.get(tag, tag)
                            if tag_name == 'Make':
                                info['camera_make'] = str(value)
                            elif tag_name == 'Model':
                                info['camera_model'] = str(value)
                            elif tag_name == 'DateTimeOriginal':
                                info['capture_time'] = str(value)
                            elif tag_name == 'ISOSpeedRatings':
                                info['iso'] = str(value)
                            elif tag_name == 'FNumber':
                                info['aperture'] = f"f/{float(value):.1f}"
                            elif tag_name == 'ExposureTime':
                                info['exposure'] = f"{value}s"
                            elif tag_name == 'FocalLength':
                                info['focal_length'] = f"{float(value):.1f}mm"
                            elif tag_name == 'LensModel':
                                info['lens'] = str(value)
            except Exception as e:
                print(f"Error reading image details: {e}")

            # 发送给 JS
            # 需要转义 JSON 中的引号等
            json_str = json.dumps(info).replace('\\', '\\\\').replace("'", "\\'")
            self.web_view.page().runJavaScript(
                f"if (typeof showExifInfo === 'function') {{ showExifInfo('{json_str}'); }}"
            )

        except Exception as e:
            print(f"Error in _send_exif_info: {e}")

    def _on_search_filter_changed(self):
        """处理搜索和筛选变化"""
        if not self.original_img_data:
            return

        t = TRANSLATIONS[self.lang]
        search_text = self.current_search_text.strip().lower()
        format_filter = self.current_format_filter
        size_filter = self.current_size_filter

        filtered_data = []

        for img in self.original_img_data:
            path = img.get("path", "")
            if not path:
                continue
                
            filename = os.path.basename(path).lower()
            
            # 1. 搜索文件名
            if search_text and search_text not in filename:
                continue
                
            # 2. 格式筛选
            if format_filter != t['all_formats']:
                ext = os.path.splitext(filename)[1].lower().replace('.', '')
                if format_filter == "RAW":
                    if ext not in ['arw', 'cr2', 'cr3', 'nef', 'dng', 'raf', 'orf']:
                        continue
                elif format_filter.lower() != ext:
                    continue
                    
            # 3. 尺寸筛选
            if size_filter != t['all_sizes']:
                try:
                    # 优先使用缓存的 size
                    size = img.get("size")
                    if size is None:
                        size = os.path.getsize(path)
                        
                    if size_filter == t['large_img']:
                        if size <= 1024 * 1024:
                            continue
                    elif size_filter == t['medium_img']:
                        if size < 100 * 1024 or size > 1024 * 1024:
                            continue
                    elif size_filter == t['small_img']:
                        if size >= 100 * 1024:
                            continue
                except:
                    continue

            filtered_data.append(img)

        self.current_img_data = filtered_data
        
        # 应用当前排序
        self._apply_sort()
        
        self._update_web_view_images()

    def _on_floating_search(self, text):
        """处理浮动搜索框的搜索请求"""
        self.current_search_text = text
        self._on_search_filter_changed()

    def keyPressEvent(self, event):
        """全局快捷键监听"""
        # 监听 Ctrl 键双击
        if event.key() == Qt.Key_Control:
            if event.isAutoRepeat():
                return
                
            current_time = time.time() * 1000 # 毫秒
            # 增加响应时间范围至 500ms
            if current_time - self.last_ctrl_press_time < 500: 
                # 弹出搜索框
                if hasattr(self, "floating_search"):
                    # 居中显示在主窗口
                    geom = self.geometry()
                    search_w = self.floating_search.width()
                    search_h = self.floating_search.height()
                    x = geom.x() + (geom.width() - search_w) // 2
                    y = geom.y() + (geom.height() - search_h) // 2
                    self.floating_search.move(x, y)
                    self.floating_search.show()
                    self.floating_search.raise_()
                    self.floating_search.activateWindow()
                self.last_ctrl_press_time = 0 # 重置
                event.accept() # 标记已处理
                return
            else:
                self.last_ctrl_press_time = current_time
        
        super().keyPressEvent(event)

    def _on_help_clicked(self):
        """打开使用说明"""
        t = TRANSLATIONS[self.lang]
        lang_code = _normalize_lang_code(self.lang)
        doc_paths = [
            resource_path(os.path.join("docs", lang_code, "readme.md")),
            resource_path(os.path.join("docs", "zh", "readme.md")),
        ]
        help_path = next((p for p in doc_paths if os.path.exists(p)), doc_paths[0])
        if os.path.exists(help_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(help_path))
        else:
            QMessageBox.information(self, t['info'], t['help_not_found'].format(help_path))

    def _toggle_scan_mode(self):
        """切换扫描模式（一级/多级）"""
        self._on_scan_mode_changed(not self.is_recursive_mode)

    def _send_web_language_pack(self):
        if not hasattr(self, "web_view") or not self.web_view:
            return
        pack = TRANSLATIONS.get(self.lang) or TRANSLATIONS.get("zh") or {}
        keys = [
            "waterfall_locate",
            "waterfall_info",
            "waterfall_loading",
            "waterfall_error_parsing",
            "waterfall_dimensions",
            "waterfall_filename",
            "waterfall_filesize",
            "waterfall_width",
            "waterfall_height",
            "waterfall_created",
            "waterfall_modified",
            "waterfall_camera_make",
            "waterfall_camera_model",
            "waterfall_lens",
            "waterfall_focal_length",
            "waterfall_aperture",
            "waterfall_exposure",
            "waterfall_iso",
            "waterfall_capture_time",
        ]
        payload = {k: pack.get(k) for k in keys if k in pack}
        lang_json = json.dumps(self.lang)
        payload_json = json.dumps(payload, ensure_ascii=False)
        self.web_view.page().runJavaScript(
            f"if (typeof setLanguagePack === 'function') {{ setLanguagePack({lang_json}, {payload_json}); }}"
        )

    def _on_web_loaded(self, ok):
        if ok:
            self.is_web_loaded = True
            # 初始化主题和皮肤颜色
            theme_info = THEME_COLORS.get(CURRENT_THEME_COLOR, THEME_COLORS["blue"])
            skin_color = theme_info["normal"]
            
            self.web_view.page().runJavaScript(
                f"if (typeof setTheme === 'function') {{ setTheme({str(self.is_dark_theme).lower()}); }}"
            )
            self.web_view.page().runJavaScript(
                f"if (typeof setSkinColor === 'function') {{ setSkinColor('{skin_color}'); }}"
            )
            self._send_web_language_pack()
            # 初始化宽度，确保响应式布局正确
            if hasattr(self, "web_view") and self.web_view:
                self.web_view.page().runJavaScript(
                    f"if (typeof setAppWindowWidth === 'function') {{ setAppWindowWidth({self.web_view.width()}); }}"
                )

    def _on_web_title_changed(self, title):
        """处理 Web 标题变化（用于接收 JS 消息）"""
        try:
            # 优先处理关闭信号（如果有）
            if title == "action:close":
                self.close()
                return

            if not title:
                return

            # 处理 EXIF 请求 (exif:path|timestamp)
            if title.startswith("exif:"):
                try:
                    content = title[5:]
                    # 去除可能的时间戳后缀
                    if "|" in content:
                        content = content.split("|")[0]
                    
                    path = content
                    # 路径处理
                    if path.startswith("file:///"):
                        path = path[8:]
                    if sys.platform == "win32":
                        path = path.replace("/", "\\")
                    from urllib.parse import unquote
                    path = unquote(path)
                    
                    full_path = safe_path(path)
                    if os.path.exists(full_path):
                        self._send_exif_info(full_path)
                except Exception as e:
                    print(f"Error handling EXIF request: {e}")
                return

            if not title.startswith("clicked:"):
                return

            # 提取路径 (clicked:path|index|timestamp)
            try:
                content = title[8:]
                parts = content.split("|")
                path = parts[0]
            except:
                return

            # 尝试提取索引并更新计数
            if len(parts) >= 3:
                try:
                    current_idx = int(parts[1])
                    if self.image_count > 0:
                        # 确保索引显示安全
                        display_idx = max(0, min(current_idx + 1, self.image_count))
                        t = TRANSLATIONS[self.lang]
                        self.count_label.setText(
                            t['image_count'].format(display_idx, self.image_count)
                        )
                except Exception:
                    pass

            # 清理路径 (可能包含 URL 编码或前缀)
            if path.startswith("file:///"):
                path = path[8:]

            # Windows 路径处理
            if sys.platform == "win32":
                path = path.replace("/", "\\")

            # 获取文件大小
            try:
                target_path = path
                # 1. 直接检查
                if not os.path.exists(target_path):
                    # 2. URL 解码后检查
                    from urllib.parse import unquote

                    target_path = unquote(path)

                # 3. 安全路径处理 (长路径)
                if not os.path.exists(target_path):
                    target_path = safe_path(target_path)

                # 最终检查
                if os.path.exists(target_path) and os.path.isfile(target_path):
                    size_bytes = os.path.getsize(target_path)
                    size_mb = size_bytes / (1024 * 1024)
                    self.size_label.setText(f"{size_mb:.2f} MB")
                else:
                    self.size_label.setText("")
            except Exception:
                self.size_label.setText("")

        except BaseException as e:
            # 捕获所有异常，防止崩溃
            try:
                print(f"CRITICAL: Error in _on_web_title_changed: {e}")
                traceback.print_exc()
            except:
                pass

    def resizeEvent(self, event):
        """主窗口大小变化"""
        # 实时通知 Web 窗口宽度，用于响应式布局计算
        if hasattr(self, "web_view") and self.web_view:
            # 使用节流定时器通知宽度变化
            self._splitter_timer.start(60)

        # 暂停 Web 更新以防止 GPU 崩溃
        if hasattr(self, "web_view") and self.web_view.isVisible():
            self.web_view.setUpdatesEnabled(False)

            # 使用 Timer 延时恢复更新
            if not hasattr(self, "_resize_timer"):
                self._resize_timer = QTimer()
                self._resize_timer.setSingleShot(True)
                self._resize_timer.timeout.connect(self._resume_web_updates)

            self._resize_timer.start(150)  # 稍微延长恢复时间，确保调整结束后再渲染

        super().resizeEvent(event)

    def _resume_web_updates(self):
        """恢复 Web 更新"""
        if hasattr(self, "web_view"):
            self.web_view.setUpdatesEnabled(True)
            # 强制重绘一次
            self.web_view.update()

    def _on_splitter_moved(self, pos, index):
        """左侧分割线拖动"""
        if hasattr(self, "web_view") and self.web_view:
            # 拖动期间暂停 Webview 更新，防止 GPU 纹理交换导致的卡顿
            if self.web_view.isVisible():
                self.web_view.setUpdatesEnabled(False)
            
            # 使用定时器节流通知 JS，频率略微降低以保证 Python 端流畅
            self._splitter_timer.start(60)
            
            # 同样使用 _resize_timer 来恢复更新
            if not hasattr(self, "_resize_timer"):
                self._resize_timer = QTimer()
                self._resize_timer.setSingleShot(True)
                self._resize_timer.timeout.connect(self._resume_web_updates)
            self._resize_timer.start(150)

    def _do_notify_splitter_move(self):
        """实际执行通知 Web 端宽度变化的操作"""
        if hasattr(self, "web_view") and self.web_view:
            curr_width = self.web_view.width()
            # 只有宽度真正发生变化时才通知
            if curr_width != self._last_notified_width:
                self.web_view.page().runJavaScript(
                    f"if (typeof setAppWindowWidth === 'function') {{ setAppWindowWidth({curr_width}); }}"
                )
                self._last_notified_width = curr_width

    def _detect_dark_theme(self):
        """检测Windows系统暗黑模式"""
        try:
            settings = QSettings(
                "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
                QSettings.NativeFormat,
            )
            return settings.value("AppsUseLightTheme", 1, type=int) == 0
        except:
            return False

    def _toggle_theme(self):
        """切换主题"""
        self.is_dark_theme = not self.is_dark_theme
        self._apply_complete_theme()

    def _tint_icon(self, icon, color):
        """给图标着色"""
        pixmap = icon.pixmap(32, 32)
        if pixmap.isNull():
            return icon
        img = pixmap.toImage()
        if img.format() != QImage.Format_ARGB32:
            img = img.convertToFormat(QImage.Format_ARGB32)
        painter = QPainter(img)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(img.rect(), color)
        painter.end()
        return QIcon(QPixmap.fromImage(img))

    def _apply_complete_theme(self):
        """应用全局暗黑/亮色主题"""
        # 更新状态栏样式
        self._set_status_bar_style()
        # 更新目录树样式
        self._set_tree_view_style()
        # 更新工具栏样式
        self._set_toolbar_style()

        # 更新浮动搜索框样式
        if hasattr(self, "floating_search"):
            self.floating_search.is_dark = self.is_dark_theme
            self.floating_search.apply_style()
            # 更新图标，使用 50x50 尺寸
            self.floating_search.icon_label.setPixmap(get_search_btn_icon(self.is_dark_theme).pixmap(50, 50))

        # 图标着色配置 (暗黑模式下使用浅色图标)
        target_color = QColor("#E0E0E0") if self.is_dark_theme else None

        # 1. 更新此电脑图标
        t = TRANSLATIONS[self.lang]
        if hasattr(self, "computer_item"):
            icon = get_computer_icon(self.is_dark_theme)
            self.computer_item.setToolTip(t['theme_tooltip_dark'] if self.is_dark_theme else t['theme_tooltip_light'])
            self.computer_item.setIcon(icon)

        # 2. 更新收藏目录图标
        if hasattr(self, "favorites_item"):
            icon = get_pin_icon(self.is_dark_theme)
            self.favorites_item.setIcon(icon)

        # 3. 更新历史目录图标
        if hasattr(self, "history_item"):
            icon = get_history_icon(self.is_dark_theme)
            self.history_item.setIcon(icon)

        self._refresh_tree_icons()

        if hasattr(self, "lang_combo"):
            self._update_language_combo_icons()

        # 5. 更新帮助按钮图标
        if hasattr(self, "help_btn"):
            icon = get_help_icon(self.is_dark_theme)
            self.help_btn.setIcon(icon)

        if self.is_dark_theme:
            # 尝试启用Windows暗黑标题栏 (Windows 10 2004+ / Windows 11)
            try:
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
                hwnd = int(self.winId())
                rendering_policy = ctypes.c_int(1)  # 1 = Enable
                set_window_attribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(rendering_policy),
                    ctypes.sizeof(rendering_policy),
                )
            except Exception as e:
                print(f"设置暗黑标题栏失败: {e}")

            # 设置全局 ToolTip 样式 (必须在 App 级别设置)
            QApplication.instance().setStyleSheet("""
                QToolTip {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    border: 1px solid #3d3d3d;
                }
            """)

            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1e1e1e;
                    color: #e0e0e0;
                }
                QSplitter::handle {
                    background-color: #3d3d3d;
                    width: 4px; /* 增加宽度便于拖动 */
                }
                QSplitter::handle:hover {
                    background-color: #505050;
                }
                QScrollBar:vertical {
                    border: none;
                    background: #1e1e1e;
                    width: 10px;
                    margin: 0px 0px 0px 0px;
                }
                QScrollBar::handle:vertical {
                    background: #424242;
                    min-height: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #686868;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    background: none;
                    border: none;
                }
                QScrollBar:horizontal {
                    border: none;
                    background: #1e1e1e;
                    height: 10px;
                    margin: 0px 0px 0px 0px;
                }
                QScrollBar::handle:horizontal {
                    background: #424242;
                    min-width: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:horizontal:hover {
                    background: #686868;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    background: none;
                    border: none;
                }
            """)
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(30, 30, 30))
            palette.setColor(QPalette.WindowText, QColor(224, 224, 224))
            palette.setColor(QPalette.Base, QColor(45, 45, 45))
            palette.setColor(QPalette.AlternateBase, QColor(50, 50, 50))
            palette.setColor(QPalette.Text, QColor(224, 224, 224))
            palette.setColor(QPalette.Button, QColor(45, 45, 45))
            palette.setColor(QPalette.ButtonText, QColor(224, 224, 224))
            palette.setColor(QPalette.ToolTipBase, QColor(45, 45, 45))
            palette.setColor(QPalette.ToolTipText, QColor(224, 224, 224))
            QApplication.setPalette(palette)
        else:
            # 恢复默认样式表
            self.setStyleSheet("")
            QApplication.setPalette(QApplication.style().standardPalette())

            # 尝试禁用Windows暗黑标题栏
            try:
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
                hwnd = int(self.winId())
                rendering_policy = ctypes.c_int(0)  # 0 = Disable
                set_window_attribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(rendering_policy),
                    ctypes.sizeof(rendering_policy),
                )
            except:
                pass

            # 设置全局 ToolTip 样式
            QApplication.instance().setStyleSheet("""
                QToolTip {
                    background-color: #ffffff;
                    color: #212529;
                    border: 1px solid #ced4da;
                }
            """)

            self.setStyleSheet("""
                QMainWindow {
                    background-color: #f8f9fa;
                    color: #495057;
                }
                QSplitter::handle {
                    background-color: #e9ecef;
                    width: 4px; /* 增加宽度便于拖动 */
                }
                QSplitter::handle:hover {
                    background-color: #ced4da;
                }
            """)

        # 通知 Web 页面
        web_view = getattr(self, "web_view", None)
        if web_view and getattr(self, "is_web_loaded", False) and web_view.page():
            web_view.page().runJavaScript(
                f"if (typeof setTheme === 'function') {{ setTheme({str(self.is_dark_theme).lower()}); }}"
            )

    def _deferred_startup_checks(self):
        """延迟执行的启动检查（检查收藏和历史目录是否存在）"""
        # 1. 重新检查历史目录
        self._load_history_from_settings(check_exists=True)
        self._update_history_tree_ui(check_subdirs=True)

        # 2. 重新检查收藏目录
        self._load_favorites_from_settings(check_exists=True)
        self._update_favorites_tree_ui(check_subdirs=True)

    def _load_history_from_settings(self, check_exists=True):
        """从配置加载历史目录"""
        try:
            # 读取存储的历史目录列表
            history_data = self.settings.value("history_dirs", [], type=list)
            
            if not check_exists:
                # 初始加载不检查存在性，直接安全路径处理
                self.history_dirs = [safe_path(path) for path in history_data]
                return

            # 过滤无效目录+安全路径处理
            self.history_dirs = [
                safe_path(path)
                for path in history_data
                if os.path.exists(safe_path(path)) and os.path.isdir(safe_path(path))
            ]
        except Exception as e:
            self.history_dirs = []

    def _load_favorites_from_settings(self, check_exists=True):
        """从配置加载收藏目录"""
        try:
            favorites_data = self.settings.value("favorites_dirs", [], type=list)
            
            if not check_exists:
                # 初始加载不检查存在性
                self.favorites_dirs = [safe_path(path) for path in favorites_data]
                return

            self.favorites_dirs = [
                safe_path(path)
                for path in favorites_data
                if os.path.exists(safe_path(path)) and os.path.isdir(safe_path(path))
            ]
        except Exception as e:
            print(f"加载收藏配置失败: {e}")
            self.favorites_dirs = []

    def _update_favorites_list_ui(self):
        """已废弃：使用 _update_favorites_tree_ui 替代"""
        pass

    def _add_to_favorites(self, dir_path):
        """添加目录到收藏"""
        safe_dir = safe_path(dir_path)
        if safe_dir not in self.favorites_dirs:
            self.favorites_dirs.append(safe_dir)
            self.settings.setValue("favorites_dirs", self.favorites_dirs)
            self._update_favorites_tree_ui()

    def _remove_from_favorites(self, dir_path):
        """从收藏中移除"""
        if dir_path in self.favorites_dirs:
            self.favorites_dirs.remove(dir_path)
            self.settings.setValue("favorites_dirs", self.favorites_dirs)
            self._update_favorites_tree_ui()

    def _remove_from_history(self, dir_path):
        """从历史中移除"""
        if dir_path in self.history_dirs:
            self.history_dirs.remove(dir_path)
            self.settings.setValue("history_dirs", self.history_dirs)
            self._update_history_tree_ui()

    def _show_tree_context_menu(self, position):
        """目录树右键菜单"""
        index = self.tree_view.indexAt(position)
        if not index.isValid():
            return

        dir_path = index.data(Qt.UserRole)
        # 忽略根节点本身
        if not dir_path or dir_path in [
            "root_computer",
            "root_network",
            "root_favorites",
            "root_history",
        ]:
            return

        safe_dir = safe_path(dir_path)

        # 判断当前是否为暗黑模式
        text_color = self.palette().color(QPalette.Text)
        is_dark = text_color.lightness() > 128

        # 判断点击的是否是收藏目录下的项目
        parent_index = index.parent()
        is_favorite_item = False
        is_history_item = False
        if parent_index.isValid():
            parent_data = parent_index.data(Qt.UserRole)
            if parent_data == "root_favorites":
                is_favorite_item = True
            elif parent_data == "root_history":
                is_history_item = True

        menu = Win11Menu(parent=self, is_dark=is_dark)

        t = TRANSLATIONS[self.lang]
        if is_favorite_item:
            # 收藏目录项：移除
            remove_action = QAction(
                get_delete_icon(is_dark),
                t['menu_remove_favorite'],
                self,
            )
            remove_action.triggered.connect(
                lambda: self._remove_from_favorites(safe_dir)
            )
            menu.addAction(remove_action)
        elif is_history_item:
            # 历史目录项：移除
            remove_action = QAction(
                get_delete_icon(is_dark),
                t['menu_remove_history'],
                self,
            )
            remove_action.triggered.connect(lambda: self._remove_from_history(safe_dir))
            menu.addAction(remove_action)
        else:
            # 普通目录项：添加到收藏
            if os.path.isdir(safe_dir):
                add_action = QAction(
                    get_add_icon(is_dark),
                    t['menu_add_favorite'],
                    self,
                )
                add_action.triggered.connect(lambda: self._add_to_favorites(safe_dir))
                menu.addAction(add_action)

        if not menu.isEmpty():
            menu.exec_(self.tree_view.viewport().mapToGlobal(position))

    def _add_to_history(self, dir_path):
        """添加目录到历史（去重+限制数量）"""
        safe_dir = safe_path(dir_path)

        # 排除根目录和盘符
        clean_path = (
            safe_dir.replace("\\\\?\\", "") if sys.platform == "win32" else safe_dir
        )
        if os.path.dirname(clean_path) == clean_path:
            return

        # 去重
        if safe_dir in self.history_dirs:
            self.history_dirs.remove(safe_dir)
        self.history_dirs.insert(0, safe_dir)
        # 限制最大数量
        if len(self.history_dirs) > MAX_HISTORY_DIRS:
            self.history_dirs = self.history_dirs[:MAX_HISTORY_DIRS]
        # 保存到配置
        self.settings.setValue("history_dirs", self.history_dirs)
        self._update_history_tree_ui()

    def _clear_history(self):
        """清空历史目录"""
        self.history_dirs = []
        self.settings.setValue("history_dirs", [])
        self._update_history_tree_ui()

    def _clear_favorites(self):
        """清空收藏目录"""
        self.favorites_dirs = []
        self.settings.setValue("favorites_dirs", [])
        self._update_favorites_tree_ui()

    def _on_clear_root_requested(self, root_type):
        """处理清除根节点内容的请求"""
        if root_type == "root_favorites":
            t = TRANSLATIONS[self.lang]
            reply = QMessageBox.question(
                self,
                t['confirm_clear'],
                t['clear_favorites_msg'],
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._clear_favorites()
        elif root_type == "root_history":
            t = TRANSLATIONS[self.lang]
            reply = QMessageBox.question(
                self,
                t['confirm_clear'],
                t['clear_history_msg'],
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._clear_history()

    def _init_file_tree(self):
        """初始化自定义文件树模型"""
        self.file_model = QStandardItemModel()
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_model)
        self.tree_view.setHeaderHidden(True)
        
        t = TRANSLATIONS[self.lang]

        # 应用自定义样式以修正折叠箭头颜色
        self.tree_view.setStyle(TreeStyle(self.tree_view.style()))

        # 根节点：此电脑 (放在最上面)
        computer_icon = get_computer_icon(self.is_dark_theme)
        self.computer_item = QStandardItem(computer_icon, t['this_pc'])
        self.computer_item.setData("root_computer", Qt.UserRole)
        self.computer_item.setEditable(False)
        # 加载自定义字体并设置粗体 思源黑体
        font_id = QFontDatabase.addApplicationFont(
            os.path.join("resources", "SourceHanSans-Bold.ttc")
        )
        if font_id >= 0:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                font = QFont(font_families[0])
            else:
                font = QFont("Source Han Sans")
        else:
            font = QFont("Source Han Sans")
        font.setBold(True)
        self.computer_item.setFont(font)
        # 初始化提示词 (根据当前主题)
        self.computer_item.setToolTip(t['theme_tooltip_dark'] if self.is_dark_theme else t['theme_tooltip_light'])
        self.file_model.appendRow(self.computer_item)

        # 加载驱动器
        self._load_drives()

        # 根节点：收藏目录 (采用 此电脑 结构)
        pin_icon = get_pin_icon(self.is_dark_theme)

        self.favorites_item = QStandardItem(pin_icon, t['favorites'])
        self.favorites_item.setData("root_favorites", Qt.UserRole)
        self.favorites_item.setEditable(False)
        # 使用相同的字体设置
        favorites_font = QFont(font)  # 复制已设置的字体
        self.favorites_item.setFont(favorites_font)  # 粗体 思源黑体
        self.file_model.appendRow(self.favorites_item)
        self._update_favorites_tree_ui(check_subdirs=False)

        # 根节点：历史目录 (采用 收藏目录 样式，时针图标)
        history_icon = get_history_icon(self.is_dark_theme)

        self.history_item = QStandardItem(history_icon, t['history'])
        self.history_item.setData("root_history", Qt.UserRole)
        self.history_item.setEditable(False)
        # 使用相同的字体设置
        history_font = QFont(font)  # 复制已设置的字体
        self.history_item.setFont(history_font)  # 粗体 思源黑体
        self.file_model.appendRow(self.history_item)
        self._update_history_tree_ui(check_subdirs=False)

        # 展开此电脑, 收藏, 历史
        self.tree_view.expand(self.computer_item.index())
        self.tree_view.expand(self.favorites_item.index())
        self.tree_view.expand(self.history_item.index())

        # 连接展开信号以实现懒加载
        self.tree_view.expanded.connect(self._on_tree_expanded)

    def _has_subdirectories(self, path):
        """Check if a directory has any subdirectories."""
        try:
            safe_p = safe_path(path)
            if not os.path.exists(safe_p) or not os.path.isdir(safe_p):
                return False
            # Use os.scandir for efficiency
            with os.scandir(safe_p) as it:
                for entry in it:
                    if entry.is_dir():
                        return True
        except Exception:
            pass
        return False

    def _update_favorites_tree_ui(self, check_subdirs=True):
        """更新收藏目录树节点"""
        if not hasattr(self, "favorites_item"):
            return

        # 清除现有子节点
        if self.favorites_item.rowCount() > 0:
            self.favorites_item.removeRows(0, self.favorites_item.rowCount())

        for dir_path in self.favorites_dirs:
            # 简化显示路径 (仅显示目录名)
            display_name = (
                os.path.basename(dir_path.replace("\\\\?\\", "").rstrip(os.sep))
                or dir_path
            )
            if sys.platform == "win32":
                clean_path = dir_path.replace("\\\\?\\", "")
                if len(clean_path) <= 3 and ":" in clean_path:
                    display_name = clean_path

            # 目录名后面显示图钉图标 (这里不再需要 HTML 图标，因为根节点已经有了)
            # 保持简洁
            display_text = display_name

            item = QStandardItem(display_text)
            item.setToolTip(dir_path)
            item.setData(dir_path, Qt.UserRole)
            item.setEditable(False)

            # 设置图标（文件夹）
            icon = get_folder_icon(self.is_dark_theme)
            item.setIcon(icon)

            # 检测是否有子文件夹，有则添加虚拟节点以显示实心三角形，否则不添加（显示空心三角形）
            if check_subdirs and self._has_subdirectories(dir_path):
                # 添加虚拟子节点，支持展开子目录
                t = TRANSLATIONS[self.lang]
                item.appendRow(QStandardItem(t['loading']))

            self.favorites_item.appendRow(item)

    def _update_history_tree_ui(self, check_subdirs=True):
        """更新历史目录树节点"""
        if not hasattr(self, "history_item"):
            return

        # 清除现有子节点
        if self.history_item.rowCount() > 0:
            self.history_item.removeRows(0, self.history_item.rowCount())

        for dir_path in self.history_dirs:
            # 显示时还原原始路径
            display_path = (
                dir_path.replace("\\\\?\\", "") if sys.platform == "win32" else dir_path
            )
            dir_name = os.path.basename(display_path)
            if not dir_name:
                dir_name = display_path

            item = QStandardItem(dir_name)
            item.setToolTip(display_path)
            item.setData(dir_path, Qt.UserRole)
            item.setEditable(False)

            # 设置图标（时针）- 这里用 SP_BrowserReload 暂时代替时钟，或者 SP_History (如果存在)
            # 使用 HTML 灰色显示 (调整颜色为 #999999 以匹配上传图片效果)
            item.setText(dir_name)

            # Icon 依然是文件夹
            icon = get_folder_icon(self.is_dark_theme)
            item.setIcon(icon)

            # 检测是否有子文件夹
            if check_subdirs and self._has_subdirectories(dir_path):
                # 添加虚拟子节点，支持展开子目录
                t = TRANSLATIONS[self.lang]
                item.appendRow(QStandardItem(t['loading']))

            self.history_item.appendRow(item)

    def _load_drives(self):
        """加载驱动器"""
        drives = QDir.drives()
        for drive in drives:
            drive_path = drive.absoluteFilePath()

            # 获取驱动器名称
            display_name = drive_path
            t = TRANSLATIONS[self.lang]
            try:
                storage = QStorageInfo(drive_path)
                name = storage.name()
                if not name:
                    name = t['drive_local']
                # 格式化显示名称，例如 "本地磁盘 (C:)"
                drive_letter = drive_path.strip(":/\\")
                display_name = f"{name} ({drive_letter}:)"
            except:
                pass

            item = QStandardItem(display_name)
            item.setData(drive_path, Qt.UserRole)
            item.setEditable(False)

            # 设置图标（驱动器/此电脑）
            icon = get_computer_icon(self.is_dark_theme)
            item.setIcon(icon)

            # 添加虚拟子节点以显示展开箭头
            t = TRANSLATIONS[self.lang]
            item.appendRow(QStandardItem(t['loading']))
            self.computer_item.appendRow(item)

    def _on_tree_expanded(self, index):
        """树节点展开处理（懒加载）"""
        item = self.file_model.itemFromIndex(index)
        if not item:
            return

        # 检查是否已经加载过
        if item.data(Qt.UserRole + 1) == True:
            return

        path = item.data(Qt.UserRole)
        # 忽略根节点
        if path in ["root_computer", "root_network", "root_favorites", "root_history"]:
            return

        if path and os.path.isdir(path):
            # 记录当前光标等待状态
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                # 清除虚拟子节点
                if item.rowCount() > 0:
                    item.removeRow(0)

                # 加载子目录
                self._load_subdirs(item, path)
                item.setData(True, Qt.UserRole + 1)  # 标记已加载
            finally:
                QApplication.restoreOverrideCursor()

    def _load_subdirs(self, parent_item, path):
        """加载子目录"""
        directory = QDir(path)
        # 只列出目录
        directory.setFilter(QDir.Dirs | QDir.NoDotAndDotDot | QDir.Hidden)
        entry_list = directory.entryInfoList()

        # 判断是否属于收藏目录或历史目录
        is_favorites_or_history = False
        temp = parent_item
        while temp is not None:
            data = temp.data(Qt.UserRole)
            if data in ["root_favorites", "root_history"]:
                is_favorites_or_history = True
                break
            if data == "root_computer":
                break
            temp = temp.parent()

        for file_info in entry_list:
            item = QStandardItem(file_info.fileName())
            child_path = file_info.absoluteFilePath()
            item.setData(child_path, Qt.UserRole)
            item.setEditable(False)

            # 设置图标（文件夹）
            icon = get_folder_icon(self.is_dark_theme)
            item.setIcon(icon)

            # 根据所属区域决定是否预先添加虚拟节点
            should_add_dummy = True
            if is_favorites_or_history:
                # 收藏/历史目录：只有当子目录确实包含内容时才添加虚拟节点（显示实心三角形）
                if not self._has_subdirectories(child_path):
                    should_add_dummy = False

            if should_add_dummy:
                # 预先添加虚拟节点，以便显示展开箭头
                t = TRANSLATIONS[self.lang]
                item.appendRow(QStandardItem(t['loading']))

            parent_item.appendRow(item)

    def _safe_dir_click(self, index: QModelIndex):
        """安全处理目录点击（兼容中文路径）"""
        try:
            dir_path = index.data(Qt.UserRole)
            if not dir_path or dir_path in [
                "root_computer",
                "root_network",
                "root_favorites",
                "root_history",
            ]:
                return

            safe_dir = safe_path(dir_path)

            # 判断是否为盘符根目录（如 C:/ 或 C:\），如果是则跳过扫描
            if sys.platform == "win32":
                # 处理 Windows 盘符逻辑
                # 去除 \\?\ 前缀后，如果长度<=3且包含冒号，通常是盘符根目录
                clean_path = safe_dir.replace("\\\\?\\", "")
                if len(clean_path) <= 3 and ":" in clean_path:
                    # 进一步确认是根目录
                    drive, tail = os.path.splitdrive(clean_path)
                    if not tail or tail in ["/", "\\"]:
                        t = TRANSLATIONS[self.lang]
                        self.progress_label.setText(
                            t['drive_root_msg'].format(clean_path)
                        )
                        # 展开该节点以便用户继续选择
                        self.tree_view.expand(index)
                        return

            if os.path.isdir(safe_dir):
                # Check if WebEngine is still alive
                if hasattr(self, "web_view"):
                    if not getattr(self, "is_web_loaded", False):
                        # Use a safe lambda to avoid QModelIndex issues if possible,
                        # but passing index is standard for retries if model doesn't change.
                        QTimer.singleShot(100, lambda: self._safe_dir_click(index))
                        return

                self._scan_images(safe_dir)
                self._add_to_history(safe_dir)
        except Exception as e:
            print(f"目录点击处理失败: {e}")
            traceback.print_exc()
            t = TRANSLATIONS[self.lang]
            QMessageBox.warning(self, t['error'], t['dir_click_fail'].format(str(e)[:50]))

    def _safe_history_click(self, item: QListWidgetItem):
        """安全处理历史目录点击"""
        try:
            # 从UserRole获取完整路径，而不是从text()获取
            dir_path = item.data(Qt.UserRole)
            if not dir_path:  # 兼容旧逻辑
                dir_path = item.text()

            safe_dir = safe_path(dir_path)
            if os.path.isdir(safe_dir):
                self._scan_images(safe_dir)
        except Exception as e:
            print(f"历史目录点击处理失败: {e}")
            t = TRANSLATIONS[self.lang]
            QMessageBox.warning(self, t['error'], t['dir_click_fail'].format(str(e)[:50]))

    def _open_in_explorer(self, file_path):
        """在资源管理器中打开文件并选中"""
        try:
            if file_path:
                file_path = unicodedata.normalize("NFC", file_path)

            # 去除可能存在的 URL 参数
            if "?" in file_path:
                file_path = file_path.split("?")[0]

            file_path = os.path.normpath(file_path)
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", file_path])
            else:
                # macOS/Linux fallback
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(file_path)))
        except Exception as e:
            print(f"Open explorer error: {e}")
            t = TRANSLATIONS[self.lang]
            QMessageBox.warning(self, t['error'], t['open_explorer_fail'].format(str(e)[:50]))

    def _rotate_image(self, path, direction):
        """旋转图片"""
        try:
            # 规范化 Unicode (NFC)
            if path:
                path = unicodedata.normalize("NFC", path)

            # 去除可能存在的 URL 参数
            if "?" in path:
                path = path.split("?")[0]

            path = os.path.normpath(path)

            if not os.path.exists(path):
                return

            with Image.open(path) as img:
                # 处理 EXIF 方向
                img = ImageOps.exif_transpose(img)

                # 旋转
                if direction == "left":
                    img = img.rotate(90, expand=True)
                else:
                    img = img.rotate(-90, expand=True)

                # 保存
                img.save(path)

                # 获取新尺寸
                new_w, new_h = img.size

            # 更新内部数据缓存 (current_img_data 和 original_img_data)
            full_path = safe_path(path)
            
            # 更新 current_img_data
            for item in self.current_img_data:
                if self._paths_are_equal(item["path"], full_path):
                    item["w"] = new_w
                    item["h"] = new_h
                    break
            
            # 更新 original_img_data
            if hasattr(self, "original_img_data"):
                for item in self.original_img_data:
                    if self._paths_are_equal(item["path"], full_path):
                        item["w"] = new_w
                        item["h"] = new_h
                        break

            # 刷新显示（不重新扫描，直接通知前端更新）
            path_str = path.replace("\\", "/")
            timestamp = int(time.time())

            # 使用 json.dumps 确保字符串安全
            path_json = json.dumps(path_str)

            if hasattr(self, "web_view") and self.web_view.page():
                # 注意：path_json 已经包含了引号，所以 JS 中不需要再加引号
                js_code = f"if (typeof imageRotated === 'function') {{ imageRotated({path_json}, {new_w}, {new_h}, {timestamp}); }}"
                self.web_view.page().runJavaScript(js_code)

        except Exception as e:
            print(f"Rotate error: {e}")
            t = TRANSLATIONS[self.lang]
            QMessageBox.warning(self, t['error'], t['rotate_fail'].format(e))

    def _on_scan_mode_changed(self, is_recursive):
        """处理扫描模式切换（来自 Delegate 点击）"""
        self.is_recursive_mode = is_recursive  # 同步全局状态
        
        if hasattr(self, "computer_item"):
            # 更新模型数据以触发重绘
            self.computer_item.setData(is_recursive, Qt.UserRole + 10)

            # 刷新显示
            self.tree_view.update(self.computer_item.index())

            t = TRANSLATIONS[self.lang]
            # 显示提示
            mode_text = t['scan_mode_multi'] if is_recursive else t['scan_mode_single']
            self.status_bar.showMessage(t['switch_mode_done'].format(mode_text), 2000)

            # 更新状态栏左侧标签和工具栏按钮图标
            tooltip = t['scan_mode_tooltip'].format(mode_text)
            self.scan_mode_label.setText(mode_text)
            self.scan_mode_label.setToolTip(tooltip)
            
            # 更新工具栏图标
            self._apply_complete_theme()

            # 如果当前有选中的目录，刷新
            if self.current_dir and not self.is_scanning:
                self._scan_images(self.current_dir)

    def _on_scan_mode_toggled(self, checked):
        # Deprecated: Kept for compatibility if button still exists, but logic moved to _on_scan_mode_changed
        pass

    def _scan_images(self, dir_path):
        """扫描目录下的图片（兼容中文/特殊符号路径）"""

        # Abort existing scan if any
        if self.current_worker:
            self.current_worker.abort()
            self.current_worker = None

        self.scan_id += 1
        current_scan_id = self.scan_id

        self.is_scanning = True
        self.current_dir = dir_path

        # 使用全局扫描模式
        is_recursive = self.is_recursive_mode

        display_path = (
            dir_path.replace("\\\\?\\", "") if sys.platform == "win32" else dir_path
        )
        t = TRANSLATIONS[self.lang]
        mode_str = f"({t['recursive_mode']})" if is_recursive else ""
        self.progress_label.setText(f"{t['scanning']}{display_path} {mode_str}")
        self.status_bar.repaint()

        # 使用线程池扫描
        worker = ScanWorker(dir_path, current_scan_id, recursive=is_recursive)
        self.current_worker = worker

        # 连接信号
        worker.signals.batch_ready.connect(self._on_batch_ready)
        worker.signals.finished.connect(self._on_scan_finished)

        # 启动前先清空 WebEngine 视图
        if self.is_web_loaded:
            # 初始化数据为空
            self.current_img_data = []
            self.web_view.page().runJavaScript(
                "if (typeof clearImages === 'function') { clearImages(); }"
            )

        self.thread_pool.start(worker)

    def _on_batch_ready(self, batch_data, scan_id):
        """处理分批扫描数据"""
        if scan_id != self.scan_id:
            return

        if not self.is_web_loaded:
            return

        # 过滤有效数据
        safe_data = []
        timestamp = int(time.time())
        for item in batch_data:
            if isinstance(item, dict) and "path" in item:
                # 处理路径
                raw_path = item["path"]
                if sys.platform == "win32" and raw_path.startswith("\\\\?\\"):
                    raw_path = raw_path[4:]
                clean_path = unicodedata.normalize("NFC", raw_path.replace("\\", "/"))

                # 构建前端对象
                safe_item = {
                    "path": clean_path,
                    "src": clean_path + f"?v={timestamp}",
                    "w": item["w"],
                    "h": item["h"],
                }
                safe_data.append(safe_item)

                # 同时更新内部数据（使用原始item以便排序等功能正常工作）
                self.current_img_data.append(item)

        if not safe_data:
            return

        json_str = json.dumps(safe_data)
        # 调用前端的 appendImages
        self.web_view.page().runJavaScript(
            f"if (typeof appendImages === 'function') {{ appendImages({json_str}); }}"
        )

        # 更新状态栏计数
        count = len(self.current_img_data)
        self.image_count = count
        t = TRANSLATIONS[self.lang]
        if count > 0:
            self.count_label.setText(t['image_count'].format(1, count))
        else:
            self.count_label.setText(t['image_count'].format(0, 0))

    def _on_scan_finished(self, img_data, scan_id):
        if scan_id != self.scan_id:
            return

        self.is_scanning = False
        if self.current_worker and self.current_worker.scan_id == scan_id:
            self.current_worker = None

        # 1. 保存原始数据
        self.original_img_data = img_data
        self.current_img_data = img_data

        t = TRANSLATIONS[self.lang]
        self.progress_label.setText(t['loading_count'].format(len(img_data)))

        # 2. 检查是否需要应用筛选
        search_text = self.current_search_text.strip()
        format_filter = self.current_format_filter
        size_filter = self.current_size_filter
        filters_active = (search_text or format_filter != t['all_formats'] or size_filter != t['all_sizes'])

        if filters_active:
            # 如果有筛选，直接调用筛选逻辑，它会更新视图
            self._on_search_filter_changed()
        else:
            # 只有在数据为空，或者排序模式不是默认时，才需要全量刷新
            # 如果是默认排序，流式加载已经显示了正确顺序的图片
            should_full_refresh = False

            if not img_data:
                should_full_refresh = True
            elif self.current_sort_mode != "name" and self.current_sort_mode != "name_asc":
                # 非默认排序，需要重新排序并刷新
                should_full_refresh = True

            if should_full_refresh:
                try:
                    self._apply_sort()
                    self._update_web_view_images()  # 这是一个全量刷新
                except Exception as e:
                    traceback.print_exc()
            else:
                # 更新一下计数和状态即可
                count = len(self.current_img_data)
                self.image_count = count
                t = TRANSLATIONS[self.lang]
                self.progress_label.setText(t['scan_done'].format(count))
                if count > 0:
                    self.count_label.setText(t['image_count'].format(1, count))

        # 尝试添加到历史记录
        if img_data and len(img_data) > 0:
            # 取第一张图所在的目录作为记录路径
            first_path = img_data[0]["path"]
            dir_path = os.path.dirname(first_path)
            self._add_to_history(dir_path)

    def _paths_are_equal(self, p1, p2):
        """比较两个路径是否相同（忽略大小写和格式差异）"""
        try:
            if not p1 or not p2:
                return False
            n1 = safe_path(p1)
            n2 = safe_path(p2)
            if sys.platform == "win32":
                return n1.lower() == n2.lower()
            return n1 == n2
        except:
            return False

    def _copy_image(self, path):
        """复制图片到..."""
        # 路径预处理
        if path.startswith("file:///"):
            path = path[8:]
        if sys.platform == "win32":
            path = path.replace("/", "\\")
            from urllib.parse import unquote
            path = unquote(path)

        if not path or not os.path.exists(path):
            return

        t = TRANSLATIONS[self.lang]
        # 选择目标目录
        target_dir = QFileDialog.getExistingDirectory(self, t['copy_target_title'], self.current_dir or "")
        if not target_dir:
            return

        try:
            filename = os.path.basename(path)
            dest_path = os.path.join(target_dir, filename)

            # 检查同名文件
            if os.path.exists(dest_path):
                reply = QMessageBox.question(self, t['overwrite_title'], t['overwrite_msg'].format(filename),
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return

            shutil.copy2(path, dest_path)
            QMessageBox.information(self, t['success'], t['copy_success'])
        except Exception as e:
            QMessageBox.critical(self, t['error'], t['copy_fail'].format(e))

    def _move_image(self, path):
        """移动图片到..."""
        # 路径预处理
        if path.startswith("file:///"):
            path = path[8:]
        if sys.platform == "win32":
            path = path.replace("/", "\\")
            from urllib.parse import unquote
            path = unquote(path)

        if not path or not os.path.exists(path):
            return

        t = TRANSLATIONS[self.lang]
        # 选择目标目录
        target_dir = QFileDialog.getExistingDirectory(self, t['move_target_title'], self.current_dir or "")
        if not target_dir:
            return

        try:
            filename = os.path.basename(path)
            dest_path = os.path.join(target_dir, filename)

            # 检查同名文件
            if os.path.exists(dest_path):
                reply = QMessageBox.question(self, t['overwrite_title'], t['overwrite_msg'].format(filename),
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return

            shutil.move(path, dest_path)

            # 更新显示
            full_path = safe_path(path)
            self.current_img_data = [
                img for img in self.current_img_data
                if not self._paths_are_equal(img["path"], full_path)
            ]
            
            # 同时更新原始数据
            if hasattr(self, "original_img_data"):
                self.original_img_data = [
                    img for img in self.original_img_data
                    if not self._paths_are_equal(img["path"], full_path)
                ]
                
            self._update_web_view_images()

            QMessageBox.information(self, t['success'], t['move_success'])
        except Exception as e:
            QMessageBox.critical(self, t['error'], t['move_fail'].format(e))

    def _delete_image(self, path):
        """删除图片"""
        if not path:
            return

        # 转换路径
        if path.startswith("file:///"):
            path = path[8:]
        if sys.platform == "win32":
            path = path.replace("/", "\\")
            # 处理可能的 URL 编码问题
            from urllib.parse import unquote

            path = unquote(path)

        # 长路径处理
        full_path = safe_path(path)
        t = TRANSLATIONS[self.lang]

        # 确认对话框
        reply = QMessageBox.question(
            self,
            t['delete_confirm_title'],
            t['delete_confirm_msg'].format(os.path.basename(path)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                if os.path.exists(full_path):
                    send2trash.send2trash(full_path)

                    # 从当前数据中移除
                    # 使用宽松匹配
                    original_count = len(self.current_img_data)
                    self.current_img_data = [
                        img
                        for img in self.current_img_data
                        if not self._paths_are_equal(img["path"], full_path)
                    ]
                    
                    # 同时从原始数据中移除
                    if hasattr(self, "original_img_data"):
                        self.original_img_data = [
                            img
                            for img in self.original_img_data
                            if not self._paths_are_equal(img["path"], full_path)
                        ]
                    
                    new_count = len(self.current_img_data)

                    # 刷新显示
                    self._update_web_view_images()
                else:
                    QMessageBox.warning(self, t['error'], t['file_not_exist'])
                    # 即使文件不存在，也尝试从列表中移除
                    self.current_img_data = [
                        img
                        for img in self.current_img_data
                        if not self._paths_are_equal(img["path"], full_path)
                    ]
                    #同时从原始数据中移除
                    if hasattr(self, "original_img_data"):
                        self.original_img_data = [
                            img
                            for img in self.original_img_data
                            if not self._paths_are_equal(img["path"], full_path)
                        ]
                    self._update_web_view_images()

            except Exception as e:
                QMessageBox.critical(self, t['error'], t['delete_fail'].format(e))

    def _refresh_images(self):
        """刷新当前目录"""
        if self.current_dir:
            # 强制清空当前数据，确保重新加载
            self.current_img_data = []
            self._scan_images(self.current_dir)

    def _change_sort_order(self, mode):
        """更改排序方式"""
        self.current_sort_mode = mode
        self._apply_sort()
        self._update_web_view_images()

    def _change_layout_mode(self, mode):
        """更改视图布局"""
        self.current_layout_mode = mode  # 更新状态
        if hasattr(self, "splitter"):
            self.splitter.set_layout_mode(mode)

        if self.is_web_loaded:
            self.web_view.page().runJavaScript(
                f"if (typeof setLayoutMode === 'function') {{ setLayoutMode('{mode}'); }}"
            )

    def _change_format_filter(self, format_name):
        """切换格式筛选"""
        self.current_format_filter = format_name
        self._on_search_filter_changed()

    def _change_size_filter(self, size_name):
        """切换尺寸筛选"""
        self.current_size_filter = size_name
        self._on_search_filter_changed()

    def _toggle_layout_from_splitter(self):
        """从分割条切换布局"""
        new_mode = (
            "horizontal" if self.current_layout_mode == "vertical" else "vertical"
        )
        self._change_layout_mode(new_mode)

    def _apply_sort(self):
        """应用排序"""
        if not self.current_img_data:
            return

        try:
            if self.current_sort_mode == "name" or self.current_sort_mode == "name_asc":
                self.current_img_data.sort(key=lambda x: x["path"].lower())
            elif self.current_sort_mode == "name_desc":
                self.current_img_data.sort(
                    key=lambda x: x["path"].lower(), reverse=True
                )
            elif self.current_sort_mode == "date_asc":
                self.current_img_data.sort(key=lambda x: x.get("mtime", 0))
            elif self.current_sort_mode == "date_desc":
                self.current_img_data.sort(
                    key=lambda x: x.get("mtime", 0), reverse=True
                )
            elif self.current_sort_mode == "size_desc":
                self.current_img_data.sort(key=lambda x: x.get("size", 0), reverse=True)
            elif self.current_sort_mode == "size_asc":
                self.current_img_data.sort(key=lambda x: x.get("size", 0))
        except Exception:
            pass

    def _update_web_view_images(self):
        """更新 Web 视图图片列表"""
        try:
            timestamp = int(time.time())
            safe_data = []
            for item in self.current_img_data:
                # 移除 Windows 长路径前缀 \\?\ 以便前端匹配
                raw_path = item["path"]
                if sys.platform == "win32" and raw_path.startswith("\\\\?\\"):
                    raw_path = raw_path[4:]

                # 规范化路径 (NFC) 并替换反斜杠
                clean_path = unicodedata.normalize("NFC", raw_path.replace("\\", "/"))
                safe_data.append(
                    {
                        "path": clean_path,  # 原始路径（用于ID）
                        "src": clean_path + f"?v={timestamp}",  # 显示路径（带时间戳）
                        "w": item["w"],
                        "h": item["h"],
                    }
                )

            json_str = json.dumps(safe_data)

            # 调用 JS 更新图片
            if hasattr(self, "web_view") and self.web_view.page():
                self.web_view.page().runJavaScript(
                    f"if (typeof updateImages === 'function') {{ updateImages({json_str}); }}"
                )
            else:
                pass

            count = len(self.current_img_data)
            self.image_count = count
            t = TRANSLATIONS[self.lang]
            self.progress_label.setText(t['scan_done'].format(count))
            if count > 0:
                self.count_label.setText(t['image_count'].format(1, count))
            else:
                self.count_label.setText(t['image_count'].format(0, 0))
        except Exception as e:
            traceback.print_exc()

    # _on_scan_finished moved up for streaming support

    def _on_scroll(self, value):
        pass

    # 样式设置方法（补充完整）
    def _set_tree_view_style(self):
        """设置目录树样式"""
        scrollbar_dark = """
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #4a4a4a;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5a5a5a;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                background-color: #2d2d2d;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background-color: #4a4a4a;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #5a5a5a;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """
        scrollbar_light = """
            QScrollBar:vertical {
                background-color: #f8f9fa;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #ced4da;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #adb5bd;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                background-color: #f8f9fa;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background-color: #ced4da;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #adb5bd;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """

        if self.is_dark_theme:
            self.tree_view.setStyleSheet(
                """
                QTreeView {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    border: none;
                }
                QTreeView::item:selected {
                    background-color: #4a4a4a;
                    color: #ffffff;
                }
                QTreeView::item:hover {
                    background-color: #3d3d3d;
                }
                QHeaderView::section {
                    background-color: #1e1e1e;
                    color: #e0e0e0;
                    border: none;
                    border-bottom: 1px solid #3d3d3d;
                    padding: 4px;
                }
            """
                + scrollbar_dark
            )
        else:
            self.tree_view.setStyleSheet(
                """
                QTreeView {
                    background-color: #ffffff;
                    color: #212529;
                    border: none;
                }
                QTreeView::item:selected {
                    background-color: #e9ecef;
                    color: #212529;
                }
                QHeaderView::section {
                    background-color: #f8f9fa;
                    color: #212529;
                    border: none;
                    border-bottom: 1px solid #e9ecef;
                    padding: 4px;
                }
            """
                + scrollbar_light
            )

    def _set_group_box_style(self):
        """设置分组框样式"""
        style_dark = """
            QGroupBox {
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                margin-top: 2px;
                padding-top: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #aaaaaa;
            }
        """
        style_light = """
            QGroupBox {
                color: #495057;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                margin-top: 2px;
                padding-top: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #6c757d;
            }
        """

        style = style_dark if self.is_dark_theme else style_light
        if hasattr(self, "history_group"):
            self.history_group.setStyleSheet(style)
        if hasattr(self, "favorites_group"):
            self.favorites_group.setStyleSheet(style)

    def _set_list_widget_style(self):
        """设置列表控件样式"""
        scrollbar_dark = """
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #4a4a4a;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5a5a5a;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                background-color: #2d2d2d;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background-color: #4a4a4a;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #5a5a5a;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """
        scrollbar_light = """
            QScrollBar:vertical {
                background-color: #f8f9fa;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #ced4da;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #adb5bd;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                background-color: #f8f9fa;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background-color: #ced4da;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #adb5bd;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """

        style_dark = (
            """
            QListWidget {
                background-color: #252526;
                color: #cccccc;
                border: none;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:selected {
                background-color: #37373d;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #2a2d2e;
            }
        """
            + scrollbar_dark
        )

        style_light = (
            """
            QListWidget {
                background-color: #ffffff;
                color: #212529;
                border: none;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:selected {
                background-color: #e9ecef;
                color: #212529;
            }
        """
            + scrollbar_light
        )

        style = style_dark if self.is_dark_theme else style_light
        if hasattr(self, "history_list"):
            self.history_list.setStyleSheet(style)
        if hasattr(self, "favorites_list"):
            self.favorites_list.setStyleSheet(style)

    def _set_button_style(self):
        """设置按钮样式"""
        if self.is_dark_theme:
            self.clear_history_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3d3d3d;
                    color: #e0e0e0;
                    border: none;
                    border-radius: 4px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:pressed {
                    background-color: #5a5a5a;
                }
            """)
        else:
            self.clear_history_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e9ecef;
                    color: #495057;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background-color: #dee2e6;
                }
                QPushButton:pressed {
                    background-color: #ced4da;
                }
            """)

    def _set_scroll_area_style(self):
        """设置滚动区域样式"""
        if self.is_dark_theme:
            self.scroll_area.setStyleSheet("""
                QScrollArea {
                    background-color: #1e1e1e;
                    border: none;
                }
                QScrollBar:vertical {
                    background-color: #2d2d2d;
                    width: 8px;
                    border-radius: 4px;
                }
                QScrollBar::handle:vertical {
                    background-color: #4a4a4a;
                    border-radius: 4px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #5a5a5a;
                }
            """)
        else:
            self.scroll_area.setStyleSheet("""
                QScrollArea {
                    background-color: #f8f9fa;
                    border: none;
                }
                QScrollBar:vertical {
                    background-color: #e9ecef;
                    width: 8px;
                    border-radius: 4px;
                }
                QScrollBar::handle:vertical {
                    background-color: #ced4da;
                    border-radius: 4px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #adb5bd;
                }
            """)

    def _set_status_bar_style(self):
        """设置状态栏样式"""
        if self.is_dark_theme:
            # 状态栏整体样式
            self.status_bar.setStyleSheet("""
                QStatusBar {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border-top: 1px solid #3d3d3d;
                }
                QStatusBar::item {
                    border: none;
                    border-right: 1px solid #505050; /* 分隔条颜色：白色/浅灰 */
                }
                QLabel {
                    color: #ffffff;
                }
            """
            )
            # 更新特定标签颜色
            if hasattr(self, "size_label"):
                self.size_label.setStyleSheet("padding: 0 10px; color: #ffffff;")

        else:
            # 状态栏整体样式
            self.status_bar.setStyleSheet("""
                QStatusBar {
                    background-color: #f8f9fa;
                    color: #000000;
                    border-top: 1px solid #e9ecef;
                }
                QStatusBar::item {
                    border: none;
                    border-right: 1px solid #ccc; /* 分隔条颜色：黑色/深灰 */
                }
                QLabel {
                    color: #000000;
                }
            """
            )
            # 更新特定标签颜色
            if hasattr(self, "size_label"):
                self.size_label.setStyleSheet("padding: 0 10px; color: #000000;")

    def _set_toolbar_style(self):
        """设置工具栏样式"""
        # 获取资源绝对路径
        base_dir = os.path.dirname(os.path.abspath(__file__))
        res_dir = os.path.join(base_dir, "resources").replace("\\", "/")
        
        if self.is_dark_theme:
            # 暗黑模式
            self.toolbar.setStyleSheet("background-color: #1e1e1e;")
            label_style = "QLabel { color: #e0e0e0; }"
            
            # 使用说明按钮样式
            help_btn_style = """
                QPushButton {
                    background-color: transparent;
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    padding: 4px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 20);
                }
            """
            
            lang_combo_style = """
                QComboBox#langCombo {
                    background-color: transparent;
                    color: #e0e0e0;
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    padding: 0px;
                }
                QComboBox#langCombo:hover {
                    background-color: rgba(255, 255, 255, 20);
                }
                QComboBox#langCombo::drop-down {
                    width: 0px;
                    border: none;
                }
                QComboBox#langCombo::down-arrow {
                    image: none;
                    width: 0px;
                    height: 0px;
                }
                QComboBox#langCombo QAbstractItemView {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    selection-background-color: #3d3d3d;
                    selection-color: #ffffff;
                    border: 1px solid #3d3d3d;
                    min-width: 44px;
                }
            """
            
        else:
            # 亮色模式
            self.toolbar.setStyleSheet("background-color: #f8f9fa;")
            label_style = "QLabel { color: #495057; }"
            
            # 使用说明按钮样式
            help_btn_style = """
                QPushButton {
                    background-color: transparent;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    padding: 4px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 0, 0, 10);
                }
            """

            lang_combo_style = """
                QComboBox#langCombo {
                    background-color: transparent;
                    color: #495057;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    padding: 0px;
                }
                QComboBox#langCombo:hover {
                    background-color: rgba(0, 0, 0, 10);
                }
                QComboBox#langCombo::drop-down {
                    width: 0px;
                    border: none;
                }
                QComboBox#langCombo::down-arrow {
                    image: none;
                    width: 0px;
                    height: 0px;
                }
                QComboBox#langCombo QAbstractItemView {
                    background-color: #ffffff;
                    color: #495057;
                    selection-background-color: #007bff;
                    selection-color: #ffffff;
                    border: 1px solid #ced4da;
                    min-width: 44px;
                }
            """

        # 应用样式
        self.help_btn.setStyleSheet(help_btn_style)
        if hasattr(self, "skin_btn"):
            self.skin_btn.setStyleSheet(help_btn_style)
        if hasattr(self, "lang_combo"):
            self.lang_combo.setStyleSheet(lang_combo_style)
        
        # 更新 QLabel 颜色
        for child in self.toolbar.children():
            if isinstance(child, QLabel):
                child.setStyleSheet(label_style)


    def _on_skin_clicked(self):
        """显示皮肤切换菜单"""
        menu = Win11Menu(parent=self, is_dark=self.is_dark_theme)
        t = TRANSLATIONS.get(self.lang, TRANSLATIONS["zh"])
        menu.setFixedWidth(64)
        checked_bg = "rgba(255, 255, 255, 25)" if self.is_dark_theme else "rgba(0, 0, 0, 15)"
        menu.setStyleSheet(
            menu.styleSheet()
            + f"""
            QMenu::item {{
                padding: 6px 10px 6px 10px;
                margin: 2px 6px;
            }}
            QMenu::indicator {{
                width: 0px;
                height: 0px;
            }}
            QMenu::item:checked {{
                background-color: {checked_bg};
            }}
            """
        )
        
        # 定义皮肤选项
        skins = [
            ("blue", t.get("theme_blue", "蓝色")),
            ("red", t.get("theme_red", "红色")),
            ("green", t.get("theme_green", "绿色"))
        ]
        
        for theme_id, theme_name in skins:
            action = QAction("", menu)
            action.setIcon(_get_tshirt_icon(THEME_COLORS[theme_id]["normal"]))
            action.setToolTip(theme_name)
            
            # 标记当前选中
            if CURRENT_THEME_COLOR == theme_id:
                action.setCheckable(True)
                action.setChecked(True)
            
            # 使用闭包绑定参数
            action.triggered.connect(lambda checked, tid=theme_id: self._on_skin_changed(tid))
            menu.addAction(action)
            
        # 在按钮下方显示菜单
        menu.exec_(self.skin_btn.mapToGlobal(QPoint(0, self.skin_btn.height())))

    def _on_skin_changed(self, theme_id):
        """处理皮肤切换"""
        global CURRENT_THEME_COLOR
        if CURRENT_THEME_COLOR == theme_id:
            return
            
        CURRENT_THEME_COLOR = theme_id
        self.settings.setValue("theme_color", theme_id)
        
        # 刷新所有图标
        self._refresh_all_icons()
        
        # 同步更新 Web 端皮肤颜色
        theme_info = THEME_COLORS.get(theme_id, THEME_COLORS["blue"])
        skin_color = theme_info["normal"]
        
        if hasattr(self, 'web_view') and self.web_view:
            self.web_view.page().runJavaScript(f"if (typeof setSkinColor === 'function') {{ setSkinColor('{skin_color}'); }}")
        
        # 如果预览窗口在 main_view 中被使用 (虽然 ImageViewerWindow 是 main，但预览可能指弹窗)
        # 检查是否有关联的预览窗口逻辑
        # 在这个应用中，预览窗口似乎是 ImageViewerWindow 的一个实例，或者是 main window
        # 根据 _trigger_web_image, ImageViewerWindow 本身就有 web_view
        # 如果是 ImageViewerWindow 的实例切换皮肤，上面的 self.web_view 已经处理了。

    def _refresh_all_icons(self):
        """刷新 UI 中所有受皮肤颜色影响的图标"""
        # 1. 顶部工具栏按钮
        if hasattr(self, 'skin_btn'):
            self.skin_btn.update_icon()
        if hasattr(self, 'lang_combo'):
            self.lang_combo.update_icon()
        if hasattr(self, 'help_btn'):
            self.help_btn.update_icon()
        
        # 2. 树状图图标（包含根节点与所有子节点）
        self._refresh_tree_icons()
            
        # 3. 分割窗口中的图标（排序、布局、操作按钮）
        if hasattr(self, 'splitter'):
            self.splitter.refresh_icons()
            
        # 4. 树状图 Delegate 中的图标（扫描模式、清除按钮等）
        if hasattr(self, 'tree_view'):
            self.tree_view.viewport().update()

    def _refresh_tree_icons(self):
        if not hasattr(self, "file_model"):
            return

        def refresh_item_icons(item: QStandardItem):
            if item is None:
                return

            role = item.data(Qt.UserRole)
            if role == "root_computer":
                item.setIcon(get_computer_icon(self.is_dark_theme))
            elif role == "root_favorites":
                item.setIcon(get_pin_icon(self.is_dark_theme))
            elif role == "root_history":
                item.setIcon(get_history_icon(self.is_dark_theme))
            else:
                if isinstance(role, str) and role:
                    icon = None
                    if sys.platform == "win32":
                        clean_path = role.replace("\\\\?\\", "")
                        if len(clean_path) <= 3 and ":" in clean_path:
                            icon = get_computer_icon(self.is_dark_theme)
                    if icon is None:
                        icon = get_folder_icon(self.is_dark_theme)
                    item.setIcon(icon)

            for i in range(item.rowCount()):
                child = item.child(i)
                if child is not None:
                    refresh_item_icons(child)

        for i in range(self.file_model.rowCount()):
            top = self.file_model.item(i)
            if top is not None:
                refresh_item_icons(top)

# ========== 主程序入口（修复无控制台环境崩溃） ==========
if __name__ == "__main__":
    # log_file = open("picsee_debug.log", "w", encoding="utf-8", buffering=1)
    # Additional crash diagnostics for headless environments
    try:
        import faulthandler

        faulthandler.enable()
    except Exception:
        pass
    try:
        import logging

        logging.basicConfig(
            filename="picsee_extra.log",
            level=logging.DEBUG,
            filemode="a",
            format="%(asctime)s %(levelname)s %(message)s",
        )
    except Exception:
        pass
    # sys.stdout = log_file
    # sys.stderr = log_file

    def exception_hook(exctype, value, traceback_obj):
        print("CRITICAL: Uncaught exception:")
        traceback.print_exception(exctype, value, traceback_obj)
        sys.__stderr__.write("CRITICAL: Uncaught exception (see log)\n")

    sys.excepthook = exception_hook

    # 配置 Chromium 命令行参数
    # 策略调整：尝试使用 ANGLE (DirectX) 后端，这在 Windows 上通常比 Desktop OpenGL 更稳定且支持 GPU。
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--no-sandbox --ignore-gpu-blocklist --enable-gpu-rasterization --enable-zero-copy"
    )

    # 【尝试】使用 ANGLE (OpenGLES) 代替 Desktop OpenGL
    # QApplication.setAttribute(Qt.AA_UseDesktopOpenGL)
    QApplication.setAttribute(Qt.AA_UseOpenGLES)
    os.environ["QT_ANGLE_PLATFORM"] = "d3d11"

    # 【启用】共享 OpenGL 上下文
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

    # 【关键修复】禁用高分屏自动缩放
    # 保持物理分辨率，避免纹理过大
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
    QApplication.setAttribute(Qt.AA_DisableHighDpiScaling)

    # 移除 ANGLE 设置
    # QApplication.setAttribute(Qt.AA_UseOpenGLES)
    # os.environ["QT_ANGLE_PLATFORM"] = "d3d11"

    # 移除软件渲染设置
    # QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)

    # Headless/CI: configure Qt to run without OpenGL/GPU for WebEngine in headless environments
    # try:
    #     import os as _os
    #
    #     _os.environ.setdefault("QT_OPENGL", "software")
    #     _os.environ.setdefault("QTWEBENGINE_DISABLE_GPU", "1")
    #     _os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
    # except Exception:
    #     pass

    app = QApplication(sys.argv)
    try:
        from PyQt5.QtGui import QFontDatabase, QFont

        # 加载 SourceHanSans-Normal 作为默认字体
        font_path = resource_path("resources/SourceHanSans-Normal.ttc").replace("\\", "/")
        if os.path.exists(font_path):
            fid = QFontDatabase.addApplicationFont(font_path)
            if fid != -1:
                fams = QFontDatabase.applicationFontFamilies(fid)
                if fams:
                    app.setFont(QFont(fams[0], 12))
    except Exception as e:
        pass

    # 【UI优化】设置全局默认字体大小 (解决 4K 禁用缩放后字体过小问题)
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    window = ImageViewerWindow()
    window.show()
    sys.exit(app.exec_())
