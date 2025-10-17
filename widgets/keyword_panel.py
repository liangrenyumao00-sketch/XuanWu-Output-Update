# widgets/keyword_panel.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QLineEdit, QPushButton, QMessageBox
import os
from core.match import match_text
from core.settings import load_settings
from core.keyword_manager import KeywordManager


class KeywordPanel(QWidget):
    KEYWORDS_FILE = "target_keywords.txt"

    def __init__(self):
        super().__init__()

        # 创建控件
        self.list = QListWidget()
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入关键词")
        self.btn_add = QPushButton("添加")
        self.btn_del = QPushButton("删除选中")

        # 布局
        layout = QVBoxLayout(self)
        layout.setSpacing(3)  # 减小间距
        layout.setContentsMargins(5, 5, 5, 5)  # 设置边距
        layout.addWidget(self.list)
        layout.addWidget(self.input)
        layout.addWidget(self.btn_add)
        layout.addWidget(self.btn_del)

        # 绑定信号
        self.btn_add.clicked.connect(self.add_kw)
        self.btn_del.clicked.connect(self.del_kw)
        self.input.returnPressed.connect(self.add_kw)  # 回车添加关键词

        # 加载已有关键词
        self.load_keywords()

        # 加载设置
        self.settings = load_settings()

    def load_keywords(self):
        """从文件加载关键词，避免重复添加"""
        if os.path.exists(self.KEYWORDS_FILE):
            existing = set()
            with open(self.KEYWORDS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    kw = line.strip()
                    if kw and kw not in existing:
                        self.list.addItem(kw)
                        existing.add(kw)

    def add_kw(self):
        """添加关键词，避免重复"""
        kw = self.input.text().strip()
        if not kw:
            QMessageBox.warning(self, "提示", "请输入关键词")
            return

        existing = set(self.get_keywords())
        if kw in existing:
            QMessageBox.information(self, "提示", "关键词已存在")
            return

        self.list.addItem(kw)
        self.input.clear()
        self.input.setFocus()
        self.save_keywords()

    def del_kw(self):
        """删除选中的关键词"""
        selected_items = self.list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请选择要删除的关键词")
            return
        for item in selected_items:
            self.list.takeItem(self.list.row(item))
        self.save_keywords()

    def save_keywords(self):
        """保存关键词到文件，增加异常处理"""
        try:
            with open(self.KEYWORDS_FILE, "w", encoding="utf-8") as f:
                for i in range(self.list.count()):
                    f.write(self.list.item(i).text() + "\n")
            # 同步更新 JSON 存储，保证导出功能获取到最新数据
            try:
                manager = KeywordManager()
                manager.save_keywords(self.get_keywords())
            except Exception as e:
                # 不影响主流程，仅记录日志
                import logging
                logging.error(f"同步保存到 keywords.json 失败: {e}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存关键词失败: {e}")

    def get_keywords(self):
        """获取所有关键词列表"""
        return [self.list.item(i).text() for i in range(self.list.count())]

    def match_keywords(self, text):
        """
        根据当前匹配模式匹配关键词，返回匹配上的关键词列表
        支持精确、模糊、正则匹配
        """
        mode = self.settings.get("match_mode", "exact")
        fuzzy_threshold = self.settings.get("fuzzy_threshold", 0.85)

        matched_keywords = []
        for keyword in self.get_keywords():
            if not keyword.strip():
                continue
            if match_text(text, keyword, mode, fuzzy_threshold):
                matched_keywords.append(keyword)
        return matched_keywords
    
    def refresh_ui_text(self):
        """刷新UI文本的国际化显示"""
        try:
            from core.i18n import t
            
            # 刷新输入框占位符文本
            self.input.setPlaceholderText(t('keyword_input_placeholder'))
            
            # 刷新按钮文本
            self.btn_add.setText(t('keyword_add'))
            self.btn_del.setText(t('keyword_delete_selected'))
            
        except Exception as e:
            import logging
            logging.error(f"刷新KeywordPanel UI文本时出错: {e}")

    def reload_keywords(self):
        """重新加载关键词（清空列表后从文件读取）"""
        try:
            self.list.clear()
            self.load_keywords()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"重新加载关键词失败: {e}")
