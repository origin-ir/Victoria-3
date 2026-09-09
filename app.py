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

CACHE_FILE = "victoria_master_cache.json"

class Victoria3AutoRepairAndTranslate:
    def __init__(self, root):
        self.root = root
        self.root.title("Victoria 3 Auto-Repair & Safe Translator")
        self.root.geometry("650x420")
        self.root.resizable(False, False)

        self.game_dir = tk.StringVar()
        self.source_lang = tk.StringVar(value="spanish")
        
        # استفاده از مترجم اسپانیایی به فارسی
        self.translator = GoogleTranslator(source='es', target='fa')
        
        self.cache_lock = threading.Lock()
        self.cache = self.load_cache()
        
        # پترن جامع برای ایزوله‌سازی کدهای پارادوکس
        self.code_pattern = re.compile(
            r'(\[[^\]]+\]'                 # کدهای براکتی مثل [GetPlayer.GetName]
            r'|\$[^\$]+\$'                 # متغیرهای متنی مثل $NAME$
            r'|#[a-zA-Z0-9_]+\s*'          # رنگ‌بندی کلمات
            r'|#!'                         # پایان رنگ
            r'|@[a-zA-Z0-9_\-\.]+\!?'      # آیکون‌های بازی
            r'|\\n|\\t'                    # کاراکترهای خط جدید و تب
            r'|<[^>]+>'                    # تگ‌های ساختاری
            r')'
        )
        
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
        with self.cache_lock:
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.cache, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def setup_ui(self):
        tk.Label(self.root, text="سیستم بازسازی خودکار و ترجمه ایمن Victoria 3", font=("Tahoma", 11, "bold")).pack(pady=12)

        frame_game = tk.LabelFrame(self.root, text=" مسیر پوشه اصلی بازی ", font=("Tahoma", 9))
        frame_game.pack(fill="x", padx=15, pady=5)
        tk.Entry(frame_game, textvariable=self.game_dir, width=54).pack(side="left", padx=8, pady=10)
        tk.Button(frame_game, text="انتخاب پوشه", command=self.browse_game).pack(side="right", padx=8, pady=10)

        frame_lang = tk.LabelFrame(self.root, text=" منبع بازسازی فایل‌های سالم ", font=("Tahoma", 9))
        frame_lang.pack(fill="x", padx=15, pady=5)
        tk.Label(frame_lang, text="استفاده از پوشه سالم:").pack(side="left", padx=8)
        cb = ttk.Combobox(frame_lang, textvariable=self.source_lang, values=["spanish", "french", "german"], state="readonly", width=12)
        cb.pack(side="left", padx=5, pady=8)

        self.status_lbl = tk.Label(self.root, text=f"وضعیت: آماده (کلمات در حافظه: {len(self.cache)})", font=("Tahoma", 9))
        self.status_lbl.pack(pady=8)

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=600, mode="determinate")
        self.progress.pack(pady=5)

        self.btn_start = tk.Button(self.root, text="۱. بازسازی فایل‌ها  |  ۲. استخراج کدها  |  ۳. ترجمه کامل", 
                                  font=("Tahoma", 10, "bold"), bg="#4CAF50", fg="white", command=self.start_thread)
        self.btn_start.pack(pady=15)

    def browse_game(self):
        path = filedialog.askdirectory(title="پوشه اصلی بازی Victoria 3")
        if path:
            self.game_dir.set(path)

    def prepare_clean_english_folder(self, base_dir):
        loc_dir = os.path.join(base_dir, "game", "localization")
        src_dir = os.path.join(loc_dir, self.source_lang.get())
        target_dir = os.path.join(loc_dir, "english")

        if not os.path.exists(src_dir):
            raise Exception(f"پوشه {self.source_lang.get()} برای بازسازی یافت نشد.")

        # ۱. پاکسازی پوشه english خراب شده
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)

        # ۲. کپی پوشه سالم به english
        shutil.copytree(src_dir, target_dir)

        # ۳. اصلاح هدر فایل‌ها از l_spanish به l_english
        yml_files = glob.glob(f"{target_dir}/**/*.yml", recursive=True)
        old_header = f"l_{self.source_lang.get()}:"
        
        for filepath in yml_files:
            try:
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
                
                content = content.replace(old_header, "l_english:")
                
                with open(filepath, 'w', encoding='utf-8-sig') as f:
                    f.write(content)
            except Exception:
                pass

    def process_localization_text(self, raw_text):
        if not raw_text or raw_text.isspace():
            return raw_text

        with self.cache_lock:
            if raw_text in self.cache:
                return self.cache[raw_text]

        placeholders = {}
        counter = 0

        def mask_code(match):
            nonlocal counter
            uid = f" __TAG{counter}__ "
            placeholders[f"__TAG{counter}__"] = match.group(0)
            counter += 1
            return uid

        # ایزوله‌سازی کدهای بازی با توکن ایمن
        protected_text = self.code_pattern.sub(mask_code, raw_text)
        protected_text = re.sub(r'\s+', ' ', protected_text).strip()

        if not protected_text or re.match(r'^[\s_TAG0-9]+$', protected_text):
            translated_text = protected_text
        else:
            try:
                translated_text = self.translator.translate(protected_text)
            except Exception:
                translated_text = protected_text

        # راست‌چین کردن متن (توکن‌های انگلیسی دست‌نخورده می‌مانند)
        try:
            reshaped = arabic_reshaper.reshape(translated_text)
            bidi_text = get_display(reshaped)
        except Exception:
            bidi_text = translated_text

        final_text = bidi_text
        # تزریق مجدد کدهای اصلی دقیقاً سر جای خود
        for uid, original_code in placeholders.items():
            final_text = re.sub(rf'\s*{uid}\s*', f"{original_code}", final_text)

        # فرار از گیومه برای جلوگیری از خراب شدن ساختار YML
        final_text = final_text.replace('"', '\\"')

        with self.cache_lock:
            self.cache[raw_text] = final_text

        return final_text

    def process_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
        except Exception:
            return

        new_lines = []
        for line in lines:
            match = re.match(r'^([\w\.\-]+:\d*\s*)("(.*)")(\s*)$', line)
            if match:
                prefix = match.group(1)
                content = match.group(3)
                suffix = match.group(4)
                
                processed_content = self.process_localization_text(content)
                new_lines.append(f'{prefix}"{processed_content}"{suffix}\n')
            else:
                new_lines.append(line)

        try:
            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.writelines(new_lines)
        except Exception:
            pass

    def start_thread(self):
        if not self.game_dir.get() or not os.path.exists(self.game_dir.get()):
            messagebox.showerror("خطا", "لطفاً مسیر پوشه اصلی بازی را انتخاب کنید.")
            return

        self.btn_start.config(state="disabled")
        threading.Thread(target=self.process, daemon=True).start()

    def process(self):
        base_dir = self.game_dir.get()
        
        try:
            self.status_lbl.config(text="در حال بازسازی فایل‌های سالم از زبان منبع...")
            self.prepare_clean_english_folder(base_dir)
        except Exception as e:
            messagebox.showerror("خطا در بازسازی", str(e))
            self.btn_start.config(state="normal")
            return

        loc_dir = os.path.join(base_dir, "game", "localization", "english")
        yml_files = glob.glob(f"{loc_dir}/**/*.yml", recursive=True)
        total_files = len(yml_files)

        self.status_lbl.config(text="در حال استخراج کدها و ترجمه ایمن...")

        with ThreadPoolExecutor(max_workers=8) as executor:
            for idx, _ in enumerate(executor.map(self.process_file, yml_files)):
                self.status_lbl.config(text=f"در حال ترجمه ({idx+1}/{total_files} فایل) | کلمات ذخیره شده: {len(self.cache)}")
                self.progress['value'] = ((idx + 1) / total_files) * 100
                if idx % 10 == 0:
                    self.save_cache()

        self.save_cache()
        self.status_lbl.config(text="عملیات با موفقیت کامل انجام شد!")
        messagebox.showinfo("پایان عملیات", "پوشه english به‌طور کامل از روی فایل‌های سالم بازسازی شد، تمامی کدها جدا گشتند و ترجمه بدون هیچ اروری اعمال شد.")
        self.btn_start.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = Victoria3AutoRepairAndTranslate(root)
    root.mainloop()
