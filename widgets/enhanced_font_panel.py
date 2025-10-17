# widgets/enhanced_font_panel.py
"""
增强版字体大小调整设置面板
提供更丰富的字体设置功能，包括：
- 字体大小调整（滑块+数值输入）
- 字体系列选择
- 实时预览
- 预设字体大小快捷选项
- 字体样式设置（粗体、斜体）
- 导入/导出字体配置
"""

import json
import logging
from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QSpinBox, QSlider, QComboBox, QPushButton, QGroupBox,
    QCheckBox, QTextEdit, QScrollArea, QWidget, QSizePolicy,
    QMessageBox, QFileDialog, QButtonGroup, QRadioButton,
    QFrame, QSplitter, QTabWidget, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QFontDatabase, QPixmap, QPainter, QColor, QIcon

from core.settings import load_settings, save_settings, DEFAULT_SETTINGS
from core.i18n import t


class FontPreviewWidget(QTextEdit):
    """字体预览控件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(200)
        self.setMinimumHeight(120)
        
        # 设置预览文本
        self.preview_text = t("font_preview_sample")
        self.setText(self.preview_text)
        
        # 设置样式
        # 使用原生样式，移除自定义样式
    
    def update_font_preview(self, font_family: str, font_size: int, bold: bool = False, italic: bool = False):
        """更新字体预览"""
        font = QFont(font_family, font_size)
        font.setBold(bold)
        font.setItalic(italic)
        self.setFont(font)


class FontSizePresetWidget(QWidget):
    """字体大小预设控件"""
    
    size_selected = pyqtSignal(int)  # 选中字体大小信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QGridLayout()
        layout.setSpacing(8)
        
        # 预设字体大小
        preset_sizes = [
            (t("extra_small"), 8), (t("small"), 10), (t("default"), 12), (t("medium"), 14),
            (t("large"), 16), (t("extra_large"), 18), (t("super_large"), 24), (t("huge"), 32)
        ]
        
        self.button_group = QButtonGroup()
        
        for i, (name, size) in enumerate(preset_sizes):
            btn = QRadioButton(f"{name}\n{size}px")
            # 使用原生样式，移除自定义样式
            btn.clicked.connect(lambda checked, s=size: self.size_selected.emit(s))
            self.button_group.addButton(btn, size)
            
            row = i // 4
            col = i % 4
            layout.addWidget(btn, row, col)
        
        self.setLayout(layout)
    
    def set_current_size(self, size: int):
        """设置当前选中的字体大小"""
        button = self.button_group.button(size)
        if button:
            button.setChecked(True)
        else:
            # 如果不是预设大小，取消所有选择
            for btn in self.button_group.buttons():
                btn.setChecked(False)


class EnhancedFontDialog(QDialog):
    """增强版字体设置对话框"""
    
    settings_changed = pyqtSignal(dict)  # 设置改变信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self.font_database = QFontDatabase
        
        # 连接语言切换信号
        self.connect_language_signal()
        
        self.init_ui()
        self.load_values()
        self.setup_connections()
        
    def init_ui(self):
        self.setWindowTitle(t("enhanced_font_settings"))
        self.setMinimumSize(900, 700)
        self.resize(1000, 750)
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        
        # 基本设置选项卡
        basic_tab = QWidget()
        self.setup_basic_tab(basic_tab)
        self.tab_widget.addTab(basic_tab, t("basic_settings"))
        
        # 高级设置选项卡
        advanced_tab = QWidget()
        self.setup_advanced_tab(advanced_tab)
        self.tab_widget.addTab(advanced_tab, t("advanced_settings"))
        
        # 预览选项卡已删除，实时预览功能已集成到基本设置页面
        
        main_layout.addWidget(self.tab_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        # 导入导出按钮
        import_btn = QPushButton(t("import_config"))
        import_btn.clicked.connect(self.import_config)
        button_layout.addWidget(import_btn)
        
        export_btn = QPushButton(t("export_config"))
        export_btn.clicked.connect(self.export_config)
        button_layout.addWidget(export_btn)
        
        button_layout.addStretch()
        
        # 重置按钮
        reset_btn = QPushButton(t("reset_default"))
        reset_btn.clicked.connect(self.reset_to_default)
        button_layout.addWidget(reset_btn)
        
        # 应用和保存按钮
        apply_btn = QPushButton(t("apply"))
        apply_btn.clicked.connect(self.apply_settings)
        button_layout.addWidget(apply_btn)
        
        save_btn = QPushButton(t("save"))
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        
        # 使用原生样式，移除所有自定义样式
    
    def setup_basic_tab(self, tab):
        """设置基本设置选项卡"""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # 字体大小设置组
        size_group = QGroupBox(t("font_size_settings"))
        size_layout = QVBoxLayout()
        
        # 字体大小滑块和数值输入
        size_control_layout = QHBoxLayout()
        
        size_control_layout.addWidget(QLabel(t("font_size")))
        
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(8, 72)
        self.font_size_slider.setValue(12)
        self.font_size_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.font_size_slider.setTickInterval(8)
        size_control_layout.addWidget(self.font_size_slider)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(12)
        self.font_size_spin.setSuffix(" px")
        self.font_size_spin.setMinimumWidth(80)
        size_control_layout.addWidget(self.font_size_spin)
        
        size_layout.addLayout(size_control_layout)
        
        # 预设字体大小
        preset_label = QLabel(t("quick_select"))
        # 使用原生样式，移除自定义样式
        size_layout.addWidget(preset_label)
        
        self.preset_widget = FontSizePresetWidget()
        size_layout.addWidget(self.preset_widget)
        
        size_group.setLayout(size_layout)
        layout.addWidget(size_group)
        
        # 字体系列设置组
        family_group = QGroupBox(t("font_family_settings"))
        family_layout = QVBoxLayout()
        
        # 字体系列选择
        family_row_layout = QHBoxLayout()
        family_label = QLabel(t("font_family"))
        family_label.setMinimumWidth(80)
        self.font_family_combo = QComboBox()
        self.font_family_combo.setEditable(True)
        self.populate_font_families()
        
        # 让标签点击时也能激活下拉框
        family_label.mousePressEvent = lambda event: self.font_family_combo.showPopup() if event.button() == Qt.MouseButton.LeftButton else None
        family_label.setStyleSheet("QLabel { color: #0066cc; }")
        family_label.setToolTip(t("click_to_open_font_selector"))
        
        family_row_layout.addWidget(family_label)
        family_row_layout.addWidget(self.font_family_combo)
        family_layout.addLayout(family_row_layout)
        
        # 字体样式
        style_row_layout = QHBoxLayout()
        style_label = QLabel(t("font_style"))
        style_label.setMinimumWidth(80)
        
        style_controls_layout = QHBoxLayout()
        self.bold_checkbox = QCheckBox(t("bold"))
        self.italic_checkbox = QCheckBox(t("italic"))
        style_controls_layout.addWidget(self.bold_checkbox)
        style_controls_layout.addWidget(self.italic_checkbox)
        style_controls_layout.addStretch()
        
        style_row_layout.addWidget(style_label)
        style_row_layout.addLayout(style_controls_layout)
        family_layout.addLayout(style_row_layout)
        
        family_group.setLayout(family_layout)
        layout.addWidget(family_group)

        # 实时预览组
        preview_group = QGroupBox(t("real_time_preview"))
        preview_layout = QVBoxLayout()
        
        # 预览说明
        info_label = QLabel(t("preview_info"))
        preview_layout.addWidget(info_label)
        
        # 字体预览控件
        self.font_preview = FontPreviewWidget()
        preview_layout.addWidget(self.font_preview)
        
        # 预览控制
        control_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 刷新预览")
        refresh_btn.clicked.connect(self.update_preview)
        control_layout.addWidget(refresh_btn)
        
        control_layout.addStretch()
        
        # 预览文本选择
        preview_text_combo = QComboBox()
        preview_text_combo.addItems([
            "默认预览文本",
            "纯中文文本",
            "纯英文文本",
            "数字符号",
            "自定义文本"
        ])
        preview_text_combo.currentTextChanged.connect(self.change_preview_text)
        control_layout.addWidget(QLabel("预览文本:"))
        control_layout.addWidget(preview_text_combo)
        
        preview_layout.addLayout(control_layout)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        layout.addStretch()
        tab.setLayout(layout)
    
    def setup_advanced_tab(self, tab):
        """设置高级设置选项卡"""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # 字体渲染设置
        render_group = QGroupBox("🎨 字体渲染设置")
        render_layout = QFormLayout()
        
        self.antialiasing_checkbox = QCheckBox("启用字体抗锯齿")
        self.antialiasing_checkbox.setChecked(True)
        render_layout.addRow("抗锯齿:", self.antialiasing_checkbox)
        
        self.subpixel_checkbox = QCheckBox("启用子像素渲染")
        render_layout.addRow("子像素渲染:", self.subpixel_checkbox)
        
        render_group.setLayout(render_layout)
        layout.addWidget(render_group)
        
        # 应用范围设置
        scope_group = QGroupBox("🎯 应用范围设置")
        scope_layout = QVBoxLayout()
        
        self.apply_to_ui_checkbox = QCheckBox("应用到用户界面")
        self.apply_to_ui_checkbox.setChecked(True)
        scope_layout.addWidget(self.apply_to_ui_checkbox)
        
        self.apply_to_logs_checkbox = QCheckBox("应用到日志显示")
        scope_layout.addWidget(self.apply_to_logs_checkbox)
        
        self.apply_to_results_checkbox = QCheckBox("应用到识别结果")
        scope_layout.addWidget(self.apply_to_results_checkbox)
        
        scope_group.setLayout(scope_layout)
        layout.addWidget(scope_group)
        
        # 性能设置
        performance_group = QGroupBox("⚡ 性能设置")
        performance_layout = QFormLayout()
        
        self.font_cache_checkbox = QCheckBox("启用字体缓存")
        self.font_cache_checkbox.setChecked(True)
        performance_layout.addRow("字体缓存:", self.font_cache_checkbox)
        
        self.lazy_loading_checkbox = QCheckBox("启用延迟加载")
        performance_layout.addRow("延迟加载:", self.lazy_loading_checkbox)
        
        performance_group.setLayout(performance_layout)
        layout.addWidget(performance_group)
        
        layout.addStretch()
        tab.setLayout(layout)
    
    # setup_preview_tab方法已删除，实时预览功能已集成到基本设置页面
    
    def populate_font_families(self):
        """填充字体系列列表"""
        
        # 获取系统字体
        families = QFontDatabase.families()
        
        # 添加常用中文字体
        common_fonts = [
            "微软雅黑", "宋体", "黑体", "楷体", "仿宋",
            "Arial", "Times New Roman", "Courier New", "Verdana", "Tahoma"
        ]
        
        # 合并并去重
        all_fonts = list(set(common_fonts + families))
        all_fonts.sort()
        
        self.font_family_combo.addItems(all_fonts)
    
    def setup_connections(self):
        """设置信号连接"""
        # 字体大小同步
        self.font_size_slider.valueChanged.connect(self.font_size_spin.setValue)
        self.font_size_spin.valueChanged.connect(self.font_size_slider.setValue)
        
        # 预设大小选择
        self.preset_widget.size_selected.connect(self.set_font_size)
        
        # 实时预览更新
        self.font_size_slider.valueChanged.connect(self.update_preview)
        self.font_family_combo.currentTextChanged.connect(self.update_preview)
        self.bold_checkbox.toggled.connect(self.update_preview)
        self.italic_checkbox.toggled.connect(self.update_preview)
    
    def set_font_size(self, size: int):
        """设置字体大小"""
        self.font_size_slider.setValue(size)
        self.font_size_spin.setValue(size)
        self.preset_widget.set_current_size(size)
    
    def update_preview(self):
        """更新字体预览"""
        font_family = self.font_family_combo.currentText()
        font_size = self.font_size_spin.value()
        bold = self.bold_checkbox.isChecked()
        italic = self.italic_checkbox.isChecked()
        
        self.font_preview.update_font_preview(font_family, font_size, bold, italic)
    
    def change_preview_text(self, text_type: str):
        """更改预览文本"""
        texts = {
            t("default_preview_text"): (
                t("font_preview_sample")
            ),
            t("chinese_text_only"): (
                t("chinese_preview_sample")
            ),
            t("english_text_only"): (
                t("english_preview_sample")
            ),
            t("numbers_symbols"): (
                t("numbers_symbols_sample")
            ),
            t("custom_text"): t("custom_text_placeholder")
        }
        
        if text_type in texts:
            self.font_preview.setText(texts[text_type])
            if text_type == t("custom_text"):
                self.font_preview.setReadOnly(False)
            else:
                self.font_preview.setReadOnly(True)
    
    def load_values(self):
        """加载设置值"""
        # 基本设置
        font_size = self.settings.get("font_size", DEFAULT_SETTINGS["font_size"])
        self.set_font_size(font_size)
        
        font_family = self.settings.get("font_family", "微软雅黑")
        index = self.font_family_combo.findText(font_family)
        if index >= 0:
            self.font_family_combo.setCurrentIndex(index)
        
        self.bold_checkbox.setChecked(self.settings.get("font_bold", False))
        self.italic_checkbox.setChecked(self.settings.get("font_italic", False))
        
        # 高级设置
        self.antialiasing_checkbox.setChecked(self.settings.get("font_antialiasing", True))
        self.subpixel_checkbox.setChecked(self.settings.get("font_subpixel", False))
        
        self.apply_to_ui_checkbox.setChecked(self.settings.get("font_apply_to_ui", True))
        self.apply_to_logs_checkbox.setChecked(self.settings.get("font_apply_to_logs", False))
        self.apply_to_results_checkbox.setChecked(self.settings.get("font_apply_to_results", False))
        
        self.font_cache_checkbox.setChecked(self.settings.get("font_cache", True))
        self.lazy_loading_checkbox.setChecked(self.settings.get("font_lazy_loading", False))
        
        # 更新预览
        self.update_preview()
    
    def apply_settings(self):
        """应用设置（不保存到文件）"""
        settings = self.get_current_settings()
        self.settings_changed.emit(settings)
        self.show_message("提示", "字体设置已应用！\n\n注意：设置仅在当前会话中生效，\n如需永久保存请点击'保存'按钮。")
    
    def save_settings(self):
        """保存设置到文件"""
        try:
            settings = self.get_current_settings()
            
            # 更新设置
            self.settings.update(settings)
            
            # 保存到文件
            save_settings(self.settings)
            
            # 发送信号
            self.settings_changed.emit(self.settings)
            
            self.show_message("成功", "字体设置已保存！")
            self.accept()
            
        except Exception as e:
            logging.exception("保存字体设置失败")
            self.show_message("错误", f"保存失败: {e}", QMessageBox.Icon.Critical)
    
    def get_current_settings(self) -> Dict[str, Any]:
        """获取当前设置"""
        return {
            "font_size": self.font_size_spin.value(),
            "font_family": self.font_family_combo.currentText(),
            "font_bold": self.bold_checkbox.isChecked(),
            "font_italic": self.italic_checkbox.isChecked(),
            "font_antialiasing": self.antialiasing_checkbox.isChecked(),
            "font_subpixel": self.subpixel_checkbox.isChecked(),
            "font_apply_to_ui": self.apply_to_ui_checkbox.isChecked(),
            "font_apply_to_logs": self.apply_to_logs_checkbox.isChecked(),
            "font_apply_to_results": self.apply_to_results_checkbox.isChecked(),
            "font_cache": self.font_cache_checkbox.isChecked(),
            "font_lazy_loading": self.lazy_loading_checkbox.isChecked(),
        }
    
    def reset_to_default(self):
        """重置为默认设置"""
        reply = QMessageBox.question(
            self, "确认重置",
            "确定要重置所有字体设置为默认值吗？\n\n此操作将清除当前所有自定义设置。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 重置为默认值
            self.set_font_size(DEFAULT_SETTINGS["font_size"])
            self.font_family_combo.setCurrentText("微软雅黑")
            self.bold_checkbox.setChecked(False)
            self.italic_checkbox.setChecked(False)
            
            self.antialiasing_checkbox.setChecked(True)
            self.subpixel_checkbox.setChecked(False)
            
            self.apply_to_ui_checkbox.setChecked(True)
            self.apply_to_logs_checkbox.setChecked(False)
            self.apply_to_results_checkbox.setChecked(False)
            
            self.font_cache_checkbox.setChecked(True)
            self.lazy_loading_checkbox.setChecked(False)
            
            self.update_preview()
            self.show_message("提示", "已重置为默认字体设置！")
    
    def import_config(self):
        """导入字体配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入字体配置", "", "JSON文件 (*.json);;所有文件 (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 验证配置格式
                required_keys = ["font_size", "font_family"]
                if not all(key in config for key in required_keys):
                    raise ValueError("配置文件格式不正确")
                
                # 应用配置
                self.set_font_size(config.get("font_size", 12))
                
                font_family = config.get("font_family", "微软雅黑")
                index = self.font_family_combo.findText(font_family)
                if index >= 0:
                    self.font_family_combo.setCurrentIndex(index)
                
                self.bold_checkbox.setChecked(config.get("font_bold", False))
                self.italic_checkbox.setChecked(config.get("font_italic", False))
                
                self.update_preview()
                self.show_message("成功", f"字体配置已从 {file_path} 导入！")
                
            except Exception as e:
                logging.exception("导入字体配置失败")
                self.show_message("错误", f"导入失败: {e}", QMessageBox.Icon.Critical)
    
    def export_config(self):
        """导出字体配置"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出字体配置", "font_config.json", "JSON文件 (*.json);;所有文件 (*)"
        )
        
        if file_path:
            try:
                config = self.get_current_settings()
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                
                self.show_message("成功", f"字体配置已导出到 {file_path}！")
                
            except Exception as e:
                logging.exception("导出字体配置失败")
                self.show_message("错误", f"导出失败: {e}", QMessageBox.Icon.Critical)
    
    def show_message(self, title: str, text: str, icon=QMessageBox.Icon.Information):
        """显示消息对话框"""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon)
        msg.exec()
    
    def connect_language_signal(self):
        """连接语言切换信号"""
        pass
    
    def refresh_ui_text(self):
        """刷新UI文本的国际化显示"""
        try:
            from core.i18n import t
            
            # 刷新窗口标题
            self.setWindowTitle(t('字体设置'))
            
            # 刷新组框标题
            for group_box in self.findChildren(QGroupBox):
                if "字体选择" in group_box.title():
                    group_box.setTitle(t('font_selection'))
                elif "字体大小" in group_box.title():
                    group_box.setTitle(t('font_size'))
                elif "字体样式" in group_box.title():
                    group_box.setTitle(t('font_style'))
                elif "预览" in group_box.title():
                    group_box.setTitle(t('preview'))
            
            # 刷新按钮文本
            for button in self.findChildren(QPushButton):
                if button.text() == "应用":
                    button.setText(t('apply'))
                elif button.text() == "保存":
                    button.setText(t('save'))
                elif button.text() == "重置":
                    button.setText(t('reset'))
                elif button.text() == "取消":
                    button.setText(t('cancel'))
                elif button.text() == "确定":
                    button.setText(t('ok'))
                    
        except Exception as e:
            import logging
            logging.error(f"刷新EnhancedFontDialog UI文本时出错: {e}")
    
    def clear_layout(self, layout):
        """清空布局中的所有控件"""
        if layout is not None:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
                elif child.layout():
                    self.clear_layout(child.layout())


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dialog = EnhancedFontDialog()
    dialog.show()
    sys.exit(app.exec())