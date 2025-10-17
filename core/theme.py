from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QStyleFactory
from typing import Dict, Tuple, Optional
import json
import os


# 主题配置
THEME_CONFIG_FILE = "theme_config.json"

# 预设主题配色方案
THEME_PRESETS = {
    "浅色": {
        "window": "#f0f0f0",
        "window_text": "#000000",
        "button": "#e1e1e1",
        "button_text": "#000000",
        "base": "#ffffff",
        "alternate_base": "#f5f5f5",
        "highlight": "#0078d4",
        "highlighted_text": "#ffffff",
        "accent": "#0078d4"
    },
    "深色": {
        "window": "#464646",
        "window_text": "#ffffff",
        "button": "#5a5a5a",
        "button_text": "#ffffff",
        "base": "#3c3c3c",
        "alternate_base": "#646464",
        "highlight": "#007acc",
        "highlighted_text": "#ffffff",
        "accent": "#007acc"
    }
}

def get_available_themes() -> list[str]:
    """获取所有可用的主题名称"""
    return list(THEME_PRESETS.keys())

def save_custom_theme(name: str, colors: Dict[str, str]) -> bool:
    """保存自定义主题"""
    try:
        config = load_theme_config()
        config["custom_themes"] = config.get("custom_themes", {})
        config["custom_themes"][name] = colors
        
        with open(THEME_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"保存自定义主题失败: {e}")
        return False

def load_theme_config() -> Dict:
    """加载主题配置"""
    if os.path.exists(THEME_CONFIG_FILE):
        try:
            with open(THEME_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"custom_themes": {}}

def get_theme_colors(theme_name: str) -> Optional[Dict[str, str]]:
    """获取主题配色方案"""
    # 首先检查预设主题
    if theme_name in THEME_PRESETS:
        return THEME_PRESETS[theme_name]
    
    # 然后检查自定义主题
    config = load_theme_config()
    custom_themes = config.get("custom_themes", {})
    if theme_name in custom_themes:
        return custom_themes[theme_name]
    
    return None

def apply_theme(app, theme="浅色"):
    """应用主题"""
    if theme == "深色":
        apply_dark_theme(app)
    elif theme == "浅色":
        apply_light_theme(app)
    else:
        # 对于其他主题（蓝色、绿色、紫色、高对比度），使用自定义主题
        colors = get_theme_colors(theme)
        if colors:
            apply_custom_theme(app, colors)
        else:
            apply_light_theme(app)  # 如果找不到主题配色，回退到浅色主题


