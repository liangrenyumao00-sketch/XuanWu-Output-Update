# widgets/virtual_list_widget.py
from PyQt6.QtWidgets import (
    QAbstractItemView, QWidget, QVBoxLayout, QScrollArea, QLabel,
    QFrame, QHBoxLayout, QPushButton, QProgressBar
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QRect, QSize, QAbstractListModel,
    QModelIndex, QVariant
)
from PyQt6.QtGui import QPainter, QFontMetrics, QPalette
from typing import List, Dict, Any, Optional, Callable
import threading
import time


class LazyLoadWorker(QThread):
    """懒加载工作线程"""
    data_loaded = pyqtSignal(int, int, list)  # start_index, end_index, data
    loading_finished = pyqtSignal()
    
    def __init__(self, data_loader: Callable, start_index: int, count: int):
        super().__init__()
        self.data_loader = data_loader
        self.start_index = start_index
        self.count = count
        self._stop_requested = False
    
    def run(self):
        """执行懒加载"""
        try:
            if self._stop_requested:
                return
            
            # 模拟加载延迟，避免频繁请求
            time.sleep(0.1)
            
            if self._stop_requested:
                return
            
            # 加载数据
            data = self.data_loader(self.start_index, self.count)
            
            if not self._stop_requested:
                self.data_loaded.emit(self.start_index, self.start_index + len(data), data)
        
        except Exception as e:
            print(f"懒加载失败: {e}")
        finally:
            self.loading_finished.emit()
    
    def stop(self):
        """停止加载"""
        self._stop_requested = True


