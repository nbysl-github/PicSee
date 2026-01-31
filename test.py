import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QLabel, QScrollArea, QFileDialog,
    QMessageBox, QDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

# 预览窗口（仅翻页+缩放）
class PreviewDialog(QDialog):
    def __init__(self, img_list, index, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图片预览")
        self.img_list = img_list
        self.current_idx = index
        self.scale = 1.0  # 缩放比例
        self.resize(800, 600)

        # 主布局
        main_layout = QHBoxLayout(self)
        
        # 上一张按钮
        btn_prev = QPushButton("上一张")
        btn_prev.clicked.connect(self.prev_img)
        main_layout.addWidget(btn_prev)

        # 图片显示区域（带滚动）
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        main_layout.addWidget(self.scroll_area, stretch=1)
        
        # 图片标签
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.img_label)

        # 下一张按钮
        btn_next = QPushButton("下一张")
        btn_next.clicked.connect(self.next_img)
        main_layout.addWidget(btn_next)

        # 加载当前图片
        self.load_image()

    def load_image(self):
        """加载当前索引的图片"""
        try:
            img_path = self.img_list[self.current_idx]
            pixmap = QPixmap(img_path)
            if pixmap.isNull():
                self.img_label.setText("图片加载失败")
                return
            
            # 初始缩放（适配窗口）
            self.scale = 1.0
            scaled_pixmap = pixmap.scaled(
                self.scroll_area.size() * 0.8,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.img_label.setPixmap(scaled_pixmap)
            self.setWindowTitle(f"图片预览 ({self.current_idx+1}/{len(self.img_list)}) - {os.path.basename(img_path)}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载图片失败：{str(e)}")

    def prev_img(self):
        """上一张"""
        if self.current_idx > 0:
            self.current_idx -= 1
            self.load_image()

    def next_img(self):
        """下一张"""
        if self.current_idx < len(self.img_list) - 1:
            self.current_idx += 1
            self.load_image()

# 主窗口
class SimpleImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("极简图片查看器")
        self.setGeometry(100, 100, 1000, 700)
        self.img_list = []  # 存储图片路径

        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 选择目录按钮
        select_btn = QPushButton("选择图片目录", self)
        select_btn.clicked.connect(self.select_directory)
        main_layout.addWidget(select_btn)

        # 图片列表
        self.img_list_widget = QListWidget()
        self.img_list_widget.clicked.connect(self.show_preview)
        main_layout.addWidget(self.img_list_widget)

    def select_directory(self):
        """选择目录并扫描图片"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择图片目录")
        if not dir_path:
            return
        
        # 扫描图片（仅支持常见格式）
        self.img_list = []
        img_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.lower().endswith(img_extensions):
                    self.img_list.append(os.path.join(root, file))
        
        # 更新列表
        self.img_list_widget.clear()
        for img_path in self.img_list:
            self.img_list_widget.addItem(os.path.basename(img_path))
        
        # 提示结果
        QMessageBox.information(self, "完成", f"共找到 {len(self.img_list)} 张图片")

    def show_preview(self):
        """预览选中的图片"""
        current_row = self.img_list_widget.currentRow()
        if 0 <= current_row < len(self.img_list):
            preview_dialog = PreviewDialog(self.img_list, current_row, self)
            preview_dialog.exec_()

# 主程序入口
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimpleImageViewer()
    window.show()
    sys.exit(app.exec_())