import tkinter as tk
from tkinter import simpledialog, messagebox
import json
import requests
import os
import threading
from datetime import datetime

SESSION_DIR = "D:\\joy\\HistoryAi"
os.makedirs(SESSION_DIR, exist_ok=True)

class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI 对话程序")

        self.api_url = ""
        self.api_key = ""
        self.model = ""
        self.messages = []
        self.api_key_visible = False
        self.current_filename = None

        self.build_gui()
        self.refresh_session_list()

    def build_gui(self):
        self.session_listbox = tk.Listbox(self.root, width=25, height=30)
        self.session_listbox.grid(row=0, column=0, rowspan=6, padx=5, pady=5, sticky="ns")
        self.session_listbox.bind("<<ListboxSelect>>", self.on_session_select)

        tk.Label(self.root, text="API地址:").grid(row=0, column=1)
        self.api_url_entry = tk.Entry(self.root, width=60)
        self.api_url_entry.grid(row=0, column=2, columnspan=2)

        tk.Label(self.root, text="APIKey:").grid(row=1, column=1)
        self.api_key_entry = tk.Entry(self.root, width=50, show="*")
        self.api_key_entry.grid(row=1, column=2)
        self.toggle_key_button = tk.Button(self.root, text="显示", width=8, command=self.toggle_api_key_visibility)
        self.toggle_key_button.grid(row=1, column=3)

        tk.Label(self.root, text="模型名:").grid(row=2, column=1)
        self.model_entry = tk.Entry(self.root, width=60)
        self.model_entry.grid(row=2, column=2, columnspan=2)

        tk.Button(self.root, text="新建对话", command=self.new_session).grid(row=3, column=2)
        tk.Button(self.root, text="保存对话", command=self.save_session).grid(row=3, column=3)

        self.chat_text = tk.Text(self.root, height=20, width=80, state="disabled")
        self.chat_text.grid(row=4, column=1, columnspan=3, padx=5, pady=5)

        # 设置样式标签
        self.chat_text.tag_config("user", foreground="blue", font=("Arial", 10, "bold"))
        self.chat_text.tag_config("ai", foreground="black", font=("Arial", 10))
        self.chat_text.tag_config("system", foreground="gray", font=("Arial", 10, "italic"))

        self.input_entry = tk.Entry(self.root, width=65)
        self.input_entry.grid(row=5, column=1, columnspan=2, padx=5, pady=5)
        self.input_entry.bind("<Return>", lambda event: self.send_message())
        tk.Button(self.root, text="发送", command=self.send_message).grid(row=5, column=3)

    def toggle_api_key_visibility(self):
        if self.api_key_visible:
            self.api_key_entry.config(show="*")
            self.toggle_key_button.config(text="显示")
        else:
            self.api_key_entry.config(show="")
            self.toggle_key_button.config(text="隐藏")
        self.api_key_visible = not self.api_key_visible

    def refresh_session_list(self):
        self.session_listbox.delete(0, tk.END)
        files = sorted(f for f in os.listdir(SESSION_DIR) if f.endswith(".json"))
        for f in files:
            self.session_listbox.insert(tk.END, f)

    def new_session(self):
        self.api_url = self.api_url_entry.get()
        self.api_key = self.api_key_entry.get()
        self.model = self.model_entry.get()
        if not self.api_url or not self.api_key or not self.model:
            messagebox.showerror("错误", "请填写API地址、Key和模型名")
            return
        self.messages = []
        self.current_filename = None
        self.chat_text.config(state="normal")
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.insert(tk.END, "[新对话已开始]\n", "system")
        self.chat_text.config(state="disabled")

    def send_message(self):
        user_input = self.input_entry.get().strip()
        if not user_input:
            return
        self.model = self.model_entry.get()  # 更新模型
        self.input_entry.delete(0, tk.END)
        self.messages.append({"role": "user", "content": user_input})
        self.append_text(f"你：{user_input}\n", tag="user")
        threading.Thread(target=self.send_message_thread).start()

    def send_message_thread(self):
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": self.messages
            }
            response = requests.post(self.api_url, headers=headers, json=payload)
            data = response.json()

            if "choices" not in data:
                error_msg = data.get("error", {}).get("message", "API未返回choices字段")
                self.append_text(f"[错误] {error_msg}\n", tag="system")
                return

            reply = data["choices"][0]["message"]["content"]
            self.messages.append({"role": "assistant", "content": reply})
            self.append_text(f"AI：{reply}\n", tag="ai")

        except Exception as e:
            self.append_text(f"[错误] {e}\n", tag="system")

    def append_text(self, text, tag=""):
        self.chat_text.config(state="normal")
        if tag:
            self.chat_text.insert(tk.END, text, tag)
        else:
            self.chat_text.insert(tk.END, text)
        self.chat_text.see(tk.END)
        self.chat_text.config(state="disabled")

    def save_session(self):
        if not self.current_filename:
            filename = simpledialog.askstring("保存对话", "请输入会话名称：")
            if not filename:
                return
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.current_filename = f"{filename}_{timestamp}.json"

        filepath = os.path.join(SESSION_DIR, self.current_filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "api_url": self.api_url,
                "api_key": self.api_key,
                "model": self.model,
                "messages": self.messages
            }, f, indent=2)
        messagebox.showinfo("成功", f"已保存到 {filepath}")
        self.refresh_session_list()

        # 清空对话和输入框内容
        self.messages = []
        self.chat_text.config(state="normal")
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.insert(tk.END, "[新对话已开始]\n", "system")
        self.chat_text.config(state="disabled")
        self.input_entry.delete(0, tk.END)

        # 清除API地址、Key、模型框内容
        self.api_url_entry.delete(0, tk.END)
        self.api_key_entry.delete(0, tk.END)
        self.model_entry.delete(0, tk.END)

        self.api_url = ""
        self.api_key = ""
        self.model = ""
        self.current_filename = None

    def on_session_select(self, event):
        if not self.session_listbox.curselection():
            return
        index = self.session_listbox.curselection()[0]
        filename = self.session_listbox.get(index)
        filepath = os.path.join(SESSION_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.api_url = data["api_url"]
        self.api_key = data["api_key"]
        self.model = data["model"]
        self.messages = data["messages"]
        self.current_filename = filename

        self.api_url_entry.delete(0, tk.END)
        self.api_url_entry.insert(0, self.api_url)
        self.api_key_entry.delete(0, tk.END)
        self.api_key_entry.insert(0, self.api_key)
        self.model_entry.delete(0, tk.END)
        self.model_entry.insert(0, self.model)

        self.chat_text.config(state="normal")
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.insert(tk.END, f"[已载入对话：{filename}]\n", "system")
        for msg in self.messages:
            role = "你" if msg["role"] == "user" else "AI"
            tag = "user" if msg["role"] == "user" else "ai"
            self.chat_text.insert(tk.END, f"{role}：{msg['content']}\n", tag)
        self.chat_text.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()