# -*- coding: utf-8 -*-
import urllib.request
import json

def translate(text, target_lang, api_key, model="deepseek/deepseek-chat", timeout=5):
    if not api_key:
        raise ValueError("OpenRouter API key is missing.")
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/salmanf16/nvda-translate",
        "X-Title": "NVDA Translate",
        "User-Agent": "Mozilla/5.0"
    }
    
    system_prompt = (
        f"You are a professional translator. Translate the text to target language code '{target_lang}'. "
        "Return ONLY the translated text. Do not explain, do not add commentary. "
        "Keep formatting and placeholders like {0}, {1} exactly intact."
    )
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "temperature": 0.3
    }
    
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
    
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            return content.strip()
    return ""

def fetch_models(api_key):
    if not api_key:
        raise ValueError("OpenRouter API key is missing.")
        
    url = "https://openrouter.ai/api/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/salmanf16/nvda-translate",
        "X-Title": "NVDA Translate",
        "User-Agent": "Mozilla/5.0"
    }
    
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        models = data.get("data", [])
        
        filtered_models = []
        for m in models:
            mid = m.get("id", "")
            if not mid:
                continue
            # Filter out embedding, moderation, and image generation models
            if not any(x in mid.lower() for x in ("embedding", "moderation", "similarity", "text-to-image", "image")):
                filtered_models.append(mid)
                
        def sort_key(model_id):
            model_id_lower = model_id.lower()
            if model_id == "deepseek/deepseek-chat":
                return (0, model_id)
            elif "deepseek" in model_id_lower:
                return (1, model_id)
            elif "gemini" in model_id_lower:
                return (2, model_id)
            elif "claude" in model_id_lower:
                return (3, model_id)
            elif "gpt" in model_id_lower:
                return (4, model_id)
            elif "minimax" in model_id_lower:
                return (5, model_id)
            elif "llama" in model_id_lower:
                return (6, model_id)
            else:
                return (7, model_id)
                
        filtered_models.sort(key=sort_key)
        return filtered_models
