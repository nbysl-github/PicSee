import os
import traceback
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal
from PIL import Image
from src.database.manager import db_manager

class ScanSignals(QObject):
    finished = pyqtSignal(list, int)
    batch_ready = pyqtSignal(list, int)  # 新增信号：分批发送数据

class ScanWorker(QRunnable):
    def __init__(self, dir_path, scan_id, recursive=False):
        super().__init__()
        self.dir_path = dir_path
        self.scan_id = scan_id
        self.recursive = recursive
        self.signals = ScanSignals()
        self.setAutoDelete(True)
        self.is_aborted = False

    def abort(self):
        self.is_aborted = True

    def run(self):
        img_data = []
        batch_data = []  # 临时存储当前批次
        cache_save_batch = []  # 待写入缓存的批次
        current_batch_size = 10  # 初始批次较小，以便快速看到第一批图
        max_batch_size = 100  # 随着加载进行，增加批次大小以提高效率

        img_extensions = (
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".webp",
            ".ico",
        )
        try:
            # os.walk works with \\\\?\\ paths on Windows
            scan_path = self.dir_path

            # Ensure scan_path exists and is a directory
            if not os.path.exists(scan_path):
                self.signals.finished.emit([], self.scan_id)
                return

            if self.recursive:
                walker = os.walk(scan_path)
            else:
                # Non-recursive: only scan the current directory
                try:
                    files = []
                    with os.scandir(scan_path) as it:
                        for entry in it:
                            if entry.is_file():
                                files.append(entry.name)
                    walker = [(scan_path, [], files)]
                except Exception:
                    walker = []

            count = 0
            for root, _, files in walker:
                if self.is_aborted:
                    return

                # 过滤出图片文件
                img_files = [f for f in files if f.lower().endswith(img_extensions)]
                if not img_files:
                    continue

                # 构建完整路径并获取文件状态（用于校验缓存是否失效）
                file_info_list = []
                for f in img_files:
                    if self.is_aborted:
                        return
                    f_path = os.path.join(root, f)
                    try:
                        st = os.stat(f_path)
                        file_info_list.append(
                            {"path": f_path, "size": st.st_size, "mtime": st.st_mtime}
                        )
                    except (OSError, PermissionError):
                        # 文件无法访问或已被删除,跳过
                        continue

                # 1. 批量从缓存读取元数据
                all_paths = [info["path"] for info in file_info_list]
                cached_data = db_manager.get_metadata_batch(all_paths)

                for info in file_info_list:
                    if self.is_aborted:
                        return

                    file_path = info["path"]
                    size_val = info["size"]
                    mtime_val = info["mtime"]

                    # 检查缓存命中且未过期
                    hit = False
                    if file_path in cached_data:
                        c_w, c_h, c_size, c_mtime = cached_data[file_path]
                        if c_size == size_val and abs(c_mtime - mtime_val) < 0.01:
                            w, h = c_w, c_h
                            item = {
                                "path": file_path,
                                "w": w,
                                "h": h,
                                "size": size_val,
                                "mtime": mtime_val,
                            }
                            img_data.append(item)
                            batch_data.append(item)
                            count += 1
                            hit = True

                    if hit:
                        # 如果批次满了，立即发送
                        if len(batch_data) >= current_batch_size:
                            self.signals.batch_ready.emit(batch_data, self.scan_id)
                            batch_data = []
                            if current_batch_size < max_batch_size:
                                current_batch_size = min(
                                    max_batch_size, current_batch_size + 10
                                )
                        continue

                    # 2. 缓存失效或不存在，使用 Pillow 解析
                    try:
                        # Use Pillow instead of QImageReader
                        with Image.open(file_path) as img:
                            w, h = img.size
                       # Handle EXIF Orientation
                        try:
                            exif = img.getexif()
                            if exif:
                                orientation = exif.get(274)  # 274 is Orientation
                                if orientation in (5, 6, 7, 8):
                                    w, h = h, w
                        except (KeyError, TypeError):
                            # EXIF 数据解析失败,忽略
                            pass

                        item = {
                            "path": file_path,
                            "w": w,
                            "h": h,
                            "size": size_val,
                            "mtime": mtime_val,
                        }
                        img_data.append(item)
                        batch_data.append(item)
                        cache_save_batch.append(item)
                        count += 1

                        # 定期保存到缓存数据库
                        if len(cache_save_batch) >= 50:
                            db_manager.save_metadata_batch(cache_save_batch)
                            cache_save_batch = []

                        # 发送批次数据
                        if len(batch_data) >= current_batch_size:
                            self.signals.batch_ready.emit(batch_data, self.scan_id)
                            batch_data = []
                            if current_batch_size < max_batch_size:
                                current_batch_size = min(
                                    max_batch_size, current_batch_size + 10
                                )

                    except Exception:
                        pass

            # 发送剩余的批次数据
            if batch_data:
                self.signals.batch_ready.emit(batch_data, self.scan_id)

            # 保存剩余的缓存数据
            if cache_save_batch:
                db_manager.save_metadata_batch(cache_save_batch)

            self.signals.finished.emit(img_data, self.scan_id)
        except Exception as e:
            traceback.print_exc()
            self.signals.finished.emit([], self.scan_id)
