# -*- coding: utf-8 -*-
"""
国际化(i18n)模块
提供多语言支持和语言切换功能

功能:
- 自动检测系统语言
- 支持简体中文、繁体中文、英文、日语
- 运行时语言切换
- 配置持久化
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)

# 支持的语言代码
SUPPORTED_LANGUAGES = {
    'zh_CN': '简体中文',
    'zh_TW': '繁體中文',
    'en': 'English',
    'ja': '日本語'
}

# 语言文件所在目录
LANG_DIR = Path(__file__).parent.parent / 'lang'


class LanguageManager(QObject):
    """
    语言管理器 (单例模式)
    
    功能:
    - 加载语言文件
    - 翻译查询
    - 语言切换
    - 配置持久化
    """
    
    # 信号：语言切换时发出
    language_changed = Signal(str)  # 新语言代码
    
    _instance: Optional['LanguageManager'] = None
    _initialized: bool = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config_manager=None):
        """
        初始化语言管理器
        
        Args:
            config_manager: 配置管理器实例，用于保存/读取语言偏好
        """
        if self._initialized:
            return
            
        super().__init__()
        
        self._config_manager = config_manager
        self._current_lang: str = 'zh_CN'
        self._translations: Dict = {}
        self._fallback_translations: Dict = {}
        
        # 确保语言文件目录存在
        if not LANG_DIR.exists():
            LANG_DIR.mkdir(parents=True, exist_ok=True)
        
        # 加载默认语言 (简体中文) 作为后备
        self._load_language('zh_CN')
        
        # 初始化语言设置
        self._initialize_language()
        
        LanguageManager._initialized = True
        logger.info(f"语言管理器初始化完成，当前语言: {self._current_lang}")
    
    def _initialize_language(self):
        """初始化语言设置"""
        # 1. 优先使用配置文件中的用户偏好
        if self._config_manager:
            user_lang = self._config_manager.get('language', '')
            if user_lang == 'auto':
                # 用户选择了自动检测，清除偏好
                detected = self.detect_system_language()
                self._load_language(detected)
                self._current_lang = detected
                return
            elif user_lang and user_lang in SUPPORTED_LANGUAGES:
                self._load_language(user_lang)
                self._current_lang = user_lang
                return
        
        # 2. 否则自动检测系统语言
        detected = self.detect_system_language()
        self._load_language(detected)
        self._current_lang = detected
    
    @staticmethod
    def detect_system_language() -> str:
        """
        检测系统语言
        
        Returns:
            语言代码 (zh_CN, zh_TW, en, ja)
        """
        try:
            from PySide6.QtCore import QLocale
            locale = QLocale.system().name()
            logger.debug(f"检测到系统语言: {locale}")
            
            if locale.startswith("zh_CN") or locale.startswith("zh_Hans"):
                return "zh_CN"
            elif locale.startswith("zh_TW") or locale.startswith("zh_Hant") or locale.startswith("zh_HK"):
                return "zh_TW"
            elif locale.startswith("ja"):
                return "ja"
            else:
                return "en"
        except Exception as e:
            logger.warning(f"检测系统语言失败: {e}，使用默认语言")
            return "zh_CN"
    
    def _load_language(self, lang_code: str) -> bool:
        """
        加载语言文件
        
        Args:
            lang_code: 语言代码
            
        Returns:
            是否加载成功
        """
        lang_file = LANG_DIR / f"{lang_code}.json"
        
        if not lang_file.exists():
            logger.error(f"语言文件不存在: {lang_file}")
            return False
        
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                self._translations = json.load(f)
            logger.info(f"已加载语言文件: {lang_code}")
            return True
        except json.JSONDecodeError as e:
            logger.error(f"语言文件JSON格式错误: {e}")
            return False
        except Exception as e:
            logger.error(f"加载语言文件失败: {e}")
            return False
    
    def _load_fallback(self):
        """加载后备语言 (简体中文)"""
        fallback_file = LANG_DIR / "zh_CN.json"
        if fallback_file.exists():
            try:
                with open(fallback_file, 'r', encoding='utf-8') as f:
                    self._fallback_translations = json.load(f)
            except Exception as e:
                logger.error(f"加载后备语言文件失败: {e}")
    
    def t(self, key: str, default: str = None) -> str:
        """
        获取翻译文本
        
        Args:
            key: 翻译键，支持点号路径，如 "main_window.title"
            default: 默认值，当找不到翻译时返回
            
        Returns:
            翻译后的文本
        """
        # 支持点号分隔的路径
        keys = key.split('.')
        
        # 尝试从当前语言获取
        value = self._translations
        try:
            for k in keys:
                value = value[k]
            if isinstance(value, str):
                return value
        except (KeyError, TypeError):
            pass
        
        # 尝试从后备语言获取
        value = self._fallback_translations
        try:
            for k in keys:
                value = value[k]
            if isinstance(value, str):
                logger.debug(f"使用后备翻译: {key}")
                return value
        except (KeyError, TypeError):
            pass
        
        # 返回默认值或原始键
        if default is not None:
            return default
        return key
    
    def get_current_language(self) -> str:
        """
        获取当前语言代码
        
        Returns:
            语言代码
        """
        return self._current_lang
    
    def get_current_language_name(self) -> str:
        """
        获取当前语言名称
        
        Returns:
            语言名称
        """
        return SUPPORTED_LANGUAGES.get(self._current_lang, self._current_lang)
    
    @Slot(str)
    def switch_language(self, lang_code: str, save_preference: bool = True):
        """
        切换语言
        
        Args:
            lang_code: 目标语言代码
            save_preference: 是否保存用户偏好到配置
        """
        if lang_code not in SUPPORTED_LANGUAGES:
            logger.error(f"不支持的语言代码: {lang_code}")
            return
        
        if lang_code == self._current_lang:
            return
        
        logger.info(f"切换语言: {self._current_lang} -> {lang_code}")
        
        # 加载新语言
        if not self._load_language(lang_code):
            logger.error(f"切换语言失败: {lang_code}")
            return
        
        # 更新当前语言
        old_lang = self._current_lang
        self._current_lang = lang_code
        
        # 保存用户偏好
        if save_preference and self._config_manager:
            if lang_code == self.detect_system_language():
                # 如果切换到与系统语言相同的语言，清除偏好（使用自动检测）
                self._config_manager['language'] = 'auto'
            else:
                self._config_manager['language'] = lang_code
            self._config_manager.save()
        
        # 发出语言切换信号
        self.language_changed.emit(lang_code)
        logger.info(f"语言切换完成: {lang_code}")
    
    def clear_preference(self):
        """清除语言偏好，使用自动检测"""
        if self._config_manager:
            self._config_manager['language'] = 'auto'
            self._config_manager.save()
        
        detected = self.detect_system_language()
        self.switch_language(detected, save_preference=False)
    
    @staticmethod
    def get_supported_languages() -> Dict[str, str]:
        """
        获取支持的语言列表
        
        Returns:
            语言代码到名称的映射
        """
        return SUPPORTED_LANGUAGES.copy()
    
    def reload(self):
        """重新加载当前语言"""
        self._load_language(self._current_lang)


# 全局便捷函数
def t(key: str, default: str = None) -> str:
    """
    获取翻译文本的便捷函数
    
    Args:
        key: 翻译键
        default: 默认值
        
    Returns:
        翻译后的文本
    """
    if LanguageManager._instance is None:
        # 如果未初始化，返回默认值
        return default if default is not None else key
    return LanguageManager._instance.t(key, default)


def switch_language(lang_code: str):
    """
    切换语言的便捷函数
    
    Args:
        lang_code: 目标语言代码
    """
    if LanguageManager._instance is not None:
        LanguageManager._instance.switch_language(lang_code)
