import sys
import os
import subprocess
import time

from PyQt5.QtWidgets import (
    QWidget,
    QScrollArea,
    QLabel,
    QPushButton,
    QMessageBox,
    QVBoxLayout,
    QAction,
    QMenu,
    QApplication,
)
from PyQt5.QtCore import (
    pyqtSignal,
    Qt,
    QEvent,
    QSize,
    QRect,
    QPoint,
    QTimer,
    QThreadPool,
    QMutex,
    QMutexLocker,
    QUrl,
    QRunnable,
    QObject,
)
from PyQt5.QtGui import (
    QPainter,
    QColor,
    QCursor,
    QPalette,
    QPixmap,
    QImage,
    QDesktopServices,
    QKeyEvent,
)

try:
    from PyQt5.QtWebEngineWidgets import (
        QWebEngineView,
        QWebEnginePage,
        QWebEngineContextMenuData,
        QWebEngineSettings,
    )

    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

    # Mock classes for fallback
    class QWebEngineView(QWidget):
        def page(self):
            return None

        def load(self, url):
            pass

        def setAttribute(self, attr):
            pass

        def titleChanged(self, title):
            pass

        # Add minimal signals/methods if needed to prevent crashes in non-web mode
        # titleChanged is a signal in QWebEngineView

    class QWebEnginePage:
        pass

    class QWebEngineSettings:
        pass

    class QWebEngineContextMenuData:
        MediaTypeImage = 1  # Dummy value

        def mediaType(self):
            return None

        def mediaUrl(self):
            return None


