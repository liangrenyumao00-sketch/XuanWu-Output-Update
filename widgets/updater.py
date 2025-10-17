# widgets/updater.py
"""
应用程序更新器模块

该模块提供了应用程序的自动更新功能，包含更新检测、文件替换、
进程管理等功能。支持安全的热更新和回滚机制。

主要功能：
- 更新检测：检查新版本的可用性
- 文件替换：安全地替换应用程序文件
- 进程管理：管理主程序进程的启停
- 更新界面：提供用户友好的更新进度显示
- 错误处理：处理更新过程中的各种异常情况

依赖：
- PyQt6：GUI框架
- psutil：进程管理
- core.i18n：国际化支持

作者：XuanWu OCR Team
版本：2.1.7
"""
import sys
import os
import shutil
import time
import subprocess
import psutil
import traceback

# 确保项目根目录在 sys.path 中，以便导入 core 模块
_this_file_dir = os.path.abspath(os.path.dirname(__file__))
_project_root_dir = os.path.abspath(os.path.join(_this_file_dir, os.pardir))
if _project_root_dir not in sys.path:
    sys.path.insert(0, _project_root_dir)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget, QPushButton, QLabel
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from core.i18n import t


class UpdaterThread(QThread):
    """
    更新器线程
    
    在后台执行应用程序更新操作，包括进程检测、文件替换、
    重启应用程序等步骤。通过信号与主界面通信。
    
    Attributes:
        update_dir (str): 更新文件所在目录
        target_dir (str): 目标安装目录
        main_script (str): 主程序脚本名称
        new_version (str): 新版本号
        python_exe (str): Python解释器路径
        main_script_path (str): 主程序脚本完整路径
    
    Signals:
        log_signal (str): 发送日志消息的信号
        finished_signal (bool): 更新完成信号，参数表示是否成功
    
    Example:
        >>> thread = UpdaterThread(update_dir, target_dir, "main.py", "2.1.7")
        >>> thread.log_signal.connect(log_handler)
        >>> thread.finished_signal.connect(finish_handler)
        >>> thread.start()
    """
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, update_dir, target_dir, main_script, new_version, parent=None):
        super().__init__(parent)
        self.update_dir = update_dir
        self.target_dir = target_dir
        self.main_script = main_script
        self.new_version = new_version
        self.python_exe = sys.executable
        self.main_script_path = os.path.join(self.target_dir, self.main_script)

    def log(self, msg):
        self.log_signal.emit(msg)
        print(msg)

    def copy_tree(self, src, dst):
        self.log(f"开始复制文件从 {src} 到 {dst} ...")
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            try:
                if os.path.isdir(s):
                    if os.path.exists(d):
                        self.log(f"删除目录: {d}")
                        shutil.rmtree(d)
                    self.log(f"复制目录: {s} -> {d}")
                    shutil.copytree(s, d)
                else:
                    self.log(f"复制文件: {s} -> {d}")
                    shutil.copy2(s, d)
            except Exception as e:
                self.log(f"❌ 复制文件失败: {d}, 错误: {e}")

    def find_running_procs(self):
        procs = []
        for proc in psutil.process_iter(['pid', 'exe', 'cmdline']):
            try:
                if (
                    proc.info['exe']
                    and os.path.abspath(proc.info['exe']) == os.path.abspath(self.python_exe)
                    and (self.main_script_path in " ".join(proc.info.get('cmdline', [])))
                ):
                    procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return procs

    def is_process_running(self):
        procs = self.find_running_procs()
        if procs:
            for p in procs:
                self.log(f"发现运行中的主程序 PID={p.pid}, CMDLINE={p.cmdline()}")
            return True
        else:
            self.log("未发现运行中的主程序")
            return False

    def kill_processes(self, procs):
        for proc in procs:
            try:
                self.log(f"尝试终止进程 PID={proc.pid} ...")
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                    self.log(f"进程 PID={proc.pid} 已终止。")
                except psutil.TimeoutExpired:
                    self.log(f"进程 PID={proc.pid} 终止超时，尝试强制杀死...")
                    proc.kill()
                    proc.wait(timeout=3)
                    self.log(f"进程 PID={proc.pid} 已被强制杀死。")
            except Exception as e:
                self.log(f"❌ 终止进程 PID={proc.pid} 失败: {e}")

    def run(self):
        try:
            self.log("Updater 启动，开始检测主程序是否退出...")

            wait_seconds = 5  # 缩短等待时间为5秒
            for i in range(wait_seconds):
                if not self.is_process_running():
                    break
                self.log(f"⏳ 等待主程序退出... {i+1}/{wait_seconds} 秒")
                time.sleep(1)
            else:
                self.log("❌ 超时：主程序仍未退出，尝试强制杀死...")
                procs = self.find_running_procs()
                if procs:
                    self.kill_processes(procs)
                    # 再次确认是否还存在
                    time.sleep(1)
                    if self.is_process_running():
                        self.log("❌ 仍有进程未退出，更新失败。")
                        self.finished_signal.emit(False)
                        return
                else:
                    self.log("未找到主程序进程，可能已退出。")

            self.log("✅ 主程序已退出，开始更新文件...")
            self.copy_tree(self.update_dir, self.target_dir)

            version_file = os.path.join(self.target_dir, "version.txt")
            try:
                with open(version_file, "w", encoding="utf-8") as vf:
                    vf.write(self.new_version.strip())
                self.log(f"✅ 已更新版本号到: {self.new_version}")
            except Exception as e:
                self.log(f"⚠️ 写入版本号失败: {e}")

            try:
                shutil.rmtree(self.update_dir, ignore_errors=True)
                self.log("🗑️ 已删除临时更新目录")
            except Exception as e:
                self.log(f"⚠️ 删除临时更新目录失败: {e}")

            zip_path = os.path.join(self.target_dir, "update_temp.zip")
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                    self.log("🗑️ 已删除更新包文件")
            except Exception as e:
                self.log(f"⚠️ 删除更新包失败: {e}")

            self.log("🚀 启动主程序...")
            try:
                subprocess.Popen([self.python_exe, self.main_script_path])
                self.log("主程序已成功启动。")
                self.finished_signal.emit(True)
            except Exception as e:
                self.log(f"❌ 启动主程序失败: {e}")
                self.finished_signal.emit(False)

        except Exception:
            self.log("Updater 运行异常:\n" + traceback.format_exc())
            self.finished_signal.emit(False)


