"""
企业微信来电/会议守护核心模块 (guard_core.py)
深度全场景覆盖：
1. 快速会议：精准匹配文字与右下角“进入会议”按钮，毫秒级进入
2. 语音通话：精准匹配“邀请你语音通话”卡片，毫秒级点击绿色接听按钮
3. 视频通话：精准匹配“邀请你视频通话”卡片，直接秒点红色拒绝按钮掐断（绝不让对方看笑话）
4. 无文本 DirectUI 兜底：基于企微多进程识别 + 弹窗物理尺寸特征 + 坐标双重点击保障
"""

import os
import sys
import time
import threading
import ctypes
from ctypes import wintypes
import psutil

try:
    import uiautomation as auto
except ImportError:
    auto = None

# 加载系统底层 user32
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# 窗口遍历常量
GW_CHILD = 5
GW_HWNDNEXT = 2
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = -1

# 接听/进入会议的关键词池
ACCEPT_KEYWORDS = [
    "进入会议", "进入", "加入会议", "加入", "立即加入",
    "接听", "接通", "入会", "接受邀请", "接受"
]

# 挂断/离开会议的关键词池
HANGUP_KEYWORDS = [
    "离开会议", "结束会议", "暂不进入", "离开", "挂断", "结束通话", "退出会议", "拒绝"
]

