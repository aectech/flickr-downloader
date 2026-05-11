# -*- coding: utf-8 -*-
"""
Flickr Downloader 主程序入口
现代化重写版本

使用方法:
    python main.py
    
打包后运行:
    flickr_downloader.exe
"""

import sys
import os
import logging
import argparse
from pathlib import Path

# 计算项目根目录
_script_dir = Path(__file__).parent.resolve()  # flickr_downloader 目录
_project_root = _script_dir.parent  # 父目录

# 添加路径 - 确保无论从哪个目录运行都能正确导入
# 1. 添加 flickr_downloader 目录自身（优先）
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))
# 2. 添加父目录（用于访问 flickr_downloader 包）
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# 尝试导入，如果包导入失败则使用相对导入
try:
    from flickr_downloader.ui.main_window import MainWindow
except (ModuleNotFoundError, ImportError):
    # 降级方案：直接使用相对导入
    if _script_dir not in sys.path:
        sys.path.insert(0, str(_script_dir))
    from ui.main_window import MainWindow

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QStyleFactory


def setup_logging(debug: bool = False):
    """配置日志"""
    level = logging.DEBUG if debug else logging.INFO
    
    # 创建日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # 文件处理器
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(
        log_dir / 'flickr_downloader.log',
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return root_logger


def setup_application() -> QApplication:
    """
    配置Qt应用程序
    
    Returns:
        配置好的QApplication实例
    """
    # 设置应用信息
    QApplication.setApplicationName("Flickr Downloader")
    QApplication.setApplicationVersion("2.0.0")
    QApplication.setOrganizationName("FlickrDownloader")
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 设置样式 - 使用Fusion暗色主题
    app.setStyle(QStyleFactory.create("Fusion"))
    
    # 设置暗色主题颜色
    palette = app.palette()
    
    # 背景色
    palette.setColor(palette.Window, QColor(53, 53, 53))
    palette.setColor(palette.WindowText, Qt.white)
    palette.setColor(palette.Base, QColor(35, 35, 35))
    palette.setColor(palette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(palette.ToolTipBase, Qt.white)
    palette.setColor(palette.ToolTipText, Qt.white)
    palette.setColor(palette.Text, Qt.white)
    palette.setColor(palette.Button, QColor(53, 53, 53))
    palette.setColor(palette.ButtonText, Qt.white)
    palette.setColor(palette.BrightText, Qt.red)
    palette.setColor(palette.Highlight, QColor(42, 130, 218))
    palette.setColor(palette.HighlightedText, Qt.black)
    
    app.setPalette(palette)
    
    # 设置默认字体
    font = QFont("Microsoft YaHei UI", 10)
    app.setFont(font)
    
    return app


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Flickr Downloader - 现代化Flickr下载器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python main.py                    # 正常启动
    python main.py --debug            # 调试模式启动
    python main.py --reset-config     # 重置配置
    python main.py --clear-logs       # 清空日志
        """
    )
    
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='启用调试模式'
    )
    
    parser.add_argument(
        '--reset-config',
        action='store_true',
        help='重置所有配置'
    )
    
    parser.add_argument(
        '--clear-logs',
        action='store_true',
        help='清空日志文件'
    )
    
    return parser.parse_args()


def main():
    """主函数"""
    # 解析参数
    args = parse_arguments()
    
    # 配置日志
    logger = setup_logging(args.debug)
    logger.info("=" * 50)
    logger.info("Flickr Downloader 启动")
    logger.info("=" * 50)
    
    # 清空日志
    if args.clear_logs:
        log_file = Path(__file__).parent / 'logs' / 'flickr_downloader.log'
        if log_file.exists():
            log_file.unlink()
            logger.info("日志已清空")
    
    # 重置配置
    if args.reset_config:
        from flickr_downloader.core.config import ConfigManager
        config = ConfigManager()
        config.reset()
        logger.info("配置已重置")
    
    # 初始化Qt应用
    app = setup_application()
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    logger.info("主窗口已显示")
    
    # 运行事件循环
    exit_code = app.exec()
    
    logger.info(f"程序退出，退出码: {exit_code}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
