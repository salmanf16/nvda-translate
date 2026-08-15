# -*- coding: utf-8 -*-
import urllib.request
import json

def translate(text, target_lang, api_key, timeout=5):
    if not api_key:
        raise ValueError("DeepL API key is missing.")
        
    # Convert language code to uppercase as required by DeepL
    lang = target_lang.upper()
    if lang == "EN":
        lang = "EN-US"
    elif lang == "PT":
        lang = "PT-BR"
        
    # Auto-detect free vs pro API endpoint
    url = "https://api.deepl.com/v2/translate"
    if api_key.endswith(":fx"):
        url = "https://api-free.deepl.com/v2/translate"
        
    headers = {
        "Authorization": f"DeepL-Auth-Key {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    payload = {
        "text": [text],
        "target_lang": lang
    }
    
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
    
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        translations = data.get("translations", [])
        if translations:
            return translations[0].get("text", "")
    return ""
