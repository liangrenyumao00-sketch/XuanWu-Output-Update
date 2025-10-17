# widgets/chart_widget.py
"""
图表组件模块

该模块提供了一系列简单易用的图表组件，用于数据可视化展示。
包含柱状图、饼图、折线图等常用图表类型。

主要功能：
- 柱状图：用于显示分类数据的比较
- 饼图：用于显示数据的比例关系
- 折线图：用于显示数据的趋势变化
- 自定义样式：支持颜色、字体等样式定制
- 响应式设计：自适应容器大小

依赖：
- PyQt6：GUI框架和绘图功能

作者：XuanWu OCR Team
版本：2.1.7
"""
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics

class SimpleBarChart(QWidget):
    """
    简单的柱状图组件
    
    用于显示分类数据的柱状图表，支持数据标签、标题显示等功能。
    适用于比较不同类别的数值大小。
    
    Attributes:
        data (list): 图表数据列表
        labels (list): 数据标签列表
        title (str): 图表标题
        max_value (float): 数据最大值，用于计算比例
    
    Example:
        >>> chart = SimpleBarChart()
        >>> chart.set_data([10, 20, 15], ["A", "B", "C"], "销售数据")
        >>> chart.show()
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = []
        self.labels = []
        self.title = ""
        self.max_value = 0
        self.setMinimumSize(300, 200)
        
    def set_data(self, data, labels, title=""):
        """设置图表数据"""
        self.data = data[:]
        self.labels = labels[:]
        self.title = title
        self.max_value = max(data) if data else 0
        self.update()
        
    def paintEvent(self, event):
        """绘制图表"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 设置背景
        painter.fillRect(self.rect(), QColor(255, 255, 255))
        
        if not self.data:
            painter.setPen(QPen(QColor(128, 128, 128)))
            painter.setFont(QFont("Arial", 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            return
            
        # 计算绘图区域
        margin = 40
        title_height = 30 if self.title else 0
        chart_rect = self.rect().adjusted(margin, margin + title_height, -margin, -margin)
        
        # 绘制标题
        if self.title:
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            title_rect = self.rect().adjusted(0, 0, 0, -(self.height() - title_height))
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self.title)
        
        # 计算柱状图参数
        bar_count = len(self.data)
        if bar_count == 0:
            return
            
        bar_width = chart_rect.width() // bar_count * 0.8
        bar_spacing = chart_rect.width() // bar_count * 0.2
        
        # 绘制柱状图
        for i, (value, label) in enumerate(zip(self.data, self.labels)):
            # 计算柱子位置和高度
            x = chart_rect.left() + i * (bar_width + bar_spacing) + bar_spacing / 2
            bar_height = (value / self.max_value * chart_rect.height()) if self.max_value > 0 else 0
            y = chart_rect.bottom() - bar_height
            
            # 绘制柱子
            color = QColor(33, 150, 243)  # 蓝色
            painter.fillRect(int(x), int(y), int(bar_width), int(bar_height), QBrush(color))
            
            # 绘制数值标签
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.setFont(QFont("Arial", 9))
            value_rect = self.rect().adjusted(int(x), int(y - 20), int(x + bar_width), int(y))
            painter.drawText(value_rect, Qt.AlignmentFlag.AlignCenter, str(int(value)))
            
            # 绘制X轴标签
            label_rect = self.rect().adjusted(int(x), chart_rect.bottom(), int(x + bar_width), self.height())
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label[:8])  # 限制标签长度
        
        # 绘制坐标轴
        painter.setPen(QPen(QColor(128, 128, 128), 1))
        # X轴
        painter.drawLine(chart_rect.bottomLeft(), chart_rect.bottomRight())
        # Y轴
        painter.drawLine(chart_rect.bottomLeft(), chart_rect.topLeft())

