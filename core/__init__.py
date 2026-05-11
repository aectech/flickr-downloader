# -*- coding: utf-8 -*-
"""
核心模块
"""

try:
    from .config import ConfigManager
    from .downloader import DownloadManager, DownloadStatus, DownloadTask, DownloadProgress
    from .flickr_api import FlickrAPI, FlickrAPIError, OAuthToken
    from .naming import NamingStrategy
    from .url_resolver import URLResolver
except ImportError:
    # 直接运行时使用绝对导入
    from flickr_downloader.core.config import ConfigManager
    from flickr_downloader.core.downloader import DownloadManager, DownloadStatus, DownloadTask, DownloadProgress
    from flickr_downloader.core.flickr_api import FlickrAPI, FlickrAPIError, OAuthToken
    from flickr_downloader.core.naming import NamingStrategy
    from flickr_downloader.core.url_resolver import URLResolver

__all__ = [
    'ConfigManager',
    'DownloadManager',
    'DownloadStatus',
    'DownloadTask',
    'DownloadProgress',
    'FlickrAPI',
    'FlickrAPIError',
    'OAuthToken',
    'NamingStrategy',
    'URLResolver'
]
