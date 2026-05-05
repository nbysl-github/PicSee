"""
Lucide Icon System for PicSee
使用 Lucide SVG 图标替换原有的自定义图标
保持"皮肤色"主题效果
"""
import os
import sys
from PyQt5.QtGui import QPixmap, QIcon, QColor, QPainter
from PyQt5.QtCore import Qt, QByteArray
from PyQt5.QtSvg import QSvgRenderer

try:
    from lucide import lucide_icon
    LUCIDE_AVAILABLE = True
except ImportError:
    LUCIDE_AVAILABLE = False

from src.core.config import get_current_theme_color

# --- 图标缓存 ---
_icon_cache = {}


def _get_theme_key(is_hovered=False, secondary_color=None):
    """获取当前主题颜色的缓存键"""
    base_key = get_current_theme_color(is_hovered).name()
    if secondary_color:
        return f"{base_key}_{secondary_color}"
    return base_key


def _svg_to_pixmap(svg_content: str, size: int = 24, color: str = None) -> QPixmap:
    """
    将 SVG 字符串转换为 QPixmap
    
    Args:
        svg_content: SVG 字符串
        size: 图标尺寸
        color: 颜色字符串 (可选)
    
    Returns:
        QPixmap 对象
    """
    if not LUCIDE_AVAILABLE:
        return _fallback_pixmap(size, color)
    
    # 如果有颜色,更新 SVG 中的 stroke 属性
    if color:
        svg_content = svg_content.replace(
            'stroke="currentColor"', f'stroke="{color}"'
        )
    
    # 使用 QSvgRenderer 渲染 SVG
    renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
    
    if not renderer.isValid():
        return _fallback_pixmap(size, color)
    
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    
    return pixmap


