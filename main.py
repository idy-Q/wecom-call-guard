"""
企微防骚扰反制小助手 - 桌面 GUI 客户端 (main.py)
基于原生 Tkinter 构建，轻量免复杂依赖。
支持 MP3/WAV 播放、真实自然语音预置、在界面内实时输入文字一键合成 AI 语音！
支持自定义专属图标、任务栏标识、系统托盘常驻与默认后台挂载运行。
"""

import os
import sys
import time
import json
import threading
import ctypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk
import pystray

from guard_core import WeComGuardCore
from audio_player import AudioPlayer
from generate_cloud_tts import synthesize_text_to_mp3

# 设置 Windows 独立进程 AppID，彻底解决任务栏显示 Python 默认蛇标的问题
try:
    myappid = "antigravity.wecom.callguard.app.v1"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "window_config.json")

class WeComGuardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("企微防骚扰反制助手 (WeCom Call Guard)")
        self.root.minsize(720, 780)
        self.root.configure(bg="#F5F7FA")
        
        # 音频与素材目录
        self.assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        os.makedirs(self.assets_dir, exist_ok=True)
        
        # 设置专属窗口与任务栏图标
        self._apply_app_icon()
        
        # 初始化核心引擎
        self.guard = WeComGuardCore(log_callback=self._append_log)
        
        # 状态变量
        self.mode_var = tk.StringVar(value="operator")
        self.audio_choice_var = tk.StringVar()
        self.delay_var = tk.IntVar(value=8)
        self.auto_hide_var = tk.BooleanVar(value=True) # 默认启动守护后挂载到后台
        self.is_playing_preview = False
        self.audio_map = {}
        self.tray_icon = None
        
        # 扫描并加载音频列表
        self._refresh_audio_list()
        
        # 绘制界面
        self._init_ui()
        
        # 初始化系统托盘图标
        self._setup_system_tray()
        
        # 应用并锁定大窗口尺寸 (带记忆恢复)
        self._apply_geometry()
        self.root.after(100, self._apply_geometry)
        
        # 启动企微进程状态轮询
        self._check_wecom_status_loop()
        
        # 拦截右上角红叉：默认最小化到系统托盘挂载
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close_clicked)

    def _apply_app_icon(self):
        """设置窗口与任务栏专属图标"""
        ico_path = os.path.join(self.assets_dir, "icon.ico")
        png_path = os.path.join(self.assets_dir, "icon.png")
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass
        if os.path.exists(png_path):
            try:
                self.app_photo = ImageTk.PhotoImage(Image.open(png_path))
                self.root.iconphoto(False, self.app_photo)
            except Exception:
                pass

    def _apply_geometry(self):
        """恢复上次保存的窗口尺寸，默认大尺寸 920x1040 (高度加长)"""
        saved_geo = None
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    geo = cfg.get("geometry", "")
                    # 如果旧配置高度偏小(<1000)，自动升级到新的加长高度
                    if geo and "x" in geo:
                        dim = geo.split("+")[0]
                        w_str, h_str = dim.split("x")
                        if int(h_str) >= 1000:
                            saved_geo = geo
            except Exception:
                pass

        if saved_geo:
            try:
                self.root.geometry(saved_geo)
                return
            except Exception:
                pass

        # 默认匹配加长的大尺寸 (高度加长至 1040，彻底留足底部空间)
        w = 920
        h = 1040
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(5, (sh - h) // 2 - 25)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _refresh_audio_list(self):
        """扫描 assets 目录下的所有音频文件 (.mp3, .wav, .wma)"""
        self.audio_map = {}
        preset_names = {
            "10086_busy_natural.mp3": "🔥【真实占线】您拨打的用户正在通话中 (自然女声)",
            "teacher_calling_natural.mp3": "🔥【老师点名】请开麦回答大屏幕第三题 (自然女声)",
            "anti_fraud_natural.mp3": "🔥【官方反诈】高频呼叫预警模式 (自然女声)",
            "exam_listening_natural.mp3": "🔥【英语听力】硕士研究生考试英语听力 (自然女声)",
            "delivery_natural.mp3": "🔥【外卖小哥】外卖放在楼下外卖柜了 (自然女声)",
            "teacher_calling.wav": "【网课提问】机械音老版",
            "exam_listening.wav": "【英语听力】机械音老版",
            "telecom_fraud.wav": "【反诈警报】机械音老版",
            "alien_answering.wav": "【外星留言】按1听相声老版",
        }
        
        if os.path.exists(self.assets_dir):
            for fname in os.listdir(self.assets_dir):
                ext = os.path.splitext(fname)[1].lower()
                if ext in [".mp3", ".wav", ".wma", ".m4a"]:
                    display_name = preset_names.get(fname, f"【外部/自制】{fname}")
                    self.audio_map[display_name] = os.path.join(self.assets_dir, fname)
        
        # 默认选中第一个
        keys = list(self.audio_map.keys())
        if keys:
            if not self.audio_choice_var.get() or self.audio_choice_var.get() not in keys:
                self.audio_choice_var.set(keys[0])

    def _init_ui(self):
        # 顶部标题栏
        header_frame = tk.Frame(self.root, bg="#1E293B", pady=12, padx=16)
        header_frame.pack(fill="x")
        
        title_lbl = tk.Label(header_frame, text="🛡️ 企微防骚扰反制助手", font=("Microsoft YaHei UI", 14, "bold"), fg="#FFFFFF", bg="#1E293B")
        title_lbl.pack(anchor="w")
        
        sub_lbl = tk.Label(header_frame, text="支持自然人声预置、在线台词合成、自动秒接/秒挂与托盘静默后台挂载", font=("Microsoft YaHei UI", 9), fg="#94A3B8", bg="#1E293B")
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # 主内容区域
        main_container = tk.Frame(self.root, bg="#F5F7FA", padx=16, pady=12)
        main_container.pack(fill="both", expand=True)

        # 状态卡片
        status_card = tk.LabelFrame(main_container, text="系统状态", font=("Microsoft YaHei UI", 9, "bold"), bg="#FFFFFF", fg="#334155", padx=12, pady=8)
        status_card.pack(fill="x", pady=(0, 8))
        
        status_inner = tk.Frame(status_card, bg="#FFFFFF")
        status_inner.pack(fill="x")
        
        self.guard_status_indicator = tk.Label(status_inner, text="● 守护已停止", font=("Microsoft YaHei UI", 9, "bold"), fg="#EF4444", bg="#FFFFFF")
        self.guard_status_indicator.pack(side="left")
        
        self.wecom_status_indicator = tk.Label(status_inner, text="企微进程检测中...", font=("Microsoft YaHei UI", 9), fg="#64748B", bg="#FFFFFF")
        self.wecom_status_indicator.pack(side="right")

        # 模式选择卡片
        mode_card = tk.LabelFrame(main_container, text="反制模式选择", font=("Microsoft YaHei UI", 9, "bold"), bg="#FFFFFF", fg="#334155", padx=12, pady=8)
        mode_card.pack(fill="x", pady=(0, 8))

        r1 = tk.Radiobutton(mode_card, text="1. 赛博接线员 (自动秒接 + 扬声器播放反制音频 + 定时挂断)", 
                            variable=self.mode_var, value="operator", font=("Microsoft YaHei UI", 9), 
                            bg="#FFFFFF", activebackground="#FFFFFF", command=self._on_mode_change)
        r1.pack(anchor="w", pady=2)
        
        r2 = tk.Radiobutton(mode_card, text="2. 薛定谔秒挂 (接听瞬间0.2秒挂断)", 
                            variable=self.mode_var, value="instant_hangup", font=("Microsoft YaHei UI", 9), 
                            bg="#FFFFFF", activebackground="#FFFFFF", command=self._on_mode_change)
        r2.pack(anchor="w", pady=2)

        r3 = tk.Radiobutton(mode_card, text="3. 静音挂机流 (自动接听后保持沉默)", 
                            variable=self.mode_var, value="silent", font=("Microsoft YaHei UI", 9), 
                            bg="#FFFFFF", activebackground="#FFFFFF", command=self._on_mode_change)
        r3.pack(anchor="w", pady=2)

        # 参数配置卡片 (模式1专属)
        self.config_card = tk.LabelFrame(main_container, text="接线员参数设置", font=("Microsoft YaHei UI", 9, "bold"), bg="#FFFFFF", fg="#334155", padx=12, pady=8)
        self.config_card.pack(fill="x", pady=(0, 8))

        # 音频选择行
        audio_row = tk.Frame(self.config_card, bg="#FFFFFF")
        audio_row.pack(fill="x", pady=(0, 6))
        
        tk.Label(audio_row, text="反制音频:", font=("Microsoft YaHei UI", 9), bg="#FFFFFF", fg="#475569").pack(side="left")
        
        combo_values = list(self.audio_map.keys()) + ["【浏览本地音频...】"]
        self.audio_combo = ttk.Combobox(audio_row, textvariable=self.audio_choice_var, values=combo_values, state="readonly", width=28)
        self.audio_combo.pack(side="left", padx=(6, 6), fill="x", expand=True)
        self.audio_combo.bind("<<ComboboxSelected>>", self._on_audio_selected)
        
        self.preview_btn = tk.Button(audio_row, text="▶ 试听", font=("Microsoft YaHei UI", 8), bg="#E2E8F0", relief="flat", padx=6, pady=2, command=self._toggle_preview)
        self.preview_btn.pack(side="left", padx=(0, 4))

        open_folder_btn = tk.Button(audio_row, text="📂 目录", font=("Microsoft YaHei UI", 8), bg="#F1F5F9", fg="#475569", relief="flat", padx=5, pady=2, command=self._open_assets_folder)
        open_folder_btn.pack(side="left", padx=(0, 4))

        refresh_btn = tk.Button(audio_row, text="🔄 刷新", font=("Microsoft YaHei UI", 8), bg="#F1F5F9", fg="#475569", relief="flat", padx=5, pady=2, command=self._on_refresh_click)
        refresh_btn.pack(side="left")

        # 挂断延时行
        delay_row = tk.Frame(self.config_card, bg="#FFFFFF")
        delay_row.pack(fill="x")
        
        tk.Label(delay_row, text="播放时长:", font=("Microsoft YaHei UI", 9), bg="#FFFFFF", fg="#475569").pack(side="left")
        
        self.delay_scale = tk.Scale(delay_row, from_=3, to=30, orient="horizontal", variable=self.delay_var, bg="#FFFFFF", highlightthickness=0, fg="#334155")
        self.delay_scale.pack(side="left", fill="x", expand=True, padx=(8, 8))
        
        tk.Label(delay_row, text="秒后自动挂断", font=("Microsoft YaHei UI", 9), bg="#FFFFFF", fg="#64748B").pack(side="right")

        # 自定义台词在线合成卡片 (模式1专属)
        self.tts_card = tk.LabelFrame(main_container, text="✨ 在线AI台词合成 (输入任意内容一键生成音频)", font=("Microsoft YaHei UI", 9, "bold"), bg="#FFFFFF", fg="#334155", padx=10, pady=8)
        self.tts_card.pack(fill="x", pady=(0, 10))

        tts_row = tk.Frame(self.tts_card, bg="#FFFFFF")
        tts_row.pack(fill="x")

        self.placeholder_text = "请输入台词..."
        self.tts_entry = tk.Entry(tts_row, font=("Microsoft YaHei UI", 9), relief="solid", bd=1, fg="#94A3B8")
        self.tts_entry.insert(0, self.placeholder_text)
        self.tts_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=3)

        self.tts_entry.bind("<FocusIn>", self._on_tts_focus_in)
        self.tts_entry.bind("<FocusOut>", self._on_tts_focus_out)

        self.tts_gen_btn = tk.Button(tts_row, text="🎙️ 一键合成", font=("Microsoft YaHei UI", 9, "bold"), bg="#3B82F6", fg="#FFFFFF", relief="flat", padx=10, pady=3, cursor="hand2", command=self._generate_custom_tts)
        self.tts_gen_btn.pack(side="right")

        # 控制操作按钮栏
        btn_frame = tk.Frame(main_container, bg="#F5F7FA")
        btn_frame.pack(fill="x", pady=(0, 6))

        self.start_btn = tk.Button(btn_frame, text="🚀 启动防骚扰守护", font=("Microsoft YaHei UI", 10, "bold"), bg="#10B981", fg="#FFFFFF", relief="flat", pady=9, cursor="hand2", command=self._toggle_guard)
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.hide_tray_btn = tk.Button(btn_frame, text="🗔 挂载到后台", font=("Microsoft YaHei UI", 9), bg="#E2E8F0", fg="#334155", relief="flat", pady=9, cursor="hand2", command=self._hide_to_tray)
        self.hide_tray_btn.pack(side="left", padx=(0, 6))

        self.mock_btn = tk.Button(btn_frame, text="🛠️ 模拟测试一次", font=("Microsoft YaHei UI", 9), bg="#E2E8F0", fg="#334155", relief="flat", pady=9, cursor="hand2", command=self._run_mock_test)
        self.mock_btn.pack(side="right")

        # 后台运行偏好选项
        pref_frame = tk.Frame(main_container, bg="#F5F7FA")
        pref_frame.pack(fill="x", pady=(0, 6))
        
        chk_autohide = tk.Checkbutton(pref_frame, text="启动守护时自动隐藏至右下角系统托盘 (推荐后台挂载)", variable=self.auto_hide_var, font=("Microsoft YaHei UI", 8), bg="#F5F7FA", activebackground="#F5F7FA", fg="#475569")
        chk_autohide.pack(side="left")

        # 日志卡片
        log_card = tk.LabelFrame(main_container, text="实时拦截与运行日志", font=("Microsoft YaHei UI", 9, "bold"), bg="#FFFFFF", fg="#334155", padx=8, pady=6)
        log_card.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_card, bg="#0F172A", fg="#38BDF8", font=("Consolas", 9), relief="flat", padx=10, pady=8, wrap="word", height=11)
        self.log_text.pack(fill="both", expand=True)

        self._append_log("系统就绪。已启用专属安全盾牌图标与系统托盘后台挂载支持。")
        self._sync_config_to_guard()

    def _setup_system_tray(self):
        """配置并启动系统托盘图标"""
        png_path = os.path.join(self.assets_dir, "icon.png")
        if not os.path.exists(png_path):
            return

        tray_image = Image.open(png_path)

        def _get_toggle_text(item):
            return "⏹ 停止防骚扰守护" if self.guard.is_running else "🚀 启动防骚扰守护"

        tray_menu = pystray.Menu(
            pystray.MenuItem("🛡️ 显示主界面", self._tray_show_window, default=True),
            pystray.MenuItem("🗔 隐藏到后台托盘", self._tray_hide_window),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(_get_toggle_text, self._tray_toggle_guard),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ 彻底退出程序", self._tray_exit_app)
        )

        self.tray_icon = pystray.Icon("wecom_guard", tray_image, "企微防骚扰反制助手", tray_menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _tray_show_window(self, icon=None, item=None):
        self.root.after(0, self._show_window)

    def _tray_hide_window(self, icon=None, item=None):
        self.root.after(0, self._hide_to_tray)

    def _tray_toggle_guard(self, icon=None, item=None):
        self.root.after(0, self._toggle_guard)

    def _tray_exit_app(self, icon=None, item=None):
        self.root.after(0, self._force_quit)

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _hide_to_tray(self):
        self._append_log("📌 界面已挂载至右下角系统托盘后台静默运行 (双击托盘图标可唤出)。")
        self.root.withdraw()

    def _on_window_close_clicked(self):
        """点击右上角红叉：默认最小化到系统托盘继续守护"""
        self._hide_to_tray()

    def _on_tts_focus_in(self, event):
        if self.tts_entry.get() == self.placeholder_text:
            self.tts_entry.delete(0, tk.END)
            self.tts_entry.config(fg="#0F172A")

    def _on_tts_focus_out(self, event):
        if not self.tts_entry.get().strip():
            self.tts_entry.delete(0, tk.END)
            self.tts_entry.insert(0, self.placeholder_text)
            self.tts_entry.config(fg="#94A3B8")

    def _generate_custom_tts(self):
        """在线合成自定义台词并添加到曲库"""
        raw_text = self.tts_entry.get().strip()
        if not raw_text or raw_text == self.placeholder_text:
            messagebox.showwarning("提示", "请输入要合成的反制台词！")
            return
        text = raw_text

        self.tts_gen_btn.config(state="disabled", text="合成中...")
        self._append_log(f"正在合成自定义语音: '{text}' ...")

        def _do_synth():
            filename = f"custom_{int(time.time())}.mp3"
            filepath = os.path.join(self.assets_dir, filename)
            success = synthesize_text_to_mp3(text, filepath)
            
            def _update_ui():
                self.tts_gen_btn.config(state="normal", text="🎙️ 一键合成")
                if success:
                    self._refresh_audio_list()
                    display_key = f"【自制】{text[:12]}..." if len(text) > 12 else f"【自制】{text}"
                    self.audio_map[display_key] = filepath
                    self.audio_combo["values"] = list(self.audio_map.keys()) + ["【浏览本地音频...】"]
                    self.audio_choice_var.set(display_key)
                    self._sync_config_to_guard()
                    self._append_log(f"✅ 合成成功！已自动选中新音频，可点击【▶ 试听】。")
                else:
                    self._append_log("❌ 合成失败，请检查网络连接。")

            self.root.after(0, _update_ui)

        threading.Thread(target=_do_synth, daemon=True).start()

    def _open_assets_folder(self):
        """一键打开音频文件夹"""
        try:
            os.startfile(self.assets_dir)
            self._append_log(f"已打开音频目录: {self.assets_dir}")
        except Exception as e:
            self._append_log(f"打开目录失败: {e}")

    def _on_refresh_click(self):
        """刷新音频列表"""
        self._refresh_audio_list()
        combo_values = list(self.audio_map.keys()) + ["【浏览本地音频...】"]
        self.audio_combo["values"] = combo_values
        self._sync_config_to_guard()
        self._append_log(f"已刷新音频库，当前共 {len(self.audio_map)} 个音频可用。")

    def _sync_config_to_guard(self):
        """同步 UI 配置到核心引擎"""
        self.guard.mode = self.mode_var.get()
        self.guard.hangup_delay = self.delay_var.get()
        
        selected_key = self.audio_choice_var.get()
        if selected_key in self.audio_map:
            self.guard.audio_path = self.audio_map[selected_key]
        elif hasattr(self, "custom_audio_path"):
            self.guard.audio_path = self.custom_audio_path

    def _on_mode_change(self):
        mode = self.mode_var.get()
        if mode == "operator":
            self.config_card.pack(fill="x", pady=(0, 8), before=self.tts_card)
            self.tts_card.pack(fill="x", pady=(0, 8), before=self.start_btn.master)
        else:
            self.config_card.pack_forget()
            self.tts_card.pack_forget()
        self._sync_config_to_guard()
        self._append_log(f"已切换模式至: {self.guard._get_mode_desc()}")

    def _on_audio_selected(self, event=None):
        choice = self.audio_choice_var.get()
        if "浏览本地" in choice:
            filepath = filedialog.askopenfilename(
                title="选择本地反制音频 (支持 MP3/WAV)",
                filetypes=[("音频文件", "*.mp3 *.wav *.wma *.m4a"), ("所有文件", "*.*")]
            )
            if filepath:
                self.custom_audio_path = filepath
                fname = os.path.basename(filepath)
                display_key = f"【外部】{fname}"
                self.audio_map[display_key] = filepath
                self.audio_combo["values"] = list(self.audio_map.keys()) + ["【浏览本地音频...】"]
                self.audio_choice_var.set(display_key)
                self._append_log(f"已载入自定义音频: {filepath}")
            else:
                self._on_refresh_click()
        self._sync_config_to_guard()

    def _toggle_preview(self):
        if not self.is_playing_preview:
            self._sync_config_to_guard()
            if self.guard.audio_path and os.path.exists(self.guard.audio_path):
                self.is_playing_preview = True
                self.preview_btn.config(text="⏹ 停止", bg="#FCA5A5")
                self._append_log(f"正在试听音频: {os.path.basename(self.guard.audio_path)}")
                AudioPlayer.play(self.guard.audio_path)
            else:
                messagebox.showwarning("提示", "音频文件不存在！")
        else:
            self.is_playing_preview = False
            self.preview_btn.config(text="▶ 试听", bg="#E2E8F0")
            AudioPlayer.stop()
            self._append_log("已停止音频试听。")

    def _toggle_guard(self):
        if not self.guard.is_running:
            self._sync_config_to_guard()
            self.guard.start()
            self.guard_status_indicator.config(text="● 守护运行中 (监听来电)", fg="#10B981")
            self.start_btn.config(text="⏹ 停止守护", bg="#EF4444")
            if self.tray_icon:
                self.tray_icon.title = "企微防骚扰反制助手 (守护运行中)"
            
            # 如果勾选了自动挂载后台，自动隐藏窗口
            if self.auto_hide_var.get():
                self.root.after(300, self._hide_to_tray)
        else:
            self.guard.stop()
            self.guard_status_indicator.config(text="● 守护已停止", fg="#EF4444")
            self.start_btn.config(text="🚀 启动防骚扰守护", bg="#10B981")
            if self.tray_icon:
                self.tray_icon.title = "企微防骚扰反制助手 (已停止)"

    def _run_mock_test(self):
        self._sync_config_to_guard()
        self.guard.test_mock_trigger()

    def _check_wecom_status_loop(self):
        def _check():
            while True:
                is_running = self.guard.is_wecom_running()
                if is_running:
                    self.wecom_status_indicator.config(text="企微状态: 正在运行 (PC在线)", fg="#10B981")
                else:
                    self.wecom_status_indicator.config(text="企微状态: 未检测到运行", fg="#94A3B8")
                time.sleep(3)

        threading.Thread(target=_check, daemon=True).start()

    def _append_log(self, text):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def _force_quit(self):
        """彻底退出程序"""
        try:
            curr_geo = self.root.geometry()
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"geometry": curr_geo}, f, ensure_ascii=False)
        except Exception:
            pass

        if self.guard.is_running:
            self.guard.stop()
        AudioPlayer.stop()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.destroy()
        sys.exit(0)

def ensure_single_instance():
    """确保单实例运行，清理之前可能残留在后台运行的旧版本守护进程"""
    curr_pid = os.getpid()
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if p.info['pid'] != curr_pid and p.info['name'] and 'python' in p.info['name'].lower():
                    cmd = ' '.join(p.info.get('cmdline') or [])
                    if 'main.py' in cmd:
                        p.terminate()
            except Exception:
                pass
    except Exception:
        pass

if __name__ == "__main__":
    ensure_single_instance()
    root = tk.Tk()
    app = WeComGuardApp(root)
    root.mainloop()

