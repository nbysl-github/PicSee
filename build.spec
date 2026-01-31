# -*- mode: python ; coding: utf-8 -*-
import sys
import os

# ========== 手动指定你的程序路径（关键修复） ==========
# 替换为你的 PicSee.py 所在目录（绝对路径，纯英文）
PROJECT_DIR = r"D:\PicSee"
# =====================================================

# 获取PyQt5插件路径（兼容嵌入式Python）
def get_qt_plugins_path():
    try:
        # 嵌入式Python路径
        pyqt5_path = os.path.join(os.path.dirname(sys.executable), 'Lib', 'site-packages', 'PyQt5')
        # 尝试Qt5/plugins
        path1 = os.path.join(pyqt5_path, 'Qt5', 'plugins')
        if os.path.exists(path1):
            return path1
        # 尝试Qt/plugins
        path2 = os.path.join(pyqt5_path, 'Qt', 'plugins')
        if os.path.exists(path2):
            return path2
        # 兜底：使用系统默认路径
        import PyQt5
        return os.path.join(os.path.dirname(PyQt5.__file__), 'Qt5', 'plugins')
    except:
        return ""

# 收集Qt插件
qt_plugins_path = get_qt_plugins_path()
qt_plugins = []
if qt_plugins_path and os.path.exists(qt_plugins_path):
    # 手动收集必要的Qt插件（避免依赖collect_data_files）
    for plugin_type in ['platforms', 'imageformats']:
        plugin_dir = os.path.join(qt_plugins_path, plugin_type)
        if os.path.exists(plugin_dir):
            for root, _, files in os.walk(plugin_dir):
                for file in files:
                    if file.endswith('.dll'):
                        src = os.path.join(root, file)
                        dst = os.path.join('PyQt5', 'Qt5', 'plugins', plugin_type)
                        qt_plugins.append((src, dst))

a = Analysis(
    [os.path.join(PROJECT_DIR, 'PicSee.py')],  # 手动指定主程序路径
    pathex=[PROJECT_DIR],  # 修复__file__问题：直接用手动指定的路径
    binaries=[],
    datas=qt_plugins,  # 手动收集的Qt插件
    hiddenimports=[
        'PIL', 'PIL.Image', 'PIL.ImageOps', 'PIL.ImageResampling',
        'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets'
    ],  # 手动指定隐藏依赖
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5.QtWebEngine', 'PyQt5.QtMultimedia',  # 排除无用模块减小体积
        'PyQt5.QtBluetooth', 'PyQt5.QtNetwork'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='图片瀑布流查看器',  # EXE文件名
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # 压缩EXE
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 先开启控制台，方便排查错误（后续可改False）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico'  # 可选：添加图标，取消注释并指定ico文件路径
)