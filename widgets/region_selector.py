# widgets/region_selector.py
from PyQt6.QtWidgets import QWidget, QApplication, QMessageBox
from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen

MIN_SELECTION_SIZE = 10  # 最小选择区域大小

class RegionSelector(QWidget):
    # 定义信号，选择区域和取消选择
    region_selected = pyqtSignal(tuple)
    selection_canceled = pyqtSignal()

    def __init__(self):
        super().__init__()

        # 获取所有屏幕并计算覆盖矩形
        screens = QApplication.screens()
        total_rect = screens[0].geometry()
        for screen in screens[1:]:
            total_rect = total_rect.united(screen.geometry())
        self.setGeometry(total_rect)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # 初始化状态
        self.start = None
        self.end = None
        self.selection_in_progress = False

        self.show()
        self.activateWindow()
        self.raise_()

    def paintEvent(self, event):
        p = QPainter(self)
        # 绘制半透明背景
        p.fillRect(self.rect(), QColor(0, 0, 0, 100))

        # 绘制屏幕边界（可选）
        pen_screen = QPen(QColor(255, 0, 0))
        pen_screen.setWidth(1)
        p.setPen(pen_screen)
        for screen in QApplication.screens():
            p.drawRect(screen.geometry())

        # 绘制选择矩形
        if self.selection_in_progress and self.start and self.end:
            self.draw_selection_rectangle(p)

    def draw_selection_rectangle(self, p):
        r = QRect(self.start, self.end).normalized()
        pen = QPen(QColor(0, 255, 0))
        pen.setWidth(2)
        p.setPen(pen)
        p.setBrush(QBrush(QColor(0, 0, 0, 0)))  # 透明填充
        p.drawRect(r)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            pos = e.globalPosition().toPoint()  # 使用全局坐标
            self.start = self.end = pos
            self.selection_in_progress = True
            self.update()

    def mouseMoveEvent(self, e):
        if self.selection_in_progress:
            new_end = e.globalPosition().toPoint()  # 使用全局坐标
            if new_end != self.end:
                self.end = new_end
                self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.selection_in_progress:
            self.end = e.globalPosition().toPoint()  # 使用全局坐标
            self.selection_in_progress = False
            r = QRect(self.start, self.end).normalized()

            if r.width() >= MIN_SELECTION_SIZE and r.height() >= MIN_SELECTION_SIZE:
                # 发射选择区域信号
                self.region_selected.emit((r.x(), r.y(), r.width(), r.height()))
            else:
                QMessageBox.warning(self, "选择区域太小", "选择的区域太小，请重新选择")

            self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.selection_canceled.emit()
            self.close()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    selector = RegionSelector()
    def on_selected(region):
        print("选中区域:", region)

    def on_canceled():
        print("取消选择")

    selector.region_selected.connect(on_selected)
    selector.selection_canceled.connect(on_canceled)

    sys.exit(app.exec())
