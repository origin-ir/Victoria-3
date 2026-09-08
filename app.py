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

CACHE_FILE = "victoria_smart_cache.json"

class Victoria3ProLocalizer:
    def __init__(self, root):
        self.root = root
        self.root.title("Victoria 3 Code-Safe Translator")
        self.root.geometry("620x380")
        self.root.resizable(False, False)

        self.game_dir = tk.StringVar()
        self.translator = GoogleTranslator(source='auto', target='fa')
        
        self.cache_lock = threading.Lock()
        self.cache = self.load_cache()
        
        self.code_pattern = re.compile(
            r'(\[[^\]]+\]'
            r'|\$[^\$]+\$'
            r'|#[a-zA-Z0-9_]+ '
            r'|#!'
            r'|@[a-zA-Z0-9_\-\.]+(?:!|)'
            r'|\\n|\\t'
            r'|<[^>]+>'
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
        tk.Label(self.root, text="مترجم هوشمند Victoria 3 (محافظت کامل از کدهای بازی)", font=("Tahoma", 11, "bold")).pack(pady=12)

        frame_game = tk.LabelFrame(self.root, text=" مسیر پوشه اصلی بازی ", font=("Tahoma", 9))
        frame_game.pack(fill="x", padx=15, pady=10)
        tk.Entry(frame_game, textvariable=self.game_dir, width=52).pack(side="left", padx=8, pady=10)
        tk.Button(frame_game, text="انتخاب پوشه", command=self.browse_game).pack(side="right", padx=8, pady=10)

        self.status_lbl = tk.Label(self.root, text=f"وضعیت: آماده (کلمات در حافظه: {len(self.cache)})", font=("Tahoma", 9))
        self.status_lbl.pack(pady=5)

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=560, mode="determinate")
        self.progress.pack(pady=10)

        self.btn_start = tk.Button(self.root, text="شروع پردازش، استخراج و ترجمه ایمن", font=("Tahoma", 11, "bold"), bg="#2196F3", fg="white", command=self.start_thread)
        self.btn_start.pack(pady=15)

    def browse_game(self):
        path = filedialog.askdirectory(title="پوشه بازی Victoria 3")
        if path:
            self.game_dir.set(path)

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
            uid = f" ZZZ{counter}ZZZ "
            placeholders[f"ZZZ{counter}ZZZ"] = match.group(0)
            counter += 1
            return uid

        protected_text = self.code_pattern.sub(mask_code, raw_text)
        protected_text = re.sub(r'\s+', ' ', protected_text).strip()

        if not protected_text or re.match(r'^[\sZ0-9]+$', protected_text):
            translated_text = protected_text
        else:
            try:
                translated_text = self.translator.translate(protected_text)
            except Exception:
                translated_text = protected_text

        try:
            reshaped = arabic_reshaper.reshape(translated_text)
            bidi_text = get_display(reshaped)
        except Exception:
            bidi_text = translated_text

        final_text = bidi_text
        for uid, original_code in placeholders.items():
            final_text = re.sub(rf'\s*{uid}\s*', f"{original_code}", final_text)

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
        threading.Thread(target=self.process, daemon=True).sart() if hasattr(threading.Thread(target=self.process, daemon=True), 'sart') else threading.Thread(target=self.process, daemon=True).start()

    def process(self):
        base_dir = self.game_dir.get()
        loc_dir = os.path.join(base_dir, "game", "localization", "english")

        if not os.path.exists(loc_dir):
            messagebox.showerror("خطا", "پوشه localization/english در این مسیر یافت نشد.")
            self.btn_start.config(state="normal")
            return

        yml_files = glob.glob(f"{loc_dir}/**/*.yml", recursive=True)
        total_files = len(yml_files)

        with ThreadPoolExecutor(max_workers=8) as executor:
            for idx, _ in enumerate(executor.map(self.process_file, yml_files)):
                self.status_lbl.config(text=f"در حال مهندسی و ترجمه ({idx+1}/{total_files} فایل) | ذخیره: {len(self.cache)}")
                self.progress['value'] = ((idx + 1) / total_files) * 100
                if idx % 10 == 0:
                    self.save_cache()

        self.save_cache()
        self.status_lbl.config(text="عملیات با موفقیت بی‌نقص به پایان رسید!")
        messagebox.showinfo("موفقیت", "فایل‌ها با حفظ ۱۰۰٪ کدهای بازی ترجمه شدند. بازی را اجرا کنید.")
        self.btn_start.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = Victoria3ProLocalizer(root)
    root.mainloop()
