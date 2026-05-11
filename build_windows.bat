@echo off
chcp 65001 >nul
title Flickr Downloader 一键打包工具
echo ============================================
echo   Flickr Downloader v2.0 一键打包工具
echo ============================================
echo.

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，正在下载安装...
    echo 请前往 https://www.python.org/downloads/ 下载Python 3.12+
    echo 安装时务必勾选 "Add Python to PATH"
    pause
    exit /b 1
)

echo [1/4] 安装依赖...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [2/4] 开始打包（首次可能需要几分钟）...
pyinstaller --onefile --windowed --name FlickrDownloader --noconfirm main.py

echo.
echo [3/4] 清理临时文件...
rmdir /s /q build 2>nul
del /q *.spec 2>nul

echo.
echo [4/4] 完成！
echo.
if exist dist\FlickrDownloader.exe (
    echo ============================================
    echo   打包成功！
    echo   exe文件位置: dist\FlickrDownloader.exe
    echo ============================================
    echo.
    echo 是否立即运行？(Y/N)
    set /p RUN_NOW=
    if /i "%RUN_NOW%"=="Y" (
        start dist\FlickrDownloader.exe
    ) else (
        explorer dist
    )
) else (
    echo [错误] 打包失败，请检查上方错误信息
)

pause
