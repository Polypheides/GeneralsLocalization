import os
import json
import re
import sys

# Format specifiers shared with the main pipeline
format_specifiers = [
    "%u", "%c", "%s", "%S", "%ls", "%hs", "%.0f%%", "%d", "%dms", "%d%%", "%d:0%d",
    "%d.%02d", "%d:%2.2d", "%d.%02d.%d", "%d:%02d:%02d", "\\n"
]

format_regex = re.compile(r'(' + '|'.join(map(re.escape, format_specifiers)) + r')')

def apply_format_specifiers(text):
    """ Apply curly braces around format specifiers in the text """
    text = re.sub(r'&(\w)', r'{&\1}', text) 
    text = format_regex.sub(r'{\1}', text)
    return text

def update_python_list(filepath, list_name, new_item):
    """ Programmatically add a new item to a list in a Python file """
    if not os.path.exists(filepath):
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple regex to find the list definition
    pattern = rf'({list_name}\s*=\s*\[)(.*?)(\])'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        prefix, existing_items, suffix = match.groups()
        
        # Clean up existing items to check for duplicates
        clean_items = [item.strip().strip("'").strip('"') for item in existing_items.split(',')]
        
        if new_item.upper() not in [i.upper() for i in clean_items]:
            print(f"Registering '{new_item}' in {os.path.basename(filepath)}...")
            # Append the new item with correct formatting
            if existing_items.strip() and not existing_items.strip().endswith(','):
                new_content = content[:match.start(2)] + existing_items + f", '{new_item}'" + content[match.end(2):]
            else:
                new_content = content[:match.start(2)] + existing_items + f"'{new_item}'" + content[match.end(2):]
                
            with open(filepath, 'w', encoding='utf-16' if 'utf-16' in content else 'utf-8') as f:
                f.write(new_content)

def update_inlang_settings(new_tag):
    """ Add a new language tag to project.inlang/settings.json """
    settings_path = os.path.join("project.inlang", "settings.json")
    if not os.path.exists(settings_path):
        return
        
    with open(settings_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Map to the tag used in Fink (e.g. SV -> sv, US -> en)
    tag_map = { 'US': 'en', 'BP': 'pt-BR' }
    target_tag = tag_map.get(new_tag.upper(), new_tag.lower())
    
    if target_tag not in data.get("languageTags", []):
        print(f"Registering '{target_tag}' in Inlang settings...")
        data["languageTags"].append(target_tag)
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

def register_new_language(lang_code):
    """ Ensure the new language is added to all configuration files """
    lang_code = lang_code.upper()
    update_python_list("str2json.py", "language_codes", lang_code)
    update_python_list("json2str.py", "language_codes", lang_code)
    update_inlang_settings(lang_code)

def parse_external_str(input_file, target_lang):
    """ Extract only the target language from the external .str file """
    target_lang = target_lang.upper()
    extracted_translations = {}

    if not os.path.exists(input_file):
        print(f"Error: External file '{input_file}' not found.")
        return None

    # Try different encodings
    for encoding in ['utf-8', 'utf-16', 'windows-1252']:
        try:
            with open(input_file, 'r', encoding=encoding) as file:
                current_label = None
                for line in file:
                    if not line.startswith('// context:'):
                        line = line.split('//')[0].strip()
                    else:
                        line = line.strip()

                    if not line:
                        continue

                    if ':' in line and not any(c in line for c in [' ', '"']):
                        current_label = line.strip()
                    elif current_label:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            lang_code, text = parts
                            lang_code = lang_code.strip().upper()
                            
                            if lang_code == target_lang:
                                text = text.strip()
                                if text.startswith('"') and text.endswith('"'):
                                    text = text[1:-1]
                                
                                text = apply_format_specifiers(text)
                                extracted_translations[current_label] = text

                    if line.strip() == "END":
                        current_label = None
                return extracted_translations
        except (UnicodeError, UnicodeDecodeError):
            continue
    return None

def import_language(source_str, target_lang, localization_folder):
    print(f"--- Starting Auto-Import for {target_lang} ---")
    
    register_new_language('CONTEXT')
    
    # 1. Parse the source
    new_data = parse_external_str(source_str, target_lang)
    if not new_data:
        print(f"No translations found for language: {target_lang}")
        return

    # 2. Map to the project's filename (e.g., US -> en, SV -> sv)
    filename_map = { 'US': 'en', 'BP': 'pt-br' }
    file_key = filename_map.get(target_lang.upper(), target_lang.lower())
    json_path = os.path.join(localization_folder, f"{file_key}.json")

    # 3. Handle merging
    existing_data = {}
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
    else:
        print(f"Creating new file: {json_path}")

    count_updated = 0
    count_new = 0
    
    for label, text in new_data.items():
        if label in existing_data:
            existing_data[label] = text
            count_updated += 1
        else:
            existing_data[label] = text
            count_new += 1

    # 4. Save updated JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)

    print(f"Successfully sync'd {target_lang}. Updated: {count_updated}, Added: {count_new}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python import_lang.py <source.str> <LANG_CODE>")
    else:
        source_file = sys.argv[1]
        language = sys.argv[2]
        import_language(source_file, language, "localization")
