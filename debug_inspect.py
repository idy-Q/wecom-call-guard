"""
企业微信窗口与呼叫探针调试工具 (debug_inspect.py)
用于一键排查当前系统中的企业微信进程、窗口、UIA 属性与尺寸。
"""

import sys
import time
import ctypes
from ctypes import wintypes
import psutil

try:
    import uiautomation as auto
except ImportError:
    auto = None

user32 = ctypes.windll.user32
GW_CHILD = 5
GW_HWNDNEXT = 2

def inspect():
    print("=" * 60)
    print("【企业微信防骚扰助手 - 实时窗口与进程探针】")
    print("=" * 60)
    
    # 1. 进程检查
    wecom_procs = []
    for p in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            pname = p.info['name']
            if pname and any(k in pname.lower() for k in ['wxwork', 'wemeet', 'wwm']):
                wecom_procs.append((p.info['pid'], pname, p.info.get('exe', '')))
        except:
            pass

    print(f"\n[1] 正在运行的企微相关进程 ({len(wecom_procs)} 个):")
    for pid, name, path in wecom_procs:
        print(f"  - PID {pid:6d} | {name:20s} | {path}")

    if not wecom_procs:
        print("  ⚠️ 未检测到企业微信运行！请先启动企业微信。")

    # 2. 窗口检查
    print(f"\n[2] 当前可见的企业微信/腾讯会议窗口扫描:")
    hwnd = user32.GetWindow(user32.GetDesktopWindow(), GW_CHILD)
    count = 0
    found_any = False

    while hwnd:
        try:
            if user32.IsWindowVisible(hwnd):
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                try:
                    p = psutil.Process(pid.value)
                    pname = p.name()
                except:
                    pname = ""

                if pname and any(k in pname.lower() for k in ['wxwork', 'wemeet', 'wwm']):
                    found_any = True
                    rect = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top

                    t_buf = ctypes.create_unicode_buffer(512)
                    user32.GetWindowTextW(hwnd, t_buf, 512)
                    c_buf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, c_buf, 256)

                    # 尝试 UIA 提取文本
                    texts = []
                    if auto:
                        try:
                            ctrl = auto.ControlFromHandle(hwnd)
                            if ctrl:
                                for c in ctrl.GetChildren():
                                    if c.Name:
                                        texts.append(c.Name.strip())
                        except:
                            pass

                    print(f"\n  [窗口 HWND: {hwnd}]")
                    print(f"    - 进程: {pname} (PID: {pid.value})")
                    print(f"    - 类名: {c_buf.value}")
                    print(f"    - 标题: '{t_buf.value}'")
                    print(f"    - 尺寸: {w}x{h}  位置: ({rect.left}, {rect.top}) ~ ({rect.right}, {rect.bottom})")
                    if texts:
                        print(f"    - UIA内部文本: {texts[:10]}")
                    else:
                        print(f"    - UIA内部文本: (无暴露文本，属于 DirectUI 自绘)")
                    
                    if 180 <= w <= 650 and 100 <= h <= 450:
                        print(f"    💡 [命中呼叫/会议卡片特征区间！]")
        except:
            pass
        hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)

    if not found_any:
        print("  当前未发现任何处于前台/可见的企微窗口（企微可能处于托盘后台或最小化）。")
    print("\n" + "=" * 60)

if __name__ == "__main__":
    inspect()
