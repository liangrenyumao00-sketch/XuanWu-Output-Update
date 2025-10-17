# widgets/control_panel.py
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QSlider, QHBoxLayout, QDoubleSpinBox, QComboBox, QGroupBox, QGraphicsOpacityEffect
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QColor, QBrush
from core.settings import load_settings, save_settings, decrypt_api_data

class ControlPanel(QWidget):
    select_region = pyqtSignal()
    start_capture = pyqtSignal()
    stop_capture = pyqtSignal()
    refresh_index = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.settings = load_settings() or {}
        self._version_enabled_map = {}

        # 保存配置防抖定时器，避免频繁写文件
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_settings_to_file)

        # =====================================
        # 接口版本选择（扩展）
        # =====================================
        self.api_label = QLabel("OCR接口版本：")
        self.api_box = QComboBox()
        self.api_box.addItems([
            "标准版 general_basic", 
            "高精度版 accurate_basic",
            "标准版含位置 general_enhanced",
            "高精度版含位置 accurate_enhanced",
            "网络图片识别 webimage",
            "手写文字识别 handwriting"
        ])

        # OCR版本与下拉框索引映射
        self.version_map = {
            "general": 0,
            "accurate": 1,
            "general_enhanced": 2,
            "accurate_enhanced": 3,
            "webimage": 4,
            "handwriting": 5
        }
        
        # 反向映射，从索引到版本
        self.index_to_version = {
            0: "general",
            1: "accurate",
            2: "general_enhanced",
            3: "accurate_enhanced",
            4: "webimage",
            5: "handwriting"
        }

        # 默认选中
        version = self.settings.get("ocr_version", "general")
        idx = self.version_map.get(version, 0)  # 默认使用标准版
        self.api_box.blockSignals(True)
        self.api_box.setCurrentIndex(idx)
        self.api_box.blockSignals(False)
        self.api_box.currentIndexChanged.connect(self.change_api_version)

        # 记录高精度版是否禁用状态，默认不禁用
        self._accurate_option_disabled = False

        # 匹配方式
        self.mode_label = QLabel("关键词匹配模式：")
        self.mode_box = QComboBox()
        self.mode_box.addItems(["精确匹配 (exact)", "模糊匹配 (fuzzy)", "正则匹配 (regex)"])

        match_mode = self.settings.get("match_mode", "exact")
        text_map = {
            "exact": "精确匹配 (exact)",
            "fuzzy": "模糊匹配 (fuzzy)",
            "regex": "正则匹配 (regex)"
        }
        self.mode_box.blockSignals(True)
        self.mode_box.setCurrentText(text_map.get(match_mode, "精确匹配 (exact)"))
        self.mode_box.blockSignals(False)
        self.mode_box.currentTextChanged.connect(self.update_match_mode)

        self.fuzzy_threshold_label = QLabel("模糊匹配阈值：")
        self.fuzzy_slider = QSlider(Qt.Orientation.Horizontal)
        self.fuzzy_slider.setRange(0, 100)

        fuzzy_val = self.settings.get("fuzzy_threshold", 0.85)
        self.fuzzy_slider.blockSignals(True)
        self.fuzzy_slider.setValue(int(fuzzy_val * 100))
        self.fuzzy_slider.blockSignals(False)
        self.fuzzy_slider.valueChanged.connect(self.on_fuzzy_slider_changed)

        self.fuzzy_spinbox = QDoubleSpinBox()
        self.fuzzy_spinbox.setDecimals(2)
        self.fuzzy_spinbox.setRange(0.0, 1.0)
        self.fuzzy_spinbox.setSingleStep(0.01)
        self.fuzzy_spinbox.blockSignals(True)
        self.fuzzy_spinbox.setValue(fuzzy_val)
        self.fuzzy_spinbox.blockSignals(False)
        self.fuzzy_spinbox.valueChanged.connect(self.on_fuzzy_spinbox_changed)

        self.update_fuzzy_enabled(match_mode == "fuzzy")

        # 识别间隔，统一单位秒
        self.interval_label = QLabel("识别间隔 (秒)：")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(2, 50)  # 对应 0.2s ~ 5.0s
        interval_val = self.settings.get("interval", 0.6)
        slider_val = int(interval_val * 10)
        self.slider.blockSignals(True)
        self.slider.setValue(slider_val)
        self.slider.blockSignals(False)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.spinbox = QDoubleSpinBox()
        self.spinbox.setDecimals(1)
        self.spinbox.setRange(0.2, 5.0)
        self.spinbox.setSingleStep(0.1)
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(interval_val)
        self.spinbox.blockSignals(False)
        self.spinbox.valueChanged.connect(self._on_spinbox_changed)

        self.select_btn = QPushButton("选择截图区域")
        self.start_btn = QPushButton("开始捕获")
        self.stop_btn = QPushButton("停止捕获")
        self.index_btn = QPushButton("刷新索引")
        self.stop_btn.setEnabled(False)
        # 初始禁用态仅应用视觉弱化（不自定义颜色/样式）
        self._set_disabled_visual(self.stop_btn, True)
        self.stop_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self.stop_btn.setToolTip("未开始捕获，无法停止")
        
        # 设置按钮样式
        for btn in [self.select_btn, self.start_btn, self.stop_btn, self.index_btn]:
            btn.setMinimumHeight(24)  # 减小按钮高度，更紧凑
            btn.setCursor(Qt.CursorShape.PointingHandCursor)  # 鼠标悬停时显示手型光标

        self.select_btn.clicked.connect(self.select_region.emit)
        self.start_btn.clicked.connect(self.start_capture.emit)
        self.stop_btn.clicked.connect(self.stop_capture.emit)
        self.index_btn.clicked.connect(self.refresh_index.emit)

        self.status_label = QLabel("状态：未开始")

        # 导入分组框组件
        from PyQt6.QtWidgets import QGroupBox
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)  # 减小间距，更紧凑
        layout.setContentsMargins(5, 5, 5, 5)  # 设置边距
        
        # OCR设置分组
        ocr_group = QGroupBox("OCR设置")
        ocr_layout = QVBoxLayout()
        ocr_layout.setSpacing(3)  # 减小组内间距
        
        # 接口版本选择
        api_layout = QHBoxLayout()
        api_layout.addWidget(self.api_label)
        api_layout.addWidget(self.api_box)
        ocr_layout.addLayout(api_layout)
        
        # 识别间隔
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(self.interval_label)
        interval_layout.addWidget(self.slider)
        interval_layout.addWidget(self.spinbox)
        ocr_layout.addLayout(interval_layout)
        
        ocr_group.setLayout(ocr_layout)
        layout.addWidget(ocr_group)
        
        # 匹配设置分组
        match_group = QGroupBox("匹配设置")
        match_layout = QVBoxLayout()
        match_layout.setSpacing(3)  # 减小组内间距
        
        # 匹配模式
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.mode_label)
        mode_layout.addWidget(self.mode_box)
        match_layout.addLayout(mode_layout)
        
        # 模糊匹配阈值
        fuzzy_layout = QHBoxLayout()
        fuzzy_layout.addWidget(self.fuzzy_threshold_label)
        fuzzy_layout.addWidget(self.fuzzy_slider)
        fuzzy_layout.addWidget(self.fuzzy_spinbox)
        match_layout.addLayout(fuzzy_layout)
        
        match_group.setLayout(match_layout)
        layout.addWidget(match_group)
        
        # 操作按钮分组
        action_group = QGroupBox("操作")
        action_layout = QVBoxLayout()
        action_layout.setSpacing(3)  # 减小组内间距
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.select_btn)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.index_btn)
        action_layout.addLayout(btn_layout)
        action_layout.addWidget(self.status_label)
        
        action_group.setLayout(action_layout)
        layout.addWidget(action_group)

        # 根据已配置的API密钥，禁用不可用的接口选项
        try:
            self.apply_version_availability()
        except Exception as e:
            logging.warning(f"应用接口可用性时发生异常: {e}")

    # ---------- 新增私有保存方法，防抖写文件 ----------
    def _save_settings_to_file(self):
        save_settings(self.settings)

    def _schedule_save_settings(self, delay=300):
        # 300ms后保存，若期间重复调用，重置计时器
        self._save_timer.start(delay)

    # ---------- 统一滑块和数字框联动 ----------

    def _on_slider_changed(self, value):
        val = value / 10.0
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(val)
        self.spinbox.blockSignals(False)

        self.settings["interval"] = val
        self._schedule_save_settings()

    def _on_spinbox_changed(self, value):
        val = round(value, 1)
        slider_val = int(val * 10)
        self.slider.blockSignals(True)
        self.slider.setValue(slider_val)
        self.slider.blockSignals(False)

        self.settings["interval"] = val
        self._schedule_save_settings()

    # ---------- API版本切换 ----------

    def change_api_version(self, idx):
        # 使用映射获取版本名称
        version = self.index_to_version.get(idx, "general")
        self.settings["ocr_version"] = version
        self._schedule_save_settings()
        logging.info(f"OCR接口版本已切换为: {version}")

    # ---------- 匹配模式更新 ----------

    def update_match_mode(self, text):
        mode_map = {
            "精确匹配 (exact)": "exact",
            "模糊匹配 (fuzzy)": "fuzzy",
            "正则匹配 (regex)": "regex"
        }
        selected = mode_map.get(text, "exact")
        self.settings["match_mode"] = selected
        self._schedule_save_settings()
        self.update_fuzzy_enabled(selected == "fuzzy")

    def update_fuzzy_enabled(self, en: bool):
        # 功能可用性
        self.fuzzy_slider.setEnabled(en)
        self.fuzzy_spinbox.setEnabled(en)

        # 视觉禁用效果（灰显/降低不透明度）
        try:
            self.fuzzy_threshold_label.setStyleSheet("color: {}".format("black" if en else "gray"))
        except Exception:
            pass
        self._set_disabled_visual(self.fuzzy_threshold_label, not en)
        self._set_disabled_visual(self.fuzzy_slider, not en)
        self._set_disabled_visual(self.fuzzy_spinbox, not en)

        # 提示信息
        tip = "" if en else "当前为非模糊匹配模式，阈值不可用"
        try:
            self.fuzzy_threshold_label.setToolTip(tip)
            self.fuzzy_slider.setToolTip(tip)
            self.fuzzy_spinbox.setToolTip(tip)
        except Exception:
            pass

    def on_fuzzy_slider_changed(self, value: int):
        val = value / 100.0
        self.fuzzy_spinbox.blockSignals(True)
        self.fuzzy_spinbox.setValue(val)
        self.fuzzy_spinbox.blockSignals(False)
        self.settings["fuzzy_threshold"] = val
        self._schedule_save_settings()

    def on_fuzzy_spinbox_changed(self, value: float):
        val = max(0.0, min(1.0, value))
        self.fuzzy_slider.blockSignals(True)
        self.fuzzy_slider.setValue(int(val * 100))
        self.fuzzy_slider.blockSignals(False)
        self.settings["fuzzy_threshold"] = val
        self._schedule_save_settings()

    # ---------- 启用/禁用高精度选项，并灰化显示 ----------

    def disable_accurate_option(self, disable: bool):
        self._accurate_option_disabled = disable
        idx = self.api_box.findText("高精度版 accurate_basic")
        if idx != -1:
            # 使用模型项的 flags 正确禁用并灰显
            model = self.api_box.model()
            item = model.item(idx)
            if item is not None:
                item.setEnabled(not disable)
                try:
                    flags = item.flags()
                    if disable:
                        item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)
                    else:
                        item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
                except Exception:
                    pass
                item.setForeground(QBrush(QColor("gray" if disable else "black")))
                item.setToolTip("" if not disable else "未配置密钥，请在设置中输入")

            # 如果禁用且当前选中高精度，切换成标准版
            if disable and self.api_box.currentIndex() == idx:
                self.api_box.setCurrentIndex(0)

    def is_accurate_option_disabled(self) -> bool:
        return self._accurate_option_disabled

    # ---------- 辅助方法 ----------

    def get_interval(self):
        return self.spinbox.value()

    def set_interval(self, sec):
        self.spinbox.setValue(sec)

    def _set_disabled_visual(self, btn, disabled: bool):
        """仅在禁用时降低不透明度，启用时恢复，保持默认样式。"""
        try:
            if disabled:
                eff = btn.graphicsEffect()
                if not isinstance(eff, QGraphicsOpacityEffect):
                    eff = QGraphicsOpacityEffect(btn)
                    btn.setGraphicsEffect(eff)
                eff.setOpacity(0.55)
            else:
                if isinstance(btn.graphicsEffect(), QGraphicsOpacityEffect):
                    btn.setGraphicsEffect(None)
        except Exception:
            pass

    def enable_buttons(self, start, stop):
        self.start_btn.setEnabled(start)
        self.stop_btn.setEnabled(stop)
        # 仅在不可点击时显示视觉弱化
        self._set_disabled_visual(self.start_btn, not start)
        self._set_disabled_visual(self.stop_btn, not stop)
        # 鼠标指针与提示信息同步
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor if start else Qt.CursorShape.ArrowCursor)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor if stop else Qt.CursorShape.ArrowCursor)
        self.start_btn.setToolTip("" if start else "捕获进行中，无法开始")
        self.stop_btn.setToolTip("" if stop else "未开始捕获，无法停止")
        self.start_btn.setToolTip("" if start else "捕获进行中，无法开始")
        self.stop_btn.setToolTip("" if stop else "未开始捕获，无法停止")

    def set_status(self, text, color="black"):
        self.status_label.setText(f"状态：{text}")
        self.status_label.setStyleSheet(f"color: {color}")
    
    def refresh_ui_text(self):
        """刷新UI文本的国际化显示"""
        try:
            from core.i18n import t
            
            # 刷新标签文本
            self.api_label.setText(t('控制面板'))
            self.mode_label.setText(t('control_match_mode'))
            self.fuzzy_threshold_label.setText(t('control_fuzzy_threshold'))
            self.interval_label.setText(t('control_interval'))
            
            # 刷新按钮文本
            self.select_btn.setText(t('control_select_region'))
            self.start_btn.setText(t('control_start_capture'))
            self.stop_btn.setText(t('control_stop_capture'))
            self.index_btn.setText(t('control_refresh_index'))
            
            # 刷新下拉框选项
            current_api_index = self.api_box.currentIndex()
            self.api_box.blockSignals(True)
            self.api_box.clear()
            self.api_box.addItems([
                "标准版 general_basic",
                "高精度版 accurate_basic",
                "标准版含位置 general_enhanced",
                "高精度版含位置 accurate_enhanced",
                "网络图片识别 webimage",
                "手写文字识别 handwriting"
            ])
            self.api_box.setCurrentIndex(current_api_index)
            self.api_box.blockSignals(False)
            
            current_mode_index = self.mode_box.currentIndex()
            self.mode_box.blockSignals(True)
            self.mode_box.clear()
            self.mode_box.addItems([
                "精确匹配 (exact)",
                "模糊匹配 (fuzzy)",
                "正则匹配 (regex)"
            ])
            self.mode_box.setCurrentIndex(current_mode_index)
            self.mode_box.blockSignals(False)
            
            # 刷新分组框标题
            # 需要找到分组框并更新标题
            for child in self.findChildren(QGroupBox):
                if child.title() == "OCR设置" or "OCR" in child.title():
                    child.setTitle("OCR设置")
                elif child.title() == "匹配设置" or "匹配" in child.title():
                    child.setTitle("匹配设置")
                elif child.title() == "操作" or "操作" in child.title():
                    child.setTitle("操作")
            
            # 刷新状态标签（保持当前状态文本，只更新"状态："前缀）
            current_status = self.status_label.text()
            if "状态：" in current_status:
                status_text = current_status.split("状态：", 1)[1] if "状态：" in current_status else current_status
                self.status_label.setText(f"状态：{status_text}")

            # 重新应用接口可用性状态，防止刷新后丢失禁用效果
            try:
                self.apply_version_availability()
            except Exception as e:
                logging.warning(f"刷新文本后应用接口可用性异常: {e}")
            
        except Exception as e:
            import logging
            logging.error(f"刷新ControlPanel UI文本时出错: {e}")

    # ---------- 接口可用性：无密钥则禁用 ----------
    def _get_api_configs(self):
        """读取加密的API配置，如果失败返回空字典"""
        try:
            with open("apikey.enc", "rb") as f:
                enc_data = f.read()
            data = decrypt_api_data(enc_data)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _is_version_available(self, cfg: dict, version_key: str) -> bool:
        """判断某个接口版本是否已配置有效密钥（且未被显式禁用）"""
        v = cfg.get(version_key, {}) if isinstance(cfg, dict) else {}
        if not isinstance(v, dict):
            return False
        # 显式禁用标志优先
        if v.get("DISABLED") is True:
            return False
        api_key = v.get("API_KEY", "")
        secret_key = v.get("SECRET_KEY", "")
        return bool(api_key) and bool(secret_key)

    def apply_version_availability(self):
        """根据apikey.enc配置，禁用未配置密钥的接口选项，并提供提示"""
        cfg = self._get_api_configs()
        availability = {
            0: self._is_version_available(cfg, "general"),
            1: self._is_version_available(cfg, "accurate"),
            2: self._is_version_available(cfg, "general_enhanced"),
            3: self._is_version_available(cfg, "accurate_enhanced"),
            4: self._is_version_available(cfg, "webimage"),
            5: self._is_version_available(cfg, "handwriting"),
        }
        self._version_enabled_map = availability

        # 应用禁用和提示
        model = self.api_box.model()
        for idx in range(self.api_box.count()):
            item = model.item(idx)
            if item is None:
                continue
            enabled = availability.get(idx, False)
            # 正确设置可用性与灰显
            item.setEnabled(enabled)
            try:
                flags = item.flags()
                if enabled:
                    item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
                else:
                    item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)
            except Exception:
                pass
            item.setForeground(QBrush(QColor("black" if enabled else "gray")))
            item.setToolTip("" if enabled else "未配置密钥，请在设置中输入")

        # 如果当前所选项不可用，自动切换到第一个可用项
        current_idx = self.api_box.currentIndex()
        if not availability.get(current_idx, False):
            fallback_idx = next((i for i, ok in availability.items() if ok), -1)
            if fallback_idx != -1:
                self.api_box.blockSignals(True)
                self.api_box.setCurrentIndex(fallback_idx)
                self.api_box.blockSignals(False)
                # 同步保存设置
                self.change_api_version(fallback_idx)
            else:
                # 所有都不可用时，保持当前选择但不做修改
                logging.warning("未配置任何OCR密钥，所有接口均不可用")
