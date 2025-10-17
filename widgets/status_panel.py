# widgets/status_panel.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import requests
from core.i18n import t

class NetworkCheckThread(QThread):
    network_status_signal = pyqtSignal(str)

    def run(self):
        """进行网络检测"""
        try:
            # 通过访问百度来检测网络连接
            requests.get("https://www.baidu.com", timeout=3)
            self.network_status_signal.emit(f"🟢 {t('normal')}")  # 网络正常
        except requests.exceptions.RequestException:
            self.network_status_signal.emit(f"🔴 {t('unavailable')}")  # 网络不可用

class StatusPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(200)  # 恢复默认高度
        layout = QVBoxLayout(self)
        layout.setSpacing(2)  # 减小间距
        layout.setContentsMargins(5, 5, 5, 5)  # 设置边距

        self.font = QFont("Consolas", 9)  # 减小字体

        # 创建所有需要显示的标签
        self.labels = {
            'status': QLabel(f"{t('running_status')}：⛔ {t('stopped')}"),
            'keywords': QLabel(f"{t('current_keywords_count')}：0"),
            'region': QLabel(f"{t('recognition_region')}：{t('not_set')}"),
            'interval': QLabel(f"{t('recognition_interval')}：0.0 {t('seconds')}"),
            'total_hits': QLabel(f"{t('total_recognitions')}：0"),
            'keyword_hits': QLabel(f"{t('keyword_hits_count')}：0"),
            'last_time': QLabel(f"{t('last_recognition_time')}：N/A"),
            'net': QLabel(f"{t('network_status')}：{t('detecting')}..."),
            'api': QLabel(f"{t('api_status')}：{t('detecting')}..."),
        }

        self._set_font()  # 设置字体
        self._add_widgets_to_layout(layout)  # 布局标签

        # 定时器，每5秒检测一次网络
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.start_network_check)
        self.timer.start(5000)

        # 启动首次检测
        self.start_network_check()

    def _set_font(self):
        """为所有标签设置相同的字体"""
        for label in self.labels.values():
            label.setFont(self.font)

    def _add_widgets_to_layout(self, layout):
        """将标签加入布局中"""
        layout.addWidget(self.labels['status'])
        layout.addWidget(self.labels['keywords'])
        layout.addWidget(self.labels['region'])
        layout.addWidget(self.labels['interval'])
        layout.addWidget(self.labels['total_hits'])
        layout.addWidget(self.labels['keyword_hits'])
        layout.addWidget(self.labels['last_time'])

        # 添加分隔符
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        separator.setStyleSheet("")
        layout.addWidget(separator)

        layout.addWidget(self.labels['net'])
        layout.addWidget(self.labels['api'])
    


    def start_network_check(self):
        """启动网络检测线程"""
        self.network_check_thread = NetworkCheckThread()
        self.network_check_thread.network_status_signal.connect(self.update_network_status)
        self.network_check_thread.start()

    def update_network_status(self, status):
        """更新网络状态"""
        self.labels['net'].setText(f"{t('network_status')}：{status}")

    def update_status(self, **kwargs):
        """更新各种状态信息"""
        if 'running' in kwargs:
            if kwargs['running']:
                self.labels['status'].setText(f"✅ {t('running')}")
                self.labels['status'].setStyleSheet("color: green; font-weight: bold;")
            else:
                self.labels['status'].setText(f"⛔ {t('stopped')}")
                self.labels['status'].setStyleSheet("color: red; font-weight: bold;")

        if 'keywords_count' in kwargs:
            self.labels['keywords'].setText(f"{t('current_keywords_count')}：{kwargs['keywords_count']}")

        if 'region' in kwargs:
            region = kwargs['region']
            region_text = f"{t('recognition_region')}：{','.join(map(str, region))}" if region else f"{t('recognition_region')}：{t('not_set')}"
            self.labels['region'].setText(region_text)

        if 'interval' in kwargs:
            self.labels['interval'].setText(f"{t('recognition_interval')}：{kwargs['interval']:.1f} {t('seconds')}")

        if 'total_hits' in kwargs:
            self.labels['total_hits'].setText(f"{t('total_recognitions')}：{kwargs['total_hits']}")

        if 'hits_per_keyword' in kwargs:
            # 统计关键词命中次数
            total = sum(kwargs['hits_per_keyword'].values())
            self.labels['keyword_hits'].setText(f"{t('keyword_hits_count')}：{total}")

        if 'last_time' in kwargs:
            self.labels['last_time'].setText(f"{t('last_recognition_time')}：{kwargs['last_time']}")

    def update_worker_status(self, info: str, data: dict):
        """根据工作线程的状态更新面板"""
        if info == "status" and "api_ok" in data:
            api_status = f"🟢 {t('normal')}" if data["api_ok"] else f"🔴 {t('abnormal')}"
            self.labels['api'].setText(f"{t('api_status')}：{api_status}")

        if info == "trend" and "total_hits" in data:
            # 更新识别统计
            self.update_status(
                total_hits=data["total_hits"],
                hits_per_keyword=data.get("hits_per_keyword"),
                last_time=data.get("last_time")
            )
    
    def refresh_ui_text(self):
        """刷新UI文本的国际化显示"""
        try:
            from core.i18n import t
            
            # 刷新状态标签
            if hasattr(self, 'labels'):
                for key, label in self.labels.items():
                    current_text = label.text()
                    if key == 'api' and 'API 状态' in current_text:
                        status_part = current_text.split('：', 1)[1] if '：' in current_text else ''
                        label.setText(f"{t('api_status')}：{status_part}")
                    elif key == 'total' and '总识别次数' in current_text:
                        count_part = current_text.split('：', 1)[1] if '：' in current_text else ''
                        label.setText(f"{t('total_recognitions')}：{count_part}")
                    elif key == 'last' and '最后识别' in current_text:
                        time_part = current_text.split('：', 1)[1] if '：' in current_text else ''
                        label.setText(f"{t('last_recognition')}：{time_part}")
                        
        except Exception as e:
            import logging
            logging.error(f"刷新StatusPanel UI文本时出错: {e}")
    
    def get_network_status(self):
        """获取当前网络状态"""
        try:
            if hasattr(self, 'labels') and 'net' in self.labels:
                # 从标签文本中提取状态部分
                text = self.labels['net'].text()
                if '：' in text:
                    status_part = text.split('：', 1)[1]
                    return status_part
            return "检测中..."
        except Exception as e:
            import logging
            logging.error(f"获取网络状态时出错: {e}")
            return "未知"
    
    def get_api_status(self):
        """获取当前API状态"""
        try:
            if hasattr(self, 'labels') and 'api' in self.labels:
                # 从标签文本中提取状态部分
                text = self.labels['api'].text()
                if '：' in text:
                    status_part = text.split('：', 1)[1]
                    return status_part
            return "检测中..."
        except Exception as e:
            import logging
            logging.error(f"获取API状态时出错: {e}")
            return "未知"
