#!/usr/bin/env python3
"""Karbordi Windows desktop launcher."""
from __future__ import annotations

import socket
import threading
import tkinter as tk
from tkinter import messagebox
import webbrowser
from pathlib import Path
import server


BG = "#f3f7f4"
GREEN = "#176b53"
DARK = "#123c35"
GOLD = "#c49a48"
TEXT = "#173a34"
MUTED = "#60736e"


def local_addresses():
    found = set()
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = item[4][0]
            if not ip.startswith("127."):
                found.add(ip)
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 80))
            ip = s.getsockname()[0]
            if not ip.startswith("127."):
                found.add(ip)
    except OSError:
        pass
    return sorted(found)


class KarbordiApp:
    def __init__(self, root):
        self.root = root
        self.httpd = None
        self.server_thread = None
        self.root.title("کاربُردی | انتقال فایل")
        self.root.geometry("690x650")
        self.root.minsize(620, 590)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        header = tk.Frame(root, bg=DARK, padx=24, pady=20)
        header.pack(fill="x")
        tk.Label(header, text="↔", font=("Segoe UI Symbol", 28, "bold"),
                 fg="#f0d99e", bg=DARK).pack(side="right", padx=(0, 14))
        titlebox = tk.Frame(header, bg=DARK)
        titlebox.pack(side="right", fill="x", expand=True)
        tk.Label(titlebox, text="کاربُردی", font=("Tahoma", 22, "bold"),
                 fg="white", bg=DARK, anchor="e").pack(fill="x")
        tk.Label(titlebox, text="انتقال آسان فایل بین ویندوز و اندروید",
                 font=("Tahoma", 10), fg="#d6e7df", bg=DARK, anchor="e").pack(fill="x")
        tk.Frame(root, bg=GOLD, height=4).pack(fill="x")

        body = tk.Frame(root, bg=BG, padx=24, pady=18)
        body.pack(fill="both", expand=True)

        self.status = tk.Label(body, text="در حال آماده‌سازی برنامه…",
                               font=("Tahoma", 11, "bold"), bg=BG, fg=GREEN, anchor="e")
        self.status.pack(fill="x", pady=(0, 12))

        self.card(body, "۱. آدرس اتصال")
        self.address_text = tk.Text(body, height=3, wrap="word", font=("Consolas", 12),
                                    bg="white", fg=TEXT, relief="flat", padx=12, pady=9)
        self.address_text.pack(fill="x", pady=(0, 8))
        self.address_text.configure(state="disabled")

        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(0, 15))
        self.button(row, "باز کردن صفحه انتقال", self.open_page, primary=True).pack(side="right", padx=(0, 8))
        self.button(row, "کپی آدرس", self.copy_addresses).pack(side="right")

        self.card(body, "۲. کد اتصال")
        code_row = tk.Frame(body, bg="white", padx=14, pady=10)
        code_row.pack(fill="x", pady=(0, 15))
        self.code_label = tk.Label(code_row, text=server.ACCESS_CODE, font=("Consolas", 25, "bold"),
                                   fg=GREEN, bg="white")
        self.code_label.pack(side="right")
        self.button(code_row, "کپی کد", self.copy_code).pack(side="left")

        self.card(body, "۳. پوشه‌های فایل")
        tk.Label(body, text="برای ارسال فایل از این رایانه به دستگاه دیگر، فایل را در پوشه Shared قرار بده.",
                 font=("Tahoma", 9), bg=BG, fg=MUTED, anchor="e", justify="right").pack(fill="x", pady=(0, 8))
        folder_row = tk.Frame(body, bg=BG)
        folder_row.pack(fill="x", pady=(0, 16))
        self.button(folder_row, "پوشه فایل‌های ارسالی", lambda: self.open_folder(server.SHARED_DIR)).pack(side="right", padx=(0, 8))
        self.button(folder_row, "پوشه فایل‌های دریافتی", lambda: self.open_folder(server.RECEIVED_DIR)).pack(side="right")

        tip = ("گوشی و رایانه دوم باید به همان Wi-Fi وصل باشند. آدرس را در مرورگر دستگاه دوم باز کن و کد بالا را وارد کن. "
               "این پنجره را تا پایان انتقال باز نگه دار.")
        tk.Label(body, text=tip, font=("Tahoma", 9), bg="#e5f2e9", fg=TEXT,
                 wraplength=620, justify="right", anchor="e", padx=12, pady=10).pack(fill="x")

        bottom = tk.Frame(root, bg=BG, padx=24, pady=12)
        bottom.pack(fill="x")
        self.button(bottom, "توقف برنامه و خروج", self.close).pack(side="left")
        tk.Label(bottom, text="نسخه محلی · بدون فضای ابری", font=("Tahoma", 8),
                 bg=BG, fg=MUTED).pack(side="right")

        self.start_server()

    def card(self, parent, title):
        tk.Label(parent, text=title, font=("Tahoma", 11, "bold"), bg=BG,
                 fg=TEXT, anchor="e").pack(fill="x", pady=(0, 6))

    def button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, font=("Tahoma", 9, "bold"),
                         bg=GREEN if primary else "#e4eee8",
                         fg="white" if primary else TEXT, activebackground="#2b8067",
                         activeforeground="white", relief="flat", bd=0, padx=14, pady=9,
                         cursor="hand2")

    def start_server(self):
        try:
            self.httpd = server.Server(("0.0.0.0", server.PORT), server.TransferHandler)
        except OSError as exc:
            self.status.configure(text="برنامه اجرا نشد؛ درگاه اتصال در دسترس نیست.", fg="#a33a32")
            messagebox.showerror("خطای اجرا", f"درگاه {server.PORT} قابل استفاده نیست. برنامه دیگری ممکن است آن را اشغال کرده باشد.\n\n{exc}")
            return
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        addresses = local_addresses()
        urls = [f"http://{ip}:{server.PORT}" for ip in addresses]
        if not urls:
            urls = [f"http://127.0.0.1:{server.PORT} (فقط همین رایانه)"]
        self.address_text.configure(state="normal")
        self.address_text.insert("1.0", "\n".join(urls))
        self.address_text.configure(state="disabled")
        self.status.configure(text="● برنامه فعال است و آماده انتقال فایل است", fg=GREEN)
        self.urls = urls

    def copy_addresses(self):
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(self.urls))
        self.status.configure(text="آدرس اتصال کپی شد.")

    def copy_code(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(server.ACCESS_CODE)
        self.status.configure(text="کد اتصال کپی شد.")

    def open_page(self):
        if self.urls:
            webbrowser.open(self.urls[0])

    def open_folder(self, folder: Path):
        folder.mkdir(parents=True, exist_ok=True)
        import os
        os.startfile(str(folder))

    def close(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        self.root.destroy()


def main():
    root = tk.Tk()
    KarbordiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
