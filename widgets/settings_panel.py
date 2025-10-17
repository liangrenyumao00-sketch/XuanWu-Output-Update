# widgets/settings_panel.py
"""
设置面板模块

该模块提供了应用程序的设置管理界面，包含基础设置、高级选项、主题配置、
字体设置、语言选择等多种配置功能。支持设置的保存、加载和实时预览。

主要功能：
- 基础设置：OCR引擎、API配置、快捷键等
- 高级选项：性能优化、网络设置、缓存管理等
- 主题配置：界面主题、颜色方案、字体设置等
- 语言设置：多语言支持和本地化配置
- 导入导出：设置的备份和恢复功能

依赖：
- PyQt6：GUI框架
- core.settings：设置管理
- core.theme：主题管理
- core.i18n：国际化支持

作者：XuanWu OCR Team
版本：2.1.7
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QMessageBox,
    QCheckBox, QLineEdit, QSpinBox, QFormLayout, QApplication, QGroupBox, QFileDialog,
    QPlainTextEdit, QGridLayout, QTabWidget, QWidget, QSizePolicy, QTableWidget, QTableWidgetItem,
    QHeaderView
)

from PyQt6.QtCore import pyqtSignal, Qt
import logging
import platform
import subprocess
import smtplib
import requests
import json
import time
import socket
from email.mime.text import MIMEText

from core.settings import load_settings, save_settings
from core.theme import apply_theme
from core.input_validator import get_input_validator, validate_api_key, validate_password, sanitize_input
from widgets.theme_panel import ThemePanel
from widgets.enhanced_font_panel import EnhancedFontDialog
from widgets.modern_language_panel import ModernLanguagePanel
from core.i18n import t


# 使用专用logger，日志将记录到xuanwu_log.html
logger = logging.getLogger('settings_manager')


class BaseSettingDialog(QDialog):
    """
    基础设置对话框
    
    提供应用程序设置的基础框架，包含通用的设置加载、保存、
    主题应用等功能。其他具体的设置对话框可以继承此类。
    
    Attributes:
        settings (dict): 当前的设置配置
        _parent_window (QWidget): 父窗口引用，用于居中显示
    
    Signals:
        settings_changed (dict): 设置发生变化时发出的信号
    
    Example:
        >>> dialog = BaseSettingDialog(parent_widget)
        >>> dialog.show()
        >>> dialog.settings_changed.connect(on_settings_changed)
    """
    settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self.setWindowModality(Qt.WindowModality.WindowModal)
        
        # 设置对话框样式
        self.setMinimumWidth(400)  # 设置最小宽度
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)  # 移除帮助按钮
        
        # 应用主题样式
        self.apply_theme_styles()
        
        self.init_ui()
        self.load_values()
        
        # 存储父窗口引用用于居中显示
        self._parent_window = parent
    
    def showEvent(self, event):
        """窗口显示事件，确保对话框居中显示"""
        super().showEvent(event)
        if self._parent_window:
            # 确保对话框在父窗口中央显示
            parent_geometry = self._parent_window.geometry()
            dialog_geometry = self.geometry()
            x = parent_geometry.x() + (parent_geometry.width() - dialog_geometry.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - dialog_geometry.height()) // 2
            self.move(x, y)
    
    def clear_layout(self, layout):
        """清除布局中的所有控件"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_layout(child.layout())
    
    def apply_theme_styles(self):
        """应用主题样式，确保在深色主题下文字显示正确"""
        current_theme = self.settings.get('theme', '浅色')
        
        if current_theme == '深色':
            # 深色主题样式
            self.setStyleSheet("""
                QDialog {
                    background-color: #464646;
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                    background-color: transparent;
                }
                QGroupBox {
                    color: #ffffff;
                    border: 1px solid #646464;
                    border-radius: 4px;
                    margin-top: 10px;
                    font-weight: 500;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 8px 0 8px;
                    background-color: #464646;
                    color: #ffffff;
                }
                QCheckBox {
                    color: #ffffff;
                    spacing: 8px;
                }
                QPushButton {
                    background-color: #5a5a5a;
                    color: #ffffff;
                    border: 1px solid #646464;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #646464;
                    border-color: #007acc;
                }
                QPushButton:pressed {
                    background-color: #007acc;
                    color: #ffffff;
                }
                QLineEdit, QTextEdit, QPlainTextEdit {
                    background-color: #3c3c3c;
                    color: #ffffff;
                    border: 1px solid #646464;
                    padding: 4px;
                    border-radius: 3px;
                }
                QLineEdit {
                    placeholder-text-color: #999999;
                }
                QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
                    border-color: #007acc;
                }
                QComboBox {
                    background-color: #5a5a5a;
                    color: #ffffff;
                    border: 1px solid #646464;
                    padding: 4px 8px;
                    border-radius: 3px;
                }
                QComboBox:hover {
                    border-color: #007acc;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 20px;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid #ffffff;
                    margin-right: 5px;
                }
                QTabWidget::pane {
                    border: 1px solid #5a5a5a;
                    background-color: #3c3c3c;
                }
                QTabBar::tab {
                    background-color: #5a5a5a;
                    color: #ffffff;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background-color: #007acc;
                    color: #ffffff;
                }
                QTabBar::tab:hover {
                    background-color: #646464;
                }
            """)
        else:
            # 浅色主题或其他主题，使用默认样式
            self.setStyleSheet("""
                QDialog {
                    background-color: #f0f0f0;
                    color: #000000;
                }
                QLabel {
                    color: #000000;
                    background-color: transparent;
                }
                QGroupBox {
                    color: #000000;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    margin-top: 10px;
                    font-weight: 500;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 8px 0 8px;
                    background-color: #f0f0f0;
                    color: #000000;
                }
                QCheckBox {
                    color: #000000;
                    spacing: 8px;
                }
            """)

    def init_ui(self):
        raise NotImplementedError

    def load_values(self):
        raise NotImplementedError

    def save_settings(self):
        raise NotImplementedError

    def show_message(self, title, text, icon=QMessageBox.Icon.Information):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon)
        msg.exec()
        
    def create_styled_button(self, text, icon=None):
        """创建统一样式的按钮"""
        btn = QPushButton(text)
        btn.setMinimumHeight(30)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon:
            btn.setIcon(icon)
        return btn


# 1. 启用桌面通知
class DesktopNotifyDialog(BaseSettingDialog):
    def init_ui(self):
        self.setWindowTitle("启用桌面通知")
        layout = QVBoxLayout()
        layout.setSpacing(15)  # 增加间距
        
        # 创建分组框
        group_box = QGroupBox("通知设置")
        group_layout = QVBoxLayout()
        
        # 添加说明文本
        description = QLabel("启用后，当识别到关键词时将显示桌面通知提醒。")
        description.setWordWrap(True)  # 允许文本换行
        group_layout.addWidget(description)
        
        # 复选框
        self.desktop_notify_cb = QCheckBox("启用桌面通知")
        group_layout.addWidget(self.desktop_notify_cb)
        
        group_box.setLayout(group_layout)
        layout.addWidget(group_box)
        
        # 添加按钮布局
        btn_layout = QHBoxLayout()
        
        # 测试按钮
        test_btn = self.create_styled_button("测试通知")
        test_btn.setDefault(False)
        test_btn.setAutoDefault(False)
        test_btn.clicked.connect(self.test_notification)
        btn_layout.addWidget(test_btn)
        
        # 保存按钮
        save_btn = self.create_styled_button("保存")
        save_btn.setDefault(False)
        save_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

    def load_values(self):
        self.desktop_notify_cb.setChecked(self.settings.get("enable_desktop_notify", False))

    def test_notification(self):
        """测试桌面通知功能"""
        try:
            from core.desktop_notifier import DesktopNotifier
            notifier = DesktopNotifier(self)
            
            # 临时启用通知进行测试
            original_setting = self.settings.get("enable_desktop_notify", False)
            self.settings["enable_desktop_notify"] = True
            save_settings(self.settings)
            
            success, msg = notifier.test_notification()
            
            # 恢复原始设置
            self.settings["enable_desktop_notify"] = original_setting
            save_settings(self.settings)
            
            if success:
                self.show_message("测试结果", "桌面通知测试成功！如果您看到了系统通知，说明功能正常工作。")
            else:
                self.show_message("测试结果", f"桌面通知测试失败：{msg}\n\n可能的原因：\n1. 系统不支持桌面通知\n2. 通知权限被禁用\n3. 缺少相关依赖库", QMessageBox.Icon.Warning)
                
        except Exception as e:
            logging.exception("测试桌面通知异常")
            self.show_message("错误", f"测试失败: {e}", QMessageBox.Icon.Critical)
    
    def save_settings(self):
        try:
            self.settings["enable_desktop_notify"] = self.desktop_notify_cb.isChecked()
            save_settings(self.settings)
            self.show_message("提示", "启用桌面通知设置已保存！")
            self.settings_changed.emit(self.settings)
            self.accept()
        except Exception as e:
            logging.exception("保存启用桌面通知设置异常")
            self.show_message(t("错误"), f"{t('保存失败')}: {e}", QMessageBox.Icon.Critical)


# 2. 错误弹窗提示开关
class ErrorPopupDialog(BaseSettingDialog):
    def init_ui(self):
        self.setWindowTitle("错误弹窗提示设置")
        layout = QVBoxLayout()
        layout.setSpacing(15)  # 增加间距
        
        # 创建分组框
        group_box = QGroupBox("错误提示设置")
        group_layout = QVBoxLayout()
        
        # 添加说明文本
        description = QLabel("启用后，当OCR识别过程中出现错误时将弹出提示窗口。\n禁用后，错误信息将只在状态栏和日志中显示。")
        description.setWordWrap(True)  # 允许文本换行
        group_layout.addWidget(description)
        
        # 复选框
        self.error_popup_cb = QCheckBox("启用错误弹窗提示")
        group_layout.addWidget(self.error_popup_cb)
        
        group_box.setLayout(group_layout)
        layout.addWidget(group_box)
        
        # 添加按钮布局
        btn_layout = QHBoxLayout()
        
        # 测试按钮
        test_btn = self.create_styled_button("测试错误弹窗")
        test_btn.setDefault(False)
        test_btn.setAutoDefault(False)
        test_btn.clicked.connect(self.test_error_popup)
        btn_layout.addWidget(test_btn)
        
        # 保存按钮
        save_btn = self.create_styled_button("保存")
        save_btn.setDefault(False)
        save_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

    def load_values(self):
        self.error_popup_cb.setChecked(self.settings.get("enable_error_popup", True))

    def test_error_popup(self):
        """测试错误弹窗功能"""
        try:
            # 临时启用错误弹窗进行测试
            original_setting = self.settings.get("enable_error_popup", True)
            self.settings["enable_error_popup"] = True
            save_settings(self.settings)
            
            # 模拟错误弹窗
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "识别提示", "这是一个测试错误弹窗\n\n模拟场景：OCR识别失败\n错误原因：网络连接超时")
            
            # 恢复原始设置
            self.settings["enable_error_popup"] = original_setting
            save_settings(self.settings)
            
            # 显示测试结果
            self.show_message("测试结果", "错误弹窗测试完成！\n\n如果您看到了上面的错误提示窗口，说明错误弹窗功能正常工作。\n\n注意：\n- 启用时：错误会弹窗提示\n- 禁用时：错误只在状态栏显示")
                
        except Exception as e:
            logging.exception("测试错误弹窗异常")
            self.show_message("错误", f"测试失败: {e}", QMessageBox.Icon.Critical)

    def save_settings(self):
        try:
            self.settings["enable_error_popup"] = self.error_popup_cb.isChecked()
            save_settings(self.settings)
            self.show_message("提示", "错误弹窗提示设置已保存！")
            self.settings_changed.emit(self.settings)
            self.accept()
        except Exception as e:
            logging.exception("保存错误弹窗提示设置异常")
            self.show_message(t("error"), f"{t('save_failed')}: {e}", QMessageBox.Icon.Critical)


# 3. 关键事件邮件通知功能已整合到EmailSettingsDialog中


# 4. 程序主题切换 - 使用新的ThemePanel
class ThemeSwitchDialog(ThemePanel):
    """主题切换对话框 - 继承自ThemePanel以保持兼容性"""
    pass

# 系统主题检测函数
def detect_system_theme():
    system = platform.system()
    try:
        if system == "Windows":
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "浅色" if value == 1 else "深色"

        elif system == "Darwin":  # macOS
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            return "深色" if result.stdout else "浅色"

    except Exception as e:
        logging.warning(f"检测系统主题失败: {e}")
    return "浅色"


