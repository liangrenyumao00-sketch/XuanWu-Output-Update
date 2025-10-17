"""
现代化灵动岛组件 - 全新设计
提供流畅的动画、现代化的视觉效果和优雅的交互体验
"""

import sys
import math
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QGraphicsDropShadowEffect, QFrame, QApplication, QPushButton,
    QGraphicsOpacityEffect, QStackedWidget, QMenu
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, 
    pyqtSignal, QRectF, QParallelAnimationGroup, QSequentialAnimationGroup,
    QPoint, QSize, QRect, QAbstractAnimation, QThread, QTime
)
from PyQt6.QtGui import (
    QPainter, QPainterPath, QColor, QFont, QPixmap, QIcon, QPen,
    QLinearGradient, QRadialGradient, QBrush, QFontMetrics, QKeySequence, QShortcut, QCursor
)
import logging


class ModernDynamicIsland(QWidget):
    """现代化灵动岛组件 - 全新设计"""
    
    # 信号定义
    clicked = pyqtSignal()
    expanded = pyqtSignal()
    collapsed = pyqtSignal()
    action_triggered = pyqtSignal(str)  # 操作触发信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 基础属性
        self._expanded = False
        self._animating = False
        self._hover_state = False
        self._animations_initialized = False  # 动画初始化标记
        self._independent_mode = False  # 独立模式标记，主窗口最小化时启用
        
        # 点击事件队列机制
        self._pending_click_action = None  # 待处理的点击动作
        self._last_click_time = 0  # 最后点击时间，用于防抖
        
        # 设置父窗口引用
        self.parent_window = parent
        
        # 尺寸配置
        self.collapsed_width = 180
        self.collapsed_height = 36
        self.expanded_width = 320
        self.expanded_height = 48
        self.border_radius = 18
        
        # 主题配置
        self.current_theme = "auto"  # auto, light, dark
        self.is_dark_theme = self.detect_system_theme()
        
        # 颜色配置（将根据主题动态调整）
        self.update_theme_colors()
        
        # 状态管理
        self.current_state = "idle"  # idle, working, notification, success, error
        self.status_text = "就绪"
        self.main_text = "炫舞OCR"
        self._menu_showing = False  # 菜单显示状态跟踪
        self.progress_value = 0
        
        # 初始化UI
        self.init_ui()
        self.setup_animations()
        self.setup_timers()
        self.setup_shortcuts()
        self.setup_context_menu()
        
        # 初始化多功能显示模式
        self.init_display_modes()
        
        # 设置窗口属性为独立窗口
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setMouseTracking(True)
        
        # 初始尺寸
        self.resize(self.collapsed_width, self.collapsed_height)
        
        # 定位到屏幕中央但不显示
        self.position_on_screen()  # 定位到屏幕中央
        
        # 初始化时隐藏灵动岛，只有在有通知时才显示
        self.hide()
        
        # 立即启动数据更新
        QTimer.singleShot(100, self.update_display_data)  # 延迟100ms确保UI完全初始化
        
        logging.info("现代化灵动岛组件初始化完成")
    
    def __del__(self):
        """析构函数，确保资源正确清理"""
        try:
            self._cleanup_animations()
        except:
            pass  # 析构时忽略所有异常
        # 安全处理定时器，避免删除后的调用
        try:
            if hasattr(self, 'auto_hide_timer') and self.auto_hide_timer:
                try:
                    if self.auto_hide_timer.isActive():
                        self.auto_hide_timer.stop()
                except RuntimeError:
                    pass
                self.auto_hide_timer.deleteLater()
                self.auto_hide_timer = None
        except Exception:
            pass
        try:
            if hasattr(self, 'state_reset_timer') and self.state_reset_timer:
                try:
                    if self.state_reset_timer.isActive():
                        self.state_reset_timer.stop()
                except RuntimeError:
                    pass
                self.state_reset_timer.deleteLater()
                self.state_reset_timer = None
        except Exception:
            pass
    
    def init_ui(self):
        """初始化UI组件"""
        # 主布局
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(12, 8, 12, 8)
        self.main_layout.setSpacing(10)
        
        # 左侧图标区域
        self.icon_container = QWidget()
        self.icon_container.setFixedSize(20, 20)
        self.icon_label = QLabel("🔍")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 根据主题设置图标颜色
        icon_color = getattr(self, 'text_color', 'white')
        self.icon_label.setStyleSheet(f"""
            QLabel {{
                color: {icon_color};
                font-size: 14px;
                background: transparent;
                border: none;
            }}
        """)
        
        icon_layout = QVBoxLayout(self.icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.addWidget(self.icon_label)
        
        # 中间内容区域
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(2)
        
        # 主标题
        self.title_label = QLabel(self.main_text)
        # 根据主题设置标题颜色
        title_color = getattr(self, 'text_color', 'white')
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {title_color};
                font-weight: 600;
                font-size: 13px;
                background: transparent;
                border: none;
            }}
        """)
        
        # 状态标签
        self.status_label = QLabel(self.status_text)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #A0A0A0;
                font-size: 10px;
                background: transparent;
                border: none;
            }
        """)
        
        # 进度条（初始隐藏）
        self.progress_container = QWidget()
        self.progress_container.setFixedHeight(4)
        self.progress_container.hide()  # 默认隐藏
        
        self.content_layout.addWidget(self.title_label)
        self.content_layout.addWidget(self.status_label)
        self.content_layout.addWidget(self.progress_container)
        
        # 右侧状态指示器
        self.status_indicator = QWidget()
        self.status_indicator.setFixedSize(8, 8)
        self.status_indicator.setStyleSheet("""
            QWidget {
                background-color: #34C759;
                border-radius: 4px;
                border: none;
            }
        """)
        
        # 操作按钮容器（展开时显示）
        self.actions_container = QWidget()
        self.actions_layout = QHBoxLayout(self.actions_container)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(8)
        
        # 创建操作按钮
        self.create_action_buttons()
        
        # 添加到主布局
        self.main_layout.addWidget(self.icon_container)
        self.main_layout.addWidget(self.content_container, 1)
        self.main_layout.addWidget(self.status_indicator)
        self.main_layout.addWidget(self.actions_container)
        
        # 初始状态
        self.actions_container.hide()
        
        # 添加阴影效果
        self.add_shadow_effect()
    
    def create_action_buttons(self):
        """创建操作按钮"""
        buttons_config = [
            ("📷", "快速识别", "quick_ocr"),
            ("⚙️", "设置", "settings"),
            ("📋", "历史", "history")
        ]
        
        self.action_buttons = {}
        
        for icon, tooltip, action in buttons_config:
            btn = self.create_modern_button(icon, tooltip, action)
            self.actions_layout.addWidget(btn)
            self.action_buttons[action] = btn
    
    def create_modern_button(self, icon, tooltip, action):
        """创建现代化按钮"""
        btn = QPushButton(icon)
        btn.setFixedSize(28, 28)
        btn.setToolTip(tooltip)
        
        # 根据当前主题设置按钮样式
        text_color = self.text_color.name() if hasattr(self, 'text_color') else "#FFFFFF"
        
        # 设置按钮样式
        btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 14px;
                color: {text_color};
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }}
            QPushButton:pressed {{
                background: rgba(255, 255, 255, 0.3);
            }}
        """)
        
        # 设置全局工具提示样式，确保在所有主题下都能正确显示
        self._apply_tooltip_style()
        
        # 连接点击事件
        btn.clicked.connect(lambda: self.trigger_action(action))
        
        return btn
    
    def _apply_tooltip_style(self):
        """应用工具提示样式"""
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if not app:
                return
            
            # 确定当前主题
            use_dark = True  # 默认深色主题
            if hasattr(self, 'current_theme') and hasattr(self, 'is_dark_theme'):
                # 标准化主题名称
                normalized_theme = self._normalize_theme_name(self.current_theme)
                if normalized_theme == "auto":
                    use_dark = self.is_dark_theme
                elif normalized_theme == "dark":
                    use_dark = True
                elif normalized_theme == "light":
                    use_dark = False
            
            # 检查是否需要更新样式（避免重复应用相同样式）
            current_tooltip_theme = getattr(self, '_current_tooltip_theme', None)
            if current_tooltip_theme == use_dark:
                return  # 样式未改变，无需重复应用
            
            # 根据主题设置工具提示颜色
            if use_dark:
                # 深色主题：深色背景 + 白色文字
                tooltip_bg = "rgb(45, 45, 45)"
                tooltip_text = "rgb(255, 255, 255)"
                tooltip_border = "rgb(100, 100, 100)"
            else:
                # 浅色主题：浅色背景 + 黑色文字
                tooltip_bg = "rgb(255, 255, 255)"
                tooltip_text = "rgb(0, 0, 0)"
                tooltip_border = "rgb(200, 200, 200)"
            
            # 获取当前样式表
            current_style = app.styleSheet()
            
            # 移除之前的工具提示样式（如果存在）
            lines = current_style.split('\n')
            filtered_lines = []
            skip_tooltip = False
            
            for line in lines:
                if 'QToolTip {' in line:
                    skip_tooltip = True
                    continue
                elif skip_tooltip and '}' in line:
                    skip_tooltip = False
                    continue
                elif not skip_tooltip:
                    filtered_lines.append(line)
            
            # 创建新的工具提示样式（更紧凑）
            tooltip_style = f"""
