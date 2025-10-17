# core/hotkey_manager.py
"""
全局快捷键管理模块

提供全局快捷键的注册、监听和管理功能。支持多种快捷键组合，
包括Ctrl、Shift、Alt、Win键与字母、数字、功能键的组合。

Dependencies:
    - PyQt6: 用于信号槽机制和线程管理
    - pynput: 用于全局快捷键监听（可选）

Author: XuanWu Team
Version: 2.1.7
"""
import logging
import re
from typing import Optional, Callable, Dict, List
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# 使用专用logger，日志将记录到xuanwu_log.html
logger = logging.getLogger('hotkey_manager')

try:
    import pynput
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    logger.warning("pynput库未安装，全局快捷键功能不可用")

class HotkeyListener(QThread):
    """
    全局快捷键监听线程
    
    在后台线程中监听全局快捷键事件，支持多种快捷键组合的注册和触发。
    使用pynput库实现跨平台的全局快捷键监听功能。
    
    Signals:
        hotkey_triggered (str): 快捷键触发信号，参数为快捷键字符串
        
    Attributes:
        listener: pynput键盘监听器
        hotkeys (Dict[str, Callable]): 已注册的快捷键字典
        running (bool): 监听器运行状态
        
    Example:
        >>> listener = HotkeyListener()
        >>> listener.register_hotkey("Ctrl+Shift+S", save_callback)
        >>> listener.start()
        >>> listener.hotkey_triggered.connect(handle_hotkey)
    """
    hotkey_triggered = pyqtSignal(str)
    
    def __init__(self):
        """
        初始化快捷键监听器
        
        创建监听器实例，初始化快捷键字典和运行状态。
        """
        super().__init__()
        self.listener = None
        self.hotkeys: Dict[str, Callable] = {}
        self.running = False
        
    def register_hotkey(self, hotkey_str: str, callback: Callable):
        """
        注册快捷键
        
        将快捷键字符串与回调函数关联，当快捷键被触发时执行回调。
        
        Args:
            hotkey_str (str): 快捷键字符串，如 'Ctrl+Shift+S'
            callback (Callable): 快捷键触发时的回调函数
            
        Returns:
            bool: 注册成功返回True，失败返回False
            
        Example:
            >>> def save_action():
            ...     print("保存操作")
            >>> listener.register_hotkey("Ctrl+S", save_action)
        """
        if not PYNPUT_AVAILABLE:
            logger.error("pynput库未安装，无法注册快捷键")
            return False
            
        try:
            # 解析快捷键字符串
            parsed_hotkey = self._parse_hotkey(hotkey_str)
            if parsed_hotkey:
                self.hotkeys[hotkey_str] = callback
                logger.info(f"快捷键已注册: {hotkey_str}")
                return True
        except Exception as e:
            logger.error(f"注册快捷键失败: {e}")
        return False
    
    def unregister_hotkey(self, hotkey_str: str):
        """
        取消注册快捷键
        
        从已注册的快捷键字典中移除指定的快捷键。
        
        Args:
            hotkey_str (str): 要取消注册的快捷键字符串
            
        Example:
            >>> listener.unregister_hotkey("Ctrl+S")
        """
        if hotkey_str in self.hotkeys:
            del self.hotkeys[hotkey_str]
            logger.info(f"快捷键已取消注册: {hotkey_str}")
    
    def _parse_hotkey(self, hotkey_str: str) -> Optional[List]:
        """
        解析快捷键字符串
        
        将快捷键字符串解析为pynput可识别的按键列表。
        支持Ctrl、Shift、Alt、Win键与字母、数字、功能键的组合。
        
        Args:
            hotkey_str (str): 快捷键字符串，如 'Ctrl+Shift+S'
            
        Returns:
            Optional[List]: 解析后的按键列表，解析失败返回None
            
        Example:
            >>> keys = listener._parse_hotkey("Ctrl+Shift+S")
            >>> # 返回 [Key.ctrl, Key.shift, 's']
        """
        if not hotkey_str:
            return None
            
        # 标准化快捷键字符串
        hotkey_str = hotkey_str.strip().replace(' ', '')
        parts = hotkey_str.split('+')
        
        if len(parts) < 2:
            return None
            
        keys = []
        for part in parts:
            part = part.lower()
            if part in ['ctrl', 'control']:
                keys.append(keyboard.Key.ctrl)
            elif part in ['shift']:
                keys.append(keyboard.Key.shift)
            elif part in ['alt']:
                keys.append(keyboard.Key.alt)
            elif part in ['cmd', 'win', 'windows']:
                keys.append(keyboard.Key.cmd)
            elif len(part) == 1 and part.isalpha():
                keys.append(part)
            elif len(part) == 1 and part.isdigit():
                # 数字键 0-9
                keys.append(part)
            elif part in ['comma', ',']:
                # 逗号键，兼容 "Ctrl+Comma"/"Ctrl+," 格式
                keys.append(',')
            elif part in ['space']:
                keys.append(keyboard.Key.space)
            elif part in ['enter', 'return']:
                keys.append(keyboard.Key.enter)
            elif part in ['tab']:
                keys.append(keyboard.Key.tab)
            elif part in ['esc', 'escape']:
                keys.append(keyboard.Key.esc)
            elif part.startswith('f') and part[1:].isdigit():
                # 功能键 F1-F12
                try:
                    f_num = int(part[1:])
                    if 1 <= f_num <= 12:
                        keys.append(getattr(keyboard.Key, f'f{f_num}'))
                except:
                    continue
            else:
                logger.warning(f"未识别的按键: {part}")
                continue
                
        return keys if len(keys) >= 2 else None
    
    def run(self):
        """运行快捷键监听"""
        if not PYNPUT_AVAILABLE:
            return
            
        self.running = True
        
        # 创建快捷键组合字典
        hotkey_combinations = {}
        for hotkey_str, callback in self.hotkeys.items():
            parsed = self._parse_hotkey(hotkey_str)
            if parsed:
                try:
                    # 构建pynput格式的快捷键字符串
                    pynput_hotkey = self._build_pynput_hotkey(parsed)
                    if pynput_hotkey:
                        def make_callback(cb, hs):
                            def wrapper():
                                try:
                                    cb()
                                    self.hotkey_triggered.emit(hs)
                                except Exception as e:
                                    logger.error(f"快捷键回调执行失败: {e}")
                            return wrapper
                        
                        hotkey_combinations[pynput_hotkey] = make_callback(callback, hotkey_str)
                except Exception as e:
                    logger.error(f"创建快捷键组合失败: {e}")
        
        if hotkey_combinations:
            try:
                # 创建全局热键监听器
                self.listener = keyboard.GlobalHotKeys(hotkey_combinations)
                self.listener.start()
                
                while self.running:
                    self.msleep(100)
                    
            except Exception as e:
                logger.error(f"全局快捷键监听失败: {e}")
    
    def _build_pynput_hotkey(self, parsed_keys) -> Optional[str]:
        """构建pynput格式的快捷键字符串
        
        Args:
            parsed_keys: 解析后的按键列表
            
        Returns:
            pynput格式的快捷键字符串
        """
        try:
            key_parts = []
            for key in parsed_keys:
                if isinstance(key, str):
                    # 普通字符键
                    key_parts.append(key)
                else:
                    # 特殊键
                    if key == keyboard.Key.ctrl:
                        key_parts.append('<ctrl>')
                    elif key == keyboard.Key.shift:
                        key_parts.append('<shift>')
                    elif key == keyboard.Key.alt:
                        key_parts.append('<alt>')
                    elif key == keyboard.Key.cmd:
                        key_parts.append('<cmd>')
                    elif key == keyboard.Key.space:
                        key_parts.append('<space>')
                    elif key == keyboard.Key.enter:
                        key_parts.append('<enter>')
                    elif key == keyboard.Key.tab:
                        key_parts.append('<tab>')
                    elif key == keyboard.Key.esc:
                        key_parts.append('<esc>')
                    elif hasattr(key, 'name') and key.name.startswith('f'):
                        key_parts.append(f'<{key.name}>')
                    else:
                        key_parts.append(str(key))
            
            return '+'.join(key_parts) if key_parts else None
            
        except Exception as e:
            logger.error(f"构建pynput快捷键字符串失败: {e}")
            return None
    
    def stop(self):
        """停止监听"""
        self.running = False
        if self.listener:
            try:
                self.listener.stop()
            except:
                pass
        self.quit()
        self.wait()

