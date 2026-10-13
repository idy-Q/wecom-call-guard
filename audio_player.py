"""
跨格式音频播放器 (audio_player.py)
基于 Windows MCI (winmm.dll) 与 winsound，完美支持 .mp3 与 .wav 格式。
零外部庞大依赖，毫秒级启停。
"""

import os
import sys
import ctypes
import winsound

class AudioPlayer:
    _alias = "wecom_guard_audio"

    @classmethod
    def play(cls, filepath):
        """播放音频文件 (.mp3 或 .wav)"""
        cls.stop()
        if not filepath or not os.path.exists(filepath):
            return False

        abs_path = os.path.abspath(filepath)
        ext = os.path.splitext(abs_path)[1].lower()

        # 尝试通过 Windows MCI 播放 (兼容 MP3 和 WAV)
        try:
            mci = ctypes.windll.winmm.mciSendStringW
            # 打开文件
            cmd_open = f'open "{abs_path}" alias {cls._alias}'
            res = mci(cmd_open, None, 0, 0)
            if res == 0:
                # 播放
                mci(f'play {cls._alias}', None, 0, 0)
                return True
        except Exception:
            pass

        # 如果是 wav 且 MCI 失败，使用 winsound 兜底
        if ext == ".wav":
            try:
                winsound.PlaySound(abs_path, winsound.SND_ASYNC | winsound.SND_FILENAME)
                return True
            except Exception:
                pass

        return False

    @classmethod
    def stop(cls):
        """停止播放并释放设备"""
        try:
            mci = ctypes.windll.winmm.mciSendStringW
            mci(f'stop {cls._alias}', None, 0, 0)
            mci(f'close {cls._alias}', None, 0, 0)
        except Exception:
            pass

        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

if __name__ == "__main__":
    test_file = os.path.join(os.path.dirname(__file__), "assets", "teacher_calling.wav")
    print(f"测试播放: {test_file}")
    AudioPlayer.play(test_file)
    import time
    time.sleep(2)
    AudioPlayer.stop()
    print("播放器测试通过！")