def apply_custom_theme(app, colors: Dict[str, str]):
    """应用自定义主题配色"""
    palette = QPalette()
    
    # 设置基础颜色
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["window_text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["base"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["alternate_base"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["base"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["window_text"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["window_text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["button"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["button_text"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff0000"))
    palette.setColor(QPalette.ColorRole.Link, QColor(colors["accent"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["highlight"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["highlighted_text"]))
    
    # 设置禁用状态的颜色
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#808080"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#808080"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#808080"))
    
    app.setPalette(palette)
    
    # 设置样式表
    style_sheet = f"""
    QWidget {{
        background-color: {colors["window"]};
        color: {colors["window_text"]};
        font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
    }}
    
    QTabWidget::pane {{
        border: 1px solid {colors["button"]};
        background-color: {colors["base"]};
    }}
    
    QTabBar::tab {{
        background-color: {colors["button"]};
        color: {colors["button_text"]};
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    
    QTabBar::tab:selected {{
        background-color: {colors["highlight"]};
        color: {colors["highlighted_text"]};
    }}
    
    QTabBar::tab:hover {{
        background-color: {colors["alternate_base"]};
    }}
    
    QPushButton {{
        background-color: {colors["button"]};
        color: {colors["button_text"]};
        border: 1px solid {colors["alternate_base"]};
        padding: 6px 12px;
        border-radius: 4px;
        font-weight: 500;
    }}
    
    QPushButton:hover {{
        background-color: {colors["alternate_base"]};
        border-color: {colors["accent"]};
    }}
    
    QPushButton:pressed {{
        background-color: {colors["highlight"]};
        color: {colors["highlighted_text"]};
    }}
    
    QPushButton:disabled {{
        background-color: {colors["alternate_base"]};
        color: #808080;
        border-color: #808080;
    }}
    
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
        background-color: {colors["base"]};
        color: {colors["window_text"]};
        border: 1px solid {colors["alternate_base"]};
        padding: 4px;
        border-radius: 3px;
    }}
    
    QLineEdit {{
        placeholder-text-color: {colors["alternate_base"]};
    }}
    
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {colors["accent"]};
        outline: none;
    }}
    
    QComboBox {{
        background-color: {colors["button"]};
        color: {colors["button_text"]};
        border: 1px solid {colors["alternate_base"]};
        padding: 4px 8px;
        border-radius: 3px;
        min-height: 20px;
    }}
    
    QComboBox:hover {{
        border-color: {colors["accent"]};
        background-color: {colors["alternate_base"]};
    }}
    
    QComboBox:focus {{
        border-color: {colors["accent"]};
        outline: none;
    }}
    
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border-left-width: 1px;
        border-left-color: {colors["alternate_base"]};
        border-left-style: solid;
        border-top-right-radius: 3px;
        border-bottom-right-radius: 3px;
        background-color: {colors["alternate_base"]};
    }}
    
    QComboBox::drop-down:hover {{
        background-color: {colors["accent"]};
    }}
    
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 6px solid {colors["button_text"]};
        margin: 0px;
    }}
    
    QComboBox::down-arrow:hover {{
        border-top-color: {colors["button_text"]};
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {colors["button"]};
        color: {colors["button_text"]};
        border: 1px solid {colors["alternate_base"]};
        selection-background-color: {colors["accent"]};
        selection-color: {colors["highlighted_text"]};
        outline: none;
    }}
    
    QComboBox QAbstractItemView::item {{
        padding: 4px;
        border: none;
    }}
    
    QComboBox QAbstractItemView::item:selected {{
        background-color: {colors["accent"]};
        color: {colors["highlighted_text"]};
    }}
    
    QComboBox QAbstractItemView::item:hover {{
        background-color: {colors["alternate_base"]};
        color: {colors["button_text"]};
    }}
    
    QCheckBox, QRadioButton {{
        color: {colors["window_text"]};
        spacing: 8px;
    }}
    
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {colors["alternate_base"]};
        background-color: {colors["base"]};
    }}
    
    QCheckBox::indicator:checked {{
        background-color: {colors["accent"]};
        border-color: {colors["accent"]};
    }}
    
    QRadioButton::indicator {{
        border-radius: 8px;
    }}
    
    QRadioButton::indicator:checked {{
        background-color: {colors["accent"]};
        border-color: {colors["accent"]};
    }}
    
    QScrollBar:vertical {{
        background-color: {colors["alternate_base"]};
        width: 12px;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {colors["button"]};
        border-radius: 6px;
        min-height: 20px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {colors["accent"]};
    }}
    
    QScrollBar:horizontal {{
        background-color: {colors["alternate_base"]};
        height: 12px;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: {colors["button"]};
        border-radius: 6px;
        min-width: 20px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background-color: {colors["accent"]};
    }}
    
    QGroupBox {{
        color: {colors["window_text"]};
        border: 1px solid {colors["alternate_base"]};
        border-radius: 4px;
        margin-top: 10px;
        font-weight: 500;
    }}
    
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 8px 0 8px;
        background-color: {colors["window"]};
    }}
    
    QProgressBar {{
        border: 1px solid {colors["alternate_base"]};
        border-radius: 4px;
        text-align: center;
        background-color: {colors["base"]};
    }}
    
    QProgressBar::chunk {{
        background-color: {colors["accent"]};
        border-radius: 3px;
    }}
    
    QSlider::groove:horizontal {{
        border: 1px solid {colors["alternate_base"]};
        height: 6px;
        background-color: {colors["base"]};
        border-radius: 3px;
    }}
    
    QSlider::handle:horizontal {{
        background-color: {colors["accent"]};
        border: 1px solid {colors["accent"]};
        width: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }}
    
    QSlider::handle:horizontal:hover {{
        background-color: {colors["highlight"]};
    }}
    
    QMenuBar {{
        background-color: {colors["window"]};
        color: {colors["window_text"]};
        border-bottom: 1px solid {colors["alternate_base"]};
    }}
    
    QMenuBar::item {{
        padding: 4px 8px;
        background-color: transparent;
    }}
    
    QMenuBar::item:selected {{
        background-color: {colors["highlight"]};
        color: {colors["highlighted_text"]};
    }}
    
    QMenu {{
        background-color: {colors["base"]};
        color: {colors["window_text"]};
        border: 1px solid {colors["alternate_base"]};
    }}
    
    QMenu::item {{
        padding: 4px 16px;
    }}
    
    QMenu::item:selected {{
        background-color: {colors["highlight"]};
        color: {colors["highlighted_text"]};
    }}
    
    QStatusBar {{
        background-color: {colors["window"]};
        color: {colors["window_text"]};
        border-top: 1px solid {colors["alternate_base"]};
    }}
    
    QToolTip {{
        background-color: {colors["base"]};
        color: {colors["window_text"]};
        border: 1px solid {colors["alternate_base"]};
        padding: 4px;
        border-radius: 3px;
    }}
    """
    
    app.setStyleSheet(style_sheet)

def apply_light_theme(app):
    """应用浅色主题"""
    app.setStyle(QStyleFactory.create("Fusion"))
    
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Button, QColor(225, 225, 225))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 120, 212))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 212))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    
    app.setPalette(palette)

