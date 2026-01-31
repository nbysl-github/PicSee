import sys
import os
import traceback
import ctypes
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QTreeView, QFileSystemModel,
    QWidget, QVBoxLayout, QScrollArea, QLabel, QHBoxLayout, QDialog,
    QStatusBar, QPushButton, QListWidget, QListWidgetItem, QGroupBox,
    QMessageBox, QSizePolicy, QScrollBar, QStyle, QToolButton, QSlider,
    QAction, QMenu, QFileIconProvider, QStyledItemDelegate, QStyleOptionViewItem,
    QSplitterHandle, QToolTip
)

from PyQt5.QtCore import (
    Qt, QModelIndex, QSize, QTimer, QSettings, QDir,
    QThreadPool, QRunnable, pyqtSignal, QObject, QRectF, QPoint, QPointF,
    QMutex, QMutexLocker, QEvent, QUrl, QRect, QFileInfo, QStorageInfo
)
from PyQt5.QtGui import (
    QPixmap, QImage, QPainter, QPainterPath, QColor, QBrush, QPen,
    QCursor, QPalette, QLinearGradient, QKeyEvent, QDesktopServices,
    QIcon, QColorConstants, QImageReader, QImageIOHandler,
    QStandardItemModel, QStandardItem, QTextDocument, QAbstractTextDocumentLayout,
    QTextOption
)
from PIL import Image, ImageOps, UnidentifiedImageError
import io
import json
import time
import unicodedata

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineContextMenuData
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
    QWebEngineView = QWidget # Mock for fallback
    QWebEnginePage = object
    QWebEngineContextMenuData = object

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# ===================== 自定义 WebEngineView =====================
class CustomWebEngineView(QWebEngineView):
    """自定义 WebEngineView 以支持右键菜单"""
    sig_open_explorer = pyqtSignal(str)
    sig_rotate_left = pyqtSignal(str)
    sig_rotate_right = pyqtSignal(str)
    sig_delete_image = pyqtSignal(str)
    sig_refresh = pyqtSignal()
    sig_sort_changed = pyqtSignal(str) # name, date_asc, date_desc, size

    def contextMenuEvent(self, event):
        if not WEBENGINE_AVAILABLE:
            return super().contextMenuEvent(event)
            
        try:
            # 获取点击位置的数据
            data = self.page().contextMenuData()
            
            # 创建自定义菜单
            menu = QMenu(self)
            
            # 检查是否点击了图片
            if data.mediaType() == QWebEngineContextMenuData.MediaTypeImage:
                url = data.mediaUrl()
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    
                    # 1. 在资源管理器中打开
                    action_open = QAction(self.style().standardIcon(QStyle.SP_DirIcon), "在资源管理器中打开", self)
                    action_open.triggered.connect(lambda: self.sig_open_explorer.emit(file_path))
                    menu.addAction(action_open)
                    
                    menu.addSeparator()
                    
                    # 2. 旋转
                    action_left = QAction(self.style().standardIcon(QStyle.SP_ArrowLeft), "向左旋转", self)
                    action_left.triggered.connect(lambda: self.sig_rotate_left.emit(file_path))
                    menu.addAction(action_left)

                    action_right = QAction(self.style().standardIcon(QStyle.SP_ArrowRight), "向右旋转", self)
                    action_right.triggered.connect(lambda: self.sig_rotate_right.emit(file_path))
                    menu.addAction(action_right)
                    
                    menu.addSeparator()
                    
                    # 3. 删除
                    action_delete = QAction(self.style().standardIcon(QStyle.SP_TrashIcon), "删除图片", self)
                    action_delete.triggered.connect(lambda: self.sig_delete_image.emit(file_path))
                    menu.addAction(action_delete)
                    
                    menu.exec_(event.globalPos())
                    return
            
            # 如果点击的是背景（或非本地图片）
            # 添加通用菜单：刷新、排序
            
            action_refresh = QAction(self.style().standardIcon(QStyle.SP_BrowserReload), "刷新", self)
            action_refresh.triggered.connect(self.sig_refresh.emit)
            menu.addAction(action_refresh)
            
            menu.addSeparator()
            
            # 排序子菜单
            sort_menu = menu.addMenu("排序方式")
            
            action_sort_name = QAction("按名称", self)
            action_sort_name.triggered.connect(lambda: self.sig_sort_changed.emit("name"))
            sort_menu.addAction(action_sort_name)
            
            action_sort_date_desc = QAction("按修改时间 (新→旧)", self)
            action_sort_date_desc.triggered.connect(lambda: self.sig_sort_changed.emit("date_desc"))
            sort_menu.addAction(action_sort_date_desc)
            
            action_sort_date_asc = QAction("按修改时间 (旧→新)", self)
            action_sort_date_asc.triggered.connect(lambda: self.sig_sort_changed.emit("date_asc"))
            sort_menu.addAction(action_sort_date_asc)

            action_sort_size = QAction("按大小", self)
            action_sort_size.triggered.connect(lambda: self.sig_sort_changed.emit("size"))
            sort_menu.addAction(action_sort_size)
            
            menu.exec_(event.globalPos())
            
        except Exception as e:
            print(f"ContextMenu Error: {e}")
            super().contextMenuEvent(event)

