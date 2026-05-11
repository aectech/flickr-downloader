# -*- coding: utf-8 -*-
"""
Flickr Downloader 打包脚本
使用PyInstaller打包为可执行文件

使用方法:
    python build.py                  # 默认打包
    python build.py --onefile       # 单文件模式
    python build.py --debug         # 调试模式
"""

import os
import sys
import shutil
import argparse
from pathlib import Path


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Flickr Downloader 打包脚本")
    
    parser.add_argument(
        '--onefile', '-f',
        action='store_true',
        help='打包为单文件'
    )
    
    parser.add_argument(
        '--windowed', '-w',
        action='store_true',
        help='窗口模式 (无控制台)'
    )
    
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='调试模式'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='dist',
        help='输出目录'
    )
    
    parser.add_argument(
        '--name', '-n',
        default='FlickrDownloader',
        help='输出文件名'
    )
    
    return parser.parse_args()


def check_dependencies():
    """检查依赖"""
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("错误: PyInstaller 未安装")
        print("请运行: pip install pyinstaller")
        sys.exit(1)
    
    try:
        from PySide6.QtCore import QLibraryInfo
        print(f"Qt version: {QLibraryInfo.version}")
    except ImportError:
        print("错误: PySide6 未安装")
        print("请运行: pip install PySide6")
        sys.exit(1)


def get_pyside6_path():
    """获取PySide6路径"""
    import PySide6
    pyside6_path = Path(PySide6.__file__).parent
    return str(pyside6_path)


def build(args):
    """执行打包"""
    print("=" * 50)
    print("Flickr Downloader 打包工具")
    print("=" * 50)
    
    # 检查依赖
    check_dependencies()
    
    # 获取路径
    script_dir = Path(__file__).parent.absolute()
    main_script = script_dir / "main.py"
    
    if not main_script.exists():
        print(f"错误: 找不到主程序 {main_script}")
        sys.exit(1)
    
    print(f"\n项目目录: {script_dir}")
    print(f"主程序: {main_script}")
    
    # 构建命令
    cmd = [
        "pyinstaller",
        f"--name={args.name}",
        f"--distpath={args.output}",
        "--specpath=build"
    ]
    
    # 跨平台分隔符处理 (Windows用;，Linux/Mac用:)
    import platform
    sep = ";" if platform.system() == "Windows" else ":"
    
    # 语言目录 - 打包到 lang 目录
    lang_dir = script_dir / "lang"
    if lang_dir.exists():
        cmd.append(f"--add-data={lang_dir}{sep}lang")
    
    # 资源目录
    resources_dir = script_dir / "resources"
    if resources_dir.exists():
        cmd.append(f"--add-data={resources_dir}{sep}resources")
    
    # 窗口模式
    if args.windowed or args.onefile:
        cmd.append("--noconsole")
    else:
        cmd.append("--console")
    
    # 单文件模式
    if args.onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")
    
    # 调试模式
    if args.debug:
        cmd.append("--debug=all")
    
    # 添加隐含导入
    hidden_imports = [
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
        "httpx",
        "Pillow",
        "logging",
        "json",
        "pathlib"
    ]
    
    for imp in hidden_imports:
        cmd.append(f"--hidden-import={imp}")
    
    # 排除模块
    excludes = [
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "PyQt5",
        "PyQt6"
    ]
    
    for exc in excludes:
        cmd.append(f"--exclude-module={exc}")
    
    # 添加主程序
    cmd.append(str(main_script))
    
    # 打印命令
    print(f"\n执行命令: {' '.join(cmd)}\n")
    
    # 执行
    print("开始打包...")
    result = os.system(" ".join(cmd))
    
    if result == 0:
        print("\n" + "=" * 50)
        print("打包成功!")
        
        # 输出路径
        if args.onefile:
            output_file = Path(args.output) / f"{args.name}.exe"
        else:
            output_file = Path(args.output) / args.name / f"{args.name}.exe"
        
        if output_file.exists():
            print(f"输出文件: {output_file.absolute()}")
        
        print("=" * 50)
    else:
        print("\n打包失败!")
        sys.exit(1)


def clean():
    """清理构建文件"""
    script_dir = Path(__file__).parent
    
    dirs_to_remove = [
        script_dir / "build",
        script_dir / "__pycache__",
    ]
    
    files_to_remove = [
        script_dir / "FlickrDownloader.spec"
    ]
    
    for d in dirs_to_remove:
        if d.exists():
            print(f"删除目录: {d}")
            shutil.rmtree(d, ignore_errors=True)
    
    for f in files_to_remove:
        if f.exists():
            print(f"删除文件: {f}")
            f.unlink()
    
    print("清理完成")


if __name__ == "__main__":
    args = parse_args()
    
    if "--clean" in sys.argv:
        clean()
    else:
        build(args)
