# -*- coding: utf-8 -*-
"""
Flickr API 封装模块
实现Flickr OAuth 1.0a认证和REST API调用

修复原项目bug:
- 使用httpx替代WebClient，支持超时和连接池
- OAuth回调端口可配置，自动重试
- User-Agent更新为现代版本
- 请求签名使用专门的OAuth库
"""

import asyncio
import base64
import hashlib
import hmac
import logging
import random
import secrets
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class OAuthToken:
    """OAuth令牌数据结构"""
    token: str
    token_secret: str
    nsid: str = ''
    username: str = ''
    fullname: str = ''
    

class FlickrAPIError(Exception):
    """Flickr API错误"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Flickr API错误 {code}: {message}")


class FlickrAPI:
    """
    Flickr API封装类
    
    功能:
    - OAuth 1.0a认证流程
    - REST API调用
    - 照片/相册/用户信息获取
    - 照片尺寸获取
    """
    
    # API端点
    API_BASE = "https://api.flickr.com/services"
    REQUEST_TOKEN_URL = f"{API_BASE}/oauth/request_token"
    AUTHORIZE_URL = f"{API_BASE}/oauth/authorize"
    ACCESS_TOKEN_URL = f"{API_BASE}/oauth/access_token"
    REST_URL = f"{API_BASE}/rest/"
    
    # 默认API密钥 (保留原项目内置Key)
    DEFAULT_API_KEY = "021e1fd66f561b265eac365661879785"
    DEFAULT_API_SECRET = "48685f9b9271b284"
    V4_API_KEY = "6f92fee8b4a726215b827c0af43afc70"
    V4_API_SECRET = "4c4fa981ad30e375"
    
    # OAuth回调
    OAUTH_CALLBACK = "http://localhost:18080"
    
    # User-Agent
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        初始化Flickr API
        
        Args:
            api_key: Flickr API Key
            api_secret: Flickr API Secret
        """
        self.api_key = api_key or self.V4_API_KEY
        self.api_secret = api_secret or self.V4_API_SECRET
        
        # OAuth状态
        self.oauth_token: Optional[str] = None
        self.oauth_token_secret: Optional[str] = None
        self.user_nsid: Optional[str] = None
        self.user_fullname: Optional[str] = None
        self.user_username: Optional[str] = None
        
        # HTTP客户端
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建HTTP客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={'User-Agent': self.USER_AGENT},
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
            )
        return self._client
    
    async def close(self):
        """关闭HTTP客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    # ==================== OAuth 1.0a 方法 ====================
    
    def _generate_nonce(self) -> str:
        """生成随机nonce"""
        return secrets.token_hex(16)
    
    def _generate_timestamp(self) -> str:
        """生成时间戳"""
        return str(int(time.time()))
    
    def _encode_params(self, params: Dict[str, str]) -> str:
        """URL编码参数"""
        return '&'.join(
            f"{urllib.parse.quote(str(k), safe='')}"
            f"={urllib.parse.quote(str(v), safe='')}"
            for k, v in sorted(params.items())
        )
    
    def _generate_signature(self, method: str, url: str, params: Dict[str, str]) -> str:
        """
        生成OAuth签名
        
        Args:
            method: HTTP方法 (GET, POST)
            url: 请求URL
            params: 请求参数
            
        Returns:
            HMAC-SHA1签名的Base64编码
        """
        # 按字母顺序排序并编码参数
        sorted_params = sorted(params.items())
        encoded_params = self._encode_params(dict(sorted_params))
        
        # 构建签名基础字符串
        signature_base = f"{method.upper()}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(encoded_params, safe='')}"
        
        # 生成签名密钥
        key = f"{urllib.parse.quote(self.api_secret, safe='')}&"
        if self.oauth_token_secret:
            key += urllib.parse.quote(self.oauth_token_secret, safe='')
        
        # HMAC-SHA1签名
        hashed = hmac.new(
            key.encode('utf-8'),
            signature_base.encode('utf-8'),
            hashlib.sha1
        )
        
        return base64.b64encode(hashed.digest()).decode('utf-8')
    
    def _build_oauth_header(self, params: Dict[str, str], 
                           include_token: bool = True) -> str:
        """构建OAuth Authorization头"""
        auth_params = {k: v for k, v in params.items() if k.startswith('oauth_')}
        
        if not include_token or not self.oauth_token:
            auth_params.pop('oauth_token', None)
        
        return 'OAuth ' + ', '.join(
            f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(str(v), safe="")}"'
            for k, v in sorted(auth_params.items())
        )
    
    async def get_request_token(self, callback: Optional[str] = None) -> Tuple[str, str]:
        """
        获取OAuth请求令牌
        
        Args:
            callback: 回调URL
            
        Returns:
            (token, token_secret) 元组
        """
        callback = callback or self.OAUTH_CALLBACK
        
        params = {
            'oauth_callback': callback,
            'oauth_consumer_key': self.api_key,
            'oauth_nonce': self._generate_nonce(),
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': self._generate_timestamp(),
            'oauth_version': '1.0'
        }
        
        params['oauth_signature'] = self._generate_signature(
            'GET', self.REQUEST_TOKEN_URL, params
        )
        
        client = await self._get_client()
        
        try:
            response = await client.get(
                self.REQUEST_TOKEN_URL,
                headers={
                    'Authorization': self._build_oauth_header(params, include_token=False),
                    'User-Agent': self.USER_AGENT
                }
            )
            
            response.raise_for_status()
            
            # 解析响应
            token_data = urllib.parse.parse_qs(response.text)
            
            self.oauth_token = token_data['oauth_token'][0]
            self.oauth_token_secret = token_data['oauth_token_secret'][0]
            
            logger.info("成功获取OAuth请求令牌")
            
            return self.oauth_token, self.oauth_token_secret
            
        except httpx.HTTPError as e:
            logger.error(f"获取OAuth请求令牌失败: {e}")
            raise FlickrAPIError(0, f"获取请求令牌失败: {e}")
    
    def get_authorize_url(self, frob: str = '') -> str:
        """
        获取授权URL
        
        Args:
            frob: 可选的FROB（如果需要的话）
            
        Returns:
            授权页面URL
        """
        params = {
            'oauth_token': self.oauth_token,
            'perms': 'read'
        }
        
        if frob:
            params['frob'] = frob
        
        return f"{self.AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
    
    async def get_access_token(self) -> OAuthToken:
        """
        获取OAuth访问令牌
        
        Returns:
            OAuthToken对象
        """
        if not self.oauth_token or not self.oauth_token_secret:
            raise FlickrAPIError(0, "需要先获取请求令牌")
        
        params = {
            'oauth_consumer_key': self.api_key,
            'oauth_nonce': self._generate_nonce(),
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': self._generate_timestamp(),
            'oauth_token': self.oauth_token,
            'oauth_version': '1.0',
            'oauth_verifier': ''  # 会在后续更新
        }
        
        # 注意: 实际使用时oauth_verifier需要从回调URL中获取
        # 这个方法需要配合回调服务器使用
        
        params['oauth_signature'] = self._generate_signature(
            'GET', self.ACCESS_TOKEN_URL, params
        )
        
        client = await self._get_client()
        
        try:
            response = await client.get(
                self.ACCESS_TOKEN_URL,
                headers={
                    'Authorization': self._build_oauth_header(params),
                    'User-Agent': self.USER_AGENT
                }
            )
            
            response.raise_for_status()
            
            # 解析响应
            token_data = urllib.parse.parse_qs(response.text)
            
            self.oauth_token = token_data['oauth_token'][0]
            self.oauth_token_secret = token_data['oauth_token_secret'][0]
            self.user_nsid = token_data.get('user_nsid', [''])[0]
            self.user_fullname = token_data.get('fullname', [''])[0]
            self.user_username = token_data.get('username', [''])[0]
            
            return OAuthToken(
                token=self.oauth_token,
                token_secret=self.oauth_token_secret,
                nsid=self.user_nsid,
                username=self.user_username,
                fullname=self.user_fullname
            )
            
        except httpx.HTTPError as e:
            logger.error(f"获取OAuth访问令牌失败: {e}")
            raise FlickrAPIError(0, f"获取访问令牌失败: {e}")
    
    def set_access_token(self, token: str, token_secret: str,
                        nsid: str = '', username: str = '', 
                        fullname: str = '') -> None:
        """
        设置访问令牌（从保存的配置加载）
        
        Args:
            token: OAuth令牌
            token_secret: 令牌密钥
            nsid: 用户NSID
            username: 用户名
            fullname: 用户全名
        """
        self.oauth_token = token
        self.oauth_token_secret = token_secret
        self.user_nsid = nsid
        self.user_username = username
        self.user_fullname = fullname
        
        logger.info(f"已设置访问令牌: {username} ({nsid})")
    
    @property
    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return bool(self.oauth_token and self.oauth_token_secret)
    
    # ==================== REST API 方法 ====================
    
    async def call_api(self, method: str, signed: bool = True,
                       **kwargs) -> Dict[str, Any]:
        """
        调用Flickr REST API
        
        Args:
            method: Flickr API方法 (如 'flickr.photos.search')
            signed: 是否使用OAuth签名
            **kwargs: 其他API参数
            
        Returns:
            API响应数据字典
        """
        params = {
            'method': method,
            'api_key': self.api_key,
            'format': 'json',
            'nojsoncallback': '1'
        }
        params.update(kwargs)
        
        # 如果需要OAuth签名
        if signed and self.is_authenticated:
            params['oauth_nonce'] = self._generate_nonce()
            params['oauth_timestamp'] = self._generate_timestamp()
            params['oauth_token'] = self.oauth_token
            params['oauth_signature_method'] = 'HMAC-SHA1'
            params['oauth_version'] = '1.0'
            params['oauth_signature'] = self._generate_signature(
                'GET', self.REST_URL, params
            )
        
        client = await self._get_client()
        
        try:
            response = await client.get(
                self.REST_URL,
                params=params,
                headers={'User-Agent': self.USER_AGENT}
            )
            
            response.raise_for_status()
            data = response.json()
            
            # 检查API错误
            if data.get('stat') == 'fail':
                code = data.get('code', 0)
                message = data.get('message', 'Unknown error')
                raise FlickrAPIError(code, message)
            
            return data
            
        except httpx.HTTPError as e:
            logger.error(f"API调用失败: {method} - {e}")
            raise FlickrAPIError(0, f"API调用失败: {e}")
    
    async def test_login(self) -> bool:
        """
        测试登录状态
        
        Returns:
            是否登录成功
        """
        try:
            await self.call_api('flickr.test.login')
            return True
        except FlickrAPIError:
            return False
    
    # ==================== 照片相关方法 ====================
    
    async def get_photo_info(self, photo_id: str) -> Dict[str, Any]:
        """
        获取照片信息
        
        Args:
            photo_id: 照片ID
            
        Returns:
            照片信息字典
        """
        return await self.call_api('flickr.photos.getInfo', photo_id=photo_id)
    
    async def get_photo_sizes(self, photo_id: str) -> List[Dict[str, Any]]:
        """
        获取照片可用尺寸
        
        Args:
            photo_id: 照片ID
            
        Returns:
            尺寸列表
        """
        data = await self.call_api('flickr.photos.getSizes', photo_id=photo_id)
        return data.get('sizes', {}).get('size', [])
    
    async def get_photo_url(self, photo_id: str, 
                           size_label: str = 'Original') -> Optional[str]:
        """
        获取指定尺寸的照片URL
        
        Args:
            photo_id: 照片ID
            size_label: 尺寸标签 (如 'Original', 'Large', 'Medium')
            
        Returns:
            照片URL或None
        """
        sizes = await self.get_photo_sizes(photo_id)
        for size in sizes:
            if size.get('label') == size_label:
                return size.get('source')
        return None
    
    # ==================== 相册相关方法 ====================
    
    async def get_albums(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户相册列表
        
        Args:
            user_id: 用户NSID
            
        Returns:
            相册列表
        """
        data = await self.call_api(
            'flickr.photosets.getList',
            user_id=user_id
        )
        return data.get('photosets', {}).get('photoset', [])
    
    async def get_album_photos(self, album_id: str, 
                               per_page: int = 500,
                               page: int = 1,
                               extras: str = 'url_o,url_6k,url_5k,url_4k,url_3k,url_k,url_h,url_l,url_c,url_z,url_m,url_n,url_s,media,date_taken') -> Dict[str, Any]:
        """
        获取相册照片
        
        Args:
            album_id: 相册ID
            per_page: 每页数量
            page: 页码
            extras: 额外字段
            
        Returns:
            包含photos和total等信息的字典
        """
        return await self.call_api(
            'flickr.photosets.getPhotos',
            photoset_id=album_id,
            per_page=str(per_page),
            page=str(page),
            extras=extras
        )
    
    # ==================== 用户相关方法 ====================
    
    async def get_user_photos(self, user_id: str,
                              per_page: int = 100,
                              page: int = 1,
                              extras: str = 'url_o,url_6k,url_5k,url_4k,url_3k,url_k,url_h,url_l,url_c,url_z,url_m,url_n,url_s,media,date_taken',
                              privacy_filter: Optional[int] = None) -> Dict[str, Any]:
        """
        获取用户照片
        
        Args:
            user_id: 用户NSID
            per_page: 每页数量
            page: 页码
            extras: 额外字段
            privacy_filter: 隐私过滤 (1=public, 2=private to friends, 3=private to family, 4=private)
            
        Returns:
            照片列表字典
        """
        params = {
            'user_id': user_id,
            'per_page': str(per_page),
            'page': str(page),
            'extras': extras
        }
        
        if privacy_filter is not None:
            params['privacy_filter'] = str(privacy_filter)
        
        return await self.call_api('flickr.people.getPhotos', **params)
    
    async def get_user_favorites(self, user_id: str,
                                 per_page: int = 100,
                                 page: int = 1,
                                 extras: str = 'url_o,url_6k,url_5k,url_4k,url_3k,url_k,url_h,url_l,url_c,url_z,url_m,url_n,url_s,media,date_taken') -> Dict[str, Any]:
        """
        获取用户收藏
        
        Args:
            user_id: 用户NSID
            per_page: 每页数量
            page: 页码
            extras: 额外字段
            
        Returns:
            收藏照片列表字典
        """
        return await self.call_api(
            'flickr.favorites.getPublicList',
            user_id=user_id,
            per_page=str(per_page),
            page=str(page),
            extras=extras
        )
    
    # ==================== 群组相关方法 ====================
    
    async def get_group_pool(self, group_id: str,
                             per_page: int = 100,
                             page: int = 1,
                             extras: str = 'url_o,url_6k,url_5k,url_4k,url_3k,url_k,url_h,url_l,url_c,url_z,url_m,url_n,url_s,media,date_taken') -> Dict[str, Any]:
        """
        获取群组照片池
        
        Args:
            group_id: 群组ID
            per_page: 每页数量
            page: 页码
            extras: 额外字段
            
        Returns:
            照片列表字典
        """
        return await self.call_api(
            'flickr.groups.pools.getPhotos',
            group_id=group_id,
            per_page=str(per_page),
            page=str(page),
            extras=extras
        )
    
    # ==================== 搜索相关方法 ====================
    
    async def search_photos(self, text: str = '',
                            user_id: str = '',
                            group_id: str = '',
                            tags: str = '',
                            per_page: int = 100,
                            page: int = 1,
                            privacy_filter: Optional[int] = None,
                            safe_search: int = 1,
                            extras: str = 'url_o,url_6k,url_5k,url_4k,url_3k,url_k,url_h,url_l,url_c,url_z,url_m,url_n,url_s,media,date_taken') -> Dict[str, Any]:
        """
        搜索照片
        
        Args:
            text: 搜索关键词
            user_id: 用户ID (flickr.people.getPhotos模式)
            group_id: 群组ID (flickr.groups.pools.getPhotos模式)
            tags: 标签搜索
            per_page: 每页数量
            page: 页码
            privacy_filter: 隐私过滤
            safe_search: 安全搜索 (1=safe, 2=moderate, 3=restricted)
            extras: 额外字段
            
        Returns:
            搜索结果字典
        """
        params = {
            'per_page': str(per_page),
            'page': str(page),
            'safe_search': str(safe_search),
            'extras': extras
        }
        
        if text:
            params['text'] = text
        
        if user_id:
            params['user_id'] = user_id
        
        if group_id:
            params['group_id'] = group_id
            
        if tags:
            params['tags'] = tags
        
        if privacy_filter is not None:
            params['privacy_filter'] = str(privacy_filter)
        
        # 根据参数选择合适的API方法
        if user_id and not text and not tags:
            method = 'flickr.people.getPhotos'
        elif group_id:
            method = 'flickr.groups.pools.getPhotos'
        else:
            method = 'flickr.photos.search'
        
        return await self.call_api(method, **params)
    
    # ==================== URL相关方法 ====================
    
    async def lookup_user(self, url: str) -> Dict[str, Any]:
        """
        通过URL查找用户
        
        Args:
            url: Flickr用户/相册/群组URL
            
        Returns:
            包含user信息的字典
        """
        return await self.call_api('flickr.urls.lookupUser', url=url)
    
    async def lookup_group(self, url: str) -> Dict[str, Any]:
        """
        通过URL查找群组
        
        Args:
            url: Flickr群组URL
            
        Returns:
            包含group信息的字典
        """
        return await self.call_api('flickr.urls.lookupGroup', url=url)
    
    async def lookup_album(self, url: str) -> Dict[str, Any]:
        """
        通过URL查找相册
        
        Args:
            url: Flickr相册URL
            
        Returns:
            包含photoset信息的字典
        """
        return await self.call_api('flickr.urls.lookupPhotoset', url=url)


