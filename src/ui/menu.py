import ctypes
from PyQt5.QtWidgets import QMenu, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QIcon, QColor
from src.core.config import get_current_theme_color

class Win11Menu(QMenu):
    _style_cache = {}

    def __init__(self, title="", parent=None, is_dark=True):
        super().__init__(title, parent)
        self.is_dark = is_dark
        self._setup_menu()

    def _setup_menu(self):
        # 设置窗口标志以支持圆角和阴影
        # 使用 Qt.Popup 标志，它是 QMenu 的默认行为，但在某些环境下需要显式设置
        self.setWindowFlags(self.windowFlags() | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_StyledBackground)
        
        # 应用样式
        self.apply_style()

    def showEvent(self, event):
        super().showEvent(event)
        # 尝试调用系统 API 开启 Win11 原生圆角和阴影
        try:
            hwnd = int(self.winId())
            
            # 设置暗色模式属性，帮助 DWM 决定阴影风格
            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            is_dark = ctypes.c_int(1 if self.is_dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(is_dark),
                ctypes.sizeof(is_dark)
            )

            # DWMWA_WINDOW_CORNER_PREFERENCE = 33
            # DWMWCP_ROUND = 2 (圆角)
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            preference = ctypes.c_int(2) 
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 
                DWMWA_WINDOW_CORNER_PREFERENCE, 
                ctypes.byref(preference), 
                ctypes.sizeof(preference)
            )
            
            # 移除可能存在的系统边框，确保圆角生效
            # DWMWA_BORDER_COLOR = 34
            # color = 0xFFFFFFFE (NONE)
            DWMWA_BORDER_COLOR = 34
            none_color = ctypes.c_int(0xFFFFFFFE)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_BORDER_COLOR,
                ctypes.byref(none_color),
                ctypes.sizeof(none_color)
            )
        except Exception:
            pass

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
        # 获取当前主题色
        theme_color = get_current_theme_color().name()
        
        # 缓存键包含主题色和暗色模式
        cache_key = (self.is_dark, theme_color)
        # 使用缓存以提高性能
        if cache_key in Win11Menu._style_cache:
            self.setStyleSheet(Win11Menu._style_cache[cache_key])
            return

        if self.is_dark:
            bg_color = "rgba(45, 45, 45, 0.95)"
            text_color = "#FFFFFF"
            border_color = "rgba(255, 255, 255, 0.15)"
            hover_bg = "rgba(255, 255, 255, 0.1)"
            separator_color = "rgba(255, 255, 255, 0.12)"
        else:
            bg_color = "rgba(250, 250, 250, 0.98)"
            text_color = "#1A1A1A"
            border_color = "rgba(0, 0, 0, 0.1)"
            hover_bg = "rgba(0, 0, 0, 0.06)"
            separator_color = "rgba(0, 0, 0, 0.08)"

        style = f"""
            QMenu {{
                background-color: {bg_color} !important;
                color: {text_color} !important;
                border: 1px solid {border_color} !important;
                border-radius: 10px !important;
                padding: 6px 4px !important;
            }}
            QMenu::item {{
                padding: 8px 36px 8px 36px !important;
                border-radius: 5px !important;
                margin: 2px 4px !important;
                background-color: transparent !important;
            }}
            QMenu::item:selected {{
                background-color: {hover_bg} !important;
            }}
            QMenu::icon {{
                padding-left: 12px !important;
            }}
            QMenu::separator {{
                height: 1px !important;
                background: {separator_color} !important;
                margin: 6px 8px !important;
            }}
            QMenu::right-arrow {{
                width: 12px !important;
                height: 12px !important;
                padding-right: 12px !important;
            }}
        """
        Win11Menu._style_cache[cache_key] = style
        self.setStyleSheet(style)