class HotkeyManager(QObject):
    """快捷键管理器"""
    hotkey_triggered = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.listener_thread = None
        self.current_hotkey = None
        self.current_hotkeys: Dict[str, Callable] = {}
        
    def is_available(self) -> bool:
        """检查快捷键功能是否可用"""
        return PYNPUT_AVAILABLE
    
    def validate_hotkey(self, hotkey_str: str) -> tuple[bool, str]:
        """验证快捷键格式
        
        Args:
            hotkey_str: 快捷键字符串
            
        Returns:
            (是否有效, 错误信息)
        """
        if not hotkey_str or not hotkey_str.strip():
            return False, "快捷键不能为空"
        
        # 基本格式检查
        hotkey_str = hotkey_str.strip().replace(' ', '')
        if '+' not in hotkey_str:
            return False, "快捷键必须包含组合键，如 Ctrl+S"
        
        parts = hotkey_str.split('+')
        if len(parts) < 2:
            return False, "快捷键至少需要两个按键组合"
        
        # 检查修饰键
        modifiers = ['ctrl', 'control', 'shift', 'alt', 'cmd', 'win', 'windows']
        has_modifier = False
        
        valid_keys = modifiers + ['space', 'enter', 'return', 'tab', 'esc', 'escape', 'comma', ',']
        valid_keys.extend([chr(i) for i in range(ord('a'), ord('z') + 1)])
        valid_keys.extend([str(i) for i in range(0, 10)])
        valid_keys.extend([f'f{i}' for i in range(1, 13)])
        
        for part in parts:
            part_lower = part.lower()
            if part_lower in modifiers:
                has_modifier = True
            elif part_lower not in valid_keys:
                return False, f"无效的按键: {part}"
        
        if not has_modifier:
            return False, "快捷键必须包含至少一个修饰键 (Ctrl, Shift, Alt, Win)"
        
        # 检查是否有重复的修饰键
        modifier_count = {}
        for part in parts:
            part_lower = part.lower()
            if part_lower in ['ctrl', 'control']:
                modifier_count['ctrl'] = modifier_count.get('ctrl', 0) + 1
            elif part_lower == 'shift':
                modifier_count['shift'] = modifier_count.get('shift', 0) + 1
            elif part_lower == 'alt':
                modifier_count['alt'] = modifier_count.get('alt', 0) + 1
            elif part_lower in ['cmd', 'win', 'windows']:
                modifier_count['win'] = modifier_count.get('win', 0) + 1
        
        for modifier, count in modifier_count.items():
            if count > 1:
                return False, f"修饰键 {modifier} 重复"
        
        # 检查常见系统快捷键冲突
        conflict_result = self._check_system_conflicts(hotkey_str)
        if not conflict_result[0]:
            return conflict_result
        
        return True, ""
    
    def register_hotkey(self, hotkey_str: str, callback: Callable) -> tuple[bool, str]:
        """注册快捷键
        
        Args:
            hotkey_str: 快捷键字符串，如 "Ctrl+Shift+S"
            callback: 回调函数
            
        Returns:
            (是否成功, 错误信息)
        """
        if not self.is_available():
            error_msg = "快捷键功能不可用，请安装 pynput 库"
            logger.error(error_msg)
            return False, error_msg
        
        # 验证快捷键格式
        is_valid, error_msg = self.validate_hotkey(hotkey_str)
        if not is_valid:
            logger.error(f"快捷键格式无效: {error_msg}")
            return False, error_msg
        
        # 停止现有监听
        self.unregister_current_hotkey()
        
        try:
            # 创建新的监听线程
            self.listener_thread = HotkeyListener()
            self.listener_thread.hotkey_triggered.connect(self.hotkey_triggered.emit)
            
            # 注册快捷键
            if self.listener_thread.register_hotkey(hotkey_str, callback):
                self.current_hotkey = hotkey_str
                self.listener_thread.start()
                
                # 等待一小段时间确保线程启动
                import time
                time.sleep(0.1)
                
                # 检查线程是否正常运行
                if not self.listener_thread.isRunning():
                    return False, "快捷键监听线程启动失败"
                
                logger.info(f"全局快捷键已注册: {hotkey_str}")
                return True, "快捷键注册成功"
            else:
                return False, "快捷键注册失败"
                
        except Exception as e:
            error_msg = f"注册快捷键失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def unregister_current_hotkey(self):
        """取消注册当前快捷键"""
        if self.listener_thread:
            self.listener_thread.stop()
            self.listener_thread = None
            self.current_hotkey = None
            self.current_hotkeys = {}
            logger.info("快捷键已取消注册")
    
    def get_current_hotkey(self) -> Optional[str]:
        """获取当前注册的快捷键"""
        return self.current_hotkey

    def get_current_hotkeys(self) -> Dict[str, Callable]:
        """获取当前已注册的多个快捷键映射"""
        return dict(self.current_hotkeys)
    
    def get_suggested_hotkeys(self) -> List[str]:
        """获取建议的快捷键组合"""
        return [
            "Ctrl+Shift+S",  # 默认推荐
            "Ctrl+Alt+S", 
            "Ctrl+Shift+C",  # 截图相关
            "Ctrl+Alt+C",
            "Ctrl+Shift+X",  # 执行相关
            "Alt+Shift+S",
            "Win+Shift+S",   # Windows风格
            "Ctrl+F1",       # 功能键组合
            "Ctrl+F2",
            "Alt+F1",
            "Ctrl+Shift+O",  # OCR相关
            "Alt+Shift+O",
            "Ctrl+F12",      # 更多功能键
            "Alt+F12"
        ]

    def register_hotkeys(self, hotkey_map: Dict[str, Callable]) -> tuple[bool, str]:
        """批量注册多个快捷键
        
        Args:
            hotkey_map: { hotkey_str: callback } 字典
        
        Returns:
            (是否成功, 错误信息)
        """
        if not self.is_available():
            error_msg = "快捷键功能不可用，请安装 pynput 库"
            logger.error(error_msg)
            return False, error_msg

        if not isinstance(hotkey_map, dict) or not hotkey_map:
            return False, "快捷键映射不能为空"

        # 验证所有快捷键
        valid_items = []
        for hk, cb in hotkey_map.items():
            is_valid, err = self.validate_hotkey(hk)
            if is_valid:
                valid_items.append((hk, cb))
            else:
                logger.warning(f"跳过无效快捷键: {hk} - {err}")

        if not valid_items:
            return False, "没有可注册的有效快捷键"

        # 停止现有监听
        self.unregister_current_hotkey()

        try:
            # 创建新的监听线程
            self.listener_thread = HotkeyListener()
            self.listener_thread.hotkey_triggered.connect(self.hotkey_triggered.emit)

            # 注册所有快捷键
            register_failures = []
            for hk, cb in valid_items:
                ok = self.listener_thread.register_hotkey(hk, cb)
                if not ok:
                    register_failures.append(hk)

            if register_failures and len(register_failures) == len(valid_items):
                return False, "全部快捷键注册失败"

            # 保存当前已注册快捷键
            self.current_hotkey = None  # 单快捷键模式不再使用
            self.current_hotkeys = {hk: cb for hk, cb in valid_items if hk not in register_failures}

            # 启动监听线程
            self.listener_thread.start()

            # 等待一小段时间确保线程启动
            import time
            time.sleep(0.1)

            if not self.listener_thread.isRunning():
                return False, "快捷键监听线程启动失败"

            if register_failures:
                logger.warning(f"部分快捷键注册失败: {', '.join(register_failures)}")
            logger.info(f"已注册{len(self.current_hotkeys)}个全局快捷键")
            return True, "快捷键批量注册成功"

        except Exception as e:
            error_msg = f"批量注册快捷键失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def _check_system_conflicts(self, hotkey_str: str) -> tuple[bool, str]:
        """检查与系统快捷键的冲突
        
        Args:
            hotkey_str: 快捷键字符串
            
        Returns:
            (是否无冲突, 警告信息)
        """
        hotkey_lower = hotkey_str.lower().replace(' ', '')
        
        # 常见系统快捷键列表
        system_hotkeys = {
            'ctrl+c': '复制',
            'ctrl+v': '粘贴',
            'ctrl+x': '剪切',
            'ctrl+z': '撤销',
            'ctrl+y': '重做',
            'ctrl+a': '全选',
            'ctrl+s': '保存',
            'ctrl+o': '打开',
            'ctrl+n': '新建',
            'ctrl+p': '打印',
            'ctrl+f': '查找',
            'ctrl+h': '替换',
            'alt+f4': '关闭窗口',
            'alt+tab': '切换窗口',
            'win+l': '锁定屏幕',
            'win+d': '显示桌面',
            'win+r': '运行对话框',
            'ctrl+alt+del': '任务管理器',
            'ctrl+shift+esc': '任务管理器'
        }
        
        if hotkey_lower in system_hotkeys:
            return False, f"与系统快捷键冲突: {system_hotkeys[hotkey_lower]} ({hotkey_str})"
        
        # 检查常见应用程序快捷键
        common_app_hotkeys = {
            'ctrl+shift+i': '开发者工具',
            'ctrl+shift+j': '控制台',
            'ctrl+shift+c': '检查元素',
            'f12': '开发者工具',
            'f5': '刷新',
            'ctrl+f5': '强制刷新',
            'ctrl+r': '刷新'
        }
        
        if hotkey_lower in common_app_hotkeys:
            return True, f"可能与应用程序快捷键冲突: {common_app_hotkeys[hotkey_lower]} ({hotkey_str})，建议选择其他组合"
        
        return True, ""

# 全局快捷键管理器实例
_hotkey_manager = None

def get_hotkey_manager() -> HotkeyManager:
    """获取全局快捷键管理器实例"""
    global _hotkey_manager
    if _hotkey_manager is None:
        _hotkey_manager = HotkeyManager()
    return _hotkey_manager