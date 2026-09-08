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

class Victoria3IndexedTurboApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Victoria 3 Fast & Precise Localizer")
        self.root.geometry("600x380")
        self.root.resizable(False, False)

        self.game_dir = tk.StringVar()
        self.font_path = tk.StringVar()
        self.translator = GoogleTranslator(source='en', target='fa')
        
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
        tk.Label(self.root, text="نرم‌افزار ترجمه سریع و دقیق Victoria 3 (موتور ایندکس‌گذاری)", font=("Tahoma", 11, "bold")).pack(pady=12)

        frame_game = tk.LabelFrame(self.root, text=" پوشه اصلی بازی ", font=("Tahoma", 9))
        frame_game.pack(fill="x", padx=15, pady=4)
        tk.Entry(frame_game, textvariable=self.game_dir, width=50).pack(side="left", padx=8, pady=8)
        tk.Button(frame_game, text="انتخاب پوشه", command=self.browse_game).pack(side="right", padx=8, pady=8)

        frame_font = tk.LabelFrame(self.root, text=" فایل فونت فارسی (اختیاری) ", font=("Tahoma", 9))
        frame_font.pack(fill="x", padx=15, pady=4)
        tk.Entry(frame_font, textvariable=self.font_path, width=50).pack(side="left", padx=8, pady=8)
        tk.Button(frame_font, text="انتخاب فونت", command=self.browse_font).pack(side="right", padx=8, pady=8)

        self.status_lbl = tk.Label(self.root, text=f"وضعیت: آماده (عبارات حافظه: {len(self.cache)})", font=("Tahoma", 9))
        self.status_lbl.pack(pady=4)

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=540, mode="determinate")
        self.progress.pack(pady=4)

        self.btn_start = tk.Button(self.root, text="شروع ترجمه هوشمند و سریع", font=("Tahoma", 11, "bold"), bg="#4CAF50", fg="white", command=self.start_thread)
        self.btn_start.pack(pady=12)

    def browse_game(self):
        path = filedialog.askdirectory(title="پوشه اصلی بازی Victoria 3 را انتخاب کنید")
        if path:
            self.game_dir.set(path)

    def browse_font(self):
        path = filedialog.askopenfilename(title="انتخاب فونت فارسی", filetypes=[("Font Files", "*.ttf")])
        if path:
            self.font_path.set(path)

    def clean_corrupted_artifacts(self, text):
        if not text:
            return text
        text = re.sub(r'_\s*_\s*VAR\s*_\s*\d+\s*_\s*_', '', text, flags=re.IGNORECASE)
        text = re.sub(r'PH\s*\d+\s*PH', '', text, flags=re.IGNORECASE)
        text = re.sub(r'XYZ\s*\d+\s*XYZ', '', text, flags=re.IGNORECASE)
        text = re.sub(r'[a-zA-Z0-9+/=]{20,}', '', text)
        return re.sub(r'\s+', ' ', text).strip()

    def fix_rtl(self, text):
        if not text:
            return text
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except Exception:
            return text

    def translate_batch_indexed(self, text_list):
        """ترجمه بلوکی متون همراه با شناسه عددی خطوط جهت جلوگیری از جابه‌جایی متون"""
        results = {}
        to_translate = []

        # ۱. بررسی موارد موجود در کش یا متون بدون نیاز به ترجمه
        for original in text_list:
            cleaned = self.clean_corrupted_artifacts(original)
            if not cleaned or re.match(r'^\s*([a-zA-Z0-9_\-+#=@!\/.]+|\$[^\$]+\$|\[[^\]]+\])\s*$', cleaned):
                results[original] = cleaned
            elif cleaned in self.cache:
                results[original] = self.cache[cleaned]
            else:
                to_translate.append((original, cleaned))

        if not to_translate:
            return results

        # ۲. گروه‌بندی ۴۰ خطی متون
        CHUNK_SIZE = 40
        for i in range(0, len(to_translate), CHUNK_SIZE):
            chunk = to_translate[i:i + CHUNK_SIZE]
            
            payload_lines = []
            chunk_placeholders = []

            # ماسک کردن متغیرهای بازی با ساختار ایمن _V0_
            var_pattern = r'(\[[^\]]+\]|\$[^\$]+\$|#[a-zA-Z0-9_! ]+#?|@[a-zA-Z0-9_!]+!)'
            
            for idx, (orig, clean) in enumerate(chunk):
                placeholders = []
                def replace_var(match):
                    placeholders.append(match.group(0))
                    return f" _V{len(placeholders)-1}_ "

                protected = re.sub(var_pattern, replace_var, clean)
                chunk_placeholders.append(placeholders)
                payload_lines.append(f"[{idx}] {protected}")

            full_payload = "\n".join(payload_lines)

            try:
                translated_payload = self.translator.translate(full_payload)
            except Exception:
                translated_payload = full_payload

            # ۳. تفکیک هوشمند بر اساس شناسه‌های [idx]
            translated_lines = translated_payload.split("\n")
            parsed_map = {}

            for line in translated_lines:
                match = re.match(r'^\s*\[(\d+)\]\s*(.*)$', line)
                if match:
                    line_idx = int(match.group(1))
                    parsed_map[line_idx] = match.group(2).strip()

            # ۴. بازسازی نهایی متن‌ها
            for idx, (orig, clean) in enumerate(chunk):
                trans_text = parsed_map.get(idx, clean)
                placeholders = chunk_placeholders[idx]

                for p_idx, ph in enumerate(placeholders):
                    ph_regex = re.compile(rf'\s*_V{p_idx}_\s*', re.IGNORECASE)
                    trans_text = ph_regex.sub(ph, trans_text)

                results[orig] = trans_text
                self.cache[clean] = trans_text

        self.save_cache()
        return results

    def process_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
        except Exception:
            return

        parsed_items = []
        texts_to_translate = []

        for line in lines:
            match = re.match(r'^(\s*[a-zA-Z0-9_.\-]+:\d*\s*")([^"]*)("(.*))?$', line)
            if match:
                prefix, content, suffix = match.group(1), match.group(2), match.group(3) or '"'
                parsed_items.append((prefix, content, suffix))
                texts_to_translate.append(content)
            else:
                parsed_items.append(line)

        if not texts_to_translate:
            return

        translated_map = self.translate_batch_indexed(texts_to_translate)

        new_lines = []
        for item in parsed_items:
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
        self.status_lbl.config(text="وضعیت: در حال جاگذاری فونت فارسی...")
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

        # ۲. پردازش سریع و دقیق فایل‌ها
        yml_files = glob.glob(f"{loc_dir}/**/*.yml", recursive=True)
        total_files = len(yml_files)

        for idx, file_path in enumerate(yml_files):
            self.status_lbl.config(text=f"ترجمه هوشمند ({idx+1}/{total_files} فایل) | ذخیره: {len(self.cache)}")
            self.progress['value'] = ((idx + 1) / total_files) * 100
            self.process_file(file_path)

        self.save_cache()
        self.status_lbl.config(text="وضعیت: عملیات با موفقیت کامل شد!")
        messagebox.showinfo("موفقیت", "ترجمه و اعمال فونت با سرعت بالا و بدون تداخل کد انجام شد.")
        self.btn_start.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = Victoria3IndexedTurboApp(root)
    root.mainloop()
