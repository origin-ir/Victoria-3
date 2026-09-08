import os
import re
import glob
from deep_translator import GoogleTranslator

# تنظیمات اولیه مترجم
translator = GoogleTranslator(source='en', target='fa')

def is_game_variable(text):
    """بررسی اینکه آیا تمام متن یک متغیر است یا خیر"""
    text = text.strip()
    if (text.startswith('[') and text.endswith(']')) or \
       (text.startswith('$') and text.endswith('$')) or \
       (text.startswith('#') and text.endswith('#!')):
        return True
    return False

def translate_text(text):
    """ترجمه متن با حفظ متغیرها و کدهای فرمت‌بندی بازی"""
    if not text or is_game_variable(text):
        return text

    # استخراج و جایگزینی موقت متغیرهای درون متنی برای جلوگیری از خرابی آن‌ها در ترجمه
    pattern = r'(\[[^\]]+\]|\$[^\$]+\$|#[a-zA-Z0-9_! ]+#!)'
    placeholders = []
    
    def replace_with_placeholder(match):
        placeholders.append(match.group(0))
        return f"__VAR_{len(placeholders)-1}__"

    protected_text = re.sub(pattern, replace_with_placeholder, text)

    try:
        translated = translator.translate(protected_text)
        # بازگرداندن متغیرها به حالت اولیه
        for i, ph in enumerate(placeholders):
            translated = translated.replace(f"__VAR_{i}__", ph)
        return translated
    except Exception as e:
        print(f"Error translating line: {e}")
        return text

def process_yml_file(input_file, output_file):
    """پردازش و ترجمه خط به خط فایل YML بازی"""
    print(f"Processing: {input_file}")
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        # شناسایی خطوط کلید:ارزش در فرمت موتور Paradox (l_english)
        match = re.match(r'^(\s*[a-zA-Z0-9_.\-]+:\d*\s*")([^"]*)("(.*))?$', line)
        if match:
            prefix = match.group(1)
            content = match.group(2)
            suffix = match.group(3) if match.group(3) else '"'
            
            # تغییر کلید اصلی زبانی اگر l_english باشد
            if "l_english:" in line:
                new_lines.append("l_english:\n") # یا l_persian بر اساس ساختار مود
                continue

            translated_content = translate_text(content)
            new_lines.append(f"{prefix}{translated_content}{suffix}\n")
        else:
            new_lines.append(line)

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8-sig') as f:
        f.writelines(new_lines)

def main():
    input_dir = "./en_files"
    output_dir = "./fa_files"
    
    yml_files = glob.glob(f"{input_dir}/**/*.yml", recursive=True)
    for file_path in yml_files:
        rel_path = os.path.relpath(file_path, input_dir)
        out_path = os.path.join(output_dir, rel_path)
        process_yml_file(file_path, out_path)

if __name__ == "__main__":
    main()