def _fallback_pixmap(size: int, color: str = None) -> QPixmap:
    """降级方案:创建简单的占位图标"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    
    if color:
        painter = QPainter(pixmap)
        painter.setPen(QColor(color))
        painter.drawEllipse(0, 0, size, size)
        painter.end()
    
    return pixmap


def _create_colored_icon(svg_name: str, primary_color: str, secondary_color: str = None, 
                         size: int = 24, is_hovered: bool = False) -> QIcon:
    """
    创建带颜色的 Lucide 图标
    
    Args:
        svg_name: Lucide 图标名称
        primary_color: 主色 (皮肤色)
        secondary_color: 次要颜色 (可选)
        size: 图标尺寸
        is_hovered: 是否悬停状态
    
    Returns:
        QIcon 对象
    """
    if not LUCIDE_AVAILABLE:
        return QIcon()
    
    cache_key = (svg_name, primary_color, secondary_color, is_hovered)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]
    
    # 获取 SVG
    svg_content = lucide_icon(svg_name)
    
    if not svg_content:
        return QIcon()
    
    # 创建主图标 (皮肤色)
    primary_pixmap = _svg_to_pixmap(svg_content, size, primary_color)
    
    icon = QIcon(primary_pixmap)
    _icon_cache[cache_key] = icon
    return icon


# ==================== PicSee 图标函数 ====================


def get_sort_icon(is_dark=True, is_hovered=False):
    """排序图标 - 使用 ArrowUpDown (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    icon = _create_colored_icon(
        "arrow-up-down",
        theme_color.name() if is_hovered else ("#e0e0e0" if is_dark else "#333333"),
        theme_color.name(),
        24, is_hovered
    )
    return icon


def get_refresh_icon(is_dark=True, is_hovered=False):
    """刷新图标 - 使用 RefreshCw (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    icon = _create_colored_icon(
        "refresh-cw",
        theme_color.name() if is_hovered else ("#e0e0e0" if is_dark else "#333333"),
        theme_color.name(),
        24, is_hovered
    )
    return icon


def get_layout_icon(is_dark=True, is_hovered=False):
    """布局图标 - 使用 Grid3x3 (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    icon = _create_colored_icon(
        "grid-3x3",
        theme_color.name() if is_hovered else ("#e0e0e0" if is_dark else "#333333"),
        theme_color.name(),
        24, is_hovered
    )
    return icon


def get_delete_icon(is_dark=True, is_hovered=False):
    """删除图标 - 使用 Trash2 (Lucide) - 红色"""
    delete_color = "#ff4d4f"
    icon = _create_colored_icon(
        "trash-2",
        delete_color,
        None,
        24, is_hovered
    )
    return icon


def get_add_icon(is_dark=True, is_hovered=False):
    """添加图标 - 使用 CirclePlus (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    icon = _create_colored_icon(
        "circle-plus",
        theme_color.name() if is_hovered else ("#e0e0e0" if is_dark else "#333333"),
        theme_color.name(),
        24, is_hovered
    )
    return icon


def get_clear_icon(color_str="#e0e0e0", is_hovered=False):
    """清除图标 - 使用 Trash2 (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    icon = _create_colored_icon(
        "trash-2",
        theme_color.name() if is_hovered else color_str,
        theme_color.name(),
        24, is_hovered
    )
    return icon


def get_folder_icon(is_dark=True, is_hovered=False):
    """文件夹图标 - 使用 Folder (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    base_color = "#FFFFFF" if is_dark else "#000000"
    icon = _create_colored_icon(
        "folder",
        base_color,
        theme_color.name(),
        24, is_hovered
    )
    return icon


def get_computer_icon(is_dark=True):
    """此电脑图标 - 使用 Monitor (Lucide)"""
    theme_color = get_current_theme_color()
    icon = _create_colored_icon(
        "monitor",
        theme_color.name(),
        "#e0e0e0" if is_dark else "#333333",
        24, False
    )
    return icon


def get_pin_icon(is_dark=True):
    """收藏图标 - 使用 Pin (Lucide)"""
    theme_color = get_current_theme_color()
    icon = _create_colored_icon(
        "pin",
        theme_color.name(),
        "#e0e0e0" if is_dark else "#333333",
        24, False
    )
    return icon


def get_history_icon(is_dark=True):
    """历史图标 - 使用 Clock (Lucide)"""
    theme_color = get_current_theme_color()
    icon = _create_colored_icon(
        "clock",
        theme_color.name(),
        "#e0e0e0" if is_dark else "#333333",
        24, False
    )
    return icon


def get_rotate_icon(direction="left", is_dark=True, is_hovered=False):
    """旋转图标 - 使用 RotateCw 或 RotateCcw (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    svg_name = "rotate-cw" if direction == "left" else "rotate-ccw"
    icon = _create_colored_icon(
        svg_name,
        theme_color.name() if is_hovered else ("#e0e0e0" if is_dark else "#333333"),
        theme_color.name(),
        24, is_hovered
    )
    return icon


def get_copy_move_icon(mode="copy", is_dark=True, is_hovered=False):
    """复制/移动图标 - 使用 Copy 或 Move (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    svg_name = "copy" if mode == "copy" else "move"
    icon = _create_colored_icon(
        svg_name,
        theme_color.name() if is_hovered else ("#e0e0e0" if is_dark else "#333333"),
        theme_color.name(),
        24, is_hovered
    )
    return icon


def get_asc_desc_icon(mode="asc", is_dark=True, is_selected=False, is_hovered=False):
    """排序方向图标 - 使用 SortAsc 或 SortDesc (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    svg_name = "arrow-up-down"  # 使用通用的上下箭头代替
    icon = _create_colored_icon(
        svg_name,
        theme_color.name(),
        None,
        24, is_hovered
    )
    return icon


def get_scan_mode_icon(mode="single", is_dark=True, is_hovered=False):
    """扫描模式图标 - 使用 FolderPlus 或 Folders (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    svg_name = "folder-plus" if mode == "single" else "folders"
    icon = _create_colored_icon(
        svg_name,
        theme_color.name(),
        None,
        24, is_hovered
    )
    return icon


def get_clear_action_icon(is_dark=True, is_hovered=False):
    """清除按钮图标 - 使用 Trash2 (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    icon = _create_colored_icon(
        "trash-2",
        theme_color.name() if is_hovered else "#ffffff",
        None,
        24, is_hovered
    )
    return icon


def get_sidebar_toggle_icon(is_collapsed=False, is_dark=True, is_hovered=False):
    """侧边栏切换图标 - 使用 PanelLeftOpen 或 PanelLeftClose (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    svg_name = "panel-left-close" if is_collapsed else "panel-left-open"
    icon = _create_colored_icon(
        svg_name,
        theme_color.name(),
        None,
        24, is_hovered
    )
    return icon


def get_layout_type_icon(mode="vertical", is_dark=True, is_selected=False, 
                         has_offset=True, is_hovered=False):
    """布局类型图标 - 使用 Columns2 或 Rows2 (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    svg_name = "columns-2" if mode == "vertical" else "rows-2"
    icon = _create_colored_icon(
        svg_name,
        theme_color.name(),
        ("#e0e0e0" if is_dark else "#333333") if has_offset else None,
        24, is_hovered
    )
    return icon


def get_size_icon(is_dark=True, is_hovered=False):
    """尺寸图标 - 使用 Maximize2 (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    icon = _create_colored_icon(
        "maximize-2",
        theme_color.name() if is_hovered else ("#e0e0e0" if is_dark else "#333333"),
        theme_color.name(),
        24, is_hovered
    )
    return icon


def get_format_icon(is_dark=True, is_hovered=False):
    """格式图标 - 使用 Image (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    icon = _create_colored_icon(
        "image",
        theme_color.name() if is_hovered else ("#e0e0e0" if is_dark else "#333333"),
        theme_color.name(),
        24, is_hovered
    )
    return icon


def get_help_icon(is_dark=True, is_hovered=False):
    """帮助图标 - 使用 LifeBuoy (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    icon = _create_colored_icon(
        "life-buoy",
        theme_color.name(),
        None,
        24, is_hovered
    )
    return icon


def get_lang_icon(lang_code="zh", is_dark=True, is_hovered=False):
    """语言图标 - 使用 Globe (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    icon = _create_colored_icon(
        "globe",
        theme_color.name(),
        None,
        24, is_hovered
    )
    return icon


def get_skin_icon(is_dark=True, is_hovered=False):
    """皮肤切换图标 - 使用 Shirt (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    icon = _create_colored_icon(
        "shirt",
        theme_color.name(),
        None,
        24, is_hovered
    )
    return icon


def get_search_btn_icon(is_dark=True, is_hovered=False):
    """搜索图标 - 使用 Search (Lucide)"""
    theme_color = get_current_theme_color(is_hovered)
    icon = _create_colored_icon(
        "search",
        theme_color.name() if is_hovered else ("#e0e0e0" if is_dark else "#333333"),
        theme_color.name(),
        24, is_hovered
    )
    return icon
