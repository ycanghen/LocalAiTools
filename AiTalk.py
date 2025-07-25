import sys
import os
import json
import requests
import threading
import base64
import re
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QListWidget, QFileDialog, QMessageBox, QLabel, QComboBox
)
from PySide6.QtGui import QTextCursor, QTextCharFormat, QFont, QColor, QIcon

SESSION_DIR = "D:/joy/HistoryAi"
os.makedirs(SESSION_DIR, exist_ok=True)

SUPPORTED_MODELS = {
    "gpt-4o": ["text", "image"],
    "gpt-4-vision-preview": ["text", "image"],
    "o4-mini": ["text", "image"],
    "gpt-4.1-mini": ["text"],
    "gpt-3.5-turbo": ["text"]
}

class SettingsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(400, 200)

        self.prompt_label = QLabel("全局 Prompt（角色设定）：")
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("例如：你是一个有趣的历史老师")

        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self.close)

        layout = QVBoxLayout()
        layout.addWidget(self.prompt_label)
        layout.addWidget(self.prompt_input)
        layout.addWidget(self.save_btn)
        self.setLayout(layout)

    def get_prompt(self):
        return self.prompt_input.text().strip()

class ChatWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 聊天程序 - PySide6 优雅版")
        self.resize(900, 600)
        self.setWindowIcon(QIcon("tubiao.jpg"))

        self.settings_window = SettingsWindow()
        self.api_url = ""
        self.api_key = ""
        self.model = ""
        self.messages = []
        self.current_filename = None
        self.pending_image = None

        self.init_ui()
        self.load_history()

    def init_ui(self):
        layout = QHBoxLayout()

        self.history_list = QListWidget()
        self.history_list.setFixedWidth(200)
        self.history_list.itemClicked.connect(self.load_selected_session)

        right_layout = QVBoxLayout()

        self.settings_btn = QPushButton("设置")
        self.settings_btn.clicked.connect(self.open_settings)

        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("API 地址")

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("API Key")
        self.api_key_input.setEchoMode(QLineEdit.Password)

        self.model_dropdown = QComboBox()
        self.model_dropdown.setEditable(True)
        self.model_dropdown.setPlaceholderText("模型名称")
        self.model_dropdown.setMinimumWidth(200)

        self.refresh_model_btn = QPushButton("刷新模型")
        self.refresh_model_btn.clicked.connect(self.fetch_models)

        self.toggle_key_btn = QPushButton("显示 Key")
        self.toggle_key_btn.setFixedWidth(80)
        self.toggle_key_btn.clicked.connect(self.toggle_key_visibility)

        input_row = QHBoxLayout()
        input_row.addWidget(self.api_url_input)
        input_row.addWidget(self.api_key_input)
        input_row.addWidget(self.model_dropdown)
        input_row.addWidget(self.refresh_model_btn)
        input_row.addWidget(self.toggle_key_btn)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("background-color: #f5f5f5;")

        self.user_input = QTextEdit()
        self.user_input.setPlaceholderText("请输入消息...")
        self.user_input.setFixedHeight(80)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: gray")

        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.send_message)

        self.upload_image_btn = QPushButton("上传图片")
        self.upload_image_btn.clicked.connect(self.upload_image)

        self.save_btn = QPushButton("保存对话")
        self.save_btn.clicked.connect(self.save_session)

        self.new_btn = QPushButton("新建对话")
        self.new_btn.clicked.connect(self.new_session)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.settings_btn)
        btn_row.addWidget(self.send_btn)
        btn_row.addWidget(self.upload_image_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.new_btn)

        right_layout.addLayout(input_row)
        right_layout.addWidget(self.chat_display)
        right_layout.addWidget(self.user_input)
        right_layout.addLayout(btn_row)
        right_layout.addWidget(self.status_label)

        layout.addWidget(self.history_list)
        layout.addLayout(right_layout)
        self.setLayout(layout)

    def open_settings(self):
        self.settings_window.show()

    def fetch_models(self):
        api_url = self.api_url_input.text().strip()
        api_key = self.api_key_input.text().strip()
        if not api_url or not api_key:
            QMessageBox.warning(self, "提示", "请先输入 API 地址和 Key")
            return
        try:
            base_url = re.sub(r"/v1/.*$", "", api_url)
            model_url = f"{base_url}/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.get(model_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            models = [m["id"] for m in data.get("data", []) if isinstance(m.get("id"), str)]
            self.model_dropdown.clear()
            self.model_dropdown.addItems(models)
        except Exception as e:
            QMessageBox.critical(self, "获取失败", f"无法获取模型列表：\n{e}")

    def new_session(self):
        self.api_url = self.api_url_input.text().strip()
        self.api_key = self.api_key_input.text().strip()
        self.model = self.model_dropdown.currentText()
        self.messages = []
        self.current_filename = None
        self.chat_display.clear()
        self.append_text("[新对话已开始]\n", role="system")

    def send_message(self):
        text = self.user_input.toPlainText().strip()
        if not text and not self.pending_image:
            return
        self.model = self.model_dropdown.currentText()
        self.api_url = self.api_url_input.text().strip()
        self.api_key = self.api_key_input.text().strip()
        self.user_input.clear()
        if self.pending_image:
            message = {"role": "user", "content": []}
            if text:
                message["content"].append({"type": "text", "text": text})
            message["content"].append({"type": "image_url", "image_url": {"url": self.pending_image}})
            self.pending_image = None
            self.append_text(f"你：{text} [图片已附带]\n", role="user")
        else:
            message = {"role": "user", "content": text}
            self.append_text(f"你：{text}\n", role="user")
        self.messages.append(message)
        self.status_label.setText("AI 正在思考中...")
        threading.Thread(target=self.call_api, daemon=True).start()

    def call_api(self):
        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            prompt_value = self.settings_window.get_prompt()
            final_messages = [{"role": "system", "content": prompt_value}] if prompt_value else []
            final_messages.extend(self.messages)
            payload = {"model": self.model, "messages": final_messages}
            res = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            data = res.json()
            if "choices" not in data:
                err = data.get("error", {}).get("message", "API 返回格式错误")
                self.append_text(f"[错误] {err}\n", role="system")
                self.status_label.setText("")
                return
            reply = data["choices"][0]["message"]["content"]
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.messages.append({"role": "assistant", "content": reply, "time": now, "model": self.model})
            self.append_text(f"AI（{now}，模型：{self.model}）：{reply}\n", role="ai")
        except Exception as e:
            self.append_text(f"[异常] {e}\n", role="system")
        finally:
            self.status_label.setText("")

    def upload_image(self):
        model_name = self.model_dropdown.currentText()
        if "image" not in SUPPORTED_MODELS.get(model_name, []):
            QMessageBox.warning(self, "不支持", "当前模型不支持图片输入。")
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images (*.png *.jpg *.jpeg)")
        if not file_path:
            return
        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        self.pending_image = f"data:image/jpeg;base64,{encoded}"
        self.append_text(f"你：已上传图片 {os.path.basename(file_path)}（将在下次发送时一并发送）\n", role="user")

    def append_text(self, text, role="ai"):
        fmt = QTextCharFormat()
        if role == "user":
            fmt.setForeground(QColor("blue"))
            fmt.setFontWeight(QFont.Bold)
        elif role == "ai":
            fmt.setForeground(QColor("black"))
        elif role == "system":
            fmt.setForeground(QColor("gray"))
            fmt.setFontItalic(True)
        self.chat_display.moveCursor(QTextCursor.End)
        self.chat_display.setCurrentCharFormat(fmt)
        self.chat_display.insertPlainText(text)
        self.chat_display.moveCursor(QTextCursor.End)

    def save_session(self):
        if not self.current_filename:
            name, _ = QFileDialog.getSaveFileName(self, "保存对话", SESSION_DIR, "*.json")
            if not name:
                return
            if not name.endswith(".json"):
                name += ".json"
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            base = os.path.splitext(os.path.basename(name))[0]
            self.current_filename = f"{base}_{timestamp}.json"
        filepath = os.path.join(SESSION_DIR, self.current_filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"api_url": self.api_url, "api_key": self.api_key, "model": self.model, "messages": self.messages}, f, indent=2)
        QMessageBox.information(self, "保存成功", f"对话保存至: {filepath}")
        self.load_history()
        self.chat_display.clear()
        self.api_url_input.clear()
        self.api_key_input.clear()
        self.model_dropdown.setCurrentText("")
        self.messages = []
        self.current_filename = None
        self.append_text("[新对话已开始]\n", role="system")

    def load_history(self):
        self.history_list.clear()
        for filename in sorted(os.listdir(SESSION_DIR)):
            if filename.endswith(".json"):
                self.history_list.addItem(filename)

    def toggle_key_visibility(self):
        if self.api_key_input.echoMode() == QLineEdit.Password:
            self.api_key_input.setEchoMode(QLineEdit.Normal)
            self.toggle_key_btn.setText("隐藏 Key")
        else:
            self.api_key_input.setEchoMode(QLineEdit.Password)
            self.toggle_key_btn.setText("显示 Key")

    def load_selected_session(self, item):
        filename = item.text()
        path = os.path.join(SESSION_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.api_url = data.get("api_url", "")
        self.api_key = data.get("api_key", "")
        self.model = data.get("model", "")
        self.messages = data.get("messages", [])
        self.current_filename = filename
        self.api_url_input.setText(self.api_url)
        self.api_key_input.setText(self.api_key)
        self.model_dropdown.setCurrentText(self.model)
        self.chat_display.clear()
        self.append_text(f"[已加载对话：{filename}]\n", role="system")
        for msg in self.messages:
            content = self.extract_clean_content(msg.get("content", ""))
            if not content:
                continue
            role = msg.get("role")
            time = msg.get("time", "")
            model = msg.get("model", self.model)
            name = "你" if role == "user" else f"AI（{time}，模型：{model}）" if time else "AI"
            self.append_text(f"{name}：{content}\n", role=role)

    def extract_clean_content(self, raw):
        if isinstance(raw, list):
            return " ".join("[图片]" for part in raw if isinstance(part, dict) and part.get("type") == "image_url")
        if not isinstance(raw, str):
            return ""
        if "<think>" in raw and "</think>" in raw:
            raw = raw.split("</think>")[-1].strip()
        lines = [line for line in raw.splitlines() if not line.strip().startswith("##")]
        return "\n".join(lines).strip()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ChatWindow()
    win.show()
    sys.exit(app.exec())
