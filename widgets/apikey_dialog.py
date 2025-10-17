# widgets/apikey_dialog.py
import os
import sys
import json
import requests
import subprocess
import base64
import webbrowser
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton,
    QCheckBox, QWidget, QMessageBox, QApplication
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from Crypto.Cipher import AES
from core.settings import encrypt_api_data, decrypt_api_data, hash_sensitive_data
from core.log_desensitizer import get_log_desensitizer

# 使用专用logger，日志将记录到debug.html
logger = logging.getLogger('apikey_dialog')

APIKEY_PATH = "apikey.enc"

BAIDU_ERR_MAP = {
    1: "未知错误，请稍后再试",
    2: "服务暂不可用",
    3: "接口不存在或URL错误",
    4: "接口流量超限",
    6: "无接口权限，请在控制台启用OCR",
    14: "IAM鉴权失败",
    17: "每日免费额度用尽",
    18: "调用过快，请稍后",
    19: "请求总量超限",
    100: "无效的access_token",
    110: "access_token无效",
    111: "access_token过期",
    216100: "请求参数非法",
    216101: "缺少必须参数",
    216200: "图片为空或格式错误",
    282000: "服务器内部错误，请稍后"
}


def read_config() -> dict:
    if not os.path.exists(APIKEY_PATH):
        return {}
    try:
        with open(APIKEY_PATH, "rb") as f:
            return decrypt_api_data(f.read())
    except Exception:
        return {}


def write_config(cfg: dict) -> None:
    with open(APIKEY_PATH, "wb") as f:
        f.write(encrypt_api_data(cfg))