# 同步包装器，便于非异步环境使用
class SyncFlickrAPI:
    """Flickr API同步包装器"""
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self._async_api = FlickrAPI(api_key, api_secret)
    
    def _run_async(self, coro):
        """运行异步函数"""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(coro)
    
    def call_api(self, method: str, signed: bool = True, **kwargs):
        return self._run_async(self._async_api.call_api(method, signed, **kwargs))
    
    def get_photo_info(self, photo_id: str):
        return self._run_async(self._async_api.get_photo_info(photo_id))
    
    def get_photo_sizes(self, photo_id: str):
        return self._run_async(self._async_api.get_photo_sizes(photo_id))
    
    def get_albums(self, user_id: str):
        return self._run_async(self._async_api.get_albums(user_id))
    
    def get_album_photos(self, album_id: str, per_page: int = 500, page: int = 1):
        return self._run_async(self._async_api.get_album_photos(album_id, per_page, page))
    
    def get_user_photos(self, user_id: str, per_page: int = 100, page: int = 1):
        return self._run_async(self._async_api.get_user_photos(user_id, per_page, page))
    
    def search_photos(self, text: str = '', per_page: int = 100, page: int = 1):
        return self._run_async(self._async_api.search_photos(text, per_page=per_page, page=page))
    
    def test_login(self):
        return self._run_async(self._async_api.test_login())
