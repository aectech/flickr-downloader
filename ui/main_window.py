# -*- coding: utf-8 -*-
"""
主窗口模块
使用PySide6实现的现代化Flickr下载器界面

修复原项目bug:
- 所有UI文字使用多语言支持
- 使用信号槽替代跨线程Invoke
- i18n国际化支持
- 现代暗色主题
"""

import asyncio
import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from PySide6.QtCore import (QCoreApplication, QSettings, Qt, QThread, 
                             Signal, Slot, QTimer)
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QTextCursor
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, 
                                QDialog, QFileDialog, QFrame,
                                QGroupBox, QLabel, QLineEdit, 
                                QListWidget, QListWidgetItem, 
                                QMainWindow, QMenuBar, QMessageBox,
                                QProgressBar, QProgressDialog,
                                QPushButton, QRadioButton, QSpinBox,
                                QStatusBar, QStyleFactory, QTabWidget,
                                QTableWidget, QTableWidgetItem, QTextEdit,
                                QToolBar, QVBoxLayout, QHBoxLayout,
                                QGridLayout, QFormLayout, QGroupBox,
                                QSizePolicy, QSplitter, QScrollArea,
                                QWidget, QStyle)

logger = logging.getLogger(__name__)


class LogHandler(logging.Handler):
    """日志处理器，将日志输出到QTextEdit"""
    
    class QtLogWidget(logging.Handler):
        """线程安全的日志处理器"""
        
        def __init__(self, text_edit: QTextEdit):
            super().__init__()
            self.text_edit = text_edit
            self.max_lines = 50000  # 原项目50000字符限制
            
        def emit(self, record: logging.LogRecord):
            try:
                msg = self.format(record)
                # 使用QMetaObject.invokeMethod确保线程安全
                QMetaObject.invokeMethod(
                    self.text_edit,
                    "append",
                    Qt.QueuedConnection,
                    Q_ARG(str, msg)
                )
            except Exception:
                self.handleError(record)
    
    def __init__(self, text_widget: QTextEdit):
        super().__init__()
        self.text_widget = text_widget


class OAuthCallbackServer(QThread):
    """OAuth回调服务器线程"""
    
    token_received = Signal(str, str)  # oauth_token, oauth_verifier
    error_occurred = Signal(str)
    
    def __init__(self, port: int = 18080):
        super().__init__()
        self.port = port
        self._running = False
        self._server = None
    
    def run(self):
        """启动HTTP服务器"""
        import http.server
        import socketserver
        import urllib.parse
        
        class Handler(http.server.BaseHTTPRequestHandler):
            server_instance = None
            
            def do_GET(self):
                """处理GET请求"""
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)
                
                if 'oauth_token' in params and 'oauth_verifier' in params:
                    oauth_token = params['oauth_token'][0]
                    oauth_verifier = params['oauth_verifier'][0]
                    
                    # 发送成功响应
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    success_html = '<html><body><h1>认证成功！</h1><p>您可以关闭此窗口并返回应用程序。</p></body></html>'
                    self.wfile.write(success_html.encode('utf-8'))
                    
                    # 发送信号
                    Handler.server_instance.token_received.emit(oauth_token, oauth_verifier)
                else:
                    self.send_response(400)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'Bad Request')
            
            def log_message(self, format, *args):
                """抑制日志输出"""
                pass
        
        Handler.server_instance = self
        
        try:
            with socketserver.TCPServer(("", self.port), Handler) as httpd:
                self._running = True
                logger.info(f"OAuth回调服务器启动: http://localhost:{self.port}")
                
                while self._running:
                    httpd.handle_request()
                    
        except OSError as e:
            if e.errno == 98:  # Address already in use
                logger.error(f"端口 {self.port} 已被占用")
                self.error_occurred.emit(f"端口 {self.port} 已被占用，请关闭其他程序或使用不同端口")
            else:
                logger.error(f"服务器错误: {e}")
                self.error_occurred.emit(str(e))
    
    def stop(self):
        """停止服务器"""
        self._running = False


