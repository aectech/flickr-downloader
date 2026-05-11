# -*- coding: utf-8 -*-
"""
UI模块初始化
"""

try:
    from .main_window import MainWindow
    from .album_picker import AlbumPickerDialog
    from .photo_picker import PhotoPickerDialog
    from .auth_dialog import AuthDialog
except ImportError:
    # 直接运行时使用绝对导入
    from flickr_downloader.ui.main_window import MainWindow
    from flickr_downloader.ui.album_picker import AlbumPickerDialog
    from flickr_downloader.ui.photo_picker import PhotoPickerDialog
    from flickr_downloader.ui.auth_dialog import AuthDialog

__all__ = [
    'MainWindow',
    'AlbumPickerDialog',
    'PhotoPickerDialog',
    'AuthDialog',
]
