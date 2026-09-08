import os
import re
import glob
import shutil
import threading
import urllib.request
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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

CACHE_FILE = "translation_cache.json"

class Victoria3TurboTranslator:
    def __init__(self, root):
        self.root = root
        self.root.title("Victoria 3 Turbo Localizer (Chunking Engine)")
        self.root.geometry("600x380")
        self.root.resizable(False, False)

        self.game_dir = tk.StringVar()
        self.font_path = tk.StringVar()
        self.translator = GoogleTranslator(source='en', target='fa')
        
        # بارگذاری حافظه کش از قبل ذخیره‌شده
        self.cache = self.load_cache()

        self.setup_ui()

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_cache(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def setup_ui(self):
        tk.Label(self.root, text="نرم‌افزار ترجمه توربو Victoria 3 (Block Engine)", font=("Tahoma", 13, "bold")).pack(pady=15)

        frame_game = tk.LabelFrame(self.root, text=" پوشه اصلی بازی ", font=("Tahoma", 10))
        frame_game.pack(fill="x", padx=15, pady=5)
        tk.Entry(frame_game, textvariable=self.game_dir, width=50).pack(side="left", padx=10, pady=10)
        tk.Button(frame_game, text="انتخاب پوشه", command=self.browse_game).pack(side="right", padx=10, pady=10)

        frame_font = tk.LabelFrame(self.root, text=" فایل فونت فارسی (اختیاری) ", font=("Tahoma", 10))
        frame_font.pack(fill="x", padx=15, pady=5)
        tk.Entry(frame_font, textvariable=self.font_path, width=50).pack(side="left", padx=10, pady=10)
        tk.Button(frame_font, text="انتخاب فونت", command=self.browse_font).pack(side="right", padx=10, pady=10)

        self.status_lbl = tk.Label(self.root, text=f"وضعیت: آماده به کار ({len(self.cache)} عبارت در کش موجود است)", font=("Tahoma", 9))
        self.status_lbl.pack(pady=5)

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=540, mode="determinate")
        self.progress.pack(pady=5)

        self.btn_start = tk.Button(self.root, text="شروع ترجمه با سرعت توربو", font=("Tahoma", 11, "bold"), bg="#2196F3", fg="white", command=self.start_thread)
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
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except Exception:
            return text

    def translate_blocks(self, text_list):
        """ادغام متون در پاراگراف‌های بزرگ برای ارسال یک‌باره به گوگل"""
        results = {}
        to_translate_texts = []
        
        # ۱. جداسازی مواردی که در کش هستند یا متغیر خالصند
        for text in text_list:
            text_str = text.strip()
            if not text or (text_str.startswith('[') and text_str.endswith(']')) or (text_str.startswith('$') and text_str.endswith('$')):
                results[text] = text
            elif text in self.cache:
                results[text] = self.cache[text]
            else:
                to_translate_texts.append(text)

        if not to_translate_texts:
            return results

        # ۲. گروه بندی متون تا حجم ۲۰۰۰ کاراکتر در هر درخواست
        chunks = []
        current_chunk = []
        current_length = 0

        for text in to_translate_texts:
            if current_length + len(text) > 2000:
                chunks.append(current_chunk)
                current_chunk = [text]
                current_length = len(text)
            else:
                current_chunk.append(text)
                current_length += len(text)
        if current_chunk:
            chunks.append(current_chunk)

        # ۳. ارسال بلوکی
        DELIMITER = " === "
        pattern = r'(\[[^\]]+\]|\$[^\$]+\$|#[a-zA-Z0-9_! ]+#!)'

        for chunk in chunks:
            protected_chunk = []
            chunk_placeholders = []

            for text in chunk:
                placeholders = []
                def replace_ph(match):
                    placeholders.append(match.group(0))
                    return f"__VAR_{len(placeholders)-1}__"

                protected = re.sub(pattern, replace_ph, text)
                protected_chunk.append(protected)
                chunk_placeholders.append(placeholders)

            # اتصال خطوط با جداکننده ویژه
            joined_text = DELIMITER.join(protected_chunk)

            try:
                translated_joined = self.translator.translate(joined_text)
                translated_split = translated_joined.split("===")
            except Exception:
                translated_split = protected_chunk

            # بازسازی متن‌ها و قرار دادن در کش
            for i, orig_text in enumerate(chunk):
                if i < len(translated_split):
                    trans_text = translated_split[i].strip()
                    placeholders = chunk_placeholders[i]
                    for ph_i, ph in enumerate(placeholders):
                        trans_text = trans_text.replace(f"__VAR_{ph_i}__", ph)
                    results[orig_text] = trans_text
                    self.cache[orig_text] = trans_text
                else:
                    results[orig_text] = orig_text

        self.save_cache()
        return results

    def process_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
        except Exception:
            return

        parsed_lines = []
        texts_to_translate = []

        for line in lines:
            match = re.match(r'^(\s*[a-zA-Z0-9_.\-]+:\d*\s*")([^"]*)("(.*))?$', line)
            if match:
                prefix = match.group(1)
                content = match.group(2)
                suffix = match.group(3) if match.group(3) else '"'
                
                parsed_lines.append((prefix, content, suffix))
                texts_to_translate.append(content)
            else:
                parsed_lines.append(line)

        if not texts_to_translate:
            return

        # ترجمه بلوکی عبارات فایل
        translated_map = self.translate_blocks(texts_to_translate)

        new_lines = []
        for item in parsed_lines:
            if isinstance(item, tuple):
                prefix, content, suffix = item
                trans_text = translated_map.get(content, content)
                fixed_rtl = self.fix_rtl(trans_text)
                new_lines.append(f"{prefix}{fixed_rtl}{suffix}\n")
            else:
                new_lines.append(item)

        with open(file_path, 'w', encoding='utf-8-sig') as f:
            f.writelines(new_lines)

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
            messagebox.showerror("خطا", "پوشه localization/english پیدا نشد.")
            self.btn_start.config(state="normal")
            return

        # ۱. اصلاح فونت
        self.status_lbl.config(text="وضعیت: در حال اعمال فونت فارسی...")
        font_source = self.font_path.get() if self.font_path.get() else os.path.join(os.getcwd(), "vazir.ttf")
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

        # ۲. پردازش توربو فایل‌ها
        yml_files = glob.glob(f"{loc_dir}/**/*.yml", recursive=True)
        total_files = len(yml_files)

        for idx, file_path in enumerate(yml_files):
            self.status_lbl.config(text=f"ترجمه توربو ({idx+1}/{total_files} فایل) | عبارات ذخیره‌شده: {len(self.cache)}")
            self.progress['value'] = ((idx + 1) / total_files) * 100
            self.process_file(file_path)

        self.status_lbl.config(text="وضعیت: عملیات با موفقیت پایان یافت!")
        messagebox.showinfo("موفقیت", "ترجمه، اصلاح فونت و چسبندگی حروف با موفقیت کامل شد.")
        self.btn_start.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = Victoria3TurboTranslator(root)
    root.mainloop()
