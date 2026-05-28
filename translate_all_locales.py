# -*- coding: utf-8 -*-
import os
import sys
import re
import time
import struct
import shutil
import socket

# Set default socket timeout to prevent network requests from hanging
socket.setdefaulttimeout(5.0)

# Add the plugin directory to sys.path so we can import mtranslate
cur_dir = os.path.dirname(os.path.abspath(__file__))
plugin_dir = os.path.join(cur_dir, "globalPlugins", "translate")
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

import mtranslate

SRC_DIR = os.path.join(cur_dir, "globalPlugins", "translate")
LOCALE_DIR = os.path.join(cur_dir, "locale")

# 1. Scan for all translatable strings in Python files
def extract_translatable_strings(directory):
    found_strings = set()
    double_quote_re = re.compile(r'_\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
    single_quote_re = re.compile(r"_\(\s*'((?:[^'\\]|\\.)*)'\s*\)")
    
    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith(".py"):
                continue
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Find all double quote matches
                for match in double_quote_re.finditer(content):
                    s = match.group(1)
                    s = s.replace(r'\"', '"').replace(r'\n', '\n').replace(r'\t', '\t')
                    found_strings.add(s)
                
                # Find all single quote matches
                for match in single_quote_re.finditer(content):
                    s = match.group(1)
                    s = s.replace(r"\'", "'").replace(r'\n', '\n').replace(r'\t', '\t')
                    found_strings.add(s)
            except Exception as e:
                print(f"Error reading {path}: {e}")
                
    return found_strings

# 2. Parse PO file
def parse_po_file(po_path):
    translations = {}
    if not os.path.exists(po_path):
        return translations
        
    with open(po_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    entries = re.split(r'\n\n+', content)
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
            
        msgid_match = re.search(r'msgid\s+(".*?(?<!\\)"(?:\s*".*?(?<!\\)")*)', entry, re.DOTALL)
        msgstr_match = re.search(r'msgstr\s+(".*?(?<!\\)"(?:\s*".*?(?<!\\)")*)', entry, re.DOTALL)
        
        if msgid_match and msgstr_match:
            def parse_quoted_block(block):
                lines = re.findall(r'"((?:[^"\\]|\\.)*)"', block)
                s = "".join(lines)
                s = s.replace(r'\"', '"').replace(r'\n', '\n').replace(r'\t', '\t').replace(r'\\', '\\')
                return s
                
            msgid = parse_quoted_block(msgid_match.group(1))
            msgstr = parse_quoted_block(msgstr_match.group(1))
            translations[msgid] = msgstr
                
    return translations

# 3. Write PO file
def write_po_file(po_path, translations, lang):
    header_val = translations.get("", (
        f"Project-Id-Version: translate 2026.1\n"
        "Report-Msgid-Bugs-To: \n"
        "POT-Creation-Date: 2026-05-22 00:00+0000\n"
        "PO-Revision-Date: 2026-05-22 00:00+0000\n"
        "Last-Translator: Translate Addon\n"
        "Language-Team: \n"
        f"Language: {lang}\n"
        "MIME-Version: 1.0\n"
        "Content-Type: text/plain; charset=UTF-8\n"
        "Content-Transfer-Encoding: 8bit\n"
    ))
    
    def escape_string(s):
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')

    with open(po_path, "w", encoding="utf-8") as f:
        # Write comments
        f.write(f'# NVDA Translate Addon - {lang}\n')
        f.write('# This file is distributed under the same license as the translate package.\n#\n')
        
        # Write header (msgid "")
        f.write('msgid ""\n')
        f.write('msgstr ""\n')
        for line in header_val.splitlines(keepends=True):
            f.write(f'"{escape_string(line)}"\n')
        f.write('\n')
        
        # Write other translations
        for msgid, msgstr in sorted(translations.items()):
            if msgid == "":
                continue
            f.write(f'msgid "{escape_string(msgid)}"\n')
            f.write(f'msgstr "{escape_string(msgstr)}"\n\n')

# 4. Compile PO to MO (binary format)
def compile_po_to_mo(po_path, mo_path, lang):
    translations = parse_po_file(po_path)
    if not translations:
        return False
        
    if "" not in translations:
        translations[""] = (
            f"Project-Id-Version: translate 2026.1\n"
            "Report-Msgid-Bugs-To: \n"
            "POT-Creation-Date: 2026-05-22 00:00+0000\n"
            "PO-Revision-Date: 2026-05-22 00:00+0000\n"
            "Last-Translator: Translate Addon\n"
            "Language-Team: \n"
            f"Language: {lang}\n"
            "MIME-Version: 1.0\n"
            "Content-Type: text/plain; charset=UTF-8\n"
            "Content-Transfer-Encoding: 8bit\n"
        )
        
    sorted_keys = sorted([k for k in translations.keys() if k != ""])
    all_keys = [""] + sorted_keys
    
    key_data = []
    val_data = []
    
    for k in all_keys:
        k_bytes = k.encode("utf-8")
        v_bytes = translations[k].encode("utf-8")
        key_data.append(k_bytes)
        val_data.append(v_bytes)
        
    num_strings = len(all_keys)
    
    orig_table_offset = 28
    trans_table_offset = orig_table_offset + 8 * num_strings
    strings_start_offset = trans_table_offset + 8 * num_strings
    
    current_offset = strings_start_offset
    orig_table = []
    for k_bytes in key_data:
        orig_table.append((len(k_bytes), current_offset))
        current_offset += len(k_bytes) + 1
        
    trans_table = []
    for v_bytes in val_data:
        trans_table.append((len(v_bytes), current_offset))
        current_offset += len(v_bytes) + 1
        
    with open(mo_path, "wb") as f:
        f.pack_data = struct.pack("<Iiiiiii", 
            0x950412de,
            0,
            num_strings,
            orig_table_offset,
            trans_table_offset,
            0, 0
        )
        f.write(f.pack_data)
        
        for length, offset in orig_table:
            f.write(struct.pack("<ii", length, offset))
            
        for length, offset in trans_table:
            f.write(struct.pack("<ii", length, offset))
            
        for k_bytes in key_data:
            f.write(k_bytes + b"\x00")
            
        for v_bytes in val_data:
            f.write(v_bytes + b"\x00")
            
    return True

def clean_and_translate_locales():
    print("--- Starting Full Localization Pipeline ---")
    code_strings = extract_translatable_strings(SRC_DIR)
    print(f"Extracted {len(code_strings)} translatable strings from code.")
    
    if not os.path.exists(LOCALE_DIR):
        print("Locale directory does not exist!")
        return
        
    langs = sorted([d for d in os.listdir(LOCALE_DIR) if os.path.isdir(os.path.join(LOCALE_DIR, d))])
    print(f"Found {len(langs)} language locales.")
    
    for idx, lang in enumerate(langs):
        po_dir = os.path.join(LOCALE_DIR, lang, "LC_MESSAGES")
        os.makedirs(po_dir, exist_ok=True)
        po_path = os.path.join(po_dir, "nvda.po")
        mo_path = os.path.join(po_dir, "nvda.mo")
        
        print(f"[{idx+1}/{len(langs)}] Processing locale '{lang}'...")
        
        # Load existing translations
        existing = parse_po_file(po_path)
        
        # Keep only code strings or header
        cleaned = {}
        for k, v in existing.items():
            if k in code_strings or k == "":
                cleaned[k] = v
                
        # Find missing strings
        missing = sorted(list(code_strings - set(cleaned.keys())))
        
        # Auto-translate missing strings using mtranslate
        if missing:
            print(f"  -> Found {len(missing)} missing translations for '{lang}'. Translating...")
            for s in missing:
                # Do not translate placeholders or special values that are obvious configuration/technical terms
                if s in ("google", "lingva", "libretranslate", "local", "auto", "cpu", "cuda", "speed", "balanced", "quality"):
                    cleaned[s] = s
                    continue
                try:
                    # Translate to target language code
                    translated = mtranslate.translate(s, lang, "en")
                    if translated and translated.strip() != s.strip():
                        # Unescape and normalize format parameters
                        translated = translated.replace("{ ", "{").replace(" }", "}")
                        cleaned[s] = translated
                        try:
                            print(f"     * '{s[:30]}...' -> '{translated[:30]}...'")
                        except Exception:
                            try:
                                print(f"     * '{s[:30]}...' -> [Translated successfully]")
                            except Exception:
                                pass
                    else:
                        cleaned[s] = ""
                except Exception as e:
                    try:
                        print(f"     ! Error translating '{s[:20]}': {e}")
                    except Exception:
                        pass
                    cleaned[s] = ""
                time.sleep(0.02) # Very light rate-limiting
                
        # Write PO file
        write_po_file(po_path, cleaned, lang)
        
        # Compile MO file
        compile_po_to_mo(po_path, mo_path, lang)
        
    print("--- Localization Pipeline Completed Successfully! ---")

if __name__ == "__main__":
    clean_and_translate_locales()