def apply_dark_theme(app):
    """应用深色主题"""
    app.setStyle(QStyleFactory.create("Fusion"))
    
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(70, 70, 70))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base, QColor(60, 60, 60))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(100, 100, 100))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(90, 90, 90))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 122, 204))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 122, 204))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    
    app.setPalette(palette)
    
    # 设置样式表以修复placeholder颜色问题
    app.setStyleSheet("""
        QLineEdit {
            placeholder-text-color: #999999;
        }
    """)

def create_theme_transition_effect(app, from_theme: str, to_theme: str, duration: int = 300):
    """创建主题切换过渡效果"""
    try:
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, pyqtProperty
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        
        # 获取主窗口
        main_window = None
        for widget in app.allWidgets():
            if widget.__class__.__name__ == 'MainWindow':
                main_window = widget
                break
        
        if main_window:
            # 创建透明度效果
            opacity_effect = QGraphicsOpacityEffect()
            main_window.setGraphicsEffect(opacity_effect)
            
            # 创建动画
            animation = QPropertyAnimation(opacity_effect, b"opacity")
            animation.setDuration(duration)
            animation.setStartValue(1.0)
            animation.setEndValue(0.3)
            animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            
            def on_fade_out_finished():
                # 应用新主题
                apply_theme(app, to_theme)
                
                # 淡入动画
                fade_in = QPropertyAnimation(opacity_effect, b"opacity")
                fade_in.setDuration(duration)
                fade_in.setStartValue(0.3)
                fade_in.setEndValue(1.0)
                fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)
                
                def on_fade_in_finished():
                    main_window.setGraphicsEffect(None)
                
                fade_in.finished.connect(on_fade_in_finished)
                fade_in.start()
            
            animation.finished.connect(on_fade_out_finished)
            animation.start()
        else:
            # 如果没有找到主窗口，直接应用主题
            apply_theme(app, to_theme)
    
    except ImportError:
        # 如果动画模块不可用，直接应用主题
        apply_theme(app, to_theme)

def get_theme_preview(theme_name: str) -> Dict[str, str]:
    """获取主题预览信息"""
    colors = get_theme_colors(theme_name)
    if not colors:
        return {}
    
    return {
        "name": theme_name,
        "primary_color": colors["accent"],
        "background_color": colors["window"],
        "text_color": colors["window_text"],
        "description": f"主色调: {colors['accent']}, 背景: {colors['window']}"
    }

def validate_theme_colors(colors: Dict[str, str]) -> bool:
    """验证主题配色方案的完整性"""
    required_keys = [
        "window", "window_text", "button", "button_text",
        "base", "alternate_base", "highlight", "highlighted_text", "accent"
    ]
    
    for key in required_keys:
        if key not in colors:
            return False
        
        # 验证颜色格式
        color_value = colors[key]
        if not (color_value.startswith('#') and len(color_value) == 7):
            try:
                QColor(color_value)
            except:
                return False
    
    return True

def export_theme(theme_name: str, file_path: str) -> bool:
    """导出主题到文件"""
    try:
        colors = get_theme_colors(theme_name)
        if not colors:
            return False
        
        theme_data = {
            "name": theme_name,
            "colors": colors,
            "version": "1.0",
            "created_at": __import__('datetime').datetime.now().isoformat()
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(theme_data, f, indent=4, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"导出主题失败: {e}")
        return False

def import_theme(file_path: str) -> Optional[str]:
    """从文件导入主题"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            theme_data = json.load(f)
        
        if "name" not in theme_data or "colors" not in theme_data:
            return None
        
        theme_name = theme_data["name"]
        colors = theme_data["colors"]
        
        if not validate_theme_colors(colors):
            return None
        
        if save_custom_theme(theme_name, colors):
            return theme_name
        
        return None
    except Exception as e:
        print(f"导入主题失败: {e}")
        return None
