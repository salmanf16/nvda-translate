# -*- coding: utf-8 -*-
import urllib.request
import urllib.parse
import json

def translate(text, target_lang, api_key, region=""):
    if not api_key:
        raise ValueError("Microsoft/Bing Translator API key is missing.")
        
    url = f"https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&to={urllib.parse.quote(target_lang.lower())}"
    
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    if region and region.strip():
        headers["Ocp-Apim-Subscription-Region"] = region.strip()
        
    payload = [{"text": text}]
    
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
    
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if data and isinstance(data, list) and len(data) > 0:
            translations = data[0].get("translations", [])
            if translations:
                return translations[0].get("text", "")
    return ""
