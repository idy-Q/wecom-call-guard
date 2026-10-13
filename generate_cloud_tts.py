"""
云端高清自然人声生成工具 (generate_cloud_tts.py)
调用高质量云端语音合成引擎，直接生成自然人声 MP3 文件。
"""

import os
import urllib.parse
import requests

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

PRESETS_CLOUD = [
    {
        "filename": "10086_busy_natural.mp3",
        "title": "【真实占线】您拨打的用户正在通话中",
        "text": "您好，您拨打的用户正在通话中，请稍后再拨。Sorry, the number you dialed is busy now, please redial later."
    },
    {
        "filename": "teacher_calling_natural.mp3",
        "title": "【老师点名】请开麦回答第三题",
        "text": "刚才进入会议的这位同学，请你打开麦克风，回答一下屏幕上的第三题。听到请回答。"
    },
    {
        "filename": "anti_fraud_natural.mp3",
        "title": "【官方反诈】高频呼叫预警",
        "text": "国家反诈中心特别提醒您，当前呼叫线路检测到高频异常呼叫，系统已进入保护模式。"
    },
    {
        "filename": "exam_listening_natural.mp3",
        "title": "【英语听力】硕士研究生考试英语听力",
        "text": "全国硕士研究生招生考试，英语听力测试现在开始。Section A, Question 1."
    },
    {
        "filename": "delivery_natural.mp3",
        "title": "【外卖小哥】您的外卖放在楼下了",
        "text": "喂您好，您的外卖到了，给您放在楼下外卖柜了啊，记得趁热拿一下。"
    }
]

def synthesize_text_to_mp3(text, output_path):
    """合成文字并保存为 MP3 文件"""
    encoded_text = urllib.parse.quote(text)
    url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl=zh-CN&client=tw-ob"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 200 and len(resp.content) > 1000:
        with open(output_path, "wb") as f:
            f.write(resp.content)
        return True
    return False

def generate_all_presets():
    for item in PRESETS_CLOUD:
        out_path = os.path.join(ASSETS_DIR, item["filename"])
        print(f"正在生成: {item['title']} ...")
        success = synthesize_text_to_mp3(item["text"], out_path)
        if success:
            print(f"[OK] Generated: {item['filename']}")
        else:
            print(f"[FAIL] Failed: {item['filename']}")

if __name__ == "__main__":
    generate_all_presets()