from src.core.config import TRANSLATIONS, THEME_COLORS
from src.utils.common import resource_path, safe_path
from src.ui.menu import Win11Menu
from src.workers.loader import PreviewLoadTask
from src.workers.utils import process_enhanced_image
from src.utils.icons import (
    get_folder_icon,
    get_rotate_icon,
    get_copy_move_icon,
    get_delete_icon,
    get_refresh_icon,
    get_sort_icon,
    get_asc_desc_icon,
    get_format_icon,
    get_size_icon,
)


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

    def __init__(self, parent=None, lang="zh"):
        super().__init__(parent)
        self.lang = lang

        if WEBENGINE_AVAILABLE:
            settings = self.settings()
            # 允许本地内容访问本地文件 (关键：修复瀑布流图片不显示)
            settings.setAttribute(
                QWebEngineSettings.LocalContentCanAccessFileUrls, True
            )
            settings.setAttribute(
                QWebEngineSettings.LocalContentCanAccessRemoteUrls, True
            )
            settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
            settings.setAttribute(QWebEngineSettings.FocusOnNavigationEnabled, False)
            # 允许从本地文件加载资源 (增强兼容性)
            if hasattr(QWebEngineSettings, "AllowFileAccessFromFiles"):
                settings.setAttribute(QWebEngineSettings.AllowFileAccessFromFiles, True)

    def contextMenuEvent(self, event):
        if not WEBENGINE_AVAILABLE:
            return super().contextMenuEvent(event)

        try:
            main_window = self.window()
            # 检测主题模式
            is_dark = getattr(main_window, "is_dark_theme", True)
            
            # 获取点击位置的数据
            data = self.page().contextMenuData() if self.page() else None
            # 获取翻译
            t = TRANSLATIONS[self.lang]

            # 创建自定义菜单
            menu = Win11Menu(parent=self, is_dark=is_dark)
            menu.apply_style()

            # 只有当我们成功准备好菜单时，才拦截原生事件
            event.accept()

            # 检查是否点击了图片
            if data and data.mediaType() == QWebEngineContextMenuData.MediaTypeImage:
                url = data.mediaUrl()
                if url and url.isLocalFile():
                    file_path = url.toLocalFile()

                    # 1. 在资源管理器中打开
                    action_open = QAction(
                        get_folder_icon(is_dark),
                        t["menu_open_explorer"],
                        self,
                    )
                    action_open.triggered.connect(
                        lambda: self.sig_open_explorer.emit(file_path)
                    )
                    menu.addAction(action_open)

                    menu.addSeparator()

                    # 2. 旋转
                    action_left = QAction(
                        get_rotate_icon("left", is_dark), t["menu_rotate_left"], self
                    )
                    action_left.triggered.connect(
                        lambda: self.sig_rotate_left.emit(file_path)
                    )
                    menu.addAction(action_left)

                    action_right = QAction(
                        get_rotate_icon("right", is_dark),
                        t["menu_rotate_right"],
                        self,
                    )
                    action_right.triggered.connect(
                        lambda: self.sig_rotate_right.emit(file_path)
                    )
                    menu.addAction(action_right)

                    menu.addSeparator()

                    # 复制/移动
                    action_copy = QAction(
                        get_copy_move_icon("copy", is_dark), t["menu_copy_to"], self
                    )
                    action_copy.triggered.connect(
                        lambda: self.sig_copy_image.emit(file_path)
                    )
                    menu.addAction(action_copy)

                    action_move = QAction(
                        get_copy_move_icon("move", is_dark), t["menu_move_to"], self
                    )
                    action_move.triggered.connect(
                        lambda: self.sig_move_image.emit(file_path)
                    )
                    menu.addAction(action_move)

                    menu.addSeparator()

                    # 3. 删除
                    action_delete = QAction(
                        get_delete_icon(is_dark), t["menu_delete"], self
                    )
                    action_delete.triggered.connect(
                        lambda: self.sig_delete_image.emit(file_path)
                    )
                    menu.addAction(action_delete)

                    menu.exec_(event.globalPos())
                    return

            # 如果点击的是背景（或非本地图片）
            # 添加通用菜单：刷新、排序

            action_refresh = QAction(get_refresh_icon(is_dark), t["menu_refresh"], self)
            action_refresh.triggered.connect(self.sig_refresh.emit)
            menu.addAction(action_refresh)

            menu.addSeparator()

            # 排序子菜单
            sort_menu = menu.addMenu(get_sort_icon(is_dark), t["menu_sort"])

            # 获取当前排序模式以显示选中状态
            main_window = self.window()
            current_sort = getattr(main_window, "current_sort_mode", "name_asc")

            def add_sort_action(menu_obj, mode, icon_type, label_key):
                # 获取选中状态
                is_selected = current_sort == mode
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

            sort_menu.addSeparator()  # 三栏之间要有分隔线

            # 2. 日期排序
            add_sort_action(sort_menu, "date_desc", "desc", "menu_sort_date_desc")
            add_sort_action(sort_menu, "date_asc", "asc", "menu_sort_date_asc")

            sort_menu.addSeparator()  # 三栏之间要有分隔线

            # 3. 大小排序
            add_sort_action(sort_menu, "size_desc", "desc", "menu_sort_size_desc")
            add_sort_action(sort_menu, "size_asc", "asc", "menu_sort_size_asc")

            menu.addSeparator()

            # 格式筛选子菜单
            format_menu = menu.addMenu(get_format_icon(is_dark), t["format_label"])

            # 获取当前选中的格式
            current_format = getattr(
                main_window, "current_format_filter", t["all_formats"]
            )

            def add_format_action(menu_obj, label):
                # 保持与排序菜单一致：点后面跟2个空格
                prefix = "·  " if current_format == label else "   "
                action = QAction(prefix + label, self)
                action.triggered.connect(lambda: self.sig_format_changed.emit(label))
                menu_obj.addAction(action)

            formats = [
                t["all_formats"],
                "JPG",
                "PNG",
                "GIF",
                "BMP",
                "WEBP",
                "SVG",
                "RAW",
            ]
            for f in formats:
                add_format_action(format_menu, f)

            # 尺寸筛选子菜单
            size_menu = menu.addMenu(get_size_icon(is_dark), t["size_label"])

            # 获取当前选中的尺寸
            current_size = getattr(main_window, "current_size_filter", t["all_sizes"])

            def add_size_action(menu_obj, label):
                prefix = "·  " if current_size == label else "   "
                action = QAction(prefix + label, self)
                action.triggered.connect(lambda: self.sig_size_changed.emit(label))
                menu_obj.addAction(action)

            sizes = [t["all_sizes"], t["size_small"], t["size_medium"], t["size_large"]]
            for s in sizes:
                add_size_action(size_menu, s)

            menu.exec_(event.globalPos())

        except Exception as e:
            pass


