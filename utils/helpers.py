# -*- coding: utf-8 -*-
"""
工具函数模块
包含加密、EXIF处理等辅助功能

修复原项目bug:
- 移除SSL证书验证禁用代码 (安全风险)
- 正确的EXIF方向处理
"""

import base64
import hashlib
import hmac
import logging
import struct
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ==================== 加密相关 ====================

def create_hash(password: bytes) -> bytes:
    """
    创建自定义哈希 (保留原项目算法)
    
    Args:
        password: 密码字节
        
    Returns:
        哈希结果
    """
    if len(password) == 0:
        return b''
    
    password90_str = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/=-*~!@#$%^&()_{}<>[]'`,.?|"
    
    result = []
    hash_bytes = []
    
    p = password[0]
    start = password[0]
    d = 0
    d_len = len(password)
    i = 0
    
    # 第一个循环
    while True:
        p = (p + password[d]) % 251
        hash_bytes.append(p)
        
        if d == 0 and p == start or i >= 10000:
            break
        
        d += 1
        i += 1
        if d == d_len:
            d = 0
    
    # 第二个循环
    i = 0
    while True:
        p = ((p + 1) * (password[d] + 1)) % 251
        hash_bytes.append(p)
        
        if (d == 0 and p == start) or i >= 10000:
            break
        
        d += 1
        i += 1
        if d == d_len:
            d = 0
    
    return bytes(hash_bytes)


def weil_90_encode(data: bytes, password: str) -> str:
    """
    自定义加密编码 (保留原项目算法)
    
    Args:
        data: 要编码的数据
        password: 密码
        
    Returns:
        编码后的字符串
    """
    if not data:
        return ''
    
    password90_str = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/=-*~!@#$%^&()_{}<>[]'`,.?|"
    
    hash_bytes = create_hash(password.encode('utf-8'))
    if not hash_bytes:
        return base64.b64encode(data).decode('ascii')
    
    # 生成随机索引
    import random
    i4 = random.randint(0, len(hash_bytes) - 1)
    i3 = random.randint(0, len(hash_bytes) - 1)
    i2 = random.randint(0, len(hash_bytes) - 1)
    i1 = random.randint(0, len(hash_bytes) - 1)
    
    tag = f"{i4}:{i3}:{i2}:{i1}"
    
    result = []
    for i, byte in enumerate(data):
        pw_byte = (hash_bytes[i4] * 7 + hash_bytes[i3] * 5 + 
                   hash_bytes[i2] * 3 + hash_bytes[i1]) % 256
        encoded = (pw_byte + byte) % 256
        result.append(password90_str[encoded])
        
        # 更新索引
        i4 += 1
        if i4 >= len(hash_bytes):
            i4 = 0
            i3 += 1
            if i3 >= len(hash_bytes):
                i3 = 0
                i2 += 1
                if i2 >= len(hash_bytes):
                    i2 = 0
                    i1 += 1
                    if i1 >= len(hash_bytes):
                        i4 = i3 = i2 = i1 = 0
    
    return ''.join(result) + ':' + tag


def weil_90_decode(encoded: str, password: str) -> Optional[bytes]:
    """
    自定义加密解码 (保留原项目算法)
    
    Args:
        encoded: 编码字符串
        password: 密码
        
    Returns:
        解码后的数据，失败返回None
    """
    if not encoded:
        return None
    
    password90_str = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/=-*~!@#$%^&()_{}<>[]'`,.?|"
    
    hash_bytes = create_hash(password.encode('utf-8'))
    if not hash_bytes:
        return None
    
    try:
        # 解析标签
        parts = encoded.rsplit(':', 1)
        if len(parts) != 2:
            return None
        
        data_str, tag = parts
        tag_parts = tag.split(':')
        if len(tag_parts) != 4:
            return None
        
        i4, i3, i2, i1 = map(int, tag_parts)
        
        # 解码
        result = []
        for char in data_str:
            if char not in password90_str:
                continue
            
            encoded_val = password90_str.index(char)
            pw_byte = (hash_bytes[i4] * 7 + hash_bytes[i3] * 5 + 
                       hash_bytes[i2] * 3 + hash_bytes[i1]) % 256
            decoded = (encoded_val - pw_byte) % 256
            result.append(decoded)
            
            # 更新索引
            i4 += 1
            if i4 >= len(hash_bytes):
                i4 = 0
                i3 += 1
                if i3 >= len(hash_bytes):
                    i3 = 0
                    i2 += 1
                    if i2 >= len(hash_bytes):
                        i2 = 0
                        i1 += 1
                        if i1 >= len(hash_bytes):
                            i4 = i3 = i2 = i1 = 0
        
        return bytes(result)
        
    except Exception as e:
        logger.error(f"解码失败: {e}")
        return None


# ==================== EXIF相关 ====================

def get_exif_orientation(image_path: str) -> int:
    """
    获取图片EXIF方向值
    
    Args:
        image_path: 图片路径
        
    Returns:
        EXIF方向值 (1-8)，无EXIF返回1
    """
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        
        with Image.open(image_path) as img:
            exif = img._getexif()
            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == 'Orientation':
                        return value
        
        return 1
        
    except Exception as e:
        logger.debug(f"获取EXIF方向失败: {image_path} - {e}")
        return 1