QToolTip {{
    background-color: {tooltip_bg};
    color: {tooltip_text};
    border: 1px solid {tooltip_border};
    border-radius: 2px;
    padding: 1px 3px;
    font-size: 10px;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    max-width: 150px;
    word-wrap: break-word;
    line-height: 1.2;
}}
"""
            
            # 应用新样式
            new_style = '\n'.join(filtered_lines) + tooltip_style
            app.setStyleSheet(new_style)
            
            # 记录当前应用的主题状态
            self._current_tooltip_theme = use_dark
            
            logging.debug(f"工具提示样式已应用: {'深色' if use_dark else '浅色'}主题")
            
        except Exception as e:
            logging.error(f"应用工具提示样式失败: {e}")
    
    def add_shadow_effect(self):
        """添加阴影效果"""
        try:
            # 清理已存在的shadow_effect
            if hasattr(self, 'shadow_effect') and self.shadow_effect:
                try:
                    # 验证是否仍然有效
                    _ = self.shadow_effect.blurRadius()
                    # 如果有效且是当前效果，先清除
                    current_effect = self.graphicsEffect()
                    if current_effect == self.shadow_effect:
                        self.setGraphicsEffect(None)
                except (RuntimeError, AttributeError):
                    # 已被删除，忽略
                    pass
            
            # 创建新的阴影效果
            # 注意：阴影效果会在需要透明度动画时被临时替换
            self.shadow_effect = QGraphicsDropShadowEffect()
            self.shadow_effect.setBlurRadius(10)  # 减少模糊半径，避免渲染问题
            self.shadow_effect.setColor(QColor(0, 0, 0, 50))  # 降低透明度
            self.shadow_effect.setOffset(0, 0)  # 不偏移，避免显示下方阴影方块
            self.setGraphicsEffect(self.shadow_effect)
            logging.debug("阴影效果创建成功")
            
        except Exception as e:
            logging.warning(f"创建阴影效果失败: {e}")
            # 确保shadow_effect引用被清除
            self.shadow_effect = None
    
    def _cleanup_animations(self):
        """清理动画对象"""
        try:
            logging.debug("开始清理动画对象")
            
            # 停止并清理动画组
            if hasattr(self, 'show_animation_group') and self.show_animation_group:
                try:
                    if self.show_animation_group.state() != QAbstractAnimation.Stopped:
                        self.show_animation_group.stop()
                    self.show_animation_group.clear()
                    # 断开所有信号连接
                    try:
                        self.show_animation_group.finished.disconnect()
                    except TypeError:
                        pass  # 信号未连接
                except (RuntimeError, AttributeError):
                    pass  # 对象可能已被删除
            
            # 停止并清理单独的动画
            for anim_name in ['size_animation', 'opacity_animation', 'scale_animation', 'fade_in_animation']:
                if hasattr(self, anim_name):
                    anim = getattr(self, anim_name)
                    if anim:
                        try:
                            if anim.state() != QAbstractAnimation.Stopped:
                                anim.stop()
                            # 断开信号连接
                            if hasattr(anim, 'valueChanged'):
                                try:
                                    anim.valueChanged.disconnect()
                                except TypeError:
                                    pass  # 信号未连接
                        except (RuntimeError, AttributeError):
                            pass  # 对象可能已被删除
            
            # 停止定时器
            for timer_name in ['color_timer', 'pulse_timer']:
                if hasattr(self, timer_name):
                    timer = getattr(self, timer_name)
                    if timer:
                        try:
                            if timer.isActive():
                                timer.stop()
                            try:
                                timer.timeout.disconnect()
                            except TypeError:
                                pass  # 信号未连接
                        except (RuntimeError, AttributeError):
                            pass  # 对象可能已被删除
            
            # 清除图形效果
            try:
                # 清除opacity_effect
                if hasattr(self, 'opacity_effect') and self.opacity_effect:
                    try:
                        self.setGraphicsEffect(None)  # 先移除效果
                        # 不立即删除，让Qt自动管理生命周期
                    except (RuntimeError, AttributeError):
                        pass
                
                # 安全处理shadow_effect
                if hasattr(self, 'shadow_effect') and self.shadow_effect:
                    try:
                        # 验证shadow_effect是否仍然有效
                        _ = self.shadow_effect.blurRadius()
                        # 如果当前图形效果是shadow_effect，则清除
                        current_effect = self.graphicsEffect()
                        if current_effect == self.shadow_effect:
                            self.setGraphicsEffect(None)
                    except (RuntimeError, AttributeError):
                        # shadow_effect已被删除或无效
                        pass
            except Exception as effect_error:
                logging.warning(f"清理图形效果时出错: {effect_error}")
            
            # 清除引用
            self.show_animation_group = None
            self.size_animation = None
            self.opacity_animation = None
            self.scale_animation = None
            self.fade_in_animation = None
            self.opacity_effect = None
            
            # 清除强引用列表
            if hasattr(self, '_animation_refs'):
                self._animation_refs.clear()
            
            # 重置初始化标记
            self._animations_initialized = False
            
        except Exception as e:
            logging.error(f"清理动画时出错: {e}")
            # 强制重置所有引用
            self.show_animation_group = None
            self.size_animation = None
            self.opacity_animation = None
            self.scale_animation = None
            self.fade_in_animation = None
            self.opacity_effect = None
            self._animations_initialized = False

    def _validate_animation_objects(self):
        """验证动画对象的有效性"""
        try:
            required_objects = ['show_animation_group', 'scale_animation', 'fade_in_animation', 'opacity_effect']
            validation_results = {}
            
            for obj_name in required_objects:
                validation_results[obj_name] = {"exists": False, "valid": False, "parent_ok": False, "details": ""}
                
                if not hasattr(self, obj_name):
                    validation_results[obj_name]["details"] = "属性不存在"
                    continue
                    
                validation_results[obj_name]["exists"] = True
                obj = getattr(self, obj_name)
                if obj is None:
                    validation_results[obj_name]["details"] = "对象为None"
                    continue
                    
                # 检查Qt对象是否仍然有效（未被删除）
                try:
                    # 尝试访问对象的基本属性来验证其有效性
                    if hasattr(obj, 'parent'):
                        parent = obj.parent()
                        # 验证父对象是否正确
                        if parent != self and parent is not None:
                            # 尝试修复父对象
                            try:
                                obj.setParent(self)
                            except Exception as fix_e:
                                logging.warning(f"修复父对象失败: {obj_name}, 错误: {fix_e}")
                                return False
                    elif hasattr(obj, 'state'):
                        state = obj.state()
                        # 检查动画状态是否正常
                        if state == QAbstractAnimation.State.Stopped and hasattr(obj, 'targetObject'):
                            target = obj.targetObject()
                            if target is None:
                                return False
                    elif hasattr(obj, 'opacity'):
                        _ = obj.opacity()
                    
                    # 对于动画对象，额外检查目标对象
                    if hasattr(obj, 'targetObject'):
                        target = obj.targetObject()
                        if target is None:
                            return False
                        # 验证目标对象是否有效
                        try:
                            _ = target.parent()
                        except RuntimeError:
                            return False
                    
                    # 对于动画组，检查其子动画
                    if hasattr(obj, 'animationCount'):
                        try:
                            count = obj.animationCount()
                            for i in range(count):
                                child_anim = obj.animationAt(i)
                                if child_anim is None:
                                    return False
                                # 验证子动画的有效性
                                _ = child_anim.state()
                                # 验证子动画的父对象
                                if hasattr(child_anim, 'parent'):
                                    child_parent = child_anim.parent()
                                    if child_parent != obj and child_parent != self:
                                        try:
                                            child_anim.setParent(obj)
                                        except Exception:
                                            return False
                        except RuntimeError as e:
                            return False
                            
                except RuntimeError as e:
                    validation_results[obj_name]["details"] = f"对象已被删除: {e}"
                    continue
                except Exception as e:
                    validation_results[obj_name]["details"] = f"验证异常: {e}"
                    continue
                
                # 如果到达这里，说明对象验证通过
                validation_results[obj_name]["valid"] = True
                validation_results[obj_name]["parent_ok"] = True
                validation_results[obj_name]["details"] = "验证通过"
            
            # 检查引用列表的完整性
            if hasattr(self, '_animation_refs'):
                valid_refs = []
                for ref in self._animation_refs:
                    try:
                        if hasattr(ref, 'parent'):
                            _ = ref.parent()
                        elif hasattr(ref, 'state'):
                            _ = ref.state()
                        elif hasattr(ref, 'opacity'):
                            _ = ref.opacity()
                        valid_refs.append(ref)
                    except RuntimeError:
                        continue
                
                # 更新引用列表，移除无效引用
                self._animation_refs = valid_refs
            
            # 汇总验证结果
            valid_count = sum(1 for result in validation_results.values() if result["valid"])
            total_count = len(required_objects)
            
            # 判断是否通过验证
            if valid_count == total_count:
                return True
            else:
                # 只在验证失败时记录警告
                logging.warning(f"动画对象验证失败: 只有 {valid_count}/{total_count} 个对象有效")
                return False
            
        except Exception as e:
            logging.warning(f"验证动画对象时出错: {e}")
            return False
    
    def _lightweight_animation_check(self):
        """轻量级动画对象检查，只检查关键对象是否存在"""
        try:
            return (hasattr(self, 'show_animation_group') and self.show_animation_group is not None and
                    hasattr(self, 'opacity_effect') and self.opacity_effect is not None and
                    hasattr(self, '_animations_initialized') and self._animations_initialized)
        except:
            return False
    
    def get_animation_status_report(self):
        """获取动画系统状态报告，用于诊断和监控"""
        report = {
            'timestamp': QTime.currentTime().toString(),
            'animation_system': {
                'initialized': getattr(self, '_animations_initialized', False),
                'objects_exist': {},
                'objects_valid': {},
                'call_statistics': {}
            },
            'performance': {
                'smooth_show_calls': getattr(self, '_smooth_show_call_count', 0),
                'last_call_time': getattr(self, '_last_smooth_show_time', 0),
                'last_validation_time': getattr(self, '_last_validation_time', 0)
            },
            'health_status': 'unknown'
        }
        
        # 检查动画对象存在性
        animation_objects = ['show_animation_group', 'hide_animation_group', 'scale_animation', 
                           'fade_in_animation', 'opacity_effect']
        
        for obj_name in animation_objects:
            exists = hasattr(self, obj_name) and getattr(self, obj_name) is not None
            report['animation_system']['objects_exist'][obj_name] = exists
            
            if exists:
                try:
                    obj = getattr(self, obj_name)
                    # 尝试访问对象属性来验证有效性
                    if hasattr(obj, 'state'):
                        _ = obj.state()
                    elif hasattr(obj, 'opacity'):
                        _ = obj.opacity()
                    elif hasattr(obj, 'parent'):
                        _ = obj.parent()
                    report['animation_system']['objects_valid'][obj_name] = True
                except RuntimeError:
                    report['animation_system']['objects_valid'][obj_name] = False
                except Exception:
                    report['animation_system']['objects_valid'][obj_name] = False
            else:
                report['animation_system']['objects_valid'][obj_name] = False
        
        # 计算健康状态
        total_objects = len(animation_objects)
        valid_objects = sum(1 for valid in report['animation_system']['objects_valid'].values() if valid)
        
        if valid_objects == total_objects:
            report['health_status'] = 'healthy'
        elif valid_objects >= total_objects * 0.8:
            report['health_status'] = 'warning'
        else:
            report['health_status'] = 'critical'
        
        # 添加调用频率统计
        current_time = QTime.currentTime().msecsSinceStartOfDay()
        if hasattr(self, '_last_smooth_show_time'):
            time_since_last = current_time - self._last_smooth_show_time
            report['performance']['time_since_last_call'] = time_since_last
        
        return report
    
    def log_animation_status(self, level='debug'):
        """记录动画系统状态到日志"""
        report = self.get_animation_status_report()
        
        status_msg = f"动画系统状态报告 - 健康状态: {report['health_status']}"
        valid_count = sum(1 for valid in report['animation_system']['objects_valid'].values() if valid)
        total_count = len(report['animation_system']['objects_valid'])
        status_msg += f", 有效对象: {valid_count}/{total_count}"
        
        if hasattr(self, '_smooth_show_call_count'):
            status_msg += f", 调用次数: {self._smooth_show_call_count}"
        
        if level == 'info':
            logging.info(status_msg)
        elif level == 'warning':
            logging.warning(status_msg)
        elif level == 'error':
            logging.error(status_msg)

    def _monitor_animation_health(self):
        """监控动画对象健康状态 - 优化版本"""
        try:
            if not hasattr(self, '_last_health_check'):
                self._last_health_check = 0
                self._health_check_failures = 0
            
            # 延长检查间隔到30秒，减少频繁检查
            current_time = QTime.currentTime().msecsSinceStartOfDay()
            if current_time - self._last_health_check < 30000:
                return True
            
            self._last_health_check = current_time
            
            # 简化的健康检查：只检查关键对象
            critical_objects = ['show_animation_group', 'scale_animation', 'fade_in_animation']
            missing_objects = []
            
            for obj_name in critical_objects:
                if not hasattr(self, obj_name) or getattr(self, obj_name) is None:
                    missing_objects.append(obj_name)
            
            if missing_objects:
                self._health_check_failures += 1
                if self._health_check_failures >= 2:  # 减少到2次失败就重新初始化
                    self._animations_initialized = False
                    self._health_check_failures = 0
                    return False
            else:
                self._health_check_failures = 0
            
            return True
            
        except Exception:
            # 减少异常日志，直接返回False
            return False

    def _lightweight_recovery(self):
        """简化的轻量级恢复"""
        try:
            # 只做最基本的清理：停止可能有问题的动画
            if hasattr(self, 'show_animation_group') and self.show_animation_group:
                try:
                    if self.show_animation_group.state() == QAbstractAnimation.State.Running:
                        self.show_animation_group.stop()
                except Exception:
                    pass
        except Exception:
            pass
            
            return True
            
        except Exception as e:
            logging.warning(f"轻量级恢复失败: {e}")
            return False

    def _preemptive_animation_check(self):
        """预防性动画检查，在关键操作前调用"""
        try:
            # 如果动画系统未初始化，直接返回False
            if not hasattr(self, '_animations_initialized') or not self._animations_initialized:
                return False
            
            # 快速验证关键动画对象
            critical_objects = ['show_animation_group', 'scale_animation', 'fade_in_animation']
            for obj_name in critical_objects:
                if not hasattr(self, obj_name):
                    return False
                obj = getattr(self, obj_name)
                if obj is None:
                    return False
                try:
                    _ = obj.state()
                except RuntimeError:
                    return False
            
            return True
            
        except Exception as e:
            logging.warning(f"预防性动画检查失败: {e}")
            return False

    def _safe_animation_group_operation(self, operation_func):
        """安全的动画组操作包装器"""
        try:
            # 操作前验证
            if not self._preemptive_animation_check():
                logging.warning("动画对象预检查失败，跳过操作")
                # 尝试重新初始化动画系统
                logging.debug("尝试重新初始化动画系统")
                self._animations_initialized = False
                self.setup_animations()
                # 再次检查
                if not self._preemptive_animation_check():
                    logging.error("重新初始化后预检查仍然失败")
                    return False
            
            # 执行操作
            result = operation_func()
            
            # 操作后验证
            if not self._preemptive_animation_check():
                logging.warning("动画对象操作后检查失败")
                return False
                
            return result
            
        except RuntimeError as e:
            logging.error(f"动画组操作失败 (RuntimeError): {e}")
            # 标记需要重新初始化
            self._animations_initialized = False
            return False
        except Exception as e:
            logging.error(f"动画组操作异常: {e}")
            return False

    def _force_cleanup_animations(self):
        """强制清理所有动画对象，防止内存泄漏和对象冲突"""
        try:
            logging.debug("开始强制清理动画对象")
            
            # 清理动画组
            if hasattr(self, 'show_animation_group') and self.show_animation_group:
                try:
                    if self.show_animation_group.state() != QAbstractAnimation.State.Stopped:
                        self.show_animation_group.stop()
                    self.show_animation_group.clear()
                    self.show_animation_group.deleteLater()
                except (RuntimeError, AttributeError):
                    pass
                finally:
                    self.show_animation_group = None
            
            # 清理不依赖于opacity_effect的动画对象
            independent_animations = ['size_animation', 'scale_animation']
            for attr in independent_animations:
                if hasattr(self, attr):
                    obj = getattr(self, attr)
                    if obj:
                        try:
                            if obj.state() != QAbstractAnimation.State.Stopped:
                                obj.stop()
                            obj.deleteLater()
                        except (RuntimeError, AttributeError):
                            pass
                        finally:
                            setattr(self, attr, None)
            
            # 清理透明度效果（会自动清理其子动画对象）
            if hasattr(self, 'opacity_effect') and self.opacity_effect:
                try:
                    self.opacity_effect.deleteLater()
                except (RuntimeError, AttributeError):
                    pass
                finally:
                    self.opacity_effect = None
                    # 清理依赖于opacity_effect的动画引用
                    self.opacity_animation = None
                    self.fade_in_animation = None
            
            # 等待Qt事件循环处理删除操作
            QThread.msleep(30)
            
            # 清理定时器
            timer_attrs = ['color_animation_timer', 'pulse_animation_timer']
            for attr in timer_attrs:
                if hasattr(self, attr):
                    timer = getattr(self, attr)
                    if timer:
                        try:
                            timer.stop()
                            timer.deleteLater()
                        except (RuntimeError, AttributeError):
                            pass
                        finally:
                            setattr(self, attr, None)
            
            # 清理动画引用列表
            if hasattr(self, '_animation_refs'):
                self._animation_refs.clear()
            
            logging.debug("动画对象强制清理完成")
            
        except Exception as e:
             logging.warning(f"强制清理动画对象时出错: {e}")

    def _robust_animation_recovery(self, start_rect, target_rect, max_retries=3):
        """健壮的动画恢复机制，提供多层次的错误恢复"""
        try:
            # 记录恢复开始时间，用于超时控制
            recovery_start_time = QTime.currentTime()
            
            # 只在第一次尝试时进行完整的重新初始化
            if not hasattr(self, '_recovery_initialized') or not self._recovery_initialized:
                logging.debug("执行完整的动画系统重新初始化")
                
                # 强制清理所有动画对象
                self._force_cleanup_animations()
                
                # 等待Qt事件循环处理清理
                for _ in range(3):
                    QApplication.processEvents()
                    QThread.msleep(50)  # 等待50ms让Qt完全清理对象
                
                # 重新初始化动画系统
                self._animations_initialized = False
                self.setup_animations()
                self._recovery_initialized = True
                
                # 再次等待确保对象完全创建
                QApplication.processEvents()
            
            for attempt in range(max_retries):
                # 检查恢复超时（最多5秒）
                current_time = QTime.currentTime()
                if recovery_start_time.msecsTo(current_time) > 5000:
                    logging.error("动画恢复超时，终止恢复过程")
                    return False
                
                # 验证动画对象是否有效
                if not self._validate_animation_objects():
                    logging.warning(f"动画对象验证失败，尝试 {attempt + 1}")
                    
                    # 根据尝试次数采用不同的恢复策略
                    if attempt == 0:
                        # 第一次失败：完全重新初始化
                        self._force_cleanup_animations()
                        QApplication.processEvents()
                        QThread.msleep(100)
                        self._animations_initialized = False
                        self.setup_animations()
                        QApplication.processEvents()
                        continue
                    elif attempt == 1:
                        # 第二次失败：尝试部分重建
                        self._partial_animation_rebuild()
                        continue
                    else:
                        # 后续尝试失败，直接跳过
                        continue
                
                # 尝试启动动画
                try:
                    # 验证关键对象存在且有效
                    if not (self.scale_animation and self.fade_in_animation and self.show_animation_group):
                        logging.warning(f"关键动画对象缺失，尝试 {attempt + 1}")
                        # 尝试重建缺失的对象
                        self._rebuild_missing_animations()
                        continue
                    
                    # 验证对象未被删除
                    try:
                        scale_state = self.scale_animation.state()
                        fade_state = self.fade_in_animation.state()
                        group_state = self.show_animation_group.state()
                    except RuntimeError as e:
                        logging.warning(f"动画对象已被删除，尝试 {attempt + 1}: {e}")
                        # 标记需要重新创建
                        self._animations_initialized = False
                        continue
                    
                    # 安全断开所有旧的信号连接
                    try:
                        self.scale_animation.valueChanged.disconnect()
                    except (RuntimeError, TypeError):
                        pass
                    try:
                        self.show_animation_group.finished.disconnect()
                    except (RuntimeError, TypeError):
                        pass
                    
                    # 设置动画参数
                    self.scale_animation.setStartValue(start_rect)
                    self.scale_animation.setEndValue(target_rect)
                    self.scale_animation.valueChanged.connect(self.on_animation_position_changed)
                    self.fade_in_animation.setStartValue(0.0)
                    self.fade_in_animation.setEndValue(1.0)
                    
                    # 使用安全的动画组操作
                    def recovery_animation_setup():
                        self.show_animation_group.clear()
                        self.show_animation_group.addAnimation(self.scale_animation)
                        self.show_animation_group.addAnimation(self.fade_in_animation)
                        self.show_animation_group.finished.connect(self.on_smooth_show_finished)
                        self.show_animation_group.start()
                        return True
                    
                    if self._safe_animation_group_operation(recovery_animation_setup):
                        return True
                        
                except Exception as e:
                    logging.warning(f"动画启动失败，尝试 {attempt + 1}: {e}")
                    # 在重试之间添加短暂延迟
                    QThread.msleep(100)
                    continue
            
            logging.error(f"动画恢复失败，已尝试 {max_retries} 次")
            return False
            
        except Exception as e:
            logging.error(f"动画恢复过程中出现异常: {e}")
            return False
        finally:
            # 重置恢复标志，为下次恢复做准备
            self._recovery_initialized = False

    def _partial_animation_rebuild(self):
        """部分重建动画对象，只重建有问题的部分"""
        try:
            logging.debug("开始部分重建动画对象")
            
            # 检查并重建缺失或无效的动画对象
            if not hasattr(self, 'scale_animation') or self.scale_animation is None:
                logging.debug("重建缩放动画")
                self.scale_animation = QPropertyAnimation(self, b"geometry", self)
                if hasattr(self, '_animation_refs'):
                    self._animation_refs.append(self.scale_animation)
            
            if not hasattr(self, 'fade_in_animation') or self.fade_in_animation is None:
                logging.debug("重建透明度动画")
                if hasattr(self, 'opacity_effect') and self.opacity_effect:
                    self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity", self)
                    if hasattr(self, '_animation_refs'):
                        self._animation_refs.append(self.fade_in_animation)
            
            if not hasattr(self, 'show_animation_group') or self.show_animation_group is None:
                logging.debug("重建动画组")
                self.show_animation_group = QParallelAnimationGroup(self)
                if hasattr(self, '_animation_refs'):
                    self._animation_refs.append(self.show_animation_group)
            
            # 验证重建结果
            rebuilt_count = 0
            if self.scale_animation:
                rebuilt_count += 1
            if self.fade_in_animation:
                rebuilt_count += 1
            if self.show_animation_group:
                rebuilt_count += 1
            
            return rebuilt_count > 0
            
        except Exception as e:
            logging.warning(f"部分重建动画对象失败: {e}")
            return False

    def _rebuild_missing_animations(self):
        """重建缺失的动画对象"""
        try:
            logging.debug("检查并重建缺失的动画对象")
            
            # 确保opacity_effect存在
            if not hasattr(self, 'opacity_effect') or self.opacity_effect is None:
                logging.debug("重建opacity_effect")
                self.opacity_effect = QGraphicsOpacityEffect(self)
                self.setGraphicsEffect(self.opacity_effect)
            
            # 重建缺失的动画对象
            missing_objects = []
            
            if not hasattr(self, 'scale_animation') or self.scale_animation is None:
                missing_objects.append('scale_animation')
                self.scale_animation = QPropertyAnimation(self, b"geometry", self)
                self.scale_animation.setDuration(300)
                self.scale_animation.setEasingCurve(QEasingCurve.Type.OutBack)
            
            if not hasattr(self, 'fade_in_animation') or self.fade_in_animation is None:
                missing_objects.append('fade_in_animation')
                self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity", self)
                self.fade_in_animation.setDuration(300)
                self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutQuart)
            
            if not hasattr(self, 'show_animation_group') or self.show_animation_group is None:
                missing_objects.append('show_animation_group')
                self.show_animation_group = QParallelAnimationGroup(self)
            
            # 更新引用列表
            if hasattr(self, '_animation_refs'):
                for obj_name in missing_objects:
                    obj = getattr(self, obj_name)
                    if obj and obj not in self._animation_refs:
                        self._animation_refs.append(obj)
            
            return len(missing_objects) == 0  # 如果没有缺失对象，返回True
            
        except Exception as e:
            logging.warning(f"重建缺失动画对象失败: {e}")
            return False

    def _emergency_animation_fallback(self):
        """紧急动画回退机制，使用最简单的显示方式"""
        try:
            # 停止所有可能正在运行的动画
            try:
                if hasattr(self, 'show_animation_group') and self.show_animation_group:
                    self.show_animation_group.stop()
                if hasattr(self, 'scale_animation') and self.scale_animation:
                    self.scale_animation.stop()
                if hasattr(self, 'fade_in_animation') and self.fade_in_animation:
                    self.fade_in_animation.stop()
            except RuntimeError:
                pass  # 对象可能已被删除
            
            # 直接设置最终状态
            self.show()
            self.raise_()
            self.activateWindow()
            
            # 设置透明度为完全可见
            if hasattr(self, 'opacity_effect') and self.opacity_effect:
                try:
                    self.opacity_effect.setOpacity(1.0)
                except RuntimeError:
                    # 如果opacity_effect有问题，移除它
                    self.setGraphicsEffect(None)
            
            # 设置目标几何位置
            target_rect = self.get_centered_rect(self.collapsed_width, self.collapsed_height)
            self.setGeometry(target_rect)
            
            # 标记动画完成
            self._animating = False
            self._programmatic_resize = False
            
            return True
            
        except Exception as e:
            logging.error(f"紧急动画回退失败: {e}")
            return False

    def setup_animations(self):
        """设置动画 - 简化版本"""
        try:
            # 防止重复初始化
            if getattr(self, '_animations_initialized', False):
                return
            
            # 清理旧的动画对象
            self._force_cleanup_animations()
            
            # 重置初始化标记
            self._animations_initialized = False
            
            # 创建透明度效果
            if not hasattr(self, 'opacity_effect') or self.opacity_effect is None:
                self.opacity_effect = QGraphicsOpacityEffect(self)
            
            # 创建尺寸动画
            self.size_animation = QPropertyAnimation(self, b"geometry", self)
            self.size_animation.setDuration(350)
            self.size_animation.setEasingCurve(QEasingCurve.Type.OutQuart)
            
            # 创建透明度动画
            if self.opacity_effect:
                self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity", self)
                self.opacity_animation.setDuration(300)
                self.opacity_animation.setEasingCurve(QEasingCurve.Type.OutQuart)
            
            # 创建显示动画组合
            if not hasattr(self, 'show_animation_group') or self.show_animation_group is None:
                self.show_animation_group = QParallelAnimationGroup(self)
            
            # 创建缩放动画
            if not hasattr(self, 'scale_animation') or self.scale_animation is None:
                self.scale_animation = QPropertyAnimation(self, b"geometry", self)
                self.scale_animation.setDuration(350)
                self.scale_animation.setEasingCurve(QEasingCurve.Type.OutQuart)
            
            # 创建渐入动画
            if self.opacity_effect and (not hasattr(self, 'fade_in_animation') or self.fade_in_animation is None):
                self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity", self)
                self.fade_in_animation.setDuration(400)
                self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
                self.fade_in_animation.setStartValue(0.0)
                self.fade_in_animation.setEndValue(1.0)
            
            # 组装动画组
            if self.show_animation_group and self.scale_animation and self.fade_in_animation:
                self.show_animation_group.clear()
                self.show_animation_group.addAnimation(self.scale_animation)
                self.show_animation_group.addAnimation(self.fade_in_animation)
            
            # 创建颜色动画定时器
            if not hasattr(self, 'color_timer') or self.color_timer is None:
                self.color_timer = QTimer(self)
                self.color_timer.timeout.connect(self.update_colors)
            
            # 创建脉冲动画定时器
            if not hasattr(self, 'pulse_timer') or self.pulse_timer is None:
                self.pulse_timer = QTimer(self)
                self.pulse_timer.timeout.connect(self.pulse_effect)
                self.pulse_phase = 0
            
            # 标记动画已初始化
            self._animations_initialized = True
            
        except Exception as e:
            logging.error(f"动画初始化失败: {e}")
            self._animations_initialized = False

    def setup_timers(self):
        """设置定时器"""
        # 自动隐藏定时器
        self.auto_hide_timer = QTimer(self)
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.timeout.connect(self.auto_collapse)
        
        # 状态重置定时器
        self.state_reset_timer = QTimer(self)
        self.state_reset_timer.setSingleShot(True)
        self.state_reset_timer.timeout.connect(self.reset_to_idle)
    
    def restart_auto_hide_timer(self):
        """重新启动自动隐藏定时器"""
        # 只有在鼠标不在灵动岛上时才启动定时器
        if not self._hover_state:
            try:
                if self._expanded:
                    self.auto_hide_timer.start(5000)  # 展开状态下5秒后隐藏
                elif self.isVisible():
                    self.auto_hide_timer.start(3000)  # 收缩状态下3秒后隐藏
            except RuntimeError:
                # 如果定时器已被删除（极端情况下），安全忽略
                pass
    
    def setup_shortcuts(self):
        """设置快捷键"""
        # 切换展开/收缩 - Space键
        self.toggle_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.toggle_shortcut.activated.connect(self.toggle_expansion)
        
        # 显示/隐藏 - Ctrl+D
        self.visibility_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        self.visibility_shortcut.activated.connect(self.toggle_visibility)
        
        # 重置状态 - Escape键
        self.reset_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.reset_shortcut.activated.connect(self.reset_to_idle)
        
        # 模拟进度 - Ctrl+P
        self.progress_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        self.progress_shortcut.activated.connect(self.simulate_progress)
        
        # 显示成功通知 - Ctrl+S
        self.success_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.success_shortcut.activated.connect(lambda: self.show_success("快捷键测试", "成功通知"))
        
        # 显示错误通知 - Ctrl+E
        self.error_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        self.error_shortcut.activated.connect(lambda: self.show_error("快捷键测试", "错误通知"))
        
        # 显示信息通知 - Ctrl+I
        self.info_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        self.info_shortcut.activated.connect(lambda: self.show_info("快捷键测试", "信息通知"))
        
        # 显示OCR通知 - Ctrl+O
        self.ocr_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        self.ocr_shortcut.activated.connect(lambda: self.show_ocr_notification("OCR识别", "正在处理图像"))
        
        # 切换主题 - Ctrl+T
        self.theme_shortcut = QShortcut(QKeySequence("Ctrl+T"), self)
        self.theme_shortcut.activated.connect(self.toggle_theme)
        
        # 开启所有通知 - Ctrl+A
        self.all_notifications_shortcut = QShortcut(QKeySequence("Ctrl+A"), self)
        self.all_notifications_shortcut.activated.connect(self.enable_all_notifications)
        
        # 切换显示模式 - Ctrl+M
        self.mode_shortcut = QShortcut(QKeySequence("Ctrl+M"), self)
        self.mode_shortcut.activated.connect(self.cycle_display_mode)
        
        logging.info("快捷键设置完成")
    
    def setup_context_menu(self):
        """设置右键菜单"""
        self.context_menu = QMenu(self)
        
        # 通知类型子菜单
        notification_menu = self.context_menu.addMenu("📢 通知类型")
        
        # 开启所有通知 - 特殊功能
        all_notifications_action = notification_menu.addAction("🔔 开启所有通知\t\t\tCtrl+A")
        all_notifications_action.triggered.connect(self.enable_all_notifications)
        
        notification_menu.addSeparator()
        
        # 成功通知
        success_action = notification_menu.addAction("✅ 成功通知\t\t\tCtrl+S")
        success_action.triggered.connect(lambda: self.show_success("手动触发", "成功通知测试"))
        
        # 警告通知
        warning_action = notification_menu.addAction("⚠️ 警告通知")
        warning_action.triggered.connect(lambda: self.show_warning("手动触发", "警告通知测试"))
        
        # 错误通知
        error_action = notification_menu.addAction("❌ 错误通知\t\t\tCtrl+E")
        error_action.triggered.connect(lambda: self.show_error("手动触发", "错误通知测试"))
        
        # 信息通知
        info_action = notification_menu.addAction("ℹ️ 信息通知\t\t\tCtrl+I")
        info_action.triggered.connect(lambda: self.show_info("手动触发", "信息通知测试"))
        
        # OCR通知
        ocr_action = notification_menu.addAction("👁️ OCR通知\t\t\tCtrl+O")
        ocr_action.triggered.connect(lambda: self.show_ocr_notification("OCR识别", "正在处理图像"))
        
        # 系统通知
        system_action = notification_menu.addAction("⚙️ 系统通知")
        system_action.triggered.connect(lambda: self.show_system_notification("系统消息", "系统状态更新"))
        
        # 文件通知
        file_action = notification_menu.addAction("📄 文件通知")
        file_action.triggered.connect(lambda: self.show_file_notification("文件操作", "文件处理完成"))
        
        # 下载通知
        download_action = notification_menu.addAction("⬇️ 下载通知")
        download_action.triggered.connect(lambda: self.show_notification("下载完成", "文件已成功下载", "download"))
        
        # 上传通知
        upload_action = notification_menu.addAction("⬆️ 上传通知")
        upload_action.triggered.connect(lambda: self.show_notification("上传完成", "文件已成功上传", "upload"))
        
        # 安全通知
        security_action = notification_menu.addAction("🔒 安全通知")
        security_action.triggered.connect(lambda: self.show_notification("安全警告", "检测到安全威胁", "security"))
        
        # 更新通知
        update_action = notification_menu.addAction("🔄 更新通知")
        update_action.triggered.connect(lambda: self.show_notification("系统更新", "正在检查更新", "update"))
        
        # 消息通知
        message_action = notification_menu.addAction("💬 消息通知")
        message_action.triggered.connect(lambda: self.show_notification("新消息", "您有新的消息", "message"))
        
        self.context_menu.addSeparator()
        
        # 进度控制子菜单
        progress_menu = self.context_menu.addMenu("📊 进度控制")
        
        # 开始进度
        start_progress_action = progress_menu.addAction("▶️ 开始进度")
        start_progress_action.triggered.connect(lambda: self.start_progress("手动进度", "正在处理..."))
        
        # 模拟进度
        simulate_progress_action = progress_menu.addAction("🔄 模拟进度\t\t\tCtrl+P")
        simulate_progress_action.triggered.connect(self.simulate_progress)
        
        # 设置进度值子菜单
        progress_value_menu = progress_menu.addMenu("📈 设置进度值")
        for value in [25, 50, 75, 100]:
            action = progress_value_menu.addAction(f"{value}%")
            action.triggered.connect(lambda checked, v=value: self.set_progress(v, f"进度: {v}%"))
        
        self.context_menu.addSeparator()
        
        # 主题控制
        theme_menu = self.context_menu.addMenu("🎨 主题设置")
        
        # 自动主题
        auto_theme_action = theme_menu.addAction("🔄 自动主题")
        auto_theme_action.triggered.connect(lambda: self.set_theme("auto"))
        
        # 浅色主题
        light_theme_action = theme_menu.addAction("☀️ 浅色主题")
        light_theme_action.triggered.connect(lambda: self.set_theme("light"))
        
        # 深色主题
        dark_theme_action = theme_menu.addAction("🌙 深色主题")
        dark_theme_action.triggered.connect(lambda: self.set_theme("dark"))
        
        # 主题切换快捷键提示
        theme_menu.addSeparator()
        theme_shortcut_action = theme_menu.addAction("💡 主题切换\t\t\tCtrl+T")
        theme_shortcut_action.triggered.connect(self.toggle_theme)
        
        self.context_menu.addSeparator()
        
        # 显示控制
        display_menu = self.context_menu.addMenu("👁️ 显示控制")
        
        # 展开/收缩
        toggle_action = display_menu.addAction("🔄 切换展开")
        toggle_action.triggered.connect(self.toggle_expansion)
        
        # 显示模式切换
        mode_action = display_menu.addAction("🔄 切换显示模式\t\t\tCtrl+M")
        mode_action.triggered.connect(self.cycle_display_mode)
        
        # 显示/隐藏
        visibility_action = display_menu.addAction("👁️ 切换显示\t\t\tCtrl+D")
        visibility_action.triggered.connect(self.toggle_visibility)
        
        # 重置状态
        reset_action = display_menu.addAction("🔄 重置状态")
        reset_action.triggered.connect(self.reset_to_idle)
        
        self.context_menu.addSeparator()
        
        # 位置控制
        position_menu = self.context_menu.addMenu("📍 位置设置")
        
        # 居中定位
        center_action = position_menu.addAction("🎯 居中定位")
        center_action.triggered.connect(self.position_on_screen)
        
        # 连接菜单隐藏信号，确保菜单关闭时正确重置状态
        self.context_menu.aboutToHide.connect(self._on_menu_about_to_hide)
        
        logging.info("右键菜单设置完成")
    
    def toggle_visibility(self):
        """切换显示/隐藏状态"""
        if self.isVisible():
            self.hide()
            logging.info("通过快捷键隐藏灵动岛")
        else:
            self.smooth_show()
            logging.info("通过快捷键显示灵动岛")
    
    def detect_system_theme(self):
        """检测系统主题"""
        try:
            # 尝试通过Qt应用程序检测系统主题
            app = QApplication.instance()
            if app:
                palette = app.palette()
                # 检查窗口背景色的亮度来判断主题
                bg_color = palette.color(palette.ColorRole.Window)
                brightness = (bg_color.red() * 0.299 + bg_color.green() * 0.587 + bg_color.blue() * 0.114)
                is_dark = brightness < 128
                logging.info(f"检测到系统主题: {'深色' if is_dark else '浅色'}")
                return is_dark
        except Exception as e:
            logging.warning(f"无法检测系统主题: {e}")
        
        # 默认返回深色主题
        return True
    
    def update_theme_colors(self):
        """根据当前主题更新颜色"""
        # 标准化当前主题名称（防止直接设置了中文主题名称）
        normalized_theme = self._normalize_theme_name(self.current_theme)
        
        if normalized_theme == "auto":
            use_dark = self.is_dark_theme
        elif normalized_theme == "dark":
            use_dark = True
        else:  # light
            use_dark = False
        
        if use_dark:
            # 深色主题配色
            self.bg_color = QColor(20, 20, 20, 240)
            self.hover_color = QColor(35, 35, 35, 250)
            self.accent_color = QColor(0, 122, 255)
            self.text_color = QColor(255, 255, 255)
            self.secondary_text_color = QColor(160, 160, 160)
        else:
            # 浅色主题配色
            self.bg_color = QColor(248, 248, 248, 240)
            self.hover_color = QColor(235, 235, 235, 250)
            self.accent_color = QColor(0, 122, 255)
            self.text_color = QColor(0, 0, 0)
            self.secondary_text_color = QColor(100, 100, 100)
        
        # 更新UI元素的样式
        self.update_ui_styles()
        # 更新工具提示样式
        self._apply_tooltip_style()
        self.update()
        
        logging.info(f"主题颜色已更新: {'深色' if use_dark else '浅色'}")
    
    def update_ui_styles(self):
        """更新UI元素的样式"""
        try:
            # 更新标题标签样式
            if hasattr(self, 'title_label'):
                self.title_label.setStyleSheet(f"""
                    QLabel {{
                        color: {self.text_color.name()};
                        font-weight: 600;
                        font-size: 13px;
                        background: transparent;
                        border: none;
                    }}
                """)
            
            # 更新状态标签样式
            if hasattr(self, 'status_label'):
                self.status_label.setStyleSheet(f"""
                    QLabel {{
                        color: {self.secondary_text_color.name()};
                        font-size: 11px;
                        background: transparent;
                        border: none;
                    }}
                """)
            
            # 更新图标标签样式
            if hasattr(self, 'icon_label'):
                self.icon_label.setStyleSheet(f"""
                    QLabel {{
                        color: {self.text_color.name()};
                        font-size: 14px;
                        background: transparent;
                        border: none;
                    }}
                """)
            
            # 更新图标标签样式
            if hasattr(self, 'icon_label'):
                self.icon_label.setStyleSheet(f"""
                    QLabel {{
                        color: {self.text_color.name()};
                        font-size: 16px;
                        background: transparent;
                        border: none;
                    }}
                """)
            
            # 更新操作按钮样式
            if hasattr(self, 'action_buttons'):
                text_color = self.text_color.name()
                for btn in self.action_buttons.values():
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background: rgba(255, 255, 255, 0.1);
                            border: 1px solid rgba(255, 255, 255, 0.2);
                            border-radius: 14px;
                            color: {text_color};
                            font-size: 12px;
                            font-weight: 500;
                        }}
                        QPushButton:hover {{
                            background: rgba(255, 255, 255, 0.2);
                            border: 1px solid rgba(255, 255, 255, 0.3);
                        }}
                        QPushButton:pressed {{
                            background: rgba(255, 255, 255, 0.3);
                        }}
                    """)
        except Exception as e:
            logging.warning(f"更新UI样式时出错: {e}")
    
    def _normalize_theme_name(self, theme):
        """将中文主题名称转换为英文标准名称
        
        Args:
            theme: 主题名称（中文或英文）
            
        Returns:
            标准化的英文主题名称
        """
        # 中文到英文的主题名称映射
        theme_mapping = {
            "浅色": "light",
            "深色": "dark", 
            "自动": "auto",
            "light": "light",
            "dark": "dark",
            "auto": "auto"
        }
        
        normalized = theme_mapping.get(theme, theme)
        # 只在主题名称实际发生转换时记录日志
        if theme != normalized:
            logging.debug(f"主题名称映射: {theme} -> {normalized}")
        return normalized
    
    def set_theme(self, theme):
        """设置主题
        
        Args:
            theme: 主题类型 (支持中文: "浅色", "深色", "自动" 或英文: "light", "dark", "auto")
        """
        # 标准化主题名称
        normalized_theme = self._normalize_theme_name(theme)
        
        if normalized_theme in ["auto", "light", "dark"]:
            self.current_theme = normalized_theme
            if normalized_theme == "auto":
                self.is_dark_theme = self.detect_system_theme()
            elif normalized_theme == "dark":
                self.is_dark_theme = True
            else:  # light
                self.is_dark_theme = False
            self.update_theme_colors()
            logging.info(f"主题已设置为: {theme} (标准化: {normalized_theme})")
        else:
            logging.warning(f"无效的主题类型: {theme}")
    
    def toggle_theme(self):
        """切换主题"""
        if self.current_theme == "auto":
            self.set_theme("light")
        elif self.current_theme == "light":
            self.set_theme("dark")
        else:
            self.set_theme("auto")
    
    def paintEvent(self, event):
        """自定义绘制"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 清除背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        
        # 创建圆角矩形路径
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, self.border_radius, self.border_radius)
        
        # 绘制背景渐变
        gradient = self.create_background_gradient(rect)
        painter.fillPath(path, gradient)
        
        # 绘制边框
        if self._hover_state:
            painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.drawPath(path)
        
        # 绘制状态相关的装饰
        self.draw_state_decorations(painter, rect)
    
    def create_background_gradient(self, rect):
        """创建背景渐变"""
        if self.current_state == "working":
            gradient = QLinearGradient(0, 0, rect.width(), 0)
            gradient.setColorAt(0, QColor(0, 122, 255, 200))
            gradient.setColorAt(1, QColor(0, 100, 200, 200))
        elif self.current_state == "success":
            gradient = QLinearGradient(0, 0, rect.width(), 0)
            gradient.setColorAt(0, QColor(52, 199, 89, 200))
            gradient.setColorAt(1, QColor(40, 160, 70, 200))
        elif self.current_state == "error":
            gradient = QLinearGradient(0, 0, rect.width(), 0)
            gradient.setColorAt(0, QColor(255, 59, 48, 200))
            gradient.setColorAt(1, QColor(200, 40, 30, 200))
        else:
            # 默认状态
            base_color = self.hover_color if self._hover_state else self.bg_color
            gradient = QRadialGradient(rect.center(), rect.width() / 2)
            gradient.setColorAt(0, base_color.lighter(110))
            gradient.setColorAt(1, base_color)
        
        return QBrush(gradient)
    
    def draw_state_decorations(self, painter, rect):
        """绘制状态装饰"""
        if self.current_state == "working" and self.progress_value > 0:
            # 绘制进度条
            progress_rect = QRectF(2, rect.height() - 3, 
                                 (rect.width() - 4) * (self.progress_value / 100), 2)
            painter.fillRect(progress_rect, QColor(255, 255, 255, 180))
        
        elif self.current_state == "notification":
            # 绘制脉冲效果
            pulse_alpha = int(50 + 30 * math.sin(self.pulse_phase))
            pulse_color = QColor(255, 255, 255, pulse_alpha)
            painter.setPen(QPen(pulse_color, 2))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 
                                  self.border_radius - 1, self.border_radius - 1)
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            current_time = QTime.currentTime().msecsSinceStartOfDay()
            
            # 防抖处理：如果距离上次点击时间太短，忽略
            if current_time - self._last_click_time < 100:  # 100ms防抖
                return
            
            self._last_click_time = current_time
            
            # 如果正在动画中，将点击动作排队
            if self._animating:
                if self._expanded:
                    self._pending_click_action = "cycle_mode"
                else:
                    self._pending_click_action = "expand"
                logging.debug("🏝️ 灵动岛点击事件已排队，等待动画完成")
            else:
                # 立即处理点击
                self._handle_click_action()
            
            self.clicked.emit()
        elif event.button() == Qt.MouseButton.RightButton:
            # 显示右键菜单时停止自动隐藏定时器
            self.auto_hide_timer.stop()
            self._menu_showing = True  # 标记菜单正在显示
            # 显示右键菜单（菜单关闭时会自动触发aboutToHide信号）
            self.context_menu.exec(event.globalPosition().toPoint())
        super().mousePressEvent(event)
    
    def _handle_click_action(self):
        """处理点击动作"""
        if self._expanded:
            self.cycle_display_mode()
            logging.debug("🏝️ 灵动岛切换显示模式")
        else:
            self.toggle_expansion()
            logging.debug("🏝️ 灵动岛展开")
    
    def _process_pending_click(self):
        """处理待处理的点击事件"""
        if self._pending_click_action:
            action = self._pending_click_action
            self._pending_click_action = None
            
            if action == "cycle_mode" and self._expanded:
                self.cycle_display_mode()
                logging.debug("🏝️ 处理排队的模式切换")
            elif action == "expand" and not self._expanded:
                self.toggle_expansion()
                logging.debug("🏝️ 处理排队的展开动作")
    
    def enterEvent(self, event):
        """鼠标进入事件"""
        self._hover_state = True
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # 鼠标悬停时停止自动隐藏定时器
        self.auto_hide_timer.stop()
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开事件"""
        self._hover_state = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        # 鼠标离开时重新启动自动隐藏定时器，但如果菜单正在显示则不启动
        if not self._menu_showing:
            self.restart_auto_hide_timer()
        self.update()
        super().leaveEvent(event)
    
    def _on_menu_about_to_hide(self):
        """菜单即将隐藏时的处理"""
        self._menu_showing = False
        # 如果鼠标不在灵动岛上，重启自动隐藏定时器
        if not self._hover_state:
            self.restart_auto_hide_timer()
        logging.debug("右键菜单已隐藏，重置菜单状态")
    
    def toggle_expansion(self):
        """切换展开/收缩状态"""
        # 如果正在动画中，停止当前动画并立即切换到目标状态
        if self._animating:
            self.size_animation.stop()
            self._animating = False
            logging.debug("🏝️ 停止当前动画，立即切换状态")
        
        if self._expanded:
            self.collapse()
        else:
            self.expand()
    
    def expand(self):
        """展开灵动岛"""
        if self._expanded:
            return
        
        # 如果正在动画中，停止当前动画
        if self._animating:
            self.size_animation.stop()
            self._animating = False
        
        self._animating = True
        self._expanded = True
        self._programmatic_resize = True  # 标记为程序控制的尺寸变化
        
        # 显示操作按钮
        self.actions_container.show()
        
        # 动画到展开尺寸 - 使用居中计算
        current_rect = self.geometry()
        target_rect = self.get_centered_rect(self.expanded_width, self.expanded_height)
        
        # 使用统一的平滑展开动画
        self.size_animation.setDuration(350)  # 统一持续时间
        self.size_animation.setEasingCurve(QEasingCurve.Type.OutQuart)  # 统一缓动
        self.size_animation.setStartValue(current_rect)
        self.size_animation.setEndValue(target_rect)
        
        # 添加动画过程中的位置同步
        self.size_animation.valueChanged.connect(self.on_animation_position_changed)
        self.size_animation.finished.connect(self.on_expand_finished)
        self.size_animation.start()
        
        # 启动自动隐藏定时器
        self.auto_hide_timer.start(5000)
    
    def collapse(self):
        """收缩灵动岛"""
        if not self._expanded:
            return
        
        # 如果正在动画中，停止当前动画
        if self._animating:
            self.size_animation.stop()
            self._animating = False
        
        self._animating = True
        self._expanded = False
        self._programmatic_resize = True  # 标记为程序控制的尺寸变化
        
        # 隐藏操作按钮
        self.actions_container.hide()
        
        # 动画到收缩尺寸 - 使用居中计算
        current_rect = self.geometry()
        target_rect = self.get_centered_rect(self.collapsed_width, self.collapsed_height)
        
        # 使用统一的平滑收缩动画
        self.size_animation.setDuration(350)  # 统一持续时间
        self.size_animation.setEasingCurve(QEasingCurve.Type.OutQuart)  # 统一缓动
        self.size_animation.setStartValue(current_rect)
        self.size_animation.setEndValue(target_rect)
        
        # 添加动画过程中的位置同步
        self.size_animation.valueChanged.connect(self.on_animation_position_changed)
        self.size_animation.finished.connect(self.on_collapse_finished)
        self.size_animation.start()
        
        # 停止自动隐藏定时器
        self.auto_hide_timer.stop()
    
    def on_animation_position_changed(self, rect):
        """动画过程中位置变化回调"""
        # 确保动画过程中窗口位置正确
        if isinstance(rect, QRect):
            self.setGeometry(rect)
    
    def on_expand_finished(self):
        """展开动画完成"""
        self._animating = False
        self._programmatic_resize = False  # 清除程序控制标记
        self.expanded.emit()
        # 清理所有连接
        self.size_animation.valueChanged.disconnect()
        self.size_animation.finished.disconnect()
        
        # 处理待处理的点击事件
        QTimer.singleShot(50, self._process_pending_click)  # 延迟50ms确保状态稳定
    
    def on_collapse_finished(self):
        """收缩动画完成"""
        self._animating = False
        self._programmatic_resize = False  # 清除程序控制标记
        self.collapsed.emit()
        # 清理所有连接
        self.size_animation.valueChanged.disconnect()
        self.size_animation.finished.disconnect()
        
        # 处理待处理的点击事件
        QTimer.singleShot(50, self._process_pending_click)  # 延迟50ms确保状态稳定
    
    def auto_collapse(self):
        """自动收缩并隐藏"""
        # 如果鼠标正在悬停，则不执行自动隐藏
        if self._hover_state:
            return
            
        if self._expanded:
            self.collapse()
            # 收缩完成后使用平滑隐藏动画
            QTimer.singleShot(450, self.smooth_hide)
        else:
            # 如果没有展开，直接平滑隐藏
            self.smooth_hide()
    
    def trigger_action(self, action):
        """触发操作"""
        self.action_triggered.emit(action)
        
        # 执行对应的操作
        if action == "quick_ocr":
            self.quick_ocr_action()
        elif action == "settings":
            self.settings_action()
        elif action == "history":
            self.history_action()
    
    def quick_ocr_action(self):
        """快速OCR操作"""
        self.set_state("working", "识别中", "正在处理图像...")
        self.animate_button_press(self.action_buttons["quick_ocr"])
        
        # 模拟进度
        self.simulate_progress()
        
        logging.info("触发快速OCR识别")
    
    def settings_action(self):
        """设置操作"""
        self.set_state("notification", "设置", "打开设置面板")
        self.animate_button_press(self.action_buttons["settings"])
        
        # 2秒后恢复
        self.state_reset_timer.start(2000)
        
        logging.info("打开设置面板")
    
    def history_action(self):
        """历史记录操作"""
        self.set_state("notification", "历史", "查看历史记录")
        self.animate_button_press(self.action_buttons["history"])
        
        # 2秒后恢复
        self.state_reset_timer.start(2000)
        
        logging.info("打开历史记录")
    
    def animate_button_press(self, button):
        """按钮按压动画"""
        # 简单的缩放效果
        original_size = button.size()
        button.resize(int(original_size.width() * 0.9), int(original_size.height() * 0.9))
        
        QTimer.singleShot(100, lambda: button.resize(original_size))
    
    def simulate_progress(self):
        """模拟进度更新"""
        self.progress_value = 0
        progress_timer = QTimer()
        
        def update_progress():
            self.progress_value += 10
            self.update()
            
            if self.progress_value >= 100:
                progress_timer.stop()
                self.set_state("success", "完成", "识别成功")
                self.state_reset_timer.start(3000)
        
        progress_timer.timeout.connect(update_progress)
        progress_timer.start(200)
    
    def set_state(self, state, title=None, status=None):
        """设置状态"""
        self.current_state = state
        
        if title:
            self.main_text = title
            self.title_label.setText(title)
        
        if status:
            self.status_text = status
            self.status_label.setText(status)
        
        # 更新图标和颜色
        self.update_state_appearance()
        
        # 启动脉冲效果（如果是通知状态）
        if state == "notification":
            if hasattr(self, 'pulse_timer') and self.pulse_timer is not None:
                self.pulse_timer.start(50)
        else:
            if hasattr(self, 'pulse_timer') and self.pulse_timer is not None:
                self.pulse_timer.stop()
        
        self.update()
    
    def update_state_appearance(self):
        """更新状态外观"""
        state_config = {
            "idle": {"icon": "🔍", "color": "#34C759"},
            "working": {"icon": "⚡", "color": "#007AFF"},
            "notification": {"icon": "💬", "color": "#FF9500"},
            "success": {"icon": "✅", "color": "#34C759"},
            "error": {"icon": "❌", "color": "#FF3B30"}
        }
        
        config = state_config.get(self.current_state, state_config["idle"])
        
        # 更新图标
        self.icon_label.setText(config["icon"])
        
        # 更新状态指示器颜色
        self.status_indicator.setStyleSheet(f"""
            QWidget {{
                background-color: {config["color"]};
                border-radius: 4px;
                border: none;
            }}
        """)
    
    def pulse_effect(self):
        """脉冲效果"""
        self.pulse_phase += 0.2
        if self.pulse_phase >= 2 * math.pi:
            self.pulse_phase = 0
        self.update()
    
    def update_colors(self):
        """更新颜色（用于颜色过渡动画）"""
        self.update()
    
    def reset_to_idle(self):
        """重置到空闲状态"""
        self.set_state("idle", "炫舞OCR", "就绪")
        self.progress_value = 0
        self.progress_container.hide()
    
    def set_progress(self, value, message=None):
        """设置进度值"""
        self.progress_value = max(0, min(100, value))  # 确保在0-100范围内
        
        if message:
            self.status_text = message
            self.status_label.setText(message)
        
        # 如果进度大于0，显示进度条并设置为工作状态
        if self.progress_value > 0:
            self.set_state("working")
            self.progress_container.show()
        else:
            self.progress_container.hide()
        
        # 如果进度达到100%，自动切换到成功状态
        if self.progress_value >= 100:
            QTimer.singleShot(500, lambda: self.set_state("success", "完成", "识别成功"))
            QTimer.singleShot(1000, lambda: self.progress_container.hide())
        
        self.update()
    
    def start_progress(self, title="处理中", message="正在识别..."):
        """开始进度显示"""
        self.set_state("working", title, message)
        self.progress_value = 0
        self.progress_container.show()
        self.update()
    
    def finish_progress(self, success=True, title=None, message=None):
        """完成进度显示"""
        if success:
            self.set_state("success", title or "完成", message or "识别成功")
        else:
            self.set_state("error", title or "失败", message or "识别失败")
        
        # 延迟隐藏进度条
        QTimer.singleShot(1000, lambda: self.progress_container.hide())
    
    def show_notification(self, title, subtitle="", notification_type="info", duration=3000):
        """显示通知
        
        Args:
            title: 通知标题
            subtitle: 通知副标题
            notification_type: 通知类型 (info, success, warning, error, ocr, system)
            duration: 显示时长(毫秒)
        """
        # 定义通知类型配置
        notification_configs = {
            "info": {"icon": "ℹ️", "color": "#007AFF", "state": "notification"},
            "success": {"icon": "✅", "color": "#34C759", "state": "success"},
            "warning": {"icon": "⚠️", "color": "#FF9500", "state": "notification"},
            "error": {"icon": "❌", "color": "#FF3B30", "state": "error"},
            "ocr": {"icon": "👁️", "color": "#5856D6", "state": "working"},
            "system": {"icon": "⚙️", "color": "#8E8E93", "state": "notification"},
            "file": {"icon": "📄", "color": "#007AFF", "state": "notification"},
            "download": {"icon": "⬇️", "color": "#34C759", "state": "working"},
            "upload": {"icon": "⬆️", "color": "#FF9500", "state": "working"},
            "security": {"icon": "🔒", "color": "#FF3B30", "state": "notification"},
            "update": {"icon": "🔄", "color": "#5856D6", "state": "working"},
            "message": {"icon": "💬", "color": "#007AFF", "state": "notification"}
        }
        
        config = notification_configs.get(notification_type, notification_configs["info"])
        
        # 设置状态和图标
        self.set_state(config["state"], title, subtitle)
        self.icon_label.setText(config["icon"])
        
        # 更新状态指示器颜色
        self.status_indicator.setStyleSheet(f"""
            QWidget {{
                background-color: {config["color"]};
                border-radius: 4px;
                border: none;
            }}
        """)
        
        # 使用平滑显示动画
        self.smooth_show()
        
        # 根据通知类型调整显示时长
        if notification_type in ["error", "warning"]:
            duration = max(duration, 5000)  # 错误和警告至少显示5秒
        elif notification_type == "success":
            duration = min(duration, 2000)  # 成功消息最多显示2秒
        
        # 自动隐藏
        self.auto_hide_timer.start(duration)
        
        logging.info(f"显示{notification_type}通知: {title} - {subtitle}")
    
    def show_success(self, title, subtitle="", duration=2000):
        """显示成功通知"""
        self.show_notification(title, subtitle, "success", duration)
    
    def show_error(self, title, subtitle="", duration=5000):
        """显示错误通知"""
        self.show_notification(title, subtitle, "error", duration)
    
    def show_warning(self, title, subtitle="", duration=4000):
        """显示警告通知"""
        self.show_notification(title, subtitle, "warning", duration)
    
    def show_info(self, title, subtitle="", duration=3000):
        """显示信息通知"""
        self.show_notification(title, subtitle, "info", duration)
    
    def show_ocr_notification(self, title, subtitle="", duration=3000):
        """显示OCR相关通知"""
        self.show_notification(title, subtitle, "ocr", duration)
    
    def show_file_notification(self, title, subtitle="", duration=3000):
        """显示文件相关通知"""
        self.show_notification(title, subtitle, "file", duration)
    
    def show_system_notification(self, title, subtitle="", duration=3000):
        """显示系统通知"""
        self.show_notification(title, subtitle, "system", duration)
    
    def show_download_notification(self, title, subtitle="", duration=3000):
        """显示下载通知"""
        self.show_notification(title, subtitle, "download", duration)
    
    def show_upload_notification(self, title, subtitle="", duration=3000):
        """显示上传通知"""
        self.show_notification(title, subtitle, "upload", duration)
    
    def show_security_notification(self, title, subtitle="", duration=3000):
        """显示安全通知"""
        self.show_notification(title, subtitle, "security", duration)
    
    def show_update_notification(self, title, subtitle="", duration=3000):
        """显示更新通知"""
        self.show_notification(title, subtitle, "update", duration)
    
    def show_message_notification(self, title, subtitle="", duration=3000):
        """显示消息通知"""
        self.show_notification(title, subtitle, "message", duration)
    
    def enable_all_notifications(self):
        """开启所有通知 - 依次展示所有类型的通知"""
        notification_types = [
            ("success", "成功通知", "所有功能正常运行"),
            ("info", "信息通知", "系统信息已更新"),
            ("warning", "警告通知", "请注意系统状态"),
            ("error", "错误通知", "发现潜在问题"),
            ("ocr", "OCR通知", "图像识别功能已启用"),
            ("system", "系统通知", "系统监控已开启"),
            ("file", "文件通知", "文件监控已激活"),
            ("download", "下载通知", "下载功能已就绪"),
            ("upload", "上传通知", "上传功能已就绪"),
            ("security", "安全通知", "安全防护已启用"),
            ("update", "更新通知", "更新检查已开启"),
            ("message", "消息通知", "消息推送已启用")
        ]
        
        # 显示开启通知的提示
        self.show_notification("灵动岛通知", "正在开启所有消息通知...", "system", 2000)
        
        # 延迟显示各种通知类型
        for i, (notification_type, title, subtitle) in enumerate(notification_types):
            delay = (i + 1) * 1500  # 每个通知间隔1.5秒
            QTimer.singleShot(delay, lambda nt=notification_type, t=title, s=subtitle: 
                             self.show_notification(t, s, nt, 2000))
        
        # 最后显示完成提示
        final_delay = len(notification_types) * 1500 + 1000
        QTimer.singleShot(final_delay, lambda: 
                         self.show_notification("通知开启完成", "所有消息通知已成功启用", "success", 3000))
        
        logging.info("开启所有通知类型展示")
    
    def position_on_screen(self):
        """将灵动岛定位到屏幕顶部中央"""
        try:
            # 获取当前鼠标所在的屏幕或主屏幕
            cursor_pos = QCursor.pos()
            screen = QApplication.screenAt(cursor_pos)
            if screen is None:
                screen = QApplication.primaryScreen()
            
            screen_geometry = screen.geometry()
            
            # 计算居中位置（相对于屏幕的绝对坐标）
            x = screen_geometry.x() + (screen_geometry.width() - self.width()) // 2
            y = screen_geometry.y() + 20  # 距离屏幕顶部20像素
            
            # 确保位置在屏幕范围内
            x = max(screen_geometry.x(), min(x, screen_geometry.x() + screen_geometry.width() - self.width()))
            y = max(screen_geometry.y(), min(y, screen_geometry.y() + screen_geometry.height() - self.height()))
            
            # 移动窗口到计算的位置
            self.move(x, y)
            
            logging.debug(f"灵动岛定位到: ({x}, {y}), 屏幕: {screen_geometry}")
            
        except Exception as e:
            logging.error(f"定位灵动岛时出错: {e}")
            # 默认位置
            self.move(100, 20)
    
    def show_status(self, status, color=None):
        """显示状态"""
        self.status_label.setText(status)
        
        if color:
            self.status_indicator.setStyleSheet(f"""
                QWidget {{
                    background-color: {color.name()};
                    border-radius: 4px;
                    border: none;
                }}
            """)
        
        self.update()
    
    def get_centered_rect(self, width, height):
        """获取居中的矩形位置"""
        try:
            # 获取屏幕几何信息
            screen = QApplication.primaryScreen()
            screen_geometry = screen.geometry()
            
            # 计算精确的居中位置
            x = screen_geometry.x() + (screen_geometry.width() - width) // 2
            y = screen_geometry.y() + 20  # 距离屏幕顶部20像素
            
            # 确保位置在屏幕范围内
            x = max(screen_geometry.x(), min(x, screen_geometry.x() + screen_geometry.width() - width))
            y = max(screen_geometry.y(), min(y, screen_geometry.y() + screen_geometry.height() - height))
            
            rect = QRect(x, y, width, height)
            return rect
            
        except Exception as e:
            logging.error(f"计算居中位置时出错: {e}")
            # 返回默认位置
            return QRect(100, 20, width, height)
    
    def update_position(self):
        """更新位置（居中显示）"""
        self.position_on_screen()
    
    def showEvent(self, event):
        """窗口显示事件 - 确保每次显示时都居中"""
        super().showEvent(event)
        # 使用QTimer.singleShot确保在窗口完全显示后再定位
        QTimer.singleShot(10, self.position_on_screen)
    
    def resizeEvent(self, event):
        """窗口尺寸变化事件 - 重新居中定位"""
        super().resizeEvent(event)
        # 只在非动画状态且非程序控制的尺寸变化时重新定位
        if (self.isVisible() and not self._animating and 
            not getattr(self, '_programmatic_resize', False)):
            QTimer.singleShot(50, self.position_on_screen)
    

    
    def hide_notification(self):
        """隐藏通知"""
        self.collapse()
        self.auto_hide_timer.stop()
        
        # 延迟隐藏整个窗口
        QTimer.singleShot(400, self.hide_completely)
    
    def smooth_show(self):
        """平滑显示灵动岛"""
        # 添加调用频率控制，避免过于频繁的验证
        current_time = QTime.currentTime().msecsSinceStartOfDay()
        if not hasattr(self, '_last_smooth_show_time'):
            self._last_smooth_show_time = 0
            self._smooth_show_call_count = 0
        
        # 如果距离上次调用时间很短（小于500ms），减少验证频率
        time_since_last = current_time - self._last_smooth_show_time
        self._smooth_show_call_count += 1
        
        if time_since_last < 500:
            # 只进行轻量级检查
            if self._lightweight_animation_check():
                # 直接执行显示逻辑，跳过验证
                self._execute_smooth_show_animation()
                return
        
        self._last_smooth_show_time = current_time
        
        # 执行动画健康监控（但不是每次都执行）
        if self._smooth_show_call_count % 3 == 1:  # 每3次调用才执行一次健康监控
            self._monitor_animation_health()
        
        # 预防性检查动画对象状态
        if not self._preemptive_animation_check():
            self._animations_initialized = False
        
        # 确保动画系统已初始化
        if not hasattr(self, '_animations_initialized') or not self._animations_initialized:
            self.setup_animations()
            
        # 检查关键动画对象是否存在且有效（减少验证频率）
        validation_needed = True
        if hasattr(self, '_last_validation_time'):
            if current_time - self._last_validation_time < 1000:  # 1秒内不重复验证
                validation_needed = False
                logging.debug("跳过重复验证（距离上次验证不足1秒）")
        
        if validation_needed:
            self._last_validation_time = current_time
            if not self._validate_animation_objects():
                logging.warning("动画对象无效，重新初始化")
                self._animations_initialized = False
                self.setup_animations()
                
                # 再次验证
                if not self._validate_animation_objects():
                    logging.error("动画系统初始化失败，使用简化显示")
                    self._fallback_show()
                    return
        
        # 执行实际的显示动画
        self._execute_smooth_show_animation()
    
    def _execute_smooth_show_animation(self):
        """执行实际的平滑显示动画逻辑"""
        try:
            self._programmatic_resize = True  # 标记为程序控制的尺寸变化
            
            # 确保opacity_effect存在
            if not hasattr(self, 'opacity_effect') or self.opacity_effect is None:
                self.setup_animations()
                if not self._validate_animation_objects():
                    self._fallback_show()
                    return
            
            # 设置初始状态
            self.setGraphicsEffect(self.opacity_effect)
            self.opacity_effect.setOpacity(0.0)
            
            # 计算目标位置
            target_rect = self.get_centered_rect(self.collapsed_width, self.collapsed_height)
            
            # 起始位置（从中心缩放）
            scale_factor = 0.7
            start_width = int(self.collapsed_width * scale_factor)
            start_height = int(self.collapsed_height * scale_factor)
            start_x = target_rect.x() + (self.collapsed_width - start_width) // 2
            start_y = target_rect.y() + (self.collapsed_height - start_height) // 2
            start_rect = QRect(start_x, start_y, start_width, start_height)
            
            # 设置起始几何位置
            self.setGeometry(start_rect)
            
            # 显示窗口
            self.show()
            self.raise_()
            self.activateWindow()
            
            # 验证动画对象
            if not self._validate_animation_objects():
                self._fallback_show()
                return
            
            # 停止任何正在运行的动画
            try:
                if self.show_animation_group.state() == QParallelAnimationGroup.State.Running:
                    self.show_animation_group.stop()
            except RuntimeError:
                self.setup_animations()
                if not self._validate_animation_objects():
                    self._fallback_show()
                    return
            
            # 清理之前的连接
            try:
                self.show_animation_group.finished.disconnect()
            except:
                pass
            try:
                self.scale_animation.valueChanged.disconnect()
            except:
                pass
            
            # 设置动画
            try:
                self.scale_animation.setStartValue(start_rect)
                self.scale_animation.setEndValue(target_rect)
                self.scale_animation.valueChanged.connect(self.on_animation_position_changed)
                self.fade_in_animation.setStartValue(0.0)
                self.fade_in_animation.setEndValue(1.0)
            except RuntimeError:
                self._fallback_show()
                return
            
            # 启动动画
            def setup_and_start_animation():
                self.show_animation_group.clear()
                self.show_animation_group.addAnimation(self.scale_animation)
                self.show_animation_group.addAnimation(self.fade_in_animation)
                self.show_animation_group.finished.connect(self.on_smooth_show_finished)
                self.show_animation_group.start()
                return True
            
            # 执行动画
            if not self._safe_animation_group_operation(setup_and_start_animation):
                if self._robust_animation_recovery(start_rect, target_rect):
                    return
                else:
                    self._fallback_show()
                    return
            
        except Exception:
            self._fallback_show()
    
    def _fallback_show(self):
        """后备显示方式，增强稳定性和错误处理"""
        try:
            # 首先尝试紧急回退机制
            if self._emergency_animation_fallback():
                return
            
            # 如果紧急回退失败，使用基本显示
            
            # 先尝试基本显示，确保窗口可见
            self.show()
            self.raise_()
            self.activateWindow()
            
            # 设置基本几何位置
            target_rect = self.get_centered_rect(self.collapsed_width, self.collapsed_height)
            self.setGeometry(target_rect)
            
            # 尝试重新初始化动画系统（但不依赖它）
            try:
                # 清理当前动画系统
                self._cleanup_animations()
                
                # 等待一小段时间让Qt处理清理
                QApplication.processEvents()
                QThread.msleep(50)
                
                # 重新初始化动画系统
                self.setup_animations()
                
                # 验证动画对象是否有效
                if self._validate_animation_objects():
                    # 标记动画系统可用
                    self._animations_initialized = True
                else:
                    logging.warning("动画系统重新初始化后验证失败")
                    # 标记动画系统不可用，但不影响基本显示
                    self._animations_initialized = False
                    
            except Exception as reinit_error:
                logging.warning(f"动画系统重新初始化失败: {reinit_error}")
                # 标记动画系统不可用
                self._animations_initialized = False
            
            # 移除可能有问题的图形效果
            try:
                self.setGraphicsEffect(None)
            except Exception:
                pass
            
            # 重置程序控制标记
            self._programmatic_resize = False
            
            # 触发显示完成信号
            try:
                self.on_smooth_show_finished()
            except Exception as signal_error:
                logging.warning(f"触发显示完成信号失败: {signal_error}")
            
        except Exception as fallback_error:
            logging.error(f"后备显示失败: {fallback_error}")
            # 最后的简单显示方式
            try:
                self.setGraphicsEffect(None)
                self.show()
                self.raise_()
                self.activateWindow()
                target_rect = self.get_centered_rect(self.collapsed_width, self.collapsed_height)
                self.setGeometry(target_rect)
                self._programmatic_resize = False
            except Exception as final_error:
                logging.error(f"最终显示方式也失败: {final_error}")
    

    
    def on_smooth_show_finished(self):
        """平滑显示动画完成"""
        try:
            self._programmatic_resize = False  # 清除程序控制标记
            
            # 安全断开动画组信号
            if hasattr(self, 'show_animation_group') and self.show_animation_group is not None:
                try:
                    self.show_animation_group.finished.disconnect()
                except:
                    pass  # 如果没有连接则忽略
            
            # 清理缩放动画连接
            if hasattr(self, 'scale_animation') and self.scale_animation is not None:
                try:
                    self.scale_animation.valueChanged.disconnect()
                except:
                    pass  # 如果没有连接则忽略
            
            # 安全恢复阴影效果
            try:
                if hasattr(self, 'shadow_effect') and self.shadow_effect is not None:
                    # 验证shadow_effect是否仍然有效
                    try:
                        _ = self.shadow_effect.blurRadius()  # 测试访问
                        self.setGraphicsEffect(self.shadow_effect)
                    except RuntimeError:
                        # shadow_effect已被删除，重新创建
                        self.add_shadow_effect()
                else:
                    # shadow_effect不存在，创建新的
                    self.add_shadow_effect()
            except Exception as shadow_error:
                logging.warning(f"恢复阴影效果失败: {shadow_error}")
                
        except Exception as e:
            logging.error(f"on_smooth_show_finished 执行出错: {e}")
        
        # 如果需要展开，则展开
        if not self._expanded:
            self.expand()

    def smooth_hide(self):
        """平滑隐藏灵动岛"""
        try:
            
            # 如果已有隐藏动画在运行，先停止
            if hasattr(self, '_hide_animation_group') and self._hide_animation_group:
                try:
                    if self._hide_animation_group.state() != QAbstractAnimation.State.Stopped:
                        self._hide_animation_group.stop()
                    self._hide_animation_group.deleteLater()
                except (RuntimeError, AttributeError):
                    pass
                finally:
                    self._hide_animation_group = None
            
            # 检查并确保opacity_effect存在且有效
            opacity_effect_valid = False
            if hasattr(self, 'opacity_effect') and self.opacity_effect is not None:
                try:
                    # 尝试访问opacity_effect来验证其有效性
                    _ = self.opacity_effect.opacity()
                    opacity_effect_valid = True
                except RuntimeError:
                    # opacity_effect已被删除
                    self.opacity_effect = None
                    logging.debug("透明度效果已被删除，需要重新创建")
            
            if not opacity_effect_valid:
                try:
                    self.opacity_effect = QGraphicsOpacityEffect(self)
                    self.opacity_effect.setParent(self)
                    self.setGraphicsEffect(self.opacity_effect)
                    logging.debug("隐藏动画透明度效果创建成功")
                except Exception as e:
                    logging.warning(f"创建隐藏动画透明度效果失败: {e}")
                    self._fallback_hide()
                    return
            
            # 安全创建隐藏动画组合
            try:
                self._hide_animation_group = QParallelAnimationGroup(self)
                
                # 透明度渐出动画
                fade_out_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
                fade_out_animation.setParent(self._hide_animation_group)
                fade_out_animation.setDuration(300)
                fade_out_animation.setEasingCurve(QEasingCurve.Type.InCubic)
                fade_out_animation.setStartValue(1.0)
                fade_out_animation.setEndValue(0.0)
                
                # 缩放隐藏动画
                current_rect = self.geometry()
                scale_factor = 0.8
                target_width = int(current_rect.width() * scale_factor)
                target_height = int(current_rect.height() * scale_factor)
                target_x = current_rect.x() + (current_rect.width() - target_width) // 2
                target_y = current_rect.y() + (current_rect.height() - target_height) // 2
                target_rect = QRect(target_x, target_y, target_width, target_height)
                
                scale_hide_animation = QPropertyAnimation(self, b"geometry")
                scale_hide_animation.setParent(self._hide_animation_group)
                scale_hide_animation.setDuration(300)
                scale_hide_animation.setEasingCurve(QEasingCurve.Type.InBack)
                scale_hide_animation.setStartValue(current_rect)
                scale_hide_animation.setEndValue(target_rect)
                
                # 使用安全的隐藏动画组操作
                def setup_hide_animation():
                    self._hide_animation_group.addAnimation(fade_out_animation)
                    self._hide_animation_group.addAnimation(scale_hide_animation)
                    self._hide_animation_group.finished.connect(self.hide_completely)
                    self._hide_animation_group.start()
                    return True
                
                if self._safe_animation_group_operation(setup_hide_animation):
                    pass
                else:
                    logging.error("隐藏动画启动失败，使用后备隐藏")
                    self._fallback_hide()
                
            except RuntimeError as e:
                logging.error(f"隐藏动画创建失败: {e}")
                self._fallback_hide()
                
        except Exception as e:
            logging.error(f"smooth_hide 执行出错: {e}")
            self._fallback_hide()

    def _fallback_hide(self):
        """后备隐藏方式"""
        try:
            self.hide()
        except Exception as fallback_error:
            logging.error(f"后备隐藏也失败: {fallback_error}")

    def hide_completely(self):
        """完全隐藏灵动岛窗口"""
        self.hide()

    def set_independent_mode(self, independent: bool):
        """设置独立模式
        
        Args:
            independent: True表示独立模式（不受主窗口影响），False表示正常模式
        """
        self._independent_mode = independent
        
        if independent:
            # 独立模式：设置为工具窗口，始终在顶层
            self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | 
                              Qt.WindowType.WindowStaysOnTopHint)
            # 确保在独立模式下可见，使用smooth_show确保正确显示
            self.smooth_show()
            self.position_on_screen()  # 重新定位
            self.activateWindow()  # 激活窗口
            self.raise_()  # 提升到最前
            logging.info("灵动岛切换到独立模式，强制显示")
        else:
            # 正常模式：恢复原有的窗口标志
            self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | 
                              Qt.WindowType.WindowStaysOnTopHint)
            # 重新显示窗口以应用新的窗口标志
            self.show()
            logging.info("灵动岛恢复正常模式")
    
    def is_independent_mode(self) -> bool:
        """检查是否处于独立模式"""
        return getattr(self, '_independent_mode', False)
    
    # 多功能显示模式
    def init_display_modes(self):
        """初始化显示模式"""
        self.display_modes = [
            "status",      # 监控状态模式
            "performance", # 性能监控模式
            "api",         # API状态模式
            "statistics"   # 统计信息模式
        ]
        self.current_mode_index = 0
        self.mode_cycle_timer = QTimer()
        self.mode_cycle_timer.timeout.connect(self.cycle_display_mode)
        
        # 数据更新定时器
        self.data_update_timer = QTimer()
        self.data_update_timer.timeout.connect(self.update_display_data)
        self.data_update_timer.start(2000)  # 每2秒更新一次数据
        
        # 初始化数据存储
        self.display_data = {
            "monitoring_status": False,
            "keyword_count": 0,
            "total_recognitions": 0,
            "keyword_hits": 0,
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "network_status": "检测中",
            "api_status": "检测中",
            "last_recognition_time": "N/A"
        }
    
    def cycle_display_mode(self):
        """循环切换显示模式"""
        self.current_mode_index = (self.current_mode_index + 1) % len(self.display_modes)
        self.update_display_for_current_mode()
    
    def update_display_for_current_mode(self):
        """根据当前模式更新显示"""
        current_mode = self.display_modes[self.current_mode_index]
        
        if current_mode == "status":
            self.show_status_mode()
        elif current_mode == "performance":
            self.show_performance_mode()
        elif current_mode == "api":
            self.show_api_mode()
        elif current_mode == "statistics":
            self.show_statistics_mode()
    
    def show_status_mode(self):
        """显示监控状态模式"""
        status_text = "运行中" if self.display_data["monitoring_status"] else "已停止"
        status_icon = "🟢" if self.display_data["monitoring_status"] else "🔴"
        
        title = f"{status_icon} 监控状态"
        subtitle = f"{status_text} | 关键词: {self.display_data['keyword_count']}"
        
        self.set_state("status", title, subtitle)
    
    def show_performance_mode(self):
        """显示性能监控模式"""
        cpu = self.display_data["cpu_usage"]
        memory = self.display_data["memory_usage"]
        
        title = "📊 系统性能"
        subtitle = f"CPU: {cpu:.1f}% | 内存: {memory:.1f}%"
        
        self.set_state("performance", title, subtitle)
    
    def show_api_mode(self):
        """显示API状态模式"""
        network = self.display_data["network_status"]
        api = self.display_data["api_status"]
        
        title = "🌐 连接状态"
        subtitle = f"网络: {network} | API: {api}"
        
        self.set_state("api", title, subtitle)
    
    def show_statistics_mode(self):
        """显示统计信息模式"""
        total = self.display_data.get("total_recognitions", 0)
        hits = self.display_data.get("keyword_hits", 0)
        last_time = self.display_data.get("last_recognition_time", "N/A")
        
        title = "📈 识别统计"
        
        # 如果有识别数据，显示详细信息
        if total > 0 or hits > 0:
            if isinstance(last_time, str) and last_time != "N/A":
                subtitle = f"识别: {total} | 命中: {hits} | 最后: {last_time}"
            else:
                subtitle = f"识别: {total} | 命中: {hits}"
        else:
            # 如果没有识别数据，显示当前状态
            monitoring = self.display_data.get("monitoring_status", False)
            keyword_count = self.display_data.get("keyword_count", 0)
            if monitoring:
                subtitle = f"监控中 | 关键词: {keyword_count} | 等待识别..."
            else:
                subtitle = f"未启动 | 关键词: {keyword_count} | 点击开始"
        
        self.set_state("statistics", title, subtitle)
    
    def update_display_data(self):
        """更新显示数据"""
        try:
            # 设置默认数据
            default_data = {
                "monitoring_status": False,
                "keyword_count": 0,
                "network_status": "检测中",
                "api_status": "检测中",
                "total_recognitions": 0,
                "keyword_hits": 0,
                "last_recognition_time": "未知",
                "cpu_usage": 0,
                "memory_usage": 0
            }
            
            # 更新默认数据
            for key, value in default_data.items():
                if key not in self.display_data:
                    self.display_data[key] = value
            
            # 从主窗口获取状态面板数据
            if hasattr(self, 'parent_window') and self.parent_window:
                main_window = self.parent_window
                
                # 获取监控状态
                if hasattr(main_window, 'ocr_worker') and main_window.ocr_worker:
                    # 检查OCR工作器是否正在运行
                    if hasattr(main_window.ocr_worker, 'isRunning') and main_window.ocr_worker.isRunning():
                        self.display_data["monitoring_status"] = True
                    elif hasattr(main_window.ocr_worker, 'running') and main_window.ocr_worker.running:
                        self.display_data["monitoring_status"] = True
                    else:
                        self.display_data["monitoring_status"] = False
                else:
                    self.display_data["monitoring_status"] = False
                
                # 获取关键词数量
                if hasattr(main_window, 'keyword_panel'):
                    keywords = main_window.keyword_panel.get_keywords()
                    self.display_data["keyword_count"] = len(keywords) if keywords else 0
                
                # 获取网络状态
                if hasattr(main_window, 'status_panel') and main_window.status_panel:
                    network_status = main_window.status_panel.get_network_status()
                    self.display_data["network_status"] = network_status if network_status else "检测中"
                
                # 获取API状态
                if hasattr(main_window, 'status_panel') and main_window.status_panel:
                    api_status = main_window.status_panel.get_api_status()
                    self.display_data["api_status"] = api_status if api_status else "检测中"
                
                # 获取统计数据
                if hasattr(main_window, 'log_panel') and main_window.log_panel:
                    stats = main_window.log_panel.get_statistics()
                    if stats:
                        self.display_data["total_recognitions"] = stats.get("total_recognitions", 0)
                        self.display_data["keyword_hits"] = stats.get("keyword_hits", 0)
                        
                        # 获取最后识别时间
                        last_time = stats.get("last_recognition_time")
                        if last_time:
                            self.display_data["last_recognition_time"] = last_time.strftime("%H:%M:%S") if hasattr(last_time, 'strftime') else str(last_time)
            
            # 获取性能数据
            try:
                import psutil
                self.display_data["cpu_usage"] = psutil.cpu_percent(interval=None)
                self.display_data["memory_usage"] = psutil.virtual_memory().percent
            except:
                pass
            
            # 更新当前显示
            self.update_display_for_current_mode()
            
        except Exception as e:
            logging.debug(f"更新显示数据失败: {e}")
            # 即使出错也要更新显示
            self.update_display_for_current_mode()
    
    def update_monitoring_data(self, **kwargs):
        """更新监控数据"""
        for key, value in kwargs.items():
            if key in self.display_data:
                self.display_data[key] = value
        
        # 立即更新显示
        self.update_display_for_current_mode()
    
    def start_auto_cycle(self, interval=5000):
        """开始自动循环显示模式"""
        self.mode_cycle_timer.start(interval)
    
    def stop_auto_cycle(self):
        """停止自动循环显示模式"""
        self.mode_cycle_timer.stop()
    
    def manual_cycle_mode(self):
        """手动切换显示模式"""
        self.cycle_display_mode()


