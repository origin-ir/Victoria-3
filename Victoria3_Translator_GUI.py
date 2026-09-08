import os
import re
import glob
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from deep_translator import GoogleTranslator
import arabic_reshaper
from bidi.algorithm import get_display

# تنظیمات ظاهری برنامه
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class TranslatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Victoria 3 Persian Localization Tool")
        self.geometry("600x420")
        self.resizable(False, False)

        # متغیرها
        self.game_path = tk.StringVar()
        self.font_path = tk.StringVar()
        self.translator = GoogleTranslator(source='en', target='fa')

        self.create_widgets()

    def create_widgets(self):
        # عنوان
        title_label = ctk.CTkLabel(self, text="ابزار فارسی‌سازی خودکار Victoria 3", font=("Tahoma", 18, "bold"))
        title_label.pack(pady=15)

        # انتخاب پوشه بازی
        game_frame = ctk.CTkFrame(self)
        game_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(game_frame, text="پوشه اصلی بازی (Victoria 3):").pack(anchor="w", padx=10, pady=5)
        game_entry = ctk.CTkEntry(game_frame, textvariable=self.game_path, width=420)
        game_entry.pack(side="left", padx=10, pady=5)
        ctk.CTkButton(game_frame, text="انتخاب", width=80, command=self.browse_game_dir).pack(side="right", padx=10, pady=5)

        # انتخاب فایل فونت فارسی
        font_frame = ctk.CTkFrame(self)
        font_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(font_frame, text="فایل فونت فارسی (.ttf / .otf):").pack(anchor="w", padx=10, pady=5)
        font_entry = ctk.CTkEntry(font_frame, textvariable=self.font_path, width=420)
        font_entry.pack(side="left", padx=10, pady=5)
        ctk.CTkButton(font_frame, text="انتخاب", width=80, command=self.browse_font_file).pack(side="right", padx=10, pady=5)

        # نوار پیشرفت و وضعیت
        self.status_label = ctk.CTkLabel(self, text="آماده به کار...", font=("Tahoma", 12))
        self.status_label.pack(pady=5)

        self.progress = ctk.CTkProgressBar(self, width=540)
        self.progress.pack(pady=5)
        self.progress.set(0)

        # دکمه شروع
        self.start_btn = ctk.CTkButton(self, text="شروع عملیات فارسی‌سازی", font=("Tahoma", 14, "bold"), height=40, command=self.start_process_thread)
        self.start_btn.pack(pady=15)

    def browse_game_dir(self):
        path = filedialog.askdirectory(title="پوشه اصلی Victoria 3 را انتخاب کنید")
        if path:
            self.game_path.set(path)

    def browse_font_file(self):
        path = filedialog.askopenfilename(title="فایل فونت فارسی را انتخاب کنید", filetypes=[("Font Files", "*.ttf *.otf")])
        if path:
            self.font_path.set(path)

    def fix_rtl(self, text):
        if not text:
            return text
        reshaped_text = arabic_reshaper.reshape(text)
        return get_display(reshaped_text)

    def translate_text(self, text):
        text_stripped = text.strip()
        if not text or (text_stripped.startswith('[') and text_stripped.endswith(']')) or \
           (text_stripped.startswith('$') and text_stripped.endswith('$')):
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

    def start_process_thread(self):
        if not self.game_path.get() or not os.path.exists(self.game_path.get()):
            messagebox.showerror("خطا", "لطفاً مسیر معتبر پوشه بازی را انتخاب کنید.")
            return

        self.start_btn.configure(state="disabled")
        threading.Thread(target=self.process_translation, daemon=True).start()

    def process_translation(self):
        game_dir = self.game_path.get()
        font_file = self.font_path.get()

        loc_dir = os.path.join(game_dir, "game", "localization", "english")
        fonts_dir = os.path.join(game_dir, "game", "gui", "fonts")

        # ۱. جایگزینی فونت برای حل مشکل مربع شدن
        if font_file and os.path.exists(font_file) and os.path.exists(fonts_dir):
            self.status_label.configure(text="در حال اعمال فونت فارسی...")
            for target_font in glob.glob(os.path.join(fonts_dir, "*.ttf")):
                try:
                    shutil.copy(font_file, target_font)
                except Exception:
                    pass

        # ۲. اسکن و ترجمه فایل‌ها
        yml_files = glob.glob(f"{loc_dir}/**/*.yml", recursive=True)
        total_files = len(yml_files)

        if total_files == 0:
            messagebox.showerror("خطا", "فایل ترجمه‌ای در مسیر localization/english بازی پیدا نشد.")
            self.start_btn.configure(state="normal")
            return

        for idx, file_path in enumerate(yml_files):
            self.status_label.configure(text=f"در حال پردازش ({idx+1}/{total_files}): {os.path.basename(file_path)}")
            self.progress.set((idx + 1) / total_files)

            with open(file_path, 'r', encoding='utf-8-sig') as f:
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

        self.status_label.configure(text="عملیات با موفقیت پایان یافت!")
        messagebox.showinfo("موفقیت", "ترجمه، اتصال حروف فارسی و اصلاح فونت با موفقیت انجام شد.")
        self.start_btn.configure(state="normal")

if __name__ == "__main__":
    app = TranslatorApp()
    app.mainloop()
