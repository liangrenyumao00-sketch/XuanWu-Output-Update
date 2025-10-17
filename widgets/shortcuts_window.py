# shortcuts_window.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QGroupBox, QScrollArea, QWidget, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QComboBox, QSplitter, QFrame, QTabWidget, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QKeySequence, QIcon, QPalette
from core.group_framework_styles import apply_group_framework_style, setup_group_framework_layout

class ShortcutsWindow(QDialog):
    """快捷键窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("快捷键帮助 - 炫舞OCR")
        self.resize(900, 700)
        self.setMinimumSize(800, 600)
        
        # 快捷键数据
        self.shortcuts_data = self._load_shortcuts_data()
        self.filtered_data = self.shortcuts_data.copy()
        
        # 创建界面
        self.setup_ui()
        
        # 应用主题样式（在UI创建后应用，确保不被覆盖）
        self.apply_theme_styles()
        
        # 初始化数据
        self.init_data()
    
    def keyPressEvent(self, event):
        """处理按键事件"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
    
    def _load_shortcuts_data(self):
        """加载快捷键数据"""
        return {
            "全局快捷键": [
                {"shortcut": "Ctrl+Shift+S", "function": "启动/停止监控", "description": "全局快捷键，可在任何界面使用", "category": "核心功能", "priority": "高"},
                {"shortcut": "Ctrl+Shift+C", "function": "快速截图识别", "description": "立即进行截图OCR识别", "category": "核心功能", "priority": "高"},
                {"shortcut": "Ctrl+Shift+V", "function": "剪贴板识别", "description": "识别剪贴板中的图片", "category": "核心功能", "priority": "高"},
            ],
            "界面操作": [
                {"shortcut": "Ctrl+C", "function": "复制识别结果", "description": "复制当前识别的文本内容", "category": "基本操作", "priority": "高"},
                {"shortcut": "Ctrl+V", "function": "粘贴文本", "description": "粘贴剪贴板内容", "category": "基本操作", "priority": "高"},
                {"shortcut": "Ctrl+S", "function": "保存设置", "description": "保存当前配置设置", "category": "基本操作", "priority": "中"},
                {"shortcut": "Ctrl+Z", "function": "撤销操作", "description": "撤销上一步操作", "category": "基本操作", "priority": "中"},
                {"shortcut": "Ctrl+Y", "function": "重做操作", "description": "重做已撤销的操作", "category": "基本操作", "priority": "中"},
                {"shortcut": "F1", "function": "打开帮助", "description": "显示帮助文档", "category": "基本操作", "priority": "低"},
                {"shortcut": "F5", "function": "刷新界面", "description": "刷新当前界面内容", "category": "基本操作", "priority": "低"},
                {"shortcut": "Esc", "function": "关闭窗口", "description": "关闭当前对话框或窗口", "category": "基本操作", "priority": "中"},
            ],
            "OCR功能": [
                {"shortcut": "F2", "function": "开始截图识别", "description": "进入截图模式进行OCR识别", "category": "OCR操作", "priority": "高"},
                {"shortcut": "F3", "function": "剪贴板图片识别", "description": "识别剪贴板中的图片内容", "category": "OCR操作", "priority": "高"},
                {"shortcut": "F4", "function": "批量识别文件", "description": "批量处理多个图片文件", "category": "OCR操作", "priority": "中"},
                {"shortcut": "Ctrl+F2", "function": "区域截图识别", "description": "选择特定区域进行识别", "category": "OCR操作", "priority": "高"},
                {"shortcut": "Ctrl+F3", "function": "全屏截图识别", "description": "对整个屏幕进行OCR识别", "category": "OCR操作", "priority": "中"},
                {"shortcut": "Alt+F2", "function": "延时截图识别", "description": "延时3秒后进行截图识别", "category": "OCR操作", "priority": "低"},
            ],
            "窗口管理": [
                {"shortcut": "Ctrl+M", "function": "最小化到托盘", "description": "将程序最小化到系统托盘", "category": "窗口操作", "priority": "中"},
                {"shortcut": "Ctrl+Alt+H", "function": "隐藏/显示主窗口", "description": "切换主窗口的显示状态", "category": "窗口操作", "priority": "中"},
                {"shortcut": "Ctrl+T", "function": "置顶/取消置顶", "description": "切换窗口置顶状态", "category": "窗口操作", "priority": "低"},
                {"shortcut": "Alt+Tab", "function": "切换窗口", "description": "在打开的窗口间切换", "category": "窗口操作", "priority": "低"},
                {"shortcut": "Ctrl+W", "function": "关闭当前标签", "description": "关闭当前活动的标签页", "category": "窗口操作", "priority": "中"},
                {"shortcut": "Ctrl+Q", "function": "退出程序", "description": "完全退出应用程序", "category": "窗口操作", "priority": "中"},
            ],
            "设置管理": [
                {"shortcut": "Ctrl+,", "function": "打开设置面板", "description": "打开程序设置界面", "category": "设置操作", "priority": "中"},
                {"shortcut": "Ctrl+Shift+T", "function": "切换主题", "description": "在浅色和深色主题间切换", "category": "设置操作", "priority": "低"},
                {"shortcut": "Ctrl+R", "function": "重置设置", "description": "恢复默认设置配置", "category": "设置操作", "priority": "低"},
                {"shortcut": "Ctrl+E", "function": "导出配置", "description": "导出当前配置到文件", "category": "设置操作", "priority": "低"},
                {"shortcut": "Ctrl+I", "function": "导入配置", "description": "从文件导入配置设置", "category": "设置操作", "priority": "低"},
            ],
            "高级功能": [
                {"shortcut": "Ctrl+D", "function": "打开调试模式", "description": "启用调试模式和详细日志", "category": "高级操作", "priority": "低"},
                {"shortcut": "Ctrl+L", "function": "查看日志", "description": "打开日志查看器", "category": "高级操作", "priority": "低"},
                {"shortcut": "Ctrl+K", "function": "管理关键词", "description": "打开关键词管理界面", "category": "高级操作", "priority": "中"},
                {"shortcut": "Ctrl+B", "function": "批处理模式", "description": "启用批量处理功能", "category": "高级操作", "priority": "中"},
                {"shortcut": "Ctrl+P", "function": "性能监控", "description": "查看程序性能统计", "category": "高级操作", "priority": "低"},
                {"shortcut": "F12", "function": "开发者工具", "description": "打开开发者调试工具", "category": "高级操作", "priority": "低"},
            ]
        }

    def apply_theme_styles(self):
        """应用主题样式"""
        try:
            # 使用新的统一分组框架样式管理器
            apply_group_framework_style(self)
        except Exception as e:
            print(f"应用主题样式时出错: {e}")
    
    def setup_ui(self):
        """设置用户界面"""
        main_layout = QVBoxLayout(self)
        setup_group_framework_layout(main_layout)
        
        # 顶部工具栏
        toolbar_layout = QHBoxLayout()
        
        # 搜索框
        search_label = QLabel("🔍 搜索:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入快捷键或功能名称...")
        self.search_input.textChanged.connect(self.filter_shortcuts)
        
        # 分类过滤器
        category_label = QLabel("📂 分类:")
        self.category_filter = QComboBox()
        self.category_filter.addItem("全部分类")
        self.category_filter.addItems(list(self.shortcuts_data.keys()))
        self.category_filter.currentTextChanged.connect(self.filter_shortcuts)
        
        # 优先级过滤器
        priority_label = QLabel("⭐ 优先级:")
        self.priority_filter = QComboBox()
        self.priority_filter.addItems(["全部", "高", "中", "低"])
        self.priority_filter.currentTextChanged.connect(self.filter_shortcuts)
        
        # 清除按钮
        clear_button = QPushButton("🗑️ 清除")
        clear_button.clicked.connect(self.clear_filters)
        
        toolbar_layout.addWidget(search_label)
        toolbar_layout.addWidget(self.search_input, 2)
        toolbar_layout.addWidget(category_label)
        toolbar_layout.addWidget(self.category_filter, 1)
        toolbar_layout.addWidget(priority_label)
        toolbar_layout.addWidget(self.priority_filter, 1)
        toolbar_layout.addWidget(clear_button)
        
        main_layout.addLayout(toolbar_layout)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：分类导航
        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(5, 5, 5, 5)
        
        nav_title = QLabel("📋 快捷键分类")
        nav_title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        nav_layout.addWidget(nav_title)
        
        # 分类列表
        self.category_list = QTableWidget()
        self.category_list.setColumnCount(2)
        self.category_list.setHorizontalHeaderLabels(["分类", "数量"])
        self.category_list.horizontalHeader().setStretchLastSection(True)
        self.category_list.verticalHeader().setVisible(False)
        self.category_list.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.category_list.setMaximumWidth(250)
        self.category_list.itemClicked.connect(self.on_category_selected)
        
        nav_layout.addWidget(self.category_list)
        
        # 右侧：快捷键表格
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.setContentsMargins(5, 5, 5, 5)
        
        table_title = QLabel("⌨️ 快捷键详情")
        table_title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        table_layout.addWidget(table_title)
        
        # 快捷键表格
        self.shortcuts_table = QTableWidget()
        self.shortcuts_table.setColumnCount(5)
        self.shortcuts_table.setHorizontalHeaderLabels(["快捷键", "功能", "描述", "分类", "优先级"])
        
        # 设置表格属性
        header = self.shortcuts_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # 快捷键列
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 功能列
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # 描述列
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 分类列
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # 优先级列
        
        self.shortcuts_table.setAlternatingRowColors(True)
        self.shortcuts_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.shortcuts_table.setSortingEnabled(True)
        self.shortcuts_table.verticalHeader().setVisible(False)
        
        table_layout.addWidget(self.shortcuts_table)
        
        # 添加到分割器
        splitter.addWidget(nav_widget)
        splitter.addWidget(table_widget)
        splitter.setSizes([250, 650])
        
        main_layout.addWidget(splitter)
        
        # 底部状态栏
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("📊 显示所有快捷键")
        self.status_label.setStyleSheet("font-size: 12px;")
        
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        # 底部按钮
        export_button = QPushButton("📤 导出")
        export_button.clicked.connect(self.export_shortcuts)
        export_button.setToolTip("导出快捷键列表到文件")
        
        copy_button = QPushButton("📋 复制")
        copy_button.clicked.connect(self.copy_selected_shortcut)
        copy_button.setToolTip("复制选中的快捷键")
        
        customize_button = QPushButton("🎯 自定义")
        customize_button.clicked.connect(self.open_customize_shortcuts)
        customize_button.setToolTip("打开快捷键自定义设置")
        
        close_button = QPushButton("❌ 关闭")
        close_button.clicked.connect(self.close)
        close_button.setDefault(True)
        
        status_layout.addWidget(export_button)
        status_layout.addWidget(copy_button)
        status_layout.addWidget(customize_button)
        status_layout.addWidget(close_button)
        
        main_layout.addLayout(status_layout)
        
        # 应用样式
        self.apply_table_styles()
    
    def init_data(self):
        """初始化数据显示"""
        self.populate_category_list()
        self.populate_shortcuts_table()
        self.update_status()
    
    def populate_category_list(self):
        """填充分类列表"""
        self.category_list.setRowCount(len(self.shortcuts_data))
        
        for row, (category, shortcuts) in enumerate(self.shortcuts_data.items()):
            # 分类名称
            category_item = QTableWidgetItem(category)
            category_item.setData(Qt.ItemDataRole.UserRole, category)
            self.category_list.setItem(row, 0, category_item)
            
            # 快捷键数量
            count_item = QTableWidgetItem(str(len(shortcuts)))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.category_list.setItem(row, 1, count_item)
    
    def populate_shortcuts_table(self, filter_category=None):
        """填充快捷键表格"""
        all_shortcuts = []
        
        for category, shortcuts in self.shortcuts_data.items():
            if filter_category and filter_category != "全部分类" and category != filter_category:
                continue
                
            for shortcut in shortcuts:
                all_shortcuts.append({
                    'shortcut': shortcut['shortcut'],
                    'function': shortcut['function'],
                    'description': shortcut['description'],
                    'category': category,
                    'priority': shortcut['priority']
                })
        
        self.shortcuts_table.setRowCount(len(all_shortcuts))
        
        for row, shortcut in enumerate(all_shortcuts):
            # 快捷键
            shortcut_item = QTableWidgetItem(shortcut['shortcut'])
            shortcut_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            self.shortcuts_table.setItem(row, 0, shortcut_item)
            
            # 功能
            function_item = QTableWidgetItem(shortcut['function'])
            self.shortcuts_table.setItem(row, 1, function_item)
            
            # 描述
            description_item = QTableWidgetItem(shortcut['description'])
            self.shortcuts_table.setItem(row, 2, description_item)
            
            # 分类
            category_item = QTableWidgetItem(shortcut['category'])
            self.shortcuts_table.setItem(row, 3, category_item)
            
            # 优先级
            priority_item = QTableWidgetItem(shortcut['priority'])
            priority_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # 移除自定义背景颜色设置，使用系统默认
            self.shortcuts_table.setItem(row, 4, priority_item)
    
    def filter_shortcuts(self):
        """过滤快捷键"""
        search_text = self.search_input.text().lower()
        category_filter = self.category_filter.currentText()
        priority_filter = self.priority_filter.currentText()
        
        for row in range(self.shortcuts_table.rowCount()):
            show_row = True
            
            # 搜索过滤
            if search_text:
                shortcut_text = self.shortcuts_table.item(row, 0).text().lower()
                function_text = self.shortcuts_table.item(row, 1).text().lower()
                description_text = self.shortcuts_table.item(row, 2).text().lower()
                
                if not (search_text in shortcut_text or 
                       search_text in function_text or 
                       search_text in description_text):
                    show_row = False
            
            # 分类过滤
            if category_filter != "全部分类":
                category_text = self.shortcuts_table.item(row, 3).text()
                if category_text != category_filter:
                    show_row = False
            
            # 优先级过滤
            if priority_filter != "全部":
                priority_text = self.shortcuts_table.item(row, 4).text()
                if priority_text != priority_filter:
                    show_row = False
            
            self.shortcuts_table.setRowHidden(row, not show_row)
        
        self.update_status()
    
    def clear_filters(self):
        """清除所有过滤器"""
        self.search_input.clear()
        self.category_filter.setCurrentText("全部分类")
        self.priority_filter.setCurrentText("全部")
        
        # 显示所有行
        for row in range(self.shortcuts_table.rowCount()):
            self.shortcuts_table.setRowHidden(row, False)
        
        self.update_status()
    
    def on_category_selected(self, item):
        """分类选择事件"""
        if item.column() == 0:  # 只响应分类列的点击
            category = item.data(Qt.ItemDataRole.UserRole)
            self.category_filter.setCurrentText(category)
    
    def update_status(self):
        """更新状态栏"""
        total_count = self.shortcuts_table.rowCount()
        visible_count = sum(1 for row in range(total_count) 
                          if not self.shortcuts_table.isRowHidden(row))
        
        if visible_count == total_count:
            self.status_label.setText(f"📊 显示所有快捷键 ({total_count} 个)")
        else:
            self.status_label.setText(f"📊 显示 {visible_count} / {total_count} 个快捷键")
    
    def export_shortcuts(self):
        """导出快捷键列表"""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出快捷键列表", "shortcuts.txt", 
            "文本文件 (*.txt);;CSV文件 (*.csv);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("快捷键列表\n")
                    f.write("=" * 50 + "\n\n")
                    
                    for category, shortcuts in self.shortcuts_data.items():
                        f.write(f"{category}\n")
                        f.write("-" * 30 + "\n")
                        
                        for shortcut in shortcuts:
                            f.write(f"{shortcut['shortcut']:<20} {shortcut['function']}\n")
                            f.write(f"{'':20} {shortcut['description']}\n\n")
                        
                        f.write("\n")
                
                QMessageBox.information(self, "成功", f"快捷键列表已导出到：\n{file_path}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"导出失败：{str(e)}")
    
    def copy_selected_shortcut(self):
        """复制选中的快捷键"""
        from PyQt6.QtWidgets import QApplication, QMessageBox
        
        current_row = self.shortcuts_table.currentRow()
        if current_row >= 0:
            shortcut = self.shortcuts_table.item(current_row, 0).text()
            function = self.shortcuts_table.item(current_row, 1).text()
            
            clipboard_text = f"{shortcut} - {function}"
            QApplication.clipboard().setText(clipboard_text)
            
            QMessageBox.information(self, "成功", f"已复制到剪贴板：\n{clipboard_text}")
        else:
            QMessageBox.warning(self, "提示", "请先选择一个快捷键")
    
    def apply_table_styles(self):
        """应用表格样式 - 移除自定义背景颜色，使用系统默认主题"""
        # 分类列表样式 - 移除所有自定义颜色，使用系统默认
        self.category_list.setStyleSheet("""
            QTableWidget {
                border-radius: 5px;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        
        # 快捷键表格样式 - 移除所有自定义颜色，使用系统默认
        self.shortcuts_table.setStyleSheet("""
            QTableWidget {
                border-radius: 5px;
            }
            QTableWidget::item {
                padding: 10px 8px;
            }
            QHeaderView::section {
                padding: 12px 8px;
                border: none;
                font-weight: bold;
            }
        """)
        
        # 搜索框样式 - 移除自定义颜色，使用系统默认
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border-radius: 20px;
                font-size: 14px;
            }
        """)
        
        # 移除下拉框的自定义样式，使用分组框架样式管理器的统一样式
        # 分组框架样式管理器已经包含了完整的下拉箭头样式设置
    
    def open_customize_shortcuts(self):
        """打开自定义快捷键设置"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "提示", "自定义快捷键功能正在开发中...")