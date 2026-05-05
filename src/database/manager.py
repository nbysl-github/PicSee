import os
import sqlite3
from PyQt5.QtCore import QStandardPaths, QMutex

class DatabaseManager:
    def __init__(self):
        # 获取系统数据目录
        data_dir = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        if not data_dir:
            # 如果 AppData 路径不可用，使用当前目录下的 data 文件夹
            data_dir = os.path.join(os.getcwd(), "data")
            
        if not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir, exist_ok=True)
            except Exception:
                # 最后的保底：直接用当前目录
                data_dir = os.getcwd()

        self.db_path = os.path.join(data_dir, "metadata_cache.db")
        self._init_db()

    def _init_db(self):
        try:
            # 尝试连接文件数据库
            conn = sqlite3.connect(self.db_path)
            conn.execute("SELECT 1")  # 测试连接是否真正可用
        except sqlite3.OperationalError:
            # 如果文件数据库不可用，回退到内存数据库
            self.db_path = ":memory:"
            conn = sqlite3.connect(self.db_path)

        try:
            with conn:
                try:
                    # 只有文件数据库支持 WAL
                    if self.db_path != ":memory:":
                        conn.execute("PRAGMA journal_mode=WAL")
                except sqlite3.OperationalError:
                    pass
                
                try:
                    conn.execute("PRAGMA synchronous=NORMAL")
                except sqlite3.OperationalError:
                    pass
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS image_metadata (
                        path TEXT PRIMARY KEY,
                        width INTEGER,
                        height INTEGER,
                        size INTEGER,
                        mtime REAL
                    )
                """)
                # 为路径建立索引以加快查询
                conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON image_metadata(path)")
                # 添加复合索引，加速基于路径和修改时间的缓存验证查询（性能优化）
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_path_mtime ON image_metadata(path, mtime)"
                )
                # 创建 EXIF 信息缓存表（性能优化：加速图片预览信息加载）
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS exif_cache (
                        path TEXT PRIMARY KEY,
                        width INTEGER,
                        height INTEGER,
                        format TEXT,
                        camera_make TEXT,
                        camera_model TEXT,
                        capture_time TEXT,
                        iso TEXT,
                        aperture TEXT,
                        exposure TEXT,
                        focal_length TEXT,
                        lens TEXT,
                        mtime REAL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_exif_path ON exif_cache(path)")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_exif_mtime ON exif_cache(path, mtime)"
                )
        except sqlite3.OperationalError:
            # 如果任何数据库操作失败，回退到内存数据库
            self.db_path = ":memory:"
            conn = sqlite3.connect(self.db_path)
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS image_metadata (
                        path TEXT PRIMARY KEY,
                        width INTEGER,
                        height INTEGER,
                        size INTEGER,
                        mtime REAL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON image_metadata(path)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_path_mtime ON image_metadata(path, mtime)")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS exif_cache (
                        path TEXT PRIMARY KEY,
                        width INTEGER,
                        height INTEGER,
                        format TEXT,
                        camera_make TEXT,
                        camera_model TEXT,
                        capture_time TEXT,
                        iso TEXT,
                        aperture TEXT,
                        exposure TEXT,
                        focal_length TEXT,
                        lens TEXT,
                        mtime REAL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_exif_path ON exif_cache(path)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_exif_mtime ON exif_cache(path, mtime)")

    def get_metadata_batch(self, paths):
        """批量获取元数据，极大提升扫描性能"""
        if not paths:
            return {}

        results = {}
        try:
            # 使用上下文管理器确保连接关闭
            with sqlite3.connect(self.db_path) as conn:
                # SQLite 默认一次最多处理 999 个变量，我们分片处理
                for i in range(0, len(paths), 900):
                    chunk = paths[i : i + 900]
                    placeholders = ",".join(["?"] * len(chunk))
                    cursor = conn.execute(
                        f"SELECT path, width, height, size, mtime FROM image_metadata WHERE path IN ({placeholders})",
                        chunk,
                    )
                    for row in cursor.fetchall():
                        results[row[0]] = (row[1], row[2], row[3], row[4])
        except Exception:
            pass
        return results

    def save_metadata_batch(self, items):
        """批量保存元数据，提升性能"""
        if not items:
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO image_metadata (path, width, height, size, mtime) VALUES (?, ?, ?, ?, ?)",
                    [
                        (
                            item["path"],
                            item["w"],
                            item["h"],
                            item["size"],
                            item["mtime"],
                        )
                        for item in items
                    ],
                )
        except Exception:
            pass

    def save_exif_cache(self, path, exif_info, mtime):
        """保存 EXIF 信息到缓存（性能优化：加速图片预览信息加载）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO exif_cache 
                    (path, width, height, format, camera_make, camera_model, capture_time, 
                     iso, aperture, exposure, focal_length, lens, mtime)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        path,
                        exif_info.get("width"),
                        exif_info.get("height"),
                        exif_info.get("format"),
                        exif_info.get("camera_make"),
                        exif_info.get("camera_model"),
                        exif_info.get("capture_time"),
                        exif_info.get("iso"),
                        exif_info.get("aperture"),
                        exif_info.get("exposure"),
                        exif_info.get("focal_length"),
                        exif_info.get("lens"),
                        mtime,
                    ),
                )
        except Exception:
            pass

    def get_exif_cache(self, path, mtime):
        """从缓存获取 EXIF 信息（性能优化：加速图片预览信息加载）

        Args:
            path: 图片路径
            mtime: 文件修改时间，用于验证缓存是否过期

        Returns:
            dict: EXIF 信息字典，如果缓存不存在或已过期则返回 None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT width, height, format, camera_make, camera_model, capture_time, "
                    "iso, aperture, exposure, focal_length, lens, mtime FROM exif_cache WHERE path = ?",
                    (path,),
                )
                row = cursor.fetchone()
                # 修复：浮点数比较使用容差，避免精度问题
                if row and abs(row[11] - mtime) < 0.001:  # 验证 mtime 是否匹配
                    return {
                        "width": row[0],
                        "height": row[1],
                        "format": row[2],
                        "camera_make": row[3],
                        "camera_model": row[4],
                        "capture_time": row[5],
                        "iso": row[6],
                        "aperture": row[7],
                        "exposure": row[8],
                        "focal_length": row[9],
                        "lens": row[10],
                    }
                return None
        except Exception as e:
            return None

# Singleton instance
db_manager = DatabaseManager()