class VirtualListModel(QAbstractListModel):
    """虚拟列表数据模型"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[Dict[str, Any]] = []
        self._total_count = 0
        self._item_height = 50
        self._loaded_ranges: List[tuple] = []  # (start, end) 已加载的范围
    
    def rowCount(self, parent=QModelIndex()) -> int:
        return self._total_count
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> QVariant:
        if not index.isValid() or index.row() >= len(self._data):
            return QVariant()
        
        item = self._data[index.row()]
        
        # 检查数据是否已加载（空字典表示未加载）
        if not item or not item.get('text'):
            return QVariant()
        
        if role == Qt.ItemDataRole.DisplayRole:
            return QVariant(item.get('text', ''))
        elif role == Qt.ItemDataRole.UserRole:
            return QVariant(item)
        
        return QVariant()
    
    def set_total_count(self, count: int):
        """设置总数据量"""
        self.beginResetModel()
        self._total_count = count
        self._data = [{}] * count  # 预分配空间
        self._loaded_ranges.clear()
        self.endResetModel()
    
    def update_data(self, start_index: int, end_index: int, data: List[Dict[str, Any]]):
        """更新指定范围的数据"""
        if start_index < 0 or end_index > self._total_count:
            return
        
        # 更新数据
        for i, item in enumerate(data):
            if start_index + i < len(self._data):
                self._data[start_index + i] = item
        
        # 更新已加载范围
        self._loaded_ranges.append((start_index, end_index))
        self._loaded_ranges.sort()
        
        # 合并重叠的范围
        merged_ranges = []
        for start, end in self._loaded_ranges:
            if merged_ranges and start <= merged_ranges[-1][1]:
                merged_ranges[-1] = (merged_ranges[-1][0], max(merged_ranges[-1][1], end))
            else:
                merged_ranges.append((start, end))
        self._loaded_ranges = merged_ranges
        
        # 通知视图更新
        top_left = self.index(start_index, 0)
        bottom_right = self.index(min(end_index - 1, self._total_count - 1), 0)
        self.dataChanged.emit(top_left, bottom_right)
    
    def is_range_loaded(self, start_index: int, end_index: int) -> bool:
        """检查指定范围是否已加载"""
        for range_start, range_end in self._loaded_ranges:
            if range_start <= start_index and end_index <= range_end:
                return True
        return False
    
    def get_item_height(self) -> int:
        return self._item_height
    
    def set_item_height(self, height: int):
        self._item_height = height


class VirtualListItemWidget(QFrame):
    """虚拟列表项组件"""
    
    # 信号
    clicked = pyqtSignal(dict)
    double_clicked = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(1)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        
        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        layout.addWidget(self.text_label)
        
        self.setMinimumHeight(50)
        self.setMaximumHeight(50)
        
        # 存储数据
        self.item_data = {}
    
    def set_data(self, data: Dict[str, Any]):
        """设置数据"""
        self.item_data = data
        text = data.get('text', '')
        self.text_label.setText(text)
        
        # 设置工具提示
        if len(text) > 50:
            self.setToolTip(text)
        else:
            self.setToolTip('')
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item_data)
        super().mousePressEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.item_data)
        super().mouseDoubleClickEvent(event)


class VirtualListWidget(QWidget):
    """虚拟化列表组件"""
    
    # 信号
    item_clicked = pyqtSignal(dict)  # 项目被点击
    item_double_clicked = pyqtSignal(dict)  # 项目被双击
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 配置参数
        self.ITEM_HEIGHT = 50
        self.BUFFER_SIZE = 10  # 缓冲区大小
        self.LOAD_BATCH_SIZE = 50  # 每次加载的数据量
        
        # 数据相关
        self.data_loader: Optional[Callable] = None
        self.total_count = 0
        self.visible_start = 0
        self.visible_end = 0
        
        # 懒加载相关
        self.load_worker: Optional[LazyLoadWorker] = None
        self.loading_timer = QTimer()
        self.loading_timer.setSingleShot(True)
        self.loading_timer.timeout.connect(self._trigger_load)
        
        # 初始化UI
        self._init_ui()
        
        # 数据模型
        self.model = VirtualListModel(self)
        self.model.set_item_height(self.ITEM_HEIGHT)
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 加载指示器
        self.loading_widget = QWidget()
        loading_layout = QHBoxLayout(self.loading_widget)
        loading_layout.setContentsMargins(10, 5, 10, 5)
        
        self.loading_label = QLabel("正在加载...")
        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, 0)  # 无限进度条
        
        loading_layout.addWidget(self.loading_label)
        loading_layout.addWidget(self.loading_progress)
        
        self.loading_widget.hide()
        
        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 内容容器
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(1)
        
        self.scroll_area.setWidget(self.content_widget)
        
        # 滚动事件连接
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll)
        
        layout.addWidget(self.loading_widget)
        layout.addWidget(self.scroll_area)
        
        # 项目组件池
        self.item_widgets: List[VirtualListItemWidget] = []
        self.visible_items: List[VirtualListItemWidget] = []
    
    def set_data_loader(self, loader: Callable[[int, int], List[Dict[str, Any]]]):
        """设置数据加载器
        
        Args:
            loader: 数据加载函数，接受(start_index, count)参数，返回数据列表
        """
        self.data_loader = loader
    
    def set_total_count(self, count: int):
        """设置总数据量"""
        self.total_count = count
        self.model.set_total_count(count)
        
        # 设置内容高度
        total_height = count * self.ITEM_HEIGHT
        self.content_widget.setMinimumHeight(total_height)
        
        # 触发初始加载
        self._update_visible_range()
        # 立即触发数据加载
        if count > 0:
            self._trigger_load()
    
    def _on_scroll(self, value):
        """滚动事件处理"""
        self._update_visible_range()
        
        # 延迟触发加载，避免频繁请求
        self.loading_timer.stop()
        self.loading_timer.start(200)
    
    def _update_visible_range(self):
        """更新可见范围"""
        if self.total_count == 0:
            return
        
        # 计算可见范围
        scroll_value = self.scroll_area.verticalScrollBar().value()
        viewport_height = self.scroll_area.viewport().height()
        
        start_index = max(0, (scroll_value // self.ITEM_HEIGHT) - self.BUFFER_SIZE)
        end_index = min(self.total_count, 
                       ((scroll_value + viewport_height) // self.ITEM_HEIGHT) + self.BUFFER_SIZE + 1)
        
        self.visible_start = start_index
        self.visible_end = end_index
        
        # 更新可见项目
        self._update_visible_items()
    
    def _update_visible_items(self):
        """更新可见的项目组件"""
        # 隐藏所有项目
        for widget in self.visible_items:
            widget.hide()
        
        self.visible_items.clear()
        
        # 显示可见范围内的项目
        for i in range(self.visible_start, self.visible_end):
            if i >= self.total_count:
                break
            
            # 获取或创建项目组件
            widget = self._get_item_widget()
            
            # 设置位置
            y_pos = i * self.ITEM_HEIGHT
            widget.setGeometry(0, y_pos, self.content_widget.width(), self.ITEM_HEIGHT)
            
            # 设置数据
            data = self.model.data(self.model.index(i, 0), Qt.ItemDataRole.UserRole)
            # 修复：正确处理QVariant数据
            if data and not data.isNull():
                data_dict = data.value() if hasattr(data, 'value') else data
                if isinstance(data_dict, dict) and data_dict.get('text'):
                    widget.set_data(data_dict)
                    widget.show()
                    self.visible_items.append(widget)
                else:
                    # 数据未加载时隐藏项目
                    widget.hide()
            else:
                # 数据未加载时隐藏项目
                widget.hide()
    
    def _get_item_widget(self) -> VirtualListItemWidget:
        """获取可用的项目组件"""
        # 从池中获取隐藏的组件
        for widget in self.item_widgets:
            if widget.isHidden():
                return widget
        
        # 创建新组件
        widget = VirtualListItemWidget(self.content_widget)
        # 连接信号
        widget.clicked.connect(self.item_clicked.emit)
        widget.double_clicked.connect(self.item_double_clicked.emit)
        self.item_widgets.append(widget)
        return widget
    
    def _trigger_load(self):
        """触发数据加载"""
        if not self.data_loader:
            return
        
        # 检查是否需要加载
        load_start = max(0, self.visible_start - self.BUFFER_SIZE)
        load_end = min(self.total_count, self.visible_end + self.BUFFER_SIZE)
        
        if self.model.is_range_loaded(load_start, load_end):
            return
        
        # 停止之前的加载
        if self.load_worker and self.load_worker.isRunning():
            self.load_worker.stop()
            self.load_worker.wait(1000)
        
        # 开始新的加载
        self.loading_widget.show()
        self.load_worker = LazyLoadWorker(self.data_loader, load_start, load_end - load_start)
        self.load_worker.data_loaded.connect(self._on_data_loaded)
        self.load_worker.loading_finished.connect(self._on_loading_finished)
        self.load_worker.start()
    
    def _on_data_loaded(self, start_index: int, end_index: int, data: List[Dict[str, Any]]):
        """数据加载完成"""
        self.model.update_data(start_index, end_index, data)
        self._update_visible_items()
    
    def _on_loading_finished(self):
        """加载完成"""
        self.loading_widget.hide()
    
    def refresh(self):
        """刷新列表"""
        # 清除已加载的数据
        self.model.set_total_count(self.total_count)
        
        # 重新计算可见范围
        self._update_visible_range()
    
    def scroll_to_top(self):
        """滚动到顶部"""
        self.scroll_area.verticalScrollBar().setValue(0)
    
    def scroll_to_bottom(self):
        """滚动到底部"""
        max_value = self.scroll_area.verticalScrollBar().maximum()
        self.scroll_area.verticalScrollBar().setValue(max_value)
    
    def get_visible_range(self) -> tuple:
        """获取当前可见范围"""
        return (self.visible_start, self.visible_end)
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        
        # 更新项目宽度
        content_width = self.content_widget.width()
        for widget in self.visible_items:
            widget.setFixedWidth(content_width)
        
        # 重新计算可见范围
        self._update_visible_range()