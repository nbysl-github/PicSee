import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QFileDialog,
    QMessageBox, QDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

# 预览窗口（保持不变）
class PreviewDialog(QDialog):
    def __init__(self, img_list, index, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图片预览")
        self.img_list = img_list
        self.current_idx = index
        self.resize(800, 600)

        main_layout = QHBoxLayout(self)
        self.btn_prev = QPushButton("上一张")
        self.btn_prev.clicked.connect(self.prev_img)
        main_layout.addWidget(self.btn_prev)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.img_label)
        main_layout.addWidget(self.scroll_area, stretch=1)

        self.btn_next = QPushButton("下一张")
        self.btn_next.clicked.connect(self.next_img)
        main_layout.addWidget(self.btn_next)

        self.load_image()
        self.update_btn_status()

    def load_image(self):
        img_path = self.img_list[self.current_idx]
        pixmap = QPixmap(img_path)
        if not pixmap.isNull():
            self.img_label.setPixmap(pixmap.scaled(
                self.scroll_area.size() * 0.8,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
        self.setWindowTitle(f"预览 ({self.current_idx+1}/{len(self.img_list)}) - {os.path.basename(img_path)}")

    def prev_img(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self.load_image()
            self.update_btn_status()

    def next_img(self):
        if self.current_idx < len(self.img_list) - 1:
            self.current_idx += 1
            self.load_image()
            self.update_btn_status()

    def update_btn_status(self):
        self.btn_prev.setEnabled(self.current_idx > 0)
        self.btn_next.setEnabled(self.current_idx < len(self.img_list) - 1)

# 主窗口（新增快捷按钮）
class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图片查看器（零崩溃版）")
        self.setGeometry(100, 100, 600, 400)
        self.img_list = []

        # 中心部件
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 按钮区域（新增快捷按钮）
        btn_layout = QHBoxLayout()
        # 原有多选按钮
        self.select_btn = QPushButton("选择图片文件（可多选）")
        self.select_btn.clicked.connect(self.select_files)
        btn_layout.addWidget(self.select_btn)
        # 新增：加载整个文件夹的图片
        self.folder_btn = QPushButton("加载文件夹所有图片")
        self.folder_btn.clicked.connect(self.load_folder_images)
        btn_layout.addWidget(self.folder_btn)
        layout.addLayout(btn_layout)

        # 状态提示
        self.status_label = QLabel("未选择任何图片")
        layout.addWidget(self.status_label)

        # 预览按钮
        self.preview_btn = QPushButton("预览选中的图片")
        self.preview_btn.clicked.connect(self.show_preview)
        self.preview_btn.setEnabled(False)
        layout.addWidget(self.preview_btn)

    def select_files(self):
        """选择多张图片"""
        file_filter = "图片文件 (*.jpg *.jpeg *.png *.bmp *.gif)"
        files, _ = QFileDialog.getOpenFileNames(self, "选择图片文件", "", file_filter)
        if not files:
            return
        
        self.img_list = files
        self.status_label.setText(f"已选择 {len(self.img_list)} 张图片")
        self.preview_btn.setEnabled(True)
        QMessageBox.information(self, "完成", f"已选择 {len(self.img_list)} 张图片")

    def load_folder_images(self):
        """快捷加载整个文件夹的图片"""
        # 先选择文件夹
        folder_path = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if not folder_path:
            return
        
        # 筛选文件夹内的图片（仅读取文件名，不遍历子目录，避免崩溃）
        img_ext = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')
        self.img_list = []
        for file in os.listdir(folder_path):
            if file.lower().endswith(img_ext):
                self.img_list.append(os.path.join(folder_path, file))
        
        if not self.img_list:
            QMessageBox.warning(self, "提示", "该文件夹中未找到图片")
            return
        
        self.status_label.setText(f"已加载 {len(self.img_list)} 张图片（来自：{folder_path}）")
        self.preview_btn.setEnabled(True)
        QMessageBox.information(self, "完成", f"已加载 {len(self.img_list)} 张图片")

    def show_preview(self):
        """预览第一张图片"""
        if self.img_list:
            dlg = PreviewDialog(self.img_list, 0, self)
            dlg.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageViewer()
    window.show()
    sys.exit(app.exec_())