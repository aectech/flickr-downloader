# -*- coding: utf-8 -*-
"""
照片选择对话框
用于人工挑选照片

修复原项目bug:
- 分页浏览功能
- 支持勾选
- 现代PySide6组件
"""

import logging
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, 
                                QCheckBox, QComboBox, QDialog,
                                QFrame, QGridLayout, QGroupBox,
                                QHeaderView, QLabel, QLineEdit,
                                QListWidget, QListWidgetItem,
                                QMessageBox, QPaginationWidget,
                                QPushButton, QScrollArea,
                                QSizePolicy, QSpinBox, QSplitter,
                                QTableWidget, QTableWidgetItem,
                                QTextBrowser, QVBoxLayout, QWidget)

logger = logging.getLogger(__name__)


class PhotoPickerDialog(QDialog):
    """
    照片选择对话框
    
    功能:
    - 显示照片缩略图列表
    - 分页浏览
    - 支持勾选
    - 显示照片信息
    """
    
    # 信号：确认选择
    photos_selected = Signal(list)  # 选中的照片URL列表
    
    def __init__(self, photos: List[Dict] = None, 
                 per_page: int = 50,
                 total_count: int = 0,
                 parent=None):
        """
        初始化对话框
        
        Args:
            photos: 照片列表
            per_page: 每页显示数量
            total_count: 总数量
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.setWindowTitle("选择照片")
        self.setMinimumSize(900, 700)
        
        self.photos = photos or []
        self.per_page = per_page
        self.total_count = total_count or len(self.photos)
        self.current_page = 1
        self.total_pages = max(1, (self.total_count + per_page - 1) // per_page)
        
        self.selected_photos: List[str] = []
        
        self._init_ui()
        self._load_photos()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar_layout = QGridLayout()
        
        # 搜索框
        toolbar_layout.addWidget(QLabel("搜索:"), 0, 0)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入照片标题搜索...")
        self.search_edit.textChanged.connect(self._filter_photos)
        toolbar_layout.addWidget(self.search_edit, 0, 1, 1, 3)
        
        # 每页数量
        toolbar_layout.addWidget(QLabel("每页:"), 0, 4)
        self.per_page_spin = QSpinBox()
        self.per_page_spin.setRange(10, 100)
        self.per_page_spin.setValue(self.per_page)
        self.per_page_spin.valueChanged.connect(self._on_per_page_changed)
        toolbar_layout.addWidget(self.per_page_spin, 0, 5)
        
        # 数量显示
        self.count_label = QLabel(f"共 {self.total_count} 张照片")
        toolbar_layout.addWidget(self.count_label, 0, 6)
        
        layout.addLayout(toolbar_layout)
        
        # 照片表格
        list_group = QGroupBox("照片列表")
        list_layout = QVBoxLayout()
        
        self.photo_table = QTableWidget()
        self.photo_table.setColumnCount(5)
        self.photo_table.setHorizontalHeaderLabels([
            "选择", "缩略图", "标题", "ID", "日期"
        ])
        
        # 设置列宽
        header = self.photo_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 100)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        self.photo_table.setAlternatingRowColors(True)
        self.photo_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        list_layout.addWidget(self.photo_table)
        
        # 分页控制
        page_layout = QGridLayout()
        
        self.prev_btn = QPushButton("上一页")
        self.prev_btn.clicked.connect(self._prev_page)
        page_layout.addWidget(self.prev_btn, 0, 0)
        
        self.page_label = QLabel(f"第 {self.current_page} / {self.total_pages} 页")
        page_layout.addWidget(self.page_label, 0, 1)
        
        self.next_btn = QPushButton("下一页")
        self.next_btn.clicked.connect(self._next_page)
        page_layout.addWidget(self.next_btn, 0, 2)
        
        self.goto_edit = QLineEdit()
        self.goto_edit.setPlaceholderText("页码")
        self.goto_edit.setMaximumWidth(60)
        self.goto_edit.returnPressed.connect(self._goto_page)
        page_layout.addWidget(self.goto_edit, 0, 3)
        
        goto_btn = QPushButton("跳转")
        goto_btn.clicked.connect(self._goto_page)
        page_layout.addWidget(goto_btn, 0, 4)
        
        page_layout.addWidget(QLabel(""), 0, 5)  # 占位
        
        # 选择按钮
        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(self._select_all)
        page_layout.addWidget(select_all_btn, 0, 6)
        
        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.clicked.connect(self._deselect_all)
        page_layout.addWidget(deselect_all_btn, 0, 7)
        
        invert_btn = QPushButton("反选")
        invert_btn.clicked.connect(self._invert_selection)
        page_layout.addWidget(invert_btn, 0, 8)
        
        self.selected_count_label = QLabel("已选择: 0 张")
        page_layout.addWidget(self.selected_count_label, 0, 9)
        
        list_layout.addLayout(page_layout)
        
        list_group.setLayout(list_layout)
        layout.addWidget(list_group, 1)
        
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
        self.photo_table.itemSelectionChanged.connect(self._on_selection_changed)
        self._update_page_buttons()
    
    def _load_photos(self):
        """加载照片列表"""
        self.photo_table.setRowCount(0)
        
        start_idx = (self.current_page - 1) * self.per_page
        end_idx = min(start_idx + self.per_page, len(self.photos))
        
        for i in range(start_idx, end_idx):
            photo = self.photos[i]
            self._add_photo_row(photo, i)
        
        self.page_label.setText(f"第 {self.current_page} / {self.total_pages} 页")
    
    def _add_photo_row(self, photo: Dict, index: int):
        """添加照片行"""
        row = self.photo_table.rowCount()
        self.photo_table.insertRow(row)
        
        # 选择框
        check_widget = QWidget()
        check_layout = QVBoxLayout(check_widget)
        check_layout.setAlignment(Qt.AlignCenter)
        check_layout.setContentsMargins(0, 0, 0, 0)
        
        check = QCheckBox()
        check.stateChanged.connect(lambda state, p=photo: self._on_check_changed(state, p))
        check_layout.addWidget(check)
        
        self.photo_table.setCellWidget(row, 0, check_widget)
        
        # 缩略图
        thumbnail_label = QLabel()
        thumbnail_label.setAlignment(Qt.AlignCenter)
        thumbnail_url = photo.get('url_sq', photo.get('url_s', ''))
        if thumbnail_url:
            from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
            from PySide6.QtCore import QUrl
            
            manager = QNetworkAccessManager()
            reply = manager.get(QNetworkRequest(QUrl(thumbnail_url)))
            reply.finished.connect(lambda r=reply, l=thumbnail_label: self._on_thumbnail_loaded(r, l))
        
        self.photo_table.setCellWidget(row, 1, thumbnail_label)
        
        # 标题
        title = photo.get('title', '未命名')
        title_item = QTableWidgetItem(title)
        title_item.setData(Qt.UserRole, photo)
        self.photo_table.setItem(row, 2, title_item)
        
        # ID
        id_item = QTableWidgetItem(photo.get('id', ''))
        self.photo_table.setItem(row, 3, id_item)
        
        # 日期
        date_item = QTableWidgetItem(photo.get('datetaken', ''))
        self.photo_table.setItem(row, 4, date_item)
    
    def _on_thumbnail_loaded(self, reply: 'QNetworkReply', label: QLabel):
        """缩略图加载完成"""
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            label.setPixmap(pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        reply.deleteLater()
    
    def _on_check_changed(self, state: int, photo: Dict):
        """复选框状态改变"""
        photo_url = photo.get('url_o', photo.get('url_k', photo.get('id', '')))
        
        if state == Qt.Checked:
            if photo_url not in self.selected_photos:
                self.selected_photos.append(photo_url)
        else:
            if photo_url in self.selected_photos:
                self.selected_photos.remove(photo_url)
        
        self.selected_count_label.setText(f"已选择: {len(self.selected_photos)} 张")
    
    def _filter_photos(self, text: str):
        """过滤照片"""
        for row in range(self.photo_table.rowCount()):
            item = self.photo_table.item(row, 2)
            if item:
                match = text.lower() in item.text().lower() if text else True
                self.photo_table.setRowHidden(row, not match)
    
    def _select_all(self):
        """全选"""
        for row in range(self.photo_table.rowCount()):
            widget = self.photo_table.cellWidget(row, 0)
            if widget:
                for child in widget.children():
                    if isinstance(child, QCheckBox):
                        child.setChecked(True)
    
    def _deselect_all(self):
        """取消全选"""
        for row in range(self.photo_table.rowCount()):
            widget = self.photo_table.cellWidget(row, 0)
            if widget:
                for child in widget.children():
                    if isinstance(child, QCheckBox):
                        child.setChecked(False)
    
    def _invert_selection(self):
        """反选"""
        for row in range(self.photo_table.rowCount()):
            widget = self.photo_table.cellWidget(row, 0)
            if widget:
                for child in widget.children():
                    if isinstance(child, QCheckBox):
                        child.setChecked(not child.isChecked())
    
    def _on_selection_changed(self):
        """选择改变"""
        pass
    
    def _prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self._load_photos()
            self._update_page_buttons()
    
    def _next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._load_photos()
            self._update_page_buttons()
    
    def _goto_page(self):
        """跳转到指定页"""
        try:
            page = int(self.goto_edit.text())
            if 1 <= page <= self.total_pages:
                self.current_page = page
                self._load_photos()
                self._update_page_buttons()
        except ValueError:
            pass
    
    def _on_per_page_changed(self, value: int):
        """每页数量改变"""
        self.per_page = value
        self.total_pages = max(1, (self.total_count + value - 1) // value)
        self.current_page = min(self.current_page, self.total_pages)
        self._load_photos()
        self._update_page_buttons()
    
    def _update_page_buttons(self):
        """更新分页按钮状态"""
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)
    
    def _on_ok(self):
        """确定"""
        if not self.selected_photos:
            QMessageBox.warning(self, "提示", "请至少选择一张照片")
            return
        
        self.photos_selected.emit(self.selected_photos)
        self.accept()
    
    def get_selected_photos(self) -> List[str]:
        """获取选中的照片URL列表"""
        return self.selected_photos.copy()