class ApiKeyDialog(QDialog):
    def __init__(self, load_keys=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置 API 密钥")
        self.resize(420, 360)
        self.setFont(QFont("微软雅黑", 8))

        # 窗口居中显示
        if parent:
            self.move(parent.geometry().center() - self.rect().center())

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(12)

        # 应用主题样式
        self.apply_theme_styles()
        
        # 创建UI组件
        self.create_ui()
        
        if load_keys:
            self.load_existing()
    
    def create_ui(self):
        """创建UI组件"""
        # 标准版输入区
        self.main_layout.addWidget(QLabel("标准版（通用OCR）API（*必填）"))
        self.std_api_input = self.create_lineedit_with_toggle("标准版 API_KEY")
        self.main_layout.addLayout(self.std_api_input['layout'])

        self.std_secret_input = self.create_lineedit_with_toggle("标准版 SECRET_KEY")
        self.main_layout.addLayout(self.std_secret_input['layout'])

        # 高精度选项
        self.accurate_checkbox = QCheckBox("我有高精度版密钥（可选）")
        self.accurate_checkbox.stateChanged.connect(
            lambda: self.accurate_widget.setVisible(self.accurate_checkbox.isChecked())
        )
        self.main_layout.addWidget(self.accurate_checkbox)

        # 高精度输入区
        self.accurate_widget = QWidget()
        acc_layout = QVBoxLayout(self.accurate_widget)
        acc_layout.setContentsMargins(0, 0, 0, 0)
        acc_layout.setSpacing(10)

        self.acc_api_input = self.create_lineedit_with_toggle("高精度 API_KEY")
        acc_layout.addLayout(self.acc_api_input['layout'])

        self.acc_secret_input = self.create_lineedit_with_toggle("高精度 SECRET_KEY")
        acc_layout.addLayout(self.acc_secret_input['layout'])

        self.accurate_widget.setVisible(False)
        self.main_layout.addWidget(self.accurate_widget)

        # 垂直按钮布局
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_save = QPushButton("保存并验证")
        self.btn_save.setObjectName("saveBtn")
        self.btn_save.setFixedHeight(28)
        self.btn_save.setMinimumWidth(160)
        self.btn_save.clicked.connect(self.save)
        btn_layout.addWidget(self.btn_save, alignment=Qt.AlignmentFlag.AlignCenter)

        self.btn_reg = QPushButton("没有账号？点击跳转百度智能云注册")
        self.btn_reg.setObjectName("regBtn")
        self.btn_reg.setFixedHeight(28)
        self.btn_reg.clicked.connect(lambda: webbrowser.open("https://cloud.baidu.com/"))
        btn_layout.addWidget(self.btn_reg, alignment=Qt.AlignmentFlag.AlignCenter)

        self.main_layout.addLayout(btn_layout)
    
    def apply_theme_styles(self):
        """应用主题样式，支持深色主题"""
        from core.settings import load_settings
        settings = load_settings()
        current_theme = settings.get('theme', '浅色')
        
        if current_theme == '深色':
            # 深色主题样式
            self.setStyleSheet("""
                QDialog {
                    background-color: #464646;
                    border-radius: 10px;
                    font-family: "微软雅黑", sans-serif;
                    color: #ffffff;
                }
                QLabel {
                    font-weight: 600;
                    font-size: 8.5pt;
                    color: #ffffff;
                    margin-bottom: 4px;
                }
                QLineEdit {
                    border: 1.2px solid #646464;
                    border-radius: 6px;
                    height: 24px;
                    padding: 4px 8px;
                    font-size: 8pt;
                    color: #ffffff;
                    background: #3c3c3c;
                    placeholder-text-color: #999999;
                }
                QLineEdit:focus {
                    border-color: #007acc;
                    background: #3c3c3c;
                }
                QPushButton#regBtn {
                    background-color: #3c3c3c;
                    color: #007acc;
                    border: 1.5px solid #007acc;
                    font-weight: 600;
                    height: 28px;
                    border-radius: 6px;
                    padding-left: 16px;
                    padding-right: 16px;
                    min-width: 0;
                }
                QPushButton#regBtn:hover {
                    background-color: #4a4a4a;
                }
                QPushButton#saveBtn {
                    background-color: #007acc;
                    border: none;
                    border-radius: 6px;
                    color: white;
                    font-weight: 600;
                    font-size: 9pt;
                    height: 28px;
                    padding-left: 20px;
                    padding-right: 20px;
                    min-width: 160px;
                }
                QPushButton#saveBtn:hover {
                    background-color: #1e88e5;
                }
                QCheckBox {
                    font-size: 9pt;
                    color: #ffffff;
                    margin: 6px 0;
                }
            """)
        else:
            # 浅色主题样式
            self.setStyleSheet("""
                QDialog {
                    background-color: #fafafa;
                    border-radius: 10px;
                    font-family: "微软雅黑", sans-serif;
                }
                QLabel {
                    font-weight: 600;
                    font-size: 8.5pt;
                    color: #222222;
                    margin-bottom: 4px;
                }
                QLineEdit {
                    border: 1.2px solid #bbb;
                    border-radius: 6px;
                    height: 24px;
                    padding: 4px 8px;
                    font-size: 8pt;
                    color: #222;
                    background: #fff;
                }
                QLineEdit:focus {
                    border-color: #409eff;
                    background: #fff;
                }
                QPushButton#regBtn {
                    background-color: #fff;
                    color: #409eff;
                    border: 1.5px solid #409eff;
                    font-weight: 600;
                    height: 28px;
                    border-radius: 6px;
                    padding-left: 16px;
                    padding-right: 16px;
                    min-width: 0;
                }
                QPushButton#regBtn:hover {
                    background-color: #e6f0ff;
                }
                QPushButton#saveBtn {
                    background-color: #409eff;
                    border: none;
                    border-radius: 6px;
                    color: white;
                    font-weight: 600;
                    font-size: 9pt;
                    height: 28px;
                    padding-left: 20px;
                    padding-right: 20px;
                    min-width: 160px;
                }
                QPushButton#saveBtn:hover {
                    background-color: #66b1ff;
                }
                QCheckBox {
                    font-size: 9pt;
                    color: #555;
                    margin: 6px 0;
                }
            """)

    def create_lineedit_with_toggle(self, placeholder):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setClearButtonEnabled(True)
        line_edit.setEchoMode(QLineEdit.EchoMode.Password)

        toggle_btn = QPushButton("显示")
        toggle_btn.setFixedWidth(40)
        toggle_btn.setCheckable(True)
        toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        def on_toggle():
            if toggle_btn.isChecked():
                line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
                toggle_btn.setText("隐藏")
            else:
                line_edit.setEchoMode(QLineEdit.EchoMode.Password)
                toggle_btn.setText("显示")

        toggle_btn.clicked.connect(on_toggle)

        layout.addWidget(line_edit)
        layout.addWidget(toggle_btn)
        return {"layout": layout, "line_edit": line_edit, "toggle_btn": toggle_btn}

    def show_message(self, title, text, icon=QMessageBox.Icon.Information):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setIcon(icon)
        msg_box.setFont(QFont("微软雅黑", 8, QFont.Weight.Normal))
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #fafafa;
                border-radius: 10px;
            }
            QLabel {
                font-size: 8pt;
                color: #333;
                padding: 8px;
            }
            QPushButton {
                background-color: #409eff;
                color: white;
                font-weight: 600;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 8pt;
                min-width: 70px;
            }
            QPushButton:hover {
                background-color: #66b1ff;
            }
        """)
        msg_box.exec()

    def load_existing(self):
        cfg = read_config()
        general = cfg.get("general", {})
        if general:
            self.std_api_input['line_edit'].setText(general.get("API_KEY", ""))
            self.std_secret_input['line_edit'].setText(general.get("SECRET_KEY", ""))
        accurate = cfg.get("accurate")
        if accurate:
            self.accurate_checkbox.setChecked(True)
            self.accurate_widget.setVisible(True)
            self.acc_api_input['line_edit'].setText(accurate.get("API_KEY", ""))
            self.acc_secret_input['line_edit'].setText(accurate.get("SECRET_KEY", ""))

    def save(self):
        std_api = self.std_api_input['line_edit'].text().strip()
        std_secret = self.std_secret_input['line_edit'].text().strip()
        acc_checked = self.accurate_checkbox.isChecked()
        acc_api = self.acc_api_input['line_edit'].text().strip() if acc_checked else None
        acc_secret = self.acc_secret_input['line_edit'].text().strip() if acc_checked else None

        if not std_api or not std_secret:
            self.show_message("提示", "标准版密钥不能为空", QMessageBox.Icon.Warning)
            return

        ok, err = self.verify_key(std_api, std_secret)
        if not ok:
            desensitizer = get_log_desensitizer()
            safe_api = desensitizer.desensitize_text(std_api)
            safe_err = desensitizer.desensitize_text(str(err))
            logging.warning(f"标准版API密钥验证失败: {safe_api}, 错误: {safe_err}")
            self.show_message("验证失败", f"标准版验证失败：{err}", QMessageBox.Icon.Critical)
            return
        else:
            desensitizer = get_log_desensitizer()
            safe_api = desensitizer.desensitize_text(std_api)
            logging.info(f"标准版API密钥验证成功: {safe_api}")

        if acc_checked:
            if not acc_api or not acc_secret:
                self.show_message("提示", "请填写完整高精度密钥", QMessageBox.Icon.Warning)
                return
            ok, err = self.verify_key(acc_api, acc_secret)
            if not ok:
                desensitizer = get_log_desensitizer()
                safe_acc_api = desensitizer.desensitize_text(acc_api)
                safe_err = desensitizer.desensitize_text(str(err))
                logging.warning(f"高精度版API密钥验证失败: {safe_acc_api}, 错误: {safe_err}")
                self.show_message("验证失败", f"高精度验证失败：{err}", QMessageBox.Icon.Critical)
                return
            else:
                desensitizer = get_log_desensitizer()
                safe_acc_api = desensitizer.desensitize_text(acc_api)
                logging.info(f"高精度版API密钥验证成功: {safe_acc_api}")

        cfg = read_config()
        cfg["general"] = {"API_KEY": std_api, "SECRET_KEY": std_secret}
        if acc_checked:
            cfg["accurate"] = {"API_KEY": acc_api, "SECRET_KEY": acc_secret}
            # 若未显式禁用 accurate_enhanced，则可使用相同密钥进行初始化
            prev_acc_enh = cfg.get("accurate_enhanced", {})
            if not prev_acc_enh.get("DISABLED", False):
                cfg["accurate_enhanced"] = {"API_KEY": acc_api, "SECRET_KEY": acc_secret}
        else:
            cfg.pop("accurate", None)
            # 标记 accurate_enhanced 为禁用，避免重启后被自动重新启用
            cfg["accurate_enhanced"] = {"DISABLED": True}

        try:
            write_config(cfg)
        except Exception as e:
            self.show_message("错误", f"保存密钥失败：{e}", QMessageBox.Icon.Critical)
            return

        self.show_message("成功", "密钥保存成功，程序将重启", QMessageBox.Icon.Information)
        self.restart_program()

    def verify_key(self, api, secret):
        # 常见英文错误描述对应的中文提示
        ERROR_DESC_MAP = {
            "unknown client id": "无效的API Key，请检查输入是否正确",
            "invalid client secret": "无效的Secret Key，请检查输入是否正确",
            "invalid client": "无效的客户端信息，请检查API Key和Secret Key",
            "invalid client credentials": "无效的客户端凭据，请检查密钥",
            "invalid_grant": "授权无效，请检查密钥",
            "invalid_request": "请求无效，请检查参数",
        }

        try:
            r = requests.get(
                "https://aip.baidubce.com/oauth/2.0/token",
                params={"grant_type": "client_credentials", "client_id": api, "client_secret": secret},
                timeout=5,
            )
            data = r.json()

            if "access_token" in data:
                return True, None

            # 优先从 error_description 获取错误信息
            err_desc = data.get("error_description", "").lower()
            if err_desc:
                # 查找映射中文提示
                for k, v in ERROR_DESC_MAP.items():
                    if k in err_desc:
                        return False, v
                # 无匹配，显示原文并提示检查
                return False, f"{data['error_description']}，请检查API Key和Secret Key"

            # 其次检查 error 字段
            err = data.get("error", "").lower()
            if err:
                for k, v in ERROR_DESC_MAP.items():
                    if k in err:
                        return False, v
                return False, f"{data['error']}，请检查API Key和Secret Key"

            # 其他未知错误
            return False, f"验证失败，返回信息：{json.dumps(data, ensure_ascii=False)}"
        except requests.exceptions.RequestException as e:
            return False, f"网络错误：{str(e)}"

    def restart_program(self):
        exe = sys.executable
        script = os.path.abspath(sys.argv[0])
        try:
            if getattr(sys, "frozen", False):
                subprocess.Popen([exe])
            else:
                subprocess.Popen([exe, script])
        except Exception as e:
            self.show_message("重启失败", f"❌ 重启失败：{e}", QMessageBox.Icon.Critical)
        sys.exit(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = ApiKeyDialog()
    dlg.show()
    sys.exit(app.exec())
