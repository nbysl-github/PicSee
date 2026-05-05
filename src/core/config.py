from PyQt5.QtGui import QColor
from src.utils.common import _load_all_language_packs

THEME_COLORS = {
    "blue": {"normal": "#3498db", "hover": "#2980b9"},
    "red": {"normal": "#e74c3c", "hover": "#c0392b"},
    "green": {"normal": "#2ecc71", "hover": "#27ae60"},
}

# Global state for current theme
CURRENT_THEME_COLOR = "blue"

def get_current_theme_color(is_hovered=False):
    """获取当前选中的皮肤颜色"""
    theme = THEME_COLORS.get(CURRENT_THEME_COLOR, THEME_COLORS["blue"])
    return QColor(theme["hover"] if is_hovered else theme["normal"])

def set_current_theme_color(color_name):
    global CURRENT_THEME_COLOR
    if color_name in THEME_COLORS:
        CURRENT_THEME_COLOR = color_name

TRANSLATIONS = _load_all_language_packs()
TRANSLATIONS.setdefault("zh", {})
TRANSLATIONS.setdefault("en", dict(TRANSLATIONS["zh"]))

# ===================== 核心配置 =====================
VERSION = "1.0.6"  # 版本标记
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