def correct_image_orientation(image_path: str, 
                              output_path: Optional[str] = None) -> bool:
    """
    修正图片方向
    
    根据EXIF Orientation标签旋转/翻转图片
    
    Args:
        image_path: 图片路径
        output_path: 输出路径，默认覆盖原文件
        
    Returns:
        是否成功
    """
    try:
        from PIL import Image
        
        output_path = output_path or image_path
        
        with Image.open(image_path) as img:
            # 获取方向
            orientation = 1
            try:
                exif = img._getexif()
                if exif:
                    for tag_id, value in exif.items():
                        from PIL.ExifTags import TAGS
                        if TAGS.get(tag_id) == 'Orientation':
                            orientation = value
                            break
            except (AttributeError, KeyError):
                pass
            
            # 根据方向旋转
            rotated = img
            if orientation == 2:
                rotated = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 3:
                rotated = img.rotate(180, expand=True)
            elif orientation == 4:
                rotated = img.transpose(Image.FLIP_TOP_BOTTOM)
            elif orientation == 5:
                rotated = img.transpose(Image.FLIP_LEFT_RIGHT).rotate(90, expand=True)
            elif orientation == 6:
                rotated = img.rotate(270, expand=True)
            elif orientation == 7:
                rotated = img.transpose(Image.FLIP_LEFT_RIGHT).rotate(270, expand=True)
            elif orientation == 8:
                rotated = img.rotate(90, expand=True)
            
            # 保存
            rotated.save(output_path, img.format or 'JPEG', quality=95)
            
        logger.debug(f"已修正图片方向: {image_path}")
        return True
        
    except Exception as e:
        logger.error(f"修正图片方向失败: {image_path} - {e}")
        return False


# ==================== 文件操作相关 ====================

def get_file_extension(url: str, content_type: str = '') -> str:
    """
    从URL或Content-Type获取文件扩展名
    
    Args:
        url: 文件URL
        content_type: Content-Type头
        
    Returns:
        扩展名（含点）
    """
    # 从URL获取
    import re
    url_ext_match = re.search(r'\.([a-zA-Z0-9]+)(?:\?|$)', url)
    if url_ext_match:
        ext = '.' + url_ext_match.group(1).lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mov', '.avi']:
            return ext
    
    # 从Content-Type推断
    content_type_lower = content_type.lower()
    if 'jpeg' in content_type_lower or 'jpg' in content_type_lower:
        return '.jpg'
    elif 'png' in content_type_lower:
        return '.png'
    elif 'gif' in content_type_lower:
        return '.gif'
    elif 'webp' in content_type_lower:
        return '.webp'
    elif 'video/mp4' in content_type_lower:
        return '.mp4'
    elif 'quicktime' in content_type_lower or 'mov' in content_type_lower:
        return '.mov'
    elif 'video' in content_type_lower:
        return '.mp4'
    
    # 默认
    return '.jpg'


def calculate_file_hash(file_path: str, algorithm: str = 'md5') -> Optional[str]:
    """
    计算文件哈希
    
    Args:
        file_path: 文件路径
        algorithm: 哈希算法 (md5, sha1, sha256)
        
    Returns:
        十六进制哈希字符串
    """
    try:
        h = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        
        return h.hexdigest()
        
    except Exception as e:
        logger.error(f"计算文件哈希失败: {file_path} - {e}")
        return None


def ensure_directory(path: str) -> bool:
    """
    确保目录存在
    
    Args:
        path: 目录路径
        
    Returns:
        是否成功
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录失败: {path} - {e}")
        return False


# ==================== 其他工具 ====================

def format_bytes(num_bytes: int) -> str:
    """
    格式化字节数为可读字符串
    
    Args:
        num_bytes: 字节数
        
    Returns:
        格式化字符串 (如 "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def format_speed(bytes_per_second: float) -> str:
    """
    格式化速度为可读字符串
    
    Args:
        bytes_per_second: 每秒字节数
        
    Returns:
        格式化字符串 (如 "1.5 MB/s")
    """
    return format_bytes(int(bytes_per_second)) + "/s"


def format_time(seconds: float) -> str:
    """
    格式化秒数为可读时间字符串
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化字符串 (如 "1h 30m 45s")
    """
    if seconds < 60:
        return f"{int(seconds)}秒"
    
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    
    if minutes < 60:
        return f"{minutes}分{seconds}秒"
    
    hours = minutes // 60
    minutes = minutes % 60
    
    return f"{hours}小时{minutes}分{seconds}秒"


def parse_date_flexible(date_str: str) -> Optional[str]:
    """
    灵活解析日期字符串
    
    Args:
        date_str: 日期字符串
        
    Returns:
        标准化日期字符串 (yyyy-MM-dd HH:mm:ss) 或 None
    """
    from datetime import datetime
    
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%d',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d',
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
    
    return None