class DynamicIslandManager:
    """灵动岛管理器"""
    
    def __init__(self):
        self.islands = []
        self.current_island = None
    
    def create_island(self, parent=None) -> ModernDynamicIsland:
        """创建新的灵动岛实例"""
        island = ModernDynamicIsland(parent)
        self.islands.append(island)
        return island
    
    def show_notification(self, title: str, subtitle: str = "", 
                         icon: QIcon = None, status_color: QColor = None):
        """显示通知"""
        if self.current_island:
            self.current_island.show_notification(title, subtitle, icon, status_color)
    
    def show_status(self, status: str, color: QColor = None):
        """显示状态"""
        if self.current_island:
            self.current_island.show_status(status, color)
    
    def update_monitoring_data(self, **kwargs):
        """更新监控数据"""
        if self.current_island:
            self.current_island.update_monitoring_data(**kwargs)
    
    def set_current_island(self, island: ModernDynamicIsland):
        """设置当前活动的灵动岛"""
        self.current_island = island
    
    def hide_all(self):
        """隐藏所有灵动岛"""
        for island in self.islands:
            island.hide_notification()


# 全局管理器实例
dynamic_island_manager = DynamicIslandManager()


def get_dynamic_island_manager() -> DynamicIslandManager:
    """获取全局灵动岛管理器"""
    return dynamic_island_manager


# 兼容性别名
DynamicIsland = ModernDynamicIsland