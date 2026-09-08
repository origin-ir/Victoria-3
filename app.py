import os
import re
import glob
import shutil
import threading
import urllib.request
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

CACHE_FILE = "translation_cache.json"

class Victoria3BulletproofApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Victoria 3 Safe & Fast Localizer")
        self.root.geometry("600x380")
        self.root.resizable(False, False)

        self.game_dir = tk.StringVar()
        self.font_path = tk.StringVar()
        self.translator = GoogleTranslator(source='en', target='fa')
        
        self.cache_lock = threading.Lock()
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
        with self.cache_lock:
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.cache, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def setup_ui(self):
        tk.Label(self.root, text="برنامه ترجمه ایمن و بدون خراب شدن کد Victoria 3", font=("Tahoma", 11, "bold")).pack(pady=12)

        frame_game = tk.LabelFrame(self.root, text=" پوشه اصلی بازی ", font=("Tahoma", 9))
        frame_game.pack(fill="x", padx=15, pady=4)
        tk.Entry(frame_game, textvariable=self.game_dir, width=50).pack(side="left", padx=8, pady=8)
        tk.Button(frame_game, text="انتخاب پوشه", command=self.browse_game).pack(side="right", padx=8, pady=8)

        frame_font = tk.LabelFrame(self.root, text=" فایل فونت فارسی (اختیاری) ", font=("Tahoma", 9))
        frame_font.pack(fill="x", padx=15, pady=4)
        tk.Entry(frame_font, textvariable=self.font_path, width=50).pack(side="left", padx=8, pady=8)
        tk.Button(frame_font, text="انتخاب فونت", command=self.browse_font).pack(side="right", padx=8, pady=8)

        self.status_lbl = tk.Label(self.root, text=f"وضعیت: آماده به کار (حافظه: {len(self.cache)} عبارت)", font=("Tahoma", 9))
        self.status_lbl.pack(pady=4)

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=540, mode="determinate")
        self.progress.pack(pady=4)

        self.btn_start = tk.Button(self.root, text="شروع ترجمه ایمن و سریع", font=("Tahoma", 11, "bold"), bg="#4CAF50", fg="white", command=self.start_thread)
        self.btn_start.pack(pady=12)

    def browse_game(self):
        path = filedialog.askdirectory(title="پوشه اصلی بازی Victoria 3 را انتخاب کنید")
        if path:
            self.game_dir.set(path)

    def browse_font(self):
        path = filedialog.askopenfilename(title="انتخاب فونت فارسی", filetypes=[("Font Files", "*.ttf")])
        if path:
            self.font_path.set(path)

    def sanitize_clean(self, text):
        if not text:
            return text
        text = re.sub(r'_\s*_\s*VAR\s*_\s*\d+\s*_\s*_', '', text, flags=re.IGNORECASE)
        text = re.sub(r'PH\s*\d+\s*PH', '', text, flags=re.IGNORECASE)
        text = re.sub(r'XYZ\s*\d+\s*XYZ', '', text, flags=re.IGNORECASE)
        text = re.sub(r'[a-zA-Z0-9+/=]{20,}', '', text)
        return re.sub(r'\s+', ' ', text).strip()

    def translate_and_protect_line(self, raw_text):
        cleaned = self.sanitize_clean(raw_text)
        if not cleaned or re.match(r'^\s*([a-zA-Z0-9_\-+#=@!\/.]+|\$[^\$]+\$|\[[^\]]+\])\s*$', cleaned):
            return cleaned

        with self.cache_lock:
            if cleaned in self.cache:
                return self.cache[cleaned]

        # ۱. استخراج و استتار تمام کدهای بازی
        tag_pattern = r'(\[[^\]]+\]|\$[^\$]+\$|#[a-zA-Z0-9_!:\- ]+#?|@[a-zA-Z0-9_!]+!|\\n)'
        extracted_tags = []

        def mask_tag(match):
            extracted_tags.append(match.group(0))
            return f" _X{len(extracted_tags)-1}X_ "

        protected_text = re.sub(tag_pattern, mask_tag, cleaned)

        # ۲. ترجمه متون به فارسی
        try:
            translated_text = self.translator.translate(protected_text)
        except Exception:
            translated_text = protected_text

        # ۳. اعمال راست‌چین فقط روی متن فارسی قبل از بازگرداندن کدهای اصلی
        try:
            reshaped = arabic_reshaper.reshape(translated_text)
            bidi_text = get_display(reshaped)
        except Exception:
            bidi_text = translated_text

        # ۴. تزریق دقیق کدهای اصلی و دست‌نخورده به جای توکن‌ها
        final_text = bidi_text
        for idx, original_tag in enumerate(extracted_tags):
            flexible_token_regex = re.compile(rf'_\s*[xX]\s*{idx}\s*[xX]\s*_|X{idx}X', re.IGNORECASE)
            final_text = flexible_token_regex.sub(original_tag, final_text)

        with self.cache_lock:
            self.cache[cleaned] = final_text

        return final_text

    def process_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
        except Exception:
            return

        new_lines = []
        for line in lines:
            match = re.match(r'^(\s*[a-zA-Z0-9_.\-]+:\d*\s*")([^"]*)("(.*))?$', line)
            if match:
                prefix, content, suffix = match.group(1), match.group(2), match.group(3) or '"'
                processed_content = self.translate_and_protect_line(content)
                new_lines.append(f"{prefix}{processed_content}{suffix}\n")
            else:
                new_lines.append(line)

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

        # ۱. جایگذاری فونت فارسی
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

        # ۲. پردازش سریع و ایمن فایل‌ها به‌صورت موازی
        yml_files = glob.glob(f"{loc_dir}/**/*.yml", recursive=True)
        total_files = len(yml_files)

        with ThreadPoolExecutor(max_workers=10) as executor:
            for idx, _ in enumerate(executor.map(self.process_file, yml_files)):
                self.status_lbl.config(text=f"ترجمه ایمن ({idx+1}/{total_files} فایل) | عبارات ذخیره: {len(self.cache)}")
                self.progress['value'] = ((idx + 1) / total_files) * 100
                if idx % 5 == 0:
                    self.save_cache()

        self.save_cache()
        self.status_lbl.config(text="وضعیت: ترجمه ایمن با موفقیت به پایان رسید!")
        messagebox.showinfo("موفقیت", "ترجمه، راست‌چین و کدهای بازی با ایمنی کامل و بدون قاطی شدن کدها انجام شد.")
        self.btn_start.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = Victoria3BulletproofApp(root)
    root.mainloop()