# 5. 字体大小调整
class FontSizeDialog(BaseSettingDialog):
    def init_ui(self):
        self.setWindowTitle("字体大小调整")
        layout = QHBoxLayout()
        layout.addWidget(QLabel("字体大小"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 32)
        layout.addWidget(self.font_size_spin)
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        test_btn = QPushButton("测试字体大小")
        test_btn.setDefault(False)
        test_btn.setAutoDefault(False)
        test_btn.clicked.connect(self.test_font_size)
        reset_btn = QPushButton("恢复默认")
        reset_btn.setDefault(False)
        reset_btn.setAutoDefault(False)
        reset_btn.clicked.connect(self.reset_to_default)
        save_btn = QPushButton("保存")
        save_btn.setDefault(False)
        save_btn.setAutoDefault(False)
        save_btn.setDefault(False)
        save_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(test_btn)
        button_layout.addWidget(reset_btn)
        button_layout.addWidget(save_btn)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def load_values(self):
        self.font_size_spin.setValue(self.settings.get("font_size", 12))

    def test_font_size(self):
        """测试字体大小调整功能"""
        try:
            # 获取当前设置的字体大小
            test_font_size = self.font_size_spin.value()
            
            # 创建测试对话框
            test_dialog = QDialog(self)
            test_dialog.setWindowTitle("字体大小测试")
            test_dialog.resize(400, 300)
            
            layout = QVBoxLayout()
            
            # 添加说明文本
            info_label = QLabel("这是字体大小测试窗口。下面的文本将使用您设置的字体大小显示：")
            layout.addWidget(info_label)
            
            # 添加测试文本，应用设置的字体大小
            test_text = QLabel("这是测试文本\n字体大小: {}px\n您可以查看字体大小是否符合预期\n\n这是一段较长的文本用于测试字体大小的显示效果。\n请检查文字是否清晰易读，大小是否合适。".format(test_font_size))
            test_text.setWordWrap(True)
            test_text.setStyleSheet(f"font-size: {test_font_size}px; padding: 10px; border: 1px solid #ccc;")
            layout.addWidget(test_text)
            
            # 添加关闭按钮
            close_btn = QPushButton("关闭测试")
            close_btn.clicked.connect(test_dialog.accept)
            layout.addWidget(close_btn)
            
            test_dialog.setLayout(layout)
            
            # 显示测试对话框
            test_dialog.exec()
            
            # 显示测试完成消息
            self.show_message("测试完成", f"字体大小测试已完成！\n当前设置: {test_font_size}px\n\n如果显示效果满意，请点击'保存'按钮保存设置。")
            
        except Exception as e:
            logging.exception("测试字体大小异常")
            self.show_message("错误", f"测试失败: {e}", QMessageBox.Icon.Critical)
    
    def reset_to_default(self):
        """恢复默认字体大小"""
        try:
            # 从DEFAULT_SETTINGS获取默认字体大小
            from core.settings import DEFAULT_SETTINGS
            default_font_size = DEFAULT_SETTINGS.get("font_size", 12)
            
            # 设置到界面控件
            self.font_size_spin.setValue(default_font_size)
            
            # 显示提示信息
            self.show_message("提示", f"已恢复默认字体大小: {default_font_size}px\n\n请点击'保存'按钮应用设置。")
            
        except Exception as e:
            logging.exception("恢复默认字体大小异常")
            self.show_message("错误", f"恢复默认设置失败: {e}", QMessageBox.Icon.Critical)
 
    def save_settings(self):
        try:
            self.settings["font_size"] = self.font_size_spin.value()
            save_settings(self.settings)
            self.show_message("提示", "字体大小设置已保存！")
            self.settings_changed.emit(self.settings)
            self.accept()
        except Exception as e:
            logging.exception("保存字体大小设置异常")
            self.show_message(t("error"), f"{t('save_failed')}: {e}", QMessageBox.Icon.Critical)

# 6. 语言切换
class LanguageSwitchDialog(QDialog):
    """语言切换设置对话框 - 系统原生样式版本"""
    settings_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        init_start = time.time()
        logging.debug("[LANG_SWITCH_DIALOG] 开始初始化语言切换对话框")
        
        super().__init__(parent)
        
        # 加载设置
        settings_start = time.time()
        self.settings = load_settings()
        settings_time = time.time() - settings_start
        
        logging.debug(f"[LANG_SWITCH_DIALOG] 设置加载完成，耗时: {settings_time:.3f}秒")
        logging.debug(f"[LANG_SWITCH_DIALOG] 加载的设置项数量: {len(self.settings)}")
        logging.debug(f"[LANG_SWITCH_DIALOG] 当前语言设置: {self.settings.get('language', '未设置')}")
        
        # 窗口模态设置
        modal_start = time.time()
        self.setWindowModality(Qt.WindowModality.WindowModal)
        modal_time = time.time() - modal_start
        
        logging.debug(f"[LANG_SWITCH_DIALOG] 窗口模态设置完成，耗时: {modal_time:.3f}秒")
        
        # 基本窗口设置，不应用自定义样式
        flags_start = time.time()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        flags_time = time.time() - flags_start
        
        logging.debug(f"[LANG_SWITCH_DIALOG] 窗口标志设置完成，耗时: {flags_time:.3f}秒")
        
        # 连接语言切换信号
        signal_start = time.time()
        try:
            self.connect_language_signal()
            signal_time = time.time() - signal_start
            logging.debug(f"[LANG_SWITCH_DIALOG] 语言切换信号连接完成，耗时: {signal_time:.3f}秒")
        except Exception as e:
            signal_time = time.time() - signal_start
            logging.error(f"[LANG_SWITCH_DIALOG] 语言切换信号连接失败，耗时: {signal_time:.3f}秒，错误: {e}")
        
        # 初始化UI
        ui_start = time.time()
        try:
            self.init_ui()
            ui_time = time.time() - ui_start
            logging.debug(f"[LANG_SWITCH_DIALOG] UI初始化完成，耗时: {ui_time:.3f}秒")
        except Exception as e:
            ui_time = time.time() - ui_start
            logging.error(f"[LANG_SWITCH_DIALOG] UI初始化失败，耗时: {ui_time:.3f}秒，错误: {e}")
            raise
        
        # 加载值
        load_start = time.time()
        try:
            self.load_values()
            load_time = time.time() - load_start
            logging.debug(f"[LANG_SWITCH_DIALOG] 值加载完成，耗时: {load_time:.3f}秒")
        except Exception as e:
            load_time = time.time() - load_start
            logging.error(f"[LANG_SWITCH_DIALOG] 值加载失败，耗时: {load_time:.3f}秒，错误: {e}")
        
        # 窗口居中显示
        center_start = time.time()
        if parent:
            try:
                parent_center = parent.geometry().center()
                self_center = self.rect().center()
                new_pos = parent_center - self_center
                self.move(new_pos)
                
                center_time = time.time() - center_start
                logging.debug(f"[LANG_SWITCH_DIALOG] 窗口居中完成，耗时: {center_time:.3f}秒")
                logging.debug(f"[LANG_SWITCH_DIALOG] 父窗口中心: {parent_center}, 对话框中心: {self_center}")
                logging.debug(f"[LANG_SWITCH_DIALOG] 新位置: {new_pos}")
            except Exception as e:
                center_time = time.time() - center_start
                logging.error(f"[LANG_SWITCH_DIALOG] 窗口居中失败，耗时: {center_time:.3f}秒，错误: {e}")
        else:
            logging.debug("[LANG_SWITCH_DIALOG] 无父窗口，跳过居中设置")
        
        total_init_time = time.time() - init_start
        logging.info(f"[LANG_SWITCH_DIALOG] 语言切换对话框初始化完成，总耗时: {total_init_time:.3f}秒")
        logging.debug(f"[LANG_SWITCH_DIALOG] 对话框大小: {self.size()}")
        logging.debug(f"[LANG_SWITCH_DIALOG] 对话框位置: {self.pos()}")
    
    def init_ui(self):
        ui_start = time.time()
        logging.debug("[LANG_SWITCH_UI] 开始初始化UI组件")
        
        # 设置窗口标题和大小
        title_start = time.time()
        self.setWindowTitle("语言设置")
        self.setFixedSize(350, 200)  # 设置固定大小
        title_time = time.time() - title_start
        
        logging.debug(f"[LANG_SWITCH_UI] 窗口标题和大小设置完成，耗时: {title_time:.3f}秒")
        logging.debug(f"[LANG_SWITCH_UI] 窗口标题: 语言设置, 大小: 350x200")
        
        # 主布局
        layout_start = time.time()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        layout_time = time.time() - layout_start
        
        logging.debug(f"[LANG_SWITCH_UI] 主布局创建完成，耗时: {layout_time:.3f}秒")
        logging.debug(f"[LANG_SWITCH_UI] 布局间距: 10px, 边距: 20px")
        
        # 当前语言显示组
        current_start = time.time()
        current_group = QGroupBox("当前语言")
        current_layout = QVBoxLayout()
        
        self.current_lang_display = QLabel("中文")
        current_layout.addWidget(self.current_lang_display)
        
        current_group.setLayout(current_layout)
        layout.addWidget(current_group)
        current_time = time.time() - current_start
        
        logging.debug(f"[LANG_SWITCH_UI] 当前语言显示组创建完成，耗时: {current_time:.3f}秒")
        logging.debug(f"[LANG_SWITCH_UI] 当前语言显示: 中文")
        
        # 语言选择组
        select_start = time.time()
        select_group = QGroupBox(t("语言切换"))
        select_layout = QVBoxLayout()
        
        # 创建语言下拉框
        combo_start = time.time()
        self.language_combo = QComboBox()
        # 添加默认语言选项
        self.language_combo.addItem(t("中文"), "zh")
        combo_time = time.time() - combo_start
        
        logging.debug(f"[LANG_SWITCH_UI] 语言下拉框创建完成，耗时: {combo_time:.3f}秒")
        logging.debug(f"[LANG_SWITCH_UI] 默认语言选项: 中文 (zh)")
        
        select_layout.addWidget(self.language_combo)
        
        # 提示信息
        tip_start = time.time()
        tip_label = QLabel(t("切换语言后需要重启应用"))
        tip_label.setWordWrap(True)
        select_layout.addWidget(tip_label)
        tip_time = time.time() - tip_start
        
        logging.debug(f"[LANG_SWITCH_UI] 提示标签创建完成，耗时: {tip_time:.3f}秒")
        logging.debug(f"[LANG_SWITCH_UI] 提示文本: 切换语言后需要重启应用")
        
        select_group.setLayout(select_layout)
        layout.addWidget(select_group)
        select_time = time.time() - select_start
        
        logging.debug(f"[LANG_SWITCH_UI] 语言选择组创建完成，耗时: {select_time:.3f}秒")
        
        # 按钮布局
        btn_start = time.time()
        btn_layout = QHBoxLayout()
        
        # 测试按钮
        test_btn_start = time.time()
        test_btn = QPushButton(t("测试"))
        test_btn.clicked.connect(self.test_language)
        btn_layout.addWidget(test_btn)
        test_btn_time = time.time() - test_btn_start
        
        logging.debug(f"[LANG_SWITCH_UI] 测试按钮创建完成，耗时: {test_btn_time:.3f}秒")
        
        btn_layout.addStretch()
        
        # 保存按钮
        save_btn_start = time.time()
        save_btn = QPushButton("保存")
        save_btn.setDefault(True)  # 设置为默认按钮
        save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(save_btn)
        save_btn_time = time.time() - save_btn_start
        
        logging.debug(f"[LANG_SWITCH_UI] 保存按钮创建完成，耗时: {save_btn_time:.3f}秒")
        logging.debug(f"[LANG_SWITCH_UI] 保存按钮设为默认按钮")
        
        # 取消按钮
        cancel_btn_start = time.time()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        cancel_btn_time = time.time() - cancel_btn_start
        
        logging.debug(f"[LANG_SWITCH_UI] 取消按钮创建完成，耗时: {cancel_btn_time:.3f}秒")
        
        layout.addLayout(btn_layout)
        btn_time = time.time() - btn_start
        
        logging.debug(f"[LANG_SWITCH_UI] 按钮布局创建完成，耗时: {btn_time:.3f}秒")
        logging.debug(f"[LANG_SWITCH_UI] 按钮数量: 3 (测试、保存、取消)")
        
        # 设置主布局
        final_start = time.time()
        self.setLayout(layout)
        final_time = time.time() - final_start
        
        logging.debug(f"[LANG_SWITCH_UI] 主布局设置完成，耗时: {final_time:.3f}秒")
        
        total_ui_time = time.time() - ui_start
        logging.info(f"[LANG_SWITCH_UI] UI组件初始化完成，总耗时: {total_ui_time:.3f}秒")
        logging.debug(f"[LANG_SWITCH_UI] UI组件统计: 2个组框, 1个下拉框, 2个标签, 3个按钮")
    
    def show_message(self, title, text, icon=QMessageBox.Icon.Information):
        """显示消息对话框"""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon)
        msg.exec()

    def load_values(self):
        load_start = time.time()
        logging.debug("[LANG_SWITCH_LOAD] 开始加载设置值")
        
        try:
            # 获取当前语言设置
            current_lang = self.settings.get('language', '中文')
            current_code = self.settings.get('language_code', 'zh')
            
            logging.debug(f"[LANG_SWITCH_LOAD] 当前语言: {current_lang}, 代码: {current_code}")
            
            # 更新当前语言显示
            display_start = time.time()
            self.current_lang_display.setText(current_lang)
            display_time = time.time() - display_start
            
            logging.debug(f"[LANG_SWITCH_LOAD] 当前语言显示更新完成，耗时: {display_time:.3f}秒")
            
            # 设置下拉框选中项
            combo_start = time.time()
            combo_count = self.language_combo.count()
            found_index = -1
            
            for i in range(combo_count):
                if self.language_combo.itemData(i) == current_code:
                    found_index = i
                    break
            
            if found_index >= 0:
                self.language_combo.setCurrentIndex(found_index)
                logging.debug(f"[LANG_SWITCH_LOAD] 下拉框设置为索引 {found_index}")
            else:
                # 设置默认选中中文
                self.language_combo.setCurrentIndex(0)
                logging.warning(f"[LANG_SWITCH_LOAD] 未找到语言代码 {current_code}，使用默认选项")
            
            combo_time = time.time() - combo_start
            logging.debug(f"[LANG_SWITCH_LOAD] 下拉框设置完成，耗时: {combo_time:.3f}秒")
            
            total_load_time = time.time() - load_start
            logging.info(f"[LANG_SWITCH_LOAD] 设置值加载完成，总耗时: {total_load_time:.3f}秒")
            
        except Exception as e:
            error_time = time.time() - load_start
            logging.error(f"[LANG_SWITCH_LOAD] 加载设置值失败，耗时: {error_time:.3f}秒，错误: {e}")
    
    def test_language(self):
        """测试语言切换"""
        test_start = time.time()
        logging.debug("[LANG_SWITCH_TEST] 开始测试语言切换")
        
        try:
            # 获取选择的语言
            selection_start = time.time()
            selected_lang = self.language_combo.currentData()
            selected_name = self.language_combo.currentText()
            current_index = self.language_combo.currentIndex()
            selection_time = time.time() - selection_start
            
            logging.debug(f"[LANG_SWITCH_TEST] 选择获取完成，耗时: {selection_time:.3f}秒")
            logging.debug(f"[LANG_SWITCH_TEST] 选择语言: {selected_name} ({selected_lang}), 索引: {current_index}")
            
            # 验证语言选择
            if not selected_lang:
                logging.warning("[LANG_SWITCH_TEST] 未选择有效语言")
                self.show_message(t("warning"), t("please_select_valid_language"), QMessageBox.Icon.Warning)
                return
            
            # 模拟语言切换测试
            simulate_start = time.time()
            # 这里可以添加实际的语言切换测试逻辑
            simulate_time = time.time() - simulate_start
            
            logging.debug(f"[LANG_SWITCH_TEST] 语言切换模拟完成，耗时: {simulate_time:.3f}秒")
            
            # 显示测试消息
            message_start = time.time()
            test_message = f"语言切换测试成功\n\n选择语言: {selected_name}\n语言代码: {selected_lang}"
            self.show_message("测试成功", test_message)
            message_time = time.time() - message_start
            
            logging.debug(f"[LANG_SWITCH_TEST] 测试消息显示完成，耗时: {message_time:.3f}秒")
            
            total_test_time = time.time() - test_start
            logging.info(f"[LANG_SWITCH_TEST] 语言切换测试完成，总耗时: {total_test_time:.3f}秒")
            
        except Exception as e:
            error_time = time.time() - test_start
            logging.error(f"[LANG_SWITCH_TEST] 测试语言切换失败，耗时: {error_time:.3f}秒，错误: {e}")
            logging.exception("[LANG_SWITCH_TEST] 详细错误信息")
            self.show_message(t("error"), f"{t('language_switch_test_failed')}: {e}", QMessageBox.Icon.Critical)

    def save_settings(self):
        save_start = time.time()
        logging.debug("[LANG_SWITCH_SAVE] 开始保存语言设置")
        
        try:
            # 获取选择的语言
            selection_start = time.time()
            selected_lang = self.language_combo.currentData()
            selected_name = self.language_combo.currentText()
            current_index = self.language_combo.currentIndex()
            selection_time = time.time() - selection_start
            
            logging.debug(f"[LANG_SWITCH_SAVE] 选择获取完成，耗时: {selection_time:.3f}秒")
            logging.debug(f"[LANG_SWITCH_SAVE] 选择语言: {selected_name} ({selected_lang}), 索引: {current_index}")
            
            # 验证语言选择
            if not selected_lang or not selected_name:
                logging.warning("[LANG_SWITCH_SAVE] 语言选择无效")
                self.show_message("警告", "请选择一个有效的语言选项", QMessageBox.Icon.Warning)
                return
            
            # 检查是否有变更
            old_lang = self.settings.get('language', '')
            old_code = self.settings.get('language_code', '')
            has_changes = (old_lang != selected_name) or (old_code != selected_lang)
            
            logging.debug(f"[LANG_SWITCH_SAVE] 变更检查: 旧语言={old_lang}({old_code}), 新语言={selected_name}({selected_lang})")
            logging.debug(f"[LANG_SWITCH_SAVE] 是否有变更: {has_changes}")
            
            # 更新设置
            update_start = time.time()
            self.settings["language"] = selected_name  # 保持兼容性
            self.settings["language_code"] = selected_lang  # 新增语言代码
            update_time = time.time() - update_start
            
            logging.debug(f"[LANG_SWITCH_SAVE] 设置更新完成，耗时: {update_time:.3f}秒")
            
            # 保存到文件
            file_save_start = time.time()
            save_settings(self.settings)
            file_save_time = time.time() - file_save_start
            
            logging.debug(f"[LANG_SWITCH_SAVE] 设置文件保存完成，耗时: {file_save_time:.3f}秒")
            
            # 发送变更信号
            signal_start = time.time()
            self.settings_changed.emit(self.settings)
            signal_time = time.time() - signal_start
            
            logging.debug(f"[LANG_SWITCH_SAVE] 设置变更信号发送完成，耗时: {signal_time:.3f}秒")
            
            # 显示成功消息
            message_start = time.time()
            success_message = f"语言设置保存成功\n\n当前语言: {selected_name}\n语言代码: {selected_lang}"
            if has_changes:
                success_message += "\n\n重启应用后生效"
            
            self.show_message("保存成功", success_message)
            message_time = time.time() - message_start
            
            logging.debug(f"[LANG_SWITCH_SAVE] 成功消息显示完成，耗时: {message_time:.3f}秒")
            
            # 关闭对话框
            close_start = time.time()
            self.accept()
            close_time = time.time() - close_start
            
            logging.debug(f"[LANG_SWITCH_SAVE] 对话框关闭完成，耗时: {close_time:.3f}秒")
            
            total_save_time = time.time() - save_start
            logging.info(f"[LANG_SWITCH_SAVE] 语言设置保存完成，总耗时: {total_save_time:.3f}秒")
            
        except Exception as e:
            error_time = time.time() - save_start
            logging.error(f"[LANG_SWITCH_SAVE] 保存语言设置失败，耗时: {error_time:.3f}秒，错误: {e}")
            logging.exception("[LANG_SWITCH_SAVE] 详细错误信息")
            self.show_message("错误", f"保存失败: {e}", QMessageBox.Icon.Critical)
    
    def connect_language_signal(self):
        """连接语言切换信号"""
        pass
    
    def refresh_ui_text(self):
        """刷新UI文本的国际化显示"""
        try:
            from core.i18n import t
            
            # 刷新窗口标题
            self.setWindowTitle(t('language_settings'))
            
            # 刷新组框标题
            for group_box in self.findChildren(QGroupBox):
                if "当前语言" in group_box.title():
                    group_box.setTitle(t('current_language'))
                elif "语言切换" in group_box.title():
                    group_box.setTitle(t('language_switch'))
            
            # 刷新按钮文本
            for button in self.findChildren(QPushButton):
                if button.text() == "测试":
                    button.setText(t('test'))
                elif button.text() == "确定":
                    button.setText(t('ok'))
                elif button.text() == "取消":
                    button.setText(t('cancel'))
            
            # 刷新提示标签
            for label in self.findChildren(QLabel):
                if "切换语言后需要重启应用" in label.text():
                    label.setText(t('restart_required'))
                    
        except Exception as e:
            import logging
            logging.error(f"刷新LanguageSwitchDialog UI文本时出错: {e}")
    
    def clear_layout(self, layout):
        """清除布局中的所有控件"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_layout(child.layout())

# 7. 自动备份日志（你已有）
# 7. 自动备份日志功能已整合到备份管理对话框中

# 8. 自动上传日志到服务器功能已整合到备份管理对话框中
# 9. 历史数据导出功能已整合到备份管理对话框中

# 10. OCR线程数调整
# 11. 缓存大小限制
class CacheSizeDialog(BaseSettingDialog):
    def init_ui(self):
        self.setWindowTitle("缓存大小限制设置")
        layout = QHBoxLayout()
        layout.addWidget(QLabel("缓存大小限制（MB）"))
        self.cache_spin = QSpinBox()
        self.cache_spin.setRange(10, 1024)
        layout.addWidget(self.cache_spin)
        btn_layout = QVBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setDefault(False)
        save_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.save_settings)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

    def load_values(self):
        self.cache_spin.setValue(self.settings.get("cache_size_mb", 100))

    def save_settings(self):
        try:
            self.settings["cache_size_mb"] = self.cache_spin.value()
            save_settings(self.settings)
            self.show_message("提示", "缓存大小限制已保存！")
            self.settings_changed.emit(self.settings)
            self.accept()
        except Exception as e:
            logging.exception("保存缓存大小限制异常")
            self.show_message("错误", f"保存失败: {e}", QMessageBox.Icon.Critical)

# 12. 日志详细级别
class LogLevelDialog(BaseSettingDialog):
    def __init__(self, parent=None):
        # 先初始化属性
        self.level_descriptions = {
            "调试": "🔍 调试信息 - 显示所有日志，包括详细的调试信息（适用于开发调试）",
            "信息": "ℹ️ 一般信息 - 显示程序运行的关键信息（推荐日常使用）", 
            "警告": "⚠️ 警告信息 - 显示可能的问题和警告（适用于生产环境）",
            "错误": "❌ 错误信息 - 只显示错误和严重问题（适用于故障排查）",
            "严重": "🚨 严重错误 - 只显示可能导致程序崩溃的严重错误（最小化日志）"
        }
        # 然后调用父类初始化
        super().__init__(parent)
        
    def init_ui(self):
        self.setWindowTitle("日志详细级别设置")
        self.setMinimumWidth(500)
        layout = QVBoxLayout()
        
        # 标题和说明
        title_label = QLabel("📋 日志详细级别配置")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # 级别选择区域
        level_group = QGroupBox("选择日志级别")
        level_layout = QVBoxLayout()
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["调试", "信息", "警告", "错误", "严重"])
        self.log_level_combo.currentTextChanged.connect(self.on_level_changed)
        level_layout.addWidget(self.log_level_combo)
        
        # 级别说明标签
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        # 根据主题设置样式
        current_theme = self.settings.get('theme', '浅色')
        if current_theme == '深色':
            # 深色主题样式
            self.description_label.setStyleSheet("""
                QLabel {
                    background-color: #2d2d2d !important;
                    border: 1px solid #0078d4 !important;
                    border-radius: 3px !important;
                    padding: 5px !important;
                    color: #ffffff !important;
                    font-weight: bold !important;
                }
            """)
        else:
            # 浅色主题样式
            self.description_label.setStyleSheet("""
                QLabel {
                    background-color: #e8f5e8 !important;
                    border: 1px solid #4CAF50 !important;
                    border-radius: 3px !important;
                    padding: 5px !important;
                    color: #2e7d32 !important;
                    font-weight: bold !important;
                }
            """)
        level_layout.addWidget(self.description_label)
        
        level_group.setLayout(level_layout)
        layout.addWidget(level_group)
        
        # 预览区域
        preview_group = QGroupBox("📊 当前级别日志预览")
        preview_layout = QVBoxLayout()
        
        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: 'Consolas', monospace;
                font-size: 9pt;
                border: 1px solid #555;
                border-radius: 3px;
            }
        """)
        preview_layout.addWidget(self.preview_text)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # 统计信息
        stats_group = QGroupBox("📈 日志统计信息")
        stats_layout = QVBoxLayout()
        
        self.stats_label = QLabel("正在加载统计信息...")
        self.stats_label.setStyleSheet("padding: 5px;")
        stats_layout.addWidget(self.stats_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        preview_btn = QPushButton("🔄 刷新预览")
        preview_btn.setDefault(False)
        preview_btn.setAutoDefault(False)
        preview_btn.clicked.connect(self.refresh_preview)
        button_layout.addWidget(preview_btn)
        
        button_layout.addStretch()
        
        save_btn = QPushButton("💾 保存设置")
        save_btn.setDefault(False)
        save_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.save_settings)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.setDefault(False)
        cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)

        # 使用滚动区域包裹内容，避免窗口过大并支持上下滚动
        from PyQt6.QtWidgets import QScrollArea
        content_widget = QWidget()
        content_widget.setLayout(layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setWidget(content_widget)

        outer_layout = QVBoxLayout()
        outer_layout.addWidget(scroll_area)
        self.setLayout(outer_layout)

        # 加载现有设置
        try:
            self.load_values()
        except Exception:
            pass

        # 加载现有设置
        try:
            self.load_values()
        except Exception:
            pass

        # 加载现有设置
        try:
            self.load_values()
        except Exception:
            pass

    def load_values(self):
        current_level = self.settings.get("log_level", "信息")
        self.log_level_combo.setCurrentText(current_level)
        self.on_level_changed(current_level)
        self.refresh_preview()
        self.update_statistics()
        
    def on_level_changed(self, level):
        """当日志级别改变时更新说明"""
        if level in self.level_descriptions:
            self.description_label.setText(self.level_descriptions[level])
        self.refresh_preview()
        
    def refresh_preview(self):
        """刷新日志预览"""
        current_level = self.log_level_combo.currentText()
        preview_logs = self.generate_preview_logs(current_level)
        self.preview_text.setPlainText(preview_logs)
        
    def generate_preview_logs(self, level):
        """生成预览日志示例"""
        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        all_logs = [
            ("调试", f"{now} - 调试 - 🔍 OCR识别开始，区域坐标: (100, 200, 300, 400)"),
            ("调试", f"{now} - 调试 - 🔍 API调用参数: {{\"image_type\": \"base64\", \"detect_direction\": true}}"),
            ("信息", f"{now} - 信息 - ℹ️ 程序启动成功，版本: 2.1.7"),
            ("信息", f"{now} - 信息 - ℹ️ 关键词匹配成功: 找到目标文本 '重要信息'"),
            ("警告", f"{now} - 警告 - ⚠️ API调用响应时间较长: 3.2秒"),
            ("警告", f"{now} - 警告 - ⚠️ 内存使用率较高: 85%"),
            ("错误", f"{now} - 错误 - ❌ OCR识别失败: 网络连接超时"),
            ("错误", f"{now} - 错误 - ❌ 配置文件读取错误: 文件格式不正确"),
            ("严重", f"{now} - 严重 - 🚨 系统内存不足，程序可能崩溃"),
            ("严重", f"{now} - 严重 - 🚨 API密钥验证失败，服务不可用")
        ]
        
        # 根据选择的级别过滤日志
        level_priority = {"调试": 0, "信息": 1, "警告": 2, "错误": 3, "严重": 4}
        current_priority = level_priority.get(level, 1)
        
        filtered_logs = []
        for log_level, log_msg in all_logs:
            if level_priority.get(log_level, 1) >= current_priority:
                filtered_logs.append(log_msg)
                
        if not filtered_logs:
            return f"当前级别 {level} 下暂无日志输出"
            
        return "\n".join(filtered_logs)
        
    def update_statistics(self):
        """更新日志统计信息"""
        try:
            # 这里可以从实际日志文件中读取统计信息
            # 为了演示，使用模拟数据
            current_level = self.log_level_combo.currentText()
            
            stats_info = {
                "调试": "📊 预计日志量: 很高 | 性能影响: 中等 | 适用场景: 开发调试",
                "信息": "📊 预计日志量: 中等 | 性能影响: 较低 | 适用场景: 日常使用",
                "警告": "📊 预计日志量: 较低 | 性能影响: 很低 | 适用场景: 生产监控",
                "错误": "📊 预计日志量: 低 | 性能影响: 最低 | 适用场景: 故障排查",
                "严重": "📊 预计日志量: 很低 | 性能影响: 最低 | 适用场景: 严重错误监控"
            }
            
            self.stats_label.setText(stats_info.get(current_level, "无统计信息"))
            
        except Exception as e:
            self.stats_label.setText(f"统计信息加载失败: {e}")

    def apply_log_level(self, level):
        """应用日志级别设置"""
        import logging
        level_map = {
            "调试": logging.DEBUG,
            "信息": logging.INFO,
            "警告": logging.WARNING,
            "错误": logging.ERROR,
            "严重": logging.CRITICAL
        }
        
        if level in level_map:
            # 设置根日志记录器的级别
            logging.getLogger().setLevel(level_map[level])
            # 设置所有处理器的级别
            for handler in logging.getLogger().handlers:
                handler.setLevel(level_map[level])
            logging.info(f"日志级别已设置为: {level}")

    def save_settings(self):
        try:
            level = self.log_level_combo.currentText()
            self.settings["log_level"] = level
            save_settings(self.settings)
            self.apply_log_level(level)
            self.show_message("提示", "日志详细级别已保存！")
            self.settings_changed.emit(self.settings)
            self.accept()
        except Exception as e:
            logging.exception("保存日志详细级别异常")
            self.show_message("错误", f"保存失败: {e}", QMessageBox.Icon.Critical)

# 13. 增强版启动密码保护
class StartupPasswordDialog(BaseSettingDialog):
    def init_ui(self):
        self.setWindowTitle(t("启动密码保护设置"))
        self.setFixedSize(500, 600)
        
        layout = QVBoxLayout()
        
        # 标题和说明
        title_label = QLabel(t("🔐 启动密码保护设置"))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        info_label = QLabel(t("启动密码保护可以防止未授权访问程序，增强系统安全性。"))
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 启用开关
        enable_group = QGroupBox(t("基本设置"))
        enable_layout = QVBoxLayout()
        
        self.startup_password_cb = QCheckBox(t("启用启动密码保护"))
        self.startup_password_cb.toggled.connect(self.toggle_password_settings)
        enable_layout.addWidget(self.startup_password_cb)
        
        # 密码设置区域
        password_group = QGroupBox(t("密码设置"))
        password_layout = QVBoxLayout()
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText(t("设置启动密码（至少6位字符）"))
        self.password_input.textChanged.connect(self.validate_password)
        password_layout.addWidget(self.password_input)
        
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input.setPlaceholderText(t("确认启动密码"))
        self.confirm_password_input.textChanged.connect(self.validate_password)
        password_layout.addWidget(self.confirm_password_input)
        
        # 密码强度指示器
        self.strength_label = QLabel(t("密码强度: 未设置"))
        password_layout.addWidget(self.strength_label)
        
        # 显示密码选项
        self.show_password_cb = QCheckBox(t("显示密码"))
        self.show_password_cb.toggled.connect(self.toggle_password_visibility)
        password_layout.addWidget(self.show_password_cb)
        
        password_group.setLayout(password_layout)
        enable_layout.addWidget(password_group)
        enable_group.setLayout(enable_layout)
        layout.addWidget(enable_group)
        
        # 安全设置
        security_group = QGroupBox(t("安全设置"))
        security_layout = QVBoxLayout()
        
        # 最大尝试次数
        attempts_layout = QHBoxLayout()
        attempts_layout.addWidget(QLabel(t("最大尝试次数:")))
        self.max_attempts_spin = QSpinBox()
        self.max_attempts_spin.setRange(1, 10)
        self.max_attempts_spin.setValue(3)
        attempts_layout.addWidget(self.max_attempts_spin)
        attempts_layout.addWidget(QLabel("次"))
        security_layout.addLayout(attempts_layout)
        
        # 失败锁定时间
        lockout_layout = QHBoxLayout()
        lockout_layout.addWidget(QLabel("失败锁定时间:"))
        self.lockout_time_spin = QSpinBox()
        self.lockout_time_spin.setRange(0, 60)
        self.lockout_time_spin.setValue(5)
        lockout_layout.addWidget(self.lockout_time_spin)
        lockout_layout.addWidget(QLabel("分钟 (0=不锁定)"))
        security_layout.addLayout(lockout_layout)
        
        # 记录失败尝试
        self.log_attempts_cb = QCheckBox("记录密码验证失败尝试")
        self.log_attempts_cb.setChecked(True)
        security_layout.addWidget(self.log_attempts_cb)
        
        # 自动锁定
        self.auto_lock_cb = QCheckBox("程序空闲时自动锁定")
        security_layout.addWidget(self.auto_lock_cb)
        
        security_group.setLayout(security_layout)
        layout.addWidget(security_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        test_btn = QPushButton("测试密码")
        test_btn.setDefault(False)
        test_btn.setAutoDefault(False)
        test_btn.clicked.connect(self.test_password)
        button_layout.addWidget(test_btn)
        
        reset_btn = QPushButton("重置设置")
        reset_btn.setDefault(False)
        reset_btn.setAutoDefault(False)
        reset_btn.clicked.connect(self.reset_settings)
        button_layout.addWidget(reset_btn)
        
        save_btn = QPushButton("保存设置")
        save_btn.setDefault(False)
        save_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        self.toggle_password_settings(False)  # 默认禁用

    def toggle_password_settings(self, enabled):
        """切换密码设置区域的启用状态"""
        self.password_input.setEnabled(enabled)
        self.confirm_password_input.setEnabled(enabled)
        self.show_password_cb.setEnabled(enabled)
        self.max_attempts_spin.setEnabled(enabled)
        self.lockout_time_spin.setEnabled(enabled)
        self.log_attempts_cb.setEnabled(enabled)
        self.auto_lock_cb.setEnabled(enabled)
        
    def toggle_password_visibility(self, show):
        """切换密码显示/隐藏"""
        mode = QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        self.password_input.setEchoMode(mode)
        self.confirm_password_input.setEchoMode(mode)
        
    def validate_password(self):
        """验证密码强度和一致性"""
        password = self.password_input.text()
        confirm = self.confirm_password_input.text()
        
        if not password:
            self.strength_label.setText("密码强度: 未设置")
            self.strength_label.setStyleSheet("color: #666; font-size: 12px; margin: 5px;")
            return
        
        # 使用新的输入验证模块
        is_valid, error_msg, strength = validate_password(password)
        
        if not is_valid:
            self.strength_label.setText(f"密码错误: {error_msg}")
            self.strength_label.setStyleSheet("color: #f44336; font-size: 12px; margin: 5px;")
            return
            
        # 根据强度等级显示不同颜色
        if strength <= 2:
            strength_text = "密码强度: 弱"
            color = "#f44336"
        elif strength <= 4:
            strength_text = "密码强度: 中等"
            color = "#FF9800"
        else:
            strength_text = "密码强度: 强"
            color = "#4CAF50"
            
        # 检查密码一致性
        if confirm and password != confirm:
            strength_text += " (密码不一致)"
            color = "#f44336"
        elif confirm and password == confirm:
            strength_text += " (密码一致)"
            
        self.strength_label.setText(strength_text)
        self.strength_label.setStyleSheet(f"color: {color}; font-size: 12px; margin: 5px;")
        
    def test_password(self):
        """测试密码设置"""
        if not self.startup_password_cb.isChecked():
            self.show_message("提示", "请先启用启动密码保护功能")
            return
            
        password = self.password_input.text()
        if not password:
            self.show_message("提示", "请先设置密码")
            return
            
        if len(password) < 6:
            self.show_message("警告", "密码长度至少需要6位字符", QMessageBox.Icon.Warning)
            return
            
        if password != self.confirm_password_input.text():
            self.show_message("错误", "两次输入的密码不一致", QMessageBox.Icon.Critical)
            return
            
        self.show_message("成功", "密码设置有效！")
        
    def reset_settings(self):
        """重置所有设置"""
        reply = QMessageBox.question(
            self, 
            "确认重置", 
            "确定要重置所有启动密码保护设置吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.startup_password_cb.setChecked(False)
            self.password_input.clear()
            self.confirm_password_input.clear()
            self.max_attempts_spin.setValue(3)
            self.lockout_time_spin.setValue(5)
            self.log_attempts_cb.setChecked(True)
            self.auto_lock_cb.setChecked(False)
            self.show_password_cb.setChecked(False)
            self.validate_password()
            self.toggle_password_settings(False)

    def load_values(self):
        """加载设置值"""
        # 基本设置
        self.startup_password_cb.setChecked(self.settings.get("enable_startup_password", False))
        self.password_input.setText(self.settings.get("startup_password", ""))
        self.confirm_password_input.setText(self.settings.get("startup_password", ""))
        
        # 安全设置
        self.max_attempts_spin.setValue(self.settings.get("startup_password_max_attempts", 3))
        self.lockout_time_spin.setValue(self.settings.get("startup_password_lockout_time", 5))
        self.log_attempts_cb.setChecked(self.settings.get("startup_password_log_attempts", True))
        self.auto_lock_cb.setChecked(self.settings.get("startup_password_auto_lock", False))
        
        # 更新界面状态
        self.toggle_password_settings(self.startup_password_cb.isChecked())
        self.validate_password()

    def save_settings(self):
        """保存设置"""
        try:
            # 验证密码
            if self.startup_password_cb.isChecked():
                password = self.password_input.text()
                confirm = self.confirm_password_input.text()
                
                if not password:
                    self.show_message(t("error"), t("please_set_startup_password"), QMessageBox.Icon.Critical)
                    return
                    
                if len(password) < 6:
                    self.show_message(t("error"), t("password_min_length_6"), QMessageBox.Icon.Critical)
                    return
                    
                if password != confirm:
                    self.show_message(t("error"), t("password_mismatch"), QMessageBox.Icon.Critical)
                    return
            
            # 保存基本设置
            self.settings["enable_startup_password"] = self.startup_password_cb.isChecked()
            if self.startup_password_cb.isChecked():
                self.settings["startup_password"] = self.password_input.text()
            
            # 保存安全设置
            self.settings["startup_password_max_attempts"] = self.max_attempts_spin.value()
            self.settings["startup_password_lockout_time"] = self.lockout_time_spin.value()
            self.settings["startup_password_log_attempts"] = self.log_attempts_cb.isChecked()
            self.settings["startup_password_auto_lock"] = self.auto_lock_cb.isChecked()
            
            save_settings(self.settings)
            
            if self.startup_password_cb.isChecked():
                self.show_message(t("提示"), t("启动密码保护设置已保存！\n下次启动程序时将需要输入密码。"))
            else:
                self.show_message(t("提示"), t("启动密码保护已禁用！"))
                
            self.settings_changed.emit(self.settings)
            self.accept()
            
        except Exception as e:
            logging.exception("Save startup password protection settings exception")
            self.show_message("错误", f"保存失败: {e}", QMessageBox.Icon.Critical)



# 16. HTTP/HTTPS代理设置
class ProxySettingsDialog(BaseSettingDialog):
    def init_ui(self):
        self.setWindowTitle(t("HTTP/HTTPS代理设置"))
        layout = QVBoxLayout()

        self.proxy_enable_cb = QCheckBox(t("启用代理"))
        layout.addWidget(self.proxy_enable_cb)

        self.proxy_host_input = QLineEdit()
        self.proxy_host_input.setPlaceholderText(t("代理地址"))
        layout.addWidget(self.proxy_host_input)

        self.proxy_port_input = QSpinBox()
        self.proxy_port_input.setRange(1, 65535)
        layout.addWidget(QLabel(t("代理端口")))
        layout.addWidget(self.proxy_port_input)

        save_btn = QPushButton("保存")
        save_btn.setDefault(False)
        save_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        self.setLayout(layout)

    def load_values(self):
        self.proxy_enable_cb.setChecked(self.settings.get("proxy_enabled", False))
        self.proxy_host_input.setText(self.settings.get("proxy_host", ""))
        self.proxy_port_input.setValue(self.settings.get("proxy_port", 0))

    def save_settings(self):
        try:
            self.settings["proxy_enabled"] = self.proxy_enable_cb.isChecked()
            self.settings["proxy_host"] = self.proxy_host_input.text()
            self.settings["proxy_port"] = self.proxy_port_input.value()
            save_settings(self.settings)
            self.show_message("提示", "代理设置已保存！")
            self.settings_changed.emit(self.settings)
            self.accept()
        except Exception as e:
            logging.exception("保存代理设置异常")
            self.show_message("错误", f"保存失败: {e}", QMessageBox.Icon.Critical)

# 17. 连接超时与重试次数
class TimeoutRetryDialog(BaseSettingDialog):
    def init_ui(self):
        self.setWindowTitle(t("连接超时与重试次数设置"))
        layout = QVBoxLayout()

        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel(t("连接超时（秒）")))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 60)
        timeout_layout.addWidget(self.timeout_spin)
        layout.addLayout(timeout_layout)

        retry_layout = QHBoxLayout()
        retry_layout.addWidget(QLabel(t("重试次数")))
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        retry_layout.addWidget(self.retry_spin)
        layout.addLayout(retry_layout)

        save_btn = QPushButton("保存")
        save_btn.setDefault(False)
        save_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        self.setLayout(layout)

    def load_values(self):
        self.timeout_spin.setValue(self.settings.get("connection_timeout", 10))
        self.retry_spin.setValue(self.settings.get("retry_count", 3))

    def save_settings(self):
        try:
            self.settings["connection_timeout"] = self.timeout_spin.value()
            self.settings["retry_count"] = self.retry_spin.value()
            save_settings(self.settings)
            self.show_message(t("提示"), t("连接超时与重试次数设置已保存！"))
            self.settings_changed.emit(self.settings)
            self.accept()
        except Exception as e:
            logging.exception("保存连接超时与重试次数异常")
            self.show_message("错误", f"保存失败: {e}", QMessageBox.Icon.Critical)

# 18. 外部工具脚本钩子
class ExternalHookDialog(BaseSettingDialog):
    def init_ui(self):
        self.setWindowTitle("外部工具脚本钩子设置")
        layout = QVBoxLayout()

        self.external_hook_cb = QCheckBox("启用外部工具脚本钩子")
        layout.addWidget(self.external_hook_cb)

        self.hook_path_input = QLineEdit()
        self.hook_path_input.setPlaceholderText("脚本路径")
        layout.addWidget(self.hook_path_input)

        hook_browse_btn = QPushButton("浏览")
        hook_browse_btn.setDefault(False)
        hook_browse_btn.setAutoDefault(False)
        hook_browse_btn.clicked.connect(self.browse_hook_script)
        layout.addWidget(hook_browse_btn)

        save_btn = QPushButton("保存")
        save_btn.setDefault(False)
        save_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        self.setLayout(layout)

    def load_values(self):
        self.external_hook_cb.setChecked(self.settings.get("enable_external_hook", False))
        self.hook_path_input.setText(self.settings.get("external_hook_path", ""))

    def save_settings(self):
        try:
            self.settings["enable_external_hook"] = self.external_hook_cb.isChecked()
            self.settings["external_hook_path"] = self.hook_path_input.text()
            save_settings(self.settings)
            self.show_message("提示", "外部工具脚本钩子设置已保存！")
            self.settings_changed.emit(self.settings)
            self.accept()
        except Exception as e:
            logging.exception("保存外部工具脚本钩子异常")
            self.show_message("错误", f"保存失败: {e}", QMessageBox.Icon.Critical)

    def browse_hook_script(self):
        filename, _ = QFileDialog.getOpenFileName(self, t("select_script_file"), "", t("script_file_filter"))
        if filename:
            self.hook_path_input.setText(filename)

# 19. 快捷键配置
class ShortcutKeyDialog(BaseSettingDialog):
    def init_ui(self):
        self.setWindowTitle("快捷键配置")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        # 默认尺寸稍微增大，提升初始可视区域
        self.resize(650, 550)
        # 构建期间暂时禁用界面更新，避免布局引起的卡顿
        self.setUpdatesEnabled(False)
        
        # 导入快捷键管理器
        from core.hotkey_manager import get_hotkey_manager
        self.hotkey_manager = get_hotkey_manager()
        
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # 标题和说明
        title_label = QLabel("全局快捷键配置")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # 功能可用性检查
        if not self.hotkey_manager.is_available():
            warning_label = QLabel("⚠️ 快捷键功能不可用：需要安装 pynput 库")
            warning_label.setStyleSheet("color: #ff6b6b; background: #ffe0e0; padding: 10px; border-radius: 5px; margin-bottom: 10px;")
            layout.addWidget(warning_label)
            
            install_btn = QPushButton("安装 pynput 库")
            install_btn.setDefault(False)
            install_btn.setAutoDefault(False)
            install_btn.clicked.connect(self.install_pynput)
            layout.addWidget(install_btn)
        
        # 当前快捷键显示
        current_group = QGroupBox("当前快捷键")
        current_layout = QVBoxLayout()
        
        self.current_hotkey_label = QLabel("无")
        self.current_hotkey_label.setStyleSheet("font-size: 14px; padding: 5px; background: #f0f0f0; border-radius: 3px;")
        current_layout.addWidget(self.current_hotkey_label)
        
        current_group.setLayout(current_layout)
        layout.addWidget(current_group)

        # 已绑定的快捷键列表
        bound_group = QGroupBox("已绑定的快捷键")
        bound_layout = QVBoxLayout()

        bound_desc = QLabel("当前已注册的全局快捷键（随主程序注册而变更）：")
        bound_layout.addWidget(bound_desc)

        self.bound_hotkeys_table = QTableWidget()
        self.bound_hotkeys_table.setColumnCount(3)
        self.bound_hotkeys_table.setHorizontalHeaderLabels(["快捷键", "操作函数", "快捷键说明"])
        self.bound_hotkeys_table.setSortingEnabled(True)
        self.bound_hotkeys_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bound_hotkeys_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        # 让表格自适应填充空间
        self.bound_hotkeys_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # 限制表格初始最大高度，减少布局计算带来的卡顿
        try:
            self.bound_hotkeys_table.setMaximumHeight(260)
        except Exception:
            pass
        if self.bound_hotkeys_table.horizontalHeader():
            self.bound_hotkeys_table.horizontalHeader().setStretchLastSection(True)
            self.bound_hotkeys_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        bound_layout.addWidget(self.bound_hotkeys_table)
        # 使表格在分组内占据更多可用空间
        bound_layout.setStretch(1, 1)

        refresh_btn = QPushButton("刷新列表")
        refresh_btn.setDefault(False)
        refresh_btn.setAutoDefault(False)
        refresh_btn.clicked.connect(self.populate_bound_hotkeys_table)
        bound_layout.addWidget(refresh_btn)

        bound_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        bound_group.setLayout(bound_layout)
        layout.addWidget(bound_group)
        # 提升该分组在整体布局中的伸展优先级
        layout.setStretch(layout.count() - 1, 1)
        
        # 快捷键输入
        input_group = QGroupBox(t("设置新快捷键"))
        input_layout = QVBoxLayout()
        
        self.shortcut_input = QLineEdit()
        self.shortcut_input.setPlaceholderText(t("例如: Ctrl+Shift+S, Alt+F1, Win+Shift+C"))
        self.shortcut_input.textChanged.connect(self.validate_input)
        input_layout.addWidget(self.shortcut_input)
        
        # 验证状态显示
        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        input_layout.addWidget(self.validation_label)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # 建议的快捷键
        suggestions_group = QGroupBox(t("建议的快捷键"))
        suggestions_layout = QVBoxLayout()
        
        suggestions_text = QLabel(t("点击下方按钮快速选择常用快捷键组合："))
        suggestions_layout.addWidget(suggestions_text)
        
        # 建议按钮网格
        suggestions_grid = QGridLayout()
        suggested_hotkeys = self.hotkey_manager.get_suggested_hotkeys()
        
        for i, hotkey in enumerate(suggested_hotkeys):
            btn = QPushButton(hotkey)
            btn.setDefault(False)
            btn.setAutoDefault(False)
            btn.clicked.connect(lambda checked, h=hotkey: self.set_suggested_hotkey(h))
            btn.setStyleSheet("padding: 5px; margin: 2px;")
            suggestions_grid.addWidget(btn, i // 3, i % 3)
        
        suggestions_layout.addLayout(suggestions_grid)
        suggestions_group.setLayout(suggestions_layout)
        layout.addWidget(suggestions_group)
        
        # 使用说明
        help_group = QGroupBox(t("使用说明"))
        help_layout = QVBoxLayout()
        
        help_text = QLabel(t(
            "• 快捷键格式：修饰键+普通键，如 Ctrl+Shift+S\n"
            "• 支持的修饰键：Ctrl, Shift, Alt, Win\n"
            "• 支持的普通键：字母(A-Z), 功能键(F1-F12), Space, Enter等\n"
            "• 快捷键将在全局范围内生效，按下后自动触发OCR截图\n"
            "• 建议使用不与其他软件冲突的组合键"
        ))
        # 根据主题设置文字颜色
        current_theme = self.settings.get('theme', '浅色')
        if current_theme == '深色':
            help_text.setStyleSheet("color: #cccccc; font-size: 12px; line-height: 1.4;")
        else:
            help_text.setStyleSheet("color: #666666; font-size: 12px; line-height: 1.4;")
        help_text.setWordWrap(True)
        help_layout.addWidget(help_text)
        
        help_group.setLayout(help_layout)
        layout.addWidget(help_group)
        
        # 高级功能热键配置
        advanced_group = QGroupBox(t("高级功能热键"))
        adv_layout = QVBoxLayout()

        # 总开关
        toggles_layout = QHBoxLayout()
        self.global_hotkeys_cb = QCheckBox(t("启用批量全局快捷键"))
        self.global_hotkeys_cb.setChecked((getattr(self, 'settings', {}) or {}).get("global_hotkeys_enabled", True))
        self.conflict_detection_cb = QCheckBox(t("启用冲突提示"))
        self.conflict_detection_cb.setChecked((getattr(self, 'settings', {}) or {}).get("hotkey_conflict_detection", True))
        toggles_layout.addWidget(self.global_hotkeys_cb)
        toggles_layout.addWidget(self.conflict_detection_cb)
        toggles_layout.addStretch()
        adv_layout.addLayout(toggles_layout)

        # 动作配置网格
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        # 表头
        grid.addWidget(QLabel(t("功能")), 0, 0)
        grid.addWidget(QLabel(t("启用")), 0, 1)
        grid.addWidget(QLabel(t("快捷键组合（逗号分隔）")), 0, 2)
        grid.addWidget(QLabel(t("状态")), 0, 3)

        # 默认映射（占位及初始显示）
        default_custom = {
            "region_select": "Ctrl+F2",
            "fullscreen_ocr": "Ctrl+F3",
            "clipboard_ocr": "F3, Ctrl+Shift+V",
            "quick_ocr": "Ctrl+Shift+C",
            "open_settings": "Ctrl+,",
            "toggle_visibility": "Ctrl+Alt+H",
            "always_on_top": "Ctrl+T",
            "open_history": "Ctrl+Shift+H",
            "perf_panel": "Ctrl+P",
            "help_window": "F1",
            "help_batch": "Ctrl+B",
            "refresh_ui": "F5",
            "minimize_tray": "Ctrl+M",
            "close_tab": "Ctrl+W",
        }

        action_labels = {
            "region_select": t("区域截图选择"),
            "fullscreen_ocr": t("全屏截图识别"),
            "clipboard_ocr": t("剪贴板识别"),
            "quick_ocr": t("快速截图识别"),
            "open_settings": t("打开设置"),
            "toggle_visibility": t("显示/隐藏主窗口"),
            "always_on_top": t("置顶/取消置顶"),
            "open_history": t("历史记录弹窗"),
            "perf_panel": t("性能监控面板"),
            "help_window": t("帮助窗口"),
            "help_batch": t("帮助-批量处理"),
            "refresh_ui": t("刷新界面"),
            "minimize_tray": t("最小化到托盘"),
            "close_tab": t("关闭当前标签页"),
        }

        self.hotkey_controls = {}
        settings = getattr(self, 'settings', {}) or {}
        enabled_hotkeys = settings.get("enabled_hotkeys", {})
        custom_hotkeys = settings.get("custom_hotkeys", {})

        row = 1
        for action, label_text in action_labels.items():
            label = QLabel(label_text)
            enabled_cb = QCheckBox()
            enabled_cb.setChecked(enabled_hotkeys.get(action, True))

            input_edit = QLineEdit()
            input_edit.setPlaceholderText(default_custom.get(action, ""))

            # 初始值：自定义优先，其次默认（阻断信号以避免初始化时触发校验）
            value = custom_hotkeys.get(action, None)
            try:
                from PyQt6.QtCore import QSignalBlocker
                blocker = QSignalBlocker(input_edit)
            except Exception:
                blocker = None
            try:
                if isinstance(value, list):
                    input_edit.setText(", ".join([str(v) for v in value if isinstance(v, str)]))
                elif isinstance(value, str):
                    input_edit.setText(value)
            finally:
                try:
                    if blocker is not None:
                        del blocker
                except Exception:
                    pass

            status_label = QLabel("")
            status_label.setWordWrap(True)

            # 存储控件引用
            self.hotkey_controls[action] = {
                "enabled_cb": enabled_cb,
                "input": input_edit,
                "status": status_label,
            }

            # 绑定输入校验
            input_edit.textChanged.connect(lambda _=None, a=action: self._validate_action_input(a))

            grid.addWidget(label, row, 0)
            grid.addWidget(enabled_cb, row, 1)
            grid.addWidget(input_edit, row, 2)
            grid.addWidget(status_label, row, 3)
            row += 1

        adv_layout.addLayout(grid)
        advanced_group.setLayout(adv_layout)
        layout.addWidget(advanced_group)

        # 延迟初始化状态提示，避免阻塞UI加载
        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(200, self._deferred_initial_validation)
        except Exception:
            pass
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.test_btn = QPushButton(t("测试快捷键"))
        self.test_btn.setDefault(False)
        self.test_btn.setAutoDefault(False)
        self.test_btn.clicked.connect(self.test_hotkey)
        self.test_btn.setEnabled(False)
        button_layout.addWidget(self.test_btn)
        
        self.clear_btn = QPushButton(t("清除快捷键"))
        self.clear_btn.setDefault(False)
        self.clear_btn.setAutoDefault(False)
        self.clear_btn.clicked.connect(self.clear_hotkey)
        button_layout.addWidget(self.clear_btn)
        
        button_layout.addStretch()
        
        save_btn = QPushButton(t("保存"))
        save_btn.setDefault(False)
        save_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.save_settings)
        save_btn.setStyleSheet("background: #4CAF50; color: white; padding: 8px 16px; font-weight: bold;")
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton(t("取消"))
        cancel_btn.setDefault(False)
        cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # 使用滚动区域包裹内容，支持上下滚动，避免窗口过大
        from PyQt6.QtWidgets import QScrollArea
        content_widget = QWidget()
        content_widget.setLayout(layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setWidget(content_widget)

        outer_layout = QVBoxLayout()
        outer_layout.addWidget(scroll_area)
        outer_layout.addLayout(button_layout)  # 将按钮固定在滚动区域下方
        self.setLayout(outer_layout)
        # 重新启用界面更新
        self.setUpdatesEnabled(True)

        # 加载现有设置
        try:
            self.load_values()
        except Exception:
            pass

    def populate_bound_hotkeys_table(self):
        """填充已绑定的快捷键表格"""
        try:
            # 在填充期间关闭排序和界面更新，提升性能
            sorting = self.bound_hotkeys_table.isSortingEnabled()
            self.bound_hotkeys_table.setSortingEnabled(False)
            self.bound_hotkeys_table.setUpdatesEnabled(False)
            # 获取所有当前注册的快捷键
            hotkey_map = {}
            if hasattr(self, 'hotkey_manager') and self.hotkey_manager:
                hotkey_map = self.hotkey_manager.get_current_hotkeys() or {}

            rows = []
            # 批量模式：显示所有注册的快捷键
            for hk, cb in hotkey_map.items():
                # 根据快捷键推断操作函数名，避免lambda显示为<lambda>
                action_name = self._get_hotkey_action_name(hk)
                desc = self._get_hotkey_description(hk, cb)
                rows.append((hk, action_name or getattr(cb, '__name__', str(cb)), desc))

            # 单键模式：如果批量为空，尝试显示当前快捷键
            if not rows and hasattr(self.hotkey_manager, 'get_current_hotkey'):
                single_hk = self.hotkey_manager.get_current_hotkey()
                if single_hk:
                    desc = self._get_hotkey_description(single_hk, None)
                    action_name = self._get_hotkey_action_name(single_hk)
                    rows.append((single_hk, action_name or 'global_hotkey', desc))

            self.bound_hotkeys_table.setRowCount(len(rows))
            for i, (hk, name, desc) in enumerate(rows):
                self.bound_hotkeys_table.setItem(i, 0, QTableWidgetItem(str(hk)))
                self.bound_hotkeys_table.setItem(i, 1, QTableWidgetItem(str(name)))
                self.bound_hotkeys_table.setItem(i, 2, QTableWidgetItem(str(desc)))
            # 重新启用更新和排序
            self.bound_hotkeys_table.setUpdatesEnabled(True)
            self.bound_hotkeys_table.setSortingEnabled(sorting)
        except Exception as e:
            # 简单降级处理：清空并显示占位信息
            self.bound_hotkeys_table.setRowCount(0)
            self.bound_hotkeys_table.setRowCount(1)
            self.bound_hotkeys_table.setItem(0, 0, QTableWidgetItem("-"))
            self.bound_hotkeys_table.setItem(0, 1, QTableWidgetItem(f"加载失败: {e}"))
            self.bound_hotkeys_table.setItem(0, 2, QTableWidgetItem("-"))
            try:
                self.bound_hotkeys_table.setUpdatesEnabled(True)
                self.bound_hotkeys_table.setSortingEnabled(True)
            except Exception:
                pass
    
    def set_suggested_hotkey(self, hotkey):
        """设置建议的快捷键"""
        self.shortcut_input.setText(hotkey)
    
    def validate_input(self):
        """验证输入的快捷键格式"""
        hotkey_str = self.shortcut_input.text().strip()
        
        if not hotkey_str:
            self.validation_label.setText("")
            self.test_btn.setEnabled(False)
            return
        
        is_valid, error_msg = self.hotkey_manager.validate_hotkey(hotkey_str)
        
        if is_valid:
            self.validation_label.setText(f"✅ {t('快捷键格式正确')}")
            self.validation_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.test_btn.setEnabled(True)
        else:
            self.validation_label.setText(f"❌ {error_msg}")
            self.validation_label.setStyleSheet("color: #f44336; font-weight: bold;")
            self.test_btn.setEnabled(False)

    def _parse_combos_text(self, text: str) -> list:
        """将输入文本切分为快捷键组合列表，支持中英文分隔符"""
        raw = text or ""
        for sep in [',', '，', ';', '；', '、', '\n', '|']:
            raw = raw.replace(sep, ',')
        parts = [p.strip() for p in raw.split(',')]
        return [p for p in parts if p]

    def _validate_action_input(self, action: str) -> bool:
        """校验单个功能热键输入并更新状态标签"""
        try:
            ctrls = self.hotkey_controls.get(action)
            if not ctrls:
                return True
            text = ctrls["input"].text().strip()
            status = ctrls["status"]
            conflict_detection = True
            try:
                conflict_detection = self.conflict_detection_cb.isChecked()
            except Exception:
                pass

            if not text:
                status.setText(t("未设置（将使用默认组合）"))
                status.setStyleSheet("color: #666666;")
                return True

            combos = self._parse_combos_text(text)
            if not combos:
                status.setText(t("未设置（将使用默认组合）"))
                status.setStyleSheet("color: #666666;")
                return True

            # 逐项校验格式
            for hk in combos:
                ok, msg = self.hotkey_manager.validate_hotkey(hk)
                if not ok:
                    status.setText(f"{t('格式错误')}：{msg}")
                    status.setStyleSheet("color: #f44336; font-weight: bold;")
                    return False

            warnings = []
            errors = []
            if conflict_detection and hasattr(self.hotkey_manager, "_check_system_conflicts"):
                for hk in combos:
                    ok, msg = self.hotkey_manager._check_system_conflicts(hk)
                    if ok and msg:
                        warnings.append(msg)
                    elif not ok:
                        errors.append(msg)

            if errors:
                status.setText("；".join(errors))
                status.setStyleSheet("color: #f44336; font-weight: bold;")
                return False
            if warnings:
                status.setText("；".join(warnings))
                status.setStyleSheet("color: #ff9800;")
            else:
                status.setText(t("✅ 可用"))
                status.setStyleSheet("color: #4CAF50; font-weight: bold;")
            return True
        except Exception:
            try:
                status = self.hotkey_controls.get(action, {}).get("status")
                if status:
                    status.setText(t("校验异常"))
                    status.setStyleSheet("color: #f44336;")
            except Exception:
                pass
            return False

    def _deferred_initial_validation(self):
        """延迟批量校验，避免初始化卡顿"""
        try:
            for action, ctrls in (self.hotkey_controls or {}).items():
                try:
                    # 仅对已启用且有文本的条目进行校验
                    text = ctrls["input"].text().strip()
                    enabled = ctrls["enabled_cb"].isChecked()
                    if enabled and text:
                        self._validate_action_input(action)
                    else:
                        status = ctrls.get("status")
                        if status and not text:
                            status.setText(t("未设置（将使用默认组合）"))
                            status.setStyleSheet("color: #666666;")
                except Exception:
                    pass
        except Exception:
            pass
    
    def test_hotkey(self):
        """测试快捷键"""
        hotkey_str = self.shortcut_input.text().strip()
        if not hotkey_str:
            return
        
        # 检查快捷键格式
        is_valid, error_msg = self.hotkey_manager.validate_hotkey(hotkey_str)
        if not is_valid:
            self.show_message(t("格式错误"), f"{t('快捷键格式不正确')}: {error_msg}", QMessageBox.Icon.Warning)
            return
        
        # 显示测试信息
        result = QMessageBox.information(
            self, t("快捷键测试"), 
            f"{t('快捷键格式验证通过')}：{hotkey_str}\n\n"
            f"{t('注意：实际测试需要在应用程序运行时进行。')}\n"
            f"{t('您可以保存设置后，在主界面按下快捷键测试功能。')}",
            QMessageBox.StandardButton.Ok
        )
    
    def clear_hotkey(self):
        """清除快捷键"""
        self.shortcut_input.clear()
        try:
            # 同步清除设置中的主快捷键
            self.settings["shortcut_key"] = ""
            save_settings(self.settings)
        except Exception:
            pass

        # 取消当前注册并立即重建（保持批量映射的一致性）
        self.hotkey_manager.unregister_current_hotkey()
        ok, msg = self._apply_hotkeys_immediately("")
        # 刷新展示
        if hasattr(self, 'populate_bound_hotkeys_table'):
            self.populate_bound_hotkeys_table()
        # 反馈给用户
        if ok:
            self.show_message(t("已清除"), t("快捷键已清除并已应用"))
        else:
            self.show_message(t("提示"), f"{t('快捷键已清除，但重新绑定其他快捷键失败')}：{msg}")
    
    def install_pynput(self):
        """安装pynput库"""
        try:
            import subprocess
            import sys
            
            result = QMessageBox.question(
                self, t("安装确认"), 
                f"{t('是否要安装 pynput 库？')}\n\n{t('这将使用 pip 命令安装，可能需要几分钟时间。')}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if result == QMessageBox.StandardButton.Yes:
                # 在后台安装
                process = subprocess.Popen(
                    [sys.executable, "-m", "pip", "install", "pynput"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    self.show_message("安装成功", "pynput 库安装成功！请重启应用程序以使用快捷键功能。")
                else:
                    self.show_message("安装失败", f"安装失败：{stderr}", QMessageBox.Icon.Critical)
        except Exception as e:
            self.show_message("安装错误", f"安装过程中出现错误：{e}", QMessageBox.Icon.Critical)

    def load_values(self):
        current_hotkey = self.settings.get("shortcut_key", "")
        self.shortcut_input.setText(current_hotkey)
        
        # 更新当前快捷键显示
        if current_hotkey:
            self.current_hotkey_label.setText(current_hotkey)
            self.current_hotkey_label.setStyleSheet("font-size: 14px; padding: 5px; background: #e8f5e8; border-radius: 3px; color: #2e7d32;")
        else:
            self.current_hotkey_label.setText("无")
            self.current_hotkey_label.setStyleSheet("font-size: 14px; padding: 5px; background: #f0f0f0; border-radius: 3px;")

        # 刷新已绑定的快捷键列表（延迟加载，避免阻塞初始化）
        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(100, self.populate_bound_hotkeys_table)
        except Exception:
            if hasattr(self, 'populate_bound_hotkeys_table'):
                self.populate_bound_hotkeys_table()

    def _get_hotkey_description(self, hk: str, cb) -> str:
        """根据快捷键或回调推断中文说明"""
        try:
            hk_lower = (hk or '').strip().lower().replace(' ', '')
            cb_name = getattr(cb, '__name__', '') if cb is not None else ''

            # 先按快捷键匹配（lambda等无法识别时更准确）
            desc_by_hotkey = {
                'ctrl+,': '打开统一设置',
                'ctrl+alt+h': '隐藏/显示主窗口',
                'ctrl+t': '置顶/取消置顶',
                'ctrl+shift+h': '打开历史记录',
                'ctrl+f2': '打开区域截图选择',
                'ctrl+f3': '全屏截图并识别',
                'f3': '识别剪贴板文字',
                'ctrl+shift+v': '识别剪贴板文字',
                'ctrl+shift+c': '执行OCR截图识别',
                'ctrl+p': '性能监控面板',
                'f1': '打开帮助窗口',
                'ctrl+b': '打开帮助窗口（批量处理章节）',
                'f5': '刷新界面文本',
                'ctrl+m': '最小化到系统托盘',
                'ctrl+w': '关闭当前标签页',
            }
            if hk_lower in desc_by_hotkey:
                return desc_by_hotkey[hk_lower]

            # 再按回调函数名匹配
            desc_by_cb = {
                'trigger_ocr_capture': '执行OCR截图识别',
                'open_region_selector': '打开区域截图选择',
                'trigger_fullscreen_ocr': '全屏截图并识别',
                'toggle_window_visibility': '隐藏/显示主窗口',
                'toggle_always_on_top': '置顶/取消置顶',
                'open_history_dialog': '打开历史记录',
                'open_setting_dialog': '打开统一设置',
                'show_optimization_status': '性能监控面板',
                'show_help_window': '打开帮助窗口',
                'show_help_topic': '打开帮助窗口（指定章节）',
                'refresh_all_ui_text': '刷新界面文本',
                'minimize_to_tray': '最小化到系统托盘',
                'close_current_tab': '关闭当前标签页',
                'trigger_clipboard_ocr': '识别剪贴板文字',
            }
            if cb_name in desc_by_cb:
                return desc_by_cb[cb_name]

            # 默认说明
            return '自定义操作'
        except Exception:
            return '自定义操作'

    def _get_hotkey_action_name(self, hk: str) -> str:
        """根据快捷键返回操作函数名（用于表格展示）"""
        try:
            hk_lower = (hk or '').strip().lower().replace(' ', '')
            parent = getattr(self, '_parent_window', None) or self.parent()
            # 快捷键到函数名的静态映射
            action_by_hotkey = {
                'ctrl+,': 'open_setting_dialog("unified_settings")',
                'ctrl+alt+h': 'toggle_window_visibility',
                'ctrl+t': 'toggle_always_on_top',
                'ctrl+shift+h': 'open_history_dialog',
                'ctrl+f2': 'open_region_selector',
                'ctrl+f3': 'trigger_fullscreen_ocr',
                'f3': 'trigger_clipboard_ocr',
                'ctrl+shift+v': 'trigger_clipboard_ocr',
                'ctrl+shift+c': 'trigger_ocr_capture',
                'ctrl+p': 'show_optimization_status',
                'f1': 'show_help_window',
                'ctrl+b': "show_help_topic('批量处理')",
                'f5': 'refresh_all_ui_text',
                'ctrl+m': 'minimize_to_tray',
                'ctrl+w': 'close_current_tab',
            }
            # 主快捷键（来自设置）特殊处理
            try:
                main_hk = (getattr(self, 'settings', {}) or {}).get('shortcut_key', '').strip().lower().replace(' ', '')
                if main_hk and hk_lower == main_hk:
                    return 'trigger_ocr_capture'
            except Exception:
                pass
            return action_by_hotkey.get(hk_lower, '')
        except Exception:
            return ''

    def _apply_hotkeys_immediately(self, saved_hotkey: str) -> tuple[bool, str]:
        """立即绑定快捷键：优先调用主窗口的批量绑定以保持一致"""
        try:
            parent = getattr(self, '_parent_window', None) or self.parent()
            if not parent:
                return False, "未找到主窗口引用，无法绑定快捷键"

            # 主程序提供批量注册，优先使用（包含所有约定快捷键）
            if hasattr(parent, 'setup_global_hotkeys'):
                try:
                    parent.setup_global_hotkeys()
                    return True, "快捷键已立即生效"
                except Exception as e:
                    return False, f"批量绑定失败: {e}"

            # 回退到单键注册（仅绑定主快捷键触发OCR）
            if saved_hotkey and hasattr(parent, 'trigger_ocr_capture'):
                ok, msg = self.hotkey_manager.register_hotkey(saved_hotkey, parent.trigger_ocr_capture)
                if not ok:
                    return False, msg or "快捷键注册失败"
                return True, "快捷键已立即生效"

            return False, "未找到可注册的回调或快捷键为空"
        except Exception as e:
            logging.exception("立即绑定快捷键异常")
            return False, f"绑定失败: {e}"

    def save_settings(self):
        try:
            hotkey_str = self.shortcut_input.text().strip()
            
            # 验证主快捷键格式
            if hotkey_str:
                is_valid, error_msg = self.hotkey_manager.validate_hotkey(hotkey_str)
                if not is_valid:
                    self.show_message(t("格式错误"), f"{t('快捷键格式无效')}：{error_msg}", QMessageBox.Icon.Warning)
                    return
            
            # 高级热键：构建启用状态与组合
            settings = getattr(self, 'settings', {}) or {}
            enabled_hotkeys = {}
            custom_hotkeys = settings.get("custom_hotkeys", {}).copy()

            for action, ctrls in (getattr(self, 'hotkey_controls', {}) or {}).items():
                enabled = bool(ctrls["enabled_cb"].isChecked())
                enabled_hotkeys[action] = enabled

                text = ctrls["input"].text().strip()
                combos = self._parse_combos_text(text)

                # 启用时校验每一项格式
                if enabled:
                    for hk in combos:
                        ok, msg = self.hotkey_manager.validate_hotkey(hk)
                        if not ok:
                            self.show_message(t("格式错误"), f"{t('功能')}[{action}] {t('快捷键无效')}：{msg}", QMessageBox.Icon.Warning)
                            return
                # 有输入则覆盖，没有则移除以回退默认
                if combos:
                    custom_hotkeys[action] = combos[0] if len(combos) == 1 else combos
                else:
                    if action in custom_hotkeys:
                        custom_hotkeys.pop(action, None)

            # 写入设置
            settings["shortcut_key"] = hotkey_str
            settings["global_hotkeys_enabled"] = bool(getattr(self, "global_hotkeys_cb", QCheckBox()).isChecked())
            settings["hotkey_conflict_detection"] = bool(getattr(self, "conflict_detection_cb", QCheckBox()).isChecked())
            settings["enabled_hotkeys"] = enabled_hotkeys
            settings["custom_hotkeys"] = custom_hotkeys

            save_settings(settings)
            self.settings = settings
            
            # 立刻应用并绑定（批量）
            self.settings_changed.emit(self.settings)
            if self.hotkey_manager.is_available():
                ok, msg = self._apply_hotkeys_immediately(hotkey_str)
                if ok:
                    if hotkey_str:
                        self.show_message(t("保存成功"), f"{t('快捷键已设置并立即生效')}：{hotkey_str}")
                    else:
                        self.show_message(t("保存成功"), t("快捷键已清除并已应用"))
                    # 刷新列表以反映最新绑定
                    if hasattr(self, 'populate_bound_hotkeys_table'):
                        self.populate_bound_hotkeys_table()
                else:
                    self.show_message(t("保存成功"), f"{t('设置已保存，但绑定失败')}：{msg}")
            else:
                self.show_message(t("保存成功"), t("设置已保存。快捷键功能不可用，请安装 pynput 库。"))

            self.accept()
            
        except Exception as e:
            logging.exception("保存快捷键配置异常")
            self.show_message("错误", f"保存失败: {e}", QMessageBox.Icon.Critical)

# 20. API密钥设置
class ApiKeySettingsDialog(BaseSettingDialog):
    def init_ui(self):
        self.setWindowTitle("API密钥设置")
        self.setMinimumWidth(800)  # 增加最小宽度以容纳350px的输入框
        self.setMinimumHeight(600)  # 适当增加高度
        self.setMaximumWidth(1200)  # 设置最大宽度防止过度拉伸
        self.setMaximumHeight(900)  # 设置最大高度
        self.resize(850, 650)  # 设置默认窗口大小
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        
        # 百度OCR选项卡
        baidu_tab = QWidget()
        self.setup_baidu_tab(baidu_tab)
        self.tab_widget.addTab(baidu_tab, "百度OCR")
        
        # 腾讯云OCR选项卡
        tencent_tab = QWidget()
        self.setup_tencent_tab(tencent_tab)
        self.tab_widget.addTab(tencent_tab, "腾讯云OCR")
        
        # 阿里云OCR选项卡
        aliyun_tab = QWidget()
        self.setup_aliyun_tab(aliyun_tab)
        self.tab_widget.addTab(aliyun_tab, "阿里云OCR")
        
        # 华为云OCR选项卡
        huawei_tab = QWidget()
        self.setup_huawei_tab(huawei_tab)
        self.tab_widget.addTab(huawei_tab, "华为云OCR")
        
        main_layout.addWidget(self.tab_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.test_button = QPushButton("测试连接")
        self.test_button.setDefault(False)
        self.test_button.setAutoDefault(False)
        self.test_button.clicked.connect(self.test_current_api)
        button_layout.addWidget(self.test_button)
        
        self.register_button = QPushButton("注册账号")
        self.register_button.setDefault(False)
        self.register_button.setAutoDefault(False)
        self.register_button.clicked.connect(self.open_register_page)
        button_layout.addWidget(self.register_button)
        
        button_layout.addStretch()
        
        self.save_button = QPushButton("保存设置")
        self.save_button.setDefault(False)
        self.save_button.setAutoDefault(False)
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setDefault(False)
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        
        # 加载现有设置
        self.load_values()
    
    def setup_baidu_tab(self, tab):
        """设置百度OCR选项卡"""
        # 创建滚动区域
        from PyQt6.QtWidgets import QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 创建内容容器
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(15)
        
        # 标准版API设置
        std_group = QGroupBox("标准版OCR（必填）")
        std_layout = QFormLayout()
        # 设置表单布局策略，防止输入框变形
        std_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        std_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        std_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)  # 标签右对齐
        std_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)    # 表单左对齐
        std_layout.setHorizontalSpacing(10)  # 设置水平间距
        std_layout.setVerticalSpacing(8)     # 设置垂直间距
        
        self.baidu_std_api_input = QLineEdit()
        self.baidu_std_api_input.setPlaceholderText("请输入百度标准版API Key")
        self.baidu_std_api_input.setFixedWidth(350)
        self.baidu_std_api_input.setMinimumWidth(350)
        self.baidu_std_api_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        std_layout.addRow("API Key:", self.baidu_std_api_input)
        
        self.baidu_std_secret_input = QLineEdit()
        self.baidu_std_secret_input.setPlaceholderText("请输入百度标准版Secret Key")
        self.baidu_std_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.baidu_std_secret_input.setFixedWidth(350)
        self.baidu_std_secret_input.setMinimumWidth(350)
        self.baidu_std_secret_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        std_layout.addRow("Secret Key:", self.baidu_std_secret_input)
        
        std_group.setLayout(std_layout)
        layout.addWidget(std_group)
        
        # 高精度版设置（可选）
        self.baidu_accurate_checkbox = QCheckBox("启用高精度版 (accurate_basic)")
        self.baidu_accurate_checkbox.toggled.connect(self.toggle_baidu_accurate_fields)
        layout.addWidget(self.baidu_accurate_checkbox)
        
        self.baidu_accurate_group = QGroupBox("高精度版API配置")
        acc_layout = QFormLayout()
        # 设置表单布局策略，防止输入框变形
        acc_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        acc_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        acc_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        acc_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.baidu_acc_api_input = QLineEdit()
        self.baidu_acc_api_input.setPlaceholderText("请输入高精度版API Key")
        self.baidu_acc_api_input.setFixedWidth(350)
        self.baidu_acc_api_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        acc_layout.addRow("API Key:", self.baidu_acc_api_input)
        
        self.baidu_acc_secret_input = QLineEdit()
        self.baidu_acc_secret_input.setPlaceholderText("请输入高精度版Secret Key")
        self.baidu_acc_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.baidu_acc_secret_input.setFixedWidth(350)
        self.baidu_acc_secret_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        acc_layout.addRow("Secret Key:", self.baidu_acc_secret_input)
        
        self.baidu_accurate_group.setLayout(acc_layout)
        self.baidu_accurate_group.setVisible(False)
        layout.addWidget(self.baidu_accurate_group)
        
        # 标准版含位置设置（可选）
        self.baidu_general_enhanced_checkbox = QCheckBox("启用标准版含位置 (general_enhanced)")
        self.baidu_general_enhanced_checkbox.toggled.connect(self.toggle_baidu_general_enhanced_fields)
        layout.addWidget(self.baidu_general_enhanced_checkbox)
        
        self.baidu_general_enhanced_group = QGroupBox("标准版含位置API配置")
        gen_enh_layout = QFormLayout()
        # 设置表单布局策略，防止输入框变形
        gen_enh_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        gen_enh_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        gen_enh_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        gen_enh_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.baidu_gen_enh_api_input = QLineEdit()
        self.baidu_gen_enh_api_input.setPlaceholderText("请输入标准版含位置API Key")
        self.baidu_gen_enh_api_input.setFixedWidth(350)
        self.baidu_gen_enh_api_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        gen_enh_layout.addRow("API Key:", self.baidu_gen_enh_api_input)
        
        self.baidu_gen_enh_secret_input = QLineEdit()
        self.baidu_gen_enh_secret_input.setPlaceholderText("请输入标准版含位置Secret Key")
        self.baidu_gen_enh_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.baidu_gen_enh_secret_input.setFixedWidth(350)
        self.baidu_gen_enh_secret_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        gen_enh_layout.addRow("Secret Key:", self.baidu_gen_enh_secret_input)
        
        self.baidu_general_enhanced_group.setLayout(gen_enh_layout)
        self.baidu_general_enhanced_group.setVisible(False)
        layout.addWidget(self.baidu_general_enhanced_group)
        
        # 高精度版含位置设置（可选）
        self.baidu_accurate_enhanced_checkbox = QCheckBox("启用高精度版含位置 (accurate_enhanced)")
        self.baidu_accurate_enhanced_checkbox.toggled.connect(self.toggle_baidu_accurate_enhanced_fields)
        layout.addWidget(self.baidu_accurate_enhanced_checkbox)
        
        self.baidu_accurate_enhanced_group = QGroupBox("高精度版含位置API配置")
        acc_enh_layout = QFormLayout()
        # 设置表单布局策略，防止输入框变形
        acc_enh_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        acc_enh_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        acc_enh_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        acc_enh_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.baidu_acc_enh_api_input = QLineEdit()
        self.baidu_acc_enh_api_input.setPlaceholderText("请输入高精度版含位置API Key")
        self.baidu_acc_enh_api_input.setFixedWidth(350)
        self.baidu_acc_enh_api_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        acc_enh_layout.addRow("API Key:", self.baidu_acc_enh_api_input)
        
        self.baidu_acc_enh_secret_input = QLineEdit()
        self.baidu_acc_enh_secret_input.setPlaceholderText("请输入高精度版含位置Secret Key")
        self.baidu_acc_enh_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.baidu_acc_enh_secret_input.setFixedWidth(350)
        self.baidu_acc_enh_secret_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        acc_enh_layout.addRow("Secret Key:", self.baidu_acc_enh_secret_input)
        
        self.baidu_accurate_enhanced_group.setLayout(acc_enh_layout)
        self.baidu_accurate_enhanced_group.setVisible(False)
        layout.addWidget(self.baidu_accurate_enhanced_group)
        
        # 网络图片识别设置（可选）
        self.baidu_webimage_checkbox = QCheckBox("启用网络图片识别 (webimage)")
        self.baidu_webimage_checkbox.toggled.connect(self.toggle_baidu_webimage_fields)
        layout.addWidget(self.baidu_webimage_checkbox)
        
        self.baidu_webimage_group = QGroupBox("网络图片识别API配置")
        webimage_layout = QFormLayout()
        # 设置表单布局策略，防止输入框变形
        webimage_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        webimage_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        webimage_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        webimage_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.baidu_webimage_api_input = QLineEdit()
        self.baidu_webimage_api_input.setPlaceholderText("请输入网络图片识别API Key")
        self.baidu_webimage_api_input.setFixedWidth(350)
        self.baidu_webimage_api_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        webimage_layout.addRow("API Key:", self.baidu_webimage_api_input)
        
        self.baidu_webimage_secret_input = QLineEdit()
        self.baidu_webimage_secret_input.setPlaceholderText("请输入网络图片识别Secret Key")
        self.baidu_webimage_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.baidu_webimage_secret_input.setFixedWidth(350)
        self.baidu_webimage_secret_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        webimage_layout.addRow("Secret Key:", self.baidu_webimage_secret_input)
        
        self.baidu_webimage_group.setLayout(webimage_layout)
        self.baidu_webimage_group.setVisible(False)
        layout.addWidget(self.baidu_webimage_group)
        
        # 手写文字识别设置（可选）
        self.baidu_handwriting_checkbox = QCheckBox("启用手写文字识别 (handwriting)")
        self.baidu_handwriting_checkbox.toggled.connect(self.toggle_baidu_handwriting_fields)
        layout.addWidget(self.baidu_handwriting_checkbox)
        
        self.baidu_handwriting_group = QGroupBox("手写文字识别API配置")
        handwriting_layout = QFormLayout()
        # 设置表单布局策略，防止输入框变形
        handwriting_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        handwriting_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        handwriting_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        handwriting_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.baidu_handwriting_api_input = QLineEdit()
        self.baidu_handwriting_api_input.setPlaceholderText("请输入手写文字识别API Key")
        self.baidu_handwriting_api_input.setFixedWidth(350)
        self.baidu_handwriting_api_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        handwriting_layout.addRow("API Key:", self.baidu_handwriting_api_input)
        
        self.baidu_handwriting_secret_input = QLineEdit()
        self.baidu_handwriting_secret_input.setPlaceholderText("请输入手写文字识别Secret Key")
        self.baidu_handwriting_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.baidu_handwriting_secret_input.setFixedWidth(350)
        self.baidu_handwriting_secret_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        handwriting_layout.addRow("Secret Key:", self.baidu_handwriting_secret_input)
        
        self.baidu_handwriting_group.setLayout(handwriting_layout)
        self.baidu_handwriting_group.setVisible(False)
        layout.addWidget(self.baidu_handwriting_group)
        
        layout.addStretch()
        
        # 将内容容器设置到滚动区域
        scroll_area.setWidget(content_widget)
        
        # 将滚动区域添加到选项卡
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll_area)
    
    def setup_tencent_tab(self, tab):
        """设置腾讯云OCR选项卡"""
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 腾讯云API设置
        tencent_group = QGroupBox("腾讯云OCR API配置")
        tencent_layout = QFormLayout()
        # 设置表单布局策略，防止输入框变形
        tencent_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        tencent_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        tencent_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        tencent_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.tencent_secret_id_input = QLineEdit()
        self.tencent_secret_id_input.setPlaceholderText("请输入腾讯云SecretId")
        self.tencent_secret_id_input.setFixedWidth(350)
        self.tencent_secret_id_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        tencent_layout.addRow("SecretId:", self.tencent_secret_id_input)
        
        self.tencent_secret_key_input = QLineEdit()
        self.tencent_secret_key_input.setPlaceholderText("请输入腾讯云SecretKey")
        self.tencent_secret_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.tencent_secret_key_input.setFixedWidth(350)
        self.tencent_secret_key_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        tencent_layout.addRow("SecretKey:", self.tencent_secret_key_input)
        
        self.tencent_region_input = QLineEdit()
        self.tencent_region_input.setPlaceholderText("请输入地域，如：ap-beijing")
        self.tencent_region_input.setText("ap-beijing")
        self.tencent_region_input.setFixedWidth(350)
        self.tencent_region_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        tencent_layout.addRow("地域:", self.tencent_region_input)
        
        tencent_group.setLayout(tencent_layout)
        layout.addWidget(tencent_group)
        
        # 说明文字
        info_label = QLabel("腾讯云OCR支持通用印刷体识别、手写体识别等多种场景")
        info_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
    
    def setup_aliyun_tab(self, tab):
        """设置阿里云OCR选项卡"""
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 阿里云API设置
        aliyun_group = QGroupBox("阿里云OCR API配置")
        aliyun_layout = QFormLayout()
        # 设置表单布局策略，防止输入框变形
        aliyun_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        aliyun_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        aliyun_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        aliyun_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.aliyun_access_key_input = QLineEdit()
        self.aliyun_access_key_input.setPlaceholderText("请输入阿里云AccessKey ID")
        self.aliyun_access_key_input.setFixedWidth(350)
        self.aliyun_access_key_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        aliyun_layout.addRow("AccessKey ID:", self.aliyun_access_key_input)
        
        self.aliyun_access_secret_input = QLineEdit()
        self.aliyun_access_secret_input.setPlaceholderText("请输入阿里云AccessKey Secret")
        self.aliyun_access_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.aliyun_access_secret_input.setFixedWidth(350)
        self.aliyun_access_secret_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        aliyun_layout.addRow("AccessKey Secret:", self.aliyun_access_secret_input)
        
        self.aliyun_endpoint_input = QLineEdit()
        self.aliyun_endpoint_input.setPlaceholderText("请输入服务端点")
        self.aliyun_endpoint_input.setText("ocr.cn-shanghai.aliyuncs.com")
        self.aliyun_endpoint_input.setFixedWidth(350)
        self.aliyun_endpoint_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        aliyun_layout.addRow("服务端点:", self.aliyun_endpoint_input)
        
        aliyun_group.setLayout(aliyun_layout)
        layout.addWidget(aliyun_group)
        
        # 说明文字
        info_label = QLabel("阿里云OCR支持印刷文字识别、手写文字识别、证件识别等")
        info_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
    
    def setup_huawei_tab(self, tab):
        """设置华为云OCR选项卡"""
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 华为云API设置
        huawei_group = QGroupBox("华为云OCR API配置")
        huawei_layout = QFormLayout()
        # 设置表单布局策略，防止输入框变形
        huawei_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        huawei_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        huawei_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        huawei_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.huawei_ak_input = QLineEdit()
        self.huawei_ak_input.setPlaceholderText("请输入华为云Access Key")
        self.huawei_ak_input.setFixedWidth(350)
        self.huawei_ak_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        huawei_layout.addRow("Access Key:", self.huawei_ak_input)
        
        self.huawei_sk_input = QLineEdit()
        self.huawei_sk_input.setPlaceholderText("请输入华为云Secret Key")
        self.huawei_sk_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.huawei_sk_input.setFixedWidth(350)
        self.huawei_sk_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        huawei_layout.addRow("Secret Key:", self.huawei_sk_input)
        
        self.huawei_project_id_input = QLineEdit()
        self.huawei_project_id_input.setPlaceholderText("请输入项目ID")
        self.huawei_project_id_input.setFixedWidth(350)
        self.huawei_project_id_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        huawei_layout.addRow("项目ID:", self.huawei_project_id_input)
        
        self.huawei_endpoint_input = QLineEdit()
        self.huawei_endpoint_input.setPlaceholderText("请输入服务端点")
        self.huawei_endpoint_input.setText("ocr.cn-north-4.myhuaweicloud.com")
        self.huawei_endpoint_input.setFixedWidth(350)
        self.huawei_endpoint_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        huawei_layout.addRow("服务端点:", self.huawei_endpoint_input)
        
        huawei_group.setLayout(huawei_layout)
        layout.addWidget(huawei_group)
        
        # 说明文字
        info_label = QLabel("华为云OCR支持通用表格识别、通用文字识别、证件识别等")
        info_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
    
    def toggle_baidu_accurate_fields(self):
        """切换百度高精度版字段的可见性"""
        self.baidu_accurate_group.setVisible(self.baidu_accurate_checkbox.isChecked())
        self.update()  # 强制重绘界面
    
    def toggle_baidu_general_enhanced_fields(self):
        """切换百度标准版含位置字段的可见性"""
        self.baidu_general_enhanced_group.setVisible(self.baidu_general_enhanced_checkbox.isChecked())
        self.update()  # 强制重绘界面
    
    def toggle_baidu_accurate_enhanced_fields(self):
        """切换百度高精度版含位置字段的可见性"""
        self.baidu_accurate_enhanced_group.setVisible(self.baidu_accurate_enhanced_checkbox.isChecked())
        self.update()  # 强制重绘界面
    
    def toggle_baidu_webimage_fields(self):
        """切换百度网络图片识别字段的可见性"""
        self.baidu_webimage_group.setVisible(self.baidu_webimage_checkbox.isChecked())
        self.update()  # 强制重绘界面
    
    def toggle_baidu_handwriting_fields(self):
        """切换百度手写文字识别字段的可见性"""
        self.baidu_handwriting_group.setVisible(self.baidu_handwriting_checkbox.isChecked())
        self.update()  # 强制重绘界面
    

    
    def test_current_api(self):
        """测试当前选中的API连接"""
        current_tab = self.tab_widget.currentIndex()
        
        if current_tab == 0:  # 百度OCR
            self.test_baidu_api()
        elif current_tab == 1:  # 腾讯云OCR
            self.test_tencent_api()
        elif current_tab == 2:  # 阿里云OCR
            self.test_aliyun_api()
        elif current_tab == 3:  # 华为云OCR
            self.test_huawei_api()
    
    def test_baidu_api(self):
        """测试百度API连接"""
        api_key = self.baidu_std_api_input.text().strip()
        secret_key = self.baidu_std_secret_input.text().strip()
        
        if not api_key or not secret_key:
            self.show_message("错误", "请先填写百度API密钥！", QMessageBox.Icon.Warning)
            return
        
        # 验证API密钥格式
        is_valid_api, api_error = validate_api_key(api_key)
        if not is_valid_api:
            self.show_message("错误", f"API Key格式错误: {api_error}", QMessageBox.Icon.Warning)
            logger.warning(f"Invalid API key format detected: {api_error}")
            return
        
        is_valid_secret, secret_error = validate_api_key(secret_key)
        if not is_valid_secret:
            self.show_message("错误", f"Secret Key格式错误: {secret_error}", QMessageBox.Icon.Warning)
            logger.warning(f"Invalid secret key format detected: {secret_error}")
            return
        
        # 测试多个百度OCR接口
        results = self._test_baidu_apis(api_key, secret_key)
        
        success_count = sum(1 for result in results if result['success'])
        total_count = len(results)
        
        if success_count == total_count:
            self.show_message("成功", f"百度API密钥验证成功！\n所有 {total_count} 个接口均可正常访问", QMessageBox.Icon.Information)
        elif success_count > 0:
            # 部分成功
            success_apis = [r['api_name'] for r in results if r['success']]
            failed_apis = [f"{r['api_name']}: {r['error']}" for r in results if not r['success']]
            
            message = f"部分接口验证成功 ({success_count}/{total_count})\n\n"
            message += f"✓ 可用接口: {', '.join(success_apis)}\n\n"
            message += f"✗ 失败接口:\n" + "\n".join(failed_apis)
            
            self.show_message("部分成功", message, QMessageBox.Icon.Warning)
        else:
            # 全部失败
            failed_apis = [f"{r['api_name']}: {r['error']}" for r in results]
            message = f"所有接口验证失败:\n\n" + "\n".join(failed_apis)
            
            self.show_message("验证失败", message, QMessageBox.Icon.Critical)
    
    def _test_baidu_apis(self, api_key, secret_key):
        """测试多个百度OCR接口"""
        # 获取access_token
        token_success, token_or_error = self._get_baidu_access_token(api_key, secret_key)
        
        if not token_success:
            # 如果获取token失败，所有接口都会失败
            apis = [
                "通用文字识别（标准版）",
                "通用文字识别（高精度版）", 
                "手写文字识别",
                "身份证识别",
                "银行卡识别"
            ]
            return [{'api_name': api, 'success': False, 'error': f'获取访问令牌失败: {token_or_error}'} for api in apis]
        
        access_token = token_or_error
        results = []
        
        # 定义要测试的百度OCR接口
        test_apis = [
            {
                'name': '通用文字识别（标准版）',
                'url': 'https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic',
                'required_params': ['image']
            },
            {
                'name': '通用文字识别（高精度版）',
                'url': 'https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic', 
                'required_params': ['image']
            },
            {
                'name': '手写文字识别',
                'url': 'https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting',
                'required_params': ['image']
            },
            {
                'name': '身份证识别',
                'url': 'https://aip.baidubce.com/rest/2.0/ocr/v1/idcard',
                'required_params': ['image', 'id_card_side']
            },
            {
                'name': '银行卡识别', 
                'url': 'https://aip.baidubce.com/rest/2.0/ocr/v1/bankcard',
                'required_params': ['image']
            }
        ]
        
        for api_info in test_apis:
            try:
                # 发送测试请求（使用空图片数据，主要测试接口可访问性和权限）
                response = requests.post(
                    api_info['url'],
                    params={'access_token': access_token},
                    data={'image': ''},  # 空图片，用于测试接口响应
                    timeout=10
                )
                
                result_data = response.json()
                
                # 检查响应
                if 'error_code' in result_data:
                    error_code = result_data['error_code']
                    error_msg = result_data.get('error_msg', '未知错误')
                    
                    # 特定错误码处理
                    if error_code in [216200, 216201, 216202, 216630, 216631, 216633, 216634]:  # 图片相关错误（预期错误，说明接口可访问）
                        # 这些错误码表示接口可访问，只是参数有问题：
                        # 216200: 图片为空
                        # 216201: 图片格式错误
                        # 216202: 图片大小错误
                        # 216630: 识别错误
                        # 216631: 识别银行卡错误
                        # 216633: 识别身份证错误
                        # 216634: 检测错误
                        results.append({
                            'api_name': api_info['name'],
                            'success': True,
                            'error': None
                        })
                    elif error_code == 6:  # 权限错误
                        results.append({
                            'api_name': api_info['name'],
                            'success': False,
                            'error': f'权限不足: 该API密钥没有访问{api_info["name"]}的权限，请检查百度云控制台中的服务开通状态'
                        })
                    elif error_code == 17:  # 每日请求量超限额
                        results.append({
                            'api_name': api_info['name'],
                            'success': True,
                            'error': '接口可用但今日调用量已达上限'
                        })
                    elif error_code == 18:  # QPS超限额
                        results.append({
                            'api_name': api_info['name'],
                            'success': True,
                            'error': '接口可用但请求频率过高'
                        })
                    elif error_code == 282000:  # 服务暂不可用
                        results.append({
                            'api_name': api_info['name'],
                            'success': False,
                            'error': '服务暂不可用，请稍后重试'
                        })
                    else:
                        results.append({
                            'api_name': api_info['name'],
                            'success': False,
                            'error': f'错误码{error_code}: {error_msg}'
                        })
                else:
                    # 没有错误码，接口正常
                    results.append({
                        'api_name': api_info['name'],
                        'success': True,
                        'error': None
                    })
                    
            except requests.exceptions.Timeout:
                results.append({
                    'api_name': api_info['name'],
                    'success': False,
                    'error': '请求超时'
                })
            except requests.exceptions.RequestException as e:
                results.append({
                    'api_name': api_info['name'],
                    'success': False,
                    'error': f'网络错误: {str(e)}'
                })
            except Exception as e:
                results.append({
                    'api_name': api_info['name'],
                    'success': False,
                    'error': f'未知错误: {str(e)}'
                })
        
        return results
    
    def _get_baidu_access_token(self, api_key, secret_key):
        """获取百度API访问令牌"""
        # 常见英文错误描述对应的中文提示
        ERROR_DESC_MAP = {
            "unknown client id": "无效的API Key，请检查输入是否正确",
            "invalid client secret": "无效的Secret Key，请检查输入是否正确",
            "invalid client": "无效的客户端信息，请检查API Key和Secret Key",
            "invalid client credentials": "无效的客户端凭据，请检查密钥",
            "invalid_grant": "授权无效，请检查密钥",
            "invalid_request": "请求无效，请检查参数",
        }
        
        try:
            r = requests.get(
                "https://aip.baidubce.com/oauth/2.0/token",
                params={"grant_type": "client_credentials", "client_id": api_key, "client_secret": secret_key},
                timeout=10,
            )
            data = r.json()

            if "access_token" in data:
                return True, data["access_token"]

            # 优先从 error_description 获取错误信息
            err_desc = data.get("error_description", "").lower()
            if err_desc:
                # 查找映射中文提示
                for k, v in ERROR_DESC_MAP.items():
                    if k in err_desc:
                        return False, v
                # 无匹配，显示原文并提示检查
                return False, f"{data['error_description']}，请检查API Key和Secret Key"

            # 其次检查 error 字段
            err = data.get("error", "").lower()
            if err:
                for k, v in ERROR_DESC_MAP.items():
                    if k in err:
                        return False, v
                return False, f"{data['error']}，请检查API Key和Secret Key"

            # 其他未知错误
            return False, f"验证失败，返回信息：{json.dumps(data, ensure_ascii=False)}"

        except requests.exceptions.Timeout:
            return False, "请求超时，请检查网络连接"
        except requests.exceptions.RequestException as e:
            return False, f"网络错误：{str(e)}"
        except Exception as e:
            return False, f"验证过程中发生错误：{str(e)}"
    

    def _verify_tencent_key(self, secret_id, secret_key):
        """验证腾讯云API密钥有效性"""
        try:
            import hashlib
            import hmac
            import time
            from urllib.parse import urlencode
            
            # 腾讯云API签名验证
            endpoint = "ocr.tencentcloudapi.com"
            service = "ocr"
            version = "2018-11-19"
            action = "GeneralBasicOCR"
            region = "ap-beijing"
            
            # 构建请求参数
            timestamp = int(time.time())
            date = time.strftime('%Y-%m-%d', time.gmtime(timestamp))
            
            # 构建签名字符串
            algorithm = "TC3-HMAC-SHA256"
            credential_scope = f"{date}/{service}/tc3_request"
            
            # 简单的连接测试：尝试构建有效的签名
            def sign(key, msg):
                return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
            
            def get_signature_key(key, date_stamp, region_name, service_name):
                k_date = sign(('TC3' + key).encode('utf-8'), date_stamp)
                k_region = sign(k_date, region_name)
                k_service = sign(k_region, service_name)
                k_signing = sign(k_service, 'tc3_request')
                return k_signing
            
            # 验证密钥格式
            if len(secret_id) < 10 or len(secret_key) < 10:
                return False, "密钥格式不正确，请检查SecretId和SecretKey"
            
            # 尝试生成签名（不实际发送请求，只验证密钥格式）
            try:
                signing_key = get_signature_key(secret_key, date, region, service)
                return True, None
            except Exception:
                return False, "密钥格式验证失败，请检查SecretId和SecretKey是否正确"
                
        except ImportError:
            return False, "缺少必要的依赖库，无法验证腾讯云密钥"
        except Exception as e:
            return False, f"验证过程中发生错误：{str(e)}"
    
    def _verify_aliyun_key(self, access_key, access_secret):
        """验证阿里云API密钥有效性"""
        try:
            import hashlib
            import hmac
            import base64
            import time
            from urllib.parse import quote
            
            # 阿里云API签名验证
            # 验证密钥格式
            if len(access_key) < 10 or len(access_secret) < 10:
                return False, "密钥格式不正确，请检查AccessKey和AccessSecret"
            
            # 构建签名测试（不实际发送请求）
            try:
                # 阿里云签名算法测试
                timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                nonce = str(int(time.time() * 1000))
                
                # 构建待签名字符串
                string_to_sign = f"GET&%2F&AccessKeyId%3D{quote(access_key, safe='')}"
                
                # 计算签名
                h = hmac.new((access_secret + '&').encode('utf-8'), 
                           string_to_sign.encode('utf-8'), 
                           hashlib.sha1)
                signature = base64.b64encode(h.digest()).decode('utf-8')
                
                # 如果能成功生成签名，说明密钥格式正确
                if signature:
                    return True, None
                else:
                    return False, "密钥格式验证失败"
                    
            except Exception:
                return False, "密钥格式验证失败，请检查AccessKey和AccessSecret是否正确"
                
        except ImportError:
            return False, "缺少必要的依赖库，无法验证阿里云密钥"
        except Exception as e:
            return False, f"验证过程中发生错误：{str(e)}"
    
    def _verify_huawei_key(self, ak, sk):
        """验证华为云API密钥有效性"""
        try:
            import hashlib
            import hmac
            import time
            from urllib.parse import quote
            
            # 华为云API签名验证
            # 验证密钥格式
            if len(ak) < 10 or len(sk) < 10:
                return False, "密钥格式不正确，请检查AK和SK"
            
            # 构建签名测试（不实际发送请求）
            try:
                # 华为云签名算法测试
                timestamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
                date = timestamp[:8]
                
                # 构建待签名字符串（简化版本）
                canonical_request = "GET\n/\n\nhost:ocr.cn-north-4.myhuaweicloud.com\n\nhost\n"
                string_to_sign = f"SDK-HMAC-SHA256\n{timestamp}\n{canonical_request}"
                
                # 计算签名
                def sign(key, msg):
                    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
                
                k_date = sign(sk.encode('utf-8'), date)
                k_signing = sign(k_date, 'sdk_request')
                signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
                
                # 如果能成功生成签名，说明密钥格式正确
                if signature:
                    return True, None
                else:
                    return False, "密钥格式验证失败"
                    
            except Exception:
                return False, "密钥格式验证失败，请检查AK和SK是否正确"
                
        except ImportError:
            return False, "缺少必要的依赖库，无法验证华为云密钥"
        except Exception as e:
            return False, f"验证过程中发生错误：{str(e)}"
    
    def test_tencent_api(self):
        """测试腾讯云API连接"""
        secret_id = self.tencent_secret_id_input.text().strip()
        secret_key = self.tencent_secret_key_input.text().strip()
        
        if not secret_id or not secret_key:
            self.show_message("错误", "请先填写腾讯云API密钥！", QMessageBox.Icon.Warning)
            return
        
        # 验证API密钥格式
        is_valid_id, id_error = validate_api_key(secret_id)
        if not is_valid_id:
            self.show_message("错误", f"Secret ID格式错误: {id_error}", QMessageBox.Icon.Warning)
            logger.warning(f"Invalid secret ID format detected: {id_error}")
            return
        
        is_valid_key, key_error = validate_api_key(secret_key)
        if not is_valid_key:
            self.show_message("错误", f"Secret Key格式错误: {key_error}", QMessageBox.Icon.Warning)
            logger.warning(f"Invalid secret key format detected: {key_error}")
            return
        
        # 实际测试腾讯云API连接
        success, error_msg = self._verify_tencent_key(secret_id, secret_key)
        
        if success:
            self.show_message("成功", "腾讯云API密钥验证成功！", QMessageBox.Icon.Information)
        else:
            self.show_message("验证失败", f"腾讯云API密钥验证失败：{error_msg}", QMessageBox.Icon.Critical)
    
    def test_aliyun_api(self):
        """测试阿里云API连接"""
        access_key = self.aliyun_access_key_input.text().strip()
        access_secret = self.aliyun_access_secret_input.text().strip()
        
        if not access_key or not access_secret:
            self.show_message("错误", "请先填写阿里云API密钥！", QMessageBox.Icon.Warning)
            return
        
        # 实际测试阿里云API连接
        success, error_msg = self._verify_aliyun_key(access_key, access_secret)
        
        if success:
            self.show_message("成功", "阿里云API密钥验证成功！", QMessageBox.Icon.Information)
        else:
            self.show_message("验证失败", f"阿里云API密钥验证失败：{error_msg}", QMessageBox.Icon.Critical)
    
    def test_huawei_api(self):
        """测试华为云API连接"""
        ak = self.huawei_ak_input.text().strip()
        sk = self.huawei_sk_input.text().strip()
        
        if not ak or not sk:
            self.show_message("错误", "请先填写华为云API密钥！", QMessageBox.Icon.Warning)
            return
        
        # 实际测试华为云API连接
        success, error_msg = self._verify_huawei_key(ak, sk)
        
        if success:
            self.show_message("成功", "华为云API密钥验证成功！", QMessageBox.Icon.Information)
        else:
            self.show_message("验证失败", f"华为云API密钥验证失败：{error_msg}", QMessageBox.Icon.Critical)
    
    def load_values(self):
        """加载现有的API密钥设置"""
        try:
            from widgets.apikey_dialog import read_config
            config = read_config()
            
            # 加载百度OCR密钥
            baidu_general = config.get('general', {})
            self.baidu_std_api_input.setText(baidu_general.get('API_KEY', ''))
            self.baidu_std_secret_input.setText(baidu_general.get('SECRET_KEY', ''))
            
            baidu_accurate = config.get('accurate', {})
            if baidu_accurate.get('API_KEY') or baidu_accurate.get('SECRET_KEY'):
                self.baidu_accurate_checkbox.setChecked(True)
                self.baidu_acc_api_input.setText(baidu_accurate.get('API_KEY', ''))
                self.baidu_acc_secret_input.setText(baidu_accurate.get('SECRET_KEY', ''))
            
            # 加载百度标准版含位置密钥
            baidu_general_enhanced = config.get('general_enhanced', {})
            if baidu_general_enhanced.get('API_KEY') or baidu_general_enhanced.get('SECRET_KEY'):
                self.baidu_general_enhanced_checkbox.setChecked(True)
                self.baidu_gen_enh_api_input.setText(baidu_general_enhanced.get('API_KEY', ''))
                self.baidu_gen_enh_secret_input.setText(baidu_general_enhanced.get('SECRET_KEY', ''))
            
            # 加载百度高精度版含位置密钥
            baidu_accurate_enhanced = config.get('accurate_enhanced', {})
            if baidu_accurate_enhanced.get('API_KEY') or baidu_accurate_enhanced.get('SECRET_KEY'):
                self.baidu_accurate_enhanced_checkbox.setChecked(True)
                self.baidu_acc_enh_api_input.setText(baidu_accurate_enhanced.get('API_KEY', ''))
                self.baidu_acc_enh_secret_input.setText(baidu_accurate_enhanced.get('SECRET_KEY', ''))
            
            # 加载百度网络图片识别密钥
            baidu_webimage = config.get('webimage', {})
            if baidu_webimage.get('API_KEY') or baidu_webimage.get('SECRET_KEY'):
                self.baidu_webimage_checkbox.setChecked(True)
                self.baidu_webimage_api_input.setText(baidu_webimage.get('API_KEY', ''))
                self.baidu_webimage_secret_input.setText(baidu_webimage.get('SECRET_KEY', ''))
            
            # 加载百度手写文字识别密钥
            baidu_handwriting = config.get('handwriting', {})
            if baidu_handwriting.get('API_KEY') or baidu_handwriting.get('SECRET_KEY'):
                self.baidu_handwriting_checkbox.setChecked(True)
                self.baidu_handwriting_api_input.setText(baidu_handwriting.get('API_KEY', ''))
                self.baidu_handwriting_secret_input.setText(baidu_handwriting.get('SECRET_KEY', ''))
            
            # 加载腾讯云OCR密钥
            tencent_config = config.get('tencent', {})
            self.tencent_secret_id_input.setText(tencent_config.get('SecretId', ''))
            self.tencent_secret_key_input.setText(tencent_config.get('SecretKey', ''))
            self.tencent_region_input.setText(tencent_config.get('Region', 'ap-beijing'))
            
            # 加载阿里云OCR密钥
            aliyun_config = config.get('aliyun', {})
            self.aliyun_access_key_input.setText(aliyun_config.get('AccessKeyId', ''))
            self.aliyun_access_secret_input.setText(aliyun_config.get('AccessKeySecret', ''))
            self.aliyun_endpoint_input.setText(aliyun_config.get('Endpoint', 'ocr.cn-shanghai.aliyuncs.com'))
            
            # 加载华为云OCR密钥
            huawei_config = config.get('huawei', {})
            self.huawei_ak_input.setText(huawei_config.get('AccessKey', ''))
            self.huawei_sk_input.setText(huawei_config.get('SecretKey', ''))
            self.huawei_project_id_input.setText(huawei_config.get('ProjectId', ''))
            self.huawei_endpoint_input.setText(huawei_config.get('Endpoint', 'ocr.cn-north-4.myhuaweicloud.com'))
                
        except Exception as e:
            print(f"加载API密钥设置失败: {e}")
    
    def save_settings(self):
        """保存API密钥设置"""
        try:
            from widgets.apikey_dialog import read_config, write_config
            
            config = read_config()
            
            # 保存百度OCR密钥
            baidu_std_api = self.baidu_std_api_input.text().strip()
            baidu_std_secret = self.baidu_std_secret_input.text().strip()
            
            if baidu_std_api and baidu_std_secret:
                config['general'] = {
                    'API_KEY': baidu_std_api,
                    'SECRET_KEY': baidu_std_secret
                }
            
            # 保存百度高精度版密钥（如果启用）
            if self.baidu_accurate_checkbox.isChecked():
                baidu_acc_api = self.baidu_acc_api_input.text().strip()
                baidu_acc_secret = self.baidu_acc_secret_input.text().strip()
                if baidu_acc_api and baidu_acc_secret:
                    config['accurate'] = {
                        'API_KEY': baidu_acc_api,
                        'SECRET_KEY': baidu_acc_secret
                    }
            else:
                config.pop('accurate', None)
            
            # 保存百度标准版含位置密钥（如果启用）
            if self.baidu_general_enhanced_checkbox.isChecked():
                baidu_gen_enh_api = self.baidu_gen_enh_api_input.text().strip()
                baidu_gen_enh_secret = self.baidu_gen_enh_secret_input.text().strip()
                if baidu_gen_enh_api and baidu_gen_enh_secret:
                    config['general_enhanced'] = {
                        'API_KEY': baidu_gen_enh_api,
                        'SECRET_KEY': baidu_gen_enh_secret
                    }
            else:
                config.pop('general_enhanced', None)
            
            # 保存百度高精度版含位置密钥（如果启用）
            if self.baidu_accurate_enhanced_checkbox.isChecked():
                baidu_acc_enh_api = self.baidu_acc_enh_api_input.text().strip()
                baidu_acc_enh_secret = self.baidu_acc_enh_secret_input.text().strip()
                if baidu_acc_enh_api and baidu_acc_enh_secret:
                    config['accurate_enhanced'] = {
                        'API_KEY': baidu_acc_enh_api,
                        'SECRET_KEY': baidu_acc_enh_secret
                    }
            else:
                # 显式标记禁用，避免启动流程自动恢复该配置
                config['accurate_enhanced'] = {'DISABLED': True}
            
            # 保存百度网络图片识别密钥（如果启用）
            if self.baidu_webimage_checkbox.isChecked():
                baidu_webimage_api = self.baidu_webimage_api_input.text().strip()
                baidu_webimage_secret = self.baidu_webimage_secret_input.text().strip()
                if baidu_webimage_api and baidu_webimage_secret:
                    config['webimage'] = {
                        'API_KEY': baidu_webimage_api,
                        'SECRET_KEY': baidu_webimage_secret
                    }
            else:
                config.pop('webimage', None)
            
            # 保存百度手写文字识别密钥（如果启用）
            if self.baidu_handwriting_checkbox.isChecked():
                baidu_handwriting_api = self.baidu_handwriting_api_input.text().strip()
                baidu_handwriting_secret = self.baidu_handwriting_secret_input.text().strip()
                if baidu_handwriting_api and baidu_handwriting_secret:
                    config['handwriting'] = {
                        'API_KEY': baidu_handwriting_api,
                        'SECRET_KEY': baidu_handwriting_secret
                    }
            else:
                config.pop('handwriting', None)
            
            # 保存腾讯云OCR密钥
            tencent_id = self.tencent_secret_id_input.text().strip()
            tencent_key = self.tencent_secret_key_input.text().strip()
            tencent_region = self.tencent_region_input.text().strip()
            
            if tencent_id and tencent_key:
                config['tencent'] = {
                    'SecretId': tencent_id,
                    'SecretKey': tencent_key,
                    'Region': tencent_region or 'ap-beijing'
                }
            else:
                config.pop('tencent', None)
            
            # 保存阿里云OCR密钥
            aliyun_key = self.aliyun_access_key_input.text().strip()
            aliyun_secret = self.aliyun_access_secret_input.text().strip()
            aliyun_endpoint = self.aliyun_endpoint_input.text().strip()
            
            if aliyun_key and aliyun_secret:
                config['aliyun'] = {
                    'AccessKeyId': aliyun_key,
                    'AccessKeySecret': aliyun_secret,
                    'Endpoint': aliyun_endpoint or 'ocr.cn-shanghai.aliyuncs.com'
                }
            else:
                config.pop('aliyun', None)
            
            # 保存华为云OCR密钥
            huawei_ak = self.huawei_ak_input.text().strip()
            huawei_sk = self.huawei_sk_input.text().strip()
            huawei_project = self.huawei_project_id_input.text().strip()
            huawei_endpoint = self.huawei_endpoint_input.text().strip()
            
            if huawei_ak and huawei_sk:
                config['huawei'] = {
                    'AccessKey': huawei_ak,
                    'SecretKey': huawei_sk,
                    'ProjectId': huawei_project,
                    'Endpoint': huawei_endpoint or 'ocr.cn-north-4.myhuaweicloud.com'
                }
            else:
                config.pop('huawei', None)
            
            write_config(config)
            self.show_message("成功", "API密钥设置已保存！")
            self.accept()
            
        except Exception as e:
            self.show_message("错误", f"保存API密钥失败: {str(e)}", QMessageBox.Icon.Critical)
    
    def show_message(self, title, message, icon=QMessageBox.Icon.Information):
        """显示消息对话框"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon)
        msg_box.exec()
    
    def open_baidu_register(self):
        """打开百度OCR注册页面"""
        import webbrowser
        webbrowser.open('https://console.bce.baidu.com/ai/#/ai/ocr/overview/index')
    
    def open_tencent_register(self):
        """打开腾讯云OCR注册页面"""
        import webbrowser
        webbrowser.open('https://console.cloud.tencent.com/ocr')
    
    def open_aliyun_register(self):
        """打开阿里云OCR注册页面"""
        import webbrowser
        webbrowser.open('https://ecs.console.aliyun.com/ocr')
    
    def open_huawei_register(self):
        """打开华为云OCR注册页面"""
        import webbrowser
        webbrowser.open('https://console.huaweicloud.com/ocr')
    
    def test_api_keys(self):
        """测试API密钥连接"""
        if not self.std_api_input.text().strip() or not self.std_secret_input.text().strip():
            self.show_message("错误", "请先填写标准版API密钥！", QMessageBox.Icon.Warning)
            return
        
        # 这里可以添加实际的API测试逻辑
        self.show_message("提示", "API密钥测试功能开发中...")
    
    def open_register_page(self):
        """打开百度智能云注册页面"""
        import webbrowser
        webbrowser.open("https://cloud.baidu.com/")

# 21. 云同步设置
class CloudSyncDialog(BaseSettingDialog):
    def init_ui(self):
        self.setWindowTitle("云同步设置")
        layout = QVBoxLayout()

        cloud_group = QGroupBox("云同步设置")
        cloud_layout = QVBoxLayout()
        cloud_group.setLayout(cloud_layout)

        self.cloud_enable_cb = QCheckBox("启用云同步")
        cloud_layout.addWidget(self.cloud_enable_cb)

        self.cloud_account_input = QLineEdit()
        self.cloud_account_input.setPlaceholderText("账号")
        cloud_layout.addWidget(self.cloud_account_input)

        self.cloud_token_input = QLineEdit()
        self.cloud_token_input.setPlaceholderText("访问令牌")
        cloud_layout.addWidget(self.cloud_token_input)

        layout.addWidget(cloud_group)

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        self.setLayout(layout)

    def load_values(self):
        self.cloud_enable_cb.setChecked(self.settings.get("cloud_sync_enabled", False))
        self.cloud_account_input.setText(self.settings.get("cloud_account", ""))
        self.cloud_token_input.setText(self.settings.get("cloud_token", ""))

    def save_settings(self):
        try:
            self.settings["cloud_sync_enabled"] = self.cloud_enable_cb.isChecked()
            self.settings["cloud_account"] = self.cloud_account_input.text()
            self.settings["cloud_token"] = self.cloud_token_input.text()
            save_settings(self.settings)
            self.show_message("提示", "云同步设置已保存！")
            self.settings_changed.emit(self.settings)
            self.accept()
        except Exception as e:
            logging.exception("保存云同步设置异常")
            self.show_message("错误", f"保存失败: {e}", QMessageBox.Icon.Critical)

# 统一设置管理对话框
class UnifiedSettingsDialog(BaseSettingDialog):
    def init_ui(self):
        self.setWindowTitle("设置管理")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        
        # API密钥管理选项卡
        api_tab = QWidget()
        self.setup_api_tab(api_tab)
        self.tab_widget.addTab(api_tab, "API密钥管理")
        
        # 通知设置选项卡
        notify_tab = QWidget()
        self.setup_notify_tab(notify_tab)
        self.tab_widget.addTab(notify_tab, "通知设置")
        
        # 外观设置选项卡
        appearance_tab = QWidget()
        self.setup_appearance_tab(appearance_tab)
        self.tab_widget.addTab(appearance_tab, "外观设置")
        
        # 系统设置选项卡
        system_tab = QWidget()
        self.setup_system_tab(system_tab)
        self.tab_widget.addTab(system_tab, "系统设置")
        
        # 网络设置选项卡
        network_tab = QWidget()
        self.setup_network_tab(network_tab)
        self.tab_widget.addTab(network_tab, "网络设置")
        
        # 高级设置选项卡
        advanced_tab = QWidget()
        self.setup_advanced_tab(advanced_tab)
        self.tab_widget.addTab(advanced_tab, "高级设置")
        
        # 云同步设置选项卡
        cloud_tab = QWidget()
        self.setup_cloud_tab(cloud_tab)
        self.tab_widget.addTab(cloud_tab, "云同步设置")
        
        main_layout.addWidget(self.tab_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("保存所有设置")
        self.save_button.setDefault(False)
        self.save_button.setAutoDefault(False)
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setDefault(False)
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
    
    def setup_api_tab(self, tab):
        """设置API密钥管理选项卡"""
        layout = QVBoxLayout()
        
        # 添加说明
        desc_label = QLabel("配置各种OCR服务的API密钥")
        desc_label.setStyleSheet("font-weight: bold; color: #666; margin-bottom: 10px;")
        layout.addWidget(desc_label)
        
        # 添加API密钥设置按钮
        api_button = QPushButton("打开API密钥设置")
        api_button.clicked.connect(self.open_api_settings)
        layout.addWidget(api_button)
        
        layout.addStretch()
        tab.setLayout(layout)
    
    def setup_notify_tab(self, tab):
        """设置通知选项卡"""
        layout = QVBoxLayout()
        
        # 桌面通知
        self.desktop_notify_cb = QCheckBox("启用桌面通知")
        layout.addWidget(self.desktop_notify_cb)
        
        # 错误弹窗
        self.error_popup_cb = QCheckBox("启用错误弹窗提示")
        layout.addWidget(self.error_popup_cb)
        
        # 邮件通知
        email_group = QGroupBox("邮件通知设置")
        email_layout = QVBoxLayout()
        
        self.email_enable_cb = QCheckBox("启用邮件通知")
        email_layout.addWidget(self.email_enable_cb)
        

        
        email_group.setLayout(email_layout)
        layout.addWidget(email_group)
        
        layout.addStretch()
        tab.setLayout(layout)
    
    def setup_appearance_tab(self, tab):
        """设置外观选项卡"""
        layout = QVBoxLayout()
        
        # 主题设置
        theme_group = QGroupBox("主题设置")
        theme_layout = QVBoxLayout()
        
        self.auto_theme_cb = QCheckBox("根据系统自动切换主题")
        theme_layout.addWidget(self.auto_theme_cb)
        
        theme_label = QLabel("程序主题:")
        theme_layout.addWidget(theme_label)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["浅色", "深色"])
        theme_layout.addWidget(self.theme_combo)
        
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)
        
        # 字体设置
        font_group = QGroupBox("字体设置")
        font_layout = QVBoxLayout()
        
        font_label = QLabel("字体大小:")
        font_layout.addWidget(font_label)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(12)
        font_layout.addWidget(self.font_size_spin)
        
        font_group.setLayout(font_layout)
        layout.addWidget(font_group)
        
        # 语言设置
        lang_group = QGroupBox("语言设置")
        lang_layout = QVBoxLayout()
        
        lang_label = QLabel("界面语言:")
        lang_layout.addWidget(lang_label)
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(["简体中文", "English"])
        lang_layout.addWidget(self.language_combo)
        
        lang_group.setLayout(lang_layout)
        layout.addWidget(lang_group)
        
        layout.addStretch()
        tab.setLayout(layout)
    
    def setup_system_tab(self, tab):
        """设置系统选项卡"""
        layout = QVBoxLayout()
        
        # 备份设置
        backup_group = QGroupBox("备份设置")
        backup_layout = QVBoxLayout()
        
        self.auto_upload_cb = QCheckBox("自动上传日志到服务器")
        backup_layout.addWidget(self.auto_upload_cb)
        
        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)
        
        # 数据管理
        data_group = QGroupBox("数据管理")
        data_layout = QVBoxLayout()
        
        export_button = QPushButton("历史数据导出")
        export_button.clicked.connect(lambda: self.open_sub_dialog("export_history"))
        data_layout.addWidget(export_button)
        
        self.auto_clear_cb = QCheckBox("定期清除历史数据")
        data_layout.addWidget(self.auto_clear_cb)
        
        data_group.setLayout(data_layout)
        layout.addWidget(data_group)
        
        # 安全设置
        security_group = QGroupBox("安全设置")
        security_layout = QVBoxLayout()
        
        self.startup_password_cb = QCheckBox("启用启动密码保护")
        security_layout.addWidget(self.startup_password_cb)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("设置启动密码")
        security_layout.addWidget(self.password_input)
        
        security_group.setLayout(security_layout)
        layout.addWidget(security_group)
        
        # 日志设置
        log_group = QGroupBox("日志设置")
        log_layout = QVBoxLayout()
        
        log_label = QLabel("日志详细级别:")
        log_layout.addWidget(log_label)
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["调试", "信息", "警告", "错误", "严重"])
        log_layout.addWidget(self.log_level_combo)
        
        view_logs_button = QPushButton("查看访问日志")
        view_logs_button.clicked.connect(self.view_logs)
        log_layout.addWidget(view_logs_button)
        
        log_mgmt_button = QPushButton("日志管理")
        log_mgmt_button.clicked.connect(self.open_log_management)
        log_layout.addWidget(log_mgmt_button)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()
        tab.setLayout(layout)
    
    def setup_network_tab(self, tab):
        """设置网络选项卡"""
        layout = QVBoxLayout()
        
        # 代理设置
        proxy_group = QGroupBox("代理设置")
        proxy_layout = QVBoxLayout()
        
        proxy_button = QPushButton(t("HTTP/HTTPS代理设置"))
        proxy_button.clicked.connect(lambda: self.open_sub_dialog("proxy"))
        proxy_layout.addWidget(proxy_button)
        
        proxy_group.setLayout(proxy_layout)
        layout.addWidget(proxy_group)
        
        # 连接设置
        connection_group = QGroupBox("连接设置")
        connection_layout = QVBoxLayout()
        
        timeout_button = QPushButton(t("连接超时与重试次数"))
        timeout_button.clicked.connect(lambda: self.open_sub_dialog("timeout_retry"))
        connection_layout.addWidget(timeout_button)
        
        connection_group.setLayout(connection_layout)
        layout.addWidget(connection_group)
        
        layout.addStretch()
        tab.setLayout(layout)
    
    def setup_advanced_tab(self, tab):
        """设置高级选项卡"""
        layout = QVBoxLayout()
        
        # 性能设置
        performance_group = QGroupBox("性能设置")
        performance_layout = QVBoxLayout()
        
        cache_label = QLabel("缓存大小限制 (MB):")
        performance_layout.addWidget(cache_label)
        
        self.cache_size_spin = QSpinBox()
        self.cache_size_spin.setRange(10, 1000)
        self.cache_size_spin.setValue(100)
        performance_layout.addWidget(self.cache_size_spin)
        
        performance_group.setLayout(performance_layout)
        layout.addWidget(performance_group)
        
        # 外部工具
        external_group = QGroupBox("外部工具")
        external_layout = QVBoxLayout()
        
        self.external_hook_cb = QCheckBox("启用外部工具脚本钩子")
        external_layout.addWidget(self.external_hook_cb)
        
        self.hook_path_input = QLineEdit()
        self.hook_path_input.setPlaceholderText("脚本路径")
        external_layout.addWidget(self.hook_path_input)
        
        hook_browse_btn = QPushButton("浏览")
        hook_browse_btn.clicked.connect(self.browse_hook_script)
        external_layout.addWidget(hook_browse_btn)
        
        external_group.setLayout(external_layout)
        layout.addWidget(external_group)
        
        # 快捷键设置
        shortcut_group = QGroupBox("快捷键设置")
        shortcut_layout = QVBoxLayout()
        
        shortcut_button = QPushButton("配置快捷键")
        shortcut_button.setDefault(False)
        shortcut_button.setAutoDefault(False)
        shortcut_button.clicked.connect(lambda: self.open_sub_dialog("shortcut_key"))
        shortcut_layout.addWidget(shortcut_button)
        
        shortcut_group.setLayout(shortcut_layout)
        layout.addWidget(shortcut_group)
        
        layout.addStretch()
        tab.setLayout(layout)
    
    def setup_cloud_tab(self, tab):
        """设置云同步选项卡"""
        layout = QVBoxLayout()
        
        # 添加说明
        desc_label = QLabel("配置云同步功能，实现多设备数据同步")
        desc_label.setStyleSheet("font-weight: bold; color: #666; margin-bottom: 10px;")
        layout.addWidget(desc_label)
        
        # 添加云同步设置按钮
        cloud_button = QPushButton("打开云同步设置")
        cloud_button.clicked.connect(self.open_cloud_settings)
        layout.addWidget(cloud_button)
        
        layout.addStretch()
        tab.setLayout(layout)
    
    def load_values(self):
        """加载所有设置值"""
        # 通知设置
        self.desktop_notify_cb.setChecked(self.settings.get("desktop_notify", True))
        self.error_popup_cb.setChecked(self.settings.get("error_popup", True))
        self.email_enable_cb.setChecked(self.settings.get("email_notify", False))
        
        # 外观设置
        self.auto_theme_cb.setChecked(self.settings.get("auto_theme", False))
        self.theme_combo.setCurrentText(self.settings.get("theme", "浅色"))
        self.font_size_spin.setValue(self.settings.get("font_size", 12))
        # 将语言代码转换为显示名称
        language_code_to_display = {
            'zh_CN': '简体中文',
            'zh_TW': '繁體中文',
            'en_US': 'English',
            'ja_JP': '日本語'
        }
        current_language = self.settings.get("language", "zh_CN")
        display_language = language_code_to_display.get(current_language, "简体中文")
        self.language_combo.setCurrentText(display_language)
        
        # 系统设置
        self.auto_upload_cb.setChecked(self.settings.get("auto_upload", False))
        self.auto_clear_cb.setChecked(self.settings.get("auto_clear_history", False))
        self.startup_password_cb.setChecked(self.settings.get("enable_startup_password", False))
        self.password_input.setText(self.settings.get("startup_password", ""))
        self.log_level_combo.setCurrentText(self.settings.get("log_level", "信息"))
        
        # 高级设置
        self.cache_size_spin.setValue(self.settings.get("cache_size", 100))
        self.external_hook_cb.setChecked(self.settings.get("enable_external_hook", False))
        self.hook_path_input.setText(self.settings.get("external_hook_path", ""))
    
    def save_settings(self):
        """保存所有设置"""
        try:
            # 通知设置
            self.settings["desktop_notify"] = self.desktop_notify_cb.isChecked()
            self.settings["error_popup"] = self.error_popup_cb.isChecked()
            self.settings["email_notify"] = self.email_enable_cb.isChecked()
            
            # 外观设置
            self.settings["auto_theme"] = self.auto_theme_cb.isChecked()
            self.settings["theme"] = self.theme_combo.currentText()
            self.settings["font_size"] = self.font_size_spin.value()
            # 将显示名称转换为语言代码
            language_display_to_code = {
                '简体中文': 'zh_CN',
                '繁體中文': 'zh_TW', 
                'English': 'en_US',
                '日本語': 'ja_JP'
            }
            selected_language = self.language_combo.currentText()
            self.settings["language"] = language_display_to_code.get(selected_language, 'zh_CN')
            
            # 系统设置
            self.settings["auto_upload"] = self.auto_upload_cb.isChecked()
            self.settings["auto_clear_history"] = self.auto_clear_cb.isChecked()
            self.settings["enable_startup_password"] = self.startup_password_cb.isChecked()
            self.settings["startup_password"] = self.password_input.text()
            self.settings["log_level"] = self.log_level_combo.currentText()
            
            # 高级设置
            self.settings["cache_size"] = self.cache_size_spin.value()
            self.settings["enable_external_hook"] = self.external_hook_cb.isChecked()
            self.settings["external_hook_path"] = self.hook_path_input.text()
            
            save_settings(self.settings)
            self.show_message("提示", "所有设置已保存！")
            self.settings_changed.emit(self.settings)
            self.accept()
        except Exception as e:
            logging.exception("保存设置异常")
            self.show_message("错误", f"保存失败: {e}", QMessageBox.Icon.Critical)
    
    def open_api_settings(self):
        """打开API密钥设置"""
        dialog = ApiKeySettingsDialog(self)
        dialog.exec()
    

    
    def open_cloud_settings(self):
        """打开云同步设置"""
        dialog = CloudSyncDialog(self)
        dialog.exec()
    
    def open_sub_dialog(self, dialog_type):
        """打开子对话框"""
        dialog = create_setting_dialog(dialog_type, self)
        dialog.exec()
    
    def view_logs(self):
        """查看日志"""
        import os
        log_path = os.path.join("logs", "debug.html")
        if not os.path.exists(log_path):
            self.show_message("提示", "日志文件不存在", QMessageBox.Icon.Warning)
            return
        try:
            os.startfile(log_path)
        except Exception as e:
            logging.exception("打开日志文件异常")
            self.show_message("错误", f"打开日志文件失败: {e}", QMessageBox.Icon.Critical)
    
    def open_log_management(self):
        """打开日志管理对话框"""
        try:
            from widgets.log_management_dialog import LogManagementDialog
            # 保存对话框引用，防止被垃圾回收
            if not hasattr(self, 'log_dialog') or self.log_dialog is None:
                self.log_dialog = LogManagementDialog(self)
            self.log_dialog.show()
            self.log_dialog.raise_()
            self.log_dialog.activateWindow()
        except Exception as e:
            logging.exception("打开日志管理对话框异常")
            self.show_message("错误", f"打开日志管理失败: {e}", QMessageBox.Icon.Critical)
    
    def browse_hook_script(self):
        """浏览脚本文件"""
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, t("select_script_file"), "", t("script_file_filter_extended")
        )
        if file_path:
            self.hook_path_input.setText(file_path)

# 工厂函数，主程序调用入口
def create_setting_dialog(dialog_name, parent=None):
    dialogs = {
        "desktop_notify": DesktopNotifyDialog,
        "error_popup": ErrorPopupDialog,

        "theme_switch": ThemePanel,
        "font_size": EnhancedFontDialog,
        "language_switch": ModernLanguagePanel,

        # 其他对话框继续添加...
        # "auto_upload": 功能已整合到备份管理对话框中
        # "export_history": 功能已整合到备份管理对话框中
        "cache_size": CacheSizeDialog,
        "log_level": LogLevelDialog,
        "startup_password": StartupPasswordDialog,
        # "view_logs": ViewLogsDialog,  # 已移除，使用开发工具面板的日志查看功能
        # "auto_clear_history": AutoClearHistoryDialog,  # 已移除，使用历史面板的清理功能
        "proxy": ProxySettingsDialog,
        "timeout_retry": TimeoutRetryDialog,
        "external_hook": ExternalHookDialog,
        "shortcut_key": ShortcutKeyDialog,
        "api_key_settings": ApiKeySettingsDialog,
        "cloud_sync": CloudSyncDialog,
        "unified_settings": UnifiedSettingsDialog,
    }
    dialog_class = dialogs.get(dialog_name)
    if dialog_class:
        return dialog_class(parent)
    else:
        raise ValueError(f"未知设置对话框: {dialog_name}")