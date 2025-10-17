#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QSlider, QSpinBox, QPushButton,
                            QGroupBox, QGridLayout, QTextEdit, QSplitter,
                            QCheckBox, QComboBox, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor

class LayoutPreview(QWidget):
    """布局预览组件"""
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        self.setMinimumSize(400, 300)
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border: 1px solid #555;
            }
        """)
        
        # 创建模拟的主布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 左侧面板模拟
        left_panel = QFrame()
        left_panel.setStyleSheet("background-color: #3c3c3c; border: 1px solid #666;")
        left_panel.setMinimumWidth(150)
        
        # 右侧面板容器
        self.right_container = QWidget()
        self.right_container_layout = QVBoxLayout(self.right_container)
        self.right_container_layout.setContentsMargins(0, 0, 0, 0)
        self.right_container_layout.setSpacing(0)
        
        # 灵动岛容器
        self.dynamic_island_container = QWidget()
        self.dynamic_island_container.setStyleSheet("background-color: #4a4a4a; border: 1px solid #777;")
        self.dynamic_island_layout = QHBoxLayout(self.dynamic_island_container)
        
        # 模拟灵动岛
        self.dynamic_island = QLabel("灵动岛")
        self.dynamic_island.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dynamic_island.setStyleSheet("""
            background-color: #1a1a1a;
            color: white;
            border-radius: 15px;
            padding: 5px 15px;
            font-weight: bold;
        """)
        self.dynamic_island.setFixedSize(120, 30)
        
        self.dynamic_island_layout.addWidget(self.dynamic_island)
        self.dynamic_island_layout.addStretch()
        
        # 右侧主面板
        right_main = QFrame()
        right_main.setStyleSheet("background-color: #3c3c3c; border: 1px solid #666;")
        
        # 添加到右侧容器
        self.right_container_layout.addWidget(self.dynamic_island_container)
        self.right_container_layout.addWidget(right_main)
        
        # 添加到主布局
        layout.addWidget(left_panel, 3)
        layout.addWidget(self.right_container, 5)
        
    def update_layout(self, params):
        """更新布局参数"""
        # 更新灵动岛容器高度
        self.dynamic_island_container.setFixedHeight(params['container_height'])
        
        # 更新容器边距
        self.dynamic_island_layout.setContentsMargins(
            params['margin_left'], params['margin_top'], 
            params['margin_right'], params['margin_bottom']
        )
        
        # 更新灵动岛大小
        self.dynamic_island.setFixedSize(params['island_width'], params['island_height'])
        
        # 更新间距
        self.right_container_layout.setSpacing(params['spacing'])

class LayoutAdjuster(QMainWindow):
    """布局调整器主窗口"""
    
    def __init__(self):
        super().__init__()
        self.current_params = {
            'container_height': 45,
            'margin_left': 5,
            'margin_top': 5,
            'margin_right': 5,
            'margin_bottom': 0,
            'island_width': 120,
            'island_height': 30,
            'spacing': 0
        }
        self.init_ui()
        self.setup_connections()
        
    def init_ui(self):
        self.setWindowTitle("灵动岛布局调整器")
        self.setGeometry(100, 100, 800, 600)
        
        # 设置深色主题
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #3c3c3c;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QLabel {
                color: white;
            }
            QSlider::groove:horizontal {
                border: 1px solid #555;
                height: 8px;
                background: #444;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                border: 1px solid #0078d4;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSpinBox {
                background-color: #444;
                border: 1px solid #666;
                color: white;
                padding: 2px;
            }
            QPushButton {
                background-color: #0078d4;
                border: none;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧控制面板
        control_panel = self.create_control_panel()
        
        # 右侧预览面板
        self.preview = LayoutPreview()
        
        splitter.addWidget(control_panel)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)
        
        # 初始化预览
        self.update_preview()
        
    def create_control_panel(self):
        """创建控制面板"""
        panel = QWidget()
        panel.setMaximumWidth(350)
        layout = QVBoxLayout(panel)
        
        # 容器设置组
        container_group = QGroupBox("容器设置")
        container_layout = QGridLayout(container_group)
        
        # 容器高度
        container_layout.addWidget(QLabel("容器高度:"), 0, 0)
        self.container_height_slider = QSlider(Qt.Orientation.Horizontal)
        self.container_height_slider.setRange(30, 100)
        self.container_height_slider.setValue(self.current_params['container_height'])
        self.container_height_spin = QSpinBox()
        self.container_height_spin.setRange(30, 100)
        self.container_height_spin.setValue(self.current_params['container_height'])
        container_layout.addWidget(self.container_height_slider, 0, 1)
        container_layout.addWidget(self.container_height_spin, 0, 2)
        
        # 间距设置
        container_layout.addWidget(QLabel("面板间距:"), 1, 0)
        self.spacing_slider = QSlider(Qt.Orientation.Horizontal)
        self.spacing_slider.setRange(0, 20)
        self.spacing_slider.setValue(self.current_params['spacing'])
        self.spacing_spin = QSpinBox()
        self.spacing_spin.setRange(0, 20)
        self.spacing_spin.setValue(self.current_params['spacing'])
        container_layout.addWidget(self.spacing_slider, 1, 1)
        container_layout.addWidget(self.spacing_spin, 1, 2)
        
        layout.addWidget(container_group)
        
        # 边距设置组
        margin_group = QGroupBox("边距设置")
        margin_layout = QGridLayout(margin_group)
        
        # 左边距
        margin_layout.addWidget(QLabel("左边距:"), 0, 0)
        self.margin_left_slider = QSlider(Qt.Orientation.Horizontal)
        self.margin_left_slider.setRange(0, 50)
        self.margin_left_slider.setValue(self.current_params['margin_left'])
        self.margin_left_spin = QSpinBox()
        self.margin_left_spin.setRange(0, 50)
        self.margin_left_spin.setValue(self.current_params['margin_left'])
        margin_layout.addWidget(self.margin_left_slider, 0, 1)
        margin_layout.addWidget(self.margin_left_spin, 0, 2)
        
        # 上边距
        margin_layout.addWidget(QLabel("上边距:"), 1, 0)
        self.margin_top_slider = QSlider(Qt.Orientation.Horizontal)
        self.margin_top_slider.setRange(0, 30)
        self.margin_top_slider.setValue(self.current_params['margin_top'])
        self.margin_top_spin = QSpinBox()
        self.margin_top_spin.setRange(0, 30)
        self.margin_top_spin.setValue(self.current_params['margin_top'])
        margin_layout.addWidget(self.margin_top_slider, 1, 1)
        margin_layout.addWidget(self.margin_top_spin, 1, 2)
        
        # 右边距
        margin_layout.addWidget(QLabel("右边距:"), 2, 0)
        self.margin_right_slider = QSlider(Qt.Orientation.Horizontal)
        self.margin_right_slider.setRange(0, 50)
        self.margin_right_slider.setValue(self.current_params['margin_right'])
        self.margin_right_spin = QSpinBox()
        self.margin_right_spin.setRange(0, 50)
        self.margin_right_spin.setValue(self.current_params['margin_right'])
        margin_layout.addWidget(self.margin_right_slider, 2, 1)
        margin_layout.addWidget(self.margin_right_spin, 2, 2)
        
        # 下边距
        margin_layout.addWidget(QLabel("下边距:"), 3, 0)
        self.margin_bottom_slider = QSlider(Qt.Orientation.Horizontal)
        self.margin_bottom_slider.setRange(0, 20)
        self.margin_bottom_slider.setValue(self.current_params['margin_bottom'])
        self.margin_bottom_spin = QSpinBox()
        self.margin_bottom_spin.setRange(0, 20)
        self.margin_bottom_spin.setValue(self.current_params['margin_bottom'])
        margin_layout.addWidget(self.margin_bottom_slider, 3, 1)
        margin_layout.addWidget(self.margin_bottom_spin, 3, 2)
        
        layout.addWidget(margin_group)
        
        # 灵动岛设置组
        island_group = QGroupBox("灵动岛设置")
        island_layout = QGridLayout(island_group)
        
        # 宽度
        island_layout.addWidget(QLabel("宽度:"), 0, 0)
        self.island_width_slider = QSlider(Qt.Orientation.Horizontal)
        self.island_width_slider.setRange(80, 200)
        self.island_width_slider.setValue(self.current_params['island_width'])
        self.island_width_spin = QSpinBox()
        self.island_width_spin.setRange(80, 200)
        self.island_width_spin.setValue(self.current_params['island_width'])
        island_layout.addWidget(self.island_width_slider, 0, 1)
        island_layout.addWidget(self.island_width_spin, 0, 2)
        
        # 高度
        island_layout.addWidget(QLabel("高度:"), 1, 0)
        self.island_height_slider = QSlider(Qt.Orientation.Horizontal)
        self.island_height_slider.setRange(20, 50)
        self.island_height_slider.setValue(self.current_params['island_height'])
        self.island_height_spin = QSpinBox()
        self.island_height_spin.setRange(20, 50)
        self.island_height_spin.setValue(self.current_params['island_height'])
        island_layout.addWidget(self.island_height_slider, 1, 1)
        island_layout.addWidget(self.island_height_spin, 1, 2)
        
        layout.addWidget(island_group)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.reset_btn = QPushButton("重置默认")
        self.save_btn = QPushButton("保存配置")
        self.apply_btn = QPushButton("应用到主程序")
        
        button_layout.addWidget(self.reset_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.apply_btn)
        
        layout.addLayout(button_layout)
        
        # 代码预览
        code_group = QGroupBox("生成的代码")
        code_layout = QVBoxLayout(code_group)
        
        self.code_preview = QTextEdit()
        self.code_preview.setMaximumHeight(150)
        self.code_preview.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #555;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10px;
            }
        """)
        code_layout.addWidget(self.code_preview)
        
        layout.addWidget(code_group)
        layout.addStretch()
        
        return panel
        
    def setup_connections(self):
        """设置信号连接"""
        # 容器设置
        self.container_height_slider.valueChanged.connect(self.container_height_spin.setValue)
        self.container_height_spin.valueChanged.connect(self.container_height_slider.setValue)
        self.container_height_slider.valueChanged.connect(self.on_param_changed)
        
        self.spacing_slider.valueChanged.connect(self.spacing_spin.setValue)
        self.spacing_spin.valueChanged.connect(self.spacing_slider.setValue)
        self.spacing_slider.valueChanged.connect(self.on_param_changed)
        
        # 边距设置
        self.margin_left_slider.valueChanged.connect(self.margin_left_spin.setValue)
        self.margin_left_spin.valueChanged.connect(self.margin_left_slider.setValue)
        self.margin_left_slider.valueChanged.connect(self.on_param_changed)
        
        self.margin_top_slider.valueChanged.connect(self.margin_top_spin.setValue)
        self.margin_top_spin.valueChanged.connect(self.margin_top_slider.setValue)
        self.margin_top_slider.valueChanged.connect(self.on_param_changed)
        
        self.margin_right_slider.valueChanged.connect(self.margin_right_spin.setValue)
        self.margin_right_spin.valueChanged.connect(self.margin_right_slider.setValue)
        self.margin_right_slider.valueChanged.connect(self.on_param_changed)
        
        self.margin_bottom_slider.valueChanged.connect(self.margin_bottom_spin.setValue)
        self.margin_bottom_spin.valueChanged.connect(self.margin_bottom_slider.setValue)
        self.margin_bottom_slider.valueChanged.connect(self.on_param_changed)
        
        # 灵动岛设置
        self.island_width_slider.valueChanged.connect(self.island_width_spin.setValue)
        self.island_width_spin.valueChanged.connect(self.island_width_slider.setValue)
        self.island_width_slider.valueChanged.connect(self.on_param_changed)
        
        self.island_height_slider.valueChanged.connect(self.island_height_spin.setValue)
        self.island_height_spin.valueChanged.connect(self.island_height_slider.setValue)
        self.island_height_slider.valueChanged.connect(self.on_param_changed)
        
        # 按钮
        self.reset_btn.clicked.connect(self.reset_to_default)
        self.save_btn.clicked.connect(self.save_config)
        self.apply_btn.clicked.connect(self.apply_to_main)
        
    def on_param_changed(self):
        """参数改变时的处理"""
        self.current_params = {
            'container_height': self.container_height_slider.value(),
            'margin_left': self.margin_left_slider.value(),
            'margin_top': self.margin_top_slider.value(),
            'margin_right': self.margin_right_slider.value(),
            'margin_bottom': self.margin_bottom_slider.value(),
            'island_width': self.island_width_slider.value(),
            'island_height': self.island_height_slider.value(),
            'spacing': self.spacing_slider.value()
        }
        self.update_preview()
        self.update_code_preview()
        
    def update_preview(self):
        """更新预览"""
        self.preview.update_layout(self.current_params)
        
    def update_code_preview(self):
        """更新代码预览"""
        code = f"""# 灵动岛容器设置
dynamic_island_container.setFixedHeight({self.current_params['container_height']})
dynamic_island_layout.setContentsMargins({self.current_params['margin_left']}, {self.current_params['margin_top']}, {self.current_params['margin_right']}, {self.current_params['margin_bottom']})

# 灵动岛大小设置
self.dynamic_island.setFixedSize({self.current_params['island_width']}, {self.current_params['island_height']})

# 面板间距设置
right_container_layout.setSpacing({self.current_params['spacing']})"""
        
        self.code_preview.setPlainText(code)
        
    def reset_to_default(self):
        """重置为默认值"""
        defaults = {
            'container_height': 45,
            'margin_left': 5,
            'margin_top': 5,
            'margin_right': 5,
            'margin_bottom': 0,
            'island_width': 120,
            'island_height': 30,
            'spacing': 0
        }
        
        self.container_height_slider.setValue(defaults['container_height'])
        self.margin_left_slider.setValue(defaults['margin_left'])
        self.margin_top_slider.setValue(defaults['margin_top'])
        self.margin_right_slider.setValue(defaults['margin_right'])
        self.margin_bottom_slider.setValue(defaults['margin_bottom'])
        self.island_width_slider.setValue(defaults['island_width'])
        self.island_height_slider.setValue(defaults['island_height'])
        self.spacing_slider.setValue(defaults['spacing'])
        
    def save_config(self):
        """保存配置到文件"""
        config_path = "layout_config.json"
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.current_params, f, indent=2, ensure_ascii=False)
            print(f"配置已保存到 {config_path}")
        except Exception as e:
            print(f"保存配置失败: {e}")
            
    def apply_to_main(self):
        """应用配置到主程序"""
        # 这里可以实现将配置应用到主程序的逻辑
        print("配置参数:")
        for key, value in self.current_params.items():
            print(f"  {key}: {value}")
        print("\n请复制上方代码预览中的代码到 main.py 中相应位置")

def main():
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    window = LayoutAdjuster()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()