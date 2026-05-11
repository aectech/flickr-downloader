# -*- coding: utf-8 -*-
"""
URL解析模块
负责Flickr各种URL格式的解析和识别

修复原项目bug:
- Base58解码功能完善
- 支持flic.kr短链接
- URL格式识别更加健壮
"""

import re
import logging
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse, parse_qs, unquote

logger = logging.getLogger(__name__)


class URLResolver:
    """
    Flickr URL解析器
    
    支持解析的URL格式:
    - 相册URL: https://www.flickr.com/photos/user/sets/album_id
    - 照片URL: https://www.flickr.com/photos/user/photo_id
    - 个人页面: https://www.flickr.com/photos/user
    - 群组页面: https://www.flickr.com/groups/group_id
    - 收藏页面: https://www.flickr.com/photos/user/favorites
    - flic.kr短链接: https://flic.kr/p/photo_id (Base58编码)
    - API格式URL
    """
    
    # Base58字符集 ( Flickr使用 )
    BASE58_CHARS = '123456789aBCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    
    # URL模式正则表达式
    PATTERNS = {
        # 照片URL: https://www.flickr.com/photos/user/12345678
        'photo': re.compile(
            r'^https?://(?:www\.)?flickr\.com/photos/([^/]+)/(\d+)(?:/.*)?$'
        ),
        
        # 相册URL: https://www.flickr.com/photos/user/sets/album_id
        'album': re.compile(
            r'^https?://(?:www\.)?flickr\.com/photos/([^/]+)/sets/(\d+)(?:/.*)?$'
        ),
        
        # 用户主页: https://www.flickr.com/photos/user
        'user': re.compile(
            r'^https?://(?:www\.)?flickr\.com/photos/([^/]+)/?$'
        ),
        
        # 群组页面: https://www.flickr.com/groups/group_id
        'group': re.compile(
            r'^https?://(?:www\.)?flickr\.com/groups/([^/]+)/?(?:/.*)?$'
        ),
        
        # 收藏页面: https://www.flickr.com/photos/user/favorites
        'favorites': re.compile(
            r'^https?://(?:www\.)?flickr\.com/photos/([^/]+)/favorites/?$'
        ),
        
        # flic.kr短链接: https://flic.kr/p/photo_id
        'short': re.compile(
            r'^https?://flic\.kr/p/([1-9A-HJ-NP-Za-km-z]+)$'
        ),
        
        # Gallery URL
        'gallery': re.compile(
            r'^https?://(?:www\.)?flickr\.com/photos/([^/]+)/galleries/(\d+)(?:/.*)?$'
        ),
        
        # Tags页面
        'tags': re.compile(
            r'^https?://(?:www\.)?flickr\.com/photos/tags/([^/]+)/?(?:/.*)?$'
        ),
    }
    
    def __init__(self):
        """初始化URL解析器"""
        self._base58_map = {c: i for i, c in enumerate(self.BASE58_CHARS)}
    
    def parse_url(self, url: str) -> Dict[str, Any]:
        """
        解析Flickr URL并返回类型和参数
        
        Args:
            url: Flickr URL
            
        Returns:
            包含 'type', 'id', 'user_id', 'nsid' 等字段的字典
        """
        url = url.strip()
        
        # 尝试解析各类型URL
        for url_type, pattern in self.PATTERNS.items():
            match = pattern.match(url)
            if match:
                result = self._parse_match(url_type, match)
                if result:
                    logger.debug(f"解析URL成功: {url} -> {result}")
                    return result
        
        # 尝试解析为纯ID
        id_result = self._parse_as_id(url)
        if id_result:
            return id_result
        
        logger.warning(f"无法解析URL: {url}")
        return {'type': 'unknown', 'raw_url': url}
    
    def _parse_match(self, url_type: str, match: re.Match) -> Optional[Dict[str, Any]]:
        """根据正则匹配结果解析URL"""
        groups = match.groups()
        
        result = {
            'type': url_type,
            'raw_url': match.string
        }
        
        if url_type == 'photo':
            result['user_id'] = groups[0]
            result['photo_id'] = groups[1]
            
        elif url_type == 'album':
            result['user_id'] = groups[0]
            result['album_id'] = groups[1]
            
        elif url_type == 'user':
            result['user_id'] = groups[0]
            
        elif url_type == 'group':
            result['group_id'] = groups[0]
            
        elif url_type == 'favorites':
            result['user_id'] = groups[0]
            
        elif url_type == 'short':
            # flic.kr短链接需要Base58解码
            photo_id = self.base58_decode(groups[0])
            if photo_id:
                result['type'] = 'photo'
                result['photo_id'] = photo_id
                
        elif url_type == 'gallery':
            result['user_id'] = groups[0]
            result['gallery_id'] = groups[1]
            
        elif url_type == 'tags':
            result['tag'] = groups[0]
            
        return result
    
    def _parse_as_id(self, url: str) -> Optional[Dict[str, Any]]:
        """尝试将输入解析为纯ID"""
        # 去除空白
        url = url.strip()
        
        # 如果是纯数字，可能是photo_id或album_id
        if url.isdigit():
            return {
                'type': 'unknown_id',
                'id': url,
                'raw_url': url
            }
        
        # 如果是Base58编码的短ID (flic.kr)
        if self._is_base58_string(url):
            photo_id = self.base58_decode(url)
            if photo_id:
                return {
                    'type': 'photo',
                    'photo_id': photo_id,
                    'raw_url': url
                }
        
        return None
    
    def _is_base58_string(self, s: str) -> bool:
        """检查字符串是否为有效的Base58"""
        return all(c in self.BASE58_CHARS for c in s)
    
    def base58_decode(self, encoded: str) -> Optional[str]:
        """
        Base58解码
        
        Flickr使用Base58编码photo_id生成flic.kr短链接
        
        Args:
            encoded: Base58编码的字符串
            
        Returns:
            解码后的数字字符串，失败返回None
        """
        if not encoded:
            return None
        
        try:
            num = 0
            for char in encoded:
                if char not in self._base58_map:
                    return None
                num = num * 58 + self._base58_map[char]
            return str(num)
        except Exception as e:
            logger.error(f"Base58解码失败: {encoded} - {e}")
            return None
    
    def base58_encode(self, num: int) -> str:
        """
        Base58编码
        
        Args:
            num: 要编码的数字
            
        Returns:
            Base58编码字符串
        """
        if num <= 0:
            return '0'
        
        result = []
        while num > 0:
            num, remainder = divmod(num, 58)
            result.append(self.BASE58_CHARS[remainder])
        
        return ''.join(reversed(result))
    
    def resolve_user_nsid(self, identifier: str) -> str:
        """
        解析用户标识符为NSID
        
        Args:
            identifier: 用户名、邮箱或NSID
            
        Returns:
            用户的NSID
        """
        # 如果看起来已经是NSID格式
        if re.match(r'^\d+@N\d+$', identifier):
            return identifier
        
        # TODO: 通过API解析
        # 需要调用 flickr.urls.lookupUser
        return identifier
    
    def extract_photo_id_from_url(self, url: str) -> Optional[str]:
        """
        从URL中提取照片ID
        
        Args:
            url: Flickr URL
            
        Returns:
            照片ID或None
        """
        parsed = self.parse_url(url)
        
        if parsed['type'] == 'photo':
            return parsed.get('photo_id')
        
        # 尝试flic.kr格式
        match = self.PATTERNS['short'].match(url)
        if match:
            return self.base58_decode(match.group(1))
        
        return None
    
    def extract_album_id_from_url(self, url: str) -> Optional[str]:
        """
        从URL中提取相册ID
        
        Args:
            url: Flickr URL
            
        Returns:
            相册ID或None
        """
        parsed = self.parse_url(url)
        
        if parsed['type'] == 'album':
            return parsed.get('album_id')
        
        return None
    
    def build_photo_url(self, user_id: str, photo_id: str, 
                       size: str = '') -> str:
        """
        构建照片URL
        
        Args:
            user_id: 用户ID
            photo_id: 照片ID
            size: 尺寸后缀 (如 '_m', '_b', '_o')
            
        Returns:
            照片URL
        """
        url = f"https://www.flickr.com/photos/{user_id}/{photo_id}"
        if size:
            url += f"/{size}"
        return url
    
    def build_album_url(self, user_id: str, album_id: str) -> str:
        """
        构建相册URL
        
        Args:
            user_id: 用户ID
            album_id: 相册ID
            
        Returns:
            相册URL
        """
        return f"https://www.flickr.com/photos/{user_id}/sets/{album_id}"
    
    def get_static_url(self, farm: int, server: str, photo_id: str, 
                       secret: str, size: str = '') -> str:
        """
        构建静态Flickr URL
        
        Args:
            farm: Farm ID
            server: Server ID
            photo_id: 照片ID
            secret: 照片密钥
            size: 尺寸后缀
            
        Returns:
            静态图片URL
        """
        base = f"https://live.staticflickr.com/{server}/{photo_id}_{secret}"
        if size:
            base += f"_{size}"
        return base + ".jpg"
    
    def parse_video_url(self, url: str) -> Dict[str, Any]:
        """
        解析视频URL并返回类型
        
        Args:
            url: 视频URL
            
        Returns:
            包含 'type' (orig/hd/site/mobile), 'photo_id' 等字段
        """
        result = {'type': 'unknown', 'url': url}
        
        if '/play/orig/' in url:
            result['type'] = 'orig'
        elif '/play/hd/' in url:
            result['type'] = 'hd'
        elif '/play/site/' in url:
            result['type'] = 'site'
        elif '/play/mobile/' in url:
            result['type'] = 'mobile'
        elif '/video_download.gne' in url:
            result['type'] = 'download'
        
        # 提取photo_id
        match = re.search(r'/(\d+)(?:/play|/video_download)', url)
        if match:
            result['photo_id'] = match.group(1)
        
        return result
    
    def get_video_url_from_image(self, image_url: str, user_id: str) -> str:
        """
        从图片URL推导视频URL
        
        根据原项目逻辑:
        - url_o -> orig
        - url_k/h/l/b/z -> hd
        - url_b/z -> site
        - 其他 -> mobile
        
        Args:
            image_url: 图片URL
            user_id: 用户ID
            
        Returns:
            视频URL
        """
        # 提取photo_id和secret
        match = re.search(
            r'live\.staticflickr\.com/\d+/(\d+)_([0-9a-z]+)(?:_[omsknhzlbc])?',
            image_url
        )
        
        if not match:
            return image_url
        
        photo_id = match.group(1)
        secret = match.group(2)
        
        # 提取图片尺寸后缀
        size_match = re.search(r'_\d+\.jpg$|_\d+_\d+\.jpg$', image_url)
        size_suffix = ''
        if size_match:
            size_suffix = image_url[size_match.start()+1:size_match.end()-4]
        
        # 根据尺寸选择视频URL
        if size_suffix == 'o':
            return f"https://www.flickr.com/photos/{user_id}/{photo_id}/play/orig/{secret}/"
        elif size_suffix in ('k', 'h', 'l', 'b', 'z'):
            return f"https://www.flickr.com/photos/{user_id}/{photo_id}/play/hd/{secret}/"
        elif size_suffix in ('b', 'z'):
            return f"https://www.flickr.com/photos/{user_id}/{photo_id}/play/site/{secret}/"
        else:
            return f"https://www.flickr.com/photos/{user_id}/{photo_id}/play/mobile/{secret}/"
    
    def sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        # Windows非法字符
        illegal_chars = r'<>:"/\|?*'
        
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        
        # 移除控制字符
        filename = ''.join(c for c in filename if ord(c) >= 32)
        
        # 限制长度
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename.strip()
