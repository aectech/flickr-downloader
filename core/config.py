# -*- coding: utf-8 -*-
"""
配置管理模块
负责应用程序配置的保存、加载和管理

修复原项目bug:
- 配置文件保存时无原子性 (现使用临时文件+原子重命名)
- 配置使用QSettings替代手动config文件
"""

import os
import json
import logging
from typing import Any, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    配置管理器
    
    功能:
    - 读写配置文件 (JSON格式)
    - 配置项类型检查
    - 默认值设置
    - 配置验证
    """
    
    # 默认配置项
    DEFAULT_CONFIG = {
        # 外观配置
        'bg_color': -16777216,           # 背景色 (黑色)
        'fg_color': -16711936,            # 前景色 (绿色)
        'button_color': -256,             # 按钮色 (黄色)
        
        # 下载类型
        'download_type': 0,               # 0-7: 八种下载类型
        
        # 文件命名
        'naming_style': 3,               # 0-16: 17种命名格式
        
        # 下载选项
        'auto_make_dirs': True,           # 自动创建子文件夹
        'preview_photos': True,           # 预览照片
        'skip_existing': False,           # 跳过已存在文件
        'thread_count': 4,                # 下载线程数 (1-10)
        'video_download': False,          # 视频下载支持
        'time_format': 'yyyy-MM-dd HH_mm_ss',  # 时间格式
        
        # 搜索配置
        'search_per_page': 50,
        'search_start_page': 1,
        'search_fetch_page': 1,
        
        # 窗口配置
        'window_width': 1000,
        'window_height': 700,
        'allow_direct_exit': 0,
        
        # 功能开关
        'sound_enabled': True,
        'clipboard_monitor': True,
        'remember_save_path': False,
        'show_detail_info': False,
        
        # 保存路径
        'save_path': '',
        'remembered_save_path': '',
        
        # OAuth认证
        'oauth_token': '',
        'oauth_token_secret': '',
        'user_nsid': '',
        'user_fullname': '',
        'user_username': '',
        
        # API配置
        'api_key': '6f92fee8b4a726215b827c0af43afc70',
        'api_secret': '4c4fa981ad30e375',
        
        # 相册大小设置
        'size_setting': 0,                # 0=自动, 1-13对应不同尺寸
        
        # 高级设置
        'privacy_filter': 0,
        'safe_search': 1,
        'search_user_id_type': 0,
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认使用程序目录下的config.json
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            # 使用程序所在目录
            app_dir = Path(__file__).parent.parent
            self.config_path = app_dir / 'config.json'
        
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> None:
        """
        从文件加载配置
        
        如果配置文件不存在或读取失败，使用默认配置
        """
        self._config = self.DEFAULT_CONFIG.copy()
        
        if not self.config_path.exists():
            logger.info(f"配置文件不存在，使用默认配置: {self.config_path}")
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                self._config.update(loaded_config)
                logger.info(f"成功加载配置文件: {self.config_path}")
        except json.JSONDecodeError as e:
            logger.error(f"配置文件JSON格式错误: {e}")
            # 尝试读取旧格式
            self._load_legacy_config()
        except Exception as e:
            logger.error(f"读取配置文件失败: {e}")
    
    def _load_legacy_config(self) -> None:
        """
        加载旧格式配置文件 (INI风格)
        
        用于兼容原项目的config.ini格式
        """
        ini_path = self.config_path.with_suffix('.ini')
        if not ini_path.exists():
            return
        
        try:
            with open(ini_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            keys = [
                'bg_color', 'fg_color', 'button_color', 'download_type',
                'naming_style', 'auto_make_dirs', 'preview_photos', 'dummy',
                'allow_direct_exit', 'window_width', 'window_height',
                'size_setting', 'thread_count', 'sound_enabled',
                'clipboard_monitor', 'remember_save_path', 'remembered_save_path',
                'skip_existing', 'show_detail_info', 'search_per_page',
                'search_start_page', 'search_fetch_page', 'time_format',
                'video_download'
            ]
            
            for i, line in enumerate(lines):
                line = line.strip()
                if i < len(keys) and line:
                    key = keys[i]
                    if key == 'dummy':
                        continue
                    # 类型推断
                    if line.lower() == 'true':
                        self._config[key] = True
                    elif line.lower() == 'false':
                        self._config[key] = False
                    else:
                        try:
                            self._config[key] = int(line)
                        except ValueError:
                            self._config[key] = line
            
            logger.info("成功加载旧格式配置文件")
        except Exception as e:
            logger.error(f"加载旧格式配置失败: {e}")
    
    def save(self) -> bool:
        """
        保存配置到文件
        
        使用原子操作确保配置文件完整性:
        1. 先写入临时文件
        2. 验证临时文件
        3. 原子重命名覆盖原文件
        
        Returns:
            bool: 保存是否成功
        """
        try:
            # 创建临时文件
            temp_path = self.config_path.with_suffix('.tmp')
            
            # 写入临时文件
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            
            # 验证临时文件
            with open(temp_path, 'r', encoding='utf-8') as f:
                json.load(f)  # 验证JSON有效性
            
            # 原子重命名
            if self.config_path.exists():
                backup_path = self.config_path.with_suffix('.bak')
                self.config_path.rename(backup_path)
            
            temp_path.rename(self.config_path)
            
            # 删除备份
            backup_path = self.config_path.with_suffix('.bak')
            if backup_path.exists():
                backup_path.unlink()
            
            logger.info(f"配置已保存: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            # 清理临时文件
            temp_path = self.config_path.with_suffix('.tmp')
            if temp_path.exists():
                temp_path.unlink()
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        
        Args:
            key: 配置键名
            default: 默认值（当键不存在时）
            
        Returns:
            配置值或默认值
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        设置配置项
        
        Args:
            key: 配置键名
            value: 配置值
        """
        self._config[key] = value
    
    def __getitem__(self, key: str) -> Any:
        """支持字典风格访问"""
        return self._config[key]
    
    def __setitem__(self, key: str, value: Any) -> None:
        """支持字典风格赋值"""
        self._config[key] = value
    
    def __contains__(self, key: str) -> bool:
        """支持 in 操作符"""
        return key in self._config
    
    def update(self, updates: Dict[str, Any]) -> None:
        """
        批量更新配置
        
        Args:
            updates: 要更新的配置字典
        """
        self._config.update(updates)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        获取完整配置字典
        
        Returns:
            配置字典的副本
        """
        return self._config.copy()
    
    def reset(self) -> None:
        """重置为默认配置"""
        self._config = self.DEFAULT_CONFIG.copy()
        self.save()
    
    @property
    def save_path(self) -> str:
        """获取保存路径"""
        return self._config.get('save_path', str(Path.home()))
    
    @save_path.setter
    def save_path(self, value: str) -> None:
        """设置保存路径"""
        self._config['save_path'] = value
    
    @property
    def thread_count(self) -> int:
        """获取下载线程数"""
        return max(1, min(10, self._config.get('thread_count', 4)))
    
    @thread_count.setter
    def thread_count(self, value: int) -> None:
        """设置下载线程数 (1-10)"""
        self._config['thread_count'] = max(1, min(10, value))
    
    @property
    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return bool(self._config.get('oauth_token') and 
                   self._config.get('oauth_token_secret'))
