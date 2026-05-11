# -*- coding: utf-8 -*-
"""
文件命名策略模块
实现17种文件命名格式

修复原项目bug:
- 消除重复代码，使用统一的命名策略类
- 优化性能，减少不必要的操作
"""

import re
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class NamingStrategy:
    """
    文件命名策略
    
    支持17种命名格式:
    0:  数字序号 (001, 002, ...)
    1:  原标题 (Photo Title)
    2:  原ID (Photo ID)
    3:  标题-ID (Title - ID)
    4:  ID-标题 (ID - Title)
    5:  相簿名-标题-ID (Album - Title - ID)
    6:  相簿名-ID (Album - ID)
    7:  相簿名-标题 (Album - Title)
    8:  拍摄日期-标题-ID (DateTaken - Title - ID)
    9:  拍摄日期-标题 (DateTaken - Title)
    10: 拍摄日期-ID (DateTaken - ID)
    11: 标题-ID-拍摄日期 (Title - ID - DateTaken)
    12: 标题-拍摄日期-ID (Title - DateTaken - ID)
    13: 标题-拍摄日期 (Title - DateTaken)
    14: ID-拍摄日期-标题 (ID - DateTaken - Title)
    15: ID-拍摄日期 (ID - DateTaken)
    16: 拍摄日期 (DateTaken)
    """
    
    # 命名格式名称映射
    FORMAT_NAMES = {
        0: "数字序号",
        1: "原标题",
        2: "原ID",
        3: "标题-ID",
        4: "ID-标题",
        5: "相簿名-标题-ID",
        6: "相簿名-ID",
        7: "相簿名-标题",
        8: "拍摄日期-标题-ID",
        9: "拍摄日期-标题",
        10: "拍摄日期-ID",
        11: "标题-ID-拍摄日期",
        12: "标题-拍摄日期-ID",
        13: "标题-拍摄日期",
        14: "ID-拍摄日期-标题",
        15: "ID-拍摄日期",
        16: "拍摄日期"
    }
    
    def __init__(self, style: int = 3, time_format: str = 'yyyy-MM-dd HH_mm_ss'):
        """
        初始化命名策略
        
        Args:
            style: 命名格式索引 (0-16)
            time_format: 时间格式字符串
        """
        self.style = max(0, min(16, style))
        self.time_format = self._convert_time_format(time_format)
    
    def _convert_time_format(self, format_str: str) -> str:
        """
        转换时间格式字符串
        
        将类似 'yyyy-MM-dd HH_mm_ss' 的格式转换为Python格式
        
        Args:
            format_str: Java风格格式字符串
            
        Returns:
            Python strftime格式字符串
        """
        # 简单映射
        mapping = {
            'yyyy': '%Y',
            'MM': '%m',
            'dd': '%d',
            'HH': '%H',
            'mm': '%M',
            'ss': '%S',
            '_': '_',
            '-': '-',
            ' ': ' '
        }
        
        result = format_str
        for java_fmt, python_fmt in sorted(mapping.items(), key=lambda x: -len(x[0])):
            result = result.replace(java_fmt, python_fmt)
        
        return result
    
    def generate_name(self,
                     index: int,
                     photo_id: str,
                     title: str,
                     album_name: str = '',
                     date_taken: str = '',
                     time_format: Optional[str] = None) -> str:
        """
        生成文件名
        
        Args:
            index: 文件序号
            photo_id: 照片ID
            title: 照片标题
            album_name: 相册名称
            date_taken: 拍摄日期 (格式: yyyy-MM-dd HH:mm:ss)
            time_format: 自定义时间格式
            
        Returns:
            生成的文件名（不含扩展名）
        """
        # 清理标题
        title = self._clean_title(title)
        
        # 格式化日期
        formatted_date = self._format_date(date_taken, time_format)
        
        # 根据格式生成文件名
        return self._generate_by_style(
            self.style, index, photo_id, title, album_name, formatted_date
        )
    
    def _generate_by_style(self, style: int, index: int, photo_id: str,
                          title: str, album_name: str, 
                          formatted_date: str) -> str:
        """根据风格生成文件名"""
        
        # 统一格式化序号为3位补零
        index_str = str(index).zfill(3)
        
        # 格式化ID
        id_str = str(photo_id) if photo_id else ''
        
        # 格式化标题
        title_str = title if title else '未命名'
        
        # 格式化相册名
        album_str = self._clean_title(album_name) if album_name else ''
        
        # 根据不同风格生成
        generators = {
            0: lambda: index_str,
            1: lambda: title_str,
            2: lambda: id_str,
            3: lambda: f"{title_str} - {id_str}",
            4: lambda: f"{id_str} - {title_str}",
            5: lambda: f"{album_str} - {title_str} - {id_str}" if album_str else f"{title_str} - {id_str}",
            6: lambda: f"{album_str} - {id_str}" if album_str else id_str,
            7: lambda: f"{album_str} - {title_str}" if album_str else title_str,
            8: lambda: f"{formatted_date} - {title_str} - {id_str}" if formatted_date else f"{title_str} - {id_str}",
            9: lambda: f"{formatted_date} - {title_str}" if formatted_date else title_str,
            10: lambda: f"{formatted_date} - {id_str}" if formatted_date else id_str,
            11: lambda: f"{title_str} - {id_str} - {formatted_date}" if formatted_date else f"{title_str} - {id_str}",
            12: lambda: f"{title_str} - {formatted_date} - {id_str}" if formatted_date else f"{title_str} - {id_str}",
            13: lambda: f"{title_str} - {formatted_date}" if formatted_date else title_str,
            14: lambda: f"{id_str} - {formatted_date} - {title_str}" if formatted_date else f"{id_str} - {title_str}",
            15: lambda: f"{id_str} - {formatted_date}" if formatted_date else id_str,
            16: lambda: formatted_date if formatted_date else index_str,
        }
        
        generator = generators.get(style, generators[3])
        return generator()
    
    def _clean_title(self, title: str) -> str:
        """
        清理标题，移除非法字符
        
        Args:
            title: 原始标题
            
        Returns:
            清理后的标题
        """
        if not title:
            return ''
        
        # Windows文件名非法字符
        illegal_chars = r'<>:"/\|?*'
        for char in illegal_chars:
            title = title.replace(char, '_')
        
        # 移除控制字符
        title = ''.join(c for c in title if ord(c) >= 32)
        
        # 移除多余空格
        title = ' '.join(title.split())
        
        return title.strip()
    
    def _format_date(self, date_str: str, 
                    custom_format: Optional[str] = None) -> str:
        """
        格式化日期字符串
        
        Args:
            date_str: 原始日期字符串 (格式: yyyy-MM-dd HH:mm:ss)
            custom_format: 自定义格式
            
        Returns:
            格式化后的日期字符串
        """
        if not date_str:
            return ''
        
        try:
            # 解析日期
            if 'T' in date_str:
                # ISO格式
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                # 标准格式
                dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            
            # 格式化
            fmt = custom_format or self.time_format
            return dt.strftime(fmt)
            
        except ValueError:
            # 尝试简单解析
            try:
                dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
                fmt = custom_format or self.time_format
                # 只取日期部分
                return dt.strftime(fmt.split()[0] if ' ' in fmt else fmt)
            except ValueError:
                logger.debug(f"无法解析日期: {date_str}")
                return ''
    
    def get_style_name(self, style: Optional[int] = None) -> str:
        """
        获取格式名称
        
        Args:
            style: 格式索引，默认使用当前风格
            
        Returns:
            格式名称
        """
        style = style if style is not None else self.style
        return self.FORMAT_NAMES.get(style, "未知格式")
    
    @classmethod
    def get_all_style_names(cls) -> Dict[int, str]:
        """
        获取所有格式名称
        
        Returns:
            格式ID到名称的映射字典
        """
        return cls.FORMAT_NAMES.copy()
    
    def set_style(self, style: int) -> None:
        """
        设置命名风格
        
        Args:
            style: 风格索引 (0-16)
        """
        self.style = max(0, min(16, style))
    
    def set_time_format(self, format_str: str) -> None:
        """
        设置时间格式
        
        Args:
            format_str: Java风格时间格式字符串
        """
        self.time_format = self._convert_time_format(format_str)
    
    @staticmethod
    def find_new_filename(base_path: str, extension: str) -> str:
        """
        查找不冲突的文件名
        
        如果文件已存在，添加数字后缀
        
        Args:
            base_path: 基础路径（不含扩展名）
            extension: 文件扩展名
            
        Returns:
            不冲突的文件名
        """
        from pathlib import Path
        
        path = Path(base_path)
        if not path.exists():
            return str(path) + extension
        
        # 尝试添加数字后缀
        counter = 1
        while True:
            new_path = Path(f"{base_path}_{counter}")
            if not new_path.exists():
                return str(new_path) + extension
            counter += 1
            if counter > 999:  # 防止无限循环
                return str(new_path) + extension
    
    @staticmethod
    def find_new_dirname(base_path: str) -> str:
        """
        查找不冲突的目录名
        
        Args:
            base_path: 基础路径
            
        Returns:
            不冲突的目录名
        """
        from pathlib import Path
        
        path = Path(base_path)
        if not path.exists():
            return str(path)
        
        counter = 1
        while True:
            new_path = Path(f"{base_path}_{counter}")
            if not new_path.exists():
                return str(new_path)
            counter += 1
            if counter > 999:
                return str(new_path)