class WeComGuardCore:
    def __init__(self, log_callback=None):
        """
        :param log_callback: 日志回调函数 func(msg, level)
        """
        self.log_callback = log_callback
        self.is_running = False
        self._thread = None
        
        # 运行配置
        self.mode = "operator"  # "operator"(赛博接线员), "instant_hangup"(薛定谔秒挂), "silent"(静音挂机)
        self.audio_path = ""
        self.hangup_delay = 8   # 赛博接线员播放多少秒后自动挂断
        
        # 状态记录，防止瞬间重复处理同一个窗口
        self.last_handled_hwnd = None
        self.last_handled_time = 0
        
    def log(self, message, level="INFO"):
        if self.log_callback:
            timestamp = time.strftime("%H:%M:%S")
            self.log_callback(f"[{timestamp}] [{level}] {message}")
        else:
            print(f"[{level}] {message}")

    @staticmethod
    def is_wecom_process_name(name):
        """检查进程名是否属于企业微信或腾讯会议生态"""
        if not name:
            return False
        nl = name.lower()
        return any(k in nl for k in ["wxwork", "wemeet", "wwm", "wmexternal"])

    def is_wecom_running(self):
        """检查企业微信或会议进程是否存在"""
        try:
            for proc in psutil.process_iter(['name']):
                pname = proc.info.get('name')
                if self.is_wecom_process_name(pname):
                    return True
        except Exception:
            pass
        return False

    def start(self):
        """启动后台监听"""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self.log("🚀 防骚扰守护引擎已启动，已开启 0.15s 极速全维监听...")

    def stop(self):
        """停止后台监听"""
        self.is_running = False
        try:
            from audio_player import AudioPlayer
            AudioPlayer.stop()
        except Exception:
            pass
        self.log("防骚扰守护引擎已停止。")

    def _monitor_loop(self):
        """主轮询循环 (0.15s 极速响应)"""
        while self.is_running:
            try:
                self._detect_and_handle_call()
            except Exception as e:
                pass
            time.sleep(0.15)

    def _get_wecom_candidate_windows(self):
        """
        通过 Windows API 链表遍历，100% 稳定枚举顶层企微窗口，
        彻底规避 win32gui.EnumWindows 在高频调用下的内存/句柄溢出崩溃。
        """
        candidates = []
        try:
            # 确保当前线程绑定在正确桌面
            hdesk = user32.OpenDesktopW("Default", 0, False, 0x10000000 | 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
        except Exception:
            pass

        hwnd = user32.GetWindow(user32.GetDesktopWindow(), GW_CHILD)
        
        while hwnd:
            try:
                if user32.IsWindowVisible(hwnd):
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    
                    try:
                        p = psutil.Process(pid.value)
                        pname = p.name()
                    except Exception:
                        pname = None

                    if self.is_wecom_process_name(pname):
                        rect = wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        w = rect.right - rect.left
                        h = rect.bottom - rect.top

                        # 过滤掉企微的主界面（大尺寸）与极小的托盘图标/阴影
                        # 呼叫/会议卡片尺寸范围在 180<=w<=600 且 100<=h<=420
                        if 180 <= w <= 650 and 100 <= h <= 450:
                            t_buf = ctypes.create_unicode_buffer(512)
                            user32.GetWindowTextW(hwnd, t_buf, 512)
                            c_buf = ctypes.create_unicode_buffer(256)
                            user32.GetClassNameW(hwnd, c_buf, 256)
                            candidates.append({
                                "hwnd": hwnd,
                                "pname": pname,
                                "pid": pid.value,
                                "title": t_buf.value,
                                "class": c_buf.value,
                                "w": w,
                                "h": h,
                                "rect": (rect.left, rect.top, rect.right, rect.bottom)
                            })
            except Exception:
                pass
            hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)

        return candidates

    def _get_all_texts_and_buttons(self, parent_ctrl, max_depth=6):
        """深度遍历提取窗口内所有文本和按钮控件"""
        texts = []
        buttons = []
        if not parent_ctrl:
            return texts, buttons

        stack = [(parent_ctrl, 0)]
        while stack:
            ctrl, depth = stack.pop()
            if depth > max_depth:
                continue
            try:
                name = ctrl.Name
                auto_id = ctrl.AutomationId
                c_type = ctrl.ControlTypeName

                if name and name.strip():
                    texts.append(name.strip())
                if auto_id and auto_id.strip():
                    texts.append(auto_id.strip())

                if "Button" in c_type:
                    buttons.append(ctrl)

                if depth < max_depth:
                    for child in ctrl.GetChildren():
                        stack.append((child, depth + 1))
            except Exception:
                pass
        return texts, buttons

    def _detect_and_handle_call(self):
        """
        全场景呼叫检测 (语音通话 / 视频通话 / 快速会议)
        """
        # 如果距离上次处理时间不足 3 秒，暂时冷却
        if time.time() - self.last_handled_time < 3:
            return

        candidates = self._get_wecom_candidate_windows()
        if not candidates:
            return

        for win in candidates:
            hwnd = win["hwnd"]
            if hwnd == self.last_handled_hwnd and (time.time() - self.last_handled_time < 5):
                continue

            w = win["w"]
            h = win["h"]
            rect = win["rect"]
            title = win["title"]
            pname = win["pname"]

            # 尝试通过 UIA 抓取内部文本与按钮控件
            win_ctrl = None
            texts = []
            buttons = []
            if auto:
                try:
                    win_ctrl = auto.ControlFromHandle(hwnd)
                    if win_ctrl and win_ctrl.Exists(0, 0):
                        texts, buttons = self._get_all_texts_and_buttons(win_ctrl)
                except Exception:
                    pass

            full_text = " ".join(texts) + " " + title

            # 排除已明确结束的记录
            if any(end_kw in full_text for end_kw in ["已结束", "通话结束", "会议已结束", "已离开"]):
                continue

            # ------------------------------------------------------------------
            # 场景 1：【视频通话】直接秒拒（绝不接通，不给对方看笑话）
            # ------------------------------------------------------------------
            is_video = ("视频通话" in full_text or "邀请你视频通话" in full_text or "视频" in full_text)
            if is_video:
                self.last_handled_hwnd = hwnd
                self.last_handled_time = time.time()
                self.log(f"📹 捕获到企微【视频通话】来电！(HWND: {hwnd}, 尺寸: {w}x{h})", "VIDEO_REJECT")
                self.log("🛡️ 已触发视频防窥保护：执行直接秒拒策略！")

                # 优先点击“拒绝”文本按钮，否则点击左侧红色圆形拒绝位置
                reject_btn = self._find_button_by_keywords_list(buttons, ["拒绝", "挂断", "暂不进入", "取消"])
                if reject_btn:
                    self._click_control(reject_btn, hwnd)
                else:
                    # 红色圆形拒绝按钮固定在左侧偏中 (rect[0] + W * 0.60, rect[1] + H * 0.72)
                    red_x = rect[0] + int(w * 0.60)
                    red_y = rect[1] + int(h * 0.72)
                    self._click_control((red_x, red_y), hwnd)
                self.log("🚫 已自动点击红色【拒绝】按钮，视频通话已被秒断！")
                break

            # ------------------------------------------------------------------
            # 场景 2：【快速会议】明确命中
            # ------------------------------------------------------------------
            is_meeting = any(k in full_text for k in ["快速会议", "进入会议", "加入会议", "邀请你进入会议", "会议"])
            
            # ------------------------------------------------------------------
            # 场景 3：【语音通话】明确命中
            # ------------------------------------------------------------------
            is_voice = any(k in full_text for k in ["语音通话", "邀请你语音通话", "语音"])

            # ------------------------------------------------------------------
            # 场景 4：DirectUI 悬浮卡片智能特征命中 (即使 UIA 无法读取文本)
            # ------------------------------------------------------------------
            is_fallback_popup = False
            # 特征：属于企微、尺寸在典型卡片范围(200-480x120-320)、非结束卡片
            if not is_meeting and not is_voice:
                if 200 <= w <= 500 and 120 <= h <= 340:
                    is_fallback_popup = True

            if is_meeting or is_voice or is_fallback_popup:
                self.last_handled_hwnd = hwnd
                self.last_handled_time = time.time()
                
                call_type_desc = "快速会议" if is_meeting else ("语音通话" if is_voice else "企微呼叫卡片")
                self.log(f"⚡ 成功捕获企微【{call_type_desc}】！(进程: {pname}, 尺寸: {w}x{h})", "TRIGGER")

                # 寻找接听目标
                accept_target = None

                # 1. 优先通过关键词在 Button 中精确搜索
                matched_btn = self._find_button_by_keywords_list(buttons, ACCEPT_KEYWORDS)
                if matched_btn:
                    accept_target = matched_btn
                    self.log(f"🎯 命中接听按钮控件: '{matched_btn.Name or 'Button'}'")
                elif buttons:
                    # 如果有按钮但没有文本，呼叫卡片的接听按钮总是排在最右侧
                    rightmost_btn = max(buttons, key=lambda b: getattr(b.BoundingRectangle, 'right', 0))
                    accept_target = rightmost_btn
                    self.log("🎯 锁定最右侧操作按钮执行点击！")
                else:
                    # 2. 坐标兜底计算
                    if is_meeting:
                        # 快速会议右下角“进入会议”按钮 (W * 0.76, H * 0.78)
                        gx = rect[0] + int(w * 0.76)
                        gy = rect[1] + int(h * 0.78)
                    else:
                        # 语音通话右下角绿色圆形接听按钮 (W * 0.82, H * 0.72)
                        gx = rect[0] + int(w * 0.82)
                        gy = rect[1] + int(h * 0.72)
                    accept_target = (gx, gy)
                    self.log(f"🎯 锁定接听物理绝对坐标 ({gx}, {gy}) 执行精准毫秒级点击！")

                self._execute_action(hwnd, win_ctrl, accept_target)
                break

    def _find_button_by_keywords_list(self, buttons, keywords):
        """在已知按钮列表中匹配关键词"""
        for btn in buttons:
            try:
                name = btn.Name or ""
                auto_id = btn.AutomationId or ""
                for kw in keywords:
                    if kw in name or kw in auto_id:
                        return btn
            except Exception:
                pass
        return None

    def _execute_action(self, hwnd, win_ctrl, accept_target):
        """执行用户选择的反制战术"""
        self.log(f"执行战术: 【{self._get_mode_desc()}】")

        if self.mode == "operator":
            # 模式 1：赛博接线员 (接听 + 播放音频 + 延时挂断)
            self._handle_operator_mode(hwnd, win_ctrl, accept_target)
            
        elif self.mode == "instant_hangup":
            # 模式 2：薛定谔秒挂 (接听瞬间0.2秒挂断)
            self._handle_instant_hangup_mode(hwnd, win_ctrl, accept_target)
            
        elif self.mode == "silent":
            # 模式 3：静音消耗 (接听后保持沉默)
            self._handle_silent_mode(hwnd, win_ctrl, accept_target)

    def _handle_operator_mode(self, hwnd, win_ctrl, accept_target):
        """执行赛博接线员"""
        try:
            self.log("正在自动点击【接听/进入】...")
            self._click_control(accept_target, hwnd)
            self.log("✅ 已执行接听指令！")
        except Exception as e:
            self.log(f"点击接听失败: {e}", "ERROR")
            return

        # 启动音频播放
        if self.audio_path and os.path.exists(self.audio_path):
            self.log(f"🔊 正在外放反制音频: {os.path.basename(self.audio_path)}")
            try:
                from audio_player import AudioPlayer
                AudioPlayer.play(self.audio_path)
            except Exception as e:
                self.log(f"音频播放异常: {e}", "WARN")
        else:
            self.log("未指定音频文件，跳过音频播放。", "WARN")

        # 开启后台倒计时挂断线程
        threading.Thread(target=self._countdown_and_hangup, args=(self.hangup_delay,), daemon=True).start()

    def _countdown_and_hangup(self, delay):
        """倒计时并在时间到达后点击挂断/离开会议"""
        self.log(f"将在 {delay} 秒后自动执行退会/挂断...")
        time.sleep(delay)
        
        self.log("⏰ 设定时间到，正在寻找【离开会议/挂断】按钮...")
        hung_up = self._find_and_click_hangup()
        if hung_up:
            self.log("🎉 已自动结束通话/退出会议！恶作剧已被优雅瓦解。")
        else:
            self.log("未检测到悬浮挂断按钮，对方可能已被反制音频震慑并主动挂断。", "INFO")

    def _handle_instant_hangup_mode(self, hwnd, win_ctrl, accept_target):
        """执行薛定谔秒挂"""
        try:
            self.log("正在点击【接听】建立握手连接...")
            self._click_control(accept_target, hwnd)
            time.sleep(0.2)
            self.log("⚡ 0.2秒已到，正在执行瞬间掐断...")
            hung_up = self._find_and_click_hangup()
            if hung_up:
                self.log("🎉 瞬间秒挂成功！对方通话记录已锁定 00:00 秒。")
            else:
                try:
                    # 尝试兜底发 WM_CLOSE 给该窗口
                    user32.PostMessageW(hwnd, 0x0010, 0, 0)
                except Exception:
                    pass
        except Exception as e:
            self.log(f"秒挂操作失败: {e}", "ERROR")

    def _handle_silent_mode(self, hwnd, win_ctrl, accept_target):
        """静音消耗流"""
        try:
            self.log("正在自动点击【接听】...")
            self._click_control(accept_target, hwnd)
            self.log("✅ 已接通，请保持沉默，静静消耗对方手机电量与屏幕时间。")
        except Exception as e:
            self.log(f"接听失败: {e}", "ERROR")

    def _find_and_click_hangup(self):
        """全屏搜索属于企微与腾讯会议的离开/挂断按钮"""
        try:
            hwnd = user32.GetWindow(user32.GetDesktopWindow(), GW_CHILD)
            while hwnd:
                try:
                    if user32.IsWindowVisible(hwnd):
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        try:
                            p = psutil.Process(pid.value)
                            pname = p.name()
                        except Exception:
                            pname = None

                        if self.is_wecom_process_name(pname):
                            rect = wintypes.RECT()
                            user32.GetWindowRect(hwnd, ctypes.byref(rect))
                            w = rect.right - rect.left
                            h = rect.bottom - rect.top

                            # 尝试 UIA 查找
                            if auto:
                                try:
                                    ctrl = auto.ControlFromHandle(hwnd)
                                    if ctrl and ctrl.Exists(0, 0):
                                        texts, buttons = self._get_all_texts_and_buttons(ctrl, max_depth=5)
                                        btn = self._find_button_by_keywords_list(buttons, HANGUP_KEYWORDS)
                                        if btn:
                                            self._click_control(btn, hwnd)
                                            return True
                                except Exception:
                                    pass

                            # 兜底：如果是通话小浮窗 (宽 200~600, 高 150~600)
                            if 200 <= w <= 650 and 120 <= h <= 600:
                                # 红色挂断按钮通常居中靠下 (W * 0.50, H * 0.80)
                                mid_x = rect.left + int(w * 0.50)
                                mid_y = rect.top + int(h * 0.80)
                                self._click_control((mid_x, mid_y), hwnd)
                                return True
                except Exception:
                    pass
                hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)
        except Exception:
            pass
        return False

    def _click_control(self, ctrl_or_point, hwnd=None):
        """安全高效点击：置顶 + 物理鼠标移动点击 + 消息双保险 + 双脉冲"""
        if hwnd:
            try:
                # 穿透置顶与焦点限制
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
            except Exception:
                pass

        cx, cy = 0, 0
        if isinstance(ctrl_or_point, tuple):
            cx, cy = ctrl_or_point
        elif ctrl_or_point:
            try:
                rect = ctrl_or_point.BoundingRectangle
                if rect.width() > 0 and rect.height() > 0:
                    cx = (rect.left + rect.right) // 2
                    cy = (rect.top + rect.bottom) // 2
            except Exception:
                pass

        # 优先触发 UIA 原生控件 Click
        if hasattr(ctrl_or_point, 'Click'):
            try:
                ctrl_or_point.Click()
            except Exception:
                pass

        # 物理坐标双击脉冲（间隔 60ms 点两次，防止淡入动画吞帧）
        if cx > 0 and cy > 0:
            try:
                if auto:
                    auto.Click(cx, cy)
                    time.sleep(0.06)
                    auto.Click(cx, cy)
                else:
                    # 备用方案：通过 win32 api mouse_event
                    user32.SetCursorPos(cx, cy)
                    user32.mouse_event(0x0002, 0, 0, 0, 0) # DOWN
                    user32.mouse_event(0x0004, 0, 0, 0, 0) # UP
                    time.sleep(0.06)
                    user32.mouse_event(0x0002, 0, 0, 0, 0)
                    user32.mouse_event(0x0004, 0, 0, 0, 0)
            except Exception:
                pass

        # 消息双保险
        if hwnd and cx > 0 and cy > 0:
            try:
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                rel_x = cx - rect.left
                rel_y = cy - rect.top
                lparam = (rel_y << 16) | (rel_x & 0xFFFF)
                user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
                user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
            except Exception:
                pass

        return True

    def _get_mode_desc(self):
        if self.mode == "operator":
            return "赛博接线员 (自动秒接+音频反制)"
        elif self.mode == "instant_hangup":
            return "薛定谔秒挂 (接听瞬间0.2秒挂断)"
        elif self.mode == "silent":
            return "静音挂机流 (自动接听后保持沉默)"
        return "未知模式"

    def test_mock_trigger(self):
        """模拟测试触发"""
        self.log("🛠️ 触发模拟演练测试...", "TEST")
        if self.mode == "operator":
            self.log(f"演练当前模式: 【赛博接线员】")
            if self.audio_path and os.path.exists(self.audio_path):
                self.log(f"🔊 演练播放音频: {os.path.basename(self.audio_path)}")
                from audio_player import AudioPlayer
                AudioPlayer.play(self.audio_path)
            threading.Thread(target=self._countdown_and_hangup, args=(self.hangup_delay,), daemon=True).start()
        elif self.mode == "instant_hangup":
            self.log(f"演练当前模式: 【薛定谔秒挂】")
            self.log("模拟执行: 建立握手连接 -> 0.2秒瞬间掐断机制已就绪！")
        else:
            self.log("演练当前模式: 【静音挂机】")
