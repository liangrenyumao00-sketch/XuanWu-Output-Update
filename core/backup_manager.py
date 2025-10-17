import os
import json
import shutil
import zipfile
import logging
from datetime import datetime, timedelta
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
from core.config import LOG_DIR, SCREENSHOT_DIR
from core.settings import load_settings, save_settings, SETTINGS_FILE
from core.enhanced_logger import get_enhanced_logger

# 获取增强日志记录器实例
enhanced_logger = get_enhanced_logger()

# 使用专用logger，日志将记录到xuanwu_log.html
logger = logging.getLogger('backup_manager')

class BackupManager(QObject):
    """备份管理器"""
    
    backup_progress = pyqtSignal(int, str)  # 进度, 消息
    backup_completed = pyqtSignal(bool, str)  # 成功, 消息
    
    def __init__(self):
        super().__init__()
        enhanced_logger.debug_function_call("BackupManager.__init__")
        enhanced_logger.debug_memory_snapshot("BackupManager初始化前")
        
        self.backup_dir = os.path.join(os.getcwd(), "backups")
        logging.debug(f"备份目录设置为: {self.backup_dir}")
        self._auto_backup_timer: QTimer | None = None
        
        self.ensure_backup_dir()
        enhanced_logger.debug_memory_snapshot("BackupManager初始化后")
        logging.debug("BackupManager初始化完成")
        
    def ensure_backup_dir(self):
        """确保备份目录存在"""
        enhanced_logger.debug_function_call("ensure_backup_dir")
        
        try:
            if not os.path.exists(self.backup_dir):
                logging.debug(f"创建备份目录: {self.backup_dir}")
                os.makedirs(self.backup_dir)
            # 目录已存在时不记录日志，避免重复输出
        except Exception as e:
            enhanced_logger.debug_error(f"创建备份目录失败: {e}")
            raise
            
    def get_backup_config(self):
        """获取备份配置"""
        enhanced_logger.debug_function_call("get_backup_config")
        logging.debug("获取备份配置")
        
        try:
            settings = load_settings()
            config = settings.get('backup', {
                'auto_backup': True,
                'backup_interval': 24,  # 小时
                'max_backups': 10,
                'backup_logs': True,
                'backup_screenshots': True,
                'backup_settings': True,
                'backup_keywords': True
            })
            logging.debug(f"备份配置: {config}")
            return config
        except Exception as e:
            enhanced_logger.debug_error(f"获取备份配置失败: {e}")
            raise
        
    def update_backup_config(self, config):
        """更新备份配置"""
        enhanced_logger.debug_function_call("update_backup_config")
        logging.debug(f"更新备份配置: {config}")
        
        try:
            settings = load_settings()
            settings['backup'] = config
            save_settings(settings)
            logging.debug("备份配置更新成功")
            # 立即按新配置重启自动备份（定时器）
            try:
                self.start_auto_backup()
            except Exception as e:
                logger.debug(f"重启自动备份失败: {e}")
        except Exception as e:
            enhanced_logger.debug_error(f"更新备份配置失败: {e}")
            raise
        
    def should_auto_backup(self):
        """检查是否需要自动备份"""
        enhanced_logger.debug_function_call("should_auto_backup")
        logging.debug("检查是否需要自动备份")
        
        try:
            config = self.get_backup_config()
            if not config.get('auto_backup', True):
                logging.debug("自动备份已禁用")
                return False
                
            # 检查上次备份时间
            last_backup_file = os.path.join(self.backup_dir, '.last_backup')
            if not os.path.exists(last_backup_file):
                logging.debug("未找到上次备份记录，需要备份")
                return True
                
            try:
                with open(last_backup_file, 'r') as f:
                    last_backup_time = datetime.fromisoformat(f.read().strip())
                
                interval_hours = config.get('backup_interval', 24)
                time_diff = datetime.now() - last_backup_time
                need_backup = time_diff > timedelta(hours=interval_hours)
                
                logging.debug(f"上次备份时间: {last_backup_time}, 间隔: {interval_hours}小时, 需要备份: {need_backup}")
                return need_backup
            except Exception as e:
                enhanced_logger.debug_error(f"检查备份时间失败: {e}")
                logger.error(f"检查备份时间失败: {e}")
                return True
        except Exception as e:
            enhanced_logger.debug_error(f"should_auto_backup失败: {e}")
            return True
    
    def stop_auto_backup(self):
        """停止自动备份"""
        try:
            # 更新配置，禁用自动备份
            config = self.get_backup_config()
            config['auto_backup'] = False
            self.update_backup_config(config)
            # 停止定时器
            if self._auto_backup_timer:
                try:
                    self._auto_backup_timer.stop()
                except Exception:
                    pass
            logger.info("自动备份已停止")
        except Exception as e:
            logger.error(f"停止自动备份失败: {e}")
            
    def create_backup(self, backup_name=None):
        """创建备份"""
        enhanced_logger.debug_function_call("create_backup")
        enhanced_logger.debug_performance("create_backup")
        
        if not backup_name:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        backup_path = os.path.join(self.backup_dir, f"{backup_name}.zip")
        logging.debug(f"开始创建备份: {backup_name}, 路径: {backup_path}")
        
        config = self.get_backup_config()
        logging.debug(f"使用备份配置: {config}")
        
        try:
            self.backup_progress.emit(0, "开始创建备份...")
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                total_files = 0
                processed_files = 0
                
                # 计算总文件数
                if config.get('backup_logs', True) and os.path.exists(LOG_DIR):
                    total_files += len(list(Path(LOG_DIR).rglob('*')))
                if config.get('backup_screenshots', True) and os.path.exists(SCREENSHOT_DIR):
                    total_files += len(list(Path(SCREENSHOT_DIR).rglob('*')))
                if config.get('backup_settings', True):
                    total_files += 1  # settings.json
                if config.get('backup_keywords', True):
                    total_files += 1  # target_keywords.txt
                    
                # 备份日志文件
                if config.get('backup_logs', True) and os.path.exists(LOG_DIR):
                    self.backup_progress.emit(10, "备份日志文件...")
                    for file_path in Path(LOG_DIR).rglob('*'):
                        if file_path.is_file():
                            arcname = os.path.join('logs', file_path.relative_to(LOG_DIR))
                            zipf.write(file_path, arcname)
                            processed_files += 1
                            if total_files > 0:
                                progress = int((processed_files / total_files) * 60)
                                self.backup_progress.emit(progress, f"备份日志文件... {processed_files}/{total_files}")
                                
                # 备份截图文件
                if config.get('backup_screenshots', True) and os.path.exists(SCREENSHOT_DIR):
                    self.backup_progress.emit(70, "备份截图文件...")
                    for file_path in Path(SCREENSHOT_DIR).rglob('*'):
                        if file_path.is_file():
                            arcname = os.path.join('screenshots', file_path.relative_to(SCREENSHOT_DIR))
                            zipf.write(file_path, arcname)
                            processed_files += 1
                            if total_files > 0:
                                progress = int((processed_files / total_files) * 80)
                                self.backup_progress.emit(progress, f"备份截图文件... {processed_files}/{total_files}")
                                
                # 备份设置文件
                if config.get('backup_settings', True):
                    self.backup_progress.emit(85, "备份设置文件...")
                    settings_file = SETTINGS_FILE
                    if os.path.exists(settings_file):
                        zipf.write(settings_file, 'settings.json')
                        
                # 备份关键词文件
                if config.get('backup_keywords', True):
                    self.backup_progress.emit(90, "备份关键词文件...")
                    keywords_file = 'target_keywords.txt'
                    if os.path.exists(keywords_file):
                        zipf.write(keywords_file, 'target_keywords.txt')
                        
                # 添加备份信息
                backup_info = {
                    'backup_name': backup_name,
                    'backup_time': datetime.now().isoformat(),
                    'backup_config': config,
                    'version': '2.1.6'
                }
                zipf.writestr('backup_info.json', json.dumps(backup_info, indent=2, ensure_ascii=False))
                
            self.backup_progress.emit(95, "完成备份创建...")
            
            # 更新最后备份时间
            last_backup_file = os.path.join(self.backup_dir, '.last_backup')
            with open(last_backup_file, 'w') as f:
                f.write(datetime.now().isoformat())
            logging.debug(f"更新最后备份时间: {datetime.now().isoformat()}")
                
            # 清理旧备份
            logging.debug("开始清理旧备份")
            self.cleanup_old_backups()
            
            self.backup_progress.emit(100, "备份创建完成")
            self.backup_completed.emit(True, f"备份已保存到: {backup_path}")
            
            enhanced_logger.debug_performance("create_backup")
            logger.info(f"备份创建成功: {backup_path}")
            logging.debug(f"备份文件大小: {os.path.getsize(backup_path)} 字节")
            return True, backup_path
            
        except Exception as e:
            error_msg = f"创建备份失败: {e}"
            enhanced_logger.debug_error(f"创建备份失败: {e}")
            logger.error(error_msg)
            self.backup_completed.emit(False, error_msg)
            return False, error_msg
            
    def restore_backup(self, backup_path, restore_config=None):
        """恢复备份"""
        if not os.path.exists(backup_path):
            error_msg = "备份文件不存在"
            self.backup_completed.emit(False, error_msg)
            return False, error_msg
            
        try:
            self.backup_progress.emit(0, "开始恢复备份...")
            
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                # 读取备份信息
                backup_info = None
                if 'backup_info.json' in zipf.namelist():
                    backup_info_data = zipf.read('backup_info.json')
                    backup_info = json.loads(backup_info_data.decode('utf-8'))
                    
                if not restore_config:
                    restore_config = {
                        'restore_logs': True,
                        'restore_screenshots': True,
                        'restore_settings': True,
                        'restore_keywords': True
                    }
                    
                # 恢复日志文件
                if restore_config.get('restore_logs', True):
                    self.backup_progress.emit(20, "恢复日志文件...")
                    for member in zipf.namelist():
                        if member.startswith('logs/'):
                            target_path = os.path.join(LOG_DIR, member[5:])  # 去掉 'logs/' 前缀
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with zipf.open(member) as source, open(target_path, 'wb') as target:
                                shutil.copyfileobj(source, target)
                                
                # 恢复截图文件
                if restore_config.get('restore_screenshots', True):
                    self.backup_progress.emit(50, "恢复截图文件...")
                    for member in zipf.namelist():
                        if member.startswith('screenshots/'):
                            target_path = os.path.join(SCREENSHOT_DIR, member[12:])  # 去掉 'screenshots/' 前缀
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with zipf.open(member) as source, open(target_path, 'wb') as target:
                                shutil.copyfileobj(source, target)
                                
                # 恢复设置文件（写入到固定设置路径）
                if restore_config.get('restore_settings', True) and 'settings.json' in zipf.namelist():
                    self.backup_progress.emit(80, "恢复设置文件...")
                    try:
                        with zipf.open('settings.json') as source, open(SETTINGS_FILE, 'wb') as target:
                            shutil.copyfileobj(source, target)
                    except Exception as e:
                        logger.error(f"恢复设置文件失败: {e}")
                    
                # 恢复关键词文件
                if restore_config.get('restore_keywords', True) and 'target_keywords.txt' in zipf.namelist():
                    self.backup_progress.emit(90, "恢复关键词文件...")
                    zipf.extract('target_keywords.txt', '.')
                    
            self.backup_progress.emit(100, "备份恢复完成")
            success_msg = f"备份恢复成功: {backup_path}"
            self.backup_completed.emit(True, success_msg)
            logger.info(success_msg)
            return True, success_msg
            
        except Exception as e:
            error_msg = f"恢复备份失败: {e}"
            logger.error(error_msg)
            self.backup_completed.emit(False, error_msg)
            return False, error_msg
            
    def list_backups(self):
        """列出所有备份"""
        enhanced_logger.debug_function_call("list_backups")
        enhanced_logger.debug_performance("list_backups_start", description="开始列出备份文件")
        logging.debug(f"列出备份目录中的文件: {self.backup_dir}")
        
        backups = []
        if not os.path.exists(self.backup_dir):
            logging.debug("备份目录不存在")
            return backups
            
        for file_name in os.listdir(self.backup_dir):
            if file_name.endswith('.zip'):
                file_path = os.path.join(self.backup_dir, file_name)
                try:
                    # 获取备份信息
                    backup_info = {
                        'name': file_name[:-4],  # 去掉 .zip 后缀
                        'path': file_path,
                        'size': os.path.getsize(file_path),
                        'created_time': datetime.fromtimestamp(os.path.getctime(file_path))
                    }
                    
                    # 尝试读取备份详细信息
                    try:
                        with zipfile.ZipFile(file_path, 'r') as zipf:
                            if 'backup_info.json' in zipf.namelist():
                                backup_info_data = zipf.read('backup_info.json')
                                detailed_info = json.loads(backup_info_data.decode('utf-8'))
                                backup_info.update(detailed_info)
                    except:
                        pass  # 如果读取失败，使用基本信息
                        
                    backups.append(backup_info)
                except Exception as e:
                    enhanced_logger.debug_error(f"读取备份信息失败 {file_name}: {e}", exception_type=type(e).__name__)
                    logger.error(f"读取备份信息失败 {file_name}: {e}")
                    
        # 按创建时间排序
        backups.sort(key=lambda x: x['created_time'], reverse=True)
        enhanced_logger.debug_performance("list_backups_end", description=f"完成备份列表，共{len(backups)}个备份")
        logging.debug(f"找到 {len(backups)} 个备份文件")
        return backups
        
    def delete_backup(self, backup_path):
        """删除备份"""
        enhanced_logger.debug_function_call("delete_backup", backup_path=backup_path)
        logging.debug(f"删除备份文件: {backup_path}")
        
        try:
            if os.path.exists(backup_path):
                file_size = os.path.getsize(backup_path)
                os.remove(backup_path)
                enhanced_logger.debug_performance("delete_backup_success", description=f"成功删除备份，释放空间{file_size}字节")
                logger.info(f"备份已删除: {backup_path}")
                logging.debug(f"删除备份成功，释放空间: {file_size} 字节")
                return True, "备份删除成功"
            else:
                logging.debug("备份文件不存在")
                return False, "备份文件不存在"
        except Exception as e:
            error_msg = f"删除备份失败: {e}"
            enhanced_logger.debug_error(error_msg, exception_type=type(e).__name__)
            logger.error(error_msg)
            return False, error_msg
            
    def cleanup_old_backups(self):
        """清理旧备份"""
        enhanced_logger.debug_function_call("cleanup_old_backups")
        logging.debug("开始清理旧备份")
        
        try:
            config = self.get_backup_config()
            max_backups = config.get('max_backups', 10)
            
            backups = self.list_backups()
            logging.debug(f"当前备份数量: {len(backups)}, 最大保留数量: {max_backups}")
            
            if len(backups) > max_backups:
                # 按创建时间排序，删除最旧的备份
                backups.sort(key=lambda x: x['created_time'])
                deleted_count = 0
                freed_space = 0
                
                for backup in backups[:-max_backups]:
                    try:
                        file_size = os.path.getsize(backup['path'])
                        os.remove(backup['path'])
                        deleted_count += 1
                        freed_space += file_size
                        logger.info(f"已删除旧备份: {backup['name']}")
                        logging.debug(f"删除旧备份: {backup['name']}, 大小: {file_size} 字节")
                    except Exception as e:
                        enhanced_logger.debug_error(f"删除旧备份失败: {e}", exception_type=type(e).__name__)
                        logger.error(f"删除旧备份失败: {e}")
                        
                enhanced_logger.debug_performance("cleanup_old_backups_complete", 
                    description=f"清理完成，删除{deleted_count}个备份，释放{freed_space}字节")
                logging.debug(f"清理旧备份完成，删除 {deleted_count} 个文件，释放 {freed_space} 字节")
            else:
                logging.debug("无需清理旧备份")
                        
        except Exception as e:
            enhanced_logger.debug_error(f"清理旧备份失败: {e}", exception_type=type(e).__name__)
            logger.error(f"清理旧备份失败: {e}")
            
    def start_auto_backup(self):
        """启动自动备份"""
        enhanced_logger.debug_function_call("start_auto_backup")
        logging.debug("启动自动备份功能")
        
        try:
            config = self.get_backup_config()
            if config.get('auto_backup', True):
                # 检查是否需要创建备份
                enhanced_logger.debug_performance("auto_backup_check_start", description="开始检查自动备份需求")
                self.check_and_create_backup()
                logger.info("自动备份功能已启动")
                logging.debug("自动备份功能启动成功")

                # 根据备份间隔启动定时器，周期性检查与创建备份
                interval_hours = max(1, int(config.get('backup_interval', 24)))
                interval_ms = interval_hours * 3600 * 1000
                if self._auto_backup_timer is None:
                    self._auto_backup_timer = QTimer(self)
                    self._auto_backup_timer.setSingleShot(False)
                    self._auto_backup_timer.timeout.connect(self.check_and_create_backup)
                try:
                    self._auto_backup_timer.stop()
                except Exception:
                    pass
                self._auto_backup_timer.start(interval_ms)
                logging.debug(f"自动备份定时器已启动，间隔: {interval_hours} 小时")
            else:
                logger.info("自动备份功能已禁用")
                logging.debug("自动备份功能已在配置中禁用")
                # 确保定时器处于停止状态
                if self._auto_backup_timer:
                    try:
                        self._auto_backup_timer.stop()
                    except Exception:
                        pass
        except Exception as e:
            enhanced_logger.debug_error(f"启动自动备份失败: {e}", exception_type=type(e).__name__)
            logger.error(f"启动自动备份失败: {e}")
            
    def check_and_create_backup(self):
        """检查并创建备份"""
        enhanced_logger.debug_function_call("check_and_create_backup")
        logging.debug("检查并创建自动备份")
        
        try:
            config = self.get_backup_config()
            interval_hours = config.get('backup_interval', 24)
            logging.debug(f"备份间隔设置: {interval_hours} 小时")
            
            # 获取最新备份时间
            backups = self.list_backups()
            if backups:
                latest_backup = max(backups, key=lambda x: x['created_time'])
                time_diff = datetime.now() - latest_backup['created_time']
                logging.debug(f"最新备份时间: {latest_backup['created_time']}, 时间差: {time_diff}")
                
                if time_diff.total_seconds() < interval_hours * 3600:
                    logger.info(f"距离上次备份时间不足{interval_hours}小时，跳过自动备份")
                    logging.debug(f"跳过自动备份，剩余时间: {interval_hours * 3600 - time_diff.total_seconds()} 秒")
                    return
            else:
                logging.debug("未找到现有备份，将创建首次备份")
                    
            # 创建新备份
            enhanced_logger.debug_performance("auto_backup_create_start", description="开始创建自动备份")
            success, message = self.create_backup()
            if success:
                enhanced_logger.debug_performance("auto_backup_create_success", description="自动备份创建成功")
                logger.info(f"自动备份创建成功: {message}")
                logging.debug(f"自动备份创建成功: {message}")
                # 清理旧备份
                self.cleanup_old_backups()
            else:
                enhanced_logger.debug_error(f"自动备份创建失败: {message}")
                logger.error(f"自动备份创建失败: {message}")
                
        except Exception as e:
            enhanced_logger.debug_error(f"检查并创建备份失败: {e}", exception_type=type(e).__name__)
            logger.error(f"检查并创建备份失败: {e}")
                
    def get_backup_size(self):
        """获取备份目录总大小"""
        enhanced_logger.debug_function_call("get_backup_size")
        logging.debug(f"计算备份目录大小: {self.backup_dir}")
        
        total_size = 0
        file_count = 0
        
        if os.path.exists(self.backup_dir):
            try:
                for dirpath, dirnames, filenames in os.walk(self.backup_dir):
                    for filename in filenames:
                        file_path = os.path.join(dirpath, filename)
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        file_count += 1
                        
                enhanced_logger.debug_performance("get_backup_size_complete", 
                    description=f"备份目录统计完成，{file_count}个文件，总大小{total_size}字节")
                logging.debug(f"备份目录大小统计: {file_count} 个文件，总大小 {total_size} 字节")
            except Exception as e:
                enhanced_logger.debug_error(f"计算备份目录大小失败: {e}", exception_type=type(e).__name__)
                logging.debug(f"计算备份目录大小时出错: {e}")
        else:
            logging.debug("备份目录不存在")
            
        return total_size

class BackupThread(QThread):
    """备份线程"""
    
    def __init__(self, backup_manager, operation, *args):
        super().__init__()
        self.backup_manager = backup_manager
        self.operation = operation
        self.args = args
        
    def run(self):
        """运行备份操作"""
        if self.operation == 'create':
            self.backup_manager.create_backup(*self.args)
        elif self.operation == 'restore':
            self.backup_manager.restore_backup(*self.args)