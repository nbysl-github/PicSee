# Lucide 图标迁移文档

## 概述

PicSee 已完成从自定义 QPainter 图标到 Lucide SVG 图标的迁移。

## 迁移内容

### 新增文件

1. **`src/utils/lucide_icons.py`** - Lucide 图标系统核心
   - SVG 到 QPixmap 转换函数
   - 图标缓存机制
   - 所有 23 个 PicSee 图标函数

2. **`docs/lucide_icons_migration.md`** - 本文档

### 修改文件

1. **`src/utils/icons.py`** - 重写为兼容层
   - 删除所有旧的 QPainter 图标实现
   - 从 `lucide_icons.py` 导入所有函数
   - 保持向后兼容

2. **`src/ui/main_window.py`** - 更新导入
   - 删除 `_get_tshirt_icon` 导入
   - 使用 `get_skin_icon` 替代

3. **`requirements.txt`** - 添加依赖
   - 新增 `python-lucide` 依赖

## Lucide 图标映射

| 原图标函数 | Lucide 图标 | 说明 |
|-----------|------------|------|
| `get_sort_icon` | `arrow-up-down` | 排序 |
| `get_refresh_icon` | `refresh-cw` | 刷新 |
| `get_layout_icon` | `grid-3x3` | 布局 |
| `get_delete_icon` | `trash-2` | 删除(红色) |
| `get_add_icon` | `plus-circle` | 添加 |
| `get_clear_icon` | `trash-2` | 清除 |
| `get_folder_icon` | `folder` | 文件夹 |
| `get_computer_icon` | `monitor` | 此电脑 |
| `get_pin_icon` | `pin` | 收藏 |
| `get_history_icon` | `clock` | 历史 |
| `get_rotate_icon` | `rotate-cw/rotate-ccw` | 旋转 |
| `get_copy_move_icon` | `copy/move` | 复制/移动 |
| `get_asc_desc_icon` | `sort-asc/sort-desc` | 升序/降序 |
| `get_scan_mode_icon` | `folder-plus/folders` | 扫描模式 |
| `get_clear_action_icon` | `trash-2` | 清除按钮 |
| `get_sidebar_toggle_icon` | `panel-left-close/panel-left-open` | 侧边栏切换 |
| `get_layout_type_icon` | `columns-2/rows-2` | 布局类型 |
| `get_size_icon` | `maximize-2` | 尺寸 |
| `get_format_icon` | `image` | 格式 |
| `get_help_icon` | `life-buoy` | 帮助 |
| `get_lang_icon` | `globe` | 语言 |
| `get_skin_icon` | `shirt` | 皮肤切换 |
| `get_search_btn_icon` | `search` | 搜索 |

## "皮肤色"主题效果

所有图标保持原有的"皮肤色"主题效果:

1. **主色 (皮肤色)**: 使用 `get_current_theme_color()` 获取当前主题颜色
2. **次要色**: 灰色 (`#e0e0e0` 暗色模式 / `#333333` 亮色模式)
3. **悬停效果**: 悬停时颜色更鲜艳

## 技术实现

### SVG 渲染

```python
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import QByteArray

def _svg_to_pixmap(svg_content: str, size: int = 24, color: str = None) -> QPixmap:
    # 更新 SVG 中的颜色
    if color:
        svg_content = svg_content.replace('stroke="currentColor"', f'stroke="{color}"')
    
    # 使用 QSvgRenderer 渲染
    renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    
    return pixmap
```

### 图标缓存

```python
_icon_cache = {}

def _create_colored_icon(svg_name: str, primary_color: str, ...) -> QIcon:
    cache_key = (svg_name, primary_color, secondary_color, is_hovered)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]
    
    # 创建图标并缓存
    icon = QIcon(primary_pixmap)
    _icon_cache[cache_key] = icon
    return icon
```

## 优势

1. **更清晰**: SVG 图标在任何缩放下都保持清晰
2. **更易维护**: Lucide 图标库持续更新,1000+ 图标可用
3. **更小体积**: SVG 文件比位图小得多
4. **统一风格**: Lucide 图标风格一致
5. **保持特色**: 保留"皮肤色"主题效果

## 依赖

```
python-lucide >= 0.2.24
PyQt5 (含 QtSvg)
```

## 参考资料

- Lucide 官网: https://lucide.dev/
- python-lucide: https://github.com/mmacpherson/python-lucide
- Lucide 图标列表: https://lucide.dev/icons/