# ===================== 自定义 Splitter =====================
class CollapsibleSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.is_hovered = False
        self.button_height = 40
        self.button_width = 12
        self.setMouseTracking(True)
        self.press_global_pos = None # 记录按下全局位置，用于区分点击和拖拽

    def paintEvent(self, event):
        # 绘制默认样式
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 计算居中位置
        h = self.height()
        w = self.width()
        
        # 绘制“按钮”背景（仅在中间区域）
        button_rect = QRect(0, (h - self.button_height) // 2, w, self.button_height)
        
        # 悬停效果
        if button_rect.contains(self.mapFromGlobal(QCursor.pos())):
            painter.fillRect(button_rect, QColor("#555555"))
        else:
            painter.fillRect(button_rect, QColor("#333333"))
            
        # 绘制 "III" 图标 (三条竖线)
        painter.setPen(QColor("#AAAAAA"))
        center_y = h // 2
        line_height = 12
        line_spacing = 3
        
        x = w // 2
        
        # 画三条线
        painter.drawLine(x - line_spacing, center_y - line_height//2, x - line_spacing, center_y + line_height//2)
        painter.drawLine(x, center_y - line_height//2, x, center_y + line_height//2)
        painter.drawLine(x + line_spacing, center_y - line_height//2, x + line_spacing, center_y + line_height//2)

    def mousePressEvent(self, event):
        # 记录按下位置
        if event.button() == Qt.LeftButton:
            self.press_global_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # 检查是否为点击操作（位移很小）且在按钮区域内
        if hasattr(self, 'press_global_pos') and self.press_global_pos and event.button() == Qt.LeftButton:
            moved = (event.globalPos() - self.press_global_pos).manhattanLength()
            
            # 将全局坐标映射回本地坐标以检查是否在按钮区域
            local_pos = self.mapFromGlobal(self.press_global_pos)
            h = self.height()
            is_on_button = abs(local_pos.y() - h // 2) <= self.button_height // 2
            
            if moved < 5 and is_on_button:
                if isinstance(self.parent(), CustomSplitter):
                    self.parent().toggle_left_panel()
                    
        self.press_global_pos = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.update() # 触发重绘以更新悬停状态

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()


class CustomSplitter(QSplitter):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setHandleWidth(12) # 稍微加宽以便更容易点击
        self.last_left_width = 250 # 默认展开宽度
        # self.setCollapsible(0, False) # 移至 addWidget 后调用，避免 Index out of range

    def createHandle(self):
        return CollapsibleSplitterHandle(self.orientation(), self)

    def toggle_left_panel(self):
        # 假设左侧面板是第一个 widget (index 0)
        if self.count() < 2:
            return
            
        current_sizes = self.sizes()
        if not current_sizes:
            return
            
        left_width = current_sizes[0]
        
        if left_width > 0:
            # 收起
            self.last_left_width = left_width
            # 必须允许折叠才能设为0
            self.setCollapsible(0, True)
            self.widget(0).setMinimumWidth(0)
            self.widget(0).setMaximumWidth(0) # 强制最大宽度为0，确保完全隐藏内容
            self.setSizes([0, sum(current_sizes)])
        else:
            # 展开
            self.setCollapsible(0, True) # 允许折叠，这样用户可以手动拖拽调整大小
            self.widget(0).setMaximumWidth(16777215) # 恢复最大宽度 (QWIDGETSIZE_MAX)
            self.widget(0).setMinimumWidth(50) 
            target_width = self.last_left_width if self.last_left_width > 50 else 250
            self.setSizes([target_width, sum(current_sizes) - target_width])

# ===================== 核心配置 =====================
FIXED_COLUMN_COUNT = 4         # 固定列数为4
COLUMN_SPACING = 10            # 列间距
ITEM_SPACING = 10              # 项间距
WIDGET_MARGINS = (15,15,15,15) # 边距
MAX_HISTORY_DIRS = 25          # 历史目录数
# 窗口默认尺寸（可调整）
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 800
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
# 性能配置
MAX_THREADS = 2                # 降低线程数，减少崩溃
# 滚动加载阈值（距离底部多少像素触发加载）
SCROLL_THRESHOLD = 100
# 图片质量配置（核心优化：最高质量小图）
IMAGE_QUALITY_SCALE = 2.0      # 缩放系数提升至2.0，预加载更高清小图
# 预览方式配置
USE_SYSTEM_VIEWER = False      # 使用优化后的内置查看器
# 内置预览窗口配置
PREVIEW_SCREEN_HEIGHT_RATIO = 1.0  # 窗口高度为屏幕高度的100%
PREVIEW_MAX_WIDTH_RATIO = 0.95     # 窗口最大宽度为屏幕宽度的95%
PREVIEW_MIN_SIZE = (400, 300)      # 窗口最小尺寸
# 翻页按钮配置
BUTTON_SIZE = 60                   # 圆形按钮尺寸
BUTTON_RADIUS = 30                 # 按钮圆角半径
BUTTON_SPACING = 20                # 按钮与图片间距（增大至20px）
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
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--ignore-gpu-blacklist --enable-gpu-rasterization --enable-zero-copy --enable-native-gpu-memory-buffers"
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
    finished = pyqtSignal(str, QPixmap, int, int)

class ScanSignals(QObject):
    finished = pyqtSignal(list)

class ScanWorker(QRunnable):
    def __init__(self, dir_path, recursive=False):
        super().__init__()
        self.dir_path = dir_path
        self.recursive = recursive
        self.signals = ScanSignals()
        self.setAutoDelete(True)

    def run(self):
        img_data = []
        img_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.ico')
        try:
            # os.walk works with \\\\?\\ paths on Windows
            scan_path = self.dir_path
            
            if self.recursive:
                walker = os.walk(scan_path)
            else:
                # Non-recursive: only scan the current directory
                try:
                    all_files = os.listdir(scan_path)
                    files = [f for f in all_files if os.path.isfile(os.path.join(scan_path, f))]
                    walker = [(scan_path, [], files)]
                except Exception:
                    walker = []
            
            for root, _, files in walker:
                for file in files:
                    if file.lower().endswith(img_extensions):
                        file_path = os.path.join(root, file)
                        
                        # Use QImageReader to get size efficiently
                        reader = QImageReader(file_path)
                        reader.setAutoTransform(True)
                        size = reader.size()
                        w, h = 0, 0
                        if size.isValid():
                            w, h = size.width(), size.height()
                            
                            # Check for rotation requiring dimension swap
                            try:
                                trans = reader.transformation()
                                if trans in [
                                    QImageIOHandler.TransformationRotate90,
                                    QImageIOHandler.TransformationMirrorAndRotate90,
                                    QImageIOHandler.TransformationFlipAndRotate90,
                                    QImageIOHandler.TransformationRotate270
                                ]:
                                    w, h = h, w
                            except Exception:
                                pass
                        
                        # Store raw path and dims
                        try:
                            stat = os.stat(file_path)
                            size_val = stat.st_size
                            mtime_val = stat.st_mtime
                        except:
                            size_val = 0
                            mtime_val = 0
                            
                        img_data.append({
                            "path": file_path,
                            "w": w,
                            "h": h,
                            "size": size_val,
                            "mtime": mtime_val
                        })
            self.signals.finished.emit(img_data)
        except Exception as e:
            print(f"Scan error: {e}")
            self.signals.finished.emit([])

# 图像处理函数（仅缩放，移除增强）
def process_enhanced_image(pil_image, target_w, target_h):
    """
    仅执行缩放，不进行图像增强（锐化、对比度等）
    """
    try:
        # 使用 Lanczos (兰索斯) 算法进行高质量缩放
        resample_method = getattr(Image.Resampling, 'LANCZOS', Image.LANCZOS)
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
                pil_image = pil_image.convert("RGB" if pil_image.mode != "RGBA" else "RGBA")
            
            available_w = max(100, self.view_width - 160)
            available_h = max(100, self.view_height - 60)
            
            scale_w = available_w / pil_image.width
            scale_h = available_h / pil_image.height
            scale_factor = min(scale_w, scale_h, 1.0)
            
            target_w = int(pil_image.width * scale_factor)
            target_h = int(pil_image.height * scale_factor)
            
            enhanced_img = process_enhanced_image(pil_image, target_w, target_h)
            
            img_data = enhanced_img.tobytes()
            q_format = QImage.Format_RGBA8888 if enhanced_img.mode == "RGBA" else QImage.Format_RGB888
            q_img = QImage(img_data, target_w, target_h, 
                          target_w * len(enhanced_img.mode), q_format).copy()
            # Do NOT create QPixmap here. It is unsafe in threads.
            
            # 还原原始路径（去掉 \\?\ 前缀用于匹配）
            original_path = self.path.replace("\\\\?\\", "") if sys.platform == "win32" else self.path
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

    def setPixmap(self, pixmap):
        self.img_pixmap = pixmap
        # 保持缩放比例
        if pixmap and not pixmap.isNull():
            super().setPixmap(pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
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
            scaled_pixmap = self.img_pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled_pixmap.width()) // 2
            y = (self.height() - scaled_pixmap.height()) // 2
            painter.drawPixmap(x, y, scaled_pixmap)

class HTMLDelegate(QStyledItemDelegate):
    sig_scan_mode_changed = pyqtSignal(bool)

    def paint(self, painter, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)

        painter.save()

        doc = QTextDocument()
        text_option = QTextOption()
        text_option.setWrapMode(QTextOption.NoWrap)
        doc.setDefaultTextOption(text_option)
        doc.setHtml(options.text)
        
        # 计算文本区域（在清空文本之前）
        style = options.widget.style()
        text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, options, options.widget)
        
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
        
        # 【新增】如果是“此电脑”节点，绘制切换按钮（倒三角）
        if index.data(Qt.UserRole) == "root_computer":
            is_recursive = index.data(Qt.UserRole + 10) or False
            
            painter.restore()
            painter.save()
            
            # 计算位置：紧跟在文本后面
            text_width = doc.idealWidth()
            icon_x = text_rect.left() + text_width + 10 # 间距 10px
            icon_y = text_rect.top() + (text_rect.height() - height) / 2
            
            # 绘制设置
            # 使用主题文本颜色，略微调淡
            text_color = option.palette.text().color()
            text_color.setAlpha(200) 
            
            painter.setRenderHint(QPainter.Antialiasing, True)
            
            # 定义三角形尺寸 (宽10px, 高8px)
            tri_w = 10
            tri_h = 8
            
            # 中心坐标
            cx = icon_x + 10 # 预留20px宽度的中心
            cy = icon_y + height / 2
            
            # 三角形顶点 (向下)
            p1 = QPointF(cx - tri_w/2, cy - tri_h/2) # 左上
            p2 = QPointF(cx + tri_w/2, cy - tri_h/2) # 右上
            p3 = QPointF(cx, cy + tri_h/2)           # 下中
            
            triangle_path = QPainterPath()
            triangle_path.moveTo(p1)
            triangle_path.lineTo(p2)
            triangle_path.lineTo(p3)
            triangle_path.closeSubpath()
            
            # 笔触设置
            pen = QPen(text_color)
            pen.setWidthF(1.2) # 线条宽度
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            
            if is_recursive:
                painter.setBrush(text_color) # 实心
            else:
                painter.setBrush(Qt.NoBrush) # 空心
                
            painter.drawPath(triangle_path)
            
        painter.restore()

    def editorEvent(self, event, model, option, index):
        # 处理点击事件
        if index.data(Qt.UserRole) == "root_computer":
            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                # 计算点击区域是否在图标上
                # 必须重新计算布局位置
                options = QStyleOptionViewItem(option)
                self.initStyleOption(options, index)
                style = options.widget.style()
                text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, options, options.widget)
                
                doc = QTextDocument()
                doc.setHtml(options.text)
                text_width = doc.idealWidth()
                
                # 图标区域 (宽约25px)
                icon_x = text_rect.left() + text_width + 5
                icon_rect = QRect(int(icon_x), text_rect.top(), 30, text_rect.height())
                
                if icon_rect.contains(event.pos()):
                    current_state = index.data(Qt.UserRole + 10) or False
                    new_state = not current_state
                    self.sig_scan_mode_changed.emit(new_state)
                    return True # 消费事件，阻止默认行为（如选中）

        return super().editorEvent(event, model, option, index)

    def helpEvent(self, event, view, option, index):
        if event.type() == QEvent.ToolTip and index.data(Qt.UserRole) == "root_computer":
            # 计算点击区域是否在图标上 (复用逻辑)
            options = QStyleOptionViewItem(option)
            self.initStyleOption(options, index)
            style = options.widget.style()
            text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, options, options.widget)
            
            doc = QTextDocument()
            doc.setHtml(options.text)
            text_width = doc.idealWidth()
            
            # 图标区域
            icon_x = text_rect.left() + text_width + 5
            icon_rect = QRect(int(icon_x), text_rect.top(), 30, text_rect.height())
            
            if icon_rect.contains(event.pos()):
                is_recursive = index.data(Qt.UserRole + 10) or False
                if is_recursive:
                    QToolTip.showText(event.globalPos(), "当前：递归扫描包含所有子目录\n点击切换为：仅扫描当前目录")
                else:
                    QToolTip.showText(event.globalPos(), "当前：仅扫描当前目录\n点击切换为：递归扫描包含所有子目录")
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
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if section == 0 and orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return "我的电脑"
        return super().headerData(section, orientation, role)


# 带翻页功能的高清预览窗口（最终优化版）
class HighQualityImagePreviewDialog(QDialog):
    def __init__(self, img_path="", img_list=None, parent=None, thumb_rect_callback=None):
        super().__init__(parent)
        
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
        self.setWindowTitle("原图预览")
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
        self.scroll_area.setFocusPolicy(Qt.StrongFocus) # 确保接收键盘事件
        # 恢复默认视口，移除 QOpenGLWidget 以避免兼容性问题
        self.scroll_area.viewport().setFocusPolicy(Qt.StrongFocus)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setAlignment(Qt.AlignCenter) # 居中显示
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar { height: 0px; width: 0px; background: transparent; }
        """)
        
        # 预览标签
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setText("正在加载原图..." if self.valid_img_path else "无有效图片")
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
        self.scroll_area.setAlignment(Qt.AlignCenter) # 确保内容小于窗口时居中
        
        if self.use_web:
            self.web_view = QWebEngineView(self)
            self.web_view.setAttribute(Qt.WA_TranslucentBackground)
            self.web_view.page().setBackgroundColor(Qt.transparent)
            
            # 加载本地 HTML
            html_path = resource_path("preview.html").replace("\\", "/")
            self.web_view.load(QUrl.fromLocalFile(html_path))
            
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
            
            self.scroll_area.hide() # Web模式不需要 ScrollArea
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
        self.play_timer.setInterval(1000) # 默认1秒
        self.play_timer.timeout.connect(self.show_next_image)

        # 高质量渲染防抖定时器
        self.hq_timer = QTimer(self)
        self.hq_timer.setSingleShot(True)
        self.hq_timer.setInterval(200) # 停止操作200ms后触发HQ渲染
        self.hq_timer.timeout.connect(self._render_high_quality)
        
        # 播放按钮
        self.btn_play = QPushButton("▶", self)
        self.btn_play.setFixedSize(40, 40)
        self.btn_play.setToolTip("自动播放")
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
        
        # 间隔滑块
        self.slider_interval = QSlider(Qt.Horizontal, self)
        self.slider_interval.setRange(1, 10) # 1-10秒
        self.slider_interval.setValue(1)
        self.slider_interval.setFixedWidth(100)
        self.slider_interval.setCursor(Qt.PointingHandCursor)
        self.slider_interval.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid rgba(255, 255, 255, 30);
                height: 6px;
                background: rgba(0, 0, 0, 100);
                margin: 2px 0;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: white;
                border: 1px solid rgba(0, 0, 0, 50);
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
        """)
        self.slider_interval.valueChanged.connect(self._update_interval)
        
        # 间隔显示标签
        self.interval_label = QLabel("1.0s", self)
        self.interval_label.setStyleSheet("color: rgba(255, 255, 255, 200); font-weight: bold; font-size: 14px;")
        

        
        # 事件绑定
        self.setFocusPolicy(Qt.StrongFocus)
        self.installEventFilter(self) # 监听 Dialog 自身事件
        self.scroll_area.installEventFilter(self) # 监听 ScrollArea 事件
        self.scroll_area.viewport().installEventFilter(self) # 监听 Viewport 事件
        self.preview_label.installEventFilter(self) # 恢复Label的事件过滤器，但逻辑中允许右键穿透

        self.btn_prev.installEventFilter(self) # 监听按钮事件
        self.btn_next.installEventFilter(self) # 监听按钮事件
        self.btn_play.installEventFilter(self)
        self.slider_interval.installEventFilter(self)
        
        # 加载初始图片
        if img_path or img_list:
            self.load_image(img_path, img_list)

    def load_image(self, img_path, img_list):
        """重置状态并加载新图片"""
        # 安全路径处理
        self.valid_img_list = [safe_path(p) for p in (img_list or []) if os.path.exists(safe_path(p)) and os.path.isfile(safe_path(p))]
        self.valid_img_path = safe_path(img_path) if safe_path(img_path) in self.valid_img_list else (self.valid_img_list[0] if self.valid_img_list else "")
        self.img_list = self.valid_img_list
        self.current_index = self.img_list.index(self.valid_img_path) if self.valid_img_path and self.img_list else 0
        
        # 重置显示状态
        self.original_image = QImage()
        self.scale_factor = 1.0
        self.pil_image = None
        self.preview_label.setText("正在加载原图..." if self.valid_img_path else "无有效图片")
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.adjustSize()
        
        # 更新UI
        if self.valid_img_path:
            original_path = self.valid_img_path.replace("\\\\?\\", "") if sys.platform == "win32" else self.valid_img_path
            self.setWindowTitle(f"原图预览 - {os.path.basename(original_path)}")
            # 延迟加载，确保UI先渲染
            QTimer.singleShot(10, self._load_original_image)
            # 确保获得焦点以响应键盘
            self.activateWindow()
            self.setFocus()
            self.scroll_area.setFocus()
        else:
            self.setWindowTitle("原图预览")
            
        # 隐藏浮层
        self.count_label.hide()
        self.filename_label.hide()
        
        # 停止播放
        if self.is_playing:
            self._toggle_play()

    def closeEvent(self, event):
        """关闭窗口时停止播放和渲染"""
        self.play_timer.stop()
        self.hq_timer.stop()
        if self.is_playing:
            self.is_playing = False
            self.btn_play.setText("▶")
            self.btn_play.setToolTip("自动播放")
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
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
        painter.setBrush(QColor(0, 0, 0, 220)) # 黑色背景，约85%不透明度
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
            if obj == self.scroll_area.viewport() and event.type() == QEvent.Wheel:
                # 获取鼠标相对于 content widget 的位置比例，用于保持缩放中心
                content_widget = self.scroll_area.widget()
                cursor_pos = event.pos()
                rx, ry = 0.5, 0.5 # 默认中心
                
                if content_widget:
                    content_pos = content_widget.mapFrom(self.scroll_area.viewport(), cursor_pos)
                    if content_widget.width() > 0 and content_widget.height() > 0:
                        rx = content_pos.x() / content_widget.width()
                        ry = content_pos.y() / content_widget.height()

                delta = event.angleDelta().y()
                # 无论是 Ctrl+滚轮 还是 直接滚轮，都执行缩放（符合看图习惯）
                if delta > 0:
                    self.scale_factor = min(self.scale_factor * 1.1, 5.0)
                else:
                    self.scale_factor = max(self.scale_factor * 0.9, self.min_scale_factor)
                
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
            if obj == self.scroll_area.viewport() and event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self.close()
                    return True
                elif event.button() == Qt.RightButton:
                    return True # 拦截背景右键，防止意外关闭
            
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
                            img_rect = QRect(x_offset, y_offset, pixmap_size.width(), pixmap_size.height())
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
                        QTimer.singleShot(0, lambda: self._show_context_menu(QCursor.pos()))
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
            return # 明确忽略非左键

        # 点击背景（非按钮区域）关闭窗口
        child = self.childAt(event.pos())

        # 如果点击的是按钮或滑块，不关闭
        if child in [self.btn_prev, self.btn_next, self.btn_play, self.slider_interval]:
            super().mousePressEvent(event)
            return
        # 也可以通过 geometry 判断是否点击在滑块区域（childAt 有时对复杂控件不准）
        if self.slider_interval.geometry().contains(event.pos()):
             super().mousePressEvent(event)
             return
             
        self.close()
        super().mousePressEvent(event)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        if not self.valid_img_path:
            return
            
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #3d3d3d;
            }
            QMenu::item {
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #404040;
            }
        """)
        
        open_folder_action = QAction("在资源管理器中打开文件", self)
        open_folder_action.triggered.connect(self._open_in_explorer)
        menu.addAction(open_folder_action)
        
        menu.exec_(pos)

    def _open_in_explorer(self):
        """在资源管理器中选中当前文件"""
        if not self.valid_img_path:
            return
            
        try:
            path = os.path.abspath(self.valid_img_path)
            if sys.platform == "win32":
                subprocess.run(['explorer', '/select,', path])
            elif sys.platform == "darwin":
                subprocess.run(['open', '-R', path])
            else:
                subprocess.run(['xdg-open', os.path.dirname(path)])
        except Exception as e:
            print(f"打开资源管理器失败: {e}")

    def _toggle_play(self):
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.play_timer.start()
            self.btn_play.setText("⏸")
            self.btn_play.setToolTip("暂停播放")
        else:
            self.play_timer.stop()
            self.btn_play.setText("▶")
            self.btn_play.setToolTip("自动播放")
            
    def _update_interval(self, value):
        self.play_timer.setInterval(value * 1000)
        self.interval_label.setText(f"{value}.0s")

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
        btn.setFocusPolicy(Qt.NoFocus) # 防止按钮抢夺焦点
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
            if not self.valid_img_path or not os.path.exists(self.valid_img_path):
                self.preview_label.setText("图片路径无效")
                return
            
            # 显示加载状态
            self.preview_label.setText("正在优化画质...")
            self.preview_label.setPixmap(QPixmap()) # 清空旧图
            self.original_image = QImage() # 重置
            self.pil_image = None
            
            # 启动后台加载任务
            task = PreviewLoadTask(self.valid_img_path, self.width(), self.height())
            task.signals.result.connect(self._on_preview_loaded)
            self.thread_pool.start(task)
            
        except Exception as e:
            error_msg = f"加载错误：{str(e)[:50]}"
            self.preview_label.setText(error_msg)
            print(f"预览加载失败: {error_msg}")
            traceback.print_exc()


    def _on_preview_loaded(self, path, q_img, scale_factor, pil_image):
        """预览图加载完成回调"""
        # 校验是否是当前需要显示的图片（防止快速翻页导致的错乱）
        current_path = self.valid_img_path.replace("\\\\?\\", "") if sys.platform == "win32" and self.valid_img_path else self.valid_img_path
        if path != current_path:
            return

        self.scale_factor = scale_factor
        self.pil_image = pil_image
        
        # Convert QImage to QPixmap in Main Thread (Safe)
        enhanced_pixmap = QPixmap.fromImage(q_img)
        
        if self.use_web and self.web_view:
            js_path = path.replace("\\", "/")
            if not js_path.startswith("file:///"):
                js_path = "file:///" + js_path
            w = pil_image.width
            h = pil_image.height
            
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
        # 这里为了响应速度，我们可以稍后加载，或者直接使用 QImage(path)
        # 注意：original_image 主要用于 _update_preview 中的快速缩放
        # 如果不加载它，滚轮缩放会失败
        QTimer.singleShot(100, lambda: self._lazy_load_original_image(self.valid_img_path))

    def _lazy_load_original_image(self, path):
        if self.valid_img_path == path:
             self.original_image = QImage(path)

    def _update_preview(self):
        """更新预览图片及按钮位置"""
        try:
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
                scaled_w, scaled_h,
                Qt.KeepAspectRatio,
                transform_flag
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
            q_format = QImage.Format_RGBA8888 if hq_img.mode == "RGBA" else QImage.Format_RGB888
            q_img = QImage(img_data, target_w, target_h, 
                          target_w * len(hq_img.mode), q_format).copy()
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
            
            self.count_label.setText(f"{self.current_index + 1} / {len(self.img_list)}  {size_str}")
            self.count_label.adjustSize()
            self.count_label.setVisible(True)
            self.count_label.raise_()
            
            # 更新文件名标签
            self.filename_label.setText(os.path.basename(self.valid_img_path))
            self.filename_label.adjustSize()
            self.filename_label.setVisible(True)
            self.filename_label.raise_()
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
            margin = 20 # 按钮与图片的间距
            
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
            count_y = self.height() - count_h - 80 # 距离底部80px，留出播放控件位置
            self.count_label.move(int(count_x), int(count_y))
            
        # 更新播放控制栏位置 (屏幕底部居中)
        # 布局：[播放按钮] [滑块] [时间标签] [锐化滑块] [锐化标签]
        
        # 确保控件在最上层
        self.btn_play.raise_()
        self.slider_interval.raise_()
        self.interval_label.raise_()
        self.btn_prev.raise_()
        self.btn_next.raise_()
        self.count_label.raise_()
        self.filename_label.raise_()

        spacing = 15
        total_ctrl_w = self.btn_play.width() + spacing + self.slider_interval.width() + spacing + self.interval_label.width()
        
        start_x = (self.width() - total_ctrl_w) // 2
        ctrl_y = self.height() - 50 # 距离底部50px中心
        
        # 播放按钮
        self.btn_play.move(int(start_x), int(ctrl_y - self.btn_play.height()//2))
        current_x = start_x + self.btn_play.width() + spacing
        
        # 间隔滑块
        self.slider_interval.move(int(current_x), int(ctrl_y - self.slider_interval.height()//2))
        current_x += self.slider_interval.width() + spacing
        
        # 时间标签
        self.interval_label.move(int(current_x), int(ctrl_y - self.interval_label.height()//2))
        self.interval_label.adjustSize()
        current_x += self.interval_label.width() + spacing
        
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
        self.is_web_loaded = True
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
                        thumb_rect_json = f"{{x: {rect['x']}, y: {rect['y']}, w: {rect['w']}}}"
                except Exception as e:
                    print(f"Error getting thumb rect: {e}")

            js_code = f"if(window.openImage) openImage('{js_path}', {w}, {h}, {thumb_rect_json});"
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
                    self.web_view.page().runJavaScript("if(window.zoomIn) window.zoomIn();")
                else:
                    self.scale_factor = min(self.scale_factor * 1.1, 5.0)
                    self._update_preview()
            elif event.key() == Qt.Key_Minus:
                if self.use_web and self.web_view:
                    self.web_view.page().runJavaScript("if(window.zoomOut) window.zoomOut();")
                else:
                    self.scale_factor = max(self.scale_factor * 0.9, self.min_scale_factor)
                    self._update_preview()
            elif event.key() == Qt.Key_Space: # 空格键切换播放/暂停
                self._toggle_play() 
        except Exception as e:
            print(f"键盘事件处理失败: {e}")




# 打开系统查看器（兼容中文路径）
def open_with_system_viewer(img_path):
    try:
        # 安全路径处理
        safe_p = safe_path(img_path)
        original_p = safe_p.replace("\\\\?\\", "") if sys.platform == "win32" else safe_p
        if sys.platform == "win32":
            os.startfile(original_p)
        elif sys.platform == "darwin":
            subprocess.run(["open", original_p], encoding='utf-8')
        else:
            subprocess.run(["xdg-open", original_p], encoding='utf-8')
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
        self.last_width = 0 # 记录上一次宽度
        self.all_img_paths = []  # 存储所有图片路径，供预览翻页使用
        self.loaded_idx = 0
        self.image_cache = {}
        self.is_loading = False
        self.screen_load_count = 0
        self.current_task_id = 0
        self.pending_tasks = []
        self.is_dark_theme = parent.is_dark_theme if hasattr(parent, 'is_dark_theme') else False
        self.preview_dialog = None # 缓存预览窗口实例
        self.path_to_widget = {} # Path -> Widget mapping for animation
        
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
        self.resize_timer.setInterval(500) # 500ms 延迟
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

    def _init_fixed_columns(self):
        self._cancel_all_tasks()
        self.path_to_widget.clear() # Clear mapping
        for w in self.col_widgets:
            w.deleteLater()
        self.columns.clear()
        self.col_widgets.clear()
        self.col_heights.clear()
        while self.horizontal_layout.count() > 0:
            item = self.horizontal_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # 创建4列
        for _ in range(FIXED_COLUMN_COUNT):
            col_widget = QWidget()
            col_layout = QVBoxLayout(col_widget)
            col_layout.setSpacing(ITEM_SPACING)
            col_layout.setContentsMargins(0,0,0,0)
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
            
            print(f"瀑布流宽度变更: {self.last_width} -> {current_width} (差值: {current_width - self.last_width})")
            self.last_width = current_width

            available_width = current_width - WIDGET_MARGINS[0] - WIDGET_MARGINS[2]
            if available_width <= 0:
                return
            total_spacing = (FIXED_COLUMN_COUNT - 1) * COLUMN_SPACING
            # 允许更小的列宽，避免在窗口较小时无法继续缩放
            new_col_width = max(50, int((available_width - total_spacing) / FIXED_COLUMN_COUNT))
            
            # 只要宽度发生变化就刷新，更新列宽
            self.col_width = new_col_width
            self._cancel_all_tasks()
            self.image_cache.clear() # 清除缓存，因为图片宽度变了
            self._init_fixed_columns()
            self._calculate_screen_load_count()
            if self.all_img_paths:
                self.loaded_idx = 0
                self.current_task_id += 1
                # 重新加载第一屏图片，而不是全部
                self._load_batch(0, self.screen_load_count)
        except Exception as e:
            print(f"调整尺寸失败: {e}")

    def clear_waterfall(self):
        self._cancel_all_tasks()
        self.image_cache.clear()
        self.path_to_widget.clear() # Clear mapping
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
        valid_paths = [safe_path(p) for p in paths if os.path.exists(safe_path(p)) and os.path.isfile(safe_path(p))]
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
            self.screen_load_count = len(self.columns) * (visible_height // avg_img_height)
            self.screen_load_count = max(8, min(30, self.screen_load_count))
        except:
            self.screen_load_count = 10

    def _load_batch(self, start_idx, count):
        if self.is_loading or not self.all_img_paths or start_idx >= len(self.all_img_paths):
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
                        p, self.all_img_paths, self.window(),
                        thumb_rect_callback=self.get_thumb_rect
                    )
                    self.preview_dialog.exec_()
            except Exception as e:
                error_msg = f"打开预览失败: {str(e)[:50]}"
                print(error_msg)
                QMessageBox.warning(self.parent(), "预览失败", error_msg)
        
        label.mousePressEvent = lambda e, p=path: safe_show_preview(p)
        label.setPixmap(pixmap)
        self.columns[min_idx].addWidget(label)
        self.col_heights[min_idx] += h + ITEM_SPACING

    def get_thumb_rect(self, path):
        """Get the global screen rectangle of the thumbnail for animation"""
        if path in self.path_to_widget:
            widget = self.path_to_widget[path]
            try:
                # Check if widget is visible and valid
                if widget.isVisible():
                     global_pos = widget.mapToGlobal(QPoint(0, 0))
                     return {'x': global_pos.x(), 'y': global_pos.y(), 'w': widget.width(), 'h': widget.height()}
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
        self.setWindowTitle("Picsee v1.0.1")
        self.setWindowIcon(QIcon(resource_path("resources/icon.png")))
        fix_chinese_path()
        
        # 初始化配置存储
        self.settings = QSettings(APP_COMPANY, APP_NAME)
        
        # 检测系统主题
        self.is_dark_theme = self._detect_dark_theme()
        
        # 初始化核心变量
        self.history_dirs = []
        self.is_scanning = False
        self.current_dir = ""
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(MAX_THREADS)
        
        # 加载历史目录（程序启动时）
        self._load_history_from_settings()
        self._load_favorites_from_settings()
        
        # 窗口基础设置
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        # 启用所有标准窗口按钮（最小化、最大化、关闭）
        # self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        
        # 获取屏幕尺寸并设置窗口大小
        screen = QApplication.desktop().screenGeometry()
        new_width = int(screen.width() * 2 / 3)
        new_height = int(screen.height() * 0.95)
        self.resize(new_width, new_height)
        # 水平居中，垂直顶部对齐
        self.move((screen.width() - new_width) // 2, 0)
        
        # 应用全局主题
        self._apply_complete_theme()
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)
        
        # 分割窗口
        self.splitter = CustomSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # 左侧目录面板
        self.left_widget = QWidget()
        self.left_widget.setMinimumWidth(50) # 允许缩小到50px
        self.left_layout = QVBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(5,5,5,5)
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
        self.tree_delegate = HTMLDelegate(self.tree_view)
        self.tree_delegate.sig_scan_mode_changed.connect(self._on_scan_mode_changed)
        self.tree_view.setItemDelegate(self.tree_delegate)
        
        # 设置内边距，使内容下移 10px
        self.tree_view.setStyleSheet(self.tree_view.styleSheet() + "QTreeView { padding-top: 10px; }")
        
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.left_v_layout.addWidget(self.tree_view)
        
        self.splitter.addWidget(self.left_widget)
        
        # 右侧瀑布流区域 (WebEngine)
        self.web_view = CustomWebEngineView()
        self.web_view.page().setBackgroundColor(Qt.transparent)
        
        # 连接右键菜单信号
        self.web_view.sig_open_explorer.connect(self._open_in_explorer)
        self.web_view.sig_rotate_left.connect(lambda path: self._rotate_image(path, 'left'))
        self.web_view.sig_rotate_right.connect(lambda path: self._rotate_image(path, 'right'))
        self.web_view.sig_delete_image.connect(self._delete_image)
        self.web_view.sig_refresh.connect(self._refresh_images)
        self.web_view.sig_sort_changed.connect(self._change_sort_order)
        
        # 加载本地 HTML
        html_path = resource_path("waterfall.html").replace("\\", "/")
        self.web_view.load(QUrl.fromLocalFile(html_path))
        
        # 传递主题设置
        self.web_view.loadFinished.connect(self._on_web_loaded)
        
        self.splitter.addWidget(self.web_view)
        # self.splitter.setCollapsible(0, False) # 允许拖拽调整
        
        # 状态栏
        self.status_bar = QStatusBar()
        self._set_status_bar_style()
        self.setStatusBar(self.status_bar)
        self.progress_label = QLabel("就绪")
        self.count_label = QLabel("图片：0/0")
        self.status_bar.addWidget(self.progress_label)
        
        self.image_count = 0 # 记录当前图片总数
        self.current_img_data = [] # 当前图片数据
        self.current_sort_mode = "name" # 当前排序模式: name, date_asc, date_desc, size
        
        # 图片大小标签 (居中显示)
        self.size_label = QLabel("")
        self.size_label.setAlignment(Qt.AlignCenter)
        self.size_label.setStyleSheet("padding: 0 10px; color: #e0e0e0;") # 确保文本可见
        # 使用 stretch 让它占据中间空间
        self.status_bar.addWidget(QWidget(), 1) # 占位符
        self.status_bar.addWidget(self.size_label)
        self.status_bar.addWidget(QWidget(), 1) # 占位符
        
        self.status_bar.addPermanentWidget(self.count_label)
        
        # 事件绑定
        self.web_view.titleChanged.connect(self._on_web_title_changed)
        self.tree_view.clicked.connect(self._safe_dir_click)
        self.splitter.setSizes([200, DEFAULT_WIDTH-200]) # 初始宽度200px
        self.splitter.setCollapsible(0, False)
        
    def _on_web_loaded(self, ok):
        if ok:
            # 初始化主题
            self.web_view.page().runJavaScript(f"setTheme({str(self.is_dark_theme).lower()})")

    def _on_web_title_changed(self, title):
        """处理 Web 标题变化（用于接收 JS 消息）"""
        try:
            # 优先处理关闭信号（如果有）
            if title == "action:close":
                self.close()
                return

            if not title or not title.startswith("clicked:"):
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
                        self.count_label.setText(f"图片：{display_idx}/{self.image_count}")
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
        super().resizeEvent(event)

    def _on_splitter_moved(self, pos, index):
        """左侧分割线拖动"""
        pass

    def _detect_dark_theme(self):
        """检测Windows系统暗黑模式"""
        try:
            settings = QSettings("HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize", QSettings.NativeFormat)
            return settings.value("AppsUseLightTheme", 1, type=int) == 0
        except:
            return False

    def _apply_complete_theme(self):
        """应用全局暗黑/亮色主题"""
        if self.is_dark_theme:
            # 尝试启用Windows暗黑标题栏 (Windows 10 2004+ / Windows 11)
            try:
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
                hwnd = int(self.winId())
                rendering_policy = ctypes.c_int(1) # 1 = Enable
                set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
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
            # 尝试禁用Windows暗黑标题栏
            try:
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
                hwnd = int(self.winId())
                rendering_policy = ctypes.c_int(0) # 0 = Disable
                set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
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
        if hasattr(self, 'web_view') and self.web_view.page():
             self.web_view.page().runJavaScript(f"setTheme({str(self.is_dark_theme).lower()})")

    def _load_history_from_settings(self):
        """从配置加载历史目录"""
        try:
            # 读取存储的历史目录列表
            history_data = self.settings.value("history_dirs", [], type=list)
            # 过滤无效目录+安全路径处理
            self.history_dirs = [
                safe_path(path) for path in history_data 
                if os.path.exists(safe_path(path)) and os.path.isdir(safe_path(path))
            ]
            print(f"加载历史目录: {self.history_dirs}")
        except Exception as e:
            self.history_dirs = []

    def _load_favorites_from_settings(self):
        """从配置加载收藏目录"""
        try:
            favorites_data = self.settings.value("favorites_dirs", [], type=list)
            self.favorites_dirs = [
                safe_path(path) for path in favorites_data 
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
        if not dir_path or dir_path in ["root_computer", "root_network", "root_favorites", "root_history"]:
            return
            
        safe_dir = safe_path(dir_path)
        
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
        
        menu = QMenu()
        
        if is_favorite_item:
            # 收藏目录项：移除
            remove_action = QAction(self.style().standardIcon(QStyle.SP_TrashIcon), "从“收藏目录”中取消固定", self)
            remove_action.triggered.connect(lambda: self._remove_from_favorites(safe_dir))
            menu.addAction(remove_action)
        elif is_history_item:
            # 历史目录项：移除
            remove_action = QAction(self.style().standardIcon(QStyle.SP_TrashIcon), "从“历史目录”中取消", self)
            remove_action.triggered.connect(lambda: self._remove_from_history(safe_dir))
            menu.addAction(remove_action)
        else:
            # 普通目录项：添加到收藏
            if os.path.isdir(safe_dir):
                add_action = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton), "保存到收藏目录", self)
                add_action.triggered.connect(lambda: self._add_to_favorites(safe_dir))
                menu.addAction(add_action)
                
        if not menu.isEmpty():
            menu.exec_(self.tree_view.viewport().mapToGlobal(position))

    def _add_to_history(self, dir_path):
        """添加目录到历史（去重+限制数量）"""
        safe_dir = safe_path(dir_path)
        
        # 排除根目录和盘符
        clean_path = safe_dir.replace("\\\\?\\", "") if sys.platform == "win32" else safe_dir
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

    def _init_file_tree(self):
        """初始化自定义文件树模型"""
        self.file_model = QStandardItemModel()
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_model)
        self.tree_view.setHeaderHidden(True)
        
        # 根节点：此电脑 (放在最上面)
        self.computer_item = QStandardItem(QApplication.style().standardIcon(QStyle.SP_ComputerIcon), "此电脑")
        self.computer_item.setData("root_computer", Qt.UserRole)
        self.computer_item.setEditable(False)
        self.file_model.appendRow(self.computer_item)
        
        # 加载驱动器
        self._load_drives()
        
        # 根节点：收藏目录 (采用 此电脑 结构)
        # 使用上传的图片这种样式? 目录名后面显示图钉图标
        self.favorites_item = QStandardItem(self.style().standardIcon(QStyle.SP_DirIcon), "收藏目录")
        self.favorites_item.setData("root_favorites", Qt.UserRole)
        self.favorites_item.setEditable(False)
        self.file_model.appendRow(self.favorites_item)
        self._update_favorites_tree_ui()

        # 根节点：历史目录 (采用 收藏目录 样式，时针图标)
        self.history_item = QStandardItem(self.style().standardIcon(QStyle.SP_DirIcon), "历史目录")
        self.history_item.setData("root_history", Qt.UserRole)
        self.history_item.setEditable(False)
        self.file_model.appendRow(self.history_item)
        self._update_history_tree_ui()

        # 展开此电脑, 收藏, 历史
        self.tree_view.expand(self.computer_item.index())
        self.tree_view.expand(self.favorites_item.index())
        self.tree_view.expand(self.history_item.index())
        
        # 连接展开信号以实现懒加载
        self.tree_view.expanded.connect(self._on_tree_expanded)

    def _update_favorites_tree_ui(self):
        """更新收藏目录树节点"""
        if not hasattr(self, 'favorites_item'):
            return
            
        # 清除现有子节点
        if self.favorites_item.rowCount() > 0:
            self.favorites_item.removeRows(0, self.favorites_item.rowCount())
            
        for dir_path in self.favorites_dirs:
            # 简化显示路径 (仅显示目录名)
            display_name = os.path.basename(dir_path.replace("\\\\?\\", "").rstrip(os.sep)) or dir_path
            if sys.platform == 'win32':
                clean_path = dir_path.replace("\\\\?\\", "")
                if len(clean_path) <= 3 and ':' in clean_path:
                    display_name = clean_path
            
            # 目录名后面显示图钉图标
            # 使用 HTML 灰色显示 (调整颜色为 #999999 以匹配上传图片效果)
            display_text = f"{display_name} <span style='color:#999999'>📌</span>"
            
            item = QStandardItem(display_text)
            item.setToolTip(dir_path)
            item.setData(dir_path, Qt.UserRole)
            item.setEditable(False)
            
            # 设置图标（文件夹）
            icon = self.style().standardIcon(QStyle.SP_DirIcon)
            item.setIcon(icon)
            
            # 添加虚拟子节点，支持展开子目录
            item.appendRow(QStandardItem("Loading..."))
            
            self.favorites_item.appendRow(item)

    def _update_history_tree_ui(self):
        """更新历史目录树节点"""
        if not hasattr(self, 'history_item'):
            return
            
        # 清除现有子节点
        if self.history_item.rowCount() > 0:
            self.history_item.removeRows(0, self.history_item.rowCount())
            
        for dir_path in self.history_dirs:
            # 显示时还原原始路径
            display_path = dir_path.replace("\\\\?\\", "") if sys.platform == "win32" else dir_path
            dir_name = os.path.basename(display_path)
            if not dir_name:
                dir_name = display_path
                
            item = QStandardItem(dir_name)
            item.setToolTip(display_path)
            item.setData(dir_path, Qt.UserRole)
            item.setEditable(False)
            
            # 设置图标（时针）- 这里用 SP_BrowserReload 暂时代替时钟，或者 SP_History (如果存在)
            # 使用 HTML 灰色显示 (调整颜色为 #999999 以匹配上传图片效果)
            item.setText(f"{dir_name} <span style='color:#999999'>🕒</span>")
            
            # Icon 依然是文件夹
            icon = self.style().standardIcon(QStyle.SP_DirIcon)
            item.setIcon(icon)
            
            # 添加虚拟子节点，支持展开子目录
            item.appendRow(QStandardItem("Loading..."))
            
            self.history_item.appendRow(item)

    def _load_drives(self):
        """加载驱动器"""
        icon_provider = QFileIconProvider()
        drives = QDir.drives()
        for drive in drives:
            drive_path = drive.absoluteFilePath()
            
            # 获取驱动器名称
            display_name = drive_path
            try:
                storage = QStorageInfo(drive_path)
                name = storage.name()
                if not name:
                    name = "本地磁盘"
                # 格式化显示名称，例如 "本地磁盘 (C:)"
                drive_letter = drive_path.strip(':/\\')
                display_name = f"{name} ({drive_letter}:)"
            except:
                pass
            
            item = QStandardItem(icon_provider.icon(QFileInfo(drive_path)), display_name)
            item.setData(drive_path, Qt.UserRole)
            item.setEditable(False)
            # 添加虚拟子节点以显示展开箭头
            item.appendRow(QStandardItem("Loading...")) 
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
                item.setData(True, Qt.UserRole + 1) # 标记已加载
            finally:
                QApplication.restoreOverrideCursor()

    def _load_subdirs(self, parent_item, path):
        """加载子目录"""
        icon_provider = QFileIconProvider()
        directory = QDir(path)
        # 只列出目录
        directory.setFilter(QDir.Dirs | QDir.NoDotAndDotDot | QDir.Hidden)
        entry_list = directory.entryInfoList()
        
        for file_info in entry_list:
            item = QStandardItem(icon_provider.icon(file_info), file_info.fileName())
            item.setData(file_info.absoluteFilePath(), Qt.UserRole)
            item.setEditable(False)
            # 预先添加虚拟节点，以便显示展开箭头
            item.appendRow(QStandardItem("Loading..."))
            parent_item.appendRow(item)

    def _safe_dir_click(self, index: QModelIndex):
        """安全处理目录点击（兼容中文路径）"""
        try:
            dir_path = index.data(Qt.UserRole)
            if not dir_path or dir_path in ["root_computer", "root_network", "root_favorites", "root_history"]:
                return
                
            safe_dir = safe_path(dir_path)
            
            # 判断是否为盘符根目录（如 C:/ 或 C:\），如果是则跳过扫描
            if sys.platform == 'win32':
                # 处理 Windows 盘符逻辑
                # 去除 \\?\ 前缀后，如果长度<=3且包含冒号，通常是盘符根目录
                clean_path = safe_dir.replace("\\\\?\\", "")
                if len(clean_path) <= 3 and ':' in clean_path:
                    # 进一步确认是根目录
                    drive, tail = os.path.splitdrive(clean_path)
                    if not tail or tail in ['/', '\\']:
                        self.progress_label.setText(f"已选中 {clean_path}，请选择具体的子目录查看图片")
                        # 展开该节点以便用户继续选择
                        self.tree_view.expand(index)
                        return

            if os.path.isdir(safe_dir):
                self._scan_images(safe_dir)
                self._add_to_history(safe_dir)
        except Exception as e:
            print(f"目录点击处理失败: {e}")
            QMessageBox.warning(self, "错误", f"无法访问目录：{str(e)[:50]}")

    def _safe_history_click(self, item: QListWidgetItem):
        """安全处理历史目录点击"""
        try:
            # 从UserRole获取完整路径，而不是从text()获取
            dir_path = item.data(Qt.UserRole)
            if not dir_path: # 兼容旧逻辑
                dir_path = item.text()
                
            safe_dir = safe_path(dir_path)
            if os.path.isdir(safe_dir):
                self._scan_images(safe_dir)
        except Exception as e:
            print(f"历史目录点击处理失败: {e}")
            QMessageBox.warning(self, "错误", f"无法访问目录：{str(e)[:50]}")

    def _open_in_explorer(self, file_path):
        """在资源管理器中打开文件并选中"""
        try:
            if file_path:
                file_path = unicodedata.normalize('NFC', file_path)
            
            # 去除可能存在的 URL 参数
            if '?' in file_path:
                file_path = file_path.split('?')[0]

            file_path = os.path.normpath(file_path)
            if sys.platform == 'win32':
                subprocess.Popen(['explorer', '/select,', file_path])
            else:
                # macOS/Linux fallback
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(file_path)))
        except Exception as e:
            print(f"Open explorer error: {e}")
            QMessageBox.warning(self, "错误", f"无法打开资源管理器: {e}")

    def _rotate_image(self, path, direction):
        """旋转图片"""
        try:
            # 规范化 Unicode (NFC)
            if path:
                path = unicodedata.normalize('NFC', path)

            # 去除可能存在的 URL 参数
            if '?' in path:
                path = path.split('?')[0]
                
            path = os.path.normpath(path)
            
            print(f"Rotating image: {path} ({direction})")
            
            if not os.path.exists(path):
                print(f"Error: Path does not exist: {path}")
                return
                
            with Image.open(path) as img:
                # 处理 EXIF 方向
                img = ImageOps.exif_transpose(img)
                
                # 旋转
                if direction == 'left':
                    img = img.rotate(90, expand=True)
                else:
                    img = img.rotate(-90, expand=True)
                    
                # 保存
                img.save(path)
                
                # 获取新尺寸
                new_w, new_h = img.size
                
            # 刷新显示（不重新扫描，直接通知前端更新）
            path_str = path.replace("\\", "/")
            timestamp = int(time.time())
            
            # 使用 json.dumps 确保字符串安全
            path_json = json.dumps(path_str)
            
            if hasattr(self, 'web_view') and self.web_view.page():
                # 注意：path_json 已经包含了引号，所以 JS 中不需要再加引号
                js_code = f"imageRotated({path_json}, {new_w}, {new_h}, {timestamp})"
                self.web_view.page().runJavaScript(js_code)
                
        except Exception as e:
            print(f"Rotate error: {e}")
            QMessageBox.warning(self, "错误", f"旋转图片失败: {e}")

    def _on_scan_mode_changed(self, is_recursive):
        """处理扫描模式切换（来自 Delegate 点击）"""
        if hasattr(self, 'computer_item'):
            # 更新模型数据以触发重绘
            self.computer_item.setData(is_recursive, Qt.UserRole + 10)
            
            # 刷新显示
            self.tree_view.update(self.computer_item.index())
            
            # 显示提示
            mode_text = "递归扫描（包含子目录）" if is_recursive else "仅当前目录"
            self.status_bar.showMessage(f"已切换模式: {mode_text}", 2000)
            
            # 如果当前有选中的目录，刷新
            if self.current_dir and not self.is_scanning:
                self._scan_images(self.current_dir)

    def _on_scan_mode_toggled(self, checked):
        # Deprecated: Kept for compatibility if button still exists, but logic moved to _on_scan_mode_changed
        pass

    def _scan_images(self, dir_path):
        """扫描目录下的图片（兼容中文/特殊符号路径）"""
        if self.is_scanning:
            return
        self.is_scanning = True
        self.current_dir = dir_path
        
        # Determine recursive mode from computer item data
        is_recursive = False
        if hasattr(self, 'computer_item'):
            is_recursive = self.computer_item.data(Qt.UserRole + 10) or False

        display_path = dir_path.replace('\\\\?\\', '') if sys.platform == 'win32' else dir_path
        mode_str = '(包含子目录)' if is_recursive else ''
        self.progress_label.setText(f"正在扫描: {display_path} {mode_str}")
        self.status_bar.repaint()
        
        # 使用线程池扫描
        worker = ScanWorker(dir_path, recursive=is_recursive)
        worker.signals.finished.connect(self._on_scan_finished)
        self.thread_pool.start(worker)

    def _paths_are_equal(self, p1, p2):
        """比较两个路径是否相同（忽略大小写和格式差异）"""
        try:
            if not p1 or not p2:
                return False
            n1 = safe_path(p1)
            n2 = safe_path(p2)
            if sys.platform == 'win32':
                return n1.lower() == n2.lower()
            return n1 == n2
        except:
            return False

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
        
        # 确认对话框
        reply = QMessageBox.question(self, '确认删除', 
                                     f"确定要删除这张图片吗？\n{os.path.basename(path)}",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                                     
        if reply == QMessageBox.Yes:
            try:
                if os.path.exists(full_path):
                    os.remove(full_path)
                    
                    # 从当前数据中移除
                    # 使用宽松匹配
                    original_count = len(self.current_img_data)
                    self.current_img_data = [
                        img for img in self.current_img_data 
                        if not self._paths_are_equal(img["path"], full_path)
                    ]
                    new_count = len(self.current_img_data)
                    
                    # 刷新显示
                    self._update_web_view_images()
                else:
                    QMessageBox.warning(self, "错误", "文件不存在，可能已被删除")
                    # 即使文件不存在，也尝试从列表中移除
                    self.current_img_data = [
                        img for img in self.current_img_data 
                        if not self._paths_are_equal(img["path"], full_path)
                    ]
                    self._update_web_view_images()
                    
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败: {e}")

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

    def _apply_sort(self):
        """应用排序"""
        if not self.current_img_data:
            return
            
        try:
            if self.current_sort_mode == "name":
                self.current_img_data.sort(key=lambda x: x["path"].lower())
            elif self.current_sort_mode == "date_asc":
                self.current_img_data.sort(key=lambda x: x.get("mtime", 0))
            elif self.current_sort_mode == "date_desc":
                self.current_img_data.sort(key=lambda x: x.get("mtime", 0), reverse=True)
            elif self.current_sort_mode == "size":
                self.current_img_data.sort(key=lambda x: x.get("size", 0), reverse=True)
        except Exception:
            pass

    def _update_web_view_images(self):
        """更新 Web 视图图片列表"""
        timestamp = int(time.time())
        safe_data = []
        for item in self.current_img_data:
            # 移除 Windows 长路径前缀 \\?\ 以便前端匹配
            raw_path = item["path"]
            if sys.platform == 'win32' and raw_path.startswith("\\\\?\\"):
                raw_path = raw_path[4:]
                
            # 规范化路径 (NFC) 并替换反斜杠
            clean_path = unicodedata.normalize('NFC', raw_path.replace("\\", "/"))
            safe_data.append({
                "path": clean_path, # 原始路径（用于ID）
                "src": clean_path + f"?v={timestamp}", # 显示路径（带时间戳）
                "w": item["w"],
                "h": item["h"]
            })
        
        json_str = json.dumps(safe_data)
        
        # 调用 JS 更新图片
        if hasattr(self, 'web_view') and self.web_view.page():
            self.web_view.page().runJavaScript(f"updateImages({json_str})")
        
        count = len(self.current_img_data)
        self.image_count = count
        self.progress_label.setText(f"扫描完成 (共{count}张)")
        if count > 0:
            self.count_label.setText(f"图片：1/{count}")
        else:
            self.count_label.setText(f"图片：0/0")

    def _on_scan_finished(self, img_data):
        self.is_scanning = False
        self.current_img_data = img_data
        self._apply_sort()
        self._update_web_view_images()

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
            self.tree_view.setStyleSheet("""
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
            """ + scrollbar_dark)
        else:
            self.tree_view.setStyleSheet("""
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
            """ + scrollbar_light)

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
        if hasattr(self, 'history_group'):
            self.history_group.setStyleSheet(style)
        if hasattr(self, 'favorites_group'):
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

        style_dark = """
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
        """ + scrollbar_dark
        
        style_light = """
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
        """ + scrollbar_light
        
        style = style_dark if self.is_dark_theme else style_light
        if hasattr(self, 'history_list'):
            self.history_list.setStyleSheet(style)
        if hasattr(self, 'favorites_list'):
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
            self.status_bar.setStyleSheet("""
                QStatusBar {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    border-top: 1px solid #3d3d3d;
                }
            """)
        else:
            self.status_bar.setStyleSheet("""
                QStatusBar {
                    background-color: #ffffff;
                    color: #495057;
                    border-top: 1px solid #e9ecef;
                }
            """)

# ========== 主程序入口（修复无控制台环境崩溃） ==========
if __name__ == "__main__":
    # 解决高分屏缩放问题
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    # 【移除】导致崩溃的编码配置（嵌入式Python无stdout/stderr）
    # （无需手动设置编码，PyQt5已自动处理中文）
    
    app = QApplication(sys.argv)
    window = ImageViewerWindow()
    window.show()
    sys.exit(app.exec_())