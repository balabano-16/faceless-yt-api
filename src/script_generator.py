import httpx
import os
import json
import time
import hmac
import hashlib

WIRO_API_KEY = os.environ.get("WIRO_API_KEY", "")
WIRO_API_SECRET = os.environ.get("WIRO_API_SECRET", "")

def _make_headers() -> dict:
    nonce = str(int(time.time() * 1000))
    signature_raw = WIRO_API_SECRET + nonce
    signature = hmac.new(
        WIRO_API_KEY.encode(),
        signature_raw.encode(),
        hashlib.sha256
    ).hexdigest()
    return {
        "x-api-key": WIRO_API_KEY,
        "x-nonce": nonce,
        "x-signature": signature,
        "Content-Type": "application/json"
    }

async def generate_script(topic: str, sections: int = 5, language: str = "tr") -> dict:
    """
    Wiro üzerinden Gemini 3 Pro ile listicle script üretir.
    Dönen format:
    {
      "title": "...",
      "intro": {"text": "...", "image_prompt": "..."},
      "sections": [
        {"number": 1, "heading": "...", "text": "...", "image_prompt": "..."},
        ...
      ],
      "outro": {"text": "...", "image_prompt": "..."}
    }
    """
    lang_instruction = "Türkçe yaz." if language == "tr" else "Write in English."

    system_prompt = f"""Sen bir YouTube video script yazarısın. {lang_instruction}
Verilen konuya göre listicle formatında script üret.
SADECE JSON döndür, başka hiçbir şey yazma."""

    user_prompt = f"""Konu: {topic}
Bölüm sayısı: {sections}

Şu JSON formatında script üret:
{{
  "title": "video başlığı",
  "intro": {{
    "text": "30-40 kelimelik giriş metni",
    "image_prompt": "cinematic image prompt in English for intro visual"
  }},
  "sections": [
    {{
      "number": 1,
      "heading": "Bölüm başlığı",
      "text": "60-80 kelimelik bölüm metni",
      "image_prompt": "cinematic image prompt in English for this section"
    }}
  ],
  "outro": {{
    "text": "20-30 kelimelik kapanış metni",
    "image_prompt": "cinematic image prompt in English for outro visual"
  }}
}}"""

    headers = _make_headers()
    payload = {
        "model": "gemini-3-pro",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 2000
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.wiro.ai/v1/Run/google/gemini-3-pro",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()

    raw_text = ""
    if isinstance(data, dict):
        raw_text = (
            data.get("output") or
            data.get("text") or
            data.get("content") or
            str(data)
        )

    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    raw_text = raw_text.strip()

    try:
        script = json.loads(raw_text)
    except json.JSONDecodeError:
        script = _fallback_script(topic, sections, language)

    return script

def _fallback_script(topic: str, sections: int, language: str) -> dict:
    """API başarısız olursa basit fallback script"""
    if language == "tr":
        return {
            "title": f"{topic} Hakkında {sections} Şey",
            "intro": {
                "text": f"Bugün {topic} hakkında bilmeniz gereken en önemli {sections} şeyi anlatacağız.",
                "image_prompt": f"cinematic wide shot related to {topic}, dramatic lighting"
            },
            "sections": [
                {
                    "number": i,
                    "heading": f"{i}. Madde",
                    "text": f"Bu bölümde {topic} ile ilgili önemli bir noktayı ele alıyoruz.",
                    "image_prompt": f"cinematic image related to {topic} point {i}, realistic style"
                }
                for i in range(1, sections + 1)
            ],
            "outro": {
                "text": "Videoyu beğendiyseniz abone olmayı unutmayın!",
                "image_prompt": "cinematic subscribe reminder, dark background, glowing text"
            }
        }
    else:
        return {
            "title": f"{sections} Things About {topic}",
            "intro": {
                "text": f"Today we cover the top {sections} things you need to know about {topic}.",
                "image_prompt": f"cinematic wide shot related to {topic}, dramatic lighting"
            },
            "sections": [
                {
                    "number": i,
                    "heading": f"Point {i}",
                    "text": f"This section covers an important aspect of {topic}.",
                    "image_prompt": f"cinematic image related to {topic} point {i}, realistic style"
                }
                for i in range(1, sections + 1)
            ],
            "outro": {
                "text": "Don't forget to subscribe if you enjoyed this video!",
                "image_prompt": "cinematic subscribe reminder, dark background, glowing text"
            }
        }
