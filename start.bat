@echo off
chcp 65001 >nul
title 企微恶搞反制助手启动器

echo ========================================================
echo        🛡️ 企微防骚扰恶搞反制助手 (WeCom Call Guard)
echo ========================================================
echo.
echo 正在检查 Python 环境与依赖...

python -c "import uiautomation, psutil, win32gui" 2>nul
if %errorlevel% neq 0 (
    echo [提示] 正在安装必要依赖 (uiautomation, pywin32, psutil)...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo [OK] 启动图形界面中...
start "" pythonw main.py
exit
