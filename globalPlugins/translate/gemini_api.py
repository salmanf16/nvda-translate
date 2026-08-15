# -*- coding: utf-8 -*-
import urllib.request
import json

def translate(text, target_lang, api_key, model="gemini-3.5-flash", timeout=5):
    if not api_key:
        raise ValueError("Gemini API key is missing.")
        
    model_id = model.replace("models/", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    system_instruction = (
        f"You are a professional translator. Translate the text to target language code '{target_lang}'. "
        "Return ONLY the translated text. Do not explain, do not add commentary. "
        "Keep formatting and placeholders like {0}, {1} exactly intact."
    )
    
    payload = {
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [{
            "parts": [{"text": text}]
        }],
        "generationConfig": {
            "temperature": 0.3
        }
    }
    
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
    
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
    return ""

def fetch_models(api_key):
    if not api_key:
        raise ValueError("Gemini API key is missing.")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models", [])
        
        filtered_models = []
        for m in models:
            name = m.get("name", "")
            methods = m.get("supportedGenerationMethods", [])
            # Only include models that support generateContent and contain "gemini"
            if "generateContent" in methods and "gemini" in name:
                model_id = name.replace("models/", "")
                # Exclude embedding or specialized non-translation models
                if not any(x in model_id for x in ("embedding", "aqa", "experimental")):
                    filtered_models.append(model_id)
                    
        # Sort in reverse order to show latest models first
        filtered_models.sort(reverse=True)
        return filtered_models