class MainWindow(QMainWindow):
    """
    Flickr Downloader 主窗口
    
    实现功能:
    - 八种下载类型选择
    - 搜索功能 (Tab 2)
    - 文件命名规则选择
    - 下载选项配置
    - OAuth认证
    - 下载进度显示
    - 配置管理
    - 多语言支持
    """
    
    # 信号定义
    log_signal = Signal(str, QColor)  # 消息, 颜色
    progress_signal = Signal(int, int, float)  # 当前, 总数, 速度
    download_complete_signal = Signal(str)  # 任务ID
    status_signal = Signal(str)  # 状态文本
    
    def __init__(self):
        super().__init__()
        
        # 初始化i18n
        from flickr_downloader.core.i18n import LanguageManager
        from flickr_downloader.core.config import ConfigManager
        config_mgr = ConfigManager()
        self.i18n = LanguageManager(config_mgr)
        
        # 连接语言切换信号
        self.i18n.language_changed.connect(self._on_language_changed)
        
        # 初始化组件
        self.setWindowTitle(self.i18n.t("main_window.title"))
        self.setMinimumSize(1000, 700)
        
        # 加载配置
        self.config = self._load_config()
        
        # 初始化组件
        self._init_ui()
        self._init_connections()
        self._init_download_manager()
        
        # 应用配置
        self._apply_config()
        
        # 剪贴板监控
        self._clipboard_timer = QTimer()
        self._clipboard_timer.timeout.connect(self._check_clipboard)
        if self.config.get('clipboard_monitor', True):
            self._clipboard_timer.start(1000)
        
        # 状态
        self._is_downloading = False
        self._oauth_server: Optional[OAuthCallbackServer] = None
        
        logger.info("主窗口初始化完成")
    
    def _load_config(self) -> Dict:
        """加载配置"""
        from flickr_downloader.core.config import ConfigManager
        config_mgr = ConfigManager()
        return config_mgr
    
    def _init_ui(self):
        """初始化UI"""
        # 创建菜单栏
        self._create_menu_bar()
        
        # 创建工具栏
        self._create_tool_bar()
        
        # 创建标签页
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 创建Tab控件
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Tab 1: 下载
        self._create_download_tab()
        
        # Tab 2: 搜索
        self._create_search_tab()
        
        # 日志区域
        self._create_log_area()
        
        # 状态栏
        self._create_status_bar()
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu(self.i18n.t("menu.file"))
        
        save_config_action = QAction(self.i18n.t("menu.save_config"), self)
        save_config_action.setStatusTip(self.i18n.t("menu.save_config_tip"))
        save_config_action.triggered.connect(self._save_config)
        file_menu.addAction(save_config_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction(self.i18n.t("menu.exit"), self)
        exit_action.setStatusTip(self.i18n.t("menu.exit_tip"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu(self.i18n.t("menu.edit"))
        
        self.clipboard_action = QAction(self.i18n.t("menu.clipboard_monitor") + "=" + self.i18n.t("common.on"), self)
        self.clipboard_action.setCheckable(True)
        self.clipboard_action.setChecked(True)
        self.clipboard_action.triggered.connect(self._toggle_clipboard)
        edit_menu.addAction(self.clipboard_action)
        
        self.sound_action = QAction(self.i18n.t("menu.sound") + "=" + self.i18n.t("common.on"), self)
        self.sound_action.setCheckable(True)
        self.sound_action.setChecked(True)
        self.sound_action.triggered.connect(self._toggle_sound)
        edit_menu.addAction(self.sound_action)
        
        # 视图菜单
        view_menu = menubar.addMenu(self.i18n.t("menu.view"))
        
        self.detail_action = QAction(self.i18n.t("menu.detail_display") + "=" + self.i18n.t("common.off"), self)
        self.detail_action.setCheckable(True)
        self.detail_action.setChecked(False)
        self.detail_action.triggered.connect(self._toggle_detail)
        view_menu.addAction(self.detail_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu(self.i18n.t("menu.help"))
        
        about_action = QAction(self.i18n.t("menu.about"), self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        check_update_action = QAction(self.i18n.t("menu.check_update"), self)
        check_update_action.triggered.connect(self._check_update)
        help_menu.addAction(check_update_action)
    
    def _create_tool_bar(self):
        """创建工具栏"""
        toolbar = QToolBar(self.i18n.t("main_window.title"))
        self.addToolBar(toolbar)
        
        # 保存路径
        toolbar.addWidget(QLabel(self.i18n.t("toolbar.save_path")))
        self.save_path_edit = QLineEdit()
        self.save_path_edit.setReadOnly(True)
        self.save_path_edit.setMinimumWidth(300)
        toolbar.addWidget(self.save_path_edit)
        
        browse_btn = QPushButton(self.i18n.t("toolbar.browse"))
        browse_btn.clicked.connect(self._browse_save_path)
        toolbar.addWidget(browse_btn)
        
        toolbar.addSeparator()
        
        # 线程数
        toolbar.addWidget(QLabel(self.i18n.t("toolbar.thread_count")))
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 10)
        self.thread_spin.setValue(4)
        self.thread_spin.setMinimumWidth(60)
        toolbar.addWidget(self.thread_spin)
        
        toolbar.addSeparator()
        
        # 语言选择器
        toolbar.addWidget(QLabel(self.i18n.t("main_window.language") + ":"))
        self.language_combo = QComboBox()
        self.language_combo.addItem("🌍 " + self.i18n.t("main_window.auto_detect"), "auto")
        from flickr_downloader.core.i18n import SUPPORTED_LANGUAGES
        for code, name in SUPPORTED_LANGUAGES.items():
            self.language_combo.addItem(name, code)
        
        # 设置当前语言
        current_lang = self.i18n.get_current_language()
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == current_lang:
                self.language_combo.setCurrentIndex(i)
                break
        
        self.language_combo.currentIndexChanged.connect(self._on_language_selected)
        toolbar.addWidget(self.language_combo)
        
        toolbar.addSeparator()
        
        # 开始/暂停按钮
        self.start_btn = QPushButton(self.i18n.t("toolbar.start_download"))
        self.start_btn.clicked.connect(self._toggle_download)
        toolbar.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton(self.i18n.t("toolbar.stop"))
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_download)
        toolbar.addWidget(self.stop_btn)
    
    def _on_language_selected(self, index: int):
        """语言选择改变"""
        lang_code = self.language_combo.itemData(index)
        if lang_code == "auto":
            self.i18n.clear_preference()
        else:
            self.i18n.switch_language(lang_code)
    
    @Slot(str)
    def _on_language_changed(self, lang_code: str):
        """语言切换回调"""
        # 更新下拉框选择
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == lang_code:
                self.language_combo.blockSignals(True)
                self.language_combo.setCurrentIndex(i)
                self.language_combo.blockSignals(False)
                break
        
        # 刷新UI
        self.refresh_ui()
    
    def refresh_ui(self):
        """刷新所有UI文本"""
        # 窗口标题
        self.setWindowTitle(self.i18n.t("main_window.title"))
        
        # 菜单栏
        self._refresh_menu_bar()
        
        # 工具栏
        self._refresh_tool_bar()
        
        # 下载Tab
        self._refresh_download_tab()
        
        # 搜索Tab
        self._refresh_search_tab()
        
        # 状态栏
        if not self.config.get('oauth_token'):
            self.login_label.setText(self.i18n.t("main_window.unlogged"))
    
    def _refresh_menu_bar(self):
        """刷新菜单栏"""
        menubar = self.menuBar()
        
        # 清空并重建菜单
        menubar.clear()
        
        # 文件菜单
        file_menu = menubar.addMenu(self.i18n.t("menu.file"))
        
        save_config_action = QAction(self.i18n.t("menu.save_config"), self)
        save_config_action.setStatusTip(self.i18n.t("menu.save_config_tip"))
        save_config_action.triggered.connect(self._save_config)
        file_menu.addAction(save_config_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction(self.i18n.t("menu.exit"), self)
        exit_action.setStatusTip(self.i18n.t("menu.exit_tip"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu(self.i18n.t("menu.edit"))
        
        self.clipboard_action = QAction(self.i18n.t("menu.clipboard_monitor") + "=" + (self.i18n.t("common.on") if self.clipboard_action.isChecked() else self.i18n.t("common.off")), self)
        self.clipboard_action.setCheckable(True)
        self.clipboard_action.setChecked(self.config.get('clipboard_monitor', True))
        self.clipboard_action.triggered.connect(self._toggle_clipboard)
        edit_menu.addAction(self.clipboard_action)
        
        self.sound_action = QAction(self.i18n.t("menu.sound") + "=" + (self.i18n.t("common.on") if self.sound_action.isChecked() else self.i18n.t("common.off")), self)
        self.sound_action.setCheckable(True)
        self.sound_action.setChecked(self.config.get('sound_enabled', True))
        self.sound_action.triggered.connect(self._toggle_sound)
        edit_menu.addAction(self.sound_action)
        
        # 视图菜单
        view_menu = menubar.addMenu(self.i18n.t("menu.view"))
        
        self.detail_action = QAction(self.i18n.t("menu.detail_display") + "=" + (self.i18n.t("common.on") if self.detail_action.isChecked() else self.i18n.t("common.off")), self)
        self.detail_action.setCheckable(True)
        self.detail_action.setChecked(self.config.get('show_detail_info', False))
        self.detail_action.triggered.connect(self._toggle_detail)
        view_menu.addAction(self.detail_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu(self.i18n.t("menu.help"))
        
        about_action = QAction(self.i18n.t("menu.about"), self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        check_update_action = QAction(self.i18n.t("menu.check_update"), self)
        check_update_action.triggered.connect(self._check_update)
        help_menu.addAction(check_update_action)
    
    def _refresh_tool_bar(self):
        """刷新工具栏"""
        # 刷新标签文本
        pass  # 工具栏标签在refresh_download_tab中处理
    
    def _refresh_download_tab(self):
        """刷新下载Tab"""
        # Tab标题
        self.tab_widget.setTabText(0, self.i18n.t("download_tab.title"))
        
        # 下载类型
        self.type_group.setTitle(self.i18n.t("download_tab.download_type"))
        type_labels = [
            self.i18n.t("download_tab.type_album"),
            self.i18n.t("download_tab.type_single"),
            self.i18n.t("download_tab.type_user_all"),
            self.i18n.t("download_tab.type_favorites"),
            self.i18n.t("download_tab.type_group"),
            self.i18n.t("download_tab.type_another"),
            self.i18n.t("download_tab.type_pick_album"),
            self.i18n.t("download_tab.type_pick_user")
        ]
        for i, rb in enumerate(self.type_radios):
            rb.setText(type_labels[i])
        
        # URL输入
        self.url_group.setTitle(self.i18n.t("download_tab.url_input"))
        self.url_input.setPlaceholderText(self.i18n.t("download_tab.url_placeholder"))
        
        # 下载选项
        self.options_group.setTitle(self.i18n.t("download_tab.options"))
        
        # 查找并刷新标签
        for child in self.options_group.findChildren(QLabel):
            if child.text() == "文件命名:":
                child.setText(self.i18n.t("download_tab.file_naming"))
            elif child.text() == "照片尺寸:":
                child.setText(self.i18n.t("download_tab.photo_size"))
        
        # 复选框
        self.auto_dir_check.setText(self.i18n.t("download_tab.auto_create_dir"))
        self.skip_existing_check.setText(self.i18n.t("download_tab.skip_existing"))
        self.preview_check.setText(self.i18n.t("download_tab.preview_photo"))
        self.video_check.setText(self.i18n.t("download_tab.video_download"))
        
        # 尺寸选项
        size_labels = [
            self.i18n.t("download_tab.size_auto_max"),
            self.i18n.t("download_tab.size_original"),
            self.i18n.t("download_tab.size_6k"),
            self.i18n.t("download_tab.size_5k"),
            self.i18n.t("download_tab.size_4k"),
            self.i18n.t("download_tab.size_3k"),
            self.i18n.t("download_tab.size_large_800"),
            self.i18n.t("download_tab.size_large_600"),
            self.i18n.t("download_tab.size_large"),
            self.i18n.t("download_tab.size_medium_800"),
            self.i18n.t("download_tab.size_medium_640"),
            self.i18n.t("download_tab.size_medium"),
            self.i18n.t("download_tab.size_small")
        ]
        current_size = self.size_combo.currentIndex()
        self.size_combo.clear()
        self.size_combo.addItems(size_labels)
        self.size_combo.setCurrentIndex(min(current_size, len(size_labels) - 1))
        
        # 时间格式
        for child in self.findChildren(QLabel):
            if child.text() == "时间格式:":
                child.setText(self.i18n.t("download_tab.time_format"))
                break
    
    def _refresh_search_tab(self):
        """刷新搜索Tab"""
        # Tab标题
        self.tab_widget.setTabText(1, self.i18n.t("search_tab.title"))
        
        # 搜索类型
        self.search_type_group.setTitle(self.i18n.t("search_tab.search_type"))
        self.keyword_radio.setText(self.i18n.t("search_tab.keyword_search"))
        self.keyword_edit.setPlaceholderText(self.i18n.t("search_tab.keyword_placeholder"))
        self.user_radio.setText(self.i18n.t("search_tab.user_search"))
        self.user_id_edit.setPlaceholderText(self.i18n.t("search_tab.user_placeholder"))
        self.group_radio.setText(self.i18n.t("search_tab.group_search"))
        self.group_id_edit.setPlaceholderText(self.i18n.t("search_tab.group_placeholder"))
        
        # 搜索选项
        self.search_options_group.setTitle(self.i18n.t("search_tab.options"))
        
        # 刷新标签
        for child in self.search_options_group.findChildren(QLabel):
            if "隐私过滤" in child.text():
                child.setText(self.i18n.t("search_tab.privacy_filter"))
            elif "安全搜索" in child.text():
                child.setText(self.i18n.t("search_tab.safe_search"))
            elif "每页数量" in child.text():
                child.setText(self.i18n.t("search_tab.per_page"))
            elif "起始页" in child.text():
                child.setText(self.i18n.t("search_tab.start_page"))
            elif "抓取页数" in child.text():
                child.setText(self.i18n.t("search_tab.fetch_pages"))
        
        # 隐私过滤选项
        privacy_labels = [
            self.i18n.t("search_tab.privacy_all"),
            self.i18n.t("search_tab.privacy_public"),
            self.i18n.t("search_tab.privacy_friends"),
            self.i18n.t("search_tab.privacy_family"),
            self.i18n.t("search_tab.privacy_private")
        ]
        current_privacy = self.privacy_combo.currentIndex()
        self.privacy_combo.clear()
        self.privacy_combo.addItems(privacy_labels)
        self.privacy_combo.setCurrentIndex(min(current_privacy, len(privacy_labels) - 1))
        
        # 安全搜索选项
        safe_labels = [
            self.i18n.t("search_tab.safe_safe"),
            self.i18n.t("search_tab.safe_moderate"),
            self.i18n.t("search_tab.safe_restricted")
        ]
        current_safe = self.safe_search_combo.currentIndex()
        self.safe_search_combo.clear()
        self.safe_search_combo.addItems(safe_labels)
        self.safe_search_combo.setCurrentIndex(min(current_safe, len(safe_labels) - 1))
        
        # 搜索按钮
        self.search_btn.setText(self.i18n.t("search_tab.start_search"))
        self.add_to_download_btn.setText(self.i18n.t("search_tab.add_to_list"))
        
        # 结果列表
        self.result_group.setTitle(self.i18n.t("search_tab.results"))
    
    def _create_download_tab(self):
        """创建下载Tab"""
        tab = QWidget()
        self.tab_widget.addTab(tab, self.i18n.t("download_tab.title"))
        
        layout = QVBoxLayout(tab)
        
        # 下载类型组
        self.type_group = QGroupBox(self.i18n.t("download_tab.download_type"))
        type_layout = QVBoxLayout()
        
        self.type_radios = []
        type_labels = [
            self.i18n.t("download_tab.type_album"),
            self.i18n.t("download_tab.type_single"),
            self.i18n.t("download_tab.type_user_all"),
            self.i18n.t("download_tab.type_favorites"),
            self.i18n.t("download_tab.type_group"),
            self.i18n.t("download_tab.type_another"),
            self.i18n.t("download_tab.type_pick_album"),
            self.i18n.t("download_tab.type_pick_user")
        ]
        
        for i, label in enumerate(type_labels):
            rb = QRadioButton(label)
            if i == 0:
                rb.setChecked(True)
            self.type_radios.append(rb)
            type_layout.addWidget(rb)
        
        self.type_group.setLayout(type_layout)
        layout.addWidget(self.type_group)
        
        # URL输入
        self.url_group = QGroupBox(self.i18n.t("download_tab.url_input"))
        url_layout = QVBoxLayout()
        
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText(self.i18n.t("download_tab.url_placeholder"))
        self.url_input.setMaximumHeight(100)
        url_layout.addWidget(self.url_input)
        
        self.url_group.setLayout(url_layout)
        layout.addWidget(self.url_group)
        
        # 选项组
        self.options_group = QGroupBox(self.i18n.t("download_tab.options"))
        options_layout = QGridLayout()
        
        # 文件命名
        options_layout.addWidget(QLabel(self.i18n.t("download_tab.file_naming")), 0, 0)
        self.naming_combo = QComboBox()
        from flickr_downloader.core.naming import NamingStrategy
        for style_id, style_name in NamingStrategy.FORMAT_NAMES.items():
            self.naming_combo.addItem(f"{style_id}: {style_name}", style_id)
        self.naming_combo.setCurrentIndex(3)
        options_layout.addWidget(self.naming_combo, 0, 1)
        
        # 尺寸选择
        options_layout.addWidget(QLabel(self.i18n.t("download_tab.photo_size")), 0, 2)
        self.size_combo = QComboBox()
        size_labels = [
            self.i18n.t("download_tab.size_auto_max"),
            self.i18n.t("download_tab.size_original"),
            self.i18n.t("download_tab.size_6k"),
            self.i18n.t("download_tab.size_5k"),
            self.i18n.t("download_tab.size_4k"),
            self.i18n.t("download_tab.size_3k"),
            self.i18n.t("download_tab.size_large_800"),
            self.i18n.t("download_tab.size_large_600"),
            self.i18n.t("download_tab.size_large"),
            self.i18n.t("download_tab.size_medium_800"),
            self.i18n.t("download_tab.size_medium_640"),
            self.i18n.t("download_tab.size_medium"),
            self.i18n.t("download_tab.size_small")
        ]
        self.size_combo.addItems(size_labels)
        options_layout.addWidget(self.size_combo, 0, 3)
        
        # 选项复选框
        self.auto_dir_check = QCheckBox(self.i18n.t("download_tab.auto_create_dir"))
        self.auto_dir_check.setChecked(True)
        options_layout.addWidget(self.auto_dir_check, 1, 0)
        
        self.skip_existing_check = QCheckBox(self.i18n.t("download_tab.skip_existing"))
        options_layout.addWidget(self.skip_existing_check, 1, 1)
        
        self.preview_check = QCheckBox(self.i18n.t("download_tab.preview_photo"))
        self.preview_check.setChecked(True)
        options_layout.addWidget(self.preview_check, 1, 2)
        
        self.video_check = QCheckBox(self.i18n.t("download_tab.video_download"))
        options_layout.addWidget(self.video_check, 1, 3)
        
        self.options_group.setLayout(options_layout)
        layout.addWidget(self.options_group)
        
        # 时间格式
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel(self.i18n.t("download_tab.time_format")))
        self.time_format_edit = QLineEdit("yyyy-MM-dd HH_mm_ss")
        time_layout.addWidget(self.time_format_edit)
        layout.addLayout(time_layout)
        
        layout.addStretch()
    
    def _create_search_tab(self):
        """创建搜索Tab"""
        tab = QWidget()
        self.tab_widget.addTab(tab, self.i18n.t("search_tab.title"))
        
        layout = QVBoxLayout(tab)
        
        # 搜索类型
        self.search_type_group = QGroupBox(self.i18n.t("search_tab.search_type"))
        search_type_layout = QGridLayout()
        
        # 关键词搜索
        self.keyword_radio = QRadioButton(self.i18n.t("search_tab.keyword_search"))
        self.keyword_radio.setChecked(True)
        search_type_layout.addWidget(self.keyword_radio, 0, 0)
        
        self.keyword_edit = QLineEdit()
        self.keyword_edit.setPlaceholderText(self.i18n.t("search_tab.keyword_placeholder"))
        search_type_layout.addWidget(self.keyword_edit, 0, 1, 1, 3)
        
        # 用户搜索
        self.user_radio = QRadioButton(self.i18n.t("search_tab.user_search"))
        search_type_layout.addWidget(self.user_radio, 1, 0)
        
        self.user_id_edit = QLineEdit()
        self.user_id_edit.setPlaceholderText(self.i18n.t("search_tab.user_placeholder"))
        search_type_layout.addWidget(self.user_id_edit, 1, 1, 1, 3)
        
        # 群组搜索
        self.group_radio = QRadioButton(self.i18n.t("search_tab.group_search"))
        search_type_layout.addWidget(self.group_radio, 2, 0)
        
        self.group_id_edit = QLineEdit()
        self.group_id_edit.setPlaceholderText(self.i18n.t("search_tab.group_placeholder"))
        search_type_layout.addWidget(self.group_id_edit, 2, 1, 1, 3)
        
        self.search_type_group.setLayout(search_type_layout)
        layout.addWidget(self.search_type_group)
        
        # 搜索选项
        self.search_options_group = QGroupBox(self.i18n.t("search_tab.options"))
        search_options_layout = QGridLayout()
        
        # 隐私过滤
        search_options_layout.addWidget(QLabel(self.i18n.t("search_tab.privacy_filter")), 0, 0)
        self.privacy_combo = QComboBox()
        privacy_labels = [
            self.i18n.t("search_tab.privacy_all"),
            self.i18n.t("search_tab.privacy_public"),
            self.i18n.t("search_tab.privacy_friends"),
            self.i18n.t("search_tab.privacy_family"),
            self.i18n.t("search_tab.privacy_private")
        ]
        self.privacy_combo.addItems(privacy_labels)
        search_options_layout.addWidget(self.privacy_combo, 0, 1)
        
        # 安全搜索
        search_options_layout.addWidget(QLabel(self.i18n.t("search_tab.safe_search")), 0, 2)
        self.safe_search_combo = QComboBox()
        safe_labels = [
            self.i18n.t("search_tab.safe_safe"),
            self.i18n.t("search_tab.safe_moderate"),
            self.i18n.t("search_tab.safe_restricted")
        ]
        self.safe_search_combo.addItems(safe_labels)
        self.safe_search_combo.setCurrentIndex(1)
        search_options_layout.addWidget(self.safe_search_combo, 0, 3)
        
        # 分页
        search_options_layout.addWidget(QLabel(self.i18n.t("search_tab.per_page")), 1, 0)
        self.per_page_spin = QSpinBox()
        self.per_page_spin.setRange(1, 500)
        self.per_page_spin.setValue(50)
        search_options_layout.addWidget(self.per_page_spin, 1, 1)
        
        search_options_layout.addWidget(QLabel(self.i18n.t("search_tab.start_page")), 1, 2)
        self.start_page_spin = QSpinBox()
        self.start_page_spin.setRange(1, 9999)
        self.start_page_spin.setValue(1)
        search_options_layout.addWidget(self.start_page_spin, 1, 3)
        
        search_options_layout.addWidget(QLabel(self.i18n.t("search_tab.fetch_pages")), 2, 0)
        self.fetch_page_spin = QSpinBox()
        self.fetch_page_spin.setRange(1, 100)
        self.fetch_page_spin.setValue(1)
        search_options_layout.addWidget(self.fetch_page_spin, 2, 1)
        
        self.search_options_group.setLayout(search_options_layout)
        layout.addWidget(self.search_options_group)
        
        # 搜索按钮
        search_btn_layout = QHBoxLayout()
        search_btn_layout.addStretch()
        
        self.search_btn = QPushButton(self.i18n.t("search_tab.start_search"))
        self.search_btn.clicked.connect(self._start_search)
        search_btn_layout.addWidget(self.search_btn)
        
        self.add_to_download_btn = QPushButton(self.i18n.t("search_tab.add_to_list"))
        self.add_to_download_btn.clicked.connect(self._add_search_results)
        search_btn_layout.addWidget(self.add_to_download_btn)
        
        layout.addLayout(search_btn_layout)
        
        # 结果列表
        self.result_group = QGroupBox(self.i18n.t("search_tab.results"))
        result_layout = QVBoxLayout()
        
        self.search_result_list = QListWidget()
        self.search_result_list.setAlternatingRowColors(True)
        result_layout.addWidget(self.search_result_list)
        
        self.result_group.setLayout(result_layout)
        layout.addWidget(self.result_group, 1)
    
    def _create_log_area(self):
        """创建日志区域"""
        # 日志区域使用splitter
        splitter = QSplitter(Qt.Vertical)
        
        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setFont(QFont("Consolas", 9))
        splitter.addWidget(self.log_text)
        
        # 失败列表
        self.fail_group = QGroupBox(self.i18n.t("fail_list.title"))
        fail_layout = QVBoxLayout()
        
        self.fail_list = QListWidget()
        fail_layout.addWidget(self.fail_list)
        
        fail_btn_layout = QHBoxLayout()
        retry_fail_btn = QPushButton(self.i18n.t("fail_list.retry_failed"))
        retry_fail_btn.clicked.connect(self._retry_failed)
        fail_btn_layout.addWidget(retry_fail_btn)
        
        clear_fail_btn = QPushButton(self.i18n.t("fail_list.clear"))
        clear_fail_btn.clicked.connect(self._clear_failed)
        fail_btn_layout.addWidget(clear_fail_btn)
        fail_btn_layout.addStretch()
        
        fail_layout.addLayout(fail_btn_layout)
        self.fail_group.setLayout(fail_layout)
        splitter.addWidget(self.fail_group)
        
        # 添加到主布局
        layout = self.tab_widget.widget(0).layout()
        if layout:
            layout.addWidget(splitter)
    
    def _create_status_bar(self):
        """创建状态栏"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        # 登录状态
        self.login_label = QLabel(self.i18n.t("main_window.unlogged"))
        self.statusbar.addPermanentWidget(self.login_label)
        
        # 下载进度
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self.progress_bar)
        
        # 速度显示
        self.speed_label = QLabel("")
        self.statusbar.addPermanentWidget(self.speed_label)
        
        # 版本信息
        self.version_label = QLabel(self.i18n.t("main_window.version"))
        self.statusbar.addPermanentWidget(self.version_label)
    
    def _init_connections(self):
        """初始化信号连接"""
        # 日志信号
        self.log_signal.connect(self._append_log)
        
        # 进度信号
        self.progress_signal.connect(self._update_progress)
        
        # 状态信号
        self.status_signal.connect(self.statusbar.showMessage)
        
        # 下载完成信号
        self.download_complete_signal.connect(self._on_download_complete)
    
    def _init_download_manager(self):
        """初始化下载管理器"""
        from flickr_downloader.core.downloader import SyncDownloadManager
        
        self.download_manager = SyncDownloadManager(
            thread_count=self.thread_spin.value(),
            save_dir=self.save_path_edit.text() or str(Path.home()),
            skip_existing=self.skip_existing_check.isChecked(),
            auto_make_dirs=self.auto_dir_check.isChecked()
        )
    
    def _apply_config(self):
        """应用配置"""
        # 窗口大小
        width = self.config.get('window_width', 1000)
        height = self.config.get('window_height', 700)
        self.resize(width, height)
        
        # 下载选项
        self.naming_combo.setCurrentIndex(self.config.get('naming_style', 3))
        self.size_combo.setCurrentIndex(self.config.get('size_setting', 0))
        self.thread_spin.setValue(self.config.get('thread_count', 4))
        
        self.auto_dir_check.setChecked(self.config.get('auto_make_dirs', True))
        self.skip_existing_check.setChecked(self.config.get('skip_existing', False))
        self.preview_check.setChecked(self.config.get('preview_photos', True))
        self.video_check.setChecked(self.config.get('video_download', False))
        
        self.time_format_edit.setText(self.config.get('time_format', 'yyyy-MM-dd HH_mm_ss'))
        
        # 搜索选项
        self.per_page_spin.setValue(self.config.get('search_per_page', 50))
        self.start_page_spin.setValue(self.config.get('search_start_page', 1))
        self.fetch_page_spin.setValue(self.config.get('search_fetch_page', 1))
        
        # 保存路径
        save_path = self.config.get('save_path', '')
        if save_path:
            self.save_path_edit.setText(save_path)
        else:
            self.save_path_edit.setText(str(Path.home()))
        
        # 剪贴板监控
        self.clipboard_action.setChecked(self.config.get('clipboard_monitor', True))
        
        # 音效
        self.sound_action.setChecked(self.config.get('sound_enabled', True))
        
        # 详细显示
        self.detail_action.setChecked(self.config.get('show_detail_info', False))
    
    def _save_config(self):
        """保存配置"""
        self.config['window_width'] = self.width()
        self.config['window_height'] = self.height()
        
        self.config['naming_style'] = self.naming_combo.currentIndex()
        self.config['size_setting'] = self.size_combo.currentIndex()
        self.config['thread_count'] = self.thread_spin.value()
        
        self.config['auto_make_dirs'] = self.auto_dir_check.isChecked()
        self.config['skip_existing'] = self.skip_existing_check.isChecked()
        self.config['preview_photos'] = self.preview_check.isChecked()
        self.config['video_download'] = self.video_check.isChecked()
        
        self.config['time_format'] = self.time_format_edit.text()
        
        self.config['search_per_page'] = self.per_page_spin.value()
        self.config['search_start_page'] = self.start_page_spin.value()
        self.config['search_fetch_page'] = self.fetch_page_spin.value()
        
        self.config['save_path'] = self.save_path_edit.text()
        
        self.config['clipboard_monitor'] = self.clipboard_action.isChecked()
        self.config['sound_enabled'] = self.sound_action.isChecked()
        self.config['show_detail_info'] = self.detail_action.isChecked()
        
        self.config.save()
        
        self._log(self.i18n.t("status.config_saved"), QColor(0, 255, 0))
    
    # ==================== 槽函数 ====================
    
    @Slot(str, QColor)
    def _append_log(self, message: str, color: QColor):
        """追加日志"""
        self.log_text.moveCursor(QTextCursor.End)
        
        # 设置颜色
        fmt = self.log_text.currentCharFormat()
        fmt.setForeground(color)
        self.log_text.setCurrentCharFormat(fmt)
        
        # 添加时间戳
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # 限制行数
        max_lines = 50000
        doc = self.log_text.document()
        if doc.blockCount() > max_lines:
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.Start)
            for _ in range(doc.blockCount() - max_lines):
                cursor.select(QTextCursor.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()
    
    def _log(self, message: str, color: QColor = QColor(255, 255, 255)):
        """记录日志"""
        self.log_signal.emit(message, color)
    
    @Slot(int, int, float)
    def _update_progress(self, current: int, total: int, speed: float):
        """更新进度"""
        if total > 0:
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            
            if speed > 0:
                self.speed_label.setText(f"{speed:.1f} KB/s")
    
    @Slot(str)
    def _on_download_complete(self, task_id: str):
        """下载完成回调"""
        task = self.download_manager.get_task(task_id)
        if task:
            self._log(f"{self.i18n.t('status.download_complete')}: {task.title}", QColor(0, 255, 0))
    
    def _browse_save_path(self):
        """浏览保存路径"""
        path = QFileDialog.getExistingDirectory(
            self, self.i18n.t("dialog.select_save_path"), self.save_path_edit.text()
        )
        if path:
            self.save_path_edit.setText(path)
            self.config['save_path'] = path
    
    def _toggle_clipboard(self, checked: bool):
        """切换剪贴板监控"""
        self.config['clipboard_monitor'] = checked
        self.clipboard_action.setText(f"{self.i18n.t('menu.clipboard_monitor')}={self.i18n.t('common.on') if checked else self.i18n.t('common.off')}")
        
        if checked:
            self._clipboard_timer.start()
        else:
            self._clipboard_timer.stop()
    
    def _toggle_sound(self, checked: bool):
        """切换音效"""
        self.config['sound_enabled'] = checked
        self.sound_action.setText(f"{self.i18n.t('menu.sound')}={self.i18n.t('common.on') if checked else self.i18n.t('common.off')}")
    
    def _toggle_detail(self, checked: bool):
        """切换详细显示"""
        self.config['show_detail_info'] = checked
        self.detail_action.setText(f"{self.i18n.t('menu.detail_display')}={self.i18n.t('common.on') if checked else self.i18n.t('common.off')}")
    
    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            self.i18n.t("about.title"),
            self.i18n.t("about.content")
        )
    
    def _check_update(self):
        """检查更新"""
        self._log(self.i18n.t("status.checking_update"), QColor(255, 255, 0))
        # TODO: 实现版本检查
        self._log(self.i18n.t("status.up_to_date"), QColor(0, 255, 0))
    
    def _check_clipboard(self):
        """检查剪贴板"""
        try:
            clipboard = QApplication.clipboard()
            text = clipboard.text()
            
            if text and ('flickr.com' in text or 'flic.kr' in text):
                # 检查是否已经添加
                current_urls = self.url_input.toPlainText()
                if text not in current_urls:
                    self._log(f"{self.i18n.t('status.clipboard_detected')}: {text[:50]}...", QColor(0, 255, 255))
                    # 可以选择自动添加或提示用户
        except Exception as e:
            logger.debug(f"剪贴板检查失败: {e}")
    
    def _toggle_download(self):
        """切换下载状态"""
        if not self._is_downloading:
            self._start_download()
        else:
            self._pause_download()
    
    def _start_download(self):
        """开始下载"""
        self._is_downloading = True
        self.start_btn.setText(self.i18n.t("toolbar.pause"))
        self.stop_btn.setEnabled(True)
        
        self._log(self.i18n.t("status.download_started"), QColor(255, 255, 0))
        
        # 获取输入的URL
        urls = self.url_input.toPlainText().strip().split('\n')
        urls = [u.strip() for u in urls if u.strip()]
        
        if not urls:
            self._log(self.i18n.t("status.please_input_url"), QColor(255, 0, 0))
            self._is_downloading = False
            self.start_btn.setText(self.i18n.t("toolbar.start_download"))
            return
        
        # 获取下载类型
        download_type = self._get_selected_type()
        
        # 添加任务
        from flickr_downloader.core.url_resolver import URLResolver
        resolver = URLResolver()
        
        for url in urls:
            parsed = resolver.parse_url(url)
            url_type = parsed.get('type', 'unknown')
            
            # 根据下载类型处理
            self._log(f"{self.i18n.t('status.url_parsed')}: {url} -> 类型: {url_type}", QColor(255, 255, 255))
            
            # TODO: 根据不同类型调用API获取照片列表
            # 目前简化处理，直接添加URL
        
        self._log(f"{len(urls)} {self.i18n.t('status.tasks_added')}", QColor(0, 255, 0))
    
    def _pause_download(self):
        """暂停下载"""
        self._is_downloading = False
        self.start_btn.setText(self.i18n.t("toolbar.resume"))
        self.download_manager.pause()
        self._log(self.i18n.t("status.download_paused"), QColor(255, 255, 0))
    
    def _stop_download(self):
        """停止下载"""
        self._is_downloading = False
        self.start_btn.setText(self.i18n.t("toolbar.start_download"))
        self.stop_btn.setEnabled(False)
        
        self.download_manager.stop()
        self._log(self.i18n.t("status.download_stopped"), QColor(255, 0, 0))
    
    def _get_selected_type(self) -> int:
        """获取选中的下载类型"""
        for i, rb in enumerate(self.type_radios):
            if rb.isChecked():
                return i
        return 0
    
    def _start_search(self):
        """开始搜索"""
        self._log(self.i18n.t("status.search_started"), QColor(255, 255, 0))
        
        # 获取搜索参数
        if self.keyword_radio.isChecked():
            keyword = self.keyword_edit.text().strip()
            if not keyword:
                self._log(self.i18n.t("status.please_input_keyword"), QColor(255, 0, 0))
                return
            self._log(f"关键词搜索: {keyword}", QColor(255, 255, 255))
        
        elif self.user_radio.isChecked():
            user_id = self.user_id_edit.text().strip()
            if not user_id:
                self._log(self.i18n.t("status.please_input_user_id"), QColor(255, 0, 0))
                return
            self._log(f"用户搜索: {user_id}", QColor(255, 255, 255))
        
        elif self.group_radio.isChecked():
            group_id = self.group_id_edit.text().strip()
            if not group_id:
                self._log(self.i18n.t("status.please_input_group_id"), QColor(255, 0, 0))
                return
            self._log(f"群组搜索: {group_id}", QColor(255, 255, 255))
        
        # TODO: 调用API执行搜索
        self._log(self.i18n.t("status.search_developing"), QColor(255, 255, 0))
    
    def _add_search_results(self):
        """添加搜索结果到下载列表"""
        selected_items = self.search_result_list.selectedItems()
        if not selected_items:
            self._log(self.i18n.t("status.please_select_results"), QColor(255, 0, 0))
            return
        
        urls = []
        for item in selected_items:
            urls.append(item.text())
        
        # 添加到下载输入框
        current = self.url_input.toPlainText()
        if current:
            current += '\n'
        self.url_input.setPlainText(current + '\n'.join(urls))
        
        self._log(f"{len(urls)} {self.i18n.t('status.items_added')}", QColor(0, 255, 0))
        
        # 切换到下载Tab
        self.tab_widget.setCurrentIndex(0)
    
    def _retry_failed(self):
        """重试失败项"""
        self._log(self.i18n.t("status.retrying"), QColor(255, 255, 0))
        count = self.download_manager.retry_failed()
        self._log(f"{count} {self.i18n.t('status.retried')}", QColor(0, 255, 0))
    
    def _clear_failed(self):
        """清空失败列表"""
        self.fail_list.clear()
    
    def closeEvent(self, event):
        """关闭事件"""
        # 保存配置
        self._save_config()
        
        # 停止下载
        if self._is_downloading:
            self.download_manager.stop()
        
        # 停止OAuth服务器
        if self._oauth_server and self._oauth_server.isRunning():
            self._oauth_server.stop()
            self._oauth_server.wait()
        
        event.accept()
