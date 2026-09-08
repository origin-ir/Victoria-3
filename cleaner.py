import os
import re
import glob
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

class Victoria3CleanerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("1. Victoria 3 File Cleaner & Sanitizer")
        self.root.geometry("550x280")
        self.root.resizable(False, False)

        self.game_dir = tk.StringVar()
        self.setup_ui()

    def setup_ui(self):
        tk.Label(self.root, text="مرحله اول: پاکسازی و آماده‌سازی فایل‌های بازی", font=("Tahoma", 11, "bold")).pack(pady=15)

        frame_game = tk.LabelFrame(self.root, text=" پوشه اصلی بازی ", font=("Tahoma", 9))
        frame_game.pack(fill="x", padx=15, pady=5)
        tk.Entry(frame_game, textvariable=self.game_dir, width=45).pack(side="left", padx=8, pady=10)
        tk.Button(frame_game, text="انتخاب پوشه", command=self.browse_game).pack(side="right", padx=8, pady=10)

        self.status_lbl = tk.Label(self.root, text="وضعیت: منتظر انتخاب پوشه بازی", font=("Tahoma", 9))
        self.status_lbl.pack(pady=5)

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=500, mode="determinate")
        self.progress.pack(pady=5)

        tk.Button(self.root, text="شروع پاکسازی و بازسازی فایل‌ها (سریع)", font=("Tahoma", 10, "bold"), bg="#E91E63", fg="white", command=self.start_cleaning).pack(pady=15)

    def browse_game(self):
        path = filedialog.askdirectory(title="پوشه اصلی بازی Victoria 3 را انتخاب کنید")
        if path:
            self.game_dir.set(path)

    def clean_text(self, text):
        if not text:
            return text
        # پاکسازی تمام آرتيفکت‌های خراب‌شده، متغیرهای اشتباه و هادهای بیس۶۴
        text = re.sub(r'_\s*_\s*VAR\s*_\s*\d+\s*_\s*_', '', text, flags=re.IGNORECASE)
        text = re.sub(r'PH\s*\d+\s*PH', '', text, flags=re.IGNORECASE)
        text = re.sub(r'XYZ\s*\d+\s*XYZ', '', text, flags=re.IGNORECASE)
        text = re.sub(r'[a-zA-Z0-9+/=]{20,}', '', text)
        return re.sub(r'\s+', ' ', text).strip()

    def start_cleaning(self):
        base_dir = self.game_dir.get()
        loc_dir = os.path.join(base_dir, "game", "localization", "english")

        if not base_dir or not os.path.exists(loc_dir):
            messagebox.showerror("خطا", "پوشه localization/english در مسیر انتخابی پیدا نشد.")
            return

        # پاکسازی فایل کش قدیمی
        if os.path.exists("translation_cache.json"):
            try:
                os.remove("translation_cache.json")
            except Exception:
                pass

        yml_files = glob.glob(f"{loc_dir}/**/*.yml", recursive=True)
        total_files = len(yml_files)

        for idx, file_path in enumerate(yml_files):
            self.status_lbl.config(text=f"در حال تمیزکاری ({idx+1}/{total_files} فایل)...")
            self.progress['value'] = ((idx + 1) / total_files) * 100
            self.root.update_idletasks()

            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    lines = f.readlines()

                cleaned_lines = []
                for line in lines:
                    match = re.match(r'^(\s*[a-zA-Z0-9_.\-]+:\d*\s*")([^"]*)("(.*))?$', line)
                    if match:
                        prefix, content, suffix = match.group(1), match.group(2), match.group(3) or '"'
                        cleaned_content = self.clean_text(content)
                        cleaned_lines.append(f"{prefix}{cleaned_content}{suffix}\n")
                    else:
                        cleaned_lines.append(line)

                with open(file_path, 'w', encoding='utf-8-sig') as f:
                    f.writelines(cleaned_lines)
            except Exception:
                pass

        self.status_lbl.config(text="پاکسازی با موفقیت انجام شد!")
        messagebox.showinfo("موفقیت", "تمام فایل‌ها تمیز و بازسازی شدند. حالا برنامه مترجم را اجرا کنید.")

if __name__ == "__main__":
    root = tk.Tk()
    app = Victoria3CleanerApp(root)
    root.mainloop()
