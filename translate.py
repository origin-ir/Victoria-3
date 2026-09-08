import os
import sys
import subprocess

# نصب خودکار پیش‌نیازها در صورت عدم وجود
def install_requirements():
    required_packages = ['deep-translator', 'arabic-reshaper', 'python-bidi', 'requests']
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_requirements()

import re
import glob
import zipfile
import urllib.request
from deep_translator import GoogleTranslator
import arabic_reshaper
from bidi.algorithm import get_display

# تنظیمات مترجم
translator = GoogleTranslator(source='en', target='fa')

def fix_rtl(text):
    """اصلاح چسبندگی حروف و راست‌به‌چپ کردن جهت متن برای موتور بازی"""
    if not text:
        return text
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

def is_game_variable(text):
    """بررسی متغیرهای ویژه بازی برای عدم ترجمه"""
    text = text.strip()
    if (text.startswith('[') and text.endswith(']')) or \
       (text.startswith('$') and text.endswith('$')) or \
       (text.startswith('#') and text.endswith('#!')):
        return True
    return False

def translate_text(text):
    """ترجمه متن با حفظ متغیرها و کدهای فرمت‌بندی"""
    if not text or is_game_variable(text):
        return text

    pattern = r'(\[[^\]]+\]|\$[^\$]+\$|#[a-zA-Z0-9_! ]+#!)'
    placeholders = []
    
    def replace_with_placeholder(match):
        placeholders.append(match.group(0))
        return f"__VAR_{len(placeholders)-1}__"

    protected_text = re.sub(pattern, replace_with_placeholder, text)

    try:
        translated = translator.translate(protected_text)
        for i, ph in enumerate(placeholders):
            translated = translated.replace(f"__VAR_{i}__", ph)
        return translated
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def process_yml_file(input_file, output_file):
    """پردازش، ترجمه و اصلاح خطوط فایل YML"""
    print(f"Processing: {input_file}")
    try:
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
    except Exception:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        match = re.match(r'^(\s*[a-zA-Z0-9_.\-]+:\d*\s*")([^"]*)("(.*))?$', line)
        if match:
            prefix = match.group(1)
            content = match.group(2)
            suffix = match.group(3) if match.group(3) else '"'

            if "l_english:" in line:
                new_lines.append("l_english:\n")
                continue

            translated_content = translate_text(content)
            fixed_rtl_content = fix_rtl(translated_content)
            new_lines.append(f"{prefix}{fixed_rtl_content}{suffix}\n")
        else:
            new_lines.append(line)

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8-sig') as f:
        f.writelines(new_lines)

def main():
    # ۱. دانلود خودکار یک فونت فارسی استاندارد (Vazirmatn) برای حل مشکل مربع شدن
    font_url = "https://github.com/rastikerdar/vazirmatn/releases/download/v33.003/Vazirmatn-Regular.ttf"
    fonts_output_dir = "./fa_files/gui/fonts"
    os.makedirs(fonts_output_dir, exist_ok=True)
    font_path = os.path.join(fonts_output_dir, "MapFont.ttf") # جایگزینی مستقیم روی فونت نقشه/رابط اصلی
    
    print("Downloading Farsi Font...")
    try:
        urllib.request.urlretrieve(font_url, font_path)
    except Exception as e:
        print(f"Could not download font: {e}")

    # ۲. اسکن و ترجمه فایل‌های ورودی
    input_dir = "./en_files"
    output_dir = "./fa_files/localization/english"
    
    yml_files = glob.glob(f"{input_dir}/**/*.yml", recursive=True)
    if not yml_files:
        print("No YML files found in ./en_files directory!")
        return

    for file_path in yml_files:
        rel_path = os.path.relpath(file_path, input_dir)
        out_path = os.path.join(output_dir, rel_path)
        process_yml_file(file_path, out_path)

if __name__ == "__main__":
    main()
