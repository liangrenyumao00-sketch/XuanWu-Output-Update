# widgets/update_log_window.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QPushButton, QTextEdit, QScrollArea, QFrame, QWidget,
    QMessageBox, QComboBox, QCheckBox, QLineEdit, QSplitter,
    QListWidget, QListWidgetItem, QTextBrowser
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QDesktopServices
from PyQt6.QtCore import QUrl
from core.group_framework_styles import apply_group_framework_style, setup_group_framework_layout
import webbrowser
import os
import re
from datetime import datetime

class UpdateLogWindow(QDialog):
    """更新日志窗口 - 简洁版本"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("炫舞OCR - 更新日志")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)
        self.setModal(True)
        
        # 应用主题样式
        self.apply_theme_styles()
        
        # 加载更新日志数据
        self.update_data = self.load_update_log()
        
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        setup_group_framework_layout(main_layout)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 顶部信息栏
        info_group = self.create_info_section()
        main_layout.addWidget(info_group)
        
        # 主要内容区域
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧版本列表
        version_list_group = self.create_version_list_section()
        content_splitter.addWidget(version_list_group)
        
        # 右侧详细内容
        detail_group = self.create_detail_section()
        content_splitter.addWidget(detail_group)
        
        # 设置分割器比例
        content_splitter.setSizes([250, 550])
        main_layout.addWidget(content_splitter)
        
        # 底部操作按钮
        button_layout = self.create_button_section()
        main_layout.addLayout(button_layout)
        
        # 初始化显示第一个版本
        if self.update_data:
            self.version_list.setCurrentRow(0)
            self.show_version_detail(0)

    def create_info_section(self):
        """创建信息栏"""
        info_group = QGroupBox("📋 更新日志概览")
        info_layout = QVBoxLayout(info_group)
        
        # 统计信息
        stats_layout = QHBoxLayout()
        
        total_versions = len(self.update_data)
        latest_version = self.update_data[0]['version'] if self.update_data else "未知"
        latest_date = self.update_data[0]['date'] if self.update_data else "未知"
        
        self.stats_label = QLabel(f"📊 总版本数: {total_versions} | 最新版本: {latest_version} | 发布日期: {latest_date}")
        stats_layout.addWidget(self.stats_label)
        
        stats_layout.addStretch()
        
        # 搜索框
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍 搜索:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索版本号或更新内容...")
        self.search_input.textChanged.connect(self.filter_versions)
        search_layout.addWidget(self.search_input)
        
        info_layout.addLayout(stats_layout)
        info_layout.addLayout(search_layout)
        
        return info_group

    def create_version_list_section(self):
        """创建版本列表区域"""
        version_group = QGroupBox("📦 版本列表")
        version_layout = QVBoxLayout(version_group)
        
        # 版本筛选
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("类型筛选:"))
        
        self.version_filter = QComboBox()
        self.version_filter.addItems(["全部", "主要版本", "次要版本", "补丁版本"])
        self.version_filter.currentTextChanged.connect(self.filter_versions)
        filter_layout.addWidget(self.version_filter)
        
        filter_layout.addStretch()
        version_layout.addLayout(filter_layout)
        
        # 版本列表
        self.version_list = QListWidget()
        self.version_list.currentRowChanged.connect(self.show_version_detail)
        
        # 填充版本列表
        self.populate_version_list()
        
        version_layout.addWidget(self.version_list)
        
        return version_group

    def create_detail_section(self):
        """创建详细内容区域"""
        detail_group = QGroupBox("📄 版本详情")
        detail_layout = QVBoxLayout(detail_group)
        
        # 版本信息头部
        self.version_header = QLabel("选择一个版本查看详情")
        self.version_header.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        detail_layout.addWidget(self.version_header)
        
        # 详细内容显示
        self.detail_browser = QTextBrowser()
        self.detail_browser.setOpenExternalLinks(True)
        detail_layout.addWidget(self.detail_browser)
        
        return detail_group

    def create_button_section(self):
        """创建底部按钮区域"""
        button_layout = QHBoxLayout()
        
        # 导出按钮
        export_btn = QPushButton("📤 导出更新日志")
        export_btn.clicked.connect(self.export_update_log)
        export_btn.setDefault(False)  # 禁用默认按钮行为
        export_btn.setAutoDefault(False)  # 禁用自动默认按钮行为
        button_layout.addWidget(export_btn)
        
        # 检查更新按钮
        check_update_btn = QPushButton("🔄 检查更新")
        check_update_btn.clicked.connect(self.check_for_updates)
        check_update_btn.setDefault(False)  # 禁用默认按钮行为
        check_update_btn.setAutoDefault(False)  # 禁用自动默认按钮行为
        button_layout.addWidget(check_update_btn)
        
        # 在线查看按钮
        online_btn = QPushButton("🌐 在线查看")
        online_btn.clicked.connect(self.view_online)
        online_btn.setDefault(False)  # 禁用默认按钮行为
        online_btn.setAutoDefault(False)  # 禁用自动默认按钮行为
        button_layout.addWidget(online_btn)
        
        button_layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        close_btn.setDefault(False)  # 禁用默认按钮行为
        close_btn.setAutoDefault(False)  # 禁用自动默认按钮行为
        button_layout.addWidget(close_btn)
        
        return button_layout

    def load_update_log(self):
        """加载更新日志数据"""
        html_log_path = os.path.join(os.getcwd(), "update_log.html")
        txt_log_path = os.path.join(os.getcwd(), "update_log.txt")
        
        if os.path.exists(html_log_path):
            return self.parse_html_log(html_log_path)
        elif os.path.exists(txt_log_path):
            return self.parse_txt_log(txt_log_path)
        else:
            return []

    def parse_html_log(self, file_path):
        """解析HTML格式的更新日志"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 简单的HTML解析，提取版本信息
            versions = []
            
            # 使用正则表达式提取版本信息
            version_pattern = r'<span class="version-number">(.*?)</span>.*?<span class="version-type.*?">(.*?)</span>.*?<span class="version-date">(.*?)</span>'
            version_matches = re.findall(version_pattern, content, re.DOTALL)
            
            for i, (version, type_info, date) in enumerate(version_matches):
                # 提取该版本的更新内容
                version_content = self.extract_version_content(content, version)
                
                versions.append({
                    'version': version.strip(),
                    'type': type_info.strip(),
                    'date': date.strip(),
                    'content': version_content,
                    'raw_html': version_content
                })
            
            return versions
            
        except Exception as e:
            print(f"解析HTML更新日志失败: {e}")
            return []

    def extract_version_content(self, html_content, version):
        """从HTML中提取特定版本的内容"""
        try:
            # 查找版本块的开始和结束
            version_start = html_content.find(f'<span class="version-number">{version}</span>')
            if version_start == -1:
                return "无法提取版本内容"
            
            # 查找下一个版本的开始位置
            next_version_start = html_content.find('<div class="version">', version_start + 1)
            if next_version_start == -1:
                version_block = html_content[version_start:]
            else:
                version_block = html_content[version_start:next_version_start]
            
            return version_block
            
        except Exception as e:
            return f"提取版本内容失败: {e}"

    def parse_txt_log(self, file_path):
        """解析文本格式的更新日志"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 简单的文本解析
            versions = []
            lines = content.split('\n')
            
            current_version = None
            current_content = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('v') or line.startswith('V'):
                    # 保存上一个版本
                    if current_version:
                        versions.append({
                            'version': current_version,
                            'type': '未知',
                            'date': '未知',
                            'content': '\n'.join(current_content),
                            'raw_html': '\n'.join(current_content)
                        })
                    
                    # 开始新版本
                    current_version = line
                    current_content = []
                else:
                    if line:
                        current_content.append(line)
            
            # 添加最后一个版本
            if current_version:
                versions.append({
                    'version': current_version,
                    'type': '未知',
                    'date': '未知',
                    'content': '\n'.join(current_content),
                    'raw_html': '\n'.join(current_content)
                })
            
            return versions
            
        except Exception as e:
            print(f"解析文本更新日志失败: {e}")
            return []

    def populate_version_list(self):
        """填充版本列表"""
        self.version_list.clear()
        
        for version_data in self.update_data:
            item_text = f"{version_data['version']} ({version_data['type']}) - {version_data['date']}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, version_data)
            self.version_list.addItem(item)

    def show_version_detail(self, row):
        """显示版本详情"""
        if row < 0 or row >= self.version_list.count():
            return
        
        item = self.version_list.item(row)
        version_data = item.data(Qt.ItemDataRole.UserRole)
        
        if version_data:
            # 更新头部信息
            header_text = f"📦 {version_data['version']} | 🏷️ {version_data['type']} | 📅 {version_data['date']}"
            self.version_header.setText(header_text)
            
            # 显示详细内容
            if 'raw_html' in version_data and version_data['raw_html']:
                self.detail_browser.setHtml(version_data['raw_html'])
            else:
                self.detail_browser.setPlainText(version_data['content'])

    def filter_versions(self):
        """筛选版本列表"""
        search_text = self.search_input.text().lower()
        filter_type = self.version_filter.currentText()
        
        for i in range(self.version_list.count()):
            item = self.version_list.item(i)
            version_data = item.data(Qt.ItemDataRole.UserRole)
            
            # 检查搜索条件
            search_match = True
            if search_text:
                search_match = (search_text in version_data['version'].lower() or 
                              search_text in version_data['content'].lower())
            
            # 检查类型筛选
            type_match = True
            if filter_type != "全部":
                type_match = filter_type in version_data['type']
            
            # 显示或隐藏项目
            item.setHidden(not (search_match and type_match))

    def export_update_log(self):
        """导出更新日志"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出更新日志", "update_log_export.html", 
                "HTML文件 (*.html);;文本文件 (*.txt);;所有文件 (*.*)"
            )
            
            if file_path:
                if file_path.endswith('.html'):
                    self.export_as_html(file_path)
                else:
                    self.export_as_text(file_path)
                
                QMessageBox.information(self, "导出成功", f"更新日志已导出到:\n{file_path}")
                
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出更新日志失败：{e}")

    def export_as_html(self, file_path):
        """导出为HTML格式"""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>炫舞OCR 更新日志</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .version { margin-bottom: 30px; border: 1px solid #ddd; padding: 15px; }
        .version-header { background: #f5f5f5; padding: 10px; margin: -15px -15px 15px -15px; }
        .version-number { font-weight: bold; color: #0078d4; }
        .version-type { background: #e1f5fe; padding: 2px 8px; border-radius: 4px; }
        .version-date { color: #666; }
    </style>
</head>
<body>
    <h1>炫舞OCR 更新日志</h1>
    <p>导出时间: {export_time}</p>
""".format(export_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        for version_data in self.update_data:
            html_content += f"""
    <div class="version">
        <div class="version-header">
            <span class="version-number">{version_data['version']}</span>
            <span class="version-type">{version_data['type']}</span>
            <span class="version-date">{version_data['date']}</span>
        </div>
        <div class="version-content">
            {version_data['content']}
        </div>
    </div>
"""
        
        html_content += """
</body>
</html>
"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def export_as_text(self, file_path):
        """导出为文本格式"""
        text_content = f"炫舞OCR 更新日志\n导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        for version_data in self.update_data:
            text_content += f"""
{version_data['version']} ({version_data['type']}) - {version_data['date']}
{'=' * 50}
{version_data['content']}

"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text_content)

    def check_for_updates(self):
        """检查更新"""
        QMessageBox.information(
            self, "检查更新", 
            "检查更新功能将在后台运行。\n\n"
            "如果有新版本可用，系统会自动通知您。\n"
            "您也可以访问官方网站获取最新版本信息。"
        )

    def view_online(self):
        """在线查看更新日志"""
        try:
            # 移除GitHub链接，改为显示提示信息
            QMessageBox.information(self, "提示", "在线更新日志功能已禁用")
        except Exception as e:
            QMessageBox.information(self, "提示", "无法打开浏览器，请手动访问项目主页查看最新更新")

    def apply_theme_styles(self):
        """应用主题样式"""
        try:
            # 使用新的统一分组框架样式管理器
            apply_group_framework_style(self)
        except Exception as e:
            print(f"应用主题样式时出错: {e}")