import os
import re
import glob
import shutil
import threading
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from concurrent.futures import ThreadPoolExecutor

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

CACHE_FILE = "victoria_clean_cache.json"

class Victoria3EngineTranslator:
    def __init__(self, root):
        self.root = root
        self.root.title("Victoria 3 Clausewitz Safe Localizer")
        self.root.geometry("620x380")
        self.root.resizable(False, False)

        self.game_dir = tk.StringVar()
        self.translator = GoogleTranslator(source='es', target='fa')
        
        self.cache_lock = threading.Lock()
        self.cache = self.load_cache()
        
        # پترن دقیق شناسایی کدهای متغیری موتور بازی
        self.code_pattern = re.compile(
            r'(\[[^\]]+\]'                 # کدهای براکتی [GetPlayer.GetName]
            r'|\$[^\$]+\$'                 # متغیرهای $NAME$
            r'|#[a-zA-Z0-9_]+\s*'          # رنگ کلمات
            r'|#!'                         # ریست رنگ
            r'|@[a-zA-Z0-9_\-\.]+\!?'      # آیکون‌ها
            r'|\\n|\\t'                    # خط بعد و تب
            r')'
        )
        
        self.setup_ui()

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_cache(self):
        with self.cache_lock:
            try:
                with open(CACHE_FILE, "w", encoding="utf-8-sig") as f:
                    json.dump(self.cache, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def setup_ui(self):
        tk.Label(self.root, text="مترجم و ترمیم‌کننده موتور Victoria 3", font=("Tahoma", 11, "bold")).pack(pady=15)

        frame = tk.LabelFrame(self.root, text=" مسیر پوشه اصلی بازی ", font=("Tahoma", 9))
        frame.pack(fill="x", padx=15, pady=10)
        tk.Entry(frame, textvariable=self.game_dir, width=50).pack(side="left", padx=8, pady=10)
        tk.Button(frame, text="انتخاب", command=self.browse_game).pack(side="right", padx=8, pady=10)

        self.status_lbl = tk.Label(self.root, text="وضعیت: آماده", font=("Tahoma", 9))
        self.status_lbl.pack(pady=5)

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=560, mode="determinate")
        self.progress.pack(pady=10)

        self.btn_start = tk.Button(self.root, text="شروع ترمیم و ترجمه سالم", font=("Tahoma", 10, "bold"), bg="#2196F3", fg="white", command=self.start_thread)
        self.btn_start.pack(pady=15)

    def browse_game(self):
        path = filedialog.askdirectory(title="پوشه اصلی Victoria 3")
        if path:
            self.game_dir.set(path)

    def process_text(self, text):
        if not text or text.isspace():
            return text

        with self.cache_lock:
            if text in self.cache:
                return self.cache[text]

        tags = {}
        counter = 0

        def protect(match):
            nonlocal counter
            tag = f" XTAG{counter}X "
            tags[f"XTAG{counter}X"] = match.group(0)
            counter += 1
            return tag

        masked = self.code_pattern.sub(protect, text)

        if masked.strip():
            try:
                translated = self.translator.translate(masked)
            except Exception:
                translated = masked
        else:
            translated = masked

        # شکل‌دهی و راست‌چین کردن حروف فارسی
        try:
            reshaped = arabic_reshaper.reshape(translated)
            bidi_text = get_display(reshaped)
        except Exception:
            bidi_text = translated

        # بازگرداندن کدهای اصلی بازی
        for tag, original in tags.items():
            bidi_text = re.sub(rf'\s*{tag}\s*', original, bidi_text)

        bidi_text = bidi_text.replace('"', '\\"')

        with self.cache_lock:
            self.cache[text] = bidi_text

        return bidi_text

    def process_yml_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
        except Exception:
            return

        output_lines = []
        for line in lines:
            # بررسی هدر زبان
            if line.strip().startswith("l_spanish:"):
                output_lines.append("l_english:\n")
                continue

            # استخراج کلید و متن بدون دستکاری فاصله یا ساختار کلید
            match = re.match(r'^(\s*[\w\.\-]+:\d*\s*)"(.*)"(\s*)$', line)
            if match:
                key_part = match.group(1)
                content = match.group(2)
                suffix = match.group(3)

                translated_content = self.process_text(content)
                output_lines.append(f'{key_part}"{translated_content}"{suffix}\n')
            else:
                output_lines.append(line)

        # ذخیره با UTF-8 BOM جهت شناسه موتور کلوزویتس
        try:
            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.writelines(output_lines)
        except Exception:
            pass

    def start_thread(self):
        if not self.game_dir.get() or not os.path.exists(self.game_dir.get()):
            messagebox.showerror("خطا", "مسیر بازی معتبر نیست.")
            return

        self.btn_start.config(state="disabled")
        threading.Thread(target=self.run_process, daemon=True).start()

    def run_process(self):
        base = self.game_dir.get()
        spanish_dir = os.path.join(base, "game", "localization", "spanish")
        english_dir = os.path.join(base, "game", "localization", "english")

        if not os.path.exists(spanish_dir):
            messagebox.showerror("خطا", "پوشه spanish یافت نشد.")
            self.btn_start.config(state="normal")
            return

        self.status_lbl.config(text="بازسازی پوشه english از منبع سالم...")
        if os.path.exists(english_dir):
            shutil.rmtree(english_dir)
        shutil.copytree(spanish_dir, english_dir)

        files = glob.glob(f"{english_dir}/**/*.yml", recursive=True)
        total = len(files)

        with ThreadPoolExecutor(max_workers=6) as executor:
            for idx, _ in enumerate(executor.map(self.process_yml_file, files)):
                self.status_lbl.config(text=f"پردازش فایل‌ها: {idx+1}/{total}")
                self.progress['value'] = ((idx + 1) / total) * 100
                if idx % 10 == 0:
                    self.save_cache()

        self.save_cache()
        self.status_lbl.config(text="عملیات تمام شد!")
        messagebox.showinfo("موفقیت", "فایل‌های ترجمه به‌طور کامل بازسازی و اصلاح شدند.")
        self.btn_start.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = Victoria3EngineTranslator(root)
    root.mainloop()
