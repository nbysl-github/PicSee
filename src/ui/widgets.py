from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QFrame,
    QLineEdit,
    QLabel,
    QComboBox,
    QPushButton,
    QSplitter,
    QSplitterHandle,
    QToolTip,
    QApplication,
    QStyleOptionViewItem,
    QStyle,
    QStyledItemDelegate,
    QGraphicsOpacityEffect,
    QAction
)
from PyQt5.QtCore import (
    pyqtSignal,
    Qt,
    QEvent,
    QSize,
    QRect,
    QPoint,
    QRectF,
    QPropertyAnimation,
    QEasingCurve,
    QModelIndex
)
from PyQt5.QtGui import (
    QPainter,
    QColor,
    QCursor,
    QPainterPath,
    QFontDatabase,
    QTextDocument,
    QTextOption,
    QPalette
)

from src.utils.icons import (
    get_search_btn_icon,
    get_lang_icon,
    get_layout_type_icon,
    get_sidebar_toggle_icon,
    get_scan_mode_icon,
    get_clear_action_icon,
    get_folder_icon,
    get_rotate_icon,
    get_copy_move_icon,
    get_delete_icon,
    get_refresh_icon,
    get_sort_icon,
    get_asc_desc_icon,
    get_format_icon,
    get_size_icon,
    get_help_icon
)
from src.core.config import TRANSLATIONS, get_current_theme_color
from src.utils.common import resource_path
from src.ui.menu import Win11Menu

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

    def closeEvent(self, event):
        super().closeEvent(event)

    def __del__(self):
        pass

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


class CollapsibleSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.is_hovered = False
        self.button_height = 50  # 增加高度以保持比例 (40 -> 50)
        self.button_width = 32  # 与 handle 宽度一致 (36 -> 32)
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
        icon = get_layout_type_icon(
            current_mode, is_dark, has_offset=False, is_hovered=is_layout_hovered
        )

        # 计算图标绘制区域
        icon_w = 32  # 图标大小 (30 -> 32)
        icon_h = 32
        icon_x = (self.width() - icon_w) // 2
        icon_y = layout_btn_rect.y() + (self.layout_btn_height - icon_h) // 2

        icon_rect = QRect(icon_x, icon_y, icon_w, icon_h)
        icon.paint(painter, icon_rect)

        # --- 绘制折叠按钮 ---
        is_collapse_hovered = collapse_btn_rect.contains(mouse_pos)

        # 根据当前状态决定箭头方向：当左侧宽度 <= 1px 认为已折叠
        is_collapsed = False
        if isinstance(self.parent(), QSplitter):
            parent = self.parent()
            sizes = parent.sizes()
            if sizes:
                is_collapsed = sizes[0] <= 1

        # 折叠与展开状态均绘制图标（方向不同），在透明句柄上仍可见
        collapse_icon = get_sidebar_toggle_icon(
            is_collapsed, is_dark, is_hovered=is_collapse_hovered
        )
        collapse_icon_w = 32
        collapse_icon_h = 32
        collapse_icon_x = (self.width() - collapse_icon_w) // 2
        collapse_icon_y = (
            collapse_btn_rect.y() + (self.button_height - collapse_icon_h) // 2
        )
        collapse_icon_rect = QRect(
            collapse_icon_x, collapse_icon_y, collapse_icon_w, collapse_icon_h
        )
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
            lang = "zh"
            if isinstance(self.parent(), CustomSplitter):
                current_mode = getattr(self.parent(), "current_layout_mode", "vertical")
                lang = getattr(self.parent(), "lang", "zh")

            t = TRANSLATIONS[lang]
            mode_text = (
                t["layout_vertical"]
                if current_mode == "vertical"
                else t["layout_horizontal"]
            )
            QToolTip.showText(event.globalPos(), mode_text)

        elif collapse_btn_rect.contains(event.pos()):
            self.setCursor(Qt.PointingHandCursor)
            lang = "zh"
            if isinstance(self.parent(), CustomSplitter):
                lang = getattr(self.parent(), "lang", "zh")
            t = TRANSLATIONS[lang]
            QToolTip.showText(event.globalPos(), t["sidebar_toggle"])
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

    def __init__(self, orientation, parent=None, lang="zh"):
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

    def refresh_icons(self):
        """刷新 Handle 中的所有图标"""
        for i in range(self.count()):
            handle = self.handle(i)
            if handle:
                handle.repaint()

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

        # 获取左侧部件以便动态调整其最小宽度
        left_widget = self.widget(0)
        if left_widget is None:
            return

        # 首次备份左侧默认最小宽度
        if not hasattr(self, "_left_min_backup"):
            try:
                self._left_min_backup = max(0, left_widget.minimumWidth())
            except Exception:
                self._left_min_backup = 0

        handle_w = 1  # 收起时保留 1px 可见细条
        total = sum(current_sizes)

        # 判定当前是否折叠（左侧宽度<=句柄宽度）
        is_collapsed = current_sizes[0] <= 1

        if not is_collapsed:
            # 收起：记录当前宽度 -> 左侧保留句柄宽度 -> 不隐藏部件，保证可点击
            if current_sizes[0] > handle_w:
                self.last_left_width = current_sizes[0]
            try:
                left_widget.setMinimumWidth(handle_w)
            except Exception:
                pass
            self.setSizes([1, max(100, total - 1)])
            # 折叠时使句柄背景透明，仅显示 1px 左侧条
            try:
                handle = self.handle(1)
                if handle:
                    handle.setStyleSheet("background: transparent;")
            except Exception:
                pass
            self.refresh_handle()
        else:
            # 展开：恢复左侧最小宽度与记录宽度
            try:
                left_widget.setMinimumWidth(self._left_min_backup if hasattr(self, "_left_min_backup") else 0)
            except Exception:
                pass
            target = max(getattr(self, "last_left_width", 300) or 300, 200)
            right = max(100, total - target) if total > 0 else max(100, target)
            self.setSizes([target, right])
            # 展开时恢复句柄背景（使用全局样式）
            try:
                handle = self.handle(1)
                if handle:
                    handle.setStyleSheet("")
            except Exception:
                pass
            self.refresh_handle()

    def refresh_handle(self):
        """强制刷新 handle 的显示状态"""
        for i in range(self.count()):
            handle = self.handle(i)
            if handle:
                handle.update()

# 圆角图片标签
class RoundedImageLabel(QLabel):
    def __init__(self, radius=12, parent=None):
        super().__init__(parent)
        self.radius = radius
        self.img_pixmap = None
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QLabel { background-color: transparent; border: none; }")

        # 性能优化：延迟创建动画效果，每个实例独立
        self._opacity_effect = None
        self._fade_animation = None

    def _init_fade_effect(self):
        """延迟初始化渐现效果，每个实例独立"""
        if self._opacity_effect is None:
            # 修复：不传递self作为parent，避免循环引用和销毁冲突
            self._opacity_effect = QGraphicsOpacityEffect()
            self._opacity_effect.setOpacity(0)
            self.setGraphicsEffect(self._opacity_effect)
        return self._opacity_effect

    def start_fade_in(self):
        """启动渐现动画，每个实例使用独立的动画对象"""
        # 清理旧动画（修复：避免重复断开信号，简化清理逻辑）
        if self._fade_animation:
            # 停止动画并断开信号
            self._fade_animation.stop()
            try:
                self._fade_animation.finished.disconnect(self._cleanup_animation)
            except (TypeError, RuntimeError):
                # 信号未连接或对象已销毁,忽略
                pass
            # 安全删除：使用deleteLater但保留引用直到清理完成
            animation = self._fade_animation
            self._fade_animation = None
            animation.deleteLater()

        effect = self._init_fade_effect()
        # 重置透明度
        effect.setOpacity(0)

        # 创建新的独立动画对象（修复：不传递parent参数，避免循环引用）
        self._fade_animation = QPropertyAnimation(effect, b"opacity")
        self._fade_animation.setDuration(200)
        self._fade_animation.setStartValue(0)
        self._fade_animation.setEndValue(1)
        self._fade_animation.setEasingCurve(QEasingCurve.OutCubic)
        # 连接完成信号（单次连接，新对象无需disconnect）
        self._fade_animation.finished.connect(self._cleanup_animation)
        self._fade_animation.start()

    def _cleanup_animation(self):
        """动画完成后的清理"""
        # 修复：安全清理，避免重复deleteLater
        animation = self._fade_animation
        self._fade_animation = None  # 先清除引用
        if animation:
            animation.deleteLater()

    def __del__(self):
        """析构函数：确保资源被正确释放（修复：防止内存泄漏）"""
        # 停止并清理动画
        if self._fade_animation:
            try:
                self._fade_animation.stop()
                self._fade_animation.deleteLater()
            except (RuntimeError, TypeError):
                # 对象已销毁,忽略
                pass
            self._fade_animation = None
        # 清理效果对象
        if self._opacity_effect:
            try:
                self._opacity_effect.deleteLater()
            except (RuntimeError, TypeError):
                # 对象已销毁,忽略
                pass
            self._opacity_effect = None

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

    _custom_font_family = None

    def __init__(self, parent=None, lang="zh"):
        super().__init__(parent)
        self.lang = lang
        self.hover_index = QModelIndex()
        self.hover_pos = QPoint()

        # 加载自定义字体 SourceHanSans-Bold (只需加载一次)
        if HTMLDelegate._custom_font_family is None:
            font_id = QFontDatabase.addApplicationFont(
                resource_path("resources/SourceHanSans-Bold.ttc")
            )
            HTMLDelegate._custom_font_family = "SimHei"  # Default fallback
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    HTMLDelegate._custom_font_family = families[0]

        # 启用鼠标追踪以支持悬停效果
        if parent:
            parent.setMouseTracking(True)

    def paint(self, painter, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)

        painter.save()

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
            html_content = f"<span style=\"font-family: '{self._custom_font_family}'; font-weight: bold;\">{html_content}</span>"

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
            return False  # 继续传递事件，不要吞掉

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
                    try:
                        # 判断当前是否为暗黑模式
                        text_color = options.palette.color(QPalette.Text)
                        is_dark = text_color.lightness() > 128

                        # 弹出菜单
                        menu = Win11Menu(parent=options.widget, is_dark=is_dark)

                        # 使用统一的蓝色风格清除图标
                        icon = get_clear_action_icon(is_dark, is_hovered=False)
                        # 获取语言设置（从主窗口获取）
                        lang = "zh"
                        if options.widget:
                            main_window = options.widget.window()
                            if hasattr(main_window, "lang"):
                                lang = main_window.lang
                        t = TRANSLATIONS.get(lang, TRANSLATIONS["zh"])
                        clear_action = QAction(icon, t.get("menu_clear", "Clear"), menu)

                        # 触发清除信号
                        clear_action.triggered.connect(
                            lambda: self.sig_clear_root.emit(item_role)
                        )
                        menu.addAction(clear_action)

                        menu.exec_(event.globalPos())
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                    return True

        return super().editorEvent(event, model, option, index)

    def helpEvent(self, event, view, option, index):
        item_role = index.data(Qt.UserRole)
        if event.type() == QEvent.ToolTip and item_role == "root_computer":
            # 计算点击区域是否在图标上 (复用逻辑)
            options = QStyleOptionViewItem(option)
            self.initStyleOption(options, index)
            style = options.widget.style()
            text_rect = style.subElementRect(
                QStyle.SE_ItemViewItemText, options, options.widget
            )

            # 图标区域 (向右对齐)
            icon_x = options.rect.right() - 35
            icon_rect = QRect(int(icon_x) - 10, text_rect.top(), 50, text_rect.height())

            if icon_rect.contains(event.pos()):
                t = TRANSLATIONS[self.lang]
                is_recursive = index.data(Qt.UserRole + 10) or False
                if is_recursive:
                    QToolTip.showText(
                        event.globalPos(),
                        t["tooltip_scan_multi"],
                    )
                else:
                    QToolTip.showText(
                        event.globalPos(),
                        t["tooltip_scan_single"],
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
                    QToolTip.showText(event.globalPos(), t["tooltip_clear"])
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
