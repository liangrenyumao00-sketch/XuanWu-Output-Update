# widgets/history_panel.py
"""
历史记录管理面板模块

该模块提供了OCR识别历史记录的管理界面，包括历史记录查看、搜索、
清理等功能。支持日志文件和截图文件的统一管理。

主要功能：
- 历史记录浏览：显示所有OCR识别历史
- 搜索过滤：支持关键词和时间戳搜索
- 文件清理：自动清理过期的日志和截图文件
- 设置管理：配置清理策略和保留天数
- 详细查看：查看单条记录的详细信息

依赖：
- PyQt6：GUI框架
- core.index_builder：日志索引构建
- core.i18n：国际化支持

作者：XuanWu OCR Team
版本：2.1.7
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel,
    QDialog, QHBoxLayout, QPushButton, QTabWidget, QTextEdit, QGraphicsView,
    QGraphicsScene, QGraphicsPixmapItem, QMessageBox, QSpinBox, QCheckBox,
    QFormLayout
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QSettings
import os
import json
import time
from core.index_builder import build_log_index
from core.i18n import t


class HistoryPanel(QWidget):
    """
    历史记录管理面板
    
    提供OCR识别历史记录的查看、搜索、管理和清理功能。
    支持日志文件和截图文件的统一管理。
    
    Attributes:
        LOG_FOLDER (str): 日志文件夹名称
        SCREENSHOT_FOLDER (str): 截图文件夹名称
        settings (QSettings): 应用程序设置对象
        search_bar (QLineEdit): 搜索输入框
        list_widget (QListWidget): 历史记录列表
        tabs (QTabWidget): 设置和操作选项卡
    
    Example:
        >>> panel = HistoryPanel()
        >>> panel.refresh()  # 刷新历史记录
        >>> panel.show()
    """
    LOG_FOLDER = "XuanWu_Logs"
    SCREENSHOT_FOLDER = "XuanWu_Screenshots"

    def __init__(self):
        super().__init__()

        self.settings = QSettings("MyApp", "XuanWu")

        layout = QVBoxLayout(self)

        # 搜索栏
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText(t('search_keywords_or_timestamp'))
        self.search_bar.textChanged.connect(self.filter_items)
        layout.addWidget(self.search_bar)

        # 历史记录列表
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.open_item)
        layout.addWidget(self.list_widget)
        
        # 创建标签页
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.settings_widget = QWidget()
        self.operations_widget = QWidget()
        self.tabs.addTab(self.settings_widget, t('cleanup_settings'))
        self.tabs.addTab(self.operations_widget, t('operations'))

        # 清理设置布局
        settings_layout = QFormLayout(self.settings_widget)

        # QSpinBox + 自定义 + / - 按钮
        self.days_spinbox = QSpinBox()
        self.days_spinbox.setRange(1, 365)
        self.days_spinbox.setValue(self.load_cleanup_days())
        self.days_spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)  # 隐藏默认箭头

        h_layout = QHBoxLayout()
        h_layout.addWidget(self.days_spinbox)

        self.plus_btn = QPushButton("+")
        self.plus_btn.setDefault(False)
        self.plus_btn.setAutoDefault(False)
        self.minus_btn = QPushButton("-")
        self.minus_btn.setDefault(False)
        self.minus_btn.setAutoDefault(False)
        self.plus_btn.setFixedSize(25, 25)
        self.minus_btn.setFixedSize(25, 25)
        h_layout.addWidget(self.minus_btn)
        h_layout.addWidget(self.plus_btn)

        # 绑定事件
        self.plus_btn.clicked.connect(lambda: self.days_spinbox.setValue(self.days_spinbox.value()+1))
        self.minus_btn.clicked.connect(lambda: self.days_spinbox.setValue(self.days_spinbox.value()-1))

        # 添加到表单布局
        settings_layout.addRow(f"{t('cleanup_old_records_days')}：", h_layout)

        self.cleanup_txt_checkbox = QCheckBox(t('cleanup_txt_log_files'))
        self.cleanup_png_checkbox = QCheckBox(t('cleanup_png_screenshot_files'))
        self.cleanup_txt_checkbox.setChecked(True)
        self.cleanup_png_checkbox.setChecked(True)

        self.save_button = QPushButton(t('保存设置'))
        self.save_button.setDefault(False)
        self.save_button.setAutoDefault(False)
        self.save_button.setToolTip(t('保存设置'))
        self.save_button.clicked.connect(self.save_settings)

        settings_layout.addRow(self.cleanup_txt_checkbox)
        settings_layout.addRow(self.cleanup_png_checkbox)
        settings_layout.addRow(self.save_button)

        # 操作布局
        operations_layout = QVBoxLayout(self.operations_widget)
        self.clear_button = QPushButton(t('cleanup_old_records'))
        self.clear_button.setDefault(False)
        self.clear_button.setAutoDefault(False)
        self.clear_button.setToolTip(t('cleanup_old_records'))
        self.clear_button.clicked.connect(self.cleanup_old_records)

        self.clear_all_button = QPushButton(t('cleanup_all_logs'))
        self.clear_all_button.setDefault(False)
        self.clear_all_button.setAutoDefault(False)
        self.clear_all_button.setToolTip(t('cleanup_all_logs'))
        self.clear_all_button.clicked.connect(self.cleanup_all_records)

        operations_layout.addWidget(self.clear_button)
        operations_layout.addWidget(self.clear_all_button)

        # 添加历史标签
        layout.addWidget(QLabel(t('hit_history')))

        self.entries = []
        self.refresh()
    
    def refresh_ui_text(self):
        """刷新UI文本的国际化显示"""
        try:
            from core.i18n import t
            
            # 更新搜索栏占位符
            self.search_bar.setPlaceholderText(t('请输入搜索关键词'))
            
            # 更新标签页标题
            self.tabs.setTabText(0, t('清理设置'))
            self.tabs.setTabText(1, t('基本操作'))
            
            # 更新复选框文本
            self.cleanup_txt_checkbox.setText(t('清理日志'))
            self.cleanup_png_checkbox.setText(t('清理资源'))
            
            # 更新按钮文本
            self.save_button.setText(t('保存设置'))
            self.clear_button.setText(t('清理旧记录'))
            self.clear_all_button.setText(t('清空历史'))
            
        except Exception as e:
            import logging
            logging.error(f"刷新HistoryPanel UI文本时出错: {e}")

    # ----------- 其余方法保持不变 -----------
    def refresh(self):
        self.entries = []
        self.list_widget.clear()
        index_path = os.path.join(self.LOG_FOLDER, "log_index.json")
        if not os.path.exists(index_path):
            return
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                self.entries = json.load(f)
            self.entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
            self.populate_list(self.entries)
        except Exception as e:
            print(f"刷新历史记录失败: {e}")
            QMessageBox.warning(self, t('error'), f"{t('load_log_index_failed')}: {e}")

    def populate_list(self, entries):
        self.list_widget.clear()
        for entry in entries:
            summary = f"{entry['keywords']} [{entry['timestamp']}]"
            icons = ""
            log_path = os.path.join(self.LOG_FOLDER, entry["log"])
            img_path = os.path.join(self.SCREENSHOT_FOLDER, os.path.basename(entry["image"]))
            if os.path.exists(log_path):
                icons += "📝"
            if os.path.exists(img_path):
                icons += "🖼️"
            if icons:
                summary = f"{icons} {summary}"
            item = QListWidgetItem(summary)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.list_widget.addItem(item)

    def filter_items(self, text):
        text_lower = text.strip().lower()
        filtered = []
        for entry in self.entries:
            summary = f"{entry['keywords']} [{entry['timestamp']}]"
            if text_lower in summary.lower():
                filtered.append(entry)
        filtered.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        self.populate_list(filtered)
    
    def open_item(self, item):
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry:
            log_path = os.path.join(self.LOG_FOLDER, entry["log"])
            img_path = os.path.join(self.SCREENSHOT_FOLDER, os.path.basename(entry["image"]))
            dialog = SelectDialog(entry, log_path, img_path)
            dialog.exec()

    def load_cleanup_days(self):
        return self.settings.value("cleanup_days", 3, type=int)

    def save_cleanup_days(self, days):
        self.settings.setValue("cleanup_days", days)

    def save_settings(self):
        days = self.days_spinbox.value()
        self.save_cleanup_days(days)
        QMessageBox.information(self, t('保存设置'), t('settings_saved_successfully'))

    def cleanup_files(self, days=None):
        removed_files = 0
        now = time.time()
        cutoff = now - days * 86400 if days is not None else None

        def should_remove(path):
            if cutoff is None:
                return True
            return os.path.getmtime(path) < cutoff

        file_types = []
        if self.cleanup_txt_checkbox.isChecked():
            file_types.append((self.LOG_FOLDER, ".txt"))
        if self.cleanup_png_checkbox.isChecked():
            file_types.append((self.SCREENSHOT_FOLDER, ".png"))

        for folder, ext in file_types:
            if not os.path.exists(folder):
                continue
            for fname in os.listdir(folder):
                if fname.endswith(ext):
                    path = os.path.join(folder, fname)
                    if os.path.isfile(path) and should_remove(path):
                        try:
                            os.remove(path)
                            removed_files += 1
                        except Exception as e:
                            print(f"❌ 删除失败 {path}: {e}")

        build_log_index()
        self.refresh()
        return removed_files

    def cleanup_old_records(self):
        days = self.days_spinbox.value()
        self.save_cleanup_days(days)
        removed_files = self.cleanup_files(days)
        QMessageBox.information(self, t('cleanup_completed'), f"✅ {t('cleaned_old_files').format(count=removed_files)}")

    def cleanup_all_records(self):
        removed_files = self.cleanup_files(None)
        QMessageBox.information(self, t('cleanup_completed'), f"✅ {t('cleaned_files').format(count=removed_files)}")
    
    def show_cleanup_dialog(self):
        """显示清理对话框，切换到清理设置选项卡"""
        # 切换到清理设置选项卡
        self.tabs.setCurrentIndex(0)  # 清理设置是第一个选项卡
        # 确保父窗口可见
        parent_window = self.window()
        if parent_window:
            parent_window.show()
            parent_window.raise_()
            parent_window.activateWindow()
        # 显示当前面板
        self.show()
        self.setVisible(True)
        # 将焦点设置到清理设置选项卡
        self.tabs.setFocus()




# --------- SelectDialog 和 PreviewDialog 保持不变 ---------
class SelectDialog(QDialog):
    def __init__(self, entry, log_path, img_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t('select_preview_method'))
        self.entry = entry
        self.log_path = log_path
        self.img_path = img_path
        
        # 应用主题样式
        self.apply_theme_styles()

        layout = QVBoxLayout(self)
        summary_label = QLabel(f"{t('record')}：{self.entry['keywords']} [{self.entry['timestamp']}]")
        layout.addWidget(summary_label)

        button_layout = QHBoxLayout()
        log_button = QPushButton(t('view_text_log'))
        log_button.setDefault(False)
        log_button.setAutoDefault(False)
        log_button.clicked.connect(self.view_log)
        img_button = QPushButton(t('view_image_log'))
        img_button.setDefault(False)
        img_button.setAutoDefault(False)
        img_button.clicked.connect(self.view_image)

        button_layout.addWidget(log_button)
        button_layout.addWidget(img_button)
        layout.addLayout(button_layout)

        self.setGeometry(100, 100, 400, 150)
        
        # 窗口居中显示
        if parent:
            self.move(parent.geometry().center() - self.rect().center())
    
    def apply_theme_styles(self):
        """应用主题样式"""
        try:
            from utils.theme import get_current_theme
            current_theme = get_current_theme()
            
            if current_theme == 'dark':
                self.setStyleSheet("""
                    QDialog {
                        background-color: #464646;
                        color: #ffffff;
                    }
                    QLabel {
                        color: #ffffff;
                        background-color: transparent;
                    }
                    QPushButton {
                        background-color: #555555;
                        color: #ffffff;
                        border: 1px solid #666666;
                        padding: 8px 16px;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background-color: #666666;
                    }
                    QCheckBox {
                        color: #ffffff;
                        spacing: 8px;
                    }
                """)
            else:
                self.setStyleSheet("")
        except Exception:
            pass

    def view_log(self):
        if os.path.exists(self.log_path):
            try:
                preview_dialog = PreviewDialog(self.log_path, is_image=False)
                preview_dialog.exec()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"打开日志失败: {e}")
        else:
            QMessageBox.warning(self, "错误", "日志文件不存在！")

    def view_image(self):
        if os.path.exists(self.img_path):
            try:
                preview_dialog = PreviewDialog(self.img_path, is_image=True)
                preview_dialog.exec()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"打开图片失败: {e}")
        else:
            QMessageBox.warning(self, "错误", "图片文件不存在！")


class PreviewDialog(QDialog):
    def __init__(self, file_path, is_image=True):
        super().__init__()
        self.is_image = is_image
        self.setWindowTitle("预览")
        
        # 应用主题样式
        self.apply_theme_styles()

        layout = QVBoxLayout(self)

        if self.is_image:
            self.view = QGraphicsView()
            scene = QGraphicsScene(self)
            pixmap = QPixmap(file_path)
            item = QGraphicsPixmapItem(pixmap)
            scene.addItem(item)
            self.view.setScene(scene)
            layout.addWidget(self.view)
        else:
            self.text_edit = QTextEdit()
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    text = file.read()
                self.text_edit.setText(text)
                self.text_edit.setReadOnly(True)
                layout.addWidget(self.text_edit)
            except Exception as e:
                self.text_edit.setText(f"加载日志失败: {e}")

        self.setGeometry(100, 100, 600, 400)
    
    def apply_theme_styles(self):
        """应用主题样式"""
        try:
            from utils.theme import get_current_theme
            current_theme = get_current_theme()
            
            if current_theme == 'dark':
                self.setStyleSheet("""
                    QDialog {
                        background-color: #464646;
                        color: #ffffff;
                    }
                    QTextEdit {
                        background-color: #555555;
                        color: #ffffff;
                        border: 1px solid #666666;
                        border-radius: 4px;
                    }
                    QGraphicsView {
                        background-color: #555555;
                        border: 1px solid #666666;
                        border-radius: 4px;
                    }
                """)
            else:
                self.setStyleSheet("")
        except Exception:
            pass


class HistoryDialog(QDialog):
    """历史记录独立弹窗对话框，内嵌 HistoryPanel"""
    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self.setWindowTitle(t('hit_history'))
        except Exception:
            self.setWindowTitle("历史记录")
        self.setModal(False)

        layout = QVBoxLayout(self)
        self.panel = HistoryPanel()
        layout.addWidget(self.panel)

        # 适当尺寸
        self.resize(800, 600)

        # 窗口居中显示
        try:
            if parent:
                self.move(parent.geometry().center() - self.rect().center())
        except Exception:
            pass

    def refresh(self):
        """刷新历史记录列表"""
        try:
            self.panel.refresh()
        except Exception as e:
            import logging
            logging.error(f"刷新历史记录对话框失败: {e}")

    def show_dialog(self):
        """显示弹窗并聚焦核心控件"""
        try:
            self.refresh()
            self.show()
            self.raise_()
            self.activateWindow()

            # 聚焦列表或搜索框
            try:
                if hasattr(self.panel, 'list_widget') and self.panel.list_widget is not None:
                    self.panel.list_widget.setFocus()
                elif hasattr(self.panel, 'search_bar') and self.panel.search_bar is not None:
                    self.panel.search_bar.setFocus()
                else:
                    self.setFocus()
            except Exception:
                pass
        except Exception as e:
            import logging
            logging.error(f"显示历史记录对话框失败: {e}")
