# Flickr Downloader v2.0 - Windows 一键打包说明

## 方式一：双击 bat 一键打包（推荐）

1. 确保已安装 Python 3.10+（https://www.python.org/downloads/）
   - 安装时**必须**勾选 "Add Python to PATH"
2. 双击 `build_windows.bat`
3. 等待打包完成，exe文件在 `dist/FlickrDownloader.exe`

## 方式二：手动打包

```cmd
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --windowed --name FlickrDownloader main.py
```

## 方式三：直接运行（开发模式）

```cmd
pip install -r requirements.txt
python main.py
```

## 常见问题

**Q: 双击bat闪退？**
A: 右键 → 以管理员身份运行

**Q: 提示找不到Python？**
A: 重新安装Python，勾选 "Add Python to PATH"，或手动添加到环境变量

**Q: 打包后exe太大？**
A: 正常现象，PyInstaller会打包Python运行时，约80-120MB

**Q: 杀毒软件报毒？**
A: PyInstaller打包的exe容易被误报，添加白名单即可
