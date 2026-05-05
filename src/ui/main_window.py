import sys
import os
import shutil
import json
import time
import unicodedata
import traceback
import send2trash
import ctypes
import subprocess
from urllib.parse import unquote
from PIL import Image, ImageOps, ExifTags

from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QStatusBar,
    QMessageBox,
    QFileDialog,
    QAction,
    QApplication,
    QSplitter,
    QTreeView,
    QToolTip,
)
from PyQt5.QtCore import (
    Qt,
    QTimer,
    QSettings,
    QThreadPool,
    QUrl,
    QPoint,
    QSize,
    QModelIndex,
    QDir,
    QStorageInfo,
)
from PyQt5.QtGui import (
    QIcon,
    QFont,
    QFontDatabase,
    QPixmap,
    QDesktopServices,
    QStandardItemModel,
    QStandardItem,
    QColor,
    QPalette,
)

# Project imports
from src.core.config import (
    APP_COMPANY,
    APP_NAME,
    THEME_COLORS,
    TRANSLATIONS,
    CURRENT_THEME_COLOR,
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT,
    MIN_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    MAX_THREADS,
    MAX_HISTORY_DIRS,
    get_current_theme_color,
    set_current_theme_color,
)
from src.utils.common import (
    resource_path,
    _normalize_lang_code,
    _detect_system_lang_code,
    safe_path,
)
from src.utils.system import fix_chinese_path
from src.utils.icons import (
    get_skin_icon,
    get_help_icon,
    get_search_btn_icon,
    get_lang_icon,
    get_computer_icon,
    get_pin_icon,
    get_history_icon,
    get_folder_icon,
    get_delete_icon,
    get_add_icon,
)
from src.ui.menu import Win11Menu
from src.ui.widgets import (
    HoverButton,
    LanguageComboBox,
    CustomSplitter,
    HTMLDelegate,
    ClickableLabel,
    FloatingSearchBox,
)
from src.ui.tree import TreeStyle
from src.ui.preview import CustomWebEngineView, WEBENGINE_AVAILABLE
from src.database.manager import db_manager as g_metadata_cache
from src.workers.scanner import ScanWorker


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
            set_current_theme_color(saved_theme)

        saved_lang = self.settings.value("language", "", type=str)
        self.lang = (
            _normalize_lang_code(saved_lang)
            if saved_lang
            else _detect_system_lang_code(TRANSLATIONS)
        )
        if self.lang not in TRANSLATIONS:
            self.lang = _detect_system_lang_code(TRANSLATIONS)
        t = TRANSLATIONS.get(self.lang, TRANSLATIONS["zh"])

        # Determine if running in headless/offscreen and thus WebEngine should be disabled
        self._headless = (
            os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"
            or os.environ.get("QT_OPENGL", "").lower() == "software"
        )
        self.setWindowTitle(t["app_title"])
        self.setWindowIcon(QIcon(resource_path("resources/icon.png")))

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

        # 使用说明按钮 (移到第一个位置)
        self.help_btn = HoverButton(get_help_icon)
        self.help_btn.setFixedSize(30, 30)
        self.help_btn.setToolTip(t["use_guide"])
        self.help_btn.setCursor(Qt.PointingHandCursor)
        self.help_btn.clicked.connect(self._on_help_clicked)
        toolbar_layout.addWidget(self.help_btn)

        # 皮肤切换按钮
        self.skin_btn = HoverButton(get_skin_icon)
        self.skin_btn.setFixedSize(30, 30)
        self.skin_btn.setToolTip(t.get("theme_skin", "皮肤颜色"))
        self.skin_btn.setCursor(Qt.PointingHandCursor)
        self.skin_btn.clicked.connect(self._on_skin_clicked)
        toolbar_layout.addWidget(self.skin_btn)

        # 语言切换下拉框
        self.lang_combo = LanguageComboBox()
        self.lang_combo.setObjectName("langCombo")
        self.lang_combo.setFixedSize(150, 30)  # 增加宽度以显示语言名称
        self.lang_combo.setCursor(Qt.PointingHandCursor)
        self.lang_combo.setFocusPolicy(Qt.NoFocus)
        self.lang_combo.currentIndexChanged.connect(self._on_language_combo_changed)
        toolbar_layout.addWidget(self.lang_combo)

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

        # 右侧瀑布流区域 (WebEngine)
        if WEBENGINE_AVAILABLE and not self._headless:
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

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 扫描模式标签（最左侧）
        t = TRANSLATIONS[self.lang]
        self.scan_mode_label = ClickableLabel(t["scan_mode_single"])
        self.scan_mode_label.setToolTip(
            t["scan_mode_tooltip"].format(t["scan_mode_single"])
        )
        self.scan_mode_label.setStyleSheet("padding: 0 10px;")
        self.scan_mode_label.clicked.connect(self._toggle_scan_mode)
        self.status_bar.addWidget(self.scan_mode_label)

        self.progress_label = QLabel(t["ready"])
        self.count_label = QLabel(t["image_count"].format(0, 0))
        self.status_bar.addWidget(self.progress_label)

        self.image_count = 0  # 记录当前图片总数
        self.original_img_data = []  # 原始图片数据（用于过滤）
        self.current_img_data = []  # 当前图片数据（过滤后）
        self.current_sort_mode = "name_asc"  # 当前排序模式
        self.current_layout_mode = "vertical"  # 当前布局模式

        t = TRANSLATIONS[self.lang]
        self.current_format_filter = t["all_formats"]
        self.current_size_filter = t["all_sizes"]
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
        available = [
            c for c in TRANSLATIONS.keys() if isinstance(TRANSLATIONS.get(c), dict)
        ]
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

            # 添加项目时同时显示语言名称
            self.lang_combo.addItem(lang_icon, name, code)
            i = self.lang_combo.count() - 1
            self.lang_combo.setItemData(i, name, Qt.ToolTipRole)

        idx = self.lang_combo.findData(self.lang)
        if idx < 0:
            self.lang = _detect_system_lang_code(TRANSLATIONS)
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
        self.setWindowTitle(t["app_title"])

        # 工具栏
        if hasattr(self, "floating_search"):
            self.floating_search.input.setPlaceholderText(t["search_placeholder"])

        # 扫描模式和工具提示
        mode_text = (
            t["scan_mode_multi"] if self.is_recursive_mode else t["scan_mode_single"]
        )
        self.scan_mode_label.setText(mode_text)
        self.scan_mode_label.setToolTip(t["scan_mode_tooltip"].format(mode_text))

        if hasattr(self, "lang_combo"):
            self.lang_combo.setToolTip(t["lang_tooltip"])

        self.help_btn.setToolTip(t["use_guide"])
        self.help_btn.setIcon(get_help_icon(self.is_dark_theme))

        # 格式和尺寸筛选文本更新
        self.current_format_filter = t["all_formats"]
        self.current_size_filter = t["all_sizes"]

        # 状态栏
        if not self.is_scanning:
            self.progress_label.setText(t["ready"])

        # 更新目录树根节点文本
        self.computer_item.setText(t["this_pc"])
        self.favorites_item.setText(t["favorites"])
        self.history_item.setText(t["history"])

        # 更新 WebEngineView 语言但不重新加载页面（修复：切换语言时不清空瀑布流）
        if self.web_view:
            self.web_view.lang = self.lang
            # 通过 JavaScript 动态更新语言，而不是重新加载页面
            self._send_web_language_pack()

        # 更新 Splitter 语言
        if self.splitter:
            self.splitter.lang = self.lang

        # 更新树代理语言
        if hasattr(self, "tree_delegate"):
            self.tree_delegate.lang = self.lang

    def _send_exif_info(self, path):
        """读取 EXIF 并发送给 Web（性能优化：使用数据库缓存加速）"""
        try:
            # 1. 基本文件信息
            info = {}
            info["filename"] = os.path.basename(path)
            stat = os.stat(path)
            size_mb = stat.st_size / (1024 * 1024)
            info["filesize"] = f"{size_mb:.2f} MB"
            info["created"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(stat.st_ctime)
            )
            info["modified"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)
            )

            # 性能优化：先尝试从缓存获取 EXIF 信息
            cached_exif = g_metadata_cache.get_exif_cache(path, stat.st_mtime)
            if cached_exif:
                info.update(cached_exif)
                info["from_cache"] = True
            else:
                # 2. 图片尺寸和 EXIF 数据
                try:
                    with Image.open(path) as img:
                        info["width"] = img.width
                        info["height"] = img.height
                        info["format"] = img.format

                        # 3. EXIF 数据
                        exif_data = img._getexif()
                        if exif_data:
                            for tag, value in exif_data.items():
                                tag_name = ExifTags.TAGS.get(tag, tag)
                                if tag_name == "Make":
                                    info["camera_make"] = str(value)
                                elif tag_name == "Model":
                                    info["camera_model"] = str(value)
                                elif tag_name == "DateTimeOriginal":
                                    info["capture_time"] = str(value)
                                elif tag_name == "ISOSpeedRatings":
                                    info["iso"] = str(value)
                                elif tag_name == "FNumber":
                                    info["aperture"] = f"f/{float(value):.1f}"
                                elif tag_name == "ExposureTime":
                                    info["exposure"] = f"{value}s"
                                elif tag_name == "FocalLength":
                                    info["focal_length"] = f"{float(value):.1f}mm"
                                elif tag_name == "LensModel":
                                    info["lens"] = str(value)

                    # 性能优化：保存到缓存
                    g_metadata_cache.save_exif_cache(path, info, stat.st_mtime)
                    info["from_cache"] = False
                except Exception:
                    pass

            # 发送给 JS
            # 需要转义 JSON 中的引号等
            json_str = json.dumps(info).replace("\\", "\\\\").replace("'", "\\'")
            self.web_view.page().runJavaScript(
                f"if (typeof showExifInfo === 'function') {{ showExifInfo('{json_str}'); }}"
            )

        except Exception:
            pass

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

            # 使用预先计算的文件名（小写）
            filename_lower = img.get("filename_lower")
            if filename_lower is None:
                filename_lower = os.path.basename(path).lower()
                img["filename_lower"] = filename_lower

            # 1. 搜索文件名
            if search_text and search_text not in filename_lower:
                continue

            # 2. 格式筛选
            if format_filter != t["all_formats"]:
                ext = os.path.splitext(filename_lower)[1].lower().replace(".", "")
                if format_filter == "RAW":
                    if ext not in ["arw", "cr2", "cr3", "nef", "dng", "raf", "orf"]:
                        continue
                elif format_filter.lower() != ext:
                    continue

            # 3. 尺寸筛选
            if size_filter != t["all_sizes"]:
                try:
                    # 优先使用缓存的 size (ScanWorker 已经提供了 size)
                    size = img.get("size")
                    if size is None:
                        size = os.path.getsize(path)
                        img["size"] = size

                    if size_filter == t["large_img"]:
                        if size <= 1024 * 1024:
                            continue
                    elif size_filter == t["medium_img"]:
                        if size < 100 * 1024 or size > 1024 * 1024:
                            continue
                    elif size_filter == t["small_img"]:
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
                super().keyPressEvent(event)
                return

            current_time = time.time() * 1000  # 毫秒
            # 增加响应时间范围至 500ms
            if current_time - self.last_ctrl_press_time < 500 and self.last_ctrl_press_time > 0:
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
                self.last_ctrl_press_time = 0  # 重置
                event.accept()  # 标记已处理
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
            QMessageBox.information(
                self, t["info"], t["help_not_found"].format(help_path)
            )

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
                # 检查是否有打开的预览窗口，如果有，优先关闭它
                if (
                    hasattr(self, "active_preview_dialog")
                    and self.active_preview_dialog
                ):
                    self.active_preview_dialog.close()
                    return

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

                    full_path = self._normalize_path_from_web(content)
                    if os.path.exists(full_path):
                        self._send_exif_info(full_path)
                except Exception:
                    pass
                return

            # 处理旋转请求 (rotate:left:path|index|timestamp 或 rotate:right:path|index|timestamp)
            if title.startswith("rotate:left:") or title.startswith("rotate:right:"):
                try:
                    direction = "left" if title.startswith("rotate:left:") else "right"
                    content = title[
                        len("rotate:left:")
                        if direction == "left"
                        else len("rotate:right:") :
                    ]
                    parts = content.split("|")
                    path = parts[0]
                    full_path = self._normalize_path_from_web(path)
                    if os.path.exists(full_path):
                        self._rotate_image(full_path, direction)
                        self._close_photoswipe_overlay()
                        # 关闭预览窗口
                        if (
                            hasattr(self, "active_preview_dialog")
                            and self.active_preview_dialog
                        ):
                            dialog = self.active_preview_dialog
                            try:
                                if hasattr(dialog, "_force_close"):
                                    dialog._force_close()
                                else:
                                    dialog.close()
                                QTimer.singleShot(120, dialog.close)
                            finally:
                                self.active_preview_dialog = None
                except Exception:
                    pass
                return

            # 处理打开资源管理器请求 (open:path|index|timestamp)
            if title.startswith("open:"):
                try:
                    content = title[5:]
                    parts = content.split("|")
                    path = parts[0]
                    full_path = self._normalize_path_from_web(path)
                    if os.path.exists(full_path):
                        self._open_in_explorer(full_path)
                except Exception:
                    pass
                return

            # 处理复制请求 (copy:path|index|timestamp)
            if title.startswith("copy:"):
                try:
                    content = title[5:]
                    parts = content.split("|")
                    path = parts[0]
                    full_path = self._normalize_path_from_web(path)
                    if os.path.exists(full_path):
                        self._copy_image(full_path)
                except Exception:
                    pass
                return

            # 处理移动请求 (move:path|index|timestamp)
            if title.startswith("move:"):
                try:
                    content = title[5:]
                    parts = content.split("|")
                    path = parts[0]
                    full_path = self._normalize_path_from_web(path)
                    if os.path.exists(full_path):
                        self._move_image(full_path)
                except Exception:
                    pass
                return

            # 处理删除请求 (delete:path|index|timestamp)
            if title.startswith("delete:"):
                try:
                    content = title[7:]
                    parts = content.split("|")
                    path = parts[0]
                    full_path = self._normalize_path_from_web(path)
                    if os.path.exists(full_path):
                        self._delete_image(full_path)
                except Exception:
                    pass
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
                            t["image_count"].format(display_idx, self.image_count)
                        )
                except Exception:
                    pass

            # 获取文件大小
            try:
                target_path = self._normalize_path_from_web(path)

                # 最终检查
                if os.path.exists(target_path) and os.path.isfile(target_path):
                    size_bytes = os.path.getsize(target_path)
                    size_mb = size_bytes / (1024 * 1024)
                    self.size_label.setText(f"{size_mb:.2f} MB")
                else:
                    self.size_label.setText("")
            except Exception:
                self.size_label.setText("")

        except BaseException:
            # 捕获所有异常，防止崩溃
            pass

    def _close_photoswipe_overlay(self):
        try:
            if hasattr(self, "web_view") and self.web_view and self.web_view.page():
                js_code = (
                    "(function(){"
                    "try{"
                    "if(window.closePhotoSwipe){return window.closePhotoSwipe();}"
                    "if(window.lightbox&&window.lightbox.pswp){window.lightbox.pswp.close();return 'closed_lightbox';}"
                    "if(window.pswpInstance){window.pswpInstance.close();return 'closed_instance';}"
                    "}catch(e){}"
                    "return 'no_instance';"
                    "})();"
                )
                self.web_view.page().runJavaScript(js_code)
        except Exception:
            pass

    def resizeEvent(self, event):
        """主窗口大小变化"""
        # 实时通知 Web 窗口宽度
        if hasattr(self, "web_view") and self.web_view:
            # 使用节流定时器通知宽度变化
            self._splitter_timer.start(60)

        # 暂停 Web 更新
        if hasattr(self, "web_view") and self.web_view.isVisible():
            self.web_view.setUpdatesEnabled(False)

            # 使用 Timer 延时恢复更新
            if not hasattr(self, "_resize_timer"):
                self._resize_timer = QTimer()
                self._resize_timer.setSingleShot(True)
                self._resize_timer.timeout.connect(self._resume_web_updates)

            self._resize_timer.start(150)  # 稍微延长恢复时间

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
            # 拖动期间暂停 Webview 更新
            if self.web_view.isVisible():
                self.web_view.setUpdatesEnabled(False)

                # 使用定时器节流通知 JS
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
            # 检查 settings 是否有效
            if settings.status() != QSettings.NoError:
                return False
            value = settings.value("AppsUseLightTheme", 1, type=int)
            # 检查 value 是否有效
            if value is None:
                return False
            return value == 0
        except Exception:
            return False

    def _toggle_theme(self):
        """切换主题"""
        self.is_dark_theme = not self.is_dark_theme
        self._apply_complete_theme()

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
            self.floating_search.icon_label.setPixmap(
                get_search_btn_icon(self.is_dark_theme).pixmap(50, 50)
            )

        # 图标着色配置 (暗黑模式下使用浅色图标)
        target_color = QColor("#E0E0E0") if self.is_dark_theme else None

        # 1. 更新此电脑图标
        t = TRANSLATIONS[self.lang]
        if hasattr(self, "computer_item"):
            icon = get_computer_icon(self.is_dark_theme)
            self.computer_item.setToolTip(
                t["theme_tooltip_dark"]
                if self.is_dark_theme
                else t["theme_tooltip_light"]
            )
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
            except Exception:
                pass

            # 设置 ToolTip 样式 (通过 QPalette 设置颜色,避免覆盖应用其他样式)
            palette = QApplication.instance().palette()
            palette.setColor(QPalette.ToolTipBase, QColor(45, 45, 45))
            palette.setColor(QPalette.ToolTipText, QColor(224, 224, 224))
            QApplication.setPalette(palette)

            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1e1e1e;
                    color: #e0e0e0;
                }
                QSplitter::handle {
                    background-color: #3d3d3d;
                    width: 32px;
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

            # 设置 ToolTip 样式 (通过 QPalette 设置颜色,避免覆盖应用其他样式)
            palette = QApplication.instance().palette()
            palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
            palette.setColor(QPalette.ToolTipText, QColor(33, 37, 41))
            QApplication.setPalette(palette)

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

        if self.web_view and self.is_web_loaded and self.web_view.page():
            self.web_view.page().runJavaScript(
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
        except Exception:
            self.favorites_dirs = []

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

        # 获取暗黑模式状态 (直接从属性获取比计算 palette 快)
        is_dark = self.is_dark_theme

        # 判断点击的是否是收藏/历史目录下的项目
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
                t["menu_remove_favorite"],
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
                t["menu_remove_history"],
                self,
            )
            remove_action.triggered.connect(lambda: self._remove_from_history(safe_dir))
            menu.addAction(remove_action)
        else:
            # 普通目录项：添加到收藏 (减少一次磁盘检查)
            add_action = QAction(
                get_add_icon(is_dark),
                t["menu_add_favorite"],
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
                t["confirm_clear"],
                t["clear_favorites_msg"],
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._clear_favorites()
        elif root_type == "root_history":
            t = TRANSLATIONS[self.lang]
            reply = QMessageBox.question(
                self,
                t["confirm_clear"],
                t["clear_history_msg"],
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
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
        self.computer_item = QStandardItem(computer_icon, t["this_pc"])
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
        self.computer_item.setToolTip(
            t["theme_tooltip_dark"] if self.is_dark_theme else t["theme_tooltip_light"]
        )
        self.file_model.appendRow(self.computer_item)

        # 加载驱动器
        self._load_drives()

        # 根节点：收藏目录 (采用 此电脑 结构)
        pin_icon = get_pin_icon(self.is_dark_theme)

        self.favorites_item = QStandardItem(pin_icon, t["favorites"])
        self.favorites_item.setData("root_favorites", Qt.UserRole)
        self.favorites_item.setEditable(False)
        # 使用相同的字体设置
        favorites_font = QFont(font)  # 复制已设置的字体
        self.favorites_item.setFont(favorites_font)  # 粗体 思源黑体
        self.file_model.appendRow(self.favorites_item)
        self._update_favorites_tree_ui(check_subdirs=False)

        # 根节点：历史目录 (采用 收藏目录 样式，时针图标)
        history_icon = get_history_icon(self.is_dark_theme)

        self.history_item = QStandardItem(history_icon, t["history"])
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
                item.appendRow(QStandardItem(t["loading"]))

            self.favorites_item.appendRow(item)

    def _update_history_tree_ui(self, check_subdirs=True):
        """更新历史目录树节点"""
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

            # 设置图标（时针）
            # 使用 HTML 灰色显示 (调整颜色为 #999999 以匹配上传图片效果)
            item.setText(dir_name)

            # Icon 依然是文件夹
            icon = get_folder_icon(self.is_dark_theme)
            item.setIcon(icon)

            # 检测是否有子文件夹
            if check_subdirs and self._has_subdirectories(dir_path):
                # 添加虚拟子节点，支持展开子目录
                t = TRANSLATIONS[self.lang]
                item.appendRow(QStandardItem(t["loading"]))

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
                    name = t["drive_local"]
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
            item.appendRow(QStandardItem(t["loading"]))
            self.computer_item.appendRow(item)

    def _on_tree_expanded(self, index):
        """树节点展开处理（懒加载）"""
        item = self.file_model.itemFromIndex(index)
        if not item:
            return

        # 检查是否已经加载过
        if item.data(Qt.UserRole + 1) is True:
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
        try:
            safe_p = safe_path(path)
            if not os.path.exists(safe_p) or not os.path.isdir(safe_p):
                return

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

            # 使用 os.scandir 提升性能
            with os.scandir(safe_p) as it:
                # 预先筛选并排序子目录
                entries = []
                for entry in it:
                    try:
                        if entry.is_dir():
                            entries.append(entry)
                    except (PermissionError, OSError):
                        continue

                entries.sort(key=lambda x: x.name.lower())

                for entry in entries:
                    item = QStandardItem(entry.name)
                    child_path = entry.path
                    item.setData(child_path, Qt.UserRole)
                    item.setEditable(False)

                    # 设置图标（文件夹）
                    item.setIcon(get_folder_icon(self.is_dark_theme))

                    # 根据所属区域决定是否预先添加虚拟节点
                    should_add_dummy = True
                    if is_favorites_or_history:
                        # 收藏/历史目录：只有当子目录确实包含内容时才添加虚拟节点
                        if not self._has_subdirectories(child_path):
                            should_add_dummy = False

                    if should_add_dummy:
                        # 预先添加虚拟节点，以便显示展开箭头
                        t = TRANSLATIONS[self.lang]
                        item.appendRow(QStandardItem(t["loading"]))

                    parent_item.appendRow(item)
        except Exception:
            pass

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
                            t["drive_root_msg"].format(clean_path)
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
            t = TRANSLATIONS[self.lang]
            QMessageBox.warning(
                self, t["error"], t["dir_click_fail"].format(str(e)[:50])
            )

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
                subprocess.Popen(
                    ["explorer", "/select,", file_path],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                # macOS/Linux fallback
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(file_path)))
        except Exception as e:
            t = TRANSLATIONS[self.lang]
            QMessageBox.warning(
                self, t["error"], t["open_explorer_fail"].format(str(e)[:50])
            )

    def _rotate_image(self, path, direction, exclude_id=None):
        """旋转图片并刷新界面"""
        try:
            # 规范化路径
            if not path or not os.path.exists(path):
                return

            path = unicodedata.normalize("NFC", path)
            if "?" in path:
                path = path.split("?")[0]
            path = os.path.normpath(path)

            # 0. 清理预览窗口，防止文件被占用
            try:
                from src.ui.preview import HighQualityImagePreviewDialog

                # 如果是从预览窗口触发的，排除该窗口自身，由它自己控制关闭流程
                HighQualityImagePreviewDialog.cleanup_all_instances(
                    exclude_id=exclude_id
                )
                QApplication.processEvents()
            except Exception:
                pass
            try:
                closed_count = 0
                for w in QApplication.topLevelWidgets():
                    if w.__class__.__name__ == "HighQualityImagePreviewDialog":
                        my_id = getattr(w, "_dialog_id", None)
                        if exclude_id and my_id and my_id == exclude_id:
                            continue
                        if hasattr(w, "_force_close"):
                            w._force_close()
                        else:
                            w.close()
                        closed_count += 1
                QApplication.processEvents()
            except Exception:
                pass
            if exclude_id is None:
                self._close_photoswipe_overlay()

            # 1. 旋转并保存图片
            try:
                with Image.open(path) as img:
                    # 保持 EXIF 方向
                    img = ImageOps.exif_transpose(img)
                    # 旋转
                    angle = 90 if direction == "left" else -90
                    img = img.rotate(angle, expand=True)
                    # 保存
                    img.save(path)
                    new_w, new_h = img.size
            except Exception as save_err:
                raise save_err

            # 2. 更新内部缓存数据
            matched_item = None

            # 移除 Windows 长路径前缀以便匹配前端存储的 file:/// URL 格式
            normalized_path = path
            if sys.platform == "win32" and path.startswith("\\\\?\\"):
                normalized_path = path[4:]

            # 更新 current_img_data（存储的是 file:/// URL 格式）
            for item in self.current_img_data:
                item_path = item.get("path", "")
                # 移除 item_path 中的 \\?\ 前缀（如果有）
                if sys.platform == "win32" and item_path.startswith("\\\\?\\"):
                    item_path = item_path[4:]
                if self._paths_are_equal(item_path, normalized_path):
                    item["w"] = new_w
                    item["h"] = new_h
                    matched_item = item
                    break

            # 更新 original_img_data
            for item in self.original_img_data:
                item_path = item.get("path", "")
                if sys.platform == "win32" and item_path.startswith("\\\\?\\"):
                    item_path = item_path[4:]
                if self._paths_are_equal(item_path, normalized_path):
                    item["w"] = new_w
                    item["h"] = new_h
                    break

            # 3. 通知前端刷新瀑布流中的该图片
            if matched_item and self.web_view and self.web_view.page():
                # matched_item["path"] 需要转换为 file:/// URL 格式
                item_path = matched_item.get("path", "")
                # 移除 Windows 长路径前缀
                if sys.platform == "win32" and item_path.startswith("\\\\?\\"):
                    item_path = item_path[4:]
                # 转换为 file:/// URL
                url = QUrl.fromLocalFile(item_path)
                path_str = url.toString()

                timestamp = int(time.time())
                path_json = json.dumps(path_str)

                # 调用前端 imageRotated 函数
                js_code = f"if (typeof imageRotated === 'function') {{ imageRotated({path_json}, {new_w}, {new_h}, {timestamp}); }}"
                self.web_view.page().runJavaScript(js_code)

        except Exception as e:
            t = TRANSLATIONS[self.lang]
            QMessageBox.warning(self, t["error"], t["rotate_fail"].format(e))

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
            mode_text = t["scan_mode_multi"] if is_recursive else t["scan_mode_single"]
            self.status_bar.showMessage(t["switch_mode_done"].format(mode_text), 2000)

            # 更新状态栏左侧标签和工具栏按钮图标
            tooltip = t["scan_mode_tooltip"].format(mode_text)
            self.scan_mode_label.setText(mode_text)
            self.scan_mode_label.setToolTip(tooltip)

            # 更新工具栏图标
            self._apply_complete_theme()

            # 如果当前有选中的目录，刷新
            if self.current_dir and not self.is_scanning:
                self._scan_images(self.current_dir)

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
                path = item["path"]
                # 预先计算并缓存各种属性，优化后续排序和过滤性能
                if "web_path" not in item:
                    item["web_path"] = self._normalize_path_for_web(path)
                if "path_lower" not in item:
                    item["path_lower"] = path.lower()
                if "filename_lower" not in item:
                    item["filename_lower"] = os.path.basename(path).lower()

                # 构建前端对象
                clean_path = item["web_path"]
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
            self.count_label.setText(t["image_count"].format(1, count))
        else:
            self.count_label.setText(t["image_count"].format(0, 0))

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
        self.progress_label.setText(t["loading_count"].format(len(img_data)))

        # 2. 检查是否需要应用筛选
        search_text = self.current_search_text.strip()
        format_filter = self.current_format_filter
        size_filter = self.current_size_filter
        filters_active = (
            search_text
            or format_filter != t["all_formats"]
            or size_filter != t["all_sizes"]
        )

        if filters_active:
            # 如果有筛选，直接调用筛选逻辑，它会更新视图
            self._on_search_filter_changed()
        else:
            # 只有在数据为空，或者排序模式不是默认时，才需要全量刷新
            # 如果是默认排序，流式加载已经显示了正确顺序的图片
            should_full_refresh = False

            if not img_data:
                should_full_refresh = True
            elif (
                self.current_sort_mode != "name"
                and self.current_sort_mode != "name_asc"
            ):
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
                self.progress_label.setText(t["scan_done"].format(count))
                if count > 0:
                    self.count_label.setText(t["image_count"].format(1, count))

        # 尝试添加到历史记录
        if img_data and len(img_data) > 0:
            # 取第一张图所在的目录作为记录路径
            first_path = img_data[0]["path"]
            dir_path = os.path.dirname(first_path)
            self._add_to_history(dir_path)

    def _normalize_path_for_web(self, path):
        """为 Web 端规范化路径，转换为标准 file:/// URL"""
        if not path:
            return ""

        # 如果已经是 file:// 开头，直接返回（可能已经规范化过）
        if path.startswith("file:///"):
            return path

        # 移除 Windows 长路径前缀，因为 QUrl 不支持它
        if sys.platform == "win32" and path.startswith("\\\\?\\"):
            path = path[4:]

        # 使用 QUrl 转换为标准 file:// URL
        # 这会自动处理编码、斜杠等，是最可靠的方式
        url = QUrl.fromLocalFile(path)
        return url.toString()

    def _normalize_path_from_web(self, path):
        """从 Web 端接收路径并规范化为本地路径"""
        if not path:
            return ""

        # 处理可能的 URL 参数
        if "?" in path:
            path = path.split("?")[0]

        # 优先使用 QUrl 转换
        if path.startswith("file://") or "://" in path:
            return QUrl(path).toLocalFile()

        # 兜底处理：移除 file:/// 前缀
        if path.startswith("file:///"):
            path = path[8:]

        # Windows 路径处理
        if sys.platform == "win32":
            path = path.replace("/", "\\")

        # URL 解码
        path = unquote(path)

        return safe_path(path)

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
        target_dir = QFileDialog.getExistingDirectory(
            self, t["copy_target_title"], self.current_dir or ""
        )
        if not target_dir:
            return

        try:
            filename = os.path.basename(path)
            dest_path = os.path.join(target_dir, filename)

            # 检查同名文件
            if os.path.exists(dest_path):
                reply = QMessageBox.question(
                    self,
                    t["overwrite_title"],
                    t["overwrite_msg"].format(filename),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    return

            shutil.copy2(path, dest_path)
            QMessageBox.information(self, t["success"], t["copy_success"])
        except Exception as e:
            QMessageBox.critical(self, t["error"], t["copy_fail"].format(e))

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
        target_dir = QFileDialog.getExistingDirectory(
            self, t["move_target_title"], self.current_dir or ""
        )
        if not target_dir:
            return

        try:
            filename = os.path.basename(path)
            dest_path = os.path.join(target_dir, filename)

            # 检查同名文件
            if os.path.exists(dest_path):
                reply = QMessageBox.question(
                    self,
                    t["overwrite_title"],
                    t["overwrite_msg"].format(filename),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    return

            shutil.move(path, dest_path)

            # 更新显示
            full_path = safe_path(path)
            self.current_img_data = [
                img
                for img in self.current_img_data
                if not self._paths_are_equal(img["path"], full_path)
            ]

            # 同时更新原始数据
            self.original_img_data = [
                img
                for img in self.original_img_data
                if not self._paths_are_equal(img["path"], full_path)
            ]

            self._update_web_view_images()

            QMessageBox.information(self, t["success"], t["move_success"])
        except Exception as e:
            QMessageBox.critical(self, t["error"], t["move_fail"].format(e))

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
            t["delete_confirm_title"],
            t["delete_confirm_msg"].format(os.path.basename(path)),
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
                    self.original_img_data = [
                        img
                        for img in self.original_img_data
                        if not self._paths_are_equal(img["path"], full_path)
                    ]

                    new_count = len(self.current_img_data)

                    # 刷新显示
                    self._update_web_view_images()
                else:
                    QMessageBox.warning(self, t["error"], t["file_not_exist"])
                    # 即使文件不存在，也尝试从列表中移除
                    self.current_img_data = [
                        img
                        for img in self.current_img_data
                        if not self._paths_are_equal(img["path"], full_path)
                    ]
                    # 同时从原始数据中移除
                    self.original_img_data = [
                        img
                        for img in self.original_img_data
                        if not self._paths_are_equal(img["path"], full_path)
                    ]
                    self._update_web_view_images()

            except Exception as e:
                QMessageBox.critical(self, t["error"], t["delete_fail"].format(e))

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
                self.current_img_data.sort(
                    key=lambda x: x.get("path_lower", x["path"].lower())
                )
            elif self.current_sort_mode == "name_desc":
                self.current_img_data.sort(
                    key=lambda x: x.get("path_lower", x["path"].lower()), reverse=True
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
                # 使用预先规范化并缓存的路径，大幅提升大数据量下的更新速度
                clean_path = item.get("web_path")
                if clean_path is None:
                    clean_path = self._normalize_path_for_web(item["path"])
                    item["web_path"] = clean_path

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
            if self.web_view and self.web_view.page():
                self.web_view.page().runJavaScript(
                    f"if (typeof updateImages === 'function') {{ updateImages({json_str}); }}"
                )

            count = len(self.current_img_data)
            self.image_count = count
            t = TRANSLATIONS[self.lang]
            self.progress_label.setText(t["scan_done"].format(count))
            if count > 0:
                self.count_label.setText(t["image_count"].format(1, count))
            else:
                self.count_label.setText(t["image_count"].format(0, 0))
        except Exception as e:
            traceback.print_exc()

    def _on_scroll(self, value):
        pass

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
            """)
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
            """)
            # 更新特定标签颜色
            if hasattr(self, "size_label"):
                self.size_label.setStyleSheet("padding: 0 10px; color: #000000;")

    def _set_toolbar_style(self):
        """设置工具栏样式"""

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
                    padding-left: 4px;
                    padding-right: 20px;
                }
                QComboBox#langCombo:hover {
                    background-color: rgba(255, 255, 255, 20);
                }
                QComboBox#langCombo::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: right center;
                    width: 16px;
                    border: none;
                }
                QComboBox#langCombo::down-arrow {
                    image: none;
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
                    padding-left: 4px;
                    padding-right: 20px;
                }
                QComboBox#langCombo:hover {
                    background-color: rgba(0, 0, 0, 10);
                }
                QComboBox#langCombo::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: right center;
                    width: 16px;
                    border: none;
                }
                QComboBox#langCombo::down-arrow {
                    image: none;
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
        checked_bg = (
            "rgba(255, 255, 255, 25)" if self.is_dark_theme else "rgba(0, 0, 0, 15)"
        )
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
            ("green", t.get("theme_green", "绿色")),
        ]

        for theme_id, theme_name in skins:
            action = QAction("", menu)
            # 为每个皮肤选项创建对应颜色的图标
            from src.utils.lucide_icons import _create_colored_icon
            theme_info = THEME_COLORS.get(theme_id, THEME_COLORS["blue"])
            icon = _create_colored_icon(
                "shirt",
                theme_info["normal"],
                None,
                24, False
            )
            action.setIcon(icon)
            action.setToolTip(theme_name)

            # 标记当前选中
            if CURRENT_THEME_COLOR == theme_id:
                action.setCheckable(True)
                action.setChecked(True)

            # 使用闭包绑定参数
            action.triggered.connect(
                lambda checked, tid=theme_id: self._on_skin_changed(tid)
            )
            menu.addAction(action)

        # 在按钮下方显示菜单
        menu.exec_(self.skin_btn.mapToGlobal(QPoint(0, self.skin_btn.height())))

    def _on_skin_changed(self, theme_id):
        """处理皮肤切换"""
        global CURRENT_THEME_COLOR
        if CURRENT_THEME_COLOR == theme_id:
            return

        CURRENT_THEME_COLOR = theme_id
        set_current_theme_color(theme_id)
        self.settings.setValue("theme_color", theme_id)

        # 清空图标缓存，因为皮肤颜色变了
        from src.utils.lucide_icons import _icon_cache

        _icon_cache.clear()

        # 刷新所有图标
        self._refresh_all_icons()

        # 同步更新 Web 端皮肤颜色
        theme_info = THEME_COLORS.get(theme_id, THEME_COLORS["blue"])
        skin_color = theme_info["normal"]

        if hasattr(self, "web_view") and self.web_view:
            self.web_view.page().runJavaScript(
                f"if (typeof setSkinColor === 'function') {{ setSkinColor('{skin_color}'); }}"
            )

    def _refresh_all_icons(self):
        """刷新 UI 中所有受皮肤颜色影响的图标"""
        # 1. 顶部工具栏按钮
        if hasattr(self, "skin_btn"):
            self.skin_btn.update_icon()
        if hasattr(self, "lang_combo"):
            self.lang_combo.update_icon()
        if hasattr(self, "help_btn"):
            self.help_btn.update_icon()

        # 2. 树状图图标（包含根节点与所有子节点）
        self._refresh_tree_icons()

        # 3. 分割窗口中的图标（排序、布局、操作按钮）
        if hasattr(self, "splitter"):
            self.splitter.refresh_icons()

        # 4. 树状图 Delegate 中的图标（扫描模式、清除按钮等）
        if hasattr(self, "tree_view"):
            self.tree_view.viewport().repaint()

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
        
        # 发射信号通知视图更新
        self.file_model.dataChanged.emit(
            self.file_model.index(0, 0),
            self.file_model.index(self.file_model.rowCount() - 1, self.file_model.columnCount() - 1)
        )
