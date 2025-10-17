# core/desktop_notifier.py
import logging
import platform
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QSystemTrayIcon, QApplication
from PyQt6.QtGui import QIcon
from core.settings import load_settings
from core.enhanced_logger import get_enhanced_logger

# 初始化增强日志记录器
enhanced_logger = get_enhanced_logger()

class DesktopNotifier(QObject):
    """桌面通知器"""
    
    # 信号
    notification_shown = pyqtSignal(bool, str)  # 显示结果, 消息
    
    def __init__(self, parent=None):
        super().__init__()
        enhanced_logger.debug_function_call("DesktopNotifier.__init__")
        self.parent = parent
        self.settings = load_settings()
        self.system_tray = None
        logging.debug("桌面通知器初始化完成")
        enhanced_logger.debug_performance("DesktopNotifier.__init__", description="桌面通知器初始化完成")
        self.init_system_tray()
        
    def init_system_tray(self):
        """初始化系统托盘图标"""
        enhanced_logger.debug_function_call("DesktopNotifier.init_system_tray")
        try:
            if QSystemTrayIcon.isSystemTrayAvailable():
                self.system_tray = QSystemTrayIcon(self.parent)
                # 设置默认图标
                if hasattr(self.parent, 'windowIcon'):
                    self.system_tray.setIcon(self.parent.windowIcon())
                else:
                    # 创建一个简单的默认图标
                    from PyQt6.QtGui import QPixmap, QPainter, QBrush
                    from PyQt6.QtCore import Qt
                    pixmap = QPixmap(16, 16)
                    pixmap.fill(Qt.GlobalColor.blue)
                    painter = QPainter(pixmap)
                    painter.setBrush(QBrush(Qt.GlobalColor.white))
                    painter.drawEllipse(2, 2, 12, 12)
                    painter.end()
                    self.system_tray.setIcon(QIcon(pixmap))
                
                self.system_tray.setToolTip("炫舞OCR")
                self.system_tray.show()
                logging.info("系统托盘图标初始化成功")
                enhanced_logger.debug_performance("DesktopNotifier.init_system_tray", description="系统托盘图标初始化成功")
            else:
                logging.warning("系统不支持系统托盘")
                enhanced_logger.log_error("DesktopNotifier.init_system_tray", "系统不支持系统托盘")
        except Exception as e:
            logging.error(f"系统托盘初始化失败: {e}")
            enhanced_logger.log_error("DesktopNotifier.init_system_tray", f"系统托盘初始化失败: {e}")
            
    def is_enabled(self):
        """检查桌面通知是否启用"""
        enhanced_logger.debug_function_call("DesktopNotifier.is_enabled")
        enabled = self.settings.get("enable_desktop_notify", False)
        logging.debug(f"桌面通知启用状态: {enabled}")
        return enabled
        
    def show_notification(self, title, message, duration=5000):
        """显示桌面通知"""
        enhanced_logger.debug_function_call("DesktopNotifier.show_notification")
        try:
            if not self.is_enabled():
                logging.debug("桌面通知未启用")
                enhanced_logger.debug_performance("DesktopNotifier.show_notification", description="桌面通知未启用，跳过显示")
                return False, "桌面通知未启用"
                
            # 刷新设置
            self.settings = load_settings()
            
            success = False
            error_msg = ""
            
            # 尝试使用系统托盘通知
            if self.system_tray and QSystemTrayIcon.isSystemTrayAvailable():
                try:
                    self.system_tray.showMessage(
                        title, 
                        message, 
                        QSystemTrayIcon.MessageIcon.Information, 
                        duration
                    )
                    success = True
                    logging.info(f"系统托盘通知已显示: {title}")
                    enhanced_logger.debug_performance("DesktopNotifier.show_notification", description=f"系统托盘通知显示成功: {title}")
                except Exception as e:
                    error_msg = f"系统托盘通知失败: {e}"
                    logging.error(error_msg)
                    enhanced_logger.log_error("DesktopNotifier.show_notification", error_msg)
            
            # 如果系统托盘不可用，尝试使用平台特定的通知
            if not success:
                success, error_msg = self._show_platform_notification(title, message)
            
            if success:
                self.notification_shown.emit(True, "桌面通知显示成功")
                enhanced_logger.debug_performance("DesktopNotifier.show_notification", description="桌面通知显示成功")
                return True, "桌面通知显示成功"
            else:
                self.notification_shown.emit(False, error_msg)
                enhanced_logger.log_error("DesktopNotifier.show_notification", f"桌面通知显示失败: {error_msg}")
                return False, error_msg
                
        except Exception as e:
            error_msg = f"桌面通知显示异常: {e}"
            logging.exception(error_msg)
            enhanced_logger.log_error("DesktopNotifier.show_notification", error_msg)
            self.notification_shown.emit(False, error_msg)
            return False, error_msg
            
    def _show_platform_notification(self, title, message):
        """显示平台特定的通知"""
        enhanced_logger.debug_function_call("DesktopNotifier._show_platform_notification")
        try:
            system = platform.system().lower()
            logging.debug(f"检测到操作系统: {system}")
            
            if system == "windows":
                return self._show_windows_notification(title, message)
            elif system == "darwin":  # macOS
                return self._show_macos_notification(title, message)
            elif system == "linux":
                return self._show_linux_notification(title, message)
            else:
                error_msg = f"不支持的操作系统: {system}"
                enhanced_logger.log_error("DesktopNotifier._show_platform_notification", error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"平台通知失败: {e}"
            enhanced_logger.log_error("DesktopNotifier._show_platform_notification", error_msg)
            return False, error_msg
            
    def _show_windows_notification(self, title, message):
        """显示Windows通知"""
        enhanced_logger.debug_function_call("DesktopNotifier._show_windows_notification")
        try:
            # 尝试使用win10toast库
            try:
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(
                    title=title,
                    msg=message,
                    duration=5,
                    threaded=True
                )
                enhanced_logger.debug_performance("DesktopNotifier._show_windows_notification", description="win10toast通知显示成功")
                return True, "Windows通知显示成功"
            except ImportError:
                logging.warning("win10toast库未安装，尝试使用plyer")
                
            # 尝试使用plyer库
            try:
                from plyer import notification
                notification.notify(
                    title=title,
                    message=message,
                    timeout=5
                )
                enhanced_logger.debug_performance("DesktopNotifier._show_windows_notification", description="Plyer通知显示成功")
                return True, "Plyer通知显示成功"
            except ImportError:
                logging.warning("plyer库未安装")
                
            # 使用Windows原生API
            try:
                import subprocess
                # 使用PowerShell显示通知
                ps_script = f'''
                Add-Type -AssemblyName System.Windows.Forms
                $notification = New-Object System.Windows.Forms.NotifyIcon
                $notification.Icon = [System.Drawing.SystemIcons]::Information
                $notification.BalloonTipTitle = "{title}"
                $notification.BalloonTipText = "{message}"
                $notification.Visible = $true
                $notification.ShowBalloonTip(5000)
                Start-Sleep -Seconds 6
                $notification.Dispose()
                '''
                subprocess.run(["powershell", "-Command", ps_script], 
                             capture_output=True, text=True, timeout=10)
                enhanced_logger.debug_performance("DesktopNotifier._show_windows_notification", description="PowerShell通知显示成功")
                return True, "PowerShell通知显示成功"
            except Exception as e:
                logging.error(f"PowerShell通知失败: {e}")
                enhanced_logger.log_error("DesktopNotifier._show_windows_notification", f"PowerShell通知失败: {e}")
                
            error_msg = "所有Windows通知方法都失败"
            enhanced_logger.log_error("DesktopNotifier._show_windows_notification", error_msg)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Windows通知异常: {e}"
            enhanced_logger.log_error("DesktopNotifier._show_windows_notification", error_msg)
            return False, error_msg
            
    def _show_macos_notification(self, title, message):
        """显示macOS通知"""
        enhanced_logger.debug_function_call("DesktopNotifier._show_macos_notification")
        try:
            import subprocess
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], timeout=10)
            enhanced_logger.debug_performance("DesktopNotifier._show_macos_notification", description="macOS通知显示成功")
            return True, "macOS通知显示成功"
        except Exception as e:
            error_msg = f"macOS通知失败: {e}"
            enhanced_logger.log_error("DesktopNotifier._show_macos_notification", error_msg)
            return False, error_msg
            
    def _show_linux_notification(self, title, message):
        """显示Linux通知"""
        enhanced_logger.debug_function_call("DesktopNotifier._show_linux_notification")
        try:
            import subprocess
            subprocess.run(["notify-send", title, message], timeout=10)
            enhanced_logger.debug_performance("DesktopNotifier._show_linux_notification", description="Linux通知显示成功")
            return True, "Linux通知显示成功"
        except Exception as e:
            error_msg = f"Linux通知失败: {e}"
            enhanced_logger.log_error("DesktopNotifier._show_linux_notification", error_msg)
            return False, error_msg
            
    def test_notification(self):
        """测试桌面通知功能"""
        enhanced_logger.debug_function_call("DesktopNotifier.test_notification")
        logging.debug("开始测试桌面通知功能")
        result = self.show_notification(
            "炫舞OCR测试", 
            "这是一条测试通知，如果您看到这条消息，说明桌面通知功能正常工作。"
        )
        enhanced_logger.debug_performance("DesktopNotifier.test_notification", description=f"测试通知结果: {result[0]}")
        return result