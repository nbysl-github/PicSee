import sys
import os
import json
from PyQt5.QtCore import QLocale

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Assuming src/utils/common.py -> ../../
        # But wait, __file__ will be in src/utils/common.py
        # The original was in root.
        # If I run from root, base_path should be root.
        
        # Adjust logic:
        # If we are in src/utils, we need to go up two levels to get to project root
        # IF we assume resources are at project root.
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # src/utils -> src -> root
        base_path = os.path.dirname(os.path.dirname(current_dir))
        
    return os.path.join(base_path, relative_path)

def safe_path(path):
    """安全处理路径，确保中文/特殊符号正常识别"""
    if not path:
        return ""
    # 转换为绝对路径并标准化
    path = os.path.abspath(path)
    # 处理Windows长路径
    if sys.platform == "win32" and not path.startswith("\\\\?\\"):
        path = f"\\\\?\\{path}"
    return path

def _normalize_lang_code(lang):
    if not lang:
        return "zh"
    lang = str(lang).strip().lower().replace("-", "_")
    parts = [p for p in lang.split("_") if p]
    if not parts:
        return "zh"
    if parts[0] == "zh":
        if "hant" in parts:
            return "zh_tw"
        if len(parts) >= 2:
            region = parts[1]
            if region in ("tw", "hk", "mo", "hant"):
                return "zh_tw"
            if region in ("cn", "sg", "hans"):
                return "zh"
        return "zh"
    return parts[0]

def _load_language_pack_from_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    if isinstance(data, dict) and isinstance(data.get("strings"), dict):
        return data["strings"]
    if isinstance(data, dict):
        return data
    return None

def _load_all_language_packs():
    translations = {}
    # resource_path will return root/lang
    lang_dir = resource_path("lang")
    if os.path.isdir(lang_dir):
        try:
            for name in os.listdir(lang_dir):
                if not name.lower().endswith(".json"):
                    continue
                code = _normalize_lang_code(os.path.splitext(name)[0])
                file_path = os.path.join(lang_dir, name)
                strings = _load_language_pack_from_file(file_path)
                if strings:
                    translations[code] = strings
        except Exception:
            pass
    return translations

def _detect_system_lang_code(translations):
    try:
        sys_lang = QLocale.system().name()
    except Exception:
        sys_lang = ""
    code = _normalize_lang_code(sys_lang)
    if code in translations:
        return code
    if "en" in translations:
        return "en"
    if "zh" in translations:
        return "zh"
    for k in translations.keys():
        if isinstance(translations.get(k), dict):
            return k
    return "zh"

def _ensure_zoom_defaults(img):
    """
    [LEGACY] Ensure zoom defaults for image dict.
    This function is currently unused and kept for potential future use.
    Consider removing in next cleanup cycle.
    """
    if isinstance(img, dict):
        img.setdefault("zoom", 1.0)
        img.setdefault("minZoom", 1.0)
        img.setdefault("maxZoom", 4.0)
    return img
