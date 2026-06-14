# -*- coding: utf-8 -*-
import urllib.request
import json

def translate(text, target_lang, api_key, model="gpt-5.4-mini"):
    if not api_key:
        raise ValueError("OpenAI API key is missing.")
        
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
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
    
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            return content.strip()
    return ""

def fetch_models(api_key):
    if not api_key:
        raise ValueError("OpenAI API key is missing.")
        
    url = "https://api.openai.com/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0"
    }
    
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        models = data.get("data", [])
        
        # Filter for text gpt models, exclude embedding, audio, realtime, instruct, and search models
        filtered_models = []
        for m in models:
            mid = m.get("id", "")
            if mid.startswith("gpt-") and not any(x in mid for x in ("realtime", "audio", "embedding", "instruct", "search", "vision")):
                filtered_models.append(mid)
                
        # Sort models so that higher versions (like gpt-5.x) appear first
        filtered_models.sort(reverse=True)
        return filtered_models