# 带翻页功能的高清预览窗口（最终优化版）
class PreviewWebEngineView(QWebEngineView):
    """用于图片预览的专用 WebEngineView，拦截滚轮事件以驱动 PhotoSwipe"""

    def __init__(self, parent=None):
        super().__init__(parent)
        if WEBENGINE_AVAILABLE:
            settings = self.settings()
            settings.setAttribute(
                QWebEngineSettings.LocalContentCanAccessFileUrls, True
            )
            settings.setAttribute(
                QWebEngineSettings.LocalContentCanAccessRemoteUrls, True
            )
            settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
            settings.setAttribute(QWebEngineSettings.FocusOnNavigationEnabled, False)
            if hasattr(QWebEngineSettings, "AllowFileAccessFromFiles"):
                settings.setAttribute(QWebEngineSettings.AllowFileAccessFromFiles, True)

    def contextMenuEvent(self, event):
        """Web 模式下的右键菜单：直接调用父窗口的菜单逻辑"""
        # 获取全局坐标
        global_pos = event.globalPos()

        # 核心：确保不弹出默认菜单
        event.accept()

        parent = self.parent()
        found = False
        while parent:
            if hasattr(parent, "_show_context_menu"):
                parent._show_context_menu(global_pos)
                found = True
                break
            parent = parent.parent()

        if not found:
            # 尝试通过 window() 找
            win = self.window()
            if hasattr(win, "_show_context_menu"):
                win._show_context_menu(global_pos)
            else:
                super().contextMenuEvent(event)

    def install_proxy_filter(self):
        """安装事件过滤器到 focusProxy (渲染部件)"""
        if self.focusProxy():
            self.focusProxy().removeEventFilter(self)
            self.focusProxy().installEventFilter(self)

    def eventFilter(self, obj, event):
        """核心：拦截渲染部件的滚轮事件"""
        return super().eventFilter(obj, event)

    def wheelEvent(self, event):
        """备用：如果事件冒泡到了 View 本身"""
        super().wheelEvent(event)