class SimplePieChart(QWidget):
    """
    简单的饼图组件
    
    用于显示数据比例关系的饼图表，支持多种颜色、数据标签、标题显示等功能。
    适用于展示各部分占整体的比例。
    
    Attributes:
        data (list): 图表数据列表
        labels (list): 数据标签列表
        colors (list): 预定义的颜色列表，用于扇形着色
        title (str): 图表标题
    
    Example:
        >>> chart = SimplePieChart()
        >>> chart.set_data([30, 20, 50], ["产品A", "产品B", "产品C"], "市场份额")
        >>> chart.show()
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = []
        self.labels = []
        self.colors = [
            QColor(33, 150, 243),   # 蓝色
            QColor(76, 175, 80),    # 绿色
            QColor(255, 152, 0),    # 橙色
            QColor(244, 67, 54),    # 红色
            QColor(156, 39, 176),   # 紫色
            QColor(96, 125, 139),   # 蓝灰色
            QColor(255, 193, 7),    # 黄色
            QColor(121, 85, 72),    # 棕色
        ]
        self.title = ""
        self.setMinimumSize(300, 200)
        
    def set_data(self, data, labels, title=""):
        """设置图表数据"""
        self.data = data[:]
        self.labels = labels[:]
        self.title = title
        self.update()
        
    def paintEvent(self, event):
        """绘制图表"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 设置背景
        painter.fillRect(self.rect(), QColor(255, 255, 255))
        
        if not self.data or sum(self.data) == 0:
            painter.setPen(QPen(QColor(128, 128, 128)))
            painter.setFont(QFont("Arial", 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            return
            
        # 计算绘图区域
        margin = 40
        title_height = 30 if self.title else 0
        chart_size = min(self.width() - 2 * margin, self.height() - 2 * margin - title_height)
        chart_rect = self.rect().adjusted(
            (self.width() - chart_size) // 2,
            margin + title_height,
            -(self.width() - chart_size) // 2,
            -(self.height() - chart_size - margin - title_height)
        )
        
        # 绘制标题
        if self.title:
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            title_rect = self.rect().adjusted(0, 0, 0, -(self.height() - title_height))
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self.title)
        
        # 计算角度
        total = sum(self.data)
        start_angle = 0
        
        # 绘制饼图扇形
        for i, (value, label) in enumerate(zip(self.data, self.labels)):
            if value <= 0:
                continue
                
            span_angle = int(value / total * 360 * 16)  # Qt使用1/16度为单位
            
            # 选择颜色
            color = self.colors[i % len(self.colors)]
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            
            # 绘制扇形
            painter.drawPie(chart_rect, start_angle, span_angle)
            
            # 绘制标签
            mid_angle = (start_angle + span_angle / 2) / 16 * math.pi / 180
            label_radius = chart_size / 2 * 0.7
            label_x = chart_rect.center().x() + label_radius * math.cos(mid_angle)
            label_y = chart_rect.center().y() + label_radius * math.sin(mid_angle)
            
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.setFont(QFont("Arial", 9))
            
            # 计算百分比
            percentage = value / total * 100
            text = f"{label}\n{percentage:.1f}%"
            
            # 绘制文本
            fm = QFontMetrics(painter.font())
            text_rect = fm.boundingRect(text)
            text_rect.moveCenter(self.rect().center())
            text_rect.moveCenter(self.rect().center())
            text_rect.translate(int(label_x - chart_rect.center().x()), 
                              int(label_y - chart_rect.center().y()))
            
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
            
            start_angle += span_angle

class SimpleLineChart(QWidget):
    """
    简单的折线图组件
    
    用于显示数据趋势变化的折线图表，支持数据点标记、网格线、标题显示等功能。
    适用于展示时间序列数据或连续数据的变化趋势。
    
    Attributes:
        data (list): 图表数据列表
        labels (list): 数据标签列表（通常为时间或序号）
        title (str): 图表标题
    
    Example:
        >>> chart = SimpleLineChart()
        >>> chart.set_data([10, 15, 12, 18, 20], ["1月", "2月", "3月", "4月", "5月"], "销售趋势")
        >>> chart.show()
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = []
        self.labels = []
        self.title = ""
        self.setMinimumSize(300, 200)
        
    def set_data(self, data, labels, title=""):
        """设置图表数据"""
        self.data = data[:]
        self.labels = labels[:]
        self.title = title
        self.update()
        
    def paintEvent(self, event):
        """绘制图表"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 设置背景
        painter.fillRect(self.rect(), QColor(255, 255, 255))
        
        if not self.data:
            painter.setPen(QPen(QColor(128, 128, 128)))
            painter.setFont(QFont("Arial", 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            return
            
        # 计算绘图区域
        margin = 40
        title_height = 30 if self.title else 0
        chart_rect = self.rect().adjusted(margin, margin + title_height, -margin, -margin)
        
        # 绘制标题
        if self.title:
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            title_rect = self.rect().adjusted(0, 0, 0, -(self.height() - title_height))
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self.title)
        
        # 计算数据点位置
        if len(self.data) < 2:
            return
            
        max_value = max(self.data) if self.data else 0
        min_value = min(self.data) if self.data else 0
        value_range = max_value - min_value if max_value != min_value else 1
        
        points = []
        for i, value in enumerate(self.data):
            x = chart_rect.left() + (i / (len(self.data) - 1)) * chart_rect.width()
            y = chart_rect.bottom() - ((value - min_value) / value_range) * chart_rect.height()
            points.append((int(x), int(y)))
        
        # 绘制网格线
        painter.setPen(QPen(QColor(230, 230, 230), 1))
        for i in range(5):
            y = chart_rect.top() + (i / 4) * chart_rect.height()
            painter.drawLine(chart_rect.left(), int(y), chart_rect.right(), int(y))
        
        # 绘制折线
        painter.setPen(QPen(QColor(33, 150, 243), 2))
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])
        
        # 绘制数据点
        painter.setBrush(QBrush(QColor(33, 150, 243)))
        for x, y in points:
            painter.drawEllipse(x - 3, y - 3, 6, 6)
        
        # 绘制坐标轴
        painter.setPen(QPen(QColor(128, 128, 128), 1))
        # X轴
        painter.drawLine(chart_rect.bottomLeft(), chart_rect.bottomRight())
        # Y轴
        painter.drawLine(chart_rect.bottomLeft(), chart_rect.topLeft())
        
        # 绘制X轴标签
        painter.setPen(QPen(QColor(0, 0, 0)))
        painter.setFont(QFont("Arial", 9))
        for i, (label, (x, y)) in enumerate(zip(self.labels, points)):
            if i % max(1, len(self.labels) // 5) == 0:  # 只显示部分标签避免重叠
                label_rect = self.rect().adjusted(x - 30, chart_rect.bottom(), x + 30, self.height())
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label[:8])