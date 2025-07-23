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
    QLineEdit, QPushButton, QListWidget, QFileDialog, QMessageBox
)
from PySide6.QtGui import QTextCursor, QTextCharFormat, QFont, QColor
from PySide6.QtCore import Qt

SESSION_DIR = "D:/joy/HistoryAi"
os.makedirs(SESSION_DIR, exist_ok=True)

SUPPORTED_MODELS = {
    "gpt-4o": ["text", "image"],
    "gpt-4-vision-preview": ["text", "image"],
    "o4-mini": ["text", "image"],
    "gpt-4.1-mini": ["text"],
    "gpt-3.5-turbo": ["text"]
}

def extract_clean_content(content):
    if isinstance(content, list):
        return "[图片]"
    if not isinstance(content, str):
        return None

    match = re.search(r"## ?[\u4e00-\u9fa5]*回答[:：]?\n*(.+)", content, re.DOTALL)
    if match:
        return match.group(1).strip()

    if any(tag in content.lower() for tag in ["<think>", "<error>", "</think>", "<unk>", "<|", "</"]):
        return None

    return content.strip()

class ChatWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 聊天程序（半成品）")
        self.resize(900, 600)
        self.api_url = ""
        self.api_key = ""
        self.model = ""
        self.messages = []
        self.current_filename = None
        self.pending_image = None  # 临时保存图片

        self.init_ui()
        self.load_history()

    def init_ui(self):
        layout = QHBoxLayout()

        self.history_list = QListWidget()
        self.history_list.setFixedWidth(200)
        self.history_list.itemClicked.connect(self.load_selected_session)

        right_layout = QVBoxLayout()

        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("API 地址")

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("API Key")
        self.api_key_input.setEchoMode(QLineEdit.Password)

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("模型名称")

        self.toggle_key_btn = QPushButton("显示 Key")
        self.toggle_key_btn.setFixedWidth(80)
        self.toggle_key_btn.clicked.connect(self.toggle_key_visibility)

        input_row = QHBoxLayout()
        input_row.addWidget(self.api_url_input)
        input_row.addWidget(self.api_key_input)
        input_row.addWidget(self.model_input)
        input_row.addWidget(self.toggle_key_btn)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("background-color: #f5f5f5;")

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("请输入消息...")
        self.user_input.returnPressed.connect(self.send_message)

        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.send_message)

        self.new_btn = QPushButton("新建对话")
        self.new_btn.clicked.connect(self.new_session)

        self.save_btn = QPushButton("保存对话")
        self.save_btn.clicked.connect(self.save_session)

        self.upload_image_btn = QPushButton("上传图片")
        self.upload_image_btn.clicked.connect(self.upload_image)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.send_btn)
        btn_row.addWidget(self.upload_image_btn)
        btn_row.addWidget(self.new_btn)
        btn_row.addWidget(self.save_btn)

        right_layout.addLayout(input_row)
        right_layout.addWidget(self.chat_display)
        right_layout.addWidget(self.user_input)
        right_layout.addLayout(btn_row)

        layout.addWidget(self.history_list)
        layout.addLayout(right_layout)
        self.setLayout(layout)

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

    def new_session(self):
        self.api_url = self.api_url_input.text().strip()
        self.api_key = self.api_key_input.text().strip()
        self.model = self.model_input.text().strip()
        self.messages = []
        self.current_filename = None
        self.chat_display.clear()
        self.append_text("[新对话已开始]\n", role="system")

    def send_message(self):
        text = self.user_input.text().strip()
        if not text and not self.pending_image:
            return

        self.model = self.model_input.text().strip()
        self.api_url = self.api_url_input.text().strip()
        self.api_key = self.api_key_input.text().strip()
        self.user_input.clear()

        # 构造消息
        if self.pending_image:
            message = {
                "role": "user",
                "content": []
            }
            if text:
                message["content"].append({"type": "text", "text": text})
            message["content"].append({"type": "image_url", "image_url": {"url": self.pending_image}})
            self.pending_image = None
            self.append_text(f"你：{text} [图片已附带]\n", role="user")
        else:
            message = {
                "role": "user",
                "content": text
            }
            self.append_text(f"你：{text}\n", role="user")

        self.messages.append(message)
        threading.Thread(target=self.call_api, daemon=True).start()

    def call_api(self):
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": self.messages
            }
            res = requests.post(self.api_url, headers=headers, json=payload)
            data = res.json()
            if "choices" not in data:
                err = data.get("error", {}).get("message", "API 返回格式错误")
                self.append_text(f"[错误] {err}\n", role="system")
                return
            reply = data["choices"][0]["message"]["content"]
            self.messages.append({"role": "assistant", "content": reply})
            clean = extract_clean_content(reply)
            if clean:
                self.append_text(f"AI：{clean}\n", role="ai")
        except Exception as e:
            self.append_text(f"[异常] {e}\n", role="system")

    def upload_image(self):
        model_name = self.model_input.text().strip()
        if "image" not in SUPPORTED_MODELS.get(model_name, []):
            QMessageBox.warning(self, "不支持", "当前模型不支持图片输入。")
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images (*.png *.jpg *.jpeg)")
        if not file_path:
            return

        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")

        image_url = f"data:image/jpeg;base64,{encoded}"
        self.pending_image = image_url

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
            json.dump({
                "api_url": self.api_url,
                "api_key": self.api_key,
                "model": self.model,
                "messages": self.messages
            }, f, indent=2)
        QMessageBox.information(self, "保存成功", f"对话保存至: {filepath}")
        self.load_history()
        self.chat_display.clear()
        self.api_url_input.clear()
        self.api_key_input.clear()
        self.model_input.clear()
        self.messages = []
        self.current_filename = None
        self.append_text("[新对话已开始]\n", role="system")

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
        self.model_input.setText(self.model)

        self.chat_display.clear()
        self.append_text(f"[已加载对话：{filename}]\n", role="system")
        for msg in self.messages:
            raw = msg.get("content", "")
            content = extract_clean_content(raw)
            if not content:
                continue
            who = "你" if msg["role"] == "user" else "AI"
            self.append_text(f"{who}：{content}\n", role=msg["role"])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ChatWindow()
    win.show()
    sys.exit(app.exec())