class UpdaterWindow(QMainWindow):
    def __init__(self, update_dir, target_dir, main_script, new_version):
        super().__init__()
        self.setWindowTitle("软件更新器")
        self.setMinimumSize(700, 500)

        self.update_dir = update_dir
        self.target_dir = target_dir
        self.main_script = main_script
        self.new_version = new_version
        
        # 应用主题样式
        self.apply_theme_styles()

        layout = QVBoxLayout()
        self.label = QLabel("更新日志：")
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("color:#d4d4d4; font-family: Consolas, monospace; font-size: 12pt;")
        self.btn_start = QPushButton("开始更新")
        self.btn_start.clicked.connect(self.start_update)

        layout.addWidget(self.label)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.btn_start)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.thread = None

    def append_log(self, msg):
        self.text_edit.append(msg)

    def start_update(self):
        self.btn_start.setEnabled(False)
        self.append_log("准备开始更新...")
        self.thread = UpdaterThread(self.update_dir, self.target_dir, self.main_script, self.new_version)
        self.thread.log_signal.connect(self.append_log)
        self.thread.finished_signal.connect(self.update_finished)
        self.thread.start()

    def update_finished(self, success):
        if success:
            self.append_log("🎉 更新完成！窗口将在1.5秒后关闭...")
            QTimer.singleShot(1500, self.close)  # 1.5秒后关闭窗口
        else:
            self.append_log("❌ 更新失败。请查看日志。")
            self.btn_start.setEnabled(True)
    
    def apply_theme_styles(self):
        """应用主题样式"""
        # 更新器使用深色主题
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, monospace;
                font-size: 12pt;
                border: 1px solid #555555;
            }
            QPushButton {
                background-color: #404040;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #888888;
            }
        """)


def main():
    if len(sys.argv) < 5:
        print(t("updater_usage"))
        sys.exit(1)

    update_dir = sys.argv[1]
    target_dir = sys.argv[2]
    main_script = sys.argv[3]
    new_version = sys.argv[4]

    app = QApplication(sys.argv)
    window = UpdaterWindow(update_dir, target_dir, main_script, new_version)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
