from collections import OrderedDict
from PyQt5.QtCore import QMutex, QMutexLocker

class LRUImageCache:
    """LRU缓存实现，限制最大缓存数量，自动淘汰最久未使用的图片"""

    def __init__(self, max_size=200):
        self.cache = OrderedDict()
        self.max_size = max_size
        self._lock = QMutex()

    def get(self, key):
        with QMutexLocker(self._lock):
            if key in self.cache:
                # 移动到末尾（最近使用）
                self.cache.move_to_end(key)
                return self.cache[key]
            return None

    def put(self, key, value):
        with QMutexLocker(self._lock):
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.max_size:
                # 移除最久未使用的
                self.cache.popitem(last=False)

    def clear(self):
        with QMutexLocker(self._lock):
            self.cache.clear()

    def __contains__(self, key):
        with QMutexLocker(self._lock):
            return key in self.cache

    def __len__(self):
        with QMutexLocker(self._lock):
            return len(self.cache)
