"""
生成专属现代精美图标 (create_icon.py)
生成多分辨率 .ico 与高清 .png 图标：
设计元素：科技深蓝圆角盾牌 + 翠绿防骚扰光环 + 闪电/通话反制符号
"""

import os
from PIL import Image, ImageDraw

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

def create_shield_icon():
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. 绘制外部深蓝微光外环
    margin = 16
    draw.ellipse([margin, margin, size - margin, size - margin], fill=(30, 41, 59, 255))
    
    # 2. 绘制翡翠绿防护环
    ring_margin = 28
    draw.ellipse([ring_margin, ring_margin, size - ring_margin, size - ring_margin], outline=(16, 185, 129, 255), width=8)

    # 3. 绘制中心盾牌
    # 盾牌多边形点位
    shield_pts = [
        (128, 55),   # 顶部尖角
        (185, 80),   # 右上肩
        (185, 140),  # 右侧腰
        (128, 205),  # 底部尖角
        (71, 140),   # 左侧腰
        (71, 80),    # 左上肩
    ]
    draw.polygon(shield_pts, fill=(15, 23, 42, 255), outline=(56, 189, 248, 255))

    # 4. 盾牌内部翡翠绿高光填充
    inner_shield = [
        (128, 70),
        (170, 90),
        (170, 135),
        (128, 190),
        (86, 135),
        (86, 90),
    ]
    draw.polygon(inner_shield, fill=(16, 185, 129, 230))

    # 5. 盾牌中央绘制通话反制电波/听筒符号 (白色高亮)
    phone_pts = [
        (115, 105),
        (141, 105),
        (145, 120),
        (135, 130),
        (125, 140),
        (135, 150),
        (120, 160),
        (105, 145),
        (110, 125)
    ]
    draw.polygon(phone_pts, fill=(255, 255, 255, 255))

    # 绘制反制小闪电/星星符号
    lightning_pts = [
        (135, 85),
        (148, 110),
        (138, 110),
        (145, 135),
        (125, 115),
        (135, 115)
    ]
    draw.polygon(lightning_pts, fill=(254, 240, 138, 255), outline=(234, 179, 8, 255))

    # 保存高清 PNG
    png_path = os.path.join(ASSETS_DIR, "icon.png")
    img.save(png_path, "PNG")

    # 保存包含多分辨率的标准 ICO
    ico_path = os.path.join(ASSETS_DIR, "icon.ico")
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico_path, format="ICO", sizes=icon_sizes)
    print(f"成功生成图标: {ico_path} 和 {png_path}")

if __name__ == "__main__":
    create_shield_icon()
