"""
使用微软高拟真 Edge-TTS 引擎生成高清广播级恶搞音频
包含：中国移动真实占线音、严肃高校老师点名、经典英语听力播音、房产中介真实推销
"""

import asyncio
import os
import edge_tts

AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(AUDIO_DIR, exist_ok=True)

# 音频列表配置 (文本, 拟真音色, 语速调节)
HD_PRESETS = [
    {
        "filename": "10086_busy.mp3",
        "voice": "zh-CN-XiaoxiaoNeural", # 官方客服温柔女声
        "rate": "+0%",
        "text": "对不起，您拨打的用户正在通话中，请稍后再拨。Sorry, the number you dialed is busy now, please redial later."
    },
    {
        "filename": "teacher_stern.mp3",
        "voice": "zh-CN-YunxiNeural",    # 青年严肃男声
        "rate": "+0%",
        "text": "这位同学，你既然进会议了就先别急着退。大屏幕上的第三小题你来作答一下。听到了请开麦回答。"
    },
    {
        "filename": "exam_listening.mp3",
        "voice": "zh-CN-XiaoyiNeural",   # 广播播音女声
        "rate": "-5%",
        "text": "全国硕士研究生招生考试，英语听力测试现在开始。Directions: In this section, you will hear several conversations. Question 1: What is the speaker's main purpose?"
    },
    {
        "filename": "estate_call.mp3",
        "voice": "zh-CN-YunyangNeural",  # 专业推销男声
        "rate": "+5%",
        "text": "喂，哥，不好意思打扰了啊！看您之前在系统里关注过咱们科技城核心区的大平层，今天开发商有专属特价房源，您看这周末方便来看看吗？"
    }
]

async def generate_all():
    for item in HD_PRESETS:
        target_path = os.path.join(AUDIO_DIR, item["filename"])
        print(f"正在生成高清音频: {item['filename']} (音色: {item['voice']})...")
        communicate = edge_tts.Communicate(item["text"], item["voice"], rate=item["rate"])
        await communicate.save(target_path)
        print(f"✅ 生成成功: {target_path}")

if __name__ == "__main__":
    asyncio.run(generate_all())
