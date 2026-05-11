# -*- coding: utf-8 -*-
"""
相册选择对话框
用于人工挑选相簿照片

修复原项目bug:
- 使用现代PySide6组件
- 所有文字使用简体中文
"""

import logging
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QSize, Signal, Slot
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, 
                                QCheckBox, QDialog, QFrame,
                                QGridLayout, QGroupBox, QHeaderView,
                                QLabel, QLineEdit, QListWidget,
                                QListWidgetItem, QPushButton,
                                QScrollArea, QSizePolicy, QSplitter,
                                QTableWidget, QTableWidgetItem,
                                QTextBrowser, QVBoxLayout, QWidget)

logger = logging.getLogger(__name__)


class AlbumPickerDialog(QDialog):
    """
    相册选择对话框
    
    功能:
    - 显示用户相册列表（带缩略图）
    - 支持全选/反选/勾选
    - 显示相册信息（名称、照片数量等）
    """
    
    # 信号：确认选择
    albums_selected = Signal(list)  # 选中的相册ID列表
    
    def __init__(self, albums: List[Dict] = None, parent=None):
        """
        初始化对话框
        
        Args:
            albums: 相册列表，每项包含id, title, count等信息
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.setWindowTitle("选择相簿")
        self.setMinimumSize(800, 600)
        
        self.albums = albums or []
        self.selected_albums: List[str] = []
        
        self._init_ui()
        self._load_albums()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 相册列表
        list_group = QGroupBox("相簿列表")
        list_layout = QVBoxLayout()
        
        # 工具栏
        toolbar_layout = QGridLayout()
        
        # 搜索框
        toolbar_layout.addWidget(QLabel("搜索:"), 0, 0)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入相册名称搜索...")
        self.search_edit.textChanged.connect(self._filter_albums)
        toolbar_layout.addWidget(self.search_edit, 0, 1, 1, 3)
        
        # 数量显示
        self.count_label = QLabel("共 0 个相册")
        toolbar_layout.addWidget(self.count_label, 0, 4)
        
        list_layout.addLayout(toolbar_layout)
        
        # 相册表格
        self.album_table = QTableWidget()
        self.album_table.setColumnCount(5)
        self.album_table.setHorizontalHeaderLabels([
            "选择", "缩略图", "相册名称", "照片数量", "相册ID"
        ])
        
        # 设置列宽
        header = self.album_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 80)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        self.album_table.setColumnHidden(4, True)  # 隐藏ID列
        self.album_table.setAlternatingRowColors(True)
        self.album_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        list_layout.addWidget(self.album_table)
        
        # 选择按钮
        btn_layout = QGridLayout()
        
        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(self._select_all)
        btn_layout.addWidget(select_all_btn, 0, 0)
        
        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.clicked.connect(self._deselect_all)
        btn_layout.addWidget(deselect_all_btn, 0, 1)
        
        invert_btn = QPushButton("反选")
        invert_btn.clicked.connect(self._invert_selection)
        btn_layout.addWidget(invert_btn, 0, 2)
        
        btn_layout.addWidget(QLabel(""), 0, 3)  # 占位
        
        self.selected_count_label = QLabel("已选择: 0 个")
        btn_layout.addWidget(self.selected_count_label, 0, 4)
        
        list_layout.addLayout(btn_layout)
        
        list_group.setLayout(list_layout)
        layout.addWidget(list_group, 1)
        
        # 相册预览
        preview_group = QGroupBox("相册预览")
        preview_layout = QVBoxLayout()
        
        self.preview_label = QLabel("选择相册查看预览")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setFrameStyle(QFrame.Box | QFrame.Sunken)
        preview_layout.addWidget(self.preview_label)
        
        self.preview_info = QTextBrowser()
        self.preview_info.setMaximumHeight(100)
        preview_layout.addWidget(self.preview_info)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # 确定/取消按钮
        button_layout = QGridLayout()
        button_layout.addWidget(QLabel(""), 0, 0)
        
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self._on_ok)
        button_layout.addWidget(ok_btn, 0, 1)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn, 0, 2)
        
        layout.addLayout(button_layout)
        
        # 连接信号
        self.album_table.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _load_albums(self):
        """加载相册列表"""
        self.album_table.setRowCount(0)
        
        for album in self.albums:
            self._add_album_row(album)
        
        self.count_label.setText(f"共 {len(self.albums)} 个相册")
    
    def _add_album_row(self, album: Dict):
        """添加相册行"""
        row = self.album_table.rowCount()
        self.album_table.insertRow(row)
        
        # 选择框
        check_widget = QWidget()
        check_layout = QVBoxLayout(check_widget)
        check_layout.setAlignment(Qt.AlignCenter)
        check_layout.setContentsMargins(0, 0, 0, 0)
        
        check = QCheckBox()
        check.stateChanged.connect(lambda state, a=album: self._on_check_changed(state, a))
        check_layout.addWidget(check)
        
        self.album_table.setCellWidget(row, 0, check_widget)
        
        # 缩略图
        thumbnail_label = QLabel()
        thumbnail_label.setAlignment(Qt.AlignCenter)
        thumbnail_url = album.get('thumbnail', album.get('url_sq', ''))
        if thumbnail_url:
            # 异步加载缩略图
            from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
            from PySide6.QtCore import QUrl
            
            manager = QNetworkAccessManager()
            reply = manager.get(QNetworkRequest(QUrl(thumbnail_url)))
            reply.finished.connect(lambda r=reply, l=thumbnail_label: self._on_thumbnail_loaded(r, l))
        
        self.album_table.setCellWidget(row, 1, thumbnail_label)
        
        # 名称
        title_item = QTableWidgetItem(album.get('title', '未命名'))
        title_item.setData(Qt.UserRole, album)
        self.album_table.setItem(row, 2, title_item)
        
        # 数量
        count_item = QTableWidgetItem(str(album.get('count', 0)))
        self.album_table.setItem(row, 3, count_item)
        
        # ID
        id_item = QTableWidgetItem(album.get('id', ''))
        self.album_table.setItem(row, 4, id_item)
    
    def _on_thumbnail_loaded(self, reply: 'QNetworkReply', label: QLabel):
        """缩略图加载完成"""
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            label.setPixmap(pixmap.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        reply.deleteLater()
    
    def _on_check_changed(self, state: int, album: Dict):
        """复选框状态改变"""
        album_id = album.get('id', '')
        
        if state == Qt.Checked:
            if album_id not in self.selected_albums:
                self.selected_albums.append(album_id)
        else:
            if album_id in self.selected_albums:
                self.selected_albums.remove(album_id)
        
        self.selected_count_label.setText(f"已选择: {len(self.selected_albums)} 个")
    
    def _filter_albums(self, text: str):
        """过滤相册"""
        for row in range(self.album_table.rowCount()):
            item = self.album_table.item(row, 2)
            if item:
                match = text.lower() in item.text().lower() if text else True
                self.album_table.setRowHidden(row, not match)
    
    def _select_all(self):
        """全选"""
        for row in range(self.album_table.rowCount()):
            widget = self.album_table.cellWidget(row, 0)
            if widget:
                for child in widget.children():
                    if isinstance(child, QCheckBox):
                        child.setChecked(True)
    
    def _deselect_all(self):
        """取消全选"""
        for row in range(self.album_table.rowCount()):
            widget = self.album_table.cellWidget(row, 0)
            if widget:
                for child in widget.children():
                    if isinstance(child, QCheckBox):
                        child.setChecked(False)
    
    def _invert_selection(self):
        """反选"""
        for row in range(self.album_table.rowCount()):
            widget = self.album_table.cellWidget(row, 0)
            if widget:
                for child in widget.children():
                    if isinstance(child, QCheckBox):
                        child.setChecked(not child.isChecked())
    
    def _on_selection_changed(self):
        """选择改变"""
        selected_rows = self.album_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            item = self.album_table.item(row, 2)
            if item:
                album = item.data(Qt.UserRole)
                if album:
                    info = f"<b>名称:</b> {album.get('title', 'N/A')}<br>"
                    info += f"<b>ID:</b> {album.get('id', 'N/A')}<br>"
                    info += f"<b>照片数量:</b> {album.get('count', 0)}<br>"
                    info += f"<b>描述:</b> {album.get('description', 'N/A')}"
                    self.preview_info.setHtml(info)
    
    def _on_ok(self):
        """确定"""
        self.albums_selected.emit(self.selected_albums)
        self.accept()
    
    def get_selected_albums(self) -> List[str]:
        """获取选中的相册ID列表"""
        return self.selected_albums.copy()
