import sys
import os
import multiprocessing
import logging

# 抑制 Chromium 弃用警告
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-deprecated-cursor-size")
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false;qml=false")

# 禁用 PyQtWebEngine 日志
logging.getLogger("PyQt5").setLevel(logging.CRITICAL)
logging.getLogger("PyQt5.QtCore").setLevel(logging.CRITICAL)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import qInstallMessageHandler

from src.ui.main_window import ImageViewerWindow
from src.utils.system import fix_chinese_path

if __name__ == "__main__":
    # Windows 打包多进程支持
    multiprocessing.freeze_support()

    # 解决中文路径和高分屏及 GPU 加速
    fix_chinese_path()

    app = QApplication(sys.argv)

    # 安装消息处理器来抑制 JavaScript 控制台输出
    def suppress_js_messages(msg_type, context, message):
        if "Custom cursors" in message or "deprecated" in message.lower():
            return

    qInstallMessageHandler(suppress_js_messages)

    # 创建并显示主窗口
    window = ImageViewerWindow()
    window.show()

    sys.exit(app.exec_())
