import os
import json
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
import requests
import zipfile
import tempfile
from core.enhanced_logger import enhanced_logger
from core.settings import load_settings, save_settings, USE_UNIFIED_CONFIG, UNIFIED_CONFIG_FILE, SETTINGS_FILE

# 使用专用logger，日志将记录到xuanwu_log.html
logger = logging.getLogger('cloud_sync')

class CloudSyncManager(QObject):
    """云同步管理器"""
    
    # 信号定义
    sync_progress = pyqtSignal(int, str)  # 进度值, 状态消息
    sync_completed = pyqtSignal(bool, str, dict)  # 成功标志, 消息, 同步统计
    conflict_detected = pyqtSignal(str, dict, dict)  # 冲突文件, 本地数据, 云端数据
    
    def __init__(self):
        super().__init__()
        enhanced_logger.debug_function_call("CloudSyncManager.__init__")
        enhanced_logger.debug_memory_snapshot("CloudSyncManager初始化前")
        
        # 配置来源改为 settings.json / unified_config.json 的 settings.cloud_sync
        self.config_source = f"{'unified_config.json (settings.cloud_sync)' if USE_UNIFIED_CONFIG else 'settings.json (cloud_sync)'}"
        self.sync_data_dir = "sync_data"
        self.temp_dir = tempfile.mkdtemp(prefix="xuanwu_sync_")
        logging.debug(f"云同步临时目录: {self.temp_dir}")
        
        self.ensure_sync_dir()
        enhanced_logger.debug_memory_snapshot("CloudSyncManager初始化后")
        logging.debug("CloudSyncManager初始化完成")
        
        # 支持的云存储服务
        self.supported_services = {
            'webdav': 'WebDAV服务器',
            'ftp': 'FTP服务器',
            'custom_api': '自定义API接口'
        }
        
        # 同步状态
        self.is_syncing = False
        self.last_sync_time = None
        
        # 自动同步定时器
        self.auto_sync_timer = QTimer()
        self.auto_sync_timer.timeout.connect(self.auto_sync)
        
    def ensure_sync_dir(self):
        """确保同步目录存在"""
        enhanced_logger.debug_function_call("ensure_sync_dir")
        
        try:
            if not os.path.exists(self.sync_data_dir):
                logging.debug(f"创建同步目录: {self.sync_data_dir}")
                os.makedirs(self.sync_data_dir)
            # 目录已存在时不记录日志，避免重复输出
        except Exception as e:
            enhanced_logger.debug_error(f"创建同步目录失败: {e}")
            raise
            
    def get_sync_config(self) -> Dict[str, Any]:
        """获取同步配置（读取自 settings.cloud_sync）"""
        enhanced_logger.debug_function_call("get_sync_config")
        enhanced_logger.debug_performance("获取同步配置开始")
        logging.debug(f"读取同步配置来源: {self.config_source}")

        try:
            settings = load_settings()
            config = settings.get('cloud_sync')

            # 初始化：优先迁移旧 cloud_sync_config.json，其次使用默认配置
            if not isinstance(config, dict):
                migrated = False
                legacy_path = 'cloud_sync_config.json'
                if os.path.exists(legacy_path):
                    try:
                        with open(legacy_path, 'r', encoding='utf-8') as f:
                            legacy_config = json.load(f)
                        if isinstance(legacy_config, dict):
                            config = legacy_config
                            migrated = True
                            logging.debug("检测到旧 cloud_sync_config.json，已迁移到 settings.cloud_sync")
                    except Exception as le:
                        logging.debug(f"迁移旧云同步配置失败，使用默认配置: {le}")
                if not migrated:
                    logging.debug("cloud_sync 配置缺失，初始化默认配置")
                    config = self.get_default_config()
                settings['cloud_sync'] = config
                save_settings(settings)
                enhanced_logger.debug_performance("获取同步配置完成（初始化/迁移）")
                return config

            # 补全缺失字段（向后兼容）
            defaults = self.get_default_config()
            updated = False
            for key, val in defaults.items():
                if key not in config:
                    config[key] = val
                    updated = True
            # 处理嵌套的 sync_items
            if 'sync_items' not in config or not isinstance(config['sync_items'], dict):
                config['sync_items'] = defaults['sync_items']
                updated = True
            else:
                for k, v in defaults['sync_items'].items():
                    if k not in config['sync_items']:
                        config['sync_items'][k] = v
                        updated = True

            if updated:
                logging.debug("补全 cloud_sync 缺失字段并保存到设置")
                settings['cloud_sync'] = config
                save_settings(settings)

            enhanced_logger.debug_performance("获取同步配置完成")
            logging.debug(f"成功读取同步配置，服务类型: {config.get('service_type', 'unknown')}")
            return config
        except Exception as e:
            enhanced_logger.debug_error(f"加载同步配置失败: {e}")
            logger.error(f"加载同步配置失败: {e}")
            logging.debug("配置加载失败，使用默认配置")
            enhanced_logger.debug_performance("获取同步配置完成（异常）")
            return self.get_default_config()
            
    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'enabled': False,
            'service_type': 'webdav',
            'server_url': '',
            'username': '',
            'password': '',
            'sync_interval': 30,  # 分钟
            'auto_sync': True,
            'sync_items': {
                'keywords': True,
                'settings': True,
                'logs': False,
                'screenshots': False
            },
            'conflict_resolution': 'ask',  # ask, local, remote, merge
            'encryption_enabled': True,
            'device_id': self.generate_device_id()
        }
        
    def save_sync_config(self, config: Dict[str, Any]) -> bool:
        """保存同步配置（写入 settings.cloud_sync）"""
        enhanced_logger.debug_function_call("save_sync_config")
        enhanced_logger.debug_performance("保存同步配置开始")
        logging.debug(f"保存同步配置到: {self.config_source}")
        logging.debug(f"配置服务类型: {config.get('service_type', 'unknown')}")

        try:
            settings = load_settings()
            settings['cloud_sync'] = config
            ok = save_settings(settings)
            if ok:
                logging.debug("同步配置保存成功")
                enhanced_logger.debug_performance("保存同步配置完成")
            else:
                enhanced_logger.debug_performance("保存同步配置失败")
            return ok
        except Exception as e:
            enhanced_logger.debug_error(f"保存同步配置失败: {e}")
            logger.error(f"保存同步配置失败: {e}")
            enhanced_logger.debug_performance("保存同步配置失败")
            return False
            
    def generate_device_id(self) -> str:
        """生成设备ID"""
        enhanced_logger.debug_function_call("generate_device_id")
        logging.debug("生成设备唯一标识")
        
        try:
            import platform
            import uuid
            
            # 基于机器信息生成唯一ID
            machine_info = f"{platform.node()}-{platform.system()}-{platform.machine()}"
            device_hash = hashlib.md5(machine_info.encode()).hexdigest()[:16]
            device_id = f"xuanwu_{device_hash}"
            logging.debug(f"生成设备ID: {device_id}")
            return device_id
        except Exception as e:
            enhanced_logger.debug_error(f"生成设备ID失败: {e}")
            # 返回一个基于时间的备用ID
            fallback_id = f"xuanwu_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:16]}"
            logging.debug(f"使用备用设备ID: {fallback_id}")
            return fallback_id
        
    def start_auto_sync(self):
        """启动自动同步"""
        enhanced_logger.debug_function_call("start_auto_sync")
        enhanced_logger.debug_performance("启动自动同步开始")
        logging.debug("检查自动同步配置")
        
        try:
            config = self.get_sync_config()
            if config.get('enabled', False) and config.get('auto_sync', True):
                interval_minutes = config.get('sync_interval', 30)
                logging.debug(f"自动同步间隔: {interval_minutes}分钟")
                self.auto_sync_timer.start(interval_minutes * 60 * 1000)  # 转换为毫秒
                logger.info(f"自动同步已启动，间隔 {interval_minutes} 分钟")
                enhanced_logger.debug_performance("启动自动同步完成")
            else:
                logger.info("自动同步已禁用")
                logging.debug("自动同步未启用或已禁用")
                enhanced_logger.debug_performance("启动自动同步完成（未启用）")
        except Exception as e:
            enhanced_logger.debug_error(f"启动自动同步失败: {e}")
            logger.error(f"启动自动同步失败: {e}")
            enhanced_logger.debug_performance("启动自动同步失败")
            
    def stop_auto_sync(self):
        """停止自动同步"""
        enhanced_logger.debug_function_call("stop_auto_sync")
        logging.debug("停止自动同步")
        
        self.auto_sync_timer.stop()
        logger.info("自动同步已停止")
        logging.debug("同步定时器已停止")
        
    def auto_sync(self):
        """自动同步"""
        if not self.is_syncing:
            logger.info("执行自动同步")
            self.sync_to_cloud()
            
    def test_connection(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """测试云服务连接"""
        enhanced_logger.debug_function_call("test_connection")
        enhanced_logger.debug_performance("测试连接开始")
        
        try:
            service_type = config.get('service_type', 'webdav')
            logging.debug(f"测试连接类型: {service_type}")
            
            if service_type == 'webdav':
                result = self._test_webdav_connection(config)
            elif service_type == 'ftp':
                result = self._test_ftp_connection(config)
            elif service_type == 'custom_api':
                result = self._test_custom_api_connection(config)
            else:
                result = False, f"不支持的服务类型: {service_type}"
                
            success, message = result
            logging.debug(f"连接测试结果: {'成功' if success else '失败'} - {message}")
            enhanced_logger.debug_performance(f"测试连接完成 - {'成功' if success else '失败'}")
            return result
                
        except Exception as e:
            enhanced_logger.debug_error(f"连接测试异常: {e}")
            enhanced_logger.debug_performance("测试连接失败（异常）")
            return False, f"连接测试失败: {e}"
            
    def _test_webdav_connection(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """测试WebDAV连接"""
        enhanced_logger.debug_function_call("_test_webdav_connection")
        enhanced_logger.debug_performance("WebDAV连接测试开始")
        logging.debug("开始WebDAV连接测试")
        
        try:
            import requests
            from requests.auth import HTTPBasicAuth
            
            url = config.get('server_url', '').rstrip('/')
            username = config.get('username', '')
            password = config.get('password', '')
            logging.debug(f"WebDAV服务器: {url}, 用户名: {username}")
            
            if not all([url, username, password]):
                logging.debug("WebDAV配置信息不完整")
                enhanced_logger.debug_performance("WebDAV连接测试完成（配置不完整）")
                return False, "请填写完整的服务器信息"
                
            # 发送PROPFIND请求测试连接
            response = requests.request(
                'PROPFIND', url,
                auth=HTTPBasicAuth(username, password),
                timeout=10
            )
            
            if response.status_code in [200, 207, 404]:  # 404也算连接成功
                logging.debug(f"WebDAV连接成功，状态码: {response.status_code}")
                enhanced_logger.debug_performance("WebDAV连接测试完成（成功）")
                return True, "WebDAV连接成功"
            else:
                logging.debug(f"WebDAV连接失败，状态码: {response.status_code}")
                enhanced_logger.debug_performance("WebDAV连接测试完成（失败）")
                return False, f"WebDAV连接失败: HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            enhanced_logger.debug_error("WebDAV连接超时")
            enhanced_logger.debug_performance("WebDAV连接测试完成（超时）")
            return False, "连接超时，请检查服务器地址"
        except requests.exceptions.ConnectionError:
            enhanced_logger.debug_error("WebDAV连接错误")
            enhanced_logger.debug_performance("WebDAV连接测试完成（连接错误）")
            return False, "无法连接到服务器，请检查网络和地址"
        except Exception as e:
            enhanced_logger.debug_error(f"WebDAV连接测试异常: {e}")
            enhanced_logger.debug_performance("WebDAV连接测试完成（异常）")
            return False, f"WebDAV连接测试失败: {e}"
            
    def _test_ftp_connection(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """测试FTP连接"""
        enhanced_logger.debug_function_call("_test_ftp_connection")
        enhanced_logger.debug_performance("FTP连接测试开始")
        logging.debug("开始FTP连接测试")
        
        try:
            import ftplib
            
            server_url = config.get('server_url', '')
            username = config.get('username', '')
            password = config.get('password', '')
            logging.debug(f"FTP服务器: {server_url}, 用户名: {username}")
            
            if not all([server_url, username, password]):
                logging.debug("FTP配置信息不完整")
                enhanced_logger.debug_performance("FTP连接测试完成（配置不完整）")
                return False, "请填写完整的服务器信息"
                
            # 解析服务器地址和端口
            if ':' in server_url:
                host, port = server_url.split(':', 1)
                port = int(port)
            else:
                host = server_url
                port = 21
                
            # 测试FTP连接
            logging.debug(f"连接FTP服务器: {host}:{port}")
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=10)
            ftp.login(username, password)
            ftp.quit()
            
            logging.debug("FTP连接测试成功")
            enhanced_logger.debug_performance("FTP连接测试完成（成功）")
            return True, "FTP连接成功"
            
        except ftplib.error_perm as e:
            enhanced_logger.debug_error(f"FTP认证失败: {e}")
            enhanced_logger.debug_performance("FTP连接测试完成（认证失败）")
            return False, f"FTP认证失败: {e}"
        except Exception as e:
            enhanced_logger.debug_error(f"FTP连接测试异常: {e}")
            enhanced_logger.debug_performance("FTP连接测试完成（异常）")
            return False, f"FTP连接测试失败: {e}"
            
    def _test_custom_api_connection(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """测试自定义API连接"""
        enhanced_logger.debug_function_call("_test_custom_api_connection")
        enhanced_logger.debug_performance("自定义API连接测试开始")
        logging.debug("开始自定义API连接测试")
        
        try:
            import requests
            
            url = config.get('server_url', '').rstrip('/')
            logging.debug(f"API地址: {url}")
            
            if not url:
                logging.debug("API地址为空")
                enhanced_logger.debug_performance("自定义API连接测试完成（地址为空）")
                return False, "请填写API地址"
                
            # 发送测试请求
            logging.debug(f"发送测试请求到: {url}/ping")
            response = requests.get(f"{url}/ping", timeout=10)
            
            if response.status_code == 200:
                logging.debug("API连接测试成功")
                enhanced_logger.debug_performance("自定义API连接测试完成（成功）")
                return True, "API连接成功"
            else:
                logging.debug(f"API连接失败，状态码: {response.status_code}")
                enhanced_logger.debug_performance("自定义API连接测试完成（失败）")
                return False, f"API连接失败: HTTP {response.status_code}"
                
        except Exception as e:
            enhanced_logger.debug_error(f"自定义API连接测试异常: {e}")
            enhanced_logger.debug_performance("自定义API连接测试完成（异常）")
            return False, f"API连接测试失败: {e}"
            
    def collect_sync_data(self) -> Dict[str, Any]:
        """收集需要同步的数据"""
        enhanced_logger.debug_function_call("collect_sync_data")
        enhanced_logger.debug_performance("收集同步数据开始")
        logging.debug("开始收集需要同步的数据")
        
        config = self.get_sync_config()
        sync_items = config.get('sync_items', {})
        logging.debug(f"同步项目配置: {sync_items}")
        
        data = {
            'device_id': config.get('device_id'),
            'sync_time': datetime.now().isoformat(),
            'data': {}
        }
        
        try:
            # 同步关键词
            if sync_items.get('keywords', True):
                logging.debug("收集关键词数据")
                if os.path.exists('keywords.json'):
                    with open('keywords.json', 'r', encoding='utf-8') as f:
                        keywords_data = json.load(f)
                        data['data']['keywords'] = keywords_data
                        logging.debug(f"收集到关键词数量: {len(keywords_data) if isinstance(keywords_data, list) else '未知'}")
                else:
                    logging.debug("关键词文件不存在")
                        
            # 同步设置
            if sync_items.get('settings', True):
                logging.debug("收集设置数据")
                try:
                    settings_data = load_settings()
                    data['data']['settings'] = settings_data
                    logging.debug(f"收集到设置项数量: {len(settings_data) if isinstance(settings_data, dict) else '未知'}")
                except Exception as e:
                    logging.debug(f"读取设置失败: {e}")
                        
            # 同步日志（最近7天）
            if sync_items.get('logs', False):
                logging.debug("收集日志数据（最近7天）")
                log_files = []
                for file in os.listdir('.'):
                    if file.startswith('xuanwu_') and file.endswith('.log'):
                        # 检查文件修改时间
                        mtime = os.path.getmtime(file)
                        if (datetime.now().timestamp() - mtime) < 7 * 24 * 3600:  # 7天内
                            with open(file, 'r', encoding='utf-8') as f:
                                content = f.read()
                                log_files.append({
                                    'filename': file,
                                    'content': content
                                })
                                logging.debug(f"收集日志文件: {file}, 大小: {len(content)}字符")
                data['data']['logs'] = log_files
                logging.debug(f"收集到日志文件数量: {len(log_files)}")
                
            # 同步截图（最近100张）
            if sync_items.get('screenshots', False):
                logging.debug("收集截图数据（最近100张）")
                screenshot_dir = 'screenshots'
                if os.path.exists(screenshot_dir):
                    screenshots = []
                    files = os.listdir(screenshot_dir)
                    files.sort(key=lambda x: os.path.getmtime(os.path.join(screenshot_dir, x)), reverse=True)
                    
                    for file in files[:100]:  # 最近100张
                        file_path = os.path.join(screenshot_dir, file)
                        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                            import base64
                            with open(file_path, 'rb') as f:
                                file_data = f.read()
                                screenshots.append({
                                    'filename': file,
                                    'data': base64.b64encode(file_data).decode('utf-8')
                                })
                                logging.debug(f"收集截图文件: {file}, 大小: {len(file_data)}字节")
                    data['data']['screenshots'] = screenshots
                    logging.debug(f"收集到截图文件数量: {len(screenshots)}")
                else:
                    logging.debug("截图目录不存在")
                    
        except Exception as e:
            enhanced_logger.debug_error(f"收集同步数据失败: {e}")
            logger.error(f"收集同步数据失败: {e}")
            
        total_size = len(json.dumps(data, ensure_ascii=False))
        logging.debug(f"同步数据收集完成，总大小: {total_size}字符")
        enhanced_logger.debug_performance("收集同步数据完成")
        return data
        
    def encrypt_data(self, data: str, password: str) -> str:
        """加密数据"""
        enhanced_logger.debug_function_call("encrypt_data", {"data_length": len(data), "has_password": bool(password)})
        enhanced_logger.debug_performance("encrypt_data_start", description="开始加密数据", stats={"data_length": len(data)})
        logging.debug(f"开始加密数据，数据长度: {len(data)}字符")
        
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64
            
            # 生成密钥
            salt = b'xuanwu_salt_2024'  # 在实际应用中应该使用随机盐
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            
            # 加密数据
            logging.debug("使用Fernet算法加密数据")
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(data.encode('utf-8'))
            result = base64.b64encode(encrypted_data).decode('utf-8')
            logging.debug(f"数据加密完成，加密后长度: {len(result)}字符")
            enhanced_logger.debug_performance("数据加密完成（成功）")
            return result
            
        except ImportError as e:
            enhanced_logger.debug_error("cryptography库未安装", exception_type=type(e).__name__)
            logger.warning("cryptography库未安装，使用简单编码")
            logging.debug("使用base64简单编码")
            import base64
            result = base64.b64encode(data.encode('utf-8')).decode('utf-8')
            enhanced_logger.debug_performance("encrypt_data_complete", description="数据加密完成（简单编码）", stats={"result_length": len(result)})
            return result
        except Exception as e:
            enhanced_logger.debug_error(f"数据加密异常: {e}", exception_type=type(e).__name__)
            logger.error(f"数据加密失败: {e}")
            enhanced_logger.debug_performance("encrypt_data_complete", description="数据加密完成（失败）")
            return data
            
    def decrypt_data(self, encrypted_data: str, password: str) -> str:
        """解密数据"""
        enhanced_logger.debug_function_call("decrypt_data", {"encrypted_data_length": len(encrypted_data), "has_password": bool(password)})
        enhanced_logger.debug_performance("decrypt_data_start", description="开始解密数据", stats={"encrypted_data_length": len(encrypted_data)})
        logging.debug(f"开始解密数据，加密数据长度: {len(encrypted_data)}字符")
        
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64
            
            # 生成密钥
            salt = b'xuanwu_salt_2024'
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            
            # 解密数据
            logging.debug("使用Fernet算法解密数据")
            fernet = Fernet(key)
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            decrypted_data = fernet.decrypt(encrypted_bytes)
            result = decrypted_data.decode('utf-8')
            logging.debug(f"数据解密完成，解密后长度: {len(result)}字符")
            enhanced_logger.debug_performance("数据解密完成（成功）")
            return result
            
        except ImportError as e:
            enhanced_logger.debug_error("cryptography库未安装", exception_type=type(e).__name__)
            logger.warning("cryptography库未安装，使用简单解码")
            logging.debug("使用base64简单解码")
            import base64
            result = base64.b64decode(encrypted_data.encode('utf-8')).decode('utf-8')
            enhanced_logger.debug_performance("decrypt_data_complete", description="数据解密完成（简单解码）", stats={"result_length": len(result)})
            return result
        except Exception as e:
            enhanced_logger.debug_error(f"数据解密异常: {e}", exception_type=type(e).__name__)
            logger.error(f"数据解密失败: {e}")
            enhanced_logger.debug_performance("decrypt_data_complete", description="数据解密完成（失败）")
            return encrypted_data
            
    def sync_to_cloud(self) -> Tuple[bool, str, Dict[str, Any]]:
        """同步到云端"""
        enhanced_logger.debug_function_call("sync_to_cloud")
        enhanced_logger.debug_performance("sync_to_cloud_start", description="开始同步到云端")
        logging.debug("开始同步到云端")
        
        if self.is_syncing:
            logging.debug("同步操作正在进行中，跳过")
            return False, "同步操作正在进行中", {}
            
        self.is_syncing = True
        
        try:
            self.sync_progress.emit(0, "开始收集同步数据...")
            
            config = self.get_sync_config()
            logging.debug(f"获取同步配置: enabled={config.get('enabled', False)}, service_type={config.get('service_type', 'webdav')}")
            if not config.get('enabled', False):
                logging.debug("云同步功能未启用")
                return False, "云同步功能未启用", {}
                
            # 收集数据
            sync_data = self.collect_sync_data()
            data_json = json.dumps(sync_data, ensure_ascii=False, indent=2)
            logging.debug(f"收集同步数据完成，数据大小: {len(data_json)}字符")
            
            self.sync_progress.emit(30, "准备上传数据...")
            
            # 加密数据
            encryption_enabled = config.get('encryption_enabled', True)
            logging.debug(f"加密设置: enabled={encryption_enabled}")
            if encryption_enabled:
                password = config.get('password', '')
                if password:
                    logging.debug("开始加密同步数据")
                    data_json = self.encrypt_data(data_json, password)
                    logging.debug(f"数据加密完成，加密后大小: {len(data_json)}字符")
                    
            # 上传到云端
            service_type = config.get('service_type', 'webdav')
            logging.debug(f"开始上传到云端，服务类型: {service_type}")
            
            if service_type == 'webdav':
                success, message = self._upload_to_webdav(data_json, config)
            elif service_type == 'ftp':
                success, message = self._upload_to_ftp(data_json, config)
            elif service_type == 'custom_api':
                success, message = self._upload_to_custom_api(data_json, config)
            else:
                success, message = False, f"不支持的服务类型: {service_type}"
                logging.debug(f"不支持的服务类型: {service_type}")
                
            logging.debug(f"上传结果: success={success}, message={message}")
            if success:
                self.last_sync_time = datetime.now()
                stats = {
                    'sync_time': self.last_sync_time.isoformat(),
                    'data_size': len(data_json),
                    'items_synced': len(sync_data.get('data', {}))
                }
                logging.debug(f"同步成功，统计信息: {stats}")
                enhanced_logger.debug_performance("sync_to_cloud_complete", description="同步到云端完成（成功）", stats=stats)
                
                self.sync_progress.emit(100, "同步完成")
                return True, message, stats
            else:
                logging.debug(f"同步失败: {message}")
                enhanced_logger.debug_performance("sync_to_cloud_complete", description="同步到云端完成（失败）")
                return False, message, {}
                
        except Exception as e:
            error_msg = f"同步到云端失败: {e}"
            enhanced_logger.debug_error(f"同步到云端异常: {e}", exception_type=type(e).__name__)
            logger.error(error_msg)
            enhanced_logger.debug_performance("sync_to_cloud_complete", description="同步到云端完成（异常）")
            return False, error_msg, {}
        finally:
            self.is_syncing = False
            logging.debug("同步操作结束，释放同步锁")
            
    def _upload_to_webdav(self, data: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        """上传到WebDAV"""
        try:
            import requests
            from requests.auth import HTTPBasicAuth
            
            url = config.get('server_url', '').rstrip('/')
            username = config.get('username', '')
            password = config.get('password', '')
            device_id = config.get('device_id', 'unknown')
            
            # 创建文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"xuanwu_sync_{device_id}_{timestamp}.json"
            upload_url = f"{url}/{filename}"
            
            self.sync_progress.emit(70, "正在上传到WebDAV...")
            
            response = requests.put(
                upload_url,
                data=data.encode('utf-8'),
                auth=HTTPBasicAuth(username, password),
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code in [200, 201, 204]:
                return True, f"数据已上传到WebDAV: {filename}"
            else:
                return False, f"WebDAV上传失败: HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"WebDAV上传失败: {e}"
            
    def _upload_to_ftp(self, data: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        """上传到FTP"""
        try:
            import ftplib
            import io
            
            server_url = config.get('server_url', '')
            username = config.get('username', '')
            password = config.get('password', '')
            device_id = config.get('device_id', 'unknown')
            
            # 解析服务器地址和端口
            if ':' in server_url:
                host, port = server_url.split(':', 1)
                port = int(port)
            else:
                host = server_url
                port = 21
                
            # 创建文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"xuanwu_sync_{device_id}_{timestamp}.json"
            
            self.sync_progress.emit(70, "正在上传到FTP...")
            
            # 上传文件
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=30)
            ftp.login(username, password)
            
            # 尝试创建目录
            try:
                ftp.mkd('xuanwu_sync')
            except (OSError, Exception):
                pass
                
            try:
                ftp.cwd('xuanwu_sync')
            except (OSError, Exception):
                pass
                
            # 上传文件
            data_io = io.BytesIO(data.encode('utf-8'))
            ftp.storbinary(f'STOR {filename}', data_io)
            ftp.quit()
            
            return True, f"数据已上传到FTP: {filename}"
            
        except Exception as e:
            return False, f"FTP上传失败: {e}"
            
    def _upload_to_custom_api(self, data: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        """上传到自定义API"""
        try:
            import requests
            
            url = config.get('server_url', '').rstrip('/')
            device_id = config.get('device_id', 'unknown')
            
            self.sync_progress.emit(70, "正在上传到API...")
            
            # 准备上传数据
            upload_data = {
                'device_id': device_id,
                'timestamp': datetime.now().isoformat(),
                'data': data
            }
            
            response = requests.post(
                f"{url}/sync/upload",
                json=upload_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return True, f"数据已上传到API: {result.get('message', '成功')}"
            else:
                return False, f"API上传失败: HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"API上传失败: {e}"
            
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        config = self.get_sync_config()
        
        return {
            'enabled': config.get('enabled', False),
            'service_type': config.get('service_type', 'webdav'),
            'auto_sync': config.get('auto_sync', True),
            'sync_interval': config.get('sync_interval', 30),
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'is_syncing': self.is_syncing,
            'device_id': config.get('device_id', 'unknown')
        }

class CloudSyncThread(QThread):
    """云同步线程"""
    
    finished = pyqtSignal(bool, str, dict)
    
    def __init__(self, sync_manager, operation='upload'):
        super().__init__()
        self.sync_manager = sync_manager
        self.operation = operation
        
    def run(self):
        try:
            if self.operation == 'upload':
                success, message, stats = self.sync_manager.sync_to_cloud()
                self.finished.emit(success, message, stats)
            else:
                self.finished.emit(False, f"不支持的操作: {self.operation}", {})
                
        except Exception as e:
            self.finished.emit(False, f"同步线程错误: {e}", {})