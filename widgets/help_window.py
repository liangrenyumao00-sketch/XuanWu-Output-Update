# widgets/help_window.py
"""
帮助窗口模块

该模块提供了一个综合的帮助系统界面，包含详细的使用说明、功能介绍、
故障排除指南、API文档等内容。支持搜索、导航、打印和导出功能。

主要功能：
- 分类导航：提供树形结构的帮助内容导航
- 内容搜索：支持全文搜索和高亮显示
- 多媒体支持：支持文本、图片、链接等多种内容格式
- 导出功能：支持打印和导出帮助内容
- 在线帮助：提供在线文档和反馈渠道

依赖：
- PyQt6：GUI框架
- core.group_framework_styles：样式管理
- webbrowser：浏览器操作

作者：XuanWu OCR Team
版本：2.1.7
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QPushButton, QTextEdit, QScrollArea, QFrame, QWidget,
    QMessageBox, QComboBox, QCheckBox, QLineEdit, QListWidget,
    QSplitter, QTabWidget, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QDesktopServices, QIcon, QKeyEvent
from PyQt6.QtCore import QUrl
from core.group_framework_styles import apply_group_framework_style
import webbrowser
import os


class HelpWindow(QDialog):
    """
    帮助窗口 - 增强版本
    
    提供完整的帮助系统界面，包含使用指南、功能说明、故障排除、
    API文档等多种帮助内容。支持搜索、导航、打印和导出等功能。
    
    Attributes:
        search_input (QLineEdit): 搜索输入框
        nav_tree (QTreeWidget): 左侧导航树
        content_area (QTextEdit): 右侧内容显示区域
        status_label (QLabel): 底部状态标签
    
    Signals:
        content_changed: 内容切换时发出的信号
        search_performed: 执行搜索时发出的信号
    
    Example:
        >>> help_window = HelpWindow(parent_widget)
        >>> help_window.show()
        >>> help_window.show_content("basic_usage")  # 显示特定内容
    """
    
    # 定义信号
    content_changed = pyqtSignal(str)
    search_performed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("帮助")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)
        self.setModal(True)
        
        # 使用系统默认样式，不应用自定义样式
        
        # 窗口居中显示
        if parent:
            self.move(parent.geometry().center() - self.rect().center())
        
        self.init_ui()
        
    def keyPressEvent(self, event: QKeyEvent):
        """处理键盘事件"""
        # 让所有按键保持原本功能，不做特殊处理
        # 由于已经禁用了所有按钮的默认行为，回车和空格键不会意外触发按钮
        super().keyPressEvent(event)
        
    def init_ui(self):
        """初始化界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 顶部工具栏
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(15, 10, 15, 10)
        
        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索帮助内容...")
        self.search_input.textChanged.connect(self.search_content)
        toolbar_layout.addWidget(QLabel("搜索:"))
        toolbar_layout.addWidget(self.search_input)
        
        toolbar_layout.addStretch()
        
        # 工具按钮
        print_btn = QPushButton("打印")
        print_btn.clicked.connect(self.print_help)
        print_btn.setDefault(False)  # 禁用默认按钮行为
        print_btn.setAutoDefault(False)  # 禁用自动默认按钮行为
        toolbar_layout.addWidget(print_btn)
        
        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self.export_help)
        export_btn.setDefault(False)  # 禁用默认按钮行为
        export_btn.setAutoDefault(False)  # 禁用自动默认按钮行为
        toolbar_layout.addWidget(export_btn)
        
        main_layout.addLayout(toolbar_layout)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧导航树
        self.nav_tree = QTreeWidget()
        self.nav_tree.setHeaderLabel("帮助目录")
        self.nav_tree.setMaximumWidth(250)
        self.nav_tree.itemClicked.connect(self.on_nav_item_clicked)
        self.setup_navigation_tree()
        splitter.addWidget(self.nav_tree)
        
        # 右侧内容区域
        self.content_area = QTextEdit()
        self.content_area.setReadOnly(True)
        self.setup_default_content()
        splitter.addWidget(self.content_area)
        
        # 设置分割器比例
        splitter.setSizes([250, 650])
        main_layout.addWidget(splitter)
        
        # 底部状态栏
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(15, 5, 15, 10)
        
        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        # 底部按钮
        online_help_btn = QPushButton("在线文档")
        online_help_btn.clicked.connect(self.open_online_help)
        online_help_btn.setDefault(False)  # 禁用默认按钮行为
        online_help_btn.setAutoDefault(False)  # 禁用自动默认按钮行为
        status_layout.addWidget(online_help_btn)
        
        feedback_btn = QPushButton("问题反馈")
        feedback_btn.clicked.connect(self.open_feedback)
        feedback_btn.setDefault(False)  # 禁用默认按钮行为
        feedback_btn.setAutoDefault(False)  # 禁用自动默认按钮行为
        status_layout.addWidget(feedback_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(False)  # 禁用默认按钮行为
        close_btn.setAutoDefault(False)  # 禁用自动默认按钮行为
        status_layout.addWidget(close_btn)
        
        main_layout.addLayout(status_layout)
    
    def setup_navigation_tree(self):
        """设置导航树"""
        # 快速开始
        quick_start = QTreeWidgetItem(self.nav_tree, ["🚀 快速开始"])
        QTreeWidgetItem(quick_start, ["安装与配置"])
        QTreeWidgetItem(quick_start, ["第一次使用"])
        QTreeWidgetItem(quick_start, ["基本操作流程"])
        
        # 功能详解
        features = QTreeWidgetItem(self.nav_tree, ["⚙️ 功能详解"])
        QTreeWidgetItem(features, ["OCR引擎"])
        QTreeWidgetItem(features, ["关键词面板"])
        QTreeWidgetItem(features, ["区域选择器"])
        QTreeWidgetItem(features, ["实时监控"])
        QTreeWidgetItem(features, ["历史记录"])
        QTreeWidgetItem(features, ["数据分析"])
        
        # 设置配置
        settings = QTreeWidgetItem(self.nav_tree, ["🔧 设置配置"])
        QTreeWidgetItem(settings, ["基本设置"])
        QTreeWidgetItem(settings, ["高级选项"])
        QTreeWidgetItem(settings, ["快捷键配置"])
        QTreeWidgetItem(settings, ["主题外观"])
        QTreeWidgetItem(settings, ["性能优化"])
        
        # 故障排除
        troubleshooting = QTreeWidgetItem(self.nav_tree, ["🔍 故障排除"])
        QTreeWidgetItem(troubleshooting, ["常见问题"])
        QTreeWidgetItem(troubleshooting, ["错误代码"])
        QTreeWidgetItem(troubleshooting, ["性能问题"])
        QTreeWidgetItem(troubleshooting, ["兼容性问题"])
        
        # 高级功能
        advanced = QTreeWidgetItem(self.nav_tree, ["🎯 高级功能"])
        QTreeWidgetItem(advanced, ["API接口"])
        QTreeWidgetItem(advanced, ["插件开发"])
        QTreeWidgetItem(advanced, ["自动化脚本"])
        QTreeWidgetItem(advanced, ["批量处理"])
        
        # 更新日志
        updates = QTreeWidgetItem(self.nav_tree, ["📝 更新日志"])
        QTreeWidgetItem(updates, ["最新版本"])
        QTreeWidgetItem(updates, ["历史版本"])
        QTreeWidgetItem(updates, ["已知问题"])
        
        # 展开所有项目
        self.nav_tree.expandAll()
    
    def setup_default_content(self):
        """设置默认显示内容"""
        # 显示欢迎页面内容
        welcome_content = self.get_welcome_content()
        self.content_area.setHtml(welcome_content)
    

    

    
    def search_content(self, text):
        """搜索帮助内容"""
        if not text.strip():
            self.status_label.setText("就绪")
            return
        
        search_text = text.lower()
        found_items = []
        
        # 搜索导航树标题
        iterator = QTreeWidgetItemIterator(self.nav_tree)
        while iterator.value():
            item = iterator.value()
            if search_text in item.text(0).lower():
                found_items.append((item, "标题匹配"))
            iterator += 1
        
        # 搜索内容区域
        content_matches = self.search_in_content(search_text)
        found_items.extend(content_matches)
        
        if found_items:
            self.status_label.setText(f"找到 {len(found_items)} 个匹配项")
            # 高亮第一个匹配项
            first_item = found_items[0][0]
            self.nav_tree.setCurrentItem(first_item)
            self.nav_tree.scrollToItem(first_item)
            self.on_nav_item_clicked(first_item, 0)
            
            # 如果是内容匹配，在内容区域高亮显示
            if len(found_items) > 0 and found_items[0][1] == "内容匹配":
                self.highlight_content_text(search_text)
        else:
            self.status_label.setText("未找到匹配内容")
    
    def search_in_content(self, search_text):
        """在所有内容中搜索"""
        content_matches = []
        
        # 定义所有可搜索的内容方法和对应的导航项
        content_methods = {
            "安装指南": self.get_installation_content,
            "首次使用": self.get_first_use_content,
            "基本工作流程": self.get_basic_workflow_content,
            "区域选择器": self.get_region_selector_content,
            "实时监控": self.get_realtime_monitoring_content,
            "历史记录": self.get_history_panel_content,
            "数据分析": self.get_analytics_panel_content,
            "基础设置": self.get_basic_settings_content,
            "高级选项": self.get_advanced_options_content,
            "主题外观": self.get_theme_appearance_content,
            "性能优化": self.get_performance_optimization_content,
            "OCR引擎": self.get_ocr_engine_content,
            "关键词面板": self.get_keyword_management_content,
            "常见问题": self.get_faq_content,
            "快捷键配置": self.get_shortcuts_content,
            "API接口": self.get_api_interface_content,
            "插件开发": self.get_plugin_development_content,
            "自动化脚本": self.get_automation_scripts_content,
            "批量处理": self.get_batch_processing_content,
            "最新版本": self.get_latest_version_content,
            "版本历史": self.get_version_history_content,
            "已知问题": self.get_known_issues_content,
            "错误代码": self.get_error_codes_content,
            "性能问题": self.get_performance_issues_content,
            "兼容性问题": self.get_compatibility_issues_content
        }
        
        # 在每个内容中搜索
        for item_name, content_method in content_methods.items():
            try:
                content = content_method()
                # 移除HTML标签进行纯文本搜索
                import re
                plain_text = re.sub(r'<[^>]+>', '', content).lower()
                if search_text in plain_text:
                    # 找到对应的导航项
                    iterator = QTreeWidgetItemIterator(self.nav_tree)
                    while iterator.value():
                        item = iterator.value()
                        clean_text = item.text(0).split(' ', 1)[-1] if ' ' in item.text(0) else item.text(0)
                        if clean_text == item_name:
                            content_matches.append((item, "内容匹配"))
                            break
                        iterator += 1
            except Exception:
                continue
        
        return content_matches
    
    def highlight_content_text(self, search_text):
        """在内容区域高亮显示搜索文本"""
        try:
            # 获取当前内容
            current_html = self.content_area.toHtml()
            
            # 简单的高亮实现
            highlighted_html = current_html.replace(
                search_text,
                f'<span style="background-color: yellow; font-weight: bold;">{search_text}</span>'
            )
            
            # 设置高亮后的内容
            self.content_area.setHtml(highlighted_html)
        except Exception:
            pass
    
    def on_nav_item_clicked(self, item, column):
        """导航项点击事件"""
        item_text = item.text(0)
        
        # 移除emoji前缀
        clean_text = item_text.split(' ', 1)[-1] if ' ' in item_text else item_text
        
        # 直接在内容区域显示对应内容
        content_html = self.get_content_for_item(clean_text)
        if content_html:
            self.content_area.setHtml(content_html)
            self.status_label.setText(f"正在显示: {clean_text}")
    
    def get_welcome_content(self):
        """获取欢迎页面内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8; padding: 20px;">
        <h1 style="color: #4a90e2; text-align: center; margin-bottom: 20px;">🎉 欢迎使用炫舞OCR</h1>
        
        <div style="text-align: center; margin-bottom: 30px;">
            <p style="font-size: 16px; color: #7f8c8d;">版本 2.1.7 - 专业OCR识别工具</p>
        </div>
        
        <h3 style="color: #4a90e2;">🌟 主要特性</h3>
        <ul style="font-size: 14px; line-height: 1.6;">
            <li><strong>多引擎支持</strong> - 集成百度、腾讯、阿里等多种OCR引擎</li>
            <li><strong>实时监控</strong> - 智能监控屏幕区域变化，自动识别文字</li>
            <li><strong>关键词匹配</strong> - 支持精确和模糊匹配，灵活配置</li>
            <li><strong>数据分析</strong> - 详细的识别统计和性能分析</li>
            <li><strong>云端同步</strong> - 配置和数据云端备份，多设备同步</li>
        </ul>
        
        <h3 style="color: #4a90e2;">🚀 快速开始指南</h3>
        <div style="padding: 15px; border-left: 4px solid #4a90e2; margin: 15px 0;">
            <p><strong>第一步：设置识别区域</strong></p>
            <p>点击"选择区域"按钮，拖拽选择需要监控的屏幕区域</p>
        </div>
        
        <div style="padding: 15px; border-left: 4px solid #4a90e2; margin: 15px 0;">
            <p><strong>第二步：配置关键词</strong></p>
            <p>在关键词面板中添加需要监控的文字内容</p>
        </div>
        
        <div style="padding: 15px; border-left: 4px solid #4a90e2; margin: 15px 0;">
            <p><strong>第三步：开始监控</strong></p>
            <p>点击"开始监控"按钮，系统将自动识别并匹配关键词</p>
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <p style="color: #7f8c8d;">点击左侧目录查看详细使用说明</p>
        </div>
        </div>
        """
    
    def get_region_selector_content(self):
        """获取区域选择内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🎯 区域选择</h2>
        
        <h3 style="color: #4a90e2;">功能概述</h3>
        <p>区域选择器允许您精确选择屏幕上需要监控的区域，支持拖拽选择和坐标调整。</p>
        
        <h3 style="color: #4a90e2;">使用方法</h3>
        <p>1. <strong>打开区域选择器</strong>：点击主界面的"选择区域"按钮</p>
        <p>2. <strong>拖拽选择</strong>：在屏幕上拖拽鼠标选择监控区域</p>
        <p>3. <strong>调整区域</strong>：拖拽区域边框进行精细调整</p>
        <p>4. <strong>确认选择</strong>：双击区域或按Enter键确认</p>
        <p>5. <strong>取消选择</strong>：按ESC键或右键取消</p>
        
        <h3 style="color: #4a90e2;">技术实现</h3>
        <p>• 使用 <strong>RegionSelector</strong> 类实现全屏覆盖选择</p>
        <p>• 支持实时预览和坐标显示</p>
        <p>• 自动保存选择的区域坐标到配置文件</p>
        <p>• 支持多显示器环境下的区域选择</p>
        
        <h3 style="color: #4a90e2;">快捷键支持</h3>
        <p>• <strong>Enter</strong>：确认当前选择</p>
        <p>• <strong>ESC</strong>：取消选择</p>
        <p>• <strong>方向键</strong>：微调选择区域</p>
        
        <h3 style="color: #e74c3c;">注意事项</h3>
        <p>• 选择区域不宜过大，影响识别性能</p>
        <p>• 建议选择文字清晰、对比度高的区域</p>
        <p>• 避免选择包含动态内容的区域</p>
        </div>
        """
    
    def get_realtime_monitoring_content(self):
        """获取实时监控内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">⚡ 实时监控</h2>
        
        <h3 style="color: #4a90e2;">监控机制</h3>
        <p>系统采用多线程架构，实时监控指定屏幕区域的文字变化：</p>
        <ul>
            <li><strong>OCR工作线程</strong>：负责图像识别和文字提取</li>
            <li><strong>关键词匹配线程</strong>：实时匹配识别结果与关键词</li>
            <li><strong>通知处理线程</strong>：处理匹配成功后的通知逻辑</li>
        </ul>
        
        <h3 style="color: #4a90e2;">监控参数</h3>
        <p>• <strong>识别间隔</strong>：可调整0.1-10秒，默认1秒</p>
        <p>• <strong>识别引擎</strong>：支持百度、腾讯、阿里等多种OCR引擎</p>
        <p>• <strong>图像预处理</strong>：自动缩放、降噪、增强对比度</p>
        <p>• <strong>错误重试</strong>：网络异常时自动重试机制</p>
        
        <h3 style="color: #4a90e2;">性能优化</h3>
        <p>• <strong>智能缓存</strong>：相同图像避免重复识别</p>
        <p>• <strong>增量识别</strong>：仅识别变化区域</p>
        <p>• <strong>资源管理</strong>：自动释放内存和临时文件</p>
        <p>• <strong>负载均衡</strong>：多API密钥轮询使用</p>
        
        <h3 style="color: #4a90e2;">监控状态</h3>
        <p>• <strong>运行中</strong>：正常监控识别</p>
        <p>• <strong>暂停</strong>：临时停止监控</p>
        <p>• <strong>错误</strong>：API异常或网络问题</p>
        <p>• <strong>限流</strong>：API调用频率受限</p>
        
        <h3 style="color: #e74c3c;">故障处理</h3>
        <p>• 自动检测API可用性</p>
        <p>• 网络异常时自动切换备用API</p>
        <p>• 详细错误日志记录和分析</p>
        <p>• 支持手动重启监控服务</p>
        </div>
        """
    
    def get_history_panel_content(self):
        """获取历史记录面板内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">📋 历史记录面板</h2>
        
        <h3 style="color: #4a90e2;">功能特性</h3>
        <p>历史记录面板提供完整的识别历史管理和分析功能：</p>
        <ul>
            <li><strong>识别记录</strong>：完整记录所有OCR识别结果</li>
            <li><strong>关键词匹配</strong>：显示匹配成功的关键词和时间</li>
            <li><strong>统计分析</strong>：按时间、关键词等维度统计</li>
            <li><strong>数据导出</strong>：支持CSV、Excel等格式导出</li>
        </ul>
        
        <h3 style="color: #4a90e2;">界面布局</h3>
        <p>• <strong>记录列表</strong>：时间倒序显示所有识别记录</p>
        <p>• <strong>筛选工具</strong>：按时间范围、关键词、状态筛选</p>
        <p>• <strong>搜索功能</strong>：全文搜索识别内容</p>
        <p>• <strong>操作按钮</strong>：清理、导出、刷新等功能</p>
        
        <h3 style="color: #4a90e2;">数据管理</h3>
        <p>• <strong>自动清理</strong>：可设置保留天数，自动清理过期记录</p>
        <p>• <strong>手动清理</strong>：支持批量删除和选择性清理</p>
        <p>• <strong>数据备份</strong>：集成到系统备份功能中</p>
        <p>• <strong>云端同步</strong>：支持历史记录云端备份</p>
        
        <h3 style="color: #4a90e2;">统计功能</h3>
        <p>• <strong>识别统计</strong>：每日/每周/每月识别次数</p>
        <p>• <strong>关键词统计</strong>：各关键词匹配频率</p>
        <p>• <strong>成功率统计</strong>：OCR识别成功率分析</p>
        <p>• <strong>性能统计</strong>：平均响应时间和资源使用</p>
        
        <h3 style="color: #4a90e2;">技术实现</h3>
        <p>• 使用 <strong>SQLite</strong> 数据库存储历史记录</p>
        <p>• 支持大数据量的分页显示和快速查询</p>
        <p>• 异步加载避免界面卡顿</p>
        <p>• 内存优化和垃圾回收机制</p>
        </div>
        """
    
    def get_analytics_panel_content(self):
        """获取数据分析面板内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">📊 数据分析面板</h2>
        
        <h3 style="color: #4a90e2;">分析维度</h3>
        <p>数据分析面板提供多维度的数据分析和可视化：</p>
        <ul>
            <li><strong>时间分析</strong>：按小时、天、周、月统计识别活动</li>
            <li><strong>关键词分析</strong>：热门关键词排行和趋势分析</li>
            <li><strong>性能分析</strong>：识别速度、成功率、资源使用分析</li>
            <li><strong>错误分析</strong>：错误类型统计和故障诊断</li>
        </ul>
        
        <h3 style="color: #4a90e2;">图表展示</h3>
        <p>• <strong>折线图</strong>：识别次数时间趋势</p>
        <p>• <strong>柱状图</strong>：关键词匹配频率对比</p>
        <p>• <strong>饼图</strong>：OCR引擎使用比例</p>
        <p>• <strong>热力图</strong>：识别活动时间分布</p>
        
        <h3 style="color: #4a90e2;">报告生成</h3>
        <p>• <strong>日报</strong>：每日识别活动摘要</p>
        <p>• <strong>周报</strong>：一周识别趋势和关键词统计</p>
        <p>• <strong>月报</strong>：月度性能分析和优化建议</p>
        <p>• <strong>自定义报告</strong>：按需生成特定时间段报告</p>
        
        <h3 style="color: #4a90e2;">性能监控</h3>
        <p>• <strong>系统资源</strong>：CPU、内存、磁盘使用情况</p>
        <p>• <strong>网络状态</strong>：API调用延迟和成功率</p>
        <p>• <strong>识别效率</strong>：平均识别时间和吞吐量</p>
        <p>• <strong>错误监控</strong>：实时错误率和异常告警</p>
        
        <h3 style="color: #4a90e2;">数据导出</h3>
        <p>• <strong>图表导出</strong>：PNG、PDF格式图表导出</p>
        <p>• <strong>数据导出</strong>：CSV、Excel格式原始数据</p>
        <p>• <strong>报告导出</strong>：HTML、PDF格式分析报告</p>
        <p>• <strong>定时导出</strong>：自动定期生成和发送报告</p>
        
        <h3 style="color: #4a90e2;">技术实现</h3>
        <p>• 使用 <strong>matplotlib</strong> 和 <strong>pyqtgraph</strong> 绘制图表</p>
        <p>• 集成 <strong>pandas</strong> 进行数据处理和分析</p>
        <p>• 支持实时数据更新和动态图表</p>
        <p>• 优化大数据量的处理性能</p>
        </div>
         """
    
    def get_basic_settings_content(self):
        """获取基本设置内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">⚙️ 基本设置</h2>
        
        <h3 style="color: #4a90e2;">OCR引擎配置</h3>
        <p>• <strong>百度OCR</strong>：高精度通用文字识别，支持中英文混合</p>
        <p>• <strong>腾讯OCR</strong>：快速识别，适合实时监控场景</p>
        <p>• <strong>阿里OCR</strong>：稳定可靠，支持多种语言</p>
        <p>• <strong>离线OCR</strong>：本地识别，无需网络连接</p>
        
        <h3 style="color: #4a90e2;">API密钥管理</h3>
        <p>• 支持多个API密钥轮询使用，提高并发能力</p>
        <p>• 自动检测密钥有效性和剩余额度</p>
        <p>• 密钥加密存储，保障账户安全</p>
        <p>• 支持密钥使用统计和成本分析</p>
        
        <h3 style="color: #4a90e2;">识别参数</h3>
        <p>• <strong>识别间隔</strong>：0.1-10秒可调，平衡性能与资源</p>
        <p>• <strong>图像质量</strong>：自动优化图像对比度和清晰度</p>
        <p>• <strong>语言设置</strong>：支持中文、英文、日文等多语言</p>
        <p>• <strong>置信度阈值</strong>：过滤低质量识别结果</p>
        
        <h3 style="color: #4a90e2;">通知设置</h3>
        <p>• <strong>桌面通知</strong>：关键词匹配时弹出系统通知</p>
        <p>• <strong>声音提醒</strong>：自定义提示音和音量</p>
        <p>• <strong>邮件通知</strong>：重要事件邮件提醒</p>
        <p>• <strong>微信推送</strong>：集成企业微信机器人</p>
        
        <h3 style="color: #4a90e2;">数据管理</h3>
        <p>• <strong>历史保留</strong>：设置识别记录保留天数</p>
        <p>• <strong>自动备份</strong>：定期备份配置和数据</p>
        <p>• <strong>数据清理</strong>：自动清理临时文件和缓存</p>
        <p>• <strong>导入导出</strong>：配置文件的导入导出功能</p>
        </div>
        """
    
    def get_advanced_options_content(self):
        """获取高级选项内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🔧 高级选项</h2>
        
        <h3 style="color: #4a90e2;">网络配置</h3>
        <p>• <strong>代理设置</strong>：支持HTTP/HTTPS/SOCKS5代理</p>
        <p>• <strong>超时设置</strong>：自定义网络请求超时时间</p>
        <p>• <strong>重试机制</strong>：网络异常时的重试次数和间隔</p>
        <p>• <strong>并发控制</strong>：限制同时进行的API调用数量</p>
        
        <h3 style="color: #4a90e2;">性能调优</h3>
        <p>• <strong>线程池大小</strong>：调整工作线程数量</p>
        <p>• <strong>内存限制</strong>：设置最大内存使用量</p>
        <p>• <strong>缓存策略</strong>：配置图像缓存和结果缓存</p>
        <p>• <strong>垃圾回收</strong>：自动内存清理频率设置</p>
        
        <h3 style="color: #4a90e2;">安全设置</h3>
        <p>• <strong>数据加密</strong>：敏感数据AES加密存储</p>
        <p>• <strong>访问控制</strong>：设置管理员密码保护</p>
        <p>• <strong>日志审计</strong>：详细记录用户操作日志</p>
        <p>• <strong>权限管理</strong>：细粒度功能权限控制</p>
        
        <h3 style="color: #4a90e2;">开发者选项</h3>
        <p>• <strong>调试模式</strong>：启用详细日志和调试信息</p>
        <p>• <strong>API测试</strong>：内置API接口测试工具</p>
        <p>• <strong>性能分析</strong>：实时性能监控和分析</p>
        <p>• <strong>插件开发</strong>：支持自定义插件扩展</p>
        
        <h3 style="color: #4a90e2;">实验性功能</h3>
        <p>• <strong>AI增强</strong>：集成机器学习优化识别</p>
        <p>• <strong>云端同步</strong>：配置和数据云端备份</p>
        <p>• <strong>多设备协同</strong>：跨设备数据同步</p>
        <p>• <strong>智能预测</strong>：基于历史数据的智能推荐</p>
        </div>
        """
    
    def get_theme_appearance_content(self):
        """获取主题外观内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🎨 主题外观</h2>
        
        <h3 style="color: #4a90e2;">主题系统</h3>
        <p>• <strong>浅色主题</strong>：经典白色背景，适合日间使用</p>
        <p>• <strong>深色主题</strong>：护眼黑色背景，适合夜间使用</p>
        <p>• <strong>自动切换</strong>：根据系统时间自动切换主题</p>
        <p>• <strong>自定义主题</strong>：支持用户自定义颜色方案</p>
        
        <h3 style="color: #4a90e2;">界面布局</h3>
        <p>• <strong>窗口大小</strong>：记住用户调整的窗口尺寸</p>
        <p>• <strong>面板布局</strong>：可拖拽调整各面板位置</p>
        <p>• <strong>工具栏</strong>：自定义工具栏按钮和顺序</p>
        <p>• <strong>状态栏</strong>：显示系统状态和统计信息</p>
        
        <h3 style="color: #4a90e2;">字体设置</h3>
        <p>• <strong>系统字体</strong>：使用系统默认字体</p>
        <p>• <strong>自定义字体</strong>：选择喜欢的字体族</p>
        <p>• <strong>字体大小</strong>：支持缩放调整字体大小</p>
        <p>• <strong>字体渲染</strong>：优化字体显示效果</p>
        
        <h3 style="color: #4a90e2;">颜色配置</h3>
        <p>• <strong>主色调</strong>：自定义界面主要颜色</p>
        <p>• <strong>强调色</strong>：设置按钮和链接颜色</p>
        <p>• <strong>背景色</strong>：调整窗口和面板背景</p>
        <p>• <strong>文字色</strong>：设置各级文字颜色</p>
        
        <h3 style="color: #4a90e2;">动画效果</h3>
        <p>• <strong>窗口动画</strong>：窗口打开关闭动画</p>
        <p>• <strong>过渡效果</strong>：界面切换平滑过渡</p>
        <p>• <strong>加载动画</strong>：数据加载时的动画提示</p>
        <p>• <strong>禁用动画</strong>：关闭所有动画效果</p>
        
        <h3 style="color: #4a90e2;">可访问性</h3>
        <p>• <strong>高对比度</strong>：提高界面对比度</p>
        <p>• <strong>大字体模式</strong>：放大所有文字显示</p>
        <p>• <strong>键盘导航</strong>：完整的键盘操作支持</p>
        <p>• <strong>屏幕阅读器</strong>：兼容辅助阅读软件</p>
        </div>
        """
    
    def get_performance_optimization_content(self):
        """获取性能优化内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🚀 性能优化</h2>
        
        <h3 style="color: #4a90e2;">系统资源监控</h3>
        <p>• <strong>CPU使用率</strong>：实时监控CPU占用情况</p>
        <p>• <strong>内存使用</strong>：跟踪内存分配和释放</p>
        <p>• <strong>磁盘I/O</strong>：监控文件读写性能</p>
        <p>• <strong>网络流量</strong>：统计API调用网络使用</p>
        
        <h3 style="color: #4a90e2;">性能优化策略</h3>
        <p>• <strong>智能缓存</strong>：缓存重复图像避免重复识别</p>
        <p>• <strong>异步处理</strong>：多线程并行处理提高效率</p>
        <p>• <strong>资源池化</strong>：复用网络连接和对象实例</p>
        <p>• <strong>延迟加载</strong>：按需加载减少启动时间</p>
        
        <h3 style="color: #4a90e2;">识别优化</h3>
        <p>• <strong>图像预处理</strong>：优化图像质量提高识别率</p>
        <p>• <strong>区域检测</strong>：智能检测文字区域</p>
        <p>• <strong>增量识别</strong>：只识别变化的区域</p>
        <p>• <strong>结果缓存</strong>：缓存识别结果避免重复计算</p>
        
        <h3 style="color: #4a90e2;">网络优化</h3>
        <p>• <strong>连接复用</strong>：保持长连接减少握手开销</p>
        <p>• <strong>请求合并</strong>：批量处理多个请求</p>
        <p>• <strong>压缩传输</strong>：启用数据压缩减少传输量</p>
        <p>• <strong>CDN加速</strong>：使用就近节点提高速度</p>
        
        <h3 style="color: #4a90e2;">内存管理</h3>
        <p>• <strong>垃圾回收</strong>：定期清理无用对象</p>
        <p>• <strong>内存池</strong>：预分配内存减少分配开销</p>
        <p>• <strong>弱引用</strong>：避免循环引用导致内存泄漏</p>
        <p>• <strong>内存监控</strong>：实时监控内存使用情况</p>
        
        <h3 style="color: #4a90e2;">性能调优建议</h3>
        <p>• <strong>硬件要求</strong>：推荐配置和最低要求</p>
        <p>• <strong>系统设置</strong>：操作系统优化建议</p>
        <p>• <strong>软件配置</strong>：程序参数调优指南</p>
        <p>• <strong>故障排除</strong>：常见性能问题解决方案</p>
        </div>
         """
    
    def get_error_codes_content(self):
        """获取错误代码内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">❌ 错误代码</h2>
        
        <h3 style="color: #4a90e2;">OCR识别错误</h3>
        <p>• <strong>E1001</strong>：API密钥无效或已过期</p>
        <p>• <strong>E1002</strong>：API调用次数超限</p>
        <p>• <strong>E1003</strong>：图像格式不支持</p>
        <p>• <strong>E1004</strong>：图像尺寸超出限制</p>
        <p>• <strong>E1005</strong>：网络连接超时</p>
        
        <h3 style="color: #4a90e2;">系统错误</h3>
        <p>• <strong>E2001</strong>：配置文件损坏</p>
        <p>• <strong>E2002</strong>：数据库连接失败</p>
        <p>• <strong>E2003</strong>：磁盘空间不足</p>
        <p>• <strong>E2004</strong>：权限不足</p>
        <p>• <strong>E2005</strong>：内存不足</p>
        
        <h3 style="color: #4a90e2;">网络错误</h3>
        <p>• <strong>E3001</strong>：DNS解析失败</p>
        <p>• <strong>E3002</strong>：代理服务器连接失败</p>
        <p>• <strong>E3003</strong>：SSL证书验证失败</p>
        <p>• <strong>E3004</strong>：HTTP状态码异常</p>
        <p>• <strong>E3005</strong>：响应数据格式错误</p>
        
        <h3 style="color: #4a90e2;">功能错误</h3>
        <p>• <strong>E4001</strong>：区域选择失败</p>
        <p>• <strong>E4002</strong>：关键词匹配异常</p>
        <p>• <strong>E4003</strong>：通知发送失败</p>
        <p>• <strong>E4004</strong>：数据导出错误</p>
        <p>• <strong>E4005</strong>：插件加载失败</p>
        
        <h3 style="color: #e74c3c;">错误处理建议</h3>
        <p>• 查看详细错误日志获取更多信息</p>
        <p>• 检查网络连接和代理设置</p>
        <p>• 验证API密钥有效性和余额</p>
        <p>• 重启程序或重置配置文件</p>
        <p>• 联系技术支持获取帮助</p>
        </div>
        """
    
    def get_performance_issues_content(self):
        """获取性能问题内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">⚡ 性能问题</h2>
        
        <h3 style="color: #4a90e2;">识别速度慢</h3>
        <p><strong>可能原因：</strong></p>
        <ul>
            <li>网络延迟过高</li>
            <li>图像尺寸过大</li>
            <li>API服务器负载高</li>
            <li>系统资源不足</li>
        </ul>
        <p><strong>解决方案：</strong></p>
        <ul>
            <li>调整识别间隔时间</li>
            <li>优化图像预处理</li>
            <li>使用多个API密钥轮询</li>
            <li>升级硬件配置</li>
        </ul>
        
        <h3 style="color: #4a90e2;">内存占用过高</h3>
        <p><strong>可能原因：</strong></p>
        <ul>
            <li>图像缓存过多</li>
            <li>历史记录积累</li>
            <li>内存泄漏</li>
            <li>大量并发请求</li>
        </ul>
        <p><strong>解决方案：</strong></p>
        <ul>
            <li>定期清理缓存</li>
            <li>设置历史记录保留期限</li>
            <li>重启程序释放内存</li>
            <li>调整并发数量</li>
        </ul>
        
        <h3 style="color: #4a90e2;">CPU使用率高</h3>
        <p><strong>可能原因：</strong></p>
        <ul>
            <li>识别频率过高</li>
            <li>图像处理复杂</li>
            <li>多线程竞争</li>
            <li>后台任务过多</li>
        </ul>
        <p><strong>解决方案：</strong></p>
        <ul>
            <li>降低识别频率</li>
            <li>简化图像预处理</li>
            <li>优化线程池配置</li>
            <li>关闭不必要功能</li>
        </ul>
        
        <h3 style="color: #4a90e2;">界面卡顿</h3>
        <p><strong>可能原因：</strong></p>
        <ul>
            <li>UI线程阻塞</li>
            <li>数据量过大</li>
            <li>频繁界面更新</li>
            <li>动画效果过多</li>
        </ul>
        <p><strong>解决方案：</strong></p>
        <ul>
            <li>使用异步处理</li>
            <li>分页显示数据</li>
            <li>减少更新频率</li>
            <li>禁用动画效果</li>
        </ul>
        </div>
        """
    
    def get_compatibility_issues_content(self):
        """获取兼容性问题内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🔧 兼容性问题</h2>
        
        <h3 style="color: #4a90e2;">操作系统兼容性</h3>
        <p><strong>Windows系统：</strong></p>
        <ul>
            <li>支持Windows 10及以上版本</li>
            <li>需要.NET Framework 4.7.2或更高版本</li>
            <li>推荐使用64位系统</li>
            <li>需要管理员权限进行安装</li>
        </ul>
        
        <p><strong>macOS系统：</strong></p>
        <ul>
            <li>支持macOS 10.14及以上版本</li>
            <li>需要允许辅助功能权限</li>
            <li>可能需要关闭系统完整性保护</li>
            <li>Apple Silicon芯片完全兼容</li>
        </ul>
        
        <p><strong>Linux系统：</strong></p>
        <ul>
            <li>支持Ubuntu 18.04及以上版本</li>
            <li>需要安装Python 3.8+环境</li>
            <li>依赖X11窗口系统</li>
            <li>Wayland支持有限</li>
        </ul>
        
        <h3 style="color: #4a90e2;">显示器兼容性</h3>
        <p>• <strong>多显示器</strong>：完全支持多显示器环境</p>
        <p>• <strong>高DPI</strong>：自动适配高分辨率显示器</p>
        <p>• <strong>缩放比例</strong>：支持125%、150%、200%缩放</p>
        <p>• <strong>色彩深度</strong>：支持16位、24位、32位色彩</p>
        
        <h3 style="color: #4a90e2;">软件兼容性</h3>
        <p>• <strong>杀毒软件</strong>：可能被误报为恶意软件</p>
        <p>• <strong>防火墙</strong>：需要允许网络访问权限</p>
        <p>• <strong>其他OCR软件</strong>：可能存在快捷键冲突</p>
        <p>• <strong>远程桌面</strong>：部分功能在远程环境下受限</p>
        
        <h3 style="color: #4a90e2;">硬件兼容性</h3>
        <p>• <strong>最低配置</strong>：2GB内存，双核CPU</p>
        <p>• <strong>推荐配置</strong>：8GB内存，四核CPU</p>
        <p>• <strong>网络要求</strong>：稳定的互联网连接</p>
        <p>• <strong>存储空间</strong>：至少500MB可用空间</p>
        
        <h3 style="color: #e74c3c;">已知问题</h3>
        <p>• Windows 7系统部分功能不可用</p>
        <p>• 某些游戏全屏模式下无法截图</p>
        <p>• 虚拟机环境下性能可能下降</p>
        <p>• 部分企业网络环境下API调用受限</p>
        </div>
        """
    
    def get_api_interface_content(self):
        """获取API接口内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🔌 API接口</h2>
        
        <h3 style="color: #4a90e2;">支持的OCR服务</h3>
        <p>• <strong>百度OCR</strong>：通用文字识别、高精度版本</p>
        <p>• <strong>腾讯OCR</strong>：通用印刷体识别、快速版本</p>
        <p>• <strong>阿里OCR</strong>：文档图像识别、表格识别</p>
        <p>• <strong>Azure OCR</strong>：微软认知服务OCR</p>
        <p>• <strong>Google Vision</strong>：谷歌云视觉API</p>
        
        <h3 style="color: #4a90e2;">API配置管理</h3>
        <p>• <strong>密钥管理</strong>：支持多个API密钥轮询使用</p>
        <p>• <strong>服务切换</strong>：自动切换可用的API服务</p>
        <p>• <strong>负载均衡</strong>：智能分配请求到不同服务</p>
        <p>• <strong>成本控制</strong>：监控API调用成本和用量</p>
        
        <h3 style="color: #4a90e2;">接口参数配置</h3>
        <p>• <strong>识别语言</strong>：中文、英文、日文等多语言</p>
        <p>• <strong>识别精度</strong>：标准版、高精度版选择</p>
        <p>• <strong>返回格式</strong>：JSON、XML格式支持</p>
        <p>• <strong>超时设置</strong>：自定义请求超时时间</p>
        
        <h3 style="color: #4a90e2;">错误处理机制</h3>
        <p>• <strong>重试策略</strong>：指数退避重试算法</p>
        <p>• <strong>降级处理</strong>：主服务不可用时自动切换</p>
        <p>• <strong>错误记录</strong>：详细记录API调用错误</p>
        <p>• <strong>告警通知</strong>：API异常时及时通知用户</p>
        
        <h3 style="color: #4a90e2;">性能优化</h3>
        <p>• <strong>连接池</strong>：复用HTTP连接减少开销</p>
        <p>• <strong>并发控制</strong>：限制同时请求数量</p>
        <p>• <strong>缓存机制</strong>：缓存相同图像的识别结果</p>
        <p>• <strong>压缩传输</strong>：启用GZIP压缩减少传输量</p>
        
        <h3 style="color: #4a90e2;">自定义API</h3>
        <p>• <strong>私有部署</strong>：支持企业私有OCR服务</p>
        <p>• <strong>协议适配</strong>：HTTP/HTTPS协议支持</p>
        <p>• <strong>认证方式</strong>：API Key、OAuth2等认证</p>
        <p>• <strong>数据格式</strong>：自定义请求和响应格式</p>
        </div>
        """
    
    def get_plugin_development_content(self):
        """获取插件开发内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🔧 插件开发</h2>
        
        <h3 style="color: #4a90e2;">插件架构</h3>
        <p>• <strong>插件接口</strong>：标准化的插件开发接口</p>
        <p>• <strong>生命周期</strong>：插件加载、初始化、卸载管理</p>
        <p>• <strong>事件系统</strong>：基于事件驱动的插件通信</p>
        <p>• <strong>依赖管理</strong>：插件间依赖关系处理</p>
        
        <h3 style="color: #4a90e2;">开发环境</h3>
        <p>• <strong>开发语言</strong>：Python 3.8+</p>
        <p>• <strong>开发框架</strong>：基于PyQt5/PySide2</p>
        <p>• <strong>调试工具</strong>：内置插件调试器</p>
        <p>• <strong>文档工具</strong>：自动生成API文档</p>
        
        <h3 style="color: #4a90e2;">插件类型</h3>
        <p>• <strong>OCR引擎插件</strong>：扩展新的OCR识别服务</p>
        <p>• <strong>通知插件</strong>：自定义通知方式和渠道</p>
        <p>• <strong>数据处理插件</strong>：扩展数据分析和处理功能</p>
        <p>• <strong>界面插件</strong>：添加新的界面组件和功能</p>
        
        <h3 style="color: #4a90e2;">开发指南</h3>
        <p>• <strong>插件模板</strong>：提供标准插件开发模板</p>
        <p>• <strong>API文档</strong>：详细的插件开发API说明</p>
        <p>• <strong>示例代码</strong>：丰富的插件开发示例</p>
        <p>• <strong>最佳实践</strong>：插件开发最佳实践指南</p>
        
        <h3 style="color: #4a90e2;">插件管理</h3>
        <p>• <strong>安装卸载</strong>：图形化插件安装管理</p>
        <p>• <strong>版本控制</strong>：插件版本更新和回滚</p>
        <p>• <strong>权限控制</strong>：插件访问权限管理</p>
        <p>• <strong>性能监控</strong>：插件性能和资源使用监控</p>
        
        <h3 style="color: #4a90e2;">发布分发</h3>
        <p>• <strong>插件商店</strong>：官方插件商店平台</p>
        <p>• <strong>打包工具</strong>：自动化插件打包工具</p>
        <p>• <strong>签名验证</strong>：插件数字签名和验证</p>
        <p>• <strong>更新机制</strong>：自动检查和更新插件</p>
        </div>
         """
    
    def get_automation_scripts_content(self):
        """获取自动化脚本内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🤖 自动化脚本</h2>
        
        <h3 style="color: #4a90e2;">脚本引擎</h3>
        <p>• <strong>Python脚本</strong>：支持Python脚本自动化</p>
        <p>• <strong>JavaScript</strong>：内置V8引擎执行JS脚本</p>
        <p>• <strong>批处理脚本</strong>：Windows批处理文件支持</p>
        <p>• <strong>Shell脚本</strong>：Linux/macOS Shell脚本</p>
        
        <h3 style="color: #4a90e2;">触发条件</h3>
        <p>• <strong>关键词匹配</strong>：识别到特定关键词时触发</p>
        <p>• <strong>时间触发</strong>：定时执行脚本任务</p>
        <p>• <strong>事件触发</strong>：系统事件发生时执行</p>
        <p>• <strong>手动触发</strong>：用户手动执行脚本</p>
        
        <h3 style="color: #4a90e2;">脚本功能</h3>
        <p>• <strong>文件操作</strong>：自动创建、移动、删除文件</p>
        <p>• <strong>网络请求</strong>：发送HTTP请求和API调用</p>
        <p>• <strong>数据处理</strong>：处理识别结果和统计数据</p>
        <p>• <strong>系统集成</strong>：与其他软件和服务集成</p>
        
        <h3 style="color: #4a90e2;">安全机制</h3>
        <p>• <strong>沙箱执行</strong>：脚本在受限环境中运行</p>
        <p>• <strong>权限控制</strong>：限制脚本访问系统资源</p>
        <p>• <strong>代码审查</strong>：脚本安全性检查</p>
        <p>• <strong>执行监控</strong>：监控脚本执行状态和资源使用</p>
        
        <h3 style="color: #4a90e2;">脚本管理</h3>
        <p>• <strong>脚本编辑器</strong>：内置代码编辑器和调试器</p>
        <p>• <strong>版本控制</strong>：脚本版本管理和回滚</p>
        <p>• <strong>共享库</strong>：脚本模板和函数库</p>
        <p>• <strong>执行日志</strong>：详细记录脚本执行历史</p>
        </div>
        """
    
    def get_batch_processing_content(self):
        """获取批量处理内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">📦 批量处理</h2>
        
        <h3 style="color: #4a90e2;">批量识别</h3>
        <p>• <strong>图像批处理</strong>：一次性处理多个图像文件</p>
        <p>• <strong>文件夹扫描</strong>：自动扫描文件夹中的图像</p>
        <p>• <strong>格式支持</strong>：PNG、JPG、BMP、TIFF等格式</p>
        <p>• <strong>进度监控</strong>：实时显示处理进度和状态</p>
        
        <h3 style="color: #4a90e2;">批量配置</h3>
        <p>• <strong>识别参数</strong>：统一设置识别引擎和参数</p>
        <p>• <strong>输出格式</strong>：选择结果输出格式和位置</p>
        <p>• <strong>错误处理</strong>：设置错误重试和跳过策略</p>
        <p>• <strong>并发控制</strong>：调整同时处理的文件数量</p>
        
        <h3 style="color: #4a90e2;">结果处理</h3>
        <p>• <strong>结果合并</strong>：将多个识别结果合并</p>
        <p>• <strong>数据清洗</strong>：自动清理和格式化结果</p>
        <p>• <strong>统计分析</strong>：生成批处理统计报告</p>
        <p>• <strong>质量检查</strong>：检查识别结果质量</p>
        
        <h3 style="color: #4a90e2;">任务调度</h3>
        <p>• <strong>队列管理</strong>：批处理任务队列管理</p>
        <p>• <strong>优先级设置</strong>：设置任务处理优先级</p>
        <p>• <strong>定时执行</strong>：定时启动批处理任务</p>
        <p>• <strong>资源限制</strong>：控制批处理资源使用</p>
        
        <h3 style="color: #4a90e2;">性能优化</h3>
        <p>• <strong>多线程处理</strong>：并行处理提高效率</p>
        <p>• <strong>内存管理</strong>：优化大批量数据内存使用</p>
        <p>• <strong>缓存机制</strong>：避免重复处理相同文件</p>
        <p>• <strong>断点续传</strong>：支持中断后继续处理</p>
        </div>
        """
    
    def get_latest_version_content(self):
        """获取最新版本内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🆕 最新版本</h2>
        
        <h3 style="color: #4a90e2;">版本 2.1.7 (当前版本)</h3>
        <p><strong>发布日期：</strong>2024年1月</p>
        
        <h4 style="color: #27ae60;">✨ 新增功能</h4>
        <ul>
            <li>全新的统一分组框架界面设计</li>
            <li>增强的性能监控和分析功能</li>
            <li>改进的插件开发和管理系统</li>
            <li>新增自动化脚本执行引擎</li>
            <li>支持批量图像处理功能</li>
        </ul>
        
        <h4 style="color: #3498db;">🔧 功能改进</h4>
        <ul>
            <li>优化OCR识别速度和准确率</li>
            <li>改进内存管理和资源使用</li>
            <li>增强网络连接稳定性</li>
            <li>完善错误处理和重试机制</li>
            <li>优化用户界面响应速度</li>
        </ul>
        
        <h4 style="color: #e74c3c;">🐛 问题修复</h4>
        <ul>
            <li>修复高DPI显示器下界面缩放问题</li>
            <li>解决多显示器环境下区域选择异常</li>
            <li>修复长时间运行后内存泄漏问题</li>
            <li>解决某些情况下程序崩溃的问题</li>
            <li>修复配置文件损坏导致的启动失败</li>
        </ul>
        
        <h3 style="color: #4a90e2;">系统要求</h3>
        <p>• <strong>操作系统</strong>：Windows 10/11, macOS 10.14+, Ubuntu 18.04+</p>
        <p>• <strong>内存</strong>：最低2GB，推荐8GB</p>
        <p>• <strong>处理器</strong>：双核CPU，推荐四核</p>
        <p>• <strong>存储空间</strong>：500MB可用空间</p>
        <p>• <strong>网络</strong>：稳定的互联网连接</p>
        
        <h3 style="color: #4a90e2;">下载和安装</h3>
        <p>• <strong>官方网站</strong>：从官方网站下载最新版本</p>
        <p>• <strong>自动更新</strong>：程序内置自动更新功能</p>
        <p>• <strong>增量更新</strong>：支持增量更新减少下载量</p>
        <p>• <strong>备份恢复</strong>：更新前自动备份配置和数据</p>
        </div>
        """
    
    def get_version_history_content(self):
        """获取历史版本内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">📚 历史版本</h2>
        
        <h3 style="color: #4a90e2;">版本 2.1.6</h3>
        <p><strong>发布日期：</strong>2023年12月</p>
        <ul>
            <li>新增多语言OCR识别支持</li>
            <li>改进关键词匹配算法</li>
            <li>优化网络连接和重试机制</li>
            <li>修复若干界面显示问题</li>
        </ul>
        
        <h3 style="color: #4a90e2;">版本 2.1.5</h3>
        <p><strong>发布日期：</strong>2023年11月</p>
        <ul>
            <li>增加数据分析和统计功能</li>
            <li>支持自定义通知方式</li>
            <li>改进历史记录管理</li>
            <li>优化程序启动速度</li>
        </ul>
        
        <h3 style="color: #4a90e2;">版本 2.1.4</h3>
        <p><strong>发布日期：</strong>2023年10月</p>
        <ul>
            <li>新增深色主题支持</li>
            <li>改进区域选择功能</li>
            <li>增强API密钥管理</li>
            <li>修复内存使用问题</li>
        </ul>
        
        <h3 style="color: #4a90e2;">版本 2.1.3</h3>
        <p><strong>发布日期：</strong>2023年9月</p>
        <ul>
            <li>支持更多OCR服务提供商</li>
            <li>改进错误处理和日志记录</li>
            <li>优化图像预处理算法</li>
            <li>增加配置导入导出功能</li>
        </ul>
        
        <h3 style="color: #4a90e2;">版本 2.1.2</h3>
        <p><strong>发布日期：</strong>2023年8月</p>
        <ul>
            <li>新增实时性能监控</li>
            <li>改进多显示器支持</li>
            <li>优化识别准确率</li>
            <li>修复若干稳定性问题</li>
        </ul>
        
        <h3 style="color: #4a90e2;">版本 2.1.1</h3>
        <p><strong>发布日期：</strong>2023年7月</p>
        <ul>
            <li>首次发布正式版本</li>
            <li>基础OCR识别功能</li>
            <li>关键词监控和通知</li>
            <li>简单的历史记录管理</li>
        </ul>
        </div>
        """
    
    def get_known_issues_content(self):
        """获取已知问题内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">⚠️ 已知问题</h2>
        
        <h3 style="color: #e74c3c;">高优先级问题</h3>
        <p><strong>问题：</strong>在某些高DPI显示器上界面元素可能显示模糊</p>
        <p><strong>影响：</strong>界面显示质量下降</p>
        <p><strong>临时解决方案：</strong>调整系统DPI设置或使用兼容模式</p>
        <p><strong>计划修复版本：</strong>2.1.8</p>
        
        <p><strong>问题：</strong>长时间运行后可能出现内存使用持续增长</p>
        <p><strong>影响：</strong>系统性能下降</p>
        <p><strong>临时解决方案：</strong>定期重启程序</p>
        <p><strong>计划修复版本：</strong>2.1.8</p>
        
        <h3 style="color: #f39c12;">中等优先级问题</h3>
        <p><strong>问题：</strong>在虚拟机环境下截图功能可能不稳定</p>
        <p><strong>影响：</strong>区域选择和识别功能受限</p>
        <p><strong>临时解决方案：</strong>使用物理机或调整虚拟机设置</p>
        
        <p><strong>问题：</strong>某些企业防火墙可能阻止API调用</p>
        <p><strong>影响：</strong>OCR识别功能无法使用</p>
        <p><strong>临时解决方案：</strong>配置代理服务器或申请网络白名单</p>
        
        <h3 style="color: #3498db;">低优先级问题</h3>
        <p><strong>问题：</strong>部分快捷键在某些应用程序中可能冲突</p>
        <p><strong>影响：</strong>快捷键功能失效</p>
        <p><strong>临时解决方案：</strong>自定义快捷键组合</p>
        
        <p><strong>问题：</strong>深色主题下某些文字颜色对比度不够</p>
        <p><strong>影响：</strong>阅读体验略有影响</p>
        <p><strong>临时解决方案：</strong>切换到浅色主题</p>
        
        <h3 style="color: #4a90e2;">报告问题</h3>
        <p>如果您遇到其他问题，请通过以下方式报告：</p>
        <ul>
            <li>发送邮件到技术支持邮箱</li>
            <li>在官方论坛发布问题描述</li>
            <li>使用程序内置的反馈功能</li>
            <li>提供详细的错误日志和系统信息</li>
        </ul>
        
        <h3 style="color: #27ae60;">问题跟踪</h3>
        <p>• 所有已知问题都在积极修复中</p>
        <p>• 修复进度可在官方网站查看</p>
        <p>• 紧急问题会优先处理</p>
        <p>• 用户反馈的问题会及时响应</p>
        </div>
        """
    
    def get_content_for_item(self, item_name):
        """根据导航项获取内容"""
        if item_name == "安装与配置":
            return self.get_installation_content()
        elif item_name == "第一次使用":
            return self.get_first_use_content()
        elif item_name == "基本操作流程":
            return self.get_basic_workflow_content()
        elif item_name == "区域选择":
            return self.get_region_selector_content()
        elif item_name == "实时监控":
            return self.get_realtime_monitoring_content()
        elif item_name == "历史记录" or item_name == "历史记录面板":
            return self.get_history_panel_content()
        elif item_name == "数据分析" or item_name == "数据分析面板":
            return self.get_analytics_panel_content()
        elif item_name == "基本设置":
            return self.get_basic_settings_content()
        elif item_name == "高级选项":
            return self.get_advanced_options_content()
        elif item_name == "主题外观":
            return self.get_theme_appearance_content()
        elif item_name == "性能优化":
            return self.get_performance_optimization_content()
        elif item_name == "OCR识别引擎":
            return self.get_ocr_engine_content()
        elif item_name == "关键词管理":
            return self.get_keyword_management_content()
        elif item_name == "常见问题":
            return self.get_faq_content()
        elif item_name == "快捷键配置":
            return self.get_shortcuts_content()
        elif item_name == "API接口":
            return self.get_api_interface_content()
        elif item_name == "插件开发":
            return self.get_plugin_development_content()
        elif item_name == "自动化脚本":
            return self.get_automation_scripts_content()
        elif item_name == "批量处理":
            return self.get_batch_processing_content()
        elif item_name == "最新版本":
            return self.get_latest_version_content()
        elif item_name == "历史版本":
            return self.get_version_history_content()
        elif item_name == "已知问题":
            return self.get_known_issues_content()
        elif item_name == "错误代码":
            return self.get_error_codes_content()
        elif item_name == "性能问题":
            return self.get_performance_issues_content()
        elif item_name == "兼容性问题":
            return self.get_compatibility_issues_content()
        else:
            return self.get_welcome_content()
    

    
    def get_installation_content(self):
        """获取安装配置内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">📦 安装与配置</h2>
        
        <h3 style="color: #4a90e2;">系统要求</h3>
        <ul>
            <li>Windows 10 或更高版本</li>
            <li>至少 4GB 内存</li>
            <li>100MB 可用磁盘空间</li>
            <li>网络连接（用于OCR API调用）</li>
            <li>Python 3.10+ 运行环境</li>
        </ul>
        
        <h3 style="color: #4a90e2;">首次配置步骤</h3>
        <p>1. <strong>API密钥配置</strong>：设置 → API密钥设置，配置百度OCR API密钥</p>
        <p>2. <strong>选择OCR版本</strong>：支持 general（标准版）、accurate（高精度版）、webimage（网络图片）等</p>
        <p>3. <strong>快捷键设置</strong>：设置 → 快捷键配置，自定义全局快捷键</p>
        <p>4. <strong>主题设置</strong>：设置 → 程序主题切换，选择合适的界面主题</p>
        <p>5. <strong>启动密码</strong>：设置 → 启动密码保护，增强安全性</p>
        
        <h3 style="color: #e74c3c;">重要提示</h3>
        <p>• 首次运行需要管理员权限以注册全局快捷键</p>
        <p>• 确保网络连接正常，OCR识别需要调用在线API</p>
        <p>• 建议配置代理设置（如需要）：设置 → HTTP/HTTPS代理设置</p>
        <p>• 可在设置中调整日志级别和缓存大小以优化性能</p>
        </div>
        """
    
    def get_first_use_content(self):
        """获取第一次使用内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🚀 首次使用</h2>
        
        <h3 style="color: #4a90e2;">快速开始流程</h3>
        <p>1. <strong>" + t("help_start_program") + "</strong>：" + t("help_run_main_py") + "</p>
        <p>2. <strong>配置API密钥</strong>：设置 → API密钥设置，输入百度OCR的API Key和Secret Key</p>
        <p>3. <strong>添加关键词</strong>：在关键词面板输入要监控的文字，支持回车快速添加</p>
        <p>4. <strong>选择监控区域</strong>：使用区域选择器框选屏幕监控范围</p>
        <p>5. <strong>开始监控</strong>：点击控制面板的"开始监控"按钮</p>
        
        <h3 style="color: #4a90e2;">主要功能模块</h3>
        <ul>
            <li><strong>控制面板</strong>：启动/停止监控，调整识别间隔和匹配模式</li>
            <li><strong>关键词面板</strong>：添加、删除、管理监控关键词，支持导入导出</li>
            <li><strong>日志面板</strong>：实时显示OCR识别结果和关键词匹配情况</li>
            <li><strong>状态面板</strong>：显示API状态、识别统计和系统性能</li>
            <li><strong>历史面板</strong>：查看历史识别记录和匹配结果</li>
            <li><strong>分析面板</strong>：数据统计分析和可视化图表</li>
            <li><strong>开发者工具</strong>：调试功能、性能监控、日志管理</li>
        </ul>
        
        <h3 style="color: #e74c3c;">首次使用提示</h3>
        <p>• 建议先在小范围区域测试OCR识别效果</p>
        <p>• 可通过帮助 → 功能导览了解各模块详细功能</p>
        <p>• 遇到问题可查看帮助 → 故障排除向导</p>
        <p>• 支持邮件通知、云同步等高级功能配置</p>
        </div>
        """
    
    def get_basic_workflow_content(self):
        """获取基本操作流程内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">⚙️ 基本工作流程</h2>
        
        <h3 style="color: #4a90e2;">完整监控流程</h3>
        <div style="padding: 15px; margin: 15px 0;">
            <p><strong>第一步：API配置</strong></p>
            <p>设置 → API密钥设置，配置百度OCR的API Key和Secret Key</p>
        </div>
        
        <div style="padding: 15px; margin: 15px 0;">
            <p><strong>第二步：区域选择</strong></p>
            <p>点击区域选择器，拖拽框选需要监控的屏幕区域</p>
        </div>
        
        <div style="padding: 15px; margin: 15px 0;">
            <p><strong>第三步：关键词管理</strong></p>
            <p>在关键词面板添加目标文字，支持精确、包含、正则三种匹配模式</p>
        </div>
        
        <div style="padding: 15px; margin: 15px 0;">
            <p><strong>第四步：参数调整</strong></p>
            <p>设置识别间隔（默认0.6秒）、匹配模式、模糊匹配阈值等参数</p>
        </div>
        
        <div style="padding: 15px; margin: 15px 0;">
            <p><strong>第五步：启动监控</strong></p>
            <p>点击"开始监控"，系统开始定期截图识别</p>
        </div>
        
        <h3 style="color: #4a90e2;">技术实现原理</h3>
        <p>1. <strong>多线程截图</strong>：OCRWorker线程定时对指定区域截图</p>
        <p>2. <strong>API调用</strong>：将图像Base64编码后调用百度OCR API</p>
        <p>3. <strong>智能缓存</strong>：相同图像使用MD5哈希避免重复识别</p>
        <p>4. <strong>关键词匹配</strong>：支持精确、模糊、正则三种匹配算法</p>
        <p>5. <strong>结果处理</strong>：匹配成功触发通知、邮件、声音等动作</p>
        
        <h3 style="color: #e74c3c;">性能优化建议</h3>
        <p>• 识别间隔建议0.5-2秒，避免API频率限制</p>
        <p>• 大图像自动缩放至2048像素以内提升速度</p>
        <p>• 启用缓存机制减少重复API调用</p>
        <p>• 定期清理日志文件：设置 → 日志管理</p>
        </div>
        """
    
    def get_ocr_engine_content(self):
        """获取OCR引擎内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🔍 OCR识别引擎</h2>
        
        <h3 style="color: #4a90e2;">当前支持的百度OCR版本</h3>
        <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
        <tr>
            <th style="border: 1px solid #ddd; padding: 10px;">版本</th>
            <th style="border: 1px solid #ddd; padding: 10px;">API接口</th>
            <th style="border: 1px solid #ddd; padding: 10px;">特点</th>
            <th style="border: 1px solid #ddd; padding: 10px;">适用场景</th>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 10px;">general</td>
            <td style="border: 1px solid #ddd; padding: 10px;">通用文字识别（标准版）</td>
            <td style="border: 1px solid #ddd; padding: 10px;">速度快，成本低</td>
            <td style="border: 1px solid #ddd; padding: 10px;">一般文档、截图</td>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 10px;">accurate</td>
            <td style="border: 1px solid #ddd; padding: 10px;">通用文字识别（高精度版）</td>
            <td style="border: 1px solid #ddd; padding: 10px;">准确率更高</td>
            <td style="border: 1px solid #ddd; padding: 10px;">重要文档、复杂图像</td>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 10px;">webimage</td>
            <td style="border: 1px solid #ddd; padding: 10px;">网络图片文字识别</td>
            <td style="border: 1px solid #ddd; padding: 10px;">针对网络图片优化</td>
            <td style="border: 1px solid #ddd; padding: 10px;">网页截图、表情包</td>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 10px;">handwriting</td>
            <td style="border: 1px solid #ddd; padding: 10px;">手写文字识别</td>
            <td style="border: 1px solid #ddd; padding: 10px;">支持手写体</td>
            <td style="border: 1px solid #ddd; padding: 10px;">手写笔记、签名</td>
        </tr>
        </table>
        
        <h3 style="color: #1e3a8a;">API配置步骤</h3>
        <p>1. <strong>注册百度智能云</strong>：访问 https://cloud.baidu.com 注册账号</p>
        <p>2. <strong>创建应用</strong>：在文字识别控制台创建新应用</p>
        <p>3. <strong>获取密钥</strong>：复制API Key和Secret Key</p>
        <p>4. <strong>配置软件</strong>：设置 → API密钥设置，填入密钥信息</p>
        <p>5. <strong>选择版本</strong>：在控制面板选择合适的OCR版本</p>
        
        <h3 style="color: #e74c3c;">使用限制与优化</h3>
        <p>• <strong>QPS限制</strong>：免费版每秒2次调用，付费版可提升</p>
        <p>• <strong>图像大小</strong>：超过2048像素自动缩放以提升速度</p>
        <p>• <strong>缓存机制</strong>：相同图像使用MD5缓存避免重复调用</p>
        <p>• <strong>重试机制</strong>：网络失败自动重试，最多3次</p>
        <p>• <strong>超时设置</strong>：可在设置中调整连接超时时间</p>
        </div>
        """
    
    def get_keyword_management_content(self):
        """获取关键词管理内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">🏷️ 关键词管理</h2>
        
        <h3 style="color: #4a90e2;">添加关键词</h3>
        <p>1. 点击"添加关键词"按钮</p>
        <p>2. 输入要监控的文字内容</p>
        <p>3. 选择匹配模式：</p>
        <ul>
            <li><strong>精确匹配</strong>：完全相同才触发</li>
            <li><strong>包含匹配</strong>：包含关键词即触发</li>
            <li><strong>正则匹配</strong>：支持正则表达式</li>
        </ul>
        
        <h3 style="color: #4a90e2;">关键词分组</h3>
        <p>支持将关键词分组管理：</p>
        <ul>
            <li>创建不同的关键词组</li>
            <li>为每组设置不同的动作</li>
            <li>可以启用/禁用整个分组</li>
            <li>支持导入/导出分组配置</li>
        </ul>
        
        <h3 style="color: #4a90e2;">基本操作</h3>
        <p>1. <strong>添加关键词</strong>：在输入框输入文字，点击"添加"或按回车键</p>
        <p>2. <strong>删除关键词</strong>：选中列表中的关键词，点击"删除选中"</p>
        <p>3. <strong>防重复添加</strong>：系统自动检测重复关键词并提示</p>
        <p>4. <strong>自动保存</strong>：关键词变更自动保存到 target_keywords.txt</p>
        
        <h3 style="color: #4a90e2;">匹配模式设置</h3>
        <p>在控制面板可选择三种匹配模式：</p>
        <ul>
            <li><strong>精确匹配（exact）</strong>：文字完全相同才触发</li>
            <li><strong>包含匹配（contains）</strong>：识别文字包含关键词即触发</li>
            <li><strong>模糊匹配（fuzzy）</strong>：使用相似度算法，默认阈值0.85</li>
        </ul>
        
        <h3 style="color: #4a90e2;">批量导入导出</h3>
        <p>支持多种格式的关键词批量管理：</p>
        <ul>
            <li><strong>TXT格式</strong>：每行一个关键词，支持逗号、分号分隔</li>
            <li><strong>CSV格式</strong>：表格格式，自动检测分隔符</li>
            <li><strong>JSON格式</strong>：结构化数据，支持多种键名</li>
            <li><strong>合并模式</strong>：可选择与现有关键词合并或替换</li>
        </ul>
        
        <h3 style="color: #4a90e2;">邮件通知关键词</h3>
        <p>在邮件设置中可配置特殊的通知关键词：</p>
        <ul>
            <li>匹配到指定关键词时自动发送邮件</li>
            <li>支持动态主题色彩和自定义模板</li>
            <li>可设置不同关键词的不同邮件内容</li>
        </ul>
        
        <h3 style="color: #e74c3c;">使用建议</h3>
        <p>• 关键词不宜过多，建议控制在50个以内</p>
        <p>• 使用模糊匹配时注意调整阈值避免误触发</p>
        <p>• 定期使用导出功能备份关键词配置</p>
        <p>• 可通过历史面板查看关键词匹配统计</p>
        </div>
        """
    
    def get_faq_content(self):
        """获取常见问题内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">❓ 常见问题</h2>
        
        <h3 style="color: #e74c3c;">OCR识别问题</h3>
        <p><strong>Q: OCR识别不准确或失败？</strong></p>
        <p>A: 1. 检查百度OCR API密钥是否正确配置<br>
           2. 确保网络连接正常，可访问百度API服务<br>
           3. 尝试切换OCR版本：accurate（高精度）、webimage（网络图片）<br>
           4. 确保截图区域文字清晰，避免模糊或过小的文字<br>
           5. 检查API调用余额是否充足</p>
        
        <p><strong>Q: 识别速度很慢或超时？</strong></p>
        <p>A: 1. 检查网络连接速度和稳定性<br>
           2. 在设置中调整连接超时时间<br>
           3. 大图像会自动缩放，但仍建议选择合适的监控区域<br>
           4. 配置HTTP/HTTPS代理（如在企业网络环境）</p>
        
        <h3 style="color: #e74c3c;">系统性能问题</h3>
        <p><strong>Q: 程序占用资源过高？</strong></p>
        <p>A: 1. 调整识别间隔，建议0.5-2秒之间<br>
           2. 使用日志管理功能清理历史日志文件<br>
           3. 在设置中调整缓存大小限制<br>
           4. 减少同时监控的关键词数量<br>
           5. 定期重启程序释放内存</p>
        
        <h3 style="color: #e74c3c;">功能配置问题</h3>
        <p><strong>Q: 全局快捷键不生效？</strong></p>
        <p>A: 1. 确保以管理员权限运行程序<br>
           2. 检查快捷键是否与其他程序冲突<br>
           3. 在设置 → 快捷键配置中重新设置<br>
           4. 重启程序重新注册全局热键</p>
        
        <p><strong>Q: 如何备份和恢复配置？</strong></p>
        <p>A: 1. 使用设置 → 备份管理进行完整备份<br>
           2. 关键词可通过设置 → 关键词导入导出单独备份<br>
           3. 配置云同步实现自动备份<br>
           4. 手动备份配置文件和target_keywords.txt</p>
        
        <h3 style="color: #e74c3c;">高级功能问题</h3>
        <p><strong>Q: 邮件通知不工作？</strong></p>
        <p>A: 1. 检查SMTP服务器配置是否正确<br>
           2. 确认邮箱密码或应用专用密码<br>
           3. 检查防火墙是否阻止邮件发送<br>
           4. 测试邮件配置功能验证设置</p>
        
        <p><strong>Q: 云同步功能异常？</strong></p>
        <p>A: 1. 检查网络连接和云服务配置<br>
           2. 验证云存储账号权限<br>
           3. 查看同步日志了解具体错误<br>
           4. 尝试手动触发同步操作</p>
        </div>
        """
    
    def get_shortcuts_content(self):
        """获取快捷键内容"""
        return """
        <div style="font-family: 'Microsoft YaHei'; line-height: 1.8;">
        <h2 style="color: #4a90e2; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;">⌨️ 快捷键说明</h2>
        
        <h3 style="color: #4a90e2;">全局快捷键</h3>
        <p>程序支持自定义全局快捷键，可在任何界面下使用：</p>
        <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
        <tr>
            <th style="border: 1px solid #ddd; padding: 10px;">功能</th>
            <th style="border: 1px solid #ddd; padding: 10px;">默认快捷键</th>
            <th style="border: 1px solid #ddd; padding: 10px;">说明</th>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 10px;">主要功能切换</td>
            <td style="border: 1px solid #ddd; padding: 10px;">可自定义</td>
            <td style="border: 1px solid #ddd; padding: 10px;">启动/停止监控等核心功能</td>
        </tr>
        </table>
        
        <h3 style="color: #4a90e2;">界面内快捷键</h3>
        <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
        <tr>
            <th style="border: 1px solid #ddd; padding: 10px;">功能</th>
            <th style="border: 1px solid #ddd; padding: 10px;">快捷键</th>
            <th style="border: 1px solid #ddd; padding: 10px;">使用位置</th>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 10px;">添加关键词</td>
            <td style="border: 1px solid #ddd; padding: 10px;">Enter</td>
            <td style="border: 1px solid #ddd; padding: 10px;">关键词面板输入框</td>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 10px;">快速添加邮件关键词</td>
            <td style="border: 1px solid #ddd; padding: 10px;">Enter</td>
            <td style="border: 1px solid #ddd; padding: 10px;">邮件设置对话框</td>
        </tr>
        </table>
        
        <h3 style="color: #4a90e2;">快捷键配置</h3>
        <p>1. <strong>打开设置</strong>：设置 → 快捷键配置</p>
        <p>2. <strong>选择功能</strong>：从下拉列表选择要设置的功能</p>
        <p>3. <strong>录制快捷键</strong>：点击输入框，按下想要的快捷键组合</p>
        <p>4. <strong>保存设置</strong>：点击保存按钮应用新的快捷键</p>
        <p>5. <strong>重启生效</strong>：全局快捷键需要重启程序才能生效</p>
        
        <h3 style="color: #4a90e2;">快捷键技术实现</h3>
        <p>• 使用 <strong>pynput</strong> 库实现全局热键监听</p>
        <p>• 支持 Ctrl、Shift、Alt、Win 等修饰键组合</p>
        <p>• 自动解析快捷键字符串格式（如 "ctrl+shift+s"）</p>
        <p>• 线程化处理避免阻塞主界面</p>
        
        <h3 style="color: #e74c3c;">使用注意事项</h3>
        <p>• <strong>管理员权限</strong>：全局快捷键需要以管理员身份运行程序</p>
        <p>• <strong>避免冲突</strong>：选择不与系统或其他软件冲突的组合键</p>
        <p>• <strong>推荐格式</strong>：建议使用 Ctrl+Shift+字母 的组合</p>
        <p>• <strong>依赖检查</strong>：程序会自动检查pynput库是否安装</p>
        <p>• <strong>错误处理</strong>：快捷键注册失败会在日志中显示详细信息</p>
        </div>
        """
    

    
    def show_content(self, content_name):
        """显示指定内容"""
        # 查找并点击导航树中的对应项
        iterator = QTreeWidgetItemIterator(self.nav_tree)
        while iterator.value():
            item = iterator.value()
            if content_name in item.text(0):
                self.on_nav_item_clicked(item, 0)
                break
            iterator += 1
    
    def print_help(self):
        """打印帮助内容"""
        try:
            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
            printer = QPrinter()
            dialog = QPrintDialog(printer, self)
            if dialog.exec() == QPrintDialog.DialogCode.Accepted:
                self.content_area.print(printer)
                self.status_label.setText("打印完成")
            else:
                self.status_label.setText("打印已取消")
        except ImportError:
            QMessageBox.information(self, "提示", "打印功能需要安装PyQt6打印支持模块")
            self.status_label.setText("打印功能不可用")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"打印时发生错误：{str(e)}")
            self.status_label.setText("打印失败")
    
    def export_help(self):
        """导出帮助内容"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出帮助内容", "help_content.html", "HTML文件 (*.html);;文本文件 (*.txt)"
            )
            if file_path:
                content = self.content_area.toHtml() if file_path.endswith('.html') else self.content_area.toPlainText()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.status_label.setText(f"已导出到：{file_path}")
            else:
                self.status_label.setText("导出已取消")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"导出时发生错误：{str(e)}")
            self.status_label.setText("导出失败")
    
    def open_online_help(self):
        """打开在线帮助文档"""
        try:
            # 移除GitHub链接，改为显示提示信息
            QMessageBox.information(self, "提示", "在线帮助功能已禁用")
        except Exception as e:
            QMessageBox.information(self, "提示", "无法打开浏览器，请手动访问帮助文档")
    
    def open_feedback(self):
        """打开问题反馈页面"""
        try:
            # 移除GitHub链接，改为显示提示信息
            QMessageBox.information(self, "提示", "问题反馈功能已禁用")
        except Exception as e:
            QMessageBox.information(self, "提示", "无法打开浏览器，请手动访问反馈页面")
    
    def apply_group_framework_styles(self):
        """应用主题样式"""
        try:
            # 使用新的统一分组框架样式管理器
            apply_group_framework_style(self)
        except Exception as e:
            print(f"应用主题样式时出错: {e}")