class HighQualityImagePreviewDialog(QWidget):
    # 类级别的共享线程池（性能优化：避免每次创建都新建线程池）
    _shared_thread_pool = None
    _thread_pool_lock = QMutex()

    # 追踪所有打开的预览窗口，确保清理彻底
    _active_instances = []
    _instances_lock = QMutex()

    @classmethod
    def get_thread_pool(cls):
        with QMutexLocker(cls._thread_pool_lock):
            if cls._shared_thread_pool is None:
                cls._shared_thread_pool = QThreadPool()
                cls._shared_thread_pool.setMaxThreadCount(4)
            return cls._shared_thread_pool

    @classmethod
    def cleanup_all_instances(cls, exclude_id=None):
        """强力清理所有实例（包括未追踪的僵尸实例）"""
        targets = []

        # 1. 从追踪列表获取
        with QMutexLocker(cls._instances_lock):
            # 使用 list() 复制一份，防止遍历时被修改
            current_instances = list(cls._active_instances)
            for ins in current_instances:
                try:
                    my_id = getattr(ins, "_dialog_id", "N/A")
                    if exclude_id is None or (my_id != "N/A" and my_id != exclude_id):
                        if ins not in targets:
                            targets.append(ins)
                except Exception:
                    pass

        # 2. 从 topLevelWidgets 获取（防止僵尸实例）
        try:
            widgets = QApplication.topLevelWidgets()
            for w in widgets:
                try:
                    # 检查类名
                    if w.__class__.__name__ == "HighQualityImagePreviewDialog":
                        my_id = getattr(w, "_dialog_id", "N/A")
                        if exclude_id is None or (
                            my_id != "N/A" and my_id != exclude_id
                        ):
                            if w not in targets:
                                targets.append(w)
                except Exception:
                    pass
        except Exception:
            pass

        if not targets:
            return

        for ins in targets:
            try:
                # 再次确认不是排除对象
                my_id = getattr(ins, "_dialog_id", "unknown")
                if exclude_id and my_id == exclude_id:
                    continue

                # 彻底断开信号
                if (
                    hasattr(ins, "use_web")
                    and ins.use_web
                    and hasattr(ins, "web_view")
                    and ins.web_view
                ):
                    try:
                        ins.web_view.titleChanged.disconnect()
                        ins.web_view.loadFinished.disconnect()
                        ins.web_view.stop()
                        ins.web_view.load(QUrl("about:blank"))
                    except:
                        pass

                ins.hide()
                # 优先使用 _force_close
                if hasattr(ins, "_force_close"):
                    ins._force_close()
                else:
                    ins.close()
                    ins.deleteLater()
            except Exception:
                try:
                    ins.hide()
                    ins.deleteLater()
                except:
                    pass

    def __init__(
        self,
        img_path="",
        img_list=None,
        parent=None,
        thumb_rect_callback=None,
        lang="zh",
    ):
        # 0. 立即设置唯一标识 (使用 id() 避免时间戳冲突)
        self._dialog_id = str(id(self))

        super().__init__(parent)
        self.lang = lang
        self.setObjectName(f"PreviewDialog_{self._dialog_id}")

        # 注册实例
        with QMutexLocker(self._instances_lock):
            HighQualityImagePreviewDialog._active_instances.append(self)

        # 1. 窗口基础设置
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # 2. 启用自定义右键菜单 (确保 Web 模式下也能触发)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # 核心属性
        self.parent_window = parent
        self.screen_geo = QApplication.desktop().screenGeometry()
        self.resize(self.screen_geo.width(), self.screen_geo.height())

        # 使用共享线程池而不是创建新线程池
        self.thread_pool = self.get_thread_pool()

        # 应用全屏半透明遮罩样式
        self.setStyleSheet(f"""
            QWidget {{
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
        t = TRANSLATIONS[self.lang]
        self.preview_label.setText(
            t["loading_original"] if self.valid_img_path else t["no_valid_image"]
        )
        self.preview_label.setMouseTracking(True)
        # 启用右键菜单
        self.preview_label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.preview_label.customContextMenuRequested.connect(self._show_context_menu)

        # 渲染模式选择：WebEngine > QLabel
        self.use_web = WEBENGINE_AVAILABLE

        # Web模式下背景设为透明，由PhotoSwipe控制背景和动画
        if self.use_web:
            self.setStyleSheet("QWidget { background-color: transparent; }")

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
                    self, t["error"], f"preview.html not found at: {html_path}"
                )

            # 使用 fromLocalFile 处理路径中的空格和特殊字符
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
        self.btn_play.setToolTip(t["play_tooltip"])
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
            t["loading_original"] if self.valid_img_path else t["no_valid_image"]
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
            self.setWindowTitle(
                t["preview_title"].format(os.path.basename(original_path))
            )
            # 延迟加载，确保UI先渲染
            QTimer.singleShot(10, self._load_original_image)
            # 确保获得焦点以响应键盘
            self.activateWindow()
            self.setFocus()
            self.scroll_area.setFocus()
        else:
            self.setWindowTitle(t["preview_title"].format(""))

        # 隐藏浮层
        self.count_label.hide()
        self.filename_label.hide()

        # 停止播放
        if self.is_playing:
            self._toggle_play()

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        # 如果已经完全销毁，则直接接受事件并返回
        if getattr(self, "_is_fully_destroyed", False):
            event.accept()
            return

        # 统一调用强制关闭逻辑
        self._force_close()
        event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        # 隐藏主窗口状态栏以防止文字重叠
        # 1. 尝试直接通过 self.parent_window 获取
        if self.parent_window and hasattr(self.parent_window, "status_bar"):
            self.parent_window.status_bar.hide()

        # 2. 尝试通过 self.parent() 获取
        parent = self.parent()
        found_status_bar = False
        while parent:
            if hasattr(parent, "status_bar"):
                parent.status_bar.hide()
                found_status_bar = True
                break
            parent = parent.parent()

        # 3. 强力模式：延时再次隐藏，防止被其他事件恢复
        def force_hide():
            if self.parent_window and hasattr(self.parent_window, "status_bar"):
                self.parent_window.status_bar.hide()

        QTimer.singleShot(100, force_hide)

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
            # 这里不需要再做任何拦截
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
                    self._press_escape()
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
                            # 点击在 Label 的空白区域 -> 模拟 ESC 关闭
                            self._press_escape()
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
            pass
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

        # 判定 pos 是全局还是局部
        if isinstance(pos, QPoint):
            # 检查 pos 是否已经在全局范围内
            cursor_pos = QCursor.pos()
            dist_to_cursor = (pos - cursor_pos).manhattanLength()

            if dist_to_cursor < 10:  # 认为 pos 已经是全局坐标
                global_pos = pos
            else:
                global_pos = self.mapToGlobal(pos)
        else:
            global_pos = QCursor.pos()

        # 检测当前背景色以决定菜单主题
        is_dark = True
        if self.parent_window:
            is_dark = getattr(self.parent_window, "is_dark_theme", True)
        
        menu = Win11Menu(parent=self, is_dark=is_dark)
        # 强制应用样式
        menu.apply_style()
        t = TRANSLATIONS[self.lang]

        # 1. 在资源管理器中打开
        open_folder_action = QAction(
            get_folder_icon(is_dark=is_dark), t["menu_open_explorer"], self
        )
        open_folder_action.triggered.connect(self._open_in_explorer)
        menu.addAction(open_folder_action)

        menu.addSeparator()

        # 2. 旋转（左/右）
        action_rotate_left = QAction(
            get_rotate_icon("left", is_dark=is_dark), t["menu_rotate_left"], self
        )
        action_rotate_left.triggered.connect(self._on_rotate_left_menu)
        menu.addAction(action_rotate_left)

        action_rotate_right = QAction(
            get_rotate_icon("right", is_dark=is_dark), t["menu_rotate_right"], self
        )
        action_rotate_right.triggered.connect(self._on_rotate_right_menu)
        menu.addAction(action_rotate_right)

        menu.addSeparator()

        # 3. 复制/移动
        action_copy = QAction(
            get_copy_move_icon("copy", is_dark=is_dark), t["menu_copy_to"], self
        )
        action_copy.triggered.connect(self._copy_image)
        menu.addAction(action_copy)

        action_move = QAction(
            get_copy_move_icon("move", is_dark=is_dark), t["menu_move_to"], self
        )
        action_move.triggered.connect(self._move_image)
        menu.addAction(action_move)

        menu.addSeparator()

        # 4. 删除
        action_delete = QAction(get_delete_icon(is_dark=is_dark), t["menu_delete"], self)
        action_delete.triggered.connect(self._delete_image)
        menu.addAction(action_delete)

        menu.exec_(global_pos)

    def _rotate_and_close(self, direction):
        """旋转图片后关闭预览并刷新瀑布流"""
        print(f"DEBUG: _rotate_and_close start direction={direction}", flush=True)
        if not self.valid_img_path:
            return

        # 移除 Windows 长路径前缀
        file_path = self.valid_img_path
        if sys.platform == "win32" and file_path.startswith("\\\\?\\"):
            file_path = file_path[4:]

        # 旋转图片
        if self.parent_window and hasattr(self.parent_window, "_rotate_image"):
            print(f"DEBUG: calling _rotate_image path={file_path}", flush=True)
            self.parent_window._rotate_image(file_path, direction, exclude_id=self._dialog_id)

        self._press_escape()
        QTimer.singleShot(120, self._force_close)

    def _on_rotate_left_menu(self):
        print("DEBUG: Right-click menu rotate left clicked", flush=True)
        self._rotate_and_close("left")

    def _on_rotate_right_menu(self):
        print("DEBUG: Right-click menu rotate right clicked", flush=True)
        self._rotate_and_close("right")

    def _force_close(self):
        """强制销毁窗口及其所有资源，确保不留残余"""
        # 如果已经完全销毁，则直接返回
        if getattr(self, "_is_fully_destroyed", False):
            return

        # 标记正在销毁中
        self._is_closing_internal = True

        try:
            # 1. 停止计时器和播放状态
            if hasattr(self, "play_timer"):
                self.play_timer.stop()
            if hasattr(self, "hq_timer"):
                self.hq_timer.stop()
            self.is_playing = False

            # 2. 立即从视觉上完全消失
            self.setWindowOpacity(0.0)
            self.setEnabled(False)
            self.hide()
            self.setVisible(False)

            # 3. 恢复主窗口状态栏
            if self.parent_window and hasattr(self.parent_window, "status_bar"):
                self.parent_window.status_bar.show()

            parent = self.parent()
            while parent:
                if hasattr(parent, "status_bar"):
                    parent.status_bar.show()
                    break
                parent = parent.parent()

            # 4. 确保从全局列表移除 (使用互斥锁)
            try:
                with QMutexLocker(HighQualityImagePreviewDialog._instances_lock):
                    if self in HighQualityImagePreviewDialog._active_instances:
                        HighQualityImagePreviewDialog._active_instances.remove(self)
            except Exception:
                pass

            # 5. 清理 WebEngineView 资源
            if hasattr(self, "web_view") and self.web_view:
                try:
                    view = self.web_view
                    self.web_view = None  # 切断引用

                    if view.page():
                        # 尝试销毁 JS 端的 PhotoSwipe (静默执行)
                        try:
                            view.page().runJavaScript(
                                "if(window.pswpInstance) { try { window.pswpInstance.destroy(); } catch(e) {} window.pswpInstance = null; }"
                            )
                        except:
                            pass

                        view.stop()
                        view.setPage(None)

                    view.setParent(None)
                    view.deleteLater()
                except Exception:
                    pass

            # 6. 通知主窗口释放引用
            if self.parent_window and hasattr(
                self.parent_window, "active_preview_dialog"
            ):
                if self.parent_window.active_preview_dialog == self:
                    self.parent_window.active_preview_dialog = None

            # 7. 标记为完全销毁
            self._is_fully_destroyed = True

            # 8. 彻底从父对象脱离并调度销毁
            self.setParent(None)
            # 使用 deleteLater 确保在事件循环中销毁
            self.deleteLater()

            # 9. 强制刷新一次事件，让隐藏生效
            QApplication.processEvents()

        except Exception:
            self.hide()
            self.deleteLater()

    def _press_escape(self):
        """模拟按下 ESC 键或通过 JS 关闭预览"""
        my_id = getattr(self, "_dialog_id", "unknown")
        my_addr = hex(id(self))

        # 始终计划一个极其激进的直接关闭兜底，以防所有模拟手段都失效
        QTimer.singleShot(100, lambda: self._safe_close_check(my_id, my_addr))

        try:
            # 1. 如果是 Web 模式，且不是空白页，优先通过 JS 调用 PhotoSwipe 的关闭方法
            is_blank = False
            if self.use_web and self.web_view:
                url = self.web_view.url().toString()
                if url == "about:blank" or not url:
                    is_blank = True

            if self.use_web and self.web_view and self.web_view.page() and not is_blank:
                # 直接设置 title 为 close，触发 _on_web_title_changed
                js_code = "document.title = 'action:close';"
                self.web_view.page().runJavaScript(js_code)
                return

            # 2. 兜底逻辑：向各个可能的部件发送 ESC 按键事件，或者直接关闭
            try:
                fw = QApplication.focusWidget()
            except Exception:
                fw = None

            candidates = []
            candidates.extend([fw, self])
            if hasattr(self, "scroll_area") and self.scroll_area:
                candidates.append(self.scroll_area)
                if self.scroll_area.viewport():
                    candidates.append(self.scroll_area.viewport())

            if hasattr(self, "web_view") and self.web_view:
                candidates.append(self.web_view)
                if self.web_view.focusProxy():
                    candidates.append(self.web_view.focusProxy())

            if hasattr(self, "preview_label") and self.preview_label:
                candidates.append(self.preview_label)

            sent = set()
            for obj in candidates:
                if obj and id(obj) not in sent:
                    sent.add(id(obj))
                    press = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
                    release = QKeyEvent(QEvent.KeyRelease, Qt.Key_Escape, Qt.NoModifier)
                    QApplication.sendEvent(obj, press)
                    QApplication.sendEvent(obj, release)
        except Exception:
            # 最后的最后，直接关闭
            self.close()

    def _safe_close_check(self, original_id, original_addr):
        """延时检查并确保窗口关闭"""
        is_destroyed = getattr(self, "_is_fully_destroyed", False)

        if not is_destroyed:
            self.close()

    def _copy_image(self):
        """复制图片"""
        if not self.valid_img_path:
            return
        if self.parent_window:
            self.parent_window.sig_copy_image.emit(self.valid_img_path)

    def _move_image(self):
        """移动图片"""
        if not self.valid_img_path:
            return
        if self.parent_window:
            self.parent_window.sig_move_image.emit(self.valid_img_path)
            # 移动后通过模拟 ESC 关闭预览
            self._press_escape()

    def _delete_image(self):
        """删除图片"""
        if not self.valid_img_path:
            return
        if self.parent_window:
            self.parent_window.sig_delete_image.emit(self.valid_img_path)
            # 删除后通过模拟 ESC 关闭预览
            self._press_escape()

    def _open_in_explorer(self):
        """在资源管理器中选中当前文件"""
        if not self.valid_img_path:
            return

        try:
            path = os.path.abspath(self.valid_img_path)
            if sys.platform == "win32":
                subprocess.run(
                    ["explorer", "/select,", path],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", path])
            else:
                subprocess.run(["xdg-open", os.path.dirname(path)])
        except Exception as e:
            pass

    def _toggle_play(self):
        self.is_playing = not self.is_playing
        t = TRANSLATIONS[self.lang]
        if self.is_playing:
            self.play_timer.start()
            self.btn_play.setText("⏸")
            self.btn_play.setToolTip(t["pause_tooltip"])
        else:
            self.play_timer.stop()
            self.btn_play.setText("▶")
            self.btn_play.setToolTip(t["play_tooltip"])

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
                self.preview_label.setText(t["invalid_image_path"])
                return

            # 保存规范化路径到当前实例
            self.valid_img_path = path

            # 显示加载状态
            t = TRANSLATIONS[self.lang]
            self.preview_label.setText(t["loading_original"])
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
            pass

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
            pass

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
            pass

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

        except Exception as e:
            pass

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
            QMessageBox.warning(self, t["load_error"], t["preview_load_fail"])

        self.is_web_loaded = True
        theme_info = THEME_COLORS.get(config.CURRENT_THEME_COLOR, THEME_COLORS["blue"])
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
                    pass

            # Add default zoom parameter (1.00x) to fix magnifier display
            js_code = f"if(window.openImage) openImage('{js_path}', {w}, {h}, {thumb_rect_json}, 1.0);"
            self.web_view.page().runJavaScript(js_code)

    def _on_web_title_changed(self, title):
        # 处理旋转请求
        if title.startswith("rotate:left:") or title.startswith("rotate:right:"):
            try:
                direction = "left" if title.startswith("rotate:left:") else "right"
                print(f"DEBUG: preview web rotate title={title}", flush=True)
                prefix_len = (
                    len("rotate:left:") if direction == "left" else len("rotate:right:")
                )
                content = title[prefix_len:]
                parts = content.split("|")
                path = parts[0]

                # 将 URL 转换为本地路径
                if path.startswith("file:///"):
                    path = path[8:]  # 移除 file:///
                    # Windows 上可能需要处理编码
                    from urllib.parse import unquote

                    path = unquote(path)

                if os.path.exists(path):
                    if self.parent_window and hasattr(
                        self.parent_window, "_rotate_image"
                    ):
                        print(f"DEBUG: preview web rotate path={path} id={self._dialog_id}", flush=True)
                        self.parent_window._rotate_image(
                            path, direction, exclude_id=self._dialog_id
                        )
                    print("DEBUG: preview web rotate closing", flush=True)
                    self._press_escape()
                    QTimer.singleShot(120, self._force_close)
            except Exception:
                pass
            return

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
        except Exception:
            pass
