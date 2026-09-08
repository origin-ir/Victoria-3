import os
import re
import glob
import shutil
import threading
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# بررسی و نصب پکیج‌های پیش‌نیاز در صورت اجرای مستقیم کد
try:
    from deep_translator import GoogleTranslator
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "deep-translator", "arabic-reshaper", "python-bidi"])
    from deep_translator import GoogleTranslator
    import arabic_reshaper
    from bidi.algorithm import get_display

class Victoria3TranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Victoria 3 Farsi Localizer (Desktop Version)")
        self.root.geometry("600x380")
        self.root.resizable(False, False)

        self.game_dir = tk.StringVar()
        self.font_path = tk.StringVar()
        self.translator = GoogleTranslator(source='en', target='fa')

        self.setup_ui()

    def setup_ui(self):
        # عنوان
        tk.Label(self.root, text="نرم‌افزار فارسی‌سازی Victoria 3 روی سیستم", font=("Tahoma", 14, "bold")).pack(pady=15)

        # انتخاب پوشه بازی
        frame_game = tk.LabelFrame(self.root, text=" پوشه اصلی بازی روی سیستم ", font=("Tahoma", 10))
        frame_game.pack(fill="x", padx=15, pady=5)

        tk.Entry(frame_game, textvariable=self.game_dir, width=50).pack(side="left", padx=10, pady=10)
        tk.Button(frame_game, text="انتخاب پوشه", command=self.browse_game).pack(side="right", padx=10, pady=10)

        # انتخاب فونت اختصاصی (اختیاری)
        frame_font = tk.LabelFrame(self.root, text=" فایل فونت فارسی (اختیاری - .ttf) ", font=("Tahoma", 10))
        frame_font.pack(fill="x", padx=15, pady=5)

        tk.Entry(frame_font, textvariable=self.font_path, width=50).pack(side="left", padx=10, pady=10)
        tk.Button(frame_font, text="انتخاب فونت", command=self.browse_font).pack(side="right", padx=10, pady=10)

        # وضعیت و Progress Bar
        self.status_lbl = tk.Label(self.root, text="وضعیت: آماده به کار", font=("Tahoma", 9))
        self.status_lbl.pack(pady=5)

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=540, mode="determinate")
        self.progress.pack(pady=5)

        # دکمه شروع
        self.btn_start = tk.Button(self.root, text="شروع عملیات ترجمه و اصلاح فایل‌ها", font=("Tahoma", 11, "bold"), bg="#2196F3", fg="white", command=self.start_thread)
        self.btn_start.pack(pady=15)

    def browse_game(self):
        path = filedialog.askdirectory(title="پوشه اصلی بازی Victoria 3 را انتخاب کنید")
        if path:
            self.game_dir.set(path)

    def browse_font(self):
        path = filedialog.askopenfilename(title="انتخاب فونت فارسی", filetypes=[("Font Files", "*.ttf")])
        if path:
            self.font_path.set(path)

    def fix_rtl(self, text):
        if not text:
            return text
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)

    def translate_text(self, text):
        text_str = text.strip()
        if not text or (text_str.startswith('[') and text_str.endswith(']')) or (text_str.startswith('$') and text_str.endswith('$')):
            return text

        pattern = r'(\[[^\]]+\]|\$[^\$]+\$|#[a-zA-Z0-9_! ]+#!)'
        placeholders = []

        def replace_with_placeholder(match):
            placeholders.append(match.group(0))
            return f"__VAR_{len(placeholders)-1}__"

        protected_text = re.sub(pattern, replace_with_placeholder, text)

        try:
            translated = self.translator.translate(protected_text)
            for i, ph in enumerate(placeholders):
                translated = translated.replace(f"__VAR_{i}__", ph)
            return translated
        except Exception:
            return text

    def start_thread(self):
        if not self.game_dir.get() or not os.path.exists(self.game_dir.get()):
            messagebox.showerror("خطا", "لطفاً مسیر صحیح پوشه اصلی بازی را انتخاب کنید.")
            return

        self.btn_start.config(state="disabled")
        threading.Thread(target=self.process, daemon=True).start()

    def process(self):
        base_dir = self.game_dir.get()
        loc_dir = os.path.join(base_dir, "game", "localization", "english")
        fonts_dir = os.path.join(base_dir, "game", "gui", "fonts")

        if not os.path.exists(loc_dir):
            messagebox.showerror("خطا", "پوشه localization/english در مسیر انتخابی پیدا نشد.")
            self.btn_start.config(state="normal")
            return

        # ۱. اصلاح فونت برای جلوگیری از مربع شدن کلمات
        self.status_lbl.config(text="وضعیت: در حال اعمال فونت فارسی...")
        if self.font_path.get() and os.path.exists(self.font_path.get()):
            font_source = self.font_path.get()
        else:
            font_source = os.path.join(os.getcwd(), "vazir.ttf")
            if not os.path.exists(font_source):
                try:
                    urllib.request.urlretrieve("https://github.com/rastikerdar/vazirmatn/releases/download/v33.003/Vazirmatn-Regular.ttf", font_source)
                except Exception:
                    pass

        if os.path.exists(font_source) and os.path.exists(fonts_dir):
            for target_font in glob.glob(os.path.join(fonts_dir, "*.ttf")):
                try:
                    shutil.copy(font_source, target_font)
                except Exception:
                    pass

        # ۲. ترجمه و اصلاح RTL فایل‌ها
        yml_files = glob.glob(f"{loc_dir}/**/*.yml", recursive=True)
        total_files = len(yml_files)

        for idx, file_path in enumerate(yml_files):
            filename = os.path.basename(file_path)
            self.status_lbl.config(text=f"در حال ترجمه ({idx+1}/{total_files}): {filename}")
            self.progress['value'] = ((idx + 1) / total_files) * 100

            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    lines = f.readlines()
            except Exception:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

            new_lines = []
            for line in lines:
                match = re.match(r'^(\s*[a-zA-Z0-9_.\-]+:\d*\s*")([^"]*)("(.*))?$', line)
                if match:
                    prefix = match.group(1)
                    content = match.group(2)
                    suffix = match.group(3) if match.group(3) else '"'

                    translated = self.translate_text(content)
                    fixed_rtl = self.fix_rtl(translated)
                    new_lines.append(f"{prefix}{fixed_rtl}{suffix}\n")
                else:
                    new_lines.append(line)

            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.writelines(new_lines)

        self.status_lbl.config(text="وضعیت: عملیات با موفقیت پایان یافت!")
        messagebox.showinfo("موفقیت", "فارسی‌سازی بازی، اصلاح چسبندگی حروف و تعویض فونت‌ها با موفقیت روی سیستم شما انجام شد.")
        self.btn_start.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = Victoria3TranslatorApp(root)
    root.mainloop()
