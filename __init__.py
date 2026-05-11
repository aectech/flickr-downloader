# -*- coding: utf-8 -*-
"""
Flickr Downloader - 现代化重写项目
使用Python 3.10+ 和 PySide6 构建的跨平台Flickr下载器
"""

__version__ = "2.0.0"
__author__ = "Flickr Downloader Team"
__license__ = "BSD-3-Clause"

from .flickr_api import FlickrAPI
from .downloader import DownloadManager
from .url_resolver import URLResolver
from .naming import NamingStrategy
from .config import ConfigManager

__all__ = [
    'FlickrAPI',
    'DownloadManager', 
    'URLResolver',
    'NamingStrategy',
    'ConfigManager',
]
