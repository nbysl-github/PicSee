import sys
import os
import ctypes
import subprocess
import winreg
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from src.utils.common import safe_path

def fix_chinese_path():
    """解决中文路径问题（增强版）"""
    try:
        # 修复：只在有控制台窗口时才设置控制台编码，避免打包后出现黑色窗口
        # 检测是否有控制台窗口
        console_handle = ctypes.windll.kernel32.GetConsoleWindow()
        if console_handle != 0:
            # 控制台编码修复（仅在存在控制台时）
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)

        # Qt路径编码修复
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = ""
        os.environ["PYTHONIOENCODING"] = "utf-8"
        os.environ["QT_CHARSET"] = "utf-8"

        # 性能优化：智能启用 WebEngine GPU 硬件加速
        _enable_gpu_acceleration()
    except Exception:
        pass  # 静默处理错误，避免触发控制台输出


def _enable_gpu_acceleration():
    """智能检测并启用 GPU 硬件加速（性能优化：提升 WebView 渲染性能）"""
    try:
        gpu_info = ""

        # 方法1: 尝试使用 PowerShell（Windows 10/11 推荐）
        try:
            # 增加 creationflags=subprocess.CREATE_NO_WINDOW 以防止弹出黑色窗口
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                [
                    "powershell",
                    "-Command",
                    "Get-WmiObject Win32_VideoController | Select-Object -ExpandProperty Name",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=creation_flags,
            )
            if result.returncode == 0:
                gpu_info = result.stdout.upper()
        except:
            pass

        # 方法2: 如果PowerShell失败，尝试读取注册表
        if not gpu_info:
            try:
                # 读取显示适配器注册表信息
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}",
                )
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        try:
                            driver_desc = winreg.QueryValueEx(subkey, "DriverDesc")[0]
                            gpu_info += driver_desc.upper() + " "
                        except:
                            pass
                        finally:
                            winreg.CloseKey(subkey)
                    except:
                        pass
                winreg.CloseKey(key)
            except:
                pass

        # 方法3: 尝试使用dxdiag（如果存在）
        if not gpu_info:
            try:
                creation_flags = 0
                if sys.platform == "win32":
                    creation_flags = subprocess.CREATE_NO_WINDOW

                result = subprocess.run(
                    ["dxdiag", "/t", "dxdiag_output.txt"],
                    capture_output=True,
                    timeout=10,
                    creationflags=creation_flags,
                )
                # dxdiag 是异步的，我们使用其他方法
            except:
                pass

        has_dedicated_gpu = any(
            gpu in gpu_info for gpu in ["NVIDIA", "AMD", "ATI", "RADEON", "GEFORCE"]
        )

        if has_dedicated_gpu:
            # 启用 GPU 加速（有独立显卡时）
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
                "--ignore-gpu-blacklist "
                "--enable-gpu-rasterization "
                "--enable-zero-copy "
                "--disable-gpu-driver-bug-workarounds"
            )
        else:
            # 集成显卡也启用基本加速，但使用保守设置
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
                "--enable-gpu-rasterization --disable-gpu-driver-bug-workarounds"
            )
    except Exception:
        # 即使检测失败，也启用保守的GPU加速（静默处理错误）
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-gpu-rasterization"


def open_with_system_viewer(img_path):
    """打开系统查看器（兼容中文路径）"""
    try:
        # 安全路径处理
        safe_p = safe_path(img_path)
        original_p = (
            safe_p.replace("\\\\?\\", "") if sys.platform == "win32" else safe_p
        )
        if sys.platform == "win32":
            os.startfile(original_p)
        elif sys.platform == "darwin":
            subprocess.run(["open", original_p], encoding="utf-8")
        else:
            subprocess.run(["xdg-open", original_p], encoding="utf-8")
    except Exception as e:
        QDesktopServices.openUrl(QUrl.fromLocalFile(img_path))
