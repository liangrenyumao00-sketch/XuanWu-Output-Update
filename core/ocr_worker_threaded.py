# core/ocr_worker_threaded.py
import os
import time
import base64
import requests
import winsound
import threading
import json
import logging
import PIL
import hashlib
from datetime import datetime
from io import BytesIO
from typing import Dict, Any, Optional, Tuple, List, Union
from core.settings import hash_sensitive_data
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from PIL import ImageGrab, Image
from core.config import SCREENSHOT_DIR, LOG_DIR
from core.settings import decrypt_api_data
from core.match import match_text
from requests.exceptions import RequestException, HTTPError, ConnectionError, Timeout
from core.email_notifier import EmailNotifier, EmailNotificationThread
from core.enhanced_logger import get_enhanced_logger
from core.i18n import t

# 使用专用logger，日志将记录到debug.html
logger = logging.getLogger('ocr_worker')
# 获取增强日志器用于调试追踪
enhanced_logger = get_enhanced_logger()

API_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
TOKEN_CACHE_TIME = 3500  # 秒
CACHE_HIT_INTERVAL = 0  # 缓存命中间隔（秒），0表示不缓存
BEEP_FILE = os.path.join("assets", "7499.wav")
REQUEST_TIMEOUT = 8
MAX_RETRIES = 3  # 网络请求重试次数
RETRY_DELAY = 1  # 重试间隔秒
IMAGE_CACHE_SIZE = 50  # 图像哈希缓存大小
IMAGE_CACHE_TTL = 300  # 图像缓存生存时间（秒）

# core/ocr_worker_threaded.py
"""
OCR工作器模块

该模块提供基于百度OCR API的图像文字识别功能，支持：
- 实时屏幕区域监控和文字识别
- 关键词匹配和统计
- 多种匹配模式（精确、模糊、正则表达式）
- 图像缓存优化
- 邮件和桌面通知
- 性能监控和调试

主要类:
    OCRWorker: 核心OCR工作器，提供完整的OCR识别和关键词匹配功能

依赖:
    - requests: HTTP请求
    - PIL: 图像处理
    - PyQt6: 信号槽机制
    - core.settings: 配置管理
    - core.enhanced_logger: 增强日志

作者: XuanWu Team
版本: 2.1.7
"""

def get_baidu_error_message(error_code: int) -> str:
    """
    获取百度OCR API错误信息的中文描述
    
    将百度API返回的错误代码转换为用户友好的中文错误信息。
    
    Args:
        error_code (int): 百度API返回的错误代码
        
    Returns:
        str: 对应的中文错误描述信息
        
    Example:
        >>> get_baidu_error_message(17)
        '免费测试资源使用完毕，每天请求量超限额，建议购买次数包或申请提升限额'
    """
    error_messages = {
        1: t("未知错误_请再次请求_如果持续出现此类错误_请在控制台提交工单联系技术支持团队"),
        2: t("服务暂不可用_请再次请求_如果持续出现此类错误_请在控制台提交工单联系技术支持团队"),
        3: t("调用的API不存在_请检查请求URL后重新尝试_一般为URL中有非英文字符_如_可手动输入重试"),
        4: t("集群超限额_请再次请求_如果持续出现此类错误_请在控制台提交工单联系技术支持团队"),
        6: t("无接口调用权限_创建应用时未勾选相关文字识别接口_请登录百度云控制台_编辑应用_勾选接口后重新调用"),
        14: t("IAM鉴权失败_建议用户参照文档自查sign生成方式_或换用控制台ak_sk方式调用"),
        17: t("免费测试资源使用完毕_每天请求量超限额_建议购买次数包或申请提升限额"),
        18: t("QPS超限额_免费额度为2QPS_付费后并发限制为10QPS_可购买叠加包"),
        19: t("请求总量超限额_建议购买次数包或申请提升限额"),
        100: t("无效的access_token参数_token拉取失败_请参考Access_Token获取文档重新获取"),
        110: t("access_token无效_token有效期为30天_请定期更换或每次请求都拉取新token"),
        111: t("access_token过期_token有效期为30天_请定期更换或每次请求都拉取新token"),
        216100: t("请求中包含非法参数_请检查后重新尝试"),
        216101: t("缺少必须参数_请检查参数是否遗漏"),
        216102: t("请求了不支持的服务_请检查调用的url"),
        216103: t("请求参数过长_请检查后重新尝试"),
        216110: t("appid不存在_请核对后台应用列表中的appid"),
        216200: t("图片为空_请检查后重新尝试"),
        216201: t("图片格式错误_仅支持PNG_JPG_JPEG_BMP_请转码或更换图片"),
        216202: t("图片大小错误_请根据接口文档调整图片大小后重新上传"),
        216205: t("请求体大小错误_base64编码后需小于10M_请重新发送请求"),
        216306: t("上传文件失败_请检查请求参数"),
        216308: t("PDF文件页数参数大于实际页数"),
        216401: t("提交请求失败"),
        216402: t("获取结果失败"),
        216603: t("获取PDF文件页数失败_请检查PDF及编码"),
        216604: t("请求总量超限额_建议购买或申请更多额度"),
        216630: t("识别错误_请确保图片中包含对应卡证票据后重试"),
        216631: t("识别银行卡错误_可能为图片非银行卡正面或不完整"),
        216633: t("识别身份证错误_可能为非身份证图片或不完整"),
        216634: t("检测错误_请再次请求_如果持续出现请提交工单"),
        216600: t("企业核验服务请求失败_请再次请求或提交工单"),
        216601: t("企业核验查询成功但无结果_请再次请求或提交工单"),
        216602: t("企业核验接口超时_请再次请求或提交工单"),
        282000: t("服务器内部错误_识别超时建议切割图片重试_持续报错请提交工单"),
        282003: t("请求参数缺失"),
        282005: t("批量处理时发生错误_请根据具体错误码排查"),
        282006: t("批量任务数量超限_请减少到10个或以下"),
        282100: t("图片压缩转码错误"),
        282102: t("未检测到识别目标_可能上传了非卡证图片或图片不完整"),
        282103: t("图片目标识别错误_请确保图片包含对应卡证票据"),
        282110: t("URL参数不存在_请核对URL"),
        282111: t("URL格式非法_请检查格式是否正确"),
        282112: t("URL下载超时_检查图床状态或图片大小及防盗链"),
        282113: t("URL返回无效参数"),
        282114: t("URL长度超过1024字节或为0"),
        282134: t("增值税发票验真接口超时_建议次日重试或提交工单"),
        282808: t("请求ID不存在"),
        282809: t("返回结果请求错误_非excel或json格式"),
        282810: t("图像识别错误_请再次请求_持续出现请提交工单"),
        282160: t("行驶证核验后端资源超限_请提交工单"),
        282161: t("行驶证核验请求过于频繁_请提交工单"),
    }
    return error_messages.get(error_code, t("未知错误"))

def safe_filename(s: str) -> str:
    """
    将字符串转换为安全的文件名
    
    移除或替换文件名中的非法字符，确保生成的文件名在各种操作系统中都有效。
    
    Args:
        s (str): 原始字符串
        
    Returns:
        str: 安全的文件名字符串
        
    Raises:
        TypeError: 当输入不是字符串类型时抛出
        
    Example:
        >>> safe_filename("测试文件<>:?*.txt")
        '测试文件_______.txt'
    """
    if not isinstance(s, str):
        raise TypeError(t("输入必须是字符串"))
    return "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in s)

