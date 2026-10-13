"""
一键在桌面生成专属带盾牌图标的快捷方式 (create_desktop_shortcut.py)
"""

import os
import win32com.client

def create_desktop_shortcut():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_pyw = os.path.join(base_dir, "main.py")
    icon_path = os.path.join(base_dir, "assets", "icon.ico")
    shortcut_path = os.path.join(desktop, "企微防骚扰反制助手.lnk")

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    
    # 查找 pythonw.exe 路径
    python_dir = os.path.dirname(sys.executable)
    pythonw_path = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw_path):
        pythonw_path = sys.executable

    shortcut.TargetPath = pythonw_path
    shortcut.Arguments = f'"{target_pyw}"'
    shortcut.WorkingDirectory = base_dir
    shortcut.IconLocation = f"{icon_path}, 0"
    shortcut.Description = "企微恶搞防骚扰反制助手"
    shortcut.Save()
    print(f"[OK] Created desktop shortcut: {shortcut_path}")

if __name__ == "__main__":
    import sys
    create_desktop_shortcut()
