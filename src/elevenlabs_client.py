import httpx
import os

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
BASE_URL = "https://api.elevenlabs.io/v1"

async def text_to_speech(text: str, voice_id: str, output_path: str) -> str:
    """Metni sese çevirir, dosyaya kaydeder, path döner"""
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "model_id": "eleven_flash_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE_URL}/text-to-speech/{voice_id}",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
    return output_path

VOICE_OPTIONS = {
    "adam_en": "pNInz6obpgDQGcFmaJgB",
    "rachel_en": "21m00Tcm4TlvDq8ikWAM",
    "josh_en": "TxGEqnHWrfWFTfGW9XjX",
    "bella_en": "EXAVITQu4vr4xnSDxMaL",
}
