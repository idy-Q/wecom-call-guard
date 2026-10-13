"""
生成预置恶搞反制音频的离线生成器
调用 Windows 内置 SAPI.SpVoice 引擎，纯本地离线合成，无需网络下载
"""
import os
import wave
import win32com.client

AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(AUDIO_DIR, exist_ok=True)

# 待生成的音频文本及配置
PRESETS = {
    "teacher_calling.wav": "刚才进入会议的这位同学，请你立刻打开麦克风，回答一下大屏幕上的第三题。听到了请回答。",
    "exam_listening.wav": "全国硕士研究生招生考试，英语听力测试现在开始。Section A. Directions: In this section, you will hear several conversations. Please answer the questions. Question 1.",
    "telecom_fraud.wav": "国家反诈中心特别提醒：系统检测到当前线路呼叫频次异常，已对本次恶作剧通话进行全程录音备案。请立即停止无意义呼叫。",
    "alien_answering.wav": "您好，机主已被外星科技接管。按1听相声，按2开始背诵出师表，按3自动扣除你的一只冰淇淋。哔声后请开始留言。"
}

def generate_audio():
    # 创建 SAPI 声音对象和文件流
    speaker = win32com.client.Dispatch("SAPI.SpVoice")
    filestream = win32com.client.Dispatch("SAPI.SpFileStream")
    
    # 查找中文或默认的声音引擎
    voices = speaker.GetVoices()
    print(f"检测到系统可用语音数: {len(voices)}")

    for filename, text in PRESETS.items():
        filepath = os.path.join(AUDIO_DIR, filename)
        # SSFMCreateForWrite = 3
        filestream.Open(filepath, 3, False)
        speaker.AudioOutputStream = filestream
        speaker.Speak(text)
        filestream.Close()
        print(f"已生成音频: {filepath}")

if __name__ == "__main__":
    generate_audio()