class OCRWorker(QObject):
    """
    OCR工作器类
    
    负责图像识别和关键词匹配的核心类。提供实时屏幕监控、文字识别、
    关键词匹配、结果统计等功能。
    
    该类基于PyQt6的QObject，使用信号槽机制与UI进行通信，支持多线程
    安全操作，并提供完整的错误处理和性能优化。
    
    Signals:
        log_signal (str): 日志信息信号
        stat_signal (dict): 统计信息信号
        status_signal (str, dict): 状态更新信号
        save_signal (str, str): 保存文件信号
        error_popup_signal (str): 错误弹窗信号
        finished_signal (): 工作完成信号
        
    Attributes:
        keywords (List[str]): 要匹配的关键词列表
        region (Tuple[int, int, int, int]): 截图区域坐标
        interval (float): 检测间隔时间（秒）
        match_mode (str): 匹配模式（exact/fuzzy/regex）
        fuzzy_threshold (float): 模糊匹配阈值
        ocr_version (str): OCR接口版本
        
    Example:
        >>> worker = OCRWorker(
        ...     keywords=["关键词1", "关键词2"],
        ...     region=(100, 100, 800, 600),
        ...     interval=1.0,
        ...     match_mode="exact"
        ... )
        >>> worker.run()
    """
    
    log_signal         = pyqtSignal(str)
    stat_signal        = pyqtSignal(dict)
    status_signal      = pyqtSignal(str, dict)
    save_signal        = pyqtSignal(str, str)
    error_popup_signal = pyqtSignal(str)
    finished_signal    = pyqtSignal()  # 线程结束信号

    def __init__(self, 
                 keywords: List[str], 
                 region: Tuple[int, int, int, int], 
                 interval: float = 0.6, 
                 match_mode: str = "exact", 
                 fuzzy_threshold: float = 0.85, 
                 ocr_version: str = "general") -> None:
        """
        初始化OCR工作器
        
        创建OCR工作器实例，配置识别参数和初始化相关组件。
        
        Args:
            keywords (List[str]): 要匹配的关键词列表，不能为空
            region (Tuple[int, int, int, int]): 截图区域，格式为(x, y, width, height)
            interval (float, optional): 检测间隔时间（秒），默认0.6秒
            match_mode (str, optional): 匹配模式，支持'exact'/'fuzzy'/'regex'，默认'exact'
            fuzzy_threshold (float, optional): 模糊匹配阈值，范围0-1，默认0.85
            ocr_version (str, optional): OCR接口版本，默认'general'
            
        Raises:
            ValueError: 当参数不符合要求时抛出
            
        Example:
            >>> worker = OCRWorker(
            ...     keywords=["登录", "注册"],
            ...     region=(0, 0, 1920, 1080),
            ...     interval=1.0,
            ...     match_mode="fuzzy",
            ...     fuzzy_threshold=0.8
            ... )
        """
        enhanced_logger.debug_function_call("OCRWorker.__init__", {
            "keywords_count": len(keywords) if keywords else 0,
            "region": region,
            "interval": interval,
            "match_mode": match_mode,
            "fuzzy_threshold": fuzzy_threshold,
            "ocr_version": ocr_version
        })
        enhanced_logger.debug_memory_snapshot("ocr_worker_init_start")
        
        super().__init__()
        
        # 参数验证
        if not keywords or not isinstance(keywords, list):
            enhanced_logger.debug_error("OCRWorker.__init__", "关键词列表不能为空且必须是列表类型", {"keywords": keywords})
            raise ValueError("关键词列表不能为空且必须是列表类型")
        if not isinstance(region, (tuple, list)) or len(region) != 4:
            enhanced_logger.debug_error("OCRWorker.__init__", "区域必须是包含4个元素的元组或列表", {"region": region})
            raise ValueError("区域必须是包含4个元素的元组或列表")
        if interval <= 0:
            enhanced_logger.debug_error("OCRWorker.__init__", "检测间隔必须大于0", {"interval": interval})
            raise ValueError("检测间隔必须大于0")
        if not 0 <= fuzzy_threshold <= 1:
            enhanced_logger.debug_error("OCRWorker.__init__", "模糊匹配阈值必须在0-1之间", {"fuzzy_threshold": fuzzy_threshold})
            raise ValueError("模糊匹配阈值必须在0-1之间")
            
        self.keywords: List[str] = keywords
        self.region: Tuple[int, int, int, int] = tuple(region)
        self.interval: float = interval
        self.match_mode: str = match_mode
        self.fuzzy_threshold: float = fuzzy_threshold
        self.ocr_version: str = ocr_version

        self._stop_event: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()

        self.stats: Dict[str, int] = {kw: 0 for kw in keywords}
        self.total_hits: int = 0
        self.last_time: Optional[float] = None
        self.cache: Dict[str, Any] = {}
        
        # 图像哈希缓存：存储 {hash: (timestamp, ocr_result)}
        self.image_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self.cache_hits: int = 0
        self.cache_misses: int = 0

        self.token: str = ""
        self.token_acquire_time: float = 0
        
        logging.debug(f"OCRWorker初始化完成 - 关键词: {len(keywords)}个, 区域: {region}, 间隔: {interval}s, 模式: {match_mode}, 版本: {ocr_version}")
        enhanced_logger.debug_memory_snapshot("ocr_worker_init_complete")
        self._api_cfg: Optional[Dict[str, str]] = None  # 缓存apikey配置，避免重复读取

        # 初始化邮件通知器
        try:
            self.email_notifier: EmailNotifier = EmailNotifier()
        except Exception as e:
            logger.warning(f"邮件通知器初始化失败: {e}")
            self.email_notifier = None
            
        # 初始化桌面通知器
        try:
            # 检查是否有QApplication实例
            from PyQt6.QtWidgets import QApplication
            if QApplication.instance() is not None:
                from core.desktop_notifier import DesktopNotifier
                self.desktop_notifier: DesktopNotifier = DesktopNotifier()
            else:
                logger.info("无QApplication实例，跳过桌面通知器初始化")
                self.desktop_notifier = None
        except Exception as e:
            logger.warning(f"桌面通知器初始化失败: {e}")
            self.desktop_notifier = None

        # 加载网络设置
        self._load_network_settings()

        # 确保目录存在
        try:
            enhanced_logger.debug_function_call("OCRWorker.__init__", "创建必要目录")
            os.makedirs(LOG_DIR, exist_ok=True)
            os.makedirs(SCREENSHOT_DIR, exist_ok=True)
            logger.debug(f"目录创建成功: LOG_DIR={LOG_DIR}, SCREENSHOT_DIR={SCREENSHOT_DIR}")
        except OSError as e:
            enhanced_logger.debug_error("OCRWorker.__init__", e, {"error_type": "OSError", "directories": [LOG_DIR, SCREENSHOT_DIR]})
            logger.error(f"创建目录失败: {e}")
            raise

    @property
    def api_ocr_url(self) -> str:
        """
        获取OCR API URL
        
        根据配置的OCR版本返回对应的百度OCR API接口地址。
        支持多种OCR接口类型，包括标准版、高精度版、网络图片识别等。
        
        Returns:
            str: 对应OCR版本的API接口URL
            
        Note:
            如果指定的OCR版本不存在，将默认返回标准版API URL
            
        Example:
            >>> worker = OCRWorker(keywords=["test"], region=(0,0,100,100), ocr_version="accurate")
            >>> worker.api_ocr_url
            'https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic'
        """
        # 百度OCR接口映射
        api_urls: Dict[str, str] = {
            "general": "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic",  # 标准版
            "accurate": "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic",  # 高精度版
            "general_enhanced": "https://aip.baidubce.com/rest/2.0/ocr/v1/general",  # 标准版含位置信息
            "accurate_enhanced": "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate",  # 高精度版含位置信息
            "webimage": "https://aip.baidubce.com/rest/2.0/ocr/v1/webimage",  # 网络图片文字识别
            "handwriting": "https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting"  # 手写文字识别
        }
        
        # 返回对应的API URL，如果不存在则默认使用标准版
        return api_urls.get(self.ocr_version, api_urls["general"])

    def _load_network_settings(self) -> None:
        """
        加载网络设置
        
        从配置文件中加载网络相关设置，包括代理配置、超时设置等。
        该方法在初始化时调用，确保网络请求使用正确的配置。
        
        Raises:
            Exception: 当配置加载失败时抛出异常
            
        Note:
            - 支持HTTP/HTTPS代理配置
            - 配置加载失败时会记录错误日志但不中断程序运行
        """
        enhanced_logger.debug_function_call("OCRWorker._load_network_settings")
        enhanced_logger.debug_performance("加载网络设置开始")
        logging.debug("开始加载网络配置")
        
        try:
            from core.settings import load_settings
            settings = load_settings()
            
            # 加载超时和重试设置
            self.request_timeout = settings.get("timeout_seconds", REQUEST_TIMEOUT)
            self.max_retries = settings.get("retry_attempts", MAX_RETRIES)
            
            logging.debug(f"网络超时设置: {self.request_timeout}秒, 重试次数: {self.max_retries}")
            
            # 加载代理设置
            self.proxies = None
            if settings.get("proxy_enabled", False):
                proxy_host = settings.get("proxy_host", "")
                proxy_port = settings.get("proxy_port", 1080)
                if proxy_host:
                    proxy_url = f"http://{proxy_host}:{proxy_port}"
                    self.proxies = {
                        'http': proxy_url,
                        'https': proxy_url
                    }
                    # 使用logging而不是_log_ui避免信号问题
                    logging.info(f"使用代理: {proxy_url}")
                    logging.debug(f"代理配置: {proxy_host}:{proxy_port}")
            
            # 使用logging而不是_log_ui避免信号问题
            logging.info(f"网络配置: 超时={self.request_timeout}秒, 重试={self.max_retries}次")
            enhanced_logger.debug_performance("网络设置加载完成", {
                "timeout": self.request_timeout,
                "retries": self.max_retries,
                "proxy_enabled": bool(self.proxies)
            })
            
        except Exception as e:
            enhanced_logger.debug_error(e, f"加载网络设置失败 | 上下文: {{\"error_type\": \"{type(e).__name__}\", \"fallback_timeout\": {REQUEST_TIMEOUT}, \"fallback_retries\": {MAX_RETRIES}}}")
            logging.warning(f"加载网络设置失败，使用默认值: {e}")
            enhanced_logger.debug_performance("网络设置加载完成（异常）")
            self.request_timeout = REQUEST_TIMEOUT
            self.max_retries = MAX_RETRIES
            self.proxies = None

    def start(self) -> None:
        """启动OCR工作器
        
        开始OCR识别和关键词匹配工作。该方法会启动主工作循环，
        定期截图并进行文字识别和关键词匹配。
        
        Note:
            - 该方法是阻塞的，会一直运行直到调用stop()方法
            - 建议在单独的线程中调用此方法
            - 工作过程中会发送各种信号通知UI更新
        """
        enhanced_logger.debug_function_call("OCRWorker.start", "启动OCR工作器")
        self._stop_event.clear()
        logger.debug(f"OCR工作器启动 - 关键词数量: {len(self.keywords)}, 区域: {self.region}, 间隔: {self.interval}秒")

    def stop(self) -> None:
        """停止OCR工作器
        
        停止OCR识别工作，清理资源并发送完成信号。
        该方法是线程安全的，可以从任何线程调用。
        
        Note:
            - 调用后工作器会在当前循环完成后停止
            - 会自动清理缓存和释放资源
            - 发送finished_signal信号通知工作完成
        """
        enhanced_logger.debug_function_call("OCRWorker.stop", "停止OCR工作器")
        self._stop_event.set()
        # 记录统计信息
        enhanced_logger.debug_system_info("OCR工作器停止", {
            "total_hits": self.total_hits,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": f"{(self.cache_hits / (self.cache_hits + self.cache_misses) * 100):.1f}%" if (self.cache_hits + self.cache_misses) > 0 else "0%"
        })
        logger.debug(f"OCR工作器已停止 - 总匹配: {self.total_hits}, 缓存命中率: {(self.cache_hits / (self.cache_hits + self.cache_misses) * 100):.1f}%" if (self.cache_hits + self.cache_misses) > 0 else "OCR工作器已停止")

    def _calculate_image_hash(self, img_data: bytes) -> str:
        """计算图像数据的哈希值
        
        使用MD5算法计算图像数据的哈希值，用于图像缓存和重复检测。
        
        Args:
            img_data (bytes): 图像的二进制数据
            
        Returns:
            str: 图像数据的MD5哈希值（十六进制字符串）
            
        Example:
            >>> worker = OCRWorker(keywords=["test"], region=(0,0,100,100))
            >>> hash_val = worker._calculate_image_hash(b'image_data')
            >>> len(hash_val)
            32
        """
        enhanced_logger.debug_function_call("OCRWorker._calculate_image_hash")
        enhanced_logger.debug_performance("计算图像哈希开始")
        logging.debug(f"计算图像数据哈希，数据大小: {len(img_data) if isinstance(img_data, bytes) else 'N/A'} bytes")
        
        if not isinstance(img_data, bytes):
            enhanced_logger.debug_error("图像数据类型错误", {"actual_type": type(img_data).__name__})
            raise TypeError(t("图像数据必须是bytes类型"))
        
        hash_value = hashlib.md5(img_data).hexdigest()
        logging.debug(f"图像哈希计算完成: {hash_value[:8]}...")
        enhanced_logger.debug_performance("计算图像哈希完成", {"hash_prefix": hash_value[:8]})
        return hash_value
    
    def _get_cached_result(self, img_hash: str) -> Optional[Dict[str, Any]]:
        """
        从缓存中获取OCR结果
        
        根据图像哈希值查找已缓存的OCR识别结果，以提高性能和减少API调用。
        会自动检查缓存是否过期，过期的缓存会被自动删除。
        
        Args:
            img_hash (str): 图像的MD5哈希值
            
        Returns:
            Optional[Dict[str, Any]]: 缓存的OCR结果字典，如果不存在或过期则返回None
            
        Note:
            - 缓存有效期由IMAGE_CACHE_TTL常量控制
            - 会自动更新缓存命中和未命中统计
            
        Example:
            >>> worker = OCRWorker(keywords=["test"], region=(0,0,100,100))
            >>> result = worker._get_cached_result("abc123def456")
            >>> result is None  # 如果缓存中没有该图像的结果
            True
        """
        enhanced_logger.debug_function_call("OCRWorker._get_cached_result")
        logging.debug(f"查找缓存结果: {img_hash[:8]}...")
        
        if not isinstance(img_hash, str):
            enhanced_logger.debug_error("图像哈希类型错误", {"actual_type": type(img_hash).__name__})
            return None
            
        current_time = time.time()
        if img_hash in self.image_cache:
            timestamp, result = self.image_cache[img_hash]
            age = current_time - timestamp
            if age < IMAGE_CACHE_TTL:
                self.cache_hits += 1
                logging.debug(f"缓存命中: {img_hash[:8]}..., 缓存年龄: {age:.1f}秒")
                enhanced_logger.debug_performance("缓存命中", {"cache_age": age, "hash_prefix": img_hash[:8]})
                return result
            else:
                # 缓存过期，删除
                del self.image_cache[img_hash]
                logging.debug(f"缓存过期删除: {img_hash[:8]}..., 年龄: {age:.1f}秒")
        
        self.cache_misses += 1
        logging.debug(f"缓存未命中: {img_hash[:8]}...")
        enhanced_logger.debug_performance("缓存未命中", {"hash_prefix": img_hash[:8]})
        return None
    
    def _cache_result(self, img_hash: str, result: Dict[str, Any]) -> None:
        """
        缓存OCR结果
        
        将OCR识别结果存储到缓存中，以便后续相同图像可以直接使用缓存结果。
        会自动管理缓存大小和清理过期条目。
        
        Args:
            img_hash (str): 图像的MD5哈希值
            result (Dict[str, Any]): OCR识别结果字典
            
        Note:
            - 缓存大小由IMAGE_CACHE_SIZE常量控制
            - 当缓存满时会删除最旧的条目
            - 会自动清理过期的缓存条目
            
        Example:
            >>> worker = OCRWorker(keywords=["test"], region=(0,0,100,100))
            >>> result = {"words_result": [{"words": "测试文字"}]}
            >>> worker._cache_result("abc123def456", result)
        """
        if not isinstance(img_hash, str) or not isinstance(result, dict):
            return
            
        current_time = time.time()
        
        # 清理过期缓存
        expired_keys: List[str] = []
        for key, (timestamp, _) in self.image_cache.items():
            if current_time - timestamp >= IMAGE_CACHE_TTL:
                expired_keys.append(key)
        for key in expired_keys:
            del self.image_cache[key]
        
        # 如果缓存已满，删除最旧的条目
        if len(self.image_cache) >= IMAGE_CACHE_SIZE:
            oldest_key = min(self.image_cache.keys(), 
                           key=lambda k: self.image_cache[k][0])
            del self.image_cache[oldest_key]
        
        # 添加新缓存
        self.image_cache[img_hash] = (current_time, result)

    def _process_ocr_result(self, ocr_result: Dict[str, Any], img_hash: str) -> None:
        """
        处理OCR结果（包括缓存结果）
        
        处理OCR识别结果，进行关键词匹配、统计更新、文件保存和通知发送。
        该方法用于处理缓存的OCR结果，避免重复的OCR API调用。
        
        Args:
            ocr_result (Dict[str, Any]): OCR识别结果字典
            img_hash (str): 图像的MD5哈希值
            
        Note:
            - 该方法会进行关键词匹配
            - 如果有匹配会更新统计信息并发送通知
            - 会发送相应的UI信号更新界面
        """
        enhanced_logger.debug_function_call("OCRWorker._process_ocr_result", {
            "img_hash": img_hash[:8],
            "has_words_result": "words_result" in ocr_result
        })
        
        ts = datetime.now().strftime("%H:%M:%S")
        
        if "words_result" in ocr_result:
            enhanced_logger.debug_info("处理缓存的OCR结果")
            lines = [r["words"] for r in ocr_result["words_result"]]
            text = "\n".join(lines)
            enhanced_logger.debug_info(f"提取文本行数: {len(lines)}")
            enhanced_logger.debug_performance("关键词匹配开始（缓存结果）")
            logging.debug(f"处理缓存OCR结果，文本长度: {len(text)}，关键词数量: {len(self.keywords)}")
            
            hits = []
            now_t = time.time()
            with self._lock:
                for kw in self.keywords:
                    for line in lines:
                        if match_text(line, kw, mode=self.match_mode, fuzzy_threshold=self.fuzzy_threshold):
                            last_line, last_ts = self.cache.get(kw, ("", 0))
                            if line != last_line or now_t - last_ts > CACHE_HIT_INTERVAL:
                                hits.append((kw, line))
                                self.cache[kw] = (line, now_t)
                                logging.debug(f"关键词匹配（缓存）: {kw} -> {line[:30]}...")
                            break

            enhanced_logger.debug_performance("关键词匹配完成（缓存结果）", {"hits_count": len(hits)})
            self._log_ui(f"[{ts}]识别完成（缓存）", full_text=text, is_keyword_hit=bool(hits),
                         keywords_hit=[h[0] for h in hits] if hits else None)

            if hits:
                enhanced_logger.debug_info(f"检测到{len(hits)}个关键词命中（缓存结果）")
                enhanced_logger.debug_performance("处理关键词命中（缓存）")
                logging.debug(f"检测到关键词命中（缓存）: {[h[0] for h in hits]}")
                kws = [k for k, _ in hits]
                with self._lock:
                    for k in kws:
                        self.stats[k] += 1
                    self.total_hits += 1
                self.last_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                enhanced_logger.debug_performance("统计信息更新完成（缓存）", {"total_hits": self.total_hits})
                self.stat_signal.emit(self.stats.copy())
                self.status_signal.emit("trend", {
                    "total_hits": self.total_hits,
                    "hits_per_keyword": self.stats,
                    "last_time": self.last_time
                })
                
                # 注意：对于缓存结果，我们不重新保存文件，因为文件可能已经存在
                # 但我们仍然发送通知
                
                # 发送邮件通知
                try:
                    enhanced_logger.debug_info("准备发送邮件通知（缓存结果）")
                    enhanced_logger.debug_performance("邮件通知开始（缓存）")
                    if self.email_notifier:
                        email_thread = EmailNotificationThread(
                            self.email_notifier,
                            kws,
                            text,
                            None,  # 缓存结果不重新保存图片
                            None   # 缓存结果不重新保存日志
                        )
                        email_thread.start()
                        logging.debug("邮件通知线程已启动（缓存结果）")
                        enhanced_logger.debug_performance("邮件通知线程启动完成（缓存）")
                        enhanced_logger.debug_info(f"邮件通知已发送（缓存），关键词: {kws}")
                    else:
                        enhanced_logger.debug_info("邮件通知器未初始化，跳过邮件发送")
                except Exception as e:
                    enhanced_logger.debug_error(e, f"邮件通知发送失败（缓存） | 上下文: {{\"keywords\": {kws}, \"error_type\": \"{type(e).__name__}\"}}")
                    self._log_ui(f"{t('❌_邮件通知发送失败')}: {e}")
                    
                # 发送桌面通知
                try:
                    enhanced_logger.debug_info("准备发送桌面通知（缓存结果）")
                    enhanced_logger.debug_performance("桌面通知开始（缓存）")
                    if self.desktop_notifier:
                        title = "OCR关键词匹配提醒（缓存）"
                        message = f"检测到关键词: {', '.join(kws)}\n识别内容: {text[:50]}{'...' if len(text) > 50 else ''}"
                        enhanced_logger.debug_info(f"桌面通知内容（缓存）: {title} - {message[:30]}...")
                        success, msg = self.desktop_notifier.show_notification(title, message)
                        if success:
                            logging.debug("桌面通知已显示（缓存）")
                            enhanced_logger.debug_performance("桌面通知显示成功（缓存）")
                            enhanced_logger.debug_info(f"桌面通知显示成功（缓存），关键词: {kws}")
                        else:
                            logging.debug(f"桌面通知显示失败（缓存）: {msg}")
                            enhanced_logger.debug_error(Exception(f"桌面通知显示失败（缓存）: {msg}"), f"桌面通知显示失败（缓存） | 上下文: {{\"keywords\": {kws}}}")
                    else:
                        enhanced_logger.debug_info("桌面通知器未初始化，跳过桌面通知")
                except Exception as e:
                    enhanced_logger.debug_error(e, f"桌面通知发送失败（缓存） | 上下文: {{\"keywords\": {kws}, \"error_type\": \"{type(e).__name__}\"}}")
                    logging.debug(f"桌面通知发送失败（缓存）: {e}")
                
                if os.path.exists(BEEP_FILE):
                    enhanced_logger.debug_info("准备播放提示音（缓存结果）")
                    enhanced_logger.debug_performance("播放提示音（缓存）")
                    winsound.PlaySound(BEEP_FILE, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    logging.debug("提示音播放完成（缓存）")
                    enhanced_logger.debug_info(f"提示音播放完成（缓存）: {BEEP_FILE}")
                else:
                    enhanced_logger.debug_info(f"提示音文件不存在: {BEEP_FILE}")
        else:
            # 处理错误的缓存结果
            err = ocr_result.get("error_code")
            if err:
                msg_cn = get_baidu_error_message(err)
                enhanced_logger.debug_error(Exception(f"缓存OCR结果包含错误: {err}"), f"缓存OCR结果错误 | 上下文: {{\"error_code\": \"{err}\", \"error_msg\": \"{msg_cn}\"}}")
                enhanced_logger.debug_info(f"缓存OCR结果失败，错误码: {err}，错误信息: {msg_cn}")
                self._log_ui(f"[{ts}]{t('OCR错误')}（缓存）({err}): {msg_cn}")
            else:
                enhanced_logger.debug_error("缓存OCR结果失败", {"error_msg": ocr_result.get('error_msg', '未知')})
                enhanced_logger.debug_info(f"缓存OCR结果失败，未知错误: {ocr_result.get('error_msg', '未知')}")
                self._log_ui(f"[{ts}]{t('OCR失败')}（缓存）:{ocr_result.get('error_msg')}")

    def _load_api_cfg(self) -> Dict[str, str]:
        """
        加载API配置
        
        从配置文件中加载百度OCR API的认证信息，包括API Key和Secret Key。
        支持配置缓存以提高性能，避免重复读取配置文件。
        
        Returns:
            Dict[str, str]: 包含API Key和Secret Key的配置字典
            
        Raises:
            ValueError: 当API配置不完整或无效时抛出
            FileNotFoundError: 当配置文件不存在时抛出
            
        Note:
            - 配置信息会被缓存以提高性能
            - 支持加密配置的自动解密
            - 配置验证失败时会记录详细错误信息
            
        Example:
            >>> worker = OCRWorker(keywords=["test"], region=(0,0,100,100))
            >>> config = worker._load_api_cfg()
            >>> "api_key" in config and "secret_key" in config
            True
        """
        enhanced_logger.debug_function_call("OCRWorker._load_api_cfg")
        
        if self._api_cfg is None:
            enhanced_logger.debug_performance("加载API配置开始")
            logging.debug(f"加载OCR版本 {self.ocr_version} 的API配置")
            
            try:
                with open("apikey.enc", "rb") as f:
                    enc_data = f.read()
                logging.debug(f"读取加密文件成功，大小: {len(enc_data)} bytes")
                
                decrypted_data = decrypt_api_data(enc_data)
                if not isinstance(decrypted_data, dict):
                    enhanced_logger.debug_error(ValueError("解密数据格式错误"), f"解密数据格式错误 | 上下文: {{\"actual_type\": \"{type(decrypted_data).__name__}\"}}")
                    raise ValueError(t("解密后的数据格式不正确"))
                
                self._api_cfg = decrypted_data.get(self.ocr_version, {})
                logging.debug(f"API配置加载成功，包含 {len(self._api_cfg)} 个配置项")
                enhanced_logger.debug_performance("API配置加载成功", {"config_count": len(self._api_cfg)})
                
            except FileNotFoundError:
                self._api_cfg = {}
                enhanced_logger.debug_error(FileNotFoundError("API配置文件未找到"), "API配置文件未找到 | 上下文: {\"filename\": \"apikey.enc\"}")
                self._log_ui(t("❌_未找到apikey_enc文件"))
                enhanced_logger.debug_performance("API配置加载失败（文件未找到）")
            except Exception as e:
                self._api_cfg = {}
                enhanced_logger.debug_error(e, f"读取API配置失败 | 上下文: {{\"error_type\": \"{type(e).__name__}\"}}")
                self._log_ui(f"{t('❌_读取apikey_enc失败')}: {e}")
                enhanced_logger.debug_performance("API配置加载失败（异常）")
        
        return self._api_cfg

    def _get_token(self) -> str:
        """获取百度API访问令牌
        
        Returns:
            访问令牌字符串，失败时返回空字符串
        """
        enhanced_logger.debug_function_call("OCRWorker._get_token", "获取百度API访问令牌")
        enhanced_logger.debug_performance("get_token_start", "开始获取token")
        
        # Token有效期判断
        if self.token and (time.time() - self.token_acquire_time) < TOKEN_CACHE_TIME:
            logging.debug("使用缓存的token")
            return self.token

        cfg = self._load_api_cfg()
        if not cfg or "API_KEY" not in cfg or "SECRET_KEY" not in cfg:
            enhanced_logger.debug_error("OCRWorker._get_token", "API配置缺失", {
                "config_exists": bool(cfg),
                "has_api_key": "API_KEY" in cfg if cfg else False,
                "has_secret_key": "SECRET_KEY" in cfg if cfg else False
            })
            self._log_ui(t("❌_API_KEY或SECRET_KEY未配置或解密失败"))
            self.status_signal.emit("status", {"api_ok": False})
            self.error_popup_signal.emit(t("API密钥配置错误_请检查apikey_enc文件"))
            return ""
        
        # 记录密钥哈希用于调试（不泄露实际密钥）
        api_key_hash = hash_sensitive_data(cfg.get("API_KEY", ""))
        logging.debug(f"使用API密钥: {api_key_hash}")

        for attempt in range(self.max_retries):
            try:
                resp = requests.get(API_TOKEN_URL, params={
                    "grant_type": "client_credentials",
                    "client_id": cfg["API_KEY"],
                    "client_secret": cfg["SECRET_KEY"]
                }, timeout=self.request_timeout, proxies=self.proxies)
                resp.raise_for_status()
                d = resp.json()
                if "error_code" in d:
                    err = d["error_code"]
                    msg = get_baidu_error_message(err)
                    self._log_ui(f"{t('❌_获取Token失败')}({err}): {msg}")
                    self.status_signal.emit("status", {"api_ok": False})
                    self.error_popup_signal.emit(f"{t('获取Token失败_错误码')}：{err}，{t('原因')}：{msg}")
                    return ""
                token = d.get("access_token", "")
                if token:
                    self.token = token
                    self.token_acquire_time = time.time()
                    token_hash = hash_sensitive_data(token)
                    logging.debug(f"Token获取成功: {token_hash}")
                    enhanced_logger.debug_performance("get_token_success", "Token获取成功", {
                        "attempt": attempt + 1,
                        "token_hash": token_hash
                    })
                    self.status_signal.emit("status", {"api_ok": True})
                    return token
                else:
                    enhanced_logger.debug_error("OCRWorker._get_token", "未获得access_token", {"attempt": attempt + 1})
                    self._log_ui(t("❌_未获得access_token"))
            except (HTTPError, ConnectionError, Timeout) as e:
                enhanced_logger.debug_error(e, f"OCRWorker._get_token网络异常 | 上下文: {{\"attempt\": {attempt + 1}, \"max_retries\": {self.max_retries}, \"error_type\": \"{type(e).__name__}\", \"error_message\": \"{str(e)}\"}}")
                self._log_ui(f"{t('❌_获取Token网络异常_尝试重试')}({attempt + 1}/{self.max_retries}): {e}")
                logging.debug(f"Token获取重试延迟 {RETRY_DELAY} 秒")
                time.sleep(RETRY_DELAY)
            except Exception as e:
                enhanced_logger.debug_error(e, f"OCRWorker._get_token未知异常 | 上下文: {{\"attempt\": {attempt + 1}, \"error_type\": \"{type(e).__name__}\", \"error_message\": \"{str(e)}\"}}")
                logging.debug(f"Token获取未知异常: {e}")
                self._log_ui(f"{t('❌_获取Token未知异常')}: {e}")
                break
        
        enhanced_logger.debug_performance("get_token_failed", "Token获取失败", {
            "max_attempts": self.max_retries
        })
        self.status_signal.emit("status", {"api_ok": False})
        return ""
        self.error_popup_signal.emit(t("获取Token失败_请检查网络或apikey配置"))
        return ""

    def run(self) -> None:
        """主运行循环，执行OCR识别任务"""
        enhanced_logger.debug_function_call("OCRWorker.run")
        enhanced_logger.debug_performance("OCR工作器开始运行")
        logging.debug(f"OCR工作器启动，版本: {self.ocr_version}，间隔: {self.interval}s")
        
        enhanced_logger.debug_info("开始获取Token")
        self.token = self._get_token()
        if not self.token:
            enhanced_logger.debug_error("无法获取token", {"ocr_version": self.ocr_version})
            self._log_ui(t("❌_无法获取token_退出"))
            enhanced_logger.debug_performance("OCR工作器退出（无token）")
            self.finished_signal.emit()
            return

        enhanced_logger.debug_memory_snapshot("ocr_worker_started")
        self._log_ui(f"{t('🟢_OCRWorker已启动')} ({t('接口')}:{self.ocr_version})")
        logging.debug(f"OCRWorker启动完成，版本: {self.ocr_version}，间隔: {self.interval}s")
        enhanced_logger.debug_info("Token获取成功，开始主循环")
        self.start()

        while not self._stop_event.is_set():
            enhanced_logger.debug_info("开始新的OCR循环")
            x, y, w, h = self.region
            if w <= 0 or h <= 0:
                logging.debug(f"区域无效，跳过: {self.region}")
                # 通过事件等待替代 sleep 提升响应速度
                if self._stop_event.wait(self.interval):
                    break
                continue

            try:
                enhanced_logger.debug_info("开始截图处理")
                enhanced_logger.debug_performance("截图开始")
                logging.debug(f"开始截图，区域: {self.region}")
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
                enhanced_logger.debug_info("截图完成，开始处理图像")
                
                if self.ocr_version == "accurate" and max(img.size) > 2048:
                    original_size = img.size
                    img = img.resize((img.width // 2, img.height // 2))
                    logging.debug(f"图像已调整大小: {original_size} -> {img.size}")
                    enhanced_logger.debug_performance("图像大小调整完成", {"original": original_size, "resized": img.size})

                # 使用with语句确保BytesIO正确关闭
                with BytesIO() as buf:
                    img.save(buf, "PNG")
                    
                    # 计算图像哈希用于缓存
                    img_data = buf.getvalue()
                    img_hash = self._calculate_image_hash(img_data)
                    logging.debug(f"截图完成，大小: {len(img_data)}字节, 哈希: {img_hash[:8]}...")
                    enhanced_logger.debug_performance("截图完成", {"size": len(img_data), "hash_prefix": img_hash[:8]})
                    
                    # 检查缓存
                    cached_result = self._get_cached_result(img_hash)
                    if cached_result:
                        enhanced_logger.debug_performance("使用缓存结果", {
                            "img_hash": img_hash[:8],
                            "cache_hits": self.cache_hits
                        })
                        logging.debug(f"使用缓存OCR结果，哈希: {img_hash[:8]}...")
                        # 处理缓存的结果
                        self._process_ocr_result(cached_result, img_hash)
                        continue
                    
                    # 在with语句内获取数据，确保buf仍然打开
                    img_data_bytes = buf.getvalue()
                    img_data = base64.b64encode(img_data_bytes).decode()
                logging.debug(f"图像编码完成，Base64长度: {len(img_data)}")
                
                # 执行OCR请求，使用指数退避重试
                enhanced_logger.debug_info("准备发送OCR请求")
                enhanced_logger.debug_performance("开始OCR请求")
                logging.debug(f"发送OCR请求，版本: {self.ocr_version}")
                resp = None
                for attempt in range(self.max_retries):
                    try:
                        resp = requests.post(
                            f"{self.api_ocr_url}?access_token={self.token}",
                            data={"image": img_data},
                            headers={"Content-Type": "application/x-www-form-urlencoded"},
                            timeout=self.request_timeout,
                            proxies=self.proxies
                        )
                        resp.raise_for_status()
                        logging.debug(f"OCR请求成功，尝试次数: {attempt + 1}")
                        enhanced_logger.debug_performance("OCR请求成功", {"attempt": attempt + 1})
                        break
                    except (HTTPError, ConnectionError, Timeout) as e:
                        # 指数退避重试策略
                        retry_delay = RETRY_DELAY * (2 ** attempt)
                        enhanced_logger.debug_error(e, f"OCR请求网络异常 | 上下文: {{\"attempt\": {attempt + 1}, \"max_retries\": {self.max_retries}, \"retry_delay\": {retry_delay}, \"error_type\": \"{type(e).__name__}\"}}")
                        self._log_ui(f"{t('❌_OCR请求网络异常_尝试重试')}({attempt + 1}/{self.max_retries})，{t('等待')} {retry_delay} {t('秒')}: {e}")
                        if self._stop_event.wait(retry_delay):
                            break
                    except Exception as e:
                        enhanced_logger.debug_error(e, f"OCR请求异常 | 上下文: {{\"attempt\": {attempt + 1}, \"error_type\": \"{type(e).__name__}\"}}")
                        self._log_ui(f"{t('❌_OCR请求异常')}: {e}")
                        break

                if resp is None:
                    enhanced_logger.debug_error("OCR请求失败", {"max_retries": self.max_retries})
                    self._log_ui(f"{t('❌_OCR请求失败_已达到最大重试次数')}({self.max_retries})，{t('跳过此次识别')}")
                    enhanced_logger.debug_performance("OCR请求失败（重试耗尽）")
                    continue

                d = resp.json()
                logging.debug(f"OCR响应解析完成，包含words_result: {'words_result' in d}")
                
                # 缓存成功的OCR结果
                if "words_result" in d:
                    self._cache_result(img_hash, d)
                    enhanced_logger.debug_performance("OCR结果已缓存", {"hash_prefix": img_hash[:8]})
                ok = "words_result" in d
                self.status_signal.emit("status", {"api_ok": ok})

                ts = datetime.now().strftime("%H:%M:%S")

                if ok:
                    enhanced_logger.debug_info("OCR识别成功，开始处理结果")
                    enhanced_logger.debug_performance("OCR请求完成")
                    lines = [r["words"] for r in d["words_result"]]
                    text = "\n".join(lines)
                    enhanced_logger.debug_info(f"提取文本行数: {len(lines)}")
                    enhanced_logger.debug_performance("关键词匹配开始")
                    logging.debug(f"OCR识别完成，文本长度: {len(text)}，关键词数量: {len(self.keywords)}")
                    hits = []
                    now_t = time.time()
                    with self._lock:
                        for kw in self.keywords:
                            for line in lines:
                                if match_text(line, kw, mode=self.match_mode, fuzzy_threshold=self.fuzzy_threshold):
                                    last_line, last_ts = self.cache.get(kw, ("", 0))
                                    if line != last_line or now_t - last_ts > CACHE_HIT_INTERVAL:
                                        hits.append((kw, line))
                                        self.cache[kw] = (line, now_t)
                                        logging.debug(f"关键词匹配: {kw} -> {line[:30]}...")
                                    break

                    enhanced_logger.debug_performance("关键词匹配完成", {"hits_count": len(hits)})
                    self._log_ui(f"[{ts}]识别完成", full_text=text, is_keyword_hit=bool(hits),
                                 keywords_hit=[h[0] for h in hits] if hits else None)

                    if hits:
                        enhanced_logger.debug_info(f"检测到{len(hits)}个关键词命中")
                        enhanced_logger.debug_performance("处理关键词命中")
                        logging.debug(f"检测到关键词命中: {[h[0] for h in hits]}")
                        kws = [k for k, _ in hits]
                        with self._lock:
                            for k in kws:
                                self.stats[k] += 1
                            self.total_hits += 1
                        self.last_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        enhanced_logger.debug_performance("统计信息更新完成", {"total_hits": self.total_hits})
                        self.stat_signal.emit(self.stats.copy())
                        self.status_signal.emit("trend", {
                            "total_hits": self.total_hits,
                            "hits_per_keyword": self.stats,
                            "last_time": self.last_time
                        })
                        enhanced_logger.debug_info("开始保存OCR结果文件")
                        enhanced_logger.debug_performance("保存文件开始")
                        base = f"{'_'.join([safe_filename(k) for k in kws])}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
                        img_path = os.path.join(SCREENSHOT_DIR, f"{base}.png")
                        log_path = os.path.join(LOG_DIR, f"{base}.txt")
                        enhanced_logger.debug_info(f"文件保存路径: 图片={img_path}, 日志={log_path}")
                        img.save(img_path)
                        with open(log_path, "w", encoding="utf-8") as f:
                            f.write(text)
                        logging.debug(f"文件已保存: {img_path}, {log_path}")
                        enhanced_logger.debug_performance("文件保存完成", {"img_path": img_path, "log_path": log_path})
                        enhanced_logger.debug_info(f"文件保存成功: {base}")
                        self.save_signal.emit(log_path, img_path)
                        
                        # 发送邮件通知
                        try:
                            enhanced_logger.debug_info("准备发送邮件通知")
                            enhanced_logger.debug_performance("邮件通知开始")
                            if self.email_notifier:
                                email_thread = EmailNotificationThread(
                                    self.email_notifier,
                                    kws,
                                    text,
                                    img_path,
                                    log_path
                                )
                                email_thread.start()
                                logging.debug("邮件通知线程已启动")
                                enhanced_logger.debug_performance("邮件通知线程启动完成")
                                enhanced_logger.debug_info(f"邮件通知已发送，关键词: {kws}")
                            else:
                                enhanced_logger.debug_info("邮件通知器未初始化，跳过邮件发送")
                        except Exception as e:
                            enhanced_logger.debug_error(e, f"邮件通知发送失败 | 上下文: {{\"keywords\": {kws}, \"error_type\": \"{type(e).__name__}\"}}")
                            self._log_ui(f"{t('❌_邮件通知发送失败')}: {e}")
                            
                        # 发送桌面通知
                        try:
                            enhanced_logger.debug_info("准备发送桌面通知")
                            enhanced_logger.debug_performance("桌面通知开始")
                            if self.desktop_notifier:
                                title = "OCR关键词匹配提醒"
                                message = f"检测到关键词: {', '.join(kws)}\n识别内容: {text[:50]}{'...' if len(text) > 50 else ''}"
                                enhanced_logger.debug_info(f"桌面通知内容: {title} - {message[:30]}...")
                                success, msg = self.desktop_notifier.show_notification(title, message)
                                if success:
                                    logging.debug("桌面通知已显示")
                                    enhanced_logger.debug_performance("桌面通知显示成功")
                                    enhanced_logger.debug_info(f"桌面通知显示成功，关键词: {kws}")
                                else:
                                    logging.debug(f"桌面通知显示失败: {msg}")
                                    enhanced_logger.debug_error(Exception(f"桌面通知显示失败: {msg}"), f"桌面通知显示失败 | 上下文: {{\"keywords\": {kws}}}")
                            else:
                                enhanced_logger.debug_info("桌面通知器未初始化，跳过桌面通知")
                        except Exception as e:
                            enhanced_logger.debug_error(e, f"桌面通知发送失败 | 上下文: {{\"keywords\": {kws}, \"error_type\": \"{type(e).__name__}\"}}")
                            logging.debug(f"桌面通知发送失败: {e}")
                        
                        if os.path.exists(BEEP_FILE):
                            enhanced_logger.debug_info("准备播放提示音")
                            enhanced_logger.debug_performance("播放提示音")
                            winsound.PlaySound(BEEP_FILE, winsound.SND_FILENAME | winsound.SND_ASYNC)
                            logging.debug("提示音播放完成")
                            enhanced_logger.debug_info(f"提示音播放完成: {BEEP_FILE}")
                        else:
                            enhanced_logger.debug_info(f"提示音文件不存在: {BEEP_FILE}")
                else:
                    err = d.get("error_code")
                    if err:
                        msg_cn = get_baidu_error_message(err)
                        enhanced_logger.debug_error(Exception(f"OCR API错误: {err}"), f"OCR API错误 | 上下文: {{\"error_code\": \"{err}\", \"error_msg\": \"{msg_cn}\"}}")
                        enhanced_logger.debug_info(f"OCR识别失败，错误码: {err}，错误信息: {msg_cn}")
                        self._log_ui(f"[{ts}]{t('OCR错误')}({err}): {msg_cn}")
                        self.error_popup_signal.emit(f"{t('OCR识别错误_错误码')}：{err}，{t('原因')}：{msg_cn}")
                    else:
                        enhanced_logger.debug_error("OCR失败", {"error_msg": d.get('error_msg', '未知')})
                        enhanced_logger.debug_info(f"OCR识别失败，未知错误: {d.get('error_msg', '未知')}")
                        self._log_ui(f"[{ts}]{t('OCR失败')}:{d.get('error_msg')}")
                        self.error_popup_signal.emit(t("OCR识别失败_接口返回未知错误_请稍后重试"))

            except RequestException as e:
                enhanced_logger.debug_error(e, f"网络异常 | 上下文: {{\"exception_type\": \"{type(e).__name__}\"}}")
                enhanced_logger.debug_info(f"OCR请求发生网络异常: {type(e).__name__}，将等待5秒后重试")
                self._log_ui(f"{t('❌_网络异常')}: {e}")
                self.error_popup_signal.emit(f"{t('网络连接异常')}: {str(e)}\n{t('请检查网络或代理设置')}")
                enhanced_logger.debug_performance("网络异常等待重试")
                # 网络异常不直接退出，而是等待一段时间后重试
                if self._stop_event.wait(5):  # 等待5秒后重试
                    break
                continue
            except json.JSONDecodeError as e:
                enhanced_logger.debug_error(e, f"JSON解析异常 | 上下文: {{\"exception_type\": \"{type(e).__name__}\"}}")
                enhanced_logger.debug_info(f"OCR响应JSON解析失败，将等待3秒后重试")
                self._log_ui(f"{t('❌_JSON解析异常')}: {e}")
                self.error_popup_signal.emit(t("API返回数据格式错误_请稍后重试"))
                enhanced_logger.debug_performance("JSON解析异常等待重试")
                # JSON解析错误可能是临时问题，等待后重试
                if self._stop_event.wait(3):  # 等待3秒后重试
                    break
                continue
            except PIL.UnidentifiedImageError as e:
                enhanced_logger.debug_error(e, f"图像处理异常 | 上下文: {{\"exception_type\": \"{type(e).__name__}\"}}")
                enhanced_logger.debug_info(f"图像处理失败，可能是截图区域或格式问题，将等待2秒后重试")
                self._log_ui(f"{t('❌_图像处理异常')}: {e}")
                self.error_popup_signal.emit(t("图像处理失败_请调整截图区域或分辨率"))
                enhanced_logger.debug_performance("图像处理异常等待重试")
                if self._stop_event.wait(2):
                    break
                continue
            except ValueError as ve:
                # 专门处理"I/O operation on closed file"错误
                if "I/O operation on closed file" in str(ve):
                    exception_id = uuid.uuid4().hex[:8]
                    enhanced_logger.debug_error(f"文件I/O操作错误 [ID:{exception_id}]", {"error": str(ve), "type": "ValueError"})
                    logging.warning(f"检测到严重错误，停止OCR捕获: 程序运行异常: ValueError: {ve}. 程序将自动尝试恢复，如果问题持续出现请重启软件")
                    self._log_ui(f"⚠️ {t('文件操作错误，尝试恢复')}: {ve}")
                    
                    # 不弹出错误窗口，只在状态栏显示
                    self.status_signal.emit("warning", {"message": f"文件操作错误，已自动恢复 [ID:{exception_id}]"})
                    
                    # 短暂暂停后继续
                    if self._stop_event.wait(2):
                        break
                    continue
                else:
                    # 其他ValueError错误按一般异常处理
                    is_critical = False
                    exception_id = id(ve)
                    exception_type = type(ve).__name__
                    exception_msg = str(ve)
            except Exception as e:
                is_critical = isinstance(e, (MemoryError, OSError))
                # 使用异常实例的唯一标识符，避免重复记录相同异常
                exception_id = id(e)
                exception_type = type(e).__name__
                exception_msg = str(e)
                
                # 记录到增强日志，包含更多上下文信息
                enhanced_logger.debug_error(e, f"程序异常 | 上下文: {{\"exception_type\": \"{exception_type}\", \"exception_id\": \"{exception_id}\", \"is_critical\": {is_critical}}}")
                enhanced_logger.debug_info(f"OCR处理发生未知异常: {exception_type}，异常ID: {exception_id}，严重程度: {'严重' if is_critical else '一般'}")
                
                # 用户界面日志，简化显示
                self._log_ui(f"{t('❌_程序异常')}: {exception_type}: {exception_msg}")
                
                # 只记录一次详细的异常堆栈
                logging.exception(f"OCR处理过程中发生未知异常 (ID: {exception_id})")
                
                # 发送错误弹窗，提供更具体的错误信息和建议
                error_message = f"{t('程序运行异常')}: {exception_type}: {exception_msg}\n"
                if is_critical:
                    error_message += t('请重启软件或联系开发者')
                else:
                    error_message += t('程序将自动尝试恢复，如果问题持续出现请重启软件')
                self.error_popup_signal.emit(error_message)
                
                # 严重错误才退出循环
                if is_critical:
                    enhanced_logger.debug_performance("严重异常，退出OCR循环")
                    enhanced_logger.debug_info(f"检测到严重异常 (ID: {exception_id})，OCR工作器将退出")
                    break
                
                # 其他异常等待后重试
                enhanced_logger.debug_performance("一般异常等待重试")
                enhanced_logger.debug_info(f"一般异常 (ID: {exception_id})，将等待3秒后重试")
                if self._stop_event.wait(3):
                    break
                continue

            enhanced_logger.debug_info(f"OCR循环完成，等待 {self.interval} 秒后继续下次循环")
            if self._stop_event.wait(self.interval):
                enhanced_logger.debug_info("收到停止信号，退出OCR循环")
                break

        enhanced_logger.debug_function_call("OCRWorker.run_end", {"total_hits": self.total_hits, "cache_hits": self.cache_hits})
        enhanced_logger.debug_performance("ocr_run_end", "OCR工作器运行结束")
        enhanced_logger.debug_system_info("OCR工作器停止时的系统状态")
        self._log_ui(t("🔴_OCRWorker已停止"))
        logging.debug(f"OCRWorker运行结束，总命中: {self.total_hits}，缓存命中: {self.cache_hits}")
        self.finished_signal.emit()

    def _log_ui(self, msg, full_text=None, is_keyword_hit=False, keywords_hit=None):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        s = f"[{now}] {msg}"
        if full_text:
            s += f"\n{t('识别内容')}：\n{full_text}"
        if is_keyword_hit and keywords_hit:
            s += f"\n{t('✅命中')}:" + ",".join(keywords_hit)
        s += "\n------------------------------------------------------------"
        self.log_signal.emit(s)

class OCRThread(QThread):
    def __init__(self, worker: OCRWorker):
        super().__init__()
        self.worker = worker

    def run(self):
        self.worker.run()

# ------------------ 单次剪贴板图片识别支持 ------------------

def run_clipboard_image_once(worker: OCRWorker) -> None:
    """
    单次处理剪贴板图片OCR。
    与 OCRWorker.run() 流程一致，但只处理剪贴板中的一张图片。
    """
    try:
        enhanced_logger.debug_function_call("run_clipboard_image_once")
        # 获取 token
        worker.token = worker._get_token()
        if not worker.token:
            worker._log_ui(t("❌_无法获取token_退出"))
            worker.finished_signal.emit()
            return

        # 获取剪贴板图片
        cb = ImageGrab.grabclipboard()
        img = None
        if isinstance(cb, Image.Image):
            img = cb
        elif isinstance(cb, list) and cb:
            try:
                img = Image.open(cb[0])
            except Exception as e:
                logger.warning(f"无法打开剪贴板文件: {cb[0]} - {e}")
        if img is None:
            worker._log_ui(t("❌_剪贴板中未发现图片"))
            worker.error_popup_signal.emit(t("剪贴板中未发现图片_请复制图片后重试"))
            worker.finished_signal.emit()
            return

        # 尺寸调整（与accurate版本逻辑保持一致）
        if worker.ocr_version == "accurate" and max(img.size) > 2048:
            img = img.resize((img.width // 2, img.height // 2))

        # 序列化图像并计算哈希
        with BytesIO() as buf:
            img.save(buf, "PNG")
            img_bytes = buf.getvalue()
        img_hash = worker._calculate_image_hash(img_bytes)

        # 缓存检查
        cached = worker._get_cached_result(img_hash)
        if cached:
            worker._process_ocr_result(cached, img_hash)
            worker.finished_signal.emit()
            return

        # 发送 OCR 请求
        img_b64 = base64.b64encode(img_bytes).decode()
        resp = None
        for attempt in range(worker.max_retries):
            try:
                resp = requests.post(
                    f"{worker.api_ocr_url}?access_token={worker.token}",
                    data={"image": img_b64},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=worker.request_timeout,
                    proxies=worker.proxies
                )
                resp.raise_for_status()
                break
            except (HTTPError, ConnectionError, Timeout) as e:
                retry_delay = RETRY_DELAY * (2 ** attempt)
                worker._log_ui(f"{t('❌_OCR请求网络异常_尝试重试')}({attempt + 1}/{worker.max_retries})，{t('等待')} {retry_delay} {t('秒')}: {e}")
                time.sleep(retry_delay)
            except Exception as e:
                worker._log_ui(f"{t('❌_OCR请求异常')}: {e}")
                resp = None
                break

        if resp is None:
            worker._log_ui(f"{t('❌_OCR请求失败_已达到最大重试次数')}({worker.max_retries})，{t('跳过此次识别')}")
            worker.finished_signal.emit()
            return

        d = resp.json()
        ok = "words_result" in d
        worker.status_signal.emit("status", {"api_ok": ok})

        ts = datetime.now().strftime("%H:%M:%S")
        if ok:
            # 缓存结果
            worker._cache_result(img_hash, d)
            lines = [r["words"] for r in d["words_result"]]
            text = "\n".join(lines)
            worker._log_ui(f"[{ts}]识别完成（剪贴板）", full_text=text)

            # 匹配关键词
            hits = []
            now_t = time.time()
            with worker._lock:
                for kw in worker.keywords:
                    for line in lines:
                        if match_text(line, kw, mode=worker.match_mode, fuzzy_threshold=worker.fuzzy_threshold):
                            last_line, last_ts = worker.cache.get(kw, ("", 0))
                            if line != last_line or now_t - last_ts > CACHE_HIT_INTERVAL:
                                hits.append((kw, line))
                                worker.cache[kw] = (line, now_t)
                            break

            if hits:
                kws = [k for k, _ in hits]
                with worker._lock:
                    for k in kws:
                        worker.stats[k] += 1
                    worker.total_hits += 1
                worker.last_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                worker.stat_signal.emit(worker.stats.copy())
                worker.status_signal.emit("trend", {
                    "total_hits": worker.total_hits,
                    "hits_per_keyword": worker.stats,
                    "last_time": worker.last_time
                })
                base = f"{'_'.join([safe_filename(k) for k in kws])}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
                img_path = os.path.join(SCREENSHOT_DIR, f"{base}.png")
                log_path = os.path.join(LOG_DIR, f"{base}.txt")
                img.save(img_path)
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                worker.save_signal.emit(log_path, img_path)

                # 邮件通知
                try:
                    if worker.email_notifier:
                        EmailNotificationThread(worker.email_notifier, kws, text, img_path, log_path).start()
                except Exception as e:
                    worker._log_ui(f"{t('❌_邮件通知发送失败')}: {e}")

                # 桌面通知
                try:
                    if worker.desktop_notifier:
                        title = t('OCR关键词匹配提醒')
                        message = f"{t('检测到关键词')}: {', '.join(kws)}\n{t('识别内容')}: {text[:50]}{'...' if len(text) > 50 else ''}"
                        worker.desktop_notifier.show_notification(title, message)
                except Exception:
                    pass

                if os.path.exists(BEEP_FILE):
                    winsound.PlaySound(BEEP_FILE, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            err = d.get('error_code')
            if err:
                msg_cn = get_baidu_error_message(err)
                worker._log_ui(f"[{ts}]{t('OCR错误')}({err}): {msg_cn}")
                worker.error_popup_signal.emit(f"{t('OCR失败')}: {msg_cn}")
            else:
                worker._log_ui(f"[{ts}]{t('OCR失败')}: {d.get('error_msg', '未知错误')}")
                worker.error_popup_signal.emit(t('OCR识别失败_接口返回未知错误_请稍后重试'))
    except Exception as e:
        logging.exception("剪贴板OCR异常")
        worker._log_ui(f"{t('❌_程序异常')}: {type(e).__name__}: {e}")
        worker.error_popup_signal.emit(f"{t('程序运行异常')}: {type(e).__name__}: {e}")
    finally:
        worker.finished_signal.emit()

class SingleImageOCRThread(QThread):
    """单次剪贴板图片OCR线程"""
    def __init__(self, worker: OCRWorker):
        super().__init__()
        self.worker = worker

    def run(self):
        run_clipboard_image_once(self.worker)
