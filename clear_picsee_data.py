#!/usr/bin/env python3
"""
清空 PicSee 的收藏目录和历史目录数据
通过 Windows 注册表操作
"""

import winreg
import os

# 注册表路径
ORGANIZATION_NAME = "ImageViewer"
APPLICATION_NAME = "WaterfallImageViewer"
REGISTRY_PATH = f"SOFTWARE\\{ORGANIZATION_NAME}\\{APPLICATION_NAME}"

print(f"组织名称: {ORGANIZATION_NAME}")
print(f"应用名称: {APPLICATION_NAME}")
print(f"注册表路径: HKEY_CURRENT_USER\\{REGISTRY_PATH}")
print()

try:
    # 打开注册表项
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_READ | winreg.KEY_WRITE
    )

    # 获取当前值
    try:
        favorites_before, _ = winreg.QueryValueEx(key, "favorites_dirs")
    except FileNotFoundError:
        favorites_before = ""

    try:
        history_before, _ = winreg.QueryValueEx(key, "history_dirs")
    except FileNotFoundError:
        history_before = ""

    print("清理前:")
    print(f"  收藏目录 (favorites_dirs): {favorites_before}")
    print(f"  历史目录 (history_dirs): {history_before}")
    print()

    # 清空设置 - 设置为空的 QByteArray 或空字符串
    # QSettings 在 Windows 上通常使用字符串列表格式存储
    winreg.SetValueEx(key, "favorites_dirs", 0, winreg.REG_SZ, "")
    winreg.SetValueEx(key, "history_dirs", 0, winreg.REG_SZ, "")

    winreg.CloseKey(key)

    # 验证清理结果
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_READ)
    try:
        favorites_after, _ = winreg.QueryValueEx(key, "favorites_dirs")
    except FileNotFoundError:
        favorites_after = ""

    try:
        history_after, _ = winreg.QueryValueEx(key, "history_dirs")
    except FileNotFoundError:
        history_after = ""

    winreg.CloseKey(key)

    print("清理后:")
    print(f"  收藏目录 (favorites_dirs): {favorites_after}")
    print(f"  历史目录 (history_dirs): {history_after}")
    print()

    print("[OK] 收藏目录和历史目录数据已清空！")
    print("\n注意: 如果 PicSee 正在运行，请重启应用以生效。")

except FileNotFoundError:
    print(f"[OK] 注册表项不存在，说明数据已经是空的或从未设置过")
    print(f"  路径: HKEY_CURRENT_USER\\{REGISTRY_PATH}")
except Exception as e:
    print(f"[ERROR] 错误: {e}")
