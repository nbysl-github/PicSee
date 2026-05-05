import sys
import os
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
from PIL import Image, ImageOps
from src.utils.common import safe_path
from src.workers.utils import process_enhanced_image

class WorkerSignals(QObject):
    # path, q_image, width, height
    finished = pyqtSignal(str, QImage, int, int)

class ImageLoadTask(QRunnable):
    def __init__(self, path, col_width, task_id):
        super().__init__()
        self.path = safe_path(path)
        self.col_width = col_width
        self.task_id = task_id
        self.signals = WorkerSignals()
        self.setAutoDelete(True)
        self.is_finished = False

    def cancel(self):
        self.is_finished = True

    def run(self):
        if self.is_finished:
            return

        try:
            # 检查文件是否存在
            if not os.path.exists(self.path):
                self.is_finished = True
                return

            # 使用 Pillow 加载并处理图片
            with Image.open(self.path) as img:
                # 处理 EXIF 旋转
                img = ImageOps.exif_transpose(img)
                orig_w, orig_h = img.size

                # 计算目标高度，保持比例
                scale = self.col_width / orig_w
                target_h = int(orig_h * scale)

                # 高质量缩放
                resample_method = getattr(Image.Resampling, "LANCZOS", Image.LANCZOS)
                img = img.resize((self.col_width, target_h), resample_method)

                # 转换为 RGB/RGBA
                if img.mode not in ["RGB", "RGBA"]:
                    img = img.convert("RGB")

                # 转换为 QImage
                img_data = img.tobytes()
                q_format = (
                    QImage.Format_RGBA8888
                    if img.mode == "RGBA"
                    else QImage.Format_RGB888
                )
                q_img = QImage(
                    img_data,
                    self.col_width,
                    target_h,
                    self.col_width * len(img.mode),
                    q_format,
                ).copy()

                if not self.is_finished:
                    # 还原原始路径用于匹配
                    original_path = (
                        self.path.replace("\\\\?\\", "")
                        if sys.platform == "win32"
                        else self.path
                    )
                    # 发送 QImage 而非 QPixmap，以确保线程安全
                    self.signals.finished.emit(
                        original_path, q_img, self.col_width, target_h
                    )

        except Exception:
            # 静默失败，或者可以在这里记录日志
            pass
        finally:
            self.is_finished = True

# 扩展 WorkerSignals 以支持预览加载
class PreviewWorkerSignals(QObject):
    # path, q_img, scale_factor, pil_image
    result = pyqtSignal(str, QImage, float, object)

class PreviewLoadTask(QRunnable):
    def __init__(self, path, view_width, view_height):
        super().__init__()
        self.path = safe_path(path)
        self.view_width = view_width
        self.view_height = view_height
        self.signals = PreviewWorkerSignals()
        self.setAutoDelete(True)

    def run(self):
        try:
            if not os.path.exists(self.path):
                return

            pil_image = Image.open(self.path)
            pil_image = ImageOps.exif_transpose(pil_image)
            if pil_image.mode not in ["RGB", "RGBA"]:
                pil_image = pil_image.convert(
                    "RGB" if pil_image.mode != "RGBA" else "RGBA"
                )

            available_w = max(100, self.view_width - 160)
            available_h = max(100, self.view_height - 60)

            scale_w = available_w / pil_image.width
            scale_h = available_h / pil_image.height
            scale_factor = min(scale_w, scale_h, 1.0)

            target_w = int(pil_image.width * scale_factor)
            target_h = int(pil_image.height * scale_factor)

            enhanced_img = process_enhanced_image(pil_image, target_w, target_h)

            img_data = enhanced_img.tobytes()
            q_format = (
                QImage.Format_RGBA8888
                if enhanced_img.mode == "RGBA"
                else QImage.Format_RGB888
            )
            q_img = QImage(
                img_data,
                target_w,
                target_h,
                target_w * len(enhanced_img.mode),
                q_format,
            ).copy()
            # Do NOT create QPixmap here. It is unsafe in threads.

            # 还原原始路径（去掉 \\?\ 前缀用于匹配）
            original_path = (
                self.path.replace("\\\\?\\", "")
                if sys.platform == "win32"
                else self.path
            )
            self.signals.result.emit(original_path, q_img, scale_factor, pil_image)

        except Exception:
            # 静默失败
            pass
