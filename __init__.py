# -*- coding: utf-8 -*-
"""
Flickr Downloader - 现代化重写项目
使用Python 3.10+ 和 PySide6 构建的跨平台Flickr下载器
"""

__version__ = "2.0.0"
__author__ = "Flickr Downloader Team"
__license__ = "BSD-3-Clause"

# 使用条件导入，支持两种运行方式：
# 1. 作为包导入 (from flickr_downloader import FlickrAPI)
# 2. 直接运行 main.py (python main.py)
try:
    from .flickr_api import FlickrAPI
    from .downloader import DownloadManager
    from .url_resolver import URLResolver
    from .naming import NamingStrategy
    from .config import ConfigManager
except ImportError:
    # 直接运行时使用绝对导入
    from flickr_downloader.core.flickr_api import FlickrAPI
    from flickr_downloader.core.downloader import DownloadManager
    from flickr_downloader.core.url_resolver import URLResolver
    from flickr_downloader.core.naming import NamingStrategy
    from flickr_downloader.core.config import ConfigManager

__all__ = [
    'FlickrAPI',
    'DownloadManager', 
    'URLResolver',
    'NamingStrategy',
    'ConfigManager',
]
