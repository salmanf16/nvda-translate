# -*- coding: utf-8 -*-
import os
import re
import struct

SRC_DIR = r"d:\Translate\globalPlugins\translate"
PO_PATH = r"d:\Translate\locale\ar\LC_MESSAGES\nvda.po"
MO_PATH = r"d:\Translate\locale\ar\LC_MESSAGES\nvda.mo"

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
def write_po_file(po_path, translations):
    header_val = translations.get("", (
        "Project-Id-Version: translate 2026.1\n"
        "Report-Msgid-Bugs-To: \n"
        "POT-Creation-Date: 2026-05-20 00:00+0000\n"
        "PO-Revision-Date: 2026-05-20 00:00+0000\n"
        "Last-Translator: Translate Addon\n"
        "Language-Team: \n"
        "Language: ar\n"
        "MIME-Version: 1.0\n"
        "Content-Type: text/plain; charset=UTF-8\n"
        "Content-Transfer-Encoding: 8bit\n"
    ))
    
    def escape_string(s):
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')

    with open(po_path, "w", encoding="utf-8") as f:
        # Write comments
        f.write('# NVDA Translate Addon - ar\n')
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
def compile_po_to_mo(po_path, mo_path):
    translations = parse_po_file(po_path)
    if not translations:
        print("No translations to compile!")
        return False
        
    # Ensure empty key (header) is in translations
    if "" not in translations:
        translations[""] = (
            "Project-Id-Version: translate 2026.1\n"
            "Report-Msgid-Bugs-To: \n"
            "POT-Creation-Date: 2026-05-20 00:00+0000\n"
            "PO-Revision-Date: 2026-05-20 00:00+0000\n"
            "Last-Translator: Translate Addon\n"
            "Language-Team: \n"
            "Language: ar\n"
            "MIME-Version: 1.0\n"
            "Content-Type: text/plain; charset=UTF-8\n"
            "Content-Transfer-Encoding: 8bit\n"
        )
        
    # Sort keys excluding the empty string (header). The empty string must always be first.
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
        current_offset += len(k_bytes) + 1 # +1 for null terminator
        
    trans_table = []
    for v_bytes in val_data:
        trans_table.append((len(v_bytes), current_offset))
        current_offset += len(v_bytes) + 1 # +1 for null terminator
        
    with open(mo_path, "wb") as f:
        # Header
        f.write(struct.pack("<Iiiiiii", 
            0x950412de, # Magic
            0,          # Revision
            num_strings,# Number of strings
            orig_table_offset,
            trans_table_offset,
            0, 0        # Hash table size & offset
        ))
        
        # Write original strings table (length, offset)
        for length, offset in orig_table:
            f.write(struct.pack("<ii", length, offset))
            
        # Write translation strings table (length, offset)
        for length, offset in trans_table:
            f.write(struct.pack("<ii", length, offset))
            
        # Write original strings content (null-terminated)
        for k_bytes in key_data:
            f.write(k_bytes + b"\x00")
            
        # Write translation strings content (null-terminated)
        for v_bytes in val_data:
            f.write(v_bytes + b"\x00")
            
    print(f"Successfully compiled {po_path} to binary format {mo_path}!")
    return True

def main():
    print("--- Translation Checker & Compiler ---")
    code_strings = extract_translatable_strings(SRC_DIR)
    po_translations = parse_po_file(PO_PATH)
    
    print(f"Extracted {len(code_strings)} translatable strings from Python code.")
    po_strings_count = len([k for k in po_translations.keys() if k != ""])
    print(f"Found {po_strings_count} translation strings in {PO_PATH}.")
    
    # Find missing strings in PO
    missing = code_strings - set(po_translations.keys())
    # Find obsolete strings in PO (present in PO but not in code, ignoring header)
    obsolete = set(po_translations.keys()) - code_strings - {""}
    
    print(f"\nMissing translations in PO ({len(missing)}):")
    for m in sorted(missing):
        print(f"  - {repr(m)}")
        
    print(f"\nObsolete/Unused translations in PO ({len(obsolete)}):")
    for o in sorted(obsolete):
        print(f"  - {repr(o)}")
        
    # Perform cleanup: remove obsolete and add missing
    cleaned_translations = {}
    for k, v in po_translations.items():
        if k in code_strings or k == "":
            cleaned_translations[k] = v
            
    # Add missing keys
    for k in missing:
        cleaned_translations[k] = ""
        
    print(f"\nCleaning PO file... Writing to {PO_PATH}")
    write_po_file(PO_PATH, cleaned_translations)
    
    # Compile
    compile_po_to_mo(PO_PATH, MO_PATH)

if __name__ == "__main__":
    main()
