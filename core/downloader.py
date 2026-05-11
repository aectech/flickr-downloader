# -*- coding: utf-8 -*-
"""
下载管理器模块
负责多线程下载、队列管理、暂停/恢复等核心功能

修复原项目bug:
- 使用asyncio+ThreadPoolExecutor替代WinForms线程模型
- 动态线程数组，可配置1-10线程
- 下载队列用asyncio.Queue替代忙等待
- 断点续传使用JSON结构化存储
"""

import asyncio
import hashlib
import logging
import os
import json
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import threading

import httpx

logger = logging.getLogger(__name__)


class DownloadStatus(Enum):
    """下载状态枚举"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DownloadTask:
    """下载任务数据结构"""
    id: str
    photo_id: str
    title: str
    url: str
    album_name: str = ''
    user_id: str = ''
    date_taken: str = ''
    media_type: str = 'photo'  # photo or video
    status: str = 'pending'
    retry_count: int = 0
    file_path: str = ''
    file_size: int = 0
    downloaded_size: int = 0
    speed: float = 0.0
    error_message: str = ''
    index: int = 0  # 下载序号
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DownloadTask':
        return cls(**data)


@dataclass
class DownloadProgress:
    """下载进度数据结构"""
    total: int
    completed: int
    failed: int
    skipped: int
    paused: int
    pending: int
    current_speed: float
    eta_seconds: Optional[float]


class DownloadManager:
    """
    下载管理器
    
    功能:
    - 多线程下载 (可配置1-10线程)
    - 异步队列管理
    - 暂停/继续功能
    - 断点续传
    - 下载进度回调
    """
    
    # 尺寸优先级 (从高到低)
    SIZE_PRIORITY = [
        'url_o', 'url_6k', 'url_5k', 'url_4k', 'url_3k', 
        'url_k', 'url_h', 'url_l', 'url_c', 'url_z', 
        'url_m', 'url_n', 'url_s'
    ]
    
    # 尺寸标签映射
    SIZE_LABELS = {
        'url_o': 'Original',
        'url_6k': '6K',
        'url_5k': '5K', 
        'url_4k': '4K',
        'url_3k': '3K',
        'url_k': 'Large 800',
        'url_h': 'Large 600',
        'url_l': 'Large',
        'url_c': 'Medium 800',
        'url_z': 'Medium 640',
        'url_m': 'Medium',
        'url_n': 'Small 320',
        'url_s': 'Small'
    }
    
    # User-Agent
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def __init__(self, 
                 thread_count: int = 4,
                 save_dir: str = '',
                 skip_existing: bool = False,
                 auto_make_dirs: bool = True,
                 on_progress: Optional[Callable] = None,
                 on_complete: Optional[Callable] = None,
                 on_error: Optional[Callable] = None):
        """
        初始化下载管理器
        
        Args:
            thread_count: 下载线程数 (1-10)
            save_dir: 保存目录
            skip_existing: 跳过已存在的文件
            auto_make_dirs: 自动创建子文件夹
            on_progress: 进度回调函数
            on_complete: 完成回调函数
            on_error: 错误回调函数
        """
        self.thread_count = max(1, min(10, thread_count))
        self.save_dir = Path(save_dir) if save_dir else Path.home()
        self.skip_existing = skip_existing
        self.auto_make_dirs = auto_make_dirs
        
        # 回调函数
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.on_error = on_error
        
        # 下载状态
        self._tasks: List[DownloadTask] = []
        self._task_index = 0
        self._is_running = False
        self._is_paused = False
        self._should_stop = False
        
        # 线程锁
        self._lock = threading.Lock()
        
        # HTTP客户端
        self._client: Optional[httpx.AsyncClient] = None
        
        # 速度计算
        self._last_byte_times: Dict[str, float] = {}
        self._current_speeds: Dict[str, float] = {}
        
        # 断点续传文件
        self._progress_file: Optional[Path] = None
        
        # 失败列表
        self._fail_list: List[Dict] = []
        
        logger.info(f"下载管理器初始化完成: {self.thread_count} 线程")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建HTTP客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=15.0),
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
    
    def add_task(self, url: str, title: str, 
                 photo_id: str = '',
                 album_name: str = '',
                 user_id: str = '',
                 date_taken: str = '',
                 media_type: str = 'photo') -> str:
        """
        添加下载任务
        
        Args:
            url: 下载URL
            title: 文件标题
            photo_id: 照片ID
            album_name: 相册名称
            user_id: 用户ID
            date_taken: 拍摄日期
            media_type: 媒体类型 (photo/video)
            
        Returns:
            任务ID
        """
        with self._lock:
            task_id = f"task_{self._task_index}_{int(time.time() * 1000)}"
            self._task_index += 1
            
            task = DownloadTask(
                id=task_id,
                photo_id=photo_id or url.split('/')[-2] if url else '',
                title=title,
                url=url,
                album_name=album_name,
                user_id=user_id,
                date_taken=date_taken,
                media_type=media_type,
                index=len(self._tasks)
            )
            
            self._tasks.append(task)
            logger.debug(f"添加任务: {task_id} - {title}")
            
            return task_id
    
    def add_tasks_batch(self, tasks: List[Dict]) -> int:
        """
        批量添加任务
        
        Args:
            tasks: 任务列表，每项包含url和title等
            
        Returns:
            添加的任务数量
        """
        count = 0
        for task_data in tasks:
            self.add_task(**task_data)
            count += 1
        return count
    
    def set_progress_file(self, file_path: str):
        """设置断点续传文件路径"""
        self._progress_file = Path(file_path)
    
    def save_progress(self) -> bool:
        """
        保存下载进度
        
        Returns:
            是否保存成功
        """
        if not self._progress_file:
            return False
        
        try:
            progress_data = {
                'tasks': [t.to_dict() for t in self._tasks],
                'timestamp': time.time()
            }
            
            # 使用临时文件确保原子性
            temp_file = self._progress_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
            
            temp_file.replace(self._progress_file)
            
            logger.debug("进度已保存")
            return True
            
        except Exception as e:
            logger.error(f"保存进度失败: {e}")
            return False
    
    def load_progress(self) -> bool:
        """
        加载下载进度
        
        Returns:
            是否加载成功
        """
        if not self._progress_file or not self._progress_file.exists():
            return False
        
        try:
            with open(self._progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
            
            # 恢复任务列表
            self._tasks = [DownloadTask.from_dict(t) for t in progress_data.get('tasks', [])]
            
            logger.info(f"已加载 {len(self._tasks)} 个任务")
            return True
            
        except Exception as e:
            logger.error(f"加载进度失败: {e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """获取任务"""
        for task in self._tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_pending_tasks(self) -> List[DownloadTask]:
        """获取待下载任务"""
        return [t for t in self._tasks if t.status == 'pending']
    
    def get_progress(self) -> DownloadProgress:
        """获取下载进度"""
        total = len(self._tasks)
        completed = sum(1 for t in self._tasks if t.status == 'completed')
        failed = sum(1 for t in self._tasks if t.status == 'failed')
        skipped = sum(1 for t in self._tasks if t.status == 'skipped')
        paused = sum(1 for t in self._tasks if t.status == 'paused')
        pending = sum(1 for t in self._tasks if t.status == 'pending')
        
        # 计算总速度
        total_speed = sum(self._current_speeds.values())
        
        # 估算剩余时间
        remaining = pending + paused
        eta = None
        if total_speed > 0 and remaining > 0:
            avg_size = sum(t.file_size for t in self._tasks if t.file_size > 0) / max(1, sum(1 for t in self._tasks if t.file_size > 0))
            eta = (remaining * avg_size) / total_speed
        
        return DownloadProgress(
            total=total,
            completed=completed,
            failed=failed,
            skipped=skipped,
            paused=paused,
            pending=pending,
            current_speed=total_speed,
            eta_seconds=eta
        )
    
    async def _download_single(self, task: DownloadTask) -> bool:
        """
        下载单个文件
        
        Args:
            task: 下载任务
            
        Returns:
            是否下载成功
        """
        try:
            client = await self._get_client()
            
            # 确定保存路径
            if self.auto_make_dirs and task.album_name:
                save_path = self.save_dir / self._sanitize_filename(task.album_name)
                save_path.mkdir(parents=True, exist_ok=True)
            else:
                save_path = self.save_dir
                save_path.mkdir(parents=True, exist_ok=True)
            
            file_name = self._sanitize_filename(task.title)
            file_path = save_path / f"{file_name}.tmp"
            final_path = save_path / f"{file_name}.jpg"
            
            # 检查是否跳过
            if self.skip_existing and final_path.exists():
                task.status = 'skipped'
                logger.info(f"跳过已存在: {final_path}")
                return True
            
            # 更新任务状态
            task.status = 'downloading'
            
            # 下载文件
            async with client.stream('GET', task.url) as response:
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                task.file_size = total_size
                
                # 获取文件扩展名
                content_type = response.headers.get('content-type', '')
                if 'video' in content_type or task.media_type == 'video':
                    ext = '.mp4'
                elif 'png' in content_type:
                    ext = '.png'
                else:
                    ext = '.jpg'
                
                final_path = save_path / f"{file_name}{ext}"
                
                # 检查Content-Disposition
                content_disp = response.headers.get('content-disposition', '')
                if 'filename=' in content_disp:
                    match = re.search(r'filename=["\']?([^"\';\s]+)', content_disp)
                    if match:
                        final_path = save_path / match.group(1)
                
                # 下载并写入文件
                downloaded = 0
                start_time = time.time()
                last_update = start_time
                
                with open(file_path, 'wb') as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        # 检查是否暂停
                        while self._is_paused:
                            await asyncio.sleep(0.1)
                            if self._should_stop:
                                raise asyncio.CancelledError("下载已停止")
                        
                        if self._should_stop:
                            raise asyncio.CancelledError("下载已停止")
                        
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # 更新进度
                        task.downloaded_size = downloaded
                        
                        # 计算速度
                        current_time = time.time()
                        elapsed = current_time - last_update
                        if elapsed >= 0.5:  # 每0.5秒更新一次速度
                            speed = (downloaded - task.downloaded_size) / elapsed if elapsed > 0 else 0
                            task.speed = speed
                            self._current_speeds[task.id] = speed
                            last_update = current_time
                            
                            # 回调进度
                            if self.on_progress:
                                self.on_progress(task)
                
                # 重命名临时文件
                file_path.rename(final_path)
                task.file_path = str(final_path)
                task.status = 'completed'
                
                logger.info(f"下载完成: {task.title}")
                
                if self.on_complete:
                    self.on_complete(task)
                
                return True
                
        except asyncio.CancelledError:
            task.status = 'paused'
            raise
        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            task.retry_count += 1
            
            logger.error(f"下载失败: {task.title} - {e}")
            
            # 添加到失败列表
            self._fail_list.append({
                'title': task.title,
                'url': task.url,
                'error': str(e)
            })
            
            if self.on_error:
                self.on_error(task, e)
            
            return False
    
    async def _download_worker(self, worker_id: int, task_queue: asyncio.Queue):
        """下载工作线程"""
        logger.debug(f"Worker {worker_id} 启动")
        
        while not self._should_stop:
            try:
                # 从队列获取任务
                try:
                    task = await asyncio.wait_for(task_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                if task is None:  # 结束信号
                    break
                
                # 执行下载
                await self._download_single(task)
                
                task_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} 错误: {e}")
        
        logger.debug(f"Worker {worker_id} 结束")
    
    async def start(self) -> bool:
        """
        开始下载
        
        Returns:
            是否成功开始
        """
        if self._is_running:
            logger.warning("下载已在运行中")
            return False
        
        if not self._tasks:
            logger.warning("没有下载任务")
            return False
        
        self._is_running = True
        self._is_paused = False
        self._should_stop = False
        
        logger.info(f"开始下载: {len(self._tasks)} 个任务, {self.thread_count} 线程")
        
        # 创建任务队列
        task_queue = asyncio.Queue()
        
        # 添加待下载任务到队列
        pending_tasks = self.get_pending_tasks()
        for task in pending_tasks:
            await task_queue.put(task)
        
        # 启动工作线程
        workers = [
            asyncio.create_task(self._download_worker(i, task_queue))
            for i in range(self.thread_count)
        ]
        
        # 等待所有任务完成
        try:
            await task_queue.join()
        except asyncio.CancelledError:
            pass
        
        # 发送结束信号
        for _ in range(self.thread_count):
            await task_queue.put(None)
        
        # 等待所有worker结束
        await asyncio.gather(*workers, return_exceptions=True)
        
        self._is_running = False
        
        # 保存进度
        self.save_progress()
        
        logger.info("下载完成")
        
        return True
    
    def pause(self):
        """暂停下载"""
        if not self._is_running:
            return
        
        self._is_paused = True
        logger.info("下载已暂停")
    
    def resume(self):
        """继续下载"""
        if not self._is_running:
            return
        
        self._is_paused = False
        logger.info("下载已继续")
    
    def stop(self):
        """停止下载"""
        self._should_stop = True
        self._is_paused = False
        logger.info("下载已停止")
        
        # 保存进度
        self.save_progress()
    
    def clear_tasks(self):
        """清空任务列表"""
        with self._lock:
            self._tasks.clear()
            self._task_index = 0
            self._fail_list.clear()
    
    def get_failed_list(self) -> List[Dict]:
        """获取失败列表"""
        return self._fail_list.copy()
    
    def retry_failed(self) -> int:
        """
        重试失败的任务
        
        Returns:
            重试的任务数量
        """
        count = 0
        for task in self._tasks:
            if task.status == 'failed' and task.retry_count < 3:
                task.status = 'pending'
                task.retry_count += 1
                count += 1
        
        logger.info(f"已重试 {count} 个失败任务")
        return count
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        # 移除Windows非法字符
        illegal_chars = r'<>:"/\|?*'
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        
        # 移除控制字符
        filename = ''.join(c for c in filename if ord(c) >= 32)
        
        # 限制长度
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename.strip()
    
    def select_best_url(self, photo_data: Dict) -> Optional[str]:
        """
        从照片数据中选择最佳URL
        
        Args:
            photo_data: 照片信息字典
            
        Returns:
            最佳下载URL
        """
        # 按优先级查找URL
        for size_key in self.SIZE_PRIORITY:
            if size_key in photo_data and photo_data[size_key]:
                return photo_data[size_key]
        
        return None
    
    @staticmethod
    def get_size_priority_index(size_label: str) -> int:
        """
        获取尺寸优先级索引
        
        Args:
            size_label: 尺寸标签
            
        Returns:
            优先级索引 (越小越高)
        """
        try:
            return DownloadManager.SIZE_PRIORITY.index(size_label)
        except ValueError:
            return len(DownloadManager.SIZE_PRIORITY)


class SyncDownloadManager:
    """下载管理器同步包装器"""
    
    def __init__(self, **kwargs):
        self._async_manager = DownloadManager(**kwargs)
        self._loop = None
    
    def _ensure_loop(self):
        """确保事件循环存在"""
        if self._loop is None:
            import asyncio
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
    
    def add_task(self, **kwargs):
        return self._async_manager.add_task(**kwargs)
    
    def add_tasks_batch(self, tasks):
        return self._async_manager.add_tasks_batch(tasks)
    
    def start(self):
        self._ensure_loop()
        return self._loop.run_until_complete(self._async_manager.start())
    
    def pause(self):
        self._async_manager.pause()
    
    def resume(self):
        self._async_manager.resume()
    
    def stop(self):
        self._async_manager.stop()
    
    def get_progress(self):
        return self._async_manager.get_progress()
    
    def get_failed_list(self):
        return self._async_manager.get_fail_list()
