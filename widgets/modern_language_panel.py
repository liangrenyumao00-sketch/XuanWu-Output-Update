# widgets/modern_language_panel.py
"""
现代化语言设置面板模块

该模块提供了一个现代化的语言和区域设置界面，支持多语言切换、
语言包管理、区域设置等功能。具有友好的用户界面和实时预览功能。

主要功能：
- 语言选择：支持多种界面语言切换
- 语言包管理：下载和安装语言包
- 区域设置：时区、日期格式等本地化配置
- 实时预览：即时查看语言切换效果
- 智能功能：自动检测系统语言、记住选择历史

依赖：
- PyQt6：GUI框架
- core.settings：设置管理
- core.theme：主题管理

作者：XuanWu OCR Team
版本：2.1.7
"""
import json
import os
import logging
import time
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, 
    QMessageBox, QApplication, QTabWidget, QGroupBox, QGridLayout,
    QCheckBox, QFrame, QSpacerItem, QSizePolicy, QScrollArea, QWidget
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPalette
from core.settings import load_settings, save_settings
from core.theme import apply_theme


class ModernLanguagePanel(QDialog):
    """
    现代化语言设置面板
    
    提供完整的语言和区域设置功能，包括界面语言切换、语言包管理、
    区域配置等。支持实时预览和智能化设置。
    
    Attributes:
        parent_window (QWidget): 父窗口引用
        settings (dict): 当前设置配置
        recent_languages (list): 最近使用的语言列表
        language_data (dict): 支持的语言数据
        language_combo (QComboBox): 语言选择下拉框
        preview_btn (QPushButton): 预览按钮
        inline_preview_group (QGroupBox): 内联预览组
    
    Signals:
        settings_changed (dict): 设置发生变化时发出的信号
        language_preview_requested (str): 请求语言预览时发出的信号
    
    Example:
        >>> panel = ModernLanguagePanel(parent_widget)
        >>> panel.settings_changed.connect(on_settings_changed)
        >>> panel.show()
    """
    settings_changed = pyqtSignal(dict)
    language_preview_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        logging.debug("[LANG_PANEL_INIT] 开始初始化现代语言设置面板")
        init_start_time = time.time()
        
        super().__init__(parent)
        self.parent_window = parent
        
        logging.debug(f"[LANG_PANEL_INIT] 父窗口: {type(parent).__name__ if parent else 'None'}")
        
        # 加载设置
        settings_start = time.time()
        self.settings = load_settings()
        settings_time = time.time() - settings_start
        logging.debug(f"[LANG_PANEL_INIT] 设置加载完成，耗时: {settings_time:.3f}秒，包含 {len(self.settings)} 个配置项")
        
        # 加载最近使用的语言
        recent_start = time.time()
        self.recent_languages = self.load_recent_languages()
        recent_time = time.time() - recent_start
        logging.debug(f"[LANG_PANEL_INIT] 最近语言加载完成，耗时: {recent_time:.3f}秒，包含 {len(self.recent_languages)} 个语言")
        
        # 移除预览动画相关代码
        
        # 语言数据
        lang_data_start = time.time()
        self.language_data = self.get_language_data()
        lang_data_time = time.time() - lang_data_start
        logging.debug(f"[LANG_PANEL_INIT] 语言数据初始化完成，耗时: {lang_data_time:.3f}秒，支持 {len(self.language_data)} 种语言")
        
        # 窗口设置
        self.setWindowTitle("🌐 语言与区域设置")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumSize(800, 650)
        self.resize(850, 700)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        logging.debug("[LANG_PANEL_INIT] 窗口基本设置完成")
        
        # 初始化UI
        ui_start = time.time()
        self.init_ui()
        ui_time = time.time() - ui_start
        logging.debug(f"[LANG_PANEL_INIT] UI初始化完成，耗时: {ui_time:.3f}秒")
        
        # 加载值
        load_start = time.time()
        self.load_values()
        load_time = time.time() - load_start
        logging.debug(f"[LANG_PANEL_INIT] 值加载完成，耗时: {load_time:.3f}秒")
        
        # 应用现代化样式 - 已禁用自定义背景颜色
        # self.apply_modern_style()
        
        # 移除主题样式应用，使用系统默认样式
        # apply_theme(self)
        
        # 窗口居中显示
        self.center_on_screen()
        
        total_init_time = time.time() - init_start_time
        logging.info(f"[LANG_PANEL_INIT] 现代语言设置面板初始化完成，总耗时: {total_init_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_INIT] 当前语言设置: {self.settings.get('language', 'zh_CN')}")
    
    def get_language_data(self):
        """获取语言数据"""
        return {
            'zh_CN': {
                'display': '简体中文',
                'native': '简体中文',
                'flag': '🇨🇳',
                'region': 'China',
                'code': 'zh'
            },
            'zh_TW': {
                'display': '繁體中文',
                'native': '繁體中文',
                'flag': '🇹🇼',
                'region': 'Taiwan',
                'code': 'zh_TW'
            },
            'en_US': {
                'display': 'English',
                'native': 'English',
                'flag': '🇺🇸',
                'region': 'United States',
                'code': 'en'
            },
            'ja_JP': {
                'display': '日本語',
                'native': '日本語',
                'flag': '🇯🇵',
                'region': 'Japan',
                'code': 'ja'
            },
            'ko_KR': {
                'display': '한국어',
                'native': '한국어',
                'flag': '🇰🇷',
                'region': 'Korea',
                'code': 'ko'
            },
            'fr_FR': {
                'display': 'Français',
                'native': 'Français',
                'flag': '🇫🇷',
                'region': 'France',
                'code': 'fr'
            },
            'de_DE': {
                'display': 'Deutsch',
                'native': 'Deutsch',
                'flag': '🇩🇪',
                'region': 'Germany',
                'code': 'de'
            },
            'es_ES': {
                'display': 'Español',
                'native': 'Español',
                'flag': '🇪🇸',
                'region': 'Spain',
                'code': 'es'
            },
            'ru_RU': {
                'display': 'Русский',
                'native': 'Русский',
                'flag': '🇷🇺',
                'region': 'Russia',
                'code': 'ru'
            },
            'ar_SA': {
                'display': 'العربية',
                'native': 'العربية',
                'flag': '🇸🇦',
                'region': 'Saudi Arabia',
                'code': 'ar'
            }
        }
    
    def init_ui(self):
        """初始化用户界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("🌐 语言与区域设置")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.create_language_tab(), "🗣️ 语言设置")
        self.tab_widget.addTab(self.create_regional_tab(), "🌍 区域设置")
        self.tab_widget.addTab(self.create_advanced_tab(), "⚙️ 高级选项")
        
        main_layout.addWidget(self.tab_widget)
        
        # 预览栏已移除，改为内联预览
        
        # 按钮区域
        self.create_button_area(main_layout)
    
    def create_language_tab(self):
        """创建语言设置标签页"""
        # 创建滚动区域，只给语言设置标签页添加滚动
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 滚动内容widget
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 当前语言组
        current_group = QGroupBox("🎯 当前语言")
        current_layout = QGridLayout(current_group)
        
        current_layout.addWidget(QLabel("界面语言:"), 0, 0)
        self.language_combo = QComboBox()
        self.language_combo.setMinimumHeight(35)
        self.populate_language_combo()
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)
        current_layout.addWidget(self.language_combo, 0, 1)
        
        self.preview_btn = QPushButton("🔍 预览效果")
        self.preview_btn.setMinimumHeight(35)
        self.preview_btn.clicked.connect(self.preview_language)
        current_layout.addWidget(self.preview_btn, 0, 2)
        
        layout.addWidget(current_group)
        
        # 内联预览区域
        self.inline_preview_group = QGroupBox("📋 语言预览")
        self.inline_preview_layout = QVBoxLayout(self.inline_preview_group)
        
        self.inline_preview_label = QLabel("点击预览按钮查看语言效果")
        self.inline_preview_label.setWordWrap(True)
        self.inline_preview_label.setStyleSheet("""
            QLabel {
                padding: 15px;
                border: 2px dashed #ccc;
                border-radius: 8px;
                color: #666;
                text-align: center;
            }
        """)
        self.inline_preview_layout.addWidget(self.inline_preview_label)
        
        self.inline_preview_group.setVisible(False)
        layout.addWidget(self.inline_preview_group)
        
        # 最近使用语言组
        recent_group = QGroupBox("⏰ 最近使用")
        recent_layout = QVBoxLayout(recent_group)
        
        self.recent_languages_layout = QHBoxLayout()
        self.update_recent_languages_ui()
        recent_layout.addLayout(self.recent_languages_layout)
        
        layout.addWidget(recent_group)
        
        # 语言包状态组
        status_group = QGroupBox("📦 语言包状态")
        status_layout = QVBoxLayout(status_group)
        
        # 状态概览
        self.package_status_label = QLabel("正在检查语言包状态...")
        self.package_status_label.setWordWrap(True)
        status_layout.addWidget(self.package_status_label)
        
        # 已安装语言包列表
        installed_label = QLabel("✅ 已安装的语言包:")
        installed_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        status_layout.addWidget(installed_label)
        
        self.installed_packages_layout = QVBoxLayout()
        status_layout.addLayout(self.installed_packages_layout)
        
        # 可下载语言包列表
        available_label = QLabel("📥 可下载的语言包:")
        available_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        status_layout.addWidget(available_label)
        
        self.available_packages_layout = QVBoxLayout()
        status_layout.addLayout(self.available_packages_layout)
        
        layout.addWidget(status_group)
        
        layout.addStretch()
        
        # 设置滚动内容
        scroll_area.setWidget(scroll_content)
        return scroll_area
    
    def create_regional_tab(self):
        """创建区域设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 日期时间格式组
        datetime_group = QGroupBox("📅 日期时间格式")
        datetime_layout = QGridLayout(datetime_group)
        
        datetime_layout.addWidget(QLabel("日期格式:"), 0, 0)
        self.date_format_combo = QComboBox()
        self.date_format_combo.addItems(["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY", "DD.MM.YYYY"])
        datetime_layout.addWidget(self.date_format_combo, 0, 1)
        
        datetime_layout.addWidget(QLabel("时间格式:"), 1, 0)
        self.time_format_combo = QComboBox()
        self.time_format_combo.addItems(["24小时制", "12小时制"])
        datetime_layout.addWidget(self.time_format_combo, 1, 1)
        
        layout.addWidget(datetime_group)
        
        # 数字格式组
        number_group = QGroupBox("🔢 数字格式")
        number_layout = QGridLayout(number_group)
        
        number_layout.addWidget(QLabel("小数点符号:"), 0, 0)
        self.decimal_combo = QComboBox()
        self.decimal_combo.addItems([".", ","])
        number_layout.addWidget(self.decimal_combo, 0, 1)
        
        number_layout.addWidget(QLabel("千位分隔符:"), 1, 0)
        self.thousand_combo = QComboBox()
        self.thousand_combo.addItems([",", ".", " ", "无"])
        number_layout.addWidget(self.thousand_combo, 1, 1)
        
        layout.addWidget(number_group)
        
        layout.addStretch()
        return tab
    
    def create_advanced_tab(self):
        """创建高级选项标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 快捷键组
        hotkey_group = QGroupBox("⌨️ 快捷键设置")
        hotkey_layout = QGridLayout(hotkey_group)
        
        self.enable_hotkey_cb = QCheckBox("启用语言切换快捷键")
        hotkey_layout.addWidget(self.enable_hotkey_cb, 0, 0, 1, 2)
        
        hotkey_layout.addWidget(QLabel("快捷键组合:"), 1, 0)
        self.hotkey_combo = QComboBox()
        self.hotkey_combo.addItems(["Ctrl+Shift+L", "Alt+Shift+L", "Ctrl+Alt+L", "F12"])
        hotkey_layout.addWidget(self.hotkey_combo, 1, 1)
        
        layout.addWidget(hotkey_group)
        
        # 自动检测组
        auto_group = QGroupBox("🤖 智能功能")
        auto_layout = QVBoxLayout(auto_group)
        
        self.auto_detect_cb = QCheckBox("自动检测系统语言")
        auto_layout.addWidget(self.auto_detect_cb)
        
        self.remember_choice_cb = QCheckBox("记住语言选择历史")
        auto_layout.addWidget(self.remember_choice_cb)
        
        layout.addWidget(auto_group)
        
        layout.addStretch()
        return tab
    
    # create_preview_bar方法已移除，改为内联预览
    
    def create_button_area(self, layout):
        """创建按钮区域"""
        # 提示文字
        info_label = QLabel("💡 提示: 某些语言更改需要重启应用程序才能完全生效")
        info_label.setWordWrap(True)
        # 移除自定义颜色，使用系统默认样式
        info_label.setStyleSheet("font-style: italic; margin: 10px 0;")
        layout.addWidget(info_label)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 重置按钮
        self.reset_btn = QPushButton("🔄 重置为默认")
        self.reset_btn.clicked.connect(self.reset_settings)
        button_layout.addWidget(self.reset_btn)
        
        button_layout.addStretch()
        
        # 取消按钮
        self.cancel_btn = QPushButton("取消")
        # 移除自定义大小设置，使用系统默认大小
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        # 保存按钮
        self.save_btn = QPushButton("💾 保存设置")
        # 移除自定义大小设置和样式，使用系统默认大小和样式
        self.save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
    
    def populate_language_combo(self):
        """填充语言下拉框"""
        self.language_combo.clear()
        for code, info in self.language_data.items():
            display_text = f"{info['flag']} {info['display']}"
            self.language_combo.addItem(display_text, code)
    
    def update_recent_languages_ui(self):
        """更新最近使用语言UI"""
        update_start = time.time()
        logging.debug("[LANG_PANEL_RECENT] 开始更新最近使用语言UI")
        
        # 清除现有按钮
        clear_start = time.time()
        layout_count = self.recent_languages_layout.count()
        cleared_count = 0
        
        for i in reversed(range(layout_count)):
            item = self.recent_languages_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
                cleared_count += 1
        
        clear_time = time.time() - clear_start
        logging.debug(f"[LANG_PANEL_RECENT] 布局清理完成，耗时: {clear_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_RECENT] 清理项目: {cleared_count}/{layout_count}")
        
        # 添加最近使用的语言按钮
        add_start = time.time()
        recent_count = len(self.recent_languages)
        display_count = min(recent_count, 5)  # 显示最近5个
        added_buttons = 0
        
        logging.debug(f"[LANG_PANEL_RECENT] 最近语言总数: {recent_count}, 将显示: {display_count}")
        
        for i, lang_code in enumerate(self.recent_languages[:5]):
            if lang_code in self.language_data:
                lang_info = self.language_data[lang_code]
                btn_text = f"{lang_info['flag']} {lang_info['native']}"
                
                btn = QPushButton(btn_text)
                btn.setMinimumHeight(30)
                btn.clicked.connect(lambda checked, code=lang_code: self.quick_switch_language(code))
                self.recent_languages_layout.addWidget(btn)
                
                added_buttons += 1
                logging.debug(f"[LANG_PANEL_RECENT] 添加按钮 {i+1}: {btn_text} ({lang_code})")
            else:
                logging.warning(f"[LANG_PANEL_RECENT] 跳过无效语言代码: {lang_code}")
        
        add_time = time.time() - add_start
        logging.debug(f"[LANG_PANEL_RECENT] 按钮添加完成，耗时: {add_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_RECENT] 成功添加按钮数: {added_buttons}")
        
        # 处理空列表情况
        empty_start = time.time()
        if not self.recent_languages:
            no_recent_label = QLabel("暂无最近使用的语言")
            no_recent_label.setStyleSheet("color: #999; font-style: italic;")
            self.recent_languages_layout.addWidget(no_recent_label)
            
            empty_time = time.time() - empty_start
            logging.debug(f"[LANG_PANEL_RECENT] 空列表处理完成，耗时: {empty_time:.3f}秒")
        
        # 添加弹性空间
        stretch_start = time.time()
        self.recent_languages_layout.addStretch()
        stretch_time = time.time() - stretch_start
        
        logging.debug(f"[LANG_PANEL_RECENT] 弹性空间添加完成，耗时: {stretch_time:.3f}秒")
        
        total_update_time = time.time() - update_start
        logging.info(f"[LANG_PANEL_RECENT] 最近语言UI更新完成，总耗时: {total_update_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_RECENT] 最终布局项目数: {self.recent_languages_layout.count()}")
    
    def load_recent_languages(self):
        """加载最近使用的语言"""
        load_start = time.time()
        logging.debug("[LANG_RECENT_LOAD] 开始加载最近使用的语言")

        try:
            # 先尝试从 settings.json 读取
            settings = load_settings()
            recent_data = settings.get('recent_languages')
            if isinstance(recent_data, list):
                data_count = len(recent_data)
                total_time = time.time() - load_start
                logging.info(f"[LANG_RECENT_LOAD] 从 settings.json 加载最近语言成功，总耗时: {total_time:.3f}秒，数量: {data_count}")
                if data_count > 0:
                    logging.debug(f"[LANG_RECENT_LOAD] 最近语言列表: {recent_data[:5]}...")
                return recent_data

            # 兼容旧版：读取 legacy 文件并迁移
            path_start = time.time()
            recent_file = os.path.join(os.path.dirname(__file__), '..', 'recent_languages.json')
            abs_path = os.path.abspath(recent_file)
            path_time = time.time() - path_start
            logging.debug(f"[LANG_RECENT_LOAD] settings中无最近语言，尝试迁移，路径耗时: {path_time:.3f}秒，相对: {recent_file}，绝对: {abs_path}")

            file_exists = os.path.exists(recent_file)
            logging.debug(f"[LANG_RECENT_LOAD] legacy 文件是否存在: {file_exists}")
            if file_exists:
                try:
                    file_size = os.path.getsize(recent_file)
                    file_mtime = os.path.getmtime(recent_file)
                    logging.debug(f"[LANG_RECENT_LOAD] legacy 文件大小: {file_size} 字节，修改时间: {time.ctime(file_mtime)}")

                    read_start = time.time()
                    with open(recent_file, 'r', encoding='utf-8') as f:
                        legacy_data = json.load(f)
                    read_time = time.time() - read_start

                    if isinstance(legacy_data, list):
                        settings['recent_languages'] = legacy_data
                        save_settings(settings)
                        total_time = time.time() - load_start
                        logging.info(f"[LANG_RECENT_LOAD] 迁移 legacy 最近语言到 settings.json 成功，总耗时: {total_time:.3f}秒，数量: {len(legacy_data)}")
                        return legacy_data
                    else:
                        logging.warning(f"[LANG_RECENT_LOAD] legacy 数据格式错误，期望列表，实际: {type(legacy_data)}")
                        return []
                except json.JSONDecodeError as e:
                    error_time = time.time() - load_start
                    logging.error(f"[LANG_RECENT_LOAD] legacy JSON解析失败，耗时: {error_time:.3f}秒，错误: {e}")
                    logging.debug(f"[LANG_RECENT_LOAD] JSON错误位置: 行{e.lineno}, 列{e.colno}")
                    return []
            else:
                logging.debug("[LANG_RECENT_LOAD] 未找到 legacy 最近语言文件，返回空列表")
                return []

        except Exception as e:
            error_time = time.time() - load_start
            logging.error(f"[LANG_RECENT_LOAD] 加载最近语言失败，耗时: {error_time:.3f}秒，错误: {e}")
            logging.exception("[LANG_RECENT_LOAD] 详细错误信息")
            return []
    
    def save_recent_languages(self):
        """保存最近使用的语言"""
        try:
            start = time.time()
            settings = load_settings()
            settings['recent_languages'] = list(self.recent_languages)
            save_settings(settings)
            total = time.time() - start
            logging.debug(f"[LANG_RECENT_SAVE] 最近语言保存到 settings.json 完成，耗时: {total:.3f}秒，数量: {len(self.recent_languages)}")
        except Exception as e:
            logging.error(f"[LANG_RECENT_SAVE_ERROR] 保存最近语言到 settings.json 失败: {e}")
    
    def load_values(self):
        """加载当前设置值"""
        load_start = time.time()
        logging.debug("[LANG_PANEL_LOAD] 开始加载当前设置值")
        
        # 加载语言设置
        lang_load_start = time.time()
        current_lang = self.settings.get('language', 'zh_CN')
        logging.debug(f"[LANG_PANEL_LOAD] 当前语言设置: {current_lang}")
        
        # 设置当前语言选项
        combo_items = self.language_combo.count()
        lang_found = False
        for i in range(combo_items):
            if self.language_combo.itemData(i) == current_lang:
                self.language_combo.setCurrentIndex(i)
                lang_found = True
                logging.debug(f"[LANG_PANEL_LOAD] 语言下拉框设置为索引 {i}: {current_lang}")
                break
        
        if not lang_found:
            logging.warning(f"[LANG_PANEL_LOAD] 未找到语言 {current_lang}，使用默认选项")
            self.language_combo.setCurrentIndex(0)
        
        lang_load_time = time.time() - lang_load_start
        logging.debug(f"[LANG_PANEL_LOAD] 语言设置加载完成，耗时: {lang_load_time:.3f}秒")
        
        # 加载区域设置
        region_load_start = time.time()
        date_format = self.settings.get('date_format', 'YYYY-MM-DD')
        time_format = self.settings.get('time_format', '24小时制')
        decimal_sep = self.settings.get('decimal_separator', '.')
        thousand_sep = self.settings.get('thousand_separator', ',')
        
        self.date_format_combo.setCurrentText(date_format)
        self.time_format_combo.setCurrentText(time_format)
        self.decimal_combo.setCurrentText(decimal_sep)
        self.thousand_combo.setCurrentText(thousand_sep)
        
        region_load_time = time.time() - region_load_start
        logging.debug(f"[LANG_PANEL_LOAD] 区域设置加载完成，耗时: {region_load_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_LOAD] 日期格式: {date_format}, 时间格式: {time_format}")
        logging.debug(f"[LANG_PANEL_LOAD] 小数分隔符: {decimal_sep}, 千位分隔符: {thousand_sep}")
        
        # 加载高级设置
        advanced_load_start = time.time()
        enable_hotkey = self.settings.get('enable_language_hotkey', False)
        hotkey = self.settings.get('language_hotkey', 'Ctrl+Shift+L')
        auto_detect = self.settings.get('auto_detect_language', False)
        remember_choice = self.settings.get('remember_language_choice', True)
        
        self.enable_hotkey_cb.setChecked(enable_hotkey)
        self.hotkey_combo.setCurrentText(hotkey)
        self.auto_detect_cb.setChecked(auto_detect)
        self.remember_choice_cb.setChecked(remember_choice)
        
        advanced_load_time = time.time() - advanced_load_start
        logging.debug(f"[LANG_PANEL_LOAD] 高级设置加载完成，耗时: {advanced_load_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_LOAD] 启用热键: {enable_hotkey}, 热键: {hotkey}")
        logging.debug(f"[LANG_PANEL_LOAD] 自动检测: {auto_detect}, 记住选择: {remember_choice}")
        
        # 更新语言包状态
        status_start = time.time()
        QTimer.singleShot(500, self.update_package_status)
        status_time = time.time() - status_start
        logging.debug(f"[LANG_PANEL_LOAD] 语言包状态更新定时器设置完成，耗时: {status_time:.3f}秒")
        
        total_load_time = time.time() - load_start
        logging.info(f"[LANG_PANEL_LOAD] 设置值加载完成，总耗时: {total_load_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_LOAD] 加载的配置项数量: {len(self.settings)}")
    
    def save_settings(self):
        """保存设置"""
        logging.debug("[LANG_PANEL_SAVE] 开始保存语言设置")
        save_start_time = time.time()
        
        # 获取选择的语言
        current_index = self.language_combo.currentIndex()
        selected_lang = self.language_combo.itemData(current_index)
        
        logging.debug(f"[LANG_PANEL_SAVE] 当前选择索引: {current_index}")
        logging.debug(f"[LANG_PANEL_SAVE] 选择的语言: {selected_lang}")
        logging.debug(f"[LANG_PANEL_SAVE] 组合框总项数: {self.language_combo.count()}")
        
        if not selected_lang:
            selected_lang = 'zh_CN'
            logging.warning(f"[LANG_PANEL_SAVE] 未选择有效语言，使用默认: {selected_lang}")
        
        # 验证语言选择
        if selected_lang not in self.language_data:
            logging.error(f"[LANG_PANEL_SAVE] 选择的语言 '{selected_lang}' 不在支持列表中")
            logging.debug(f"[LANG_PANEL_SAVE] 支持的语言: {list(self.language_data.keys())}")
            return
        
        # 更新设置
        old_language = self.settings.get('language', 'zh_CN')
        
        # 检查是否真的需要更改
        if old_language == selected_lang:
            logging.debug(f"[LANG_PANEL_SAVE] 语言未变化，跳过保存: {selected_lang}")
            self.accept()
            return
        
        logging.info(f"[LANG_PANEL_SAVE] 语言变更: {old_language} -> {selected_lang}")
        
        self.settings['language'] = selected_lang
        
        # 保存语言代码用于国际化系统
        lang_info = self.language_data.get(selected_lang, {})
        language_code = lang_info.get('code', selected_lang.split('_')[0] if '_' in selected_lang else selected_lang)
        self.settings['language_code'] = language_code
        
        logging.debug(f"[LANG_PANEL_SAVE] 语言信息: {lang_info}")
        logging.debug(f"[LANG_PANEL_SAVE] 国际化代码: {language_code}")
        logging.debug(f"[LANG_PANEL_SAVE] 语言显示名: {lang_info.get('display', selected_lang)}")
        logging.debug(f"[LANG_PANEL_SAVE] 语言本地名: {lang_info.get('native', selected_lang)}")
        
        # 保存区域设置
        region_start = time.time()
        self.settings['date_format'] = self.date_format_combo.currentText()
        self.settings['time_format'] = self.time_format_combo.currentText()
        self.settings['decimal_separator'] = self.decimal_combo.currentText()
        self.settings['thousand_separator'] = self.thousand_combo.currentText()
        region_time = time.time() - region_start
        
        logging.debug(f"[LANG_PANEL_SAVE] 区域设置保存完成，耗时: {region_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_SAVE] 日期格式: {self.settings['date_format']}")
        logging.debug(f"[LANG_PANEL_SAVE] 时间格式: {self.settings['time_format']}")
        
        # 保存高级设置
        advanced_start = time.time()
        self.settings['enable_language_hotkey'] = self.enable_hotkey_cb.isChecked()
        self.settings['language_hotkey'] = self.hotkey_combo.currentText()
        self.settings['auto_detect_language'] = self.auto_detect_cb.isChecked()
        self.settings['remember_language_choice'] = self.remember_choice_cb.isChecked()
        advanced_time = time.time() - advanced_start
        
        logging.debug(f"[LANG_PANEL_SAVE] 高级设置保存完成，耗时: {advanced_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_SAVE] 启用热键: {self.settings['enable_language_hotkey']}")
        logging.debug(f"[LANG_PANEL_SAVE] 热键组合: {self.settings['language_hotkey']}")
        logging.debug(f"[LANG_PANEL_SAVE] 自动检测: {self.settings['auto_detect_language']}")
        logging.debug(f"[LANG_PANEL_SAVE] 记住选择: {self.settings['remember_language_choice']}")
        
        # 更新最近使用的语言
        recent_start = time.time()
        if self.settings['remember_language_choice']:
            old_recent_count = len(self.recent_languages)
            if selected_lang in self.recent_languages:
                self.recent_languages.remove(selected_lang)
            self.recent_languages.insert(0, selected_lang)
            self.recent_languages = self.recent_languages[:10]  # 保留最近10个
            
            try:
                self.save_recent_languages()
                recent_time = time.time() - recent_start
                logging.debug(f"[LANG_PANEL_SAVE] 最近语言更新完成，耗时: {recent_time:.3f}秒")
                logging.debug(f"[LANG_PANEL_SAVE] 最近语言列表: {self.recent_languages[:5]}...")
            except Exception as e:
                logging.error(f"[LANG_PANEL_SAVE] 保存最近语言失败: {e}")
        else:
            logging.debug("[LANG_PANEL_SAVE] 跳过最近语言更新（用户禁用）")
        
        # 保存设置到文件
        file_save_start = time.time()
        try:
            logging.debug(f"[LANG_PANEL_SAVE] 准备保存设置到文件，包含 {len(self.settings)} 个配置项")
            save_settings(self.settings)
            file_save_time = time.time() - file_save_start
            logging.debug(f"[LANG_PANEL_SAVE] 设置文件保存完成，耗时: {file_save_time:.3f}秒")
        except Exception as e:
            logging.error(f"[LANG_PANEL_SAVE] 设置文件保存失败: {e}")
            QMessageBox.critical(self, "错误", f"保存设置失败: {e}")
            return
        
        # 发送设置变更信号
        signal_start = time.time()
        try:
            logging.debug("[LANG_PANEL_SAVE] 发送设置变更信号")
            self.settings_changed.emit(self.settings)
            signal_time = time.time() - signal_start
            logging.debug(f"[LANG_PANEL_SAVE] 设置变更信号发送完成，耗时: {signal_time:.3f}秒")
        except Exception as e:
            logging.error(f"[LANG_PANEL_SAVE] 发送设置变更信号失败: {e}")
        
        # 显示提示信息
        display_name = self.language_data.get(selected_lang, {}).get('display', selected_lang)
        native_name = self.language_data.get(selected_lang, {}).get('native', selected_lang)
        
        logging.debug(f"[LANG_PANEL_SAVE] 显示语言名称: {display_name}")
        logging.debug(f"[LANG_PANEL_SAVE] 本地语言名称: {native_name}")
        
        try:
            QMessageBox.information(
                self,
                "✅ 设置已保存",
                f"语言和区域设置已保存。\n\n当前语言: {display_name} ({native_name})\n\n某些更改可能需要重启程序才能完全生效。"
            )
        except Exception as e:
            logging.error(f"[LANG_PANEL_SAVE] 显示确认对话框失败: {e}")
        
        total_save_time = time.time() - save_start_time
        logging.info(f"[LANG_PANEL_SAVE] 语言设置保存流程完成，总耗时: {total_save_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_SAVE] 最终语言设置: {selected_lang} ({display_name})")
        
        self.accept()
    
    def on_language_changed(self):
        """语言选择改变时的处理"""
        change_start = time.time()
        logging.debug("[LANG_PANEL_CHANGE] 开始处理语言选择变更")
        
        # 获取当前选择
        selection_start = time.time()
        current_index = self.language_combo.currentIndex()
        selected_lang = self.language_combo.itemData(current_index)
        selection_time = time.time() - selection_start
        
        logging.debug(f"[LANG_PANEL_CHANGE] 选择获取完成，耗时: {selection_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_CHANGE] 当前索引: {current_index}, 选择语言: {selected_lang}")
        
        if selected_lang and selected_lang in self.language_data:
            # 处理有效语言选择
            valid_start = time.time()
            lang_info = self.language_data[selected_lang]
            
            # 更新预览按钮文本
            old_text = self.preview_btn.text()
            new_text = f"🔍 预览 {lang_info['native']}"
            self.preview_btn.setText(new_text)
            
            valid_time = time.time() - valid_start
            logging.debug(f"[LANG_PANEL_CHANGE] 有效语言处理完成，耗时: {valid_time:.3f}秒")
            logging.debug(f"[LANG_PANEL_CHANGE] 按钮文本更新: '{old_text}' -> '{new_text}'")
            logging.debug(f"[LANG_PANEL_CHANGE] 语言详情: {lang_info}")
            
        else:
            # 处理无效语言选择
            invalid_start = time.time()
            logging.warning(f"[LANG_PANEL_CHANGE] 无效的语言选择: {selected_lang}")
            
            # 重置预览按钮文本
            old_text = self.preview_btn.text()
            new_text = "🔍 预览效果"
            self.preview_btn.setText(new_text)
            
            invalid_time = time.time() - invalid_start
            logging.debug(f"[LANG_PANEL_CHANGE] 无效语言处理完成，耗时: {invalid_time:.3f}秒")
            logging.debug(f"[LANG_PANEL_CHANGE] 按钮文本重置: '{old_text}' -> '{new_text}'")
            logging.debug(f"[LANG_PANEL_CHANGE] 可用语言列表: {list(self.language_data.keys())}")
        
        total_change_time = time.time() - change_start
        logging.debug(f"[LANG_PANEL_CHANGE] 语言选择变更处理完成，总耗时: {total_change_time:.3f}秒")
    
    def preview_language(self):
        """预览语言效果"""
        preview_start = time.time()
        logging.debug("[LANG_PANEL_PREVIEW] 开始预览语言效果")
        
        # 获取当前选择
        selection_start = time.time()
        current_index = self.language_combo.currentIndex()
        selected_lang = self.language_combo.itemData(current_index)
        selection_time = time.time() - selection_start
        
        logging.debug(f"[LANG_PANEL_PREVIEW] 获取选择完成，耗时: {selection_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_PREVIEW] 当前索引: {current_index}, 选择语言: {selected_lang}")
        
        if selected_lang and selected_lang in self.language_data:
            # 获取语言信息
            info_start = time.time()
            lang_info = self.language_data[selected_lang]
            info_time = time.time() - info_start
            
            logging.debug(f"[LANG_PANEL_PREVIEW] 语言信息获取完成，耗时: {info_time:.3f}秒")
            logging.debug(f"[LANG_PANEL_PREVIEW] 语言信息: {lang_info}")
            
            # 生成预览内容
            content_start = time.time()
            preview_text = f"""<div style='text-align: center;'>
            <h3 style='margin-bottom: 10px;'>🌍 {lang_info['display']}</h3>
            <p style='margin-bottom: 8px;'>本地名称: <strong>{lang_info['native']}</strong></p>
            <p style='margin-bottom: 15px;'>语言代码: <strong>{selected_lang}</strong></p>
            <div style='padding: 12px; border-radius: 6px; margin: 10px 0;'>
                 <p style='margin: 0;'>预览模式: 界面将显示为该语言</p>
             </div>
            </div>"""
            content_time = time.time() - content_start
            
            logging.debug(f"[LANG_PANEL_PREVIEW] 预览内容生成完成，耗时: {content_time:.3f}秒")
            logging.debug(f"[LANG_PANEL_PREVIEW] 预览文本长度: {len(preview_text)} 字符")
            
            # 更新UI
            ui_start = time.time()
            self.inline_preview_label.setText(preview_text)
            self.inline_preview_label.setStyleSheet("""
                 QLabel {
                     padding: 18px;
                     border: 2px solid #4a90e2;
                     border-radius: 10px;
                 }
             """)
            self.inline_preview_group.setVisible(True)
            ui_time = time.time() - ui_start
            
            logging.debug(f"[LANG_PANEL_PREVIEW] UI更新完成，耗时: {ui_time:.3f}秒")
            
            # 发送预览信号
            signal_start = time.time()
            self.language_preview_requested.emit(selected_lang)
            signal_time = time.time() - signal_start
            
            logging.debug(f"[LANG_PANEL_PREVIEW] 预览信号发送完成，耗时: {signal_time:.3f}秒")
            
        else:
            # 处理错误情况
            error_start = time.time()
            logging.warning(f"[LANG_PANEL_PREVIEW] 无效的语言选择: {selected_lang}")
            logging.debug(f"[LANG_PANEL_PREVIEW] 可用语言: {list(self.language_data.keys())}")
            
            error_text = "<div style='text-align: center;'><h3 style='color: #dc3545; margin-bottom: 10px;'>⚠️ 语言选择错误</h3><p>请选择一个有效的语言选项</p></div>"
            self.inline_preview_label.setText(error_text)
            self.inline_preview_label.setStyleSheet("""
                QLabel {
                    padding: 18px;
                    border: 2px solid #dc3545;
                    border-radius: 10px;
                    background-color: #f8d7da;
                }
            """)
            self.inline_preview_group.setVisible(True)
            
            error_time = time.time() - error_start
            logging.debug(f"[LANG_PANEL_PREVIEW] 错误处理完成，耗时: {error_time:.3f}秒")
        
        total_preview_time = time.time() - preview_start
        logging.info(f"[LANG_PANEL_PREVIEW] 语言预览完成，总耗时: {total_preview_time:.3f}秒")
    
    def quick_switch_language(self, lang_code):
        """快速切换语言"""
        switch_start = time.time()
        logging.debug(f"[LANG_PANEL_QUICK] 开始快速切换到语言: {lang_code}")
        
        # 搜索匹配的语言项
        search_start = time.time()
        combo_count = self.language_combo.count()
        found_index = -1
        
        for i in range(combo_count):
            item_data = self.language_combo.itemData(i)
            if item_data == lang_code:
                found_index = i
                break
        
        search_time = time.time() - search_start
        logging.debug(f"[LANG_PANEL_QUICK] 语言搜索完成，耗时: {search_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_QUICK] 搜索范围: {combo_count} 项，找到索引: {found_index}")
        
        if found_index >= 0:
            # 执行切换
            switch_exec_start = time.time()
            old_index = self.language_combo.currentIndex()
            self.language_combo.setCurrentIndex(found_index)
            
            # 触发变更处理
            self.on_language_changed()
            
            switch_exec_time = time.time() - switch_exec_start
            logging.debug(f"[LANG_PANEL_QUICK] 语言切换执行完成，耗时: {switch_exec_time:.3f}秒")
            logging.debug(f"[LANG_PANEL_QUICK] 索引变更: {old_index} -> {found_index}")
            
            # 获取语言信息用于日志
            if lang_code in self.language_data:
                lang_info = self.language_data[lang_code]
                logging.info(f"[LANG_PANEL_QUICK] 快速切换成功: {lang_info.get('display', lang_code)}")
            
        else:
            # 未找到匹配项
            logging.warning(f"[LANG_PANEL_QUICK] 未找到语言代码: {lang_code}")
            logging.debug(f"[LANG_PANEL_QUICK] 可用语言代码: {[self.language_combo.itemData(i) for i in range(combo_count)]}")
        
        total_switch_time = time.time() - switch_start
        logging.debug(f"[LANG_PANEL_QUICK] 快速语言切换完成，总耗时: {total_switch_time:.3f}秒")
    
    # show_preview和hide_preview方法已移除，改为内联预览
    
    def reset_settings(self):
        """重置设置为默认值"""
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要将所有语言和区域设置重置为默认值吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 重置为默认值
            for i in range(self.language_combo.count()):
                if self.language_combo.itemData(i) == 'zh_CN':
                    self.language_combo.setCurrentIndex(i)
                    break
            
            self.date_format_combo.setCurrentText('YYYY-MM-DD')
            self.time_format_combo.setCurrentText('24小时制')
            self.decimal_combo.setCurrentText('.')
            self.thousand_combo.setCurrentText(',')
            
            self.enable_hotkey_cb.setChecked(False)
            self.hotkey_combo.setCurrentText('Ctrl+Shift+L')
            self.auto_detect_cb.setChecked(False)
            self.remember_choice_cb.setChecked(True)
            
            self.on_language_changed()
    
    def update_package_status(self):
        """更新语言包状态"""
        update_start = time.time()
        logging.debug("[LANG_PANEL_PKG] 开始更新语言包状态")
        
        # 模拟已安装的语言包（实际应用中应该检查实际安装状态）
        check_start = time.time()
        installed_packages = ['zh_CN', 'zh_TW', 'en_US', 'ja_JP']
        available_packages = [code for code in self.language_data.keys() if code not in installed_packages]
        check_time = time.time() - check_start
        
        logging.debug(f"[LANG_PANEL_PKG] 语言包检查完成，耗时: {check_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_PKG] 已安装: {len(installed_packages)} 个 - {installed_packages}")
        logging.debug(f"[LANG_PANEL_PKG] 可下载: {len(available_packages)} 个 - {available_packages}")
        
        # 更新状态概览
        status_start = time.time()
        status_text = f"已安装 {len(installed_packages)}/{len(self.language_data)} 个语言包"
        if available_packages:
            status_text += f" (还有 {len(available_packages)} 个可下载)"
        self.package_status_label.setText(status_text)
        status_time = time.time() - status_start
        
        logging.debug(f"[LANG_PANEL_PKG] 状态概览更新完成，耗时: {status_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_PKG] 状态文本: {status_text}")
        
        # 清除现有的语言包显示
        clear_start = time.time()
        self.clear_layout(self.installed_packages_layout)
        self.clear_layout(self.available_packages_layout)
        clear_time = time.time() - clear_start
        
        logging.debug(f"[LANG_PANEL_PKG] 布局清理完成，耗时: {clear_time:.3f}秒")
        
        # 显示已安装的语言包
        installed_start = time.time()
        installed_count = 0
        for lang_code in installed_packages:
            if lang_code in self.language_data:
                lang_info = self.language_data[lang_code]
                package_widget = self.create_installed_package_widget(lang_code, lang_info)
                self.installed_packages_layout.addWidget(package_widget)
                installed_count += 1
        
        installed_time = time.time() - installed_start
        logging.debug(f"[LANG_PANEL_PKG] 已安装语言包UI创建完成，耗时: {installed_time:.3f}秒，创建了 {installed_count} 个组件")
        
        # 显示可下载的语言包
        available_start = time.time()
        available_count = 0
        for lang_code in available_packages:
            if lang_code in self.language_data:
                lang_info = self.language_data[lang_code]
                package_widget = self.create_available_package_widget(lang_code, lang_info)
                self.available_packages_layout.addWidget(package_widget)
                available_count += 1
        
        available_time = time.time() - available_start
        logging.debug(f"[LANG_PANEL_PKG] 可下载语言包UI创建完成，耗时: {available_time:.3f}秒，创建了 {available_count} 个组件")
        
        # 如果没有可下载的语言包，显示提示
        if not available_packages:
            no_available_label = QLabel("🎉 所有语言包都已安装")
            no_available_label.setStyleSheet("color: #28a745; font-style: italic; padding: 10px;")
            self.available_packages_layout.addWidget(no_available_label)
            logging.debug("[LANG_PANEL_PKG] 显示所有语言包已安装提示")
        
        total_update_time = time.time() - update_start
        logging.info(f"[LANG_PANEL_PKG] 语言包状态更新完成，总耗时: {total_update_time:.3f}秒")
        logging.debug(f"[LANG_PANEL_PKG] 总语言包数: {len(self.language_data)}, 已安装: {len(installed_packages)}, 可下载: {len(available_packages)}")
    
    def clear_layout(self, layout):
        """清除布局中的所有widget"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def create_installed_package_widget(self, lang_code, lang_info):
        """创建已安装语言包的widget"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Shape.StyledPanel)
        widget.setMinimumHeight(50)  # 设置最小高度确保文字不被遮挡
        widget.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 8px;
                margin: 2px;
            }
        """)
        
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 8, 10, 8)  # 增加上下边距
        
        # 语言信息
        info_label = QLabel(f"{lang_info['flag']} {lang_info['display']} ({lang_info['native']})")
        info_label.setWordWrap(True)  # 允许文字换行
        info_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        info_label.setMinimumHeight(30)  # 确保有足够高度显示文字
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        # 状态标签
        status_label = QLabel("✅ 已安装")
        status_label.setStyleSheet("color: #28a745; font-weight: bold;")
        layout.addWidget(status_label)
        
        return widget
    
    def create_available_package_widget(self, lang_code, lang_info):
        """创建可下载语言包的widget"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Shape.StyledPanel)
        widget.setMinimumHeight(50)  # 设置最小高度确保文字不被遮挡
        widget.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 8px;
                margin: 2px;
            }
        """)
        
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 8, 10, 8)  # 增加上下边距
        
        # 语言信息
        info_label = QLabel(f"{lang_info['flag']} {lang_info['display']} ({lang_info['native']})")
        info_label.setWordWrap(True)  # 允许文字换行
        info_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        info_label.setMinimumHeight(30)  # 确保有足够高度显示文字
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        # 下载按钮
        download_btn = QPushButton("📥 下载")
        download_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        download_btn.clicked.connect(lambda: self.download_language_package(lang_code, lang_info))
        layout.addWidget(download_btn)
        
        return widget
    
    def download_language_package(self, lang_code, lang_info):
        """下载语言包"""
        download_start = time.time()
        logging.debug(f"[LANG_PKG_DOWNLOAD] 开始下载语言包: {lang_code}")
        logging.debug(f"[LANG_PKG_DOWNLOAD] 语言信息: {lang_info}")
        
        try:
            # 验证输入参数
            if not lang_code or not lang_info:
                logging.error("[LANG_PKG_DOWNLOAD] 无效的语言代码或语言信息")
                QMessageBox.warning(self, "错误", "无效的语言包信息")
                return
            
            display_name = lang_info.get('display', lang_code)
            native_name = lang_info.get('native', lang_code)
            
            logging.debug(f"[LANG_PKG_DOWNLOAD] 显示名称: {display_name}")
            logging.debug(f"[LANG_PKG_DOWNLOAD] 本地名称: {native_name}")
            
            # 显示下载确认对话框
            confirm_start = time.time()
            reply = QMessageBox.question(
                self,
                "下载语言包",
                f"确定要下载 {display_name} ({native_name}) 语言包吗？\n\n下载完成后将自动安装。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            confirm_time = time.time() - confirm_start
            
            logging.debug(f"[LANG_PKG_DOWNLOAD] 确认对话框显示完成，耗时: {confirm_time:.3f}秒")
            logging.debug(f"[LANG_PKG_DOWNLOAD] 用户选择: {'确认' if reply == QMessageBox.StandardButton.Yes else '取消'}")
            
            if reply == QMessageBox.StandardButton.Yes:
                # 开始下载过程
                download_process_start = time.time()
                logging.info(f"[LANG_PKG_DOWNLOAD] 用户确认下载 {display_name} 语言包")
                
                # 显示下载进度对话框
                progress_start = time.time()
                QMessageBox.information(
                    self,
                    "下载中",
                    f"正在下载 {display_name} 语言包...\n\n这可能需要几分钟时间，请耐心等待。"
                )
                progress_time = time.time() - progress_start
                
                logging.debug(f"[LANG_PKG_DOWNLOAD] 下载进度对话框显示完成，耗时: {progress_time:.3f}秒")
                
                # 模拟下载过程（实际应用中应该实现真实的下载逻辑）
                simulate_start = time.time()
                
                # 这里可以添加实际的下载逻辑：
                # 1. 从服务器下载语言包文件
                # 2. 验证文件完整性
                # 3. 解压和安装语言包
                # 4. 更新本地语言包列表
                
                # 模拟下载耗时
                import time as time_module
                time_module.sleep(0.1)  # 模拟下载时间
                
                simulate_time = time.time() - simulate_start
                logging.debug(f"[LANG_PKG_DOWNLOAD] 下载模拟完成，耗时: {simulate_time:.3f}秒")
                
                # 验证下载结果
                verify_start = time.time()
                download_success = True  # 模拟下载成功
                
                if download_success:
                    # 模拟安装过程
                    install_start = time.time()
                    install_success = True  # 模拟安装成功
                    install_time = time.time() - install_start
                    
                    logging.debug(f"[LANG_PKG_DOWNLOAD] 语言包安装完成，耗时: {install_time:.3f}秒")
                    
                    if install_success:
                        verify_time = time.time() - verify_start
                        logging.debug(f"[LANG_PKG_DOWNLOAD] 下载验证完成，耗时: {verify_time:.3f}秒")
                        
                        # 显示成功消息
                        success_start = time.time()
                        QMessageBox.information(
                            self,
                            "下载完成",
                            f"{display_name} 语言包下载并安装成功！\n\n您现在可以使用这个语言了。"
                        )
                        success_time = time.time() - success_start
                        
                        logging.debug(f"[LANG_PKG_DOWNLOAD] 成功消息显示完成，耗时: {success_time:.3f}秒")
                        
                        # 刷新语言包状态显示
                        refresh_start = time.time()
                        QTimer.singleShot(100, self.update_package_status)
                        refresh_time = time.time() - refresh_start
                        
                        logging.debug(f"[LANG_PKG_DOWNLOAD] 状态刷新调度完成，耗时: {refresh_time:.3f}秒")
                        
                        download_process_time = time.time() - download_process_start
                        total_time = time.time() - download_start
                        
                        logging.info(f"[LANG_PKG_DOWNLOAD] {display_name} 语言包下载成功")
                        logging.debug(f"[LANG_PKG_DOWNLOAD] 下载过程耗时: {download_process_time:.3f}秒")
                        logging.debug(f"[LANG_PKG_DOWNLOAD] 总耗时: {total_time:.3f}秒")
                    else:
                        logging.error(f"[LANG_PKG_DOWNLOAD] {display_name} 语言包安装失败")
                        QMessageBox.critical(self, "安装失败", f"{display_name} 语言包安装失败，请重试。")
                else:
                    logging.error(f"[LANG_PKG_DOWNLOAD] {display_name} 语言包下载失败")
                    QMessageBox.critical(self, "下载失败", f"{display_name} 语言包下载失败，请检查网络连接后重试。")
            else:
                cancel_time = time.time() - download_start
                logging.debug(f"[LANG_PKG_DOWNLOAD] 用户取消下载，总耗时: {cancel_time:.3f}秒")
                
        except Exception as e:
            error_time = time.time() - download_start
            logging.error(f"[LANG_PKG_DOWNLOAD] 下载语言包失败，耗时: {error_time:.3f}秒，错误: {e}")
            logging.exception("[LANG_PKG_DOWNLOAD] 详细错误信息")
            QMessageBox.critical(
                self, 
                "下载错误", 
                f"下载 {lang_info.get('display', lang_code)} 语言包时发生错误：\n\n{str(e)}"
            )
    
    def position_relative_to_parent(self):
        """相对于父窗口定位"""
        if self.parent_window:
            parent_geometry = self.parent_window.geometry()
            # 计算面板在父窗口右侧的位置
            x = parent_geometry.x() + parent_geometry.width() + 10
            y = parent_geometry.y() + 30
            
            # 获取屏幕几何信息
            screen = QApplication.primaryScreen().geometry()
            
            # 检查右侧是否有足够空间
            if x + self.width() > screen.width():
                # 右侧空间不足，尝试左侧
                x = parent_geometry.x() - self.width() - 10
                if x < 0:
                    # 左侧也不足，居中显示
                    x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
            
            # 检查垂直位置
            if y + self.height() > screen.height():
                y = screen.height() - self.height() - 30
                if y < 0:
                    y = 30
            
            self.move(x, y)
        else:
            self.center_on_screen()
    
    def center_on_screen(self):
        """将窗口居中显示在屏幕上"""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        
        # 获取窗口大小
        window_size = self.size()
        
        # 计算居中位置
        x = (screen_geometry.width() - window_size.width()) // 2 + screen_geometry.x()
        y = (screen_geometry.height() - window_size.height()) // 2 + screen_geometry.y()
        
        # 移动窗口到计算的位置
        self.move(x, y)
    
    def refresh_ui_text(self):
        """刷新UI文本的国际化显示"""
        try:
            from core.i18n import t
            
            # 刷新窗口标题
            self.setWindowTitle(t('language_settings_title'))
            
            # 刷新标签页标题
            if hasattr(self, 'tab_widget'):
                for i in range(self.tab_widget.count()):
                    tab_text = self.tab_widget.tabText(i)
                    if '语言选择' in tab_text or 'Language Selection' in tab_text:
                        self.tab_widget.setTabText(i, t('language_selection'))
                    elif '区域设置' in tab_text or 'Regional Settings' in tab_text:
                        self.tab_widget.setTabText(i, t('regional_settings'))
                    elif '高级选项' in tab_text or 'Advanced Options' in tab_text:
                        self.tab_widget.setTabText(i, t('advanced_options'))
            
            # 刷新按钮文本
            for button in self.findChildren(QPushButton):
                if button.text() == '应用' or button.text() == 'Apply':
                    button.setText(t('apply'))
                elif button.text() == '取消' or button.text() == 'Cancel':
                    button.setText(t('cancel'))
                elif button.text() == '确定' or button.text() == 'OK':
                    button.setText(t('ok'))
                elif button.text() == '预览' or button.text() == 'Preview':
                    button.setText(t('preview'))
            
            # 刷新组框标题
            for group_box in self.findChildren(QGroupBox):
                if '当前语言' in group_box.title() or 'Current Language' in group_box.title():
                    group_box.setTitle(t('current_language'))
                elif '最近使用' in group_box.title() or 'Recently Used' in group_box.title():
                    group_box.setTitle(t('recently_used_languages'))
                elif '所有语言' in group_box.title() or 'All Languages' in group_box.title():
                    group_box.setTitle(t('all_languages'))
            
        except Exception as e:
            import logging
            logging.error(f"刷新ModernLanguagePanel UI文本时出错: {e}")


# 为了保持向后兼容性，保留简化版本的别名
LanguagePanel = ModernLanguagePanel