# -*- coding: utf-8 -*-
"""
核心模块
"""

from .config import ConfigManager
from .downloader import DownloadManager, DownloadStatus, DownloadTask, DownloadProgress
from .flickr_api import FlickrAPI, FlickrAPIError, OAuthToken
from .naming import NamingStrategy
from .url_resolver import URLResolver

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
