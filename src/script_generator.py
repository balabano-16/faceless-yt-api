import json
import httpx
import asyncio
import os
import time
import hmac
import hashlib

WIRO_API_KEY = os.environ.get("WIRO_API_KEY", "")
WIRO_API_SECRET = os.environ.get("WIRO_API_SECRET", "")
RUN_URL = "https://api.wiro.ai/v1/Run/google/gemini-2-5-flash"
TASK_URL = "https://api.wiro.ai/v1/Task/Detail"

def _auth_headers() -> dict:
    nonce = str(int(time.time()))
    signature = hmac.new(
        WIRO_API_KEY.encode(),
        f"{WIRO_API_SECRET}{nonce}".encode(),
        hashlib.sha256
    ).hexdigest()
    return {
        "x-api-key": WIRO_API_KEY,
        "x-nonce": nonce,
        "x-signature": signature,
    }

async def _poll_task(taskid: str, timeout: int = 120) -> str:
    start = time.time()
    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() - start < timeout:
            resp = await client.post(
                TASK_URL,
                headers=_auth_headers(),
                data={"taskid": taskid}
            )
            resp.raise_for_status()
            data = resp.json()
            tasklist = data.get("tasklist", [])
            if not tasklist:
                await asyncio.sleep(3)
                continue
            task = tasklist[0]
            status = task.get("status", "")
            print(f"[DEBUG] Gemini task status: {status}")
            if status == "task_postprocess_end":
                outputs = task.get("outputs", [])
                print(f"[DEBUG] Gemini outputs: {outputs}")
                if outputs:
                    url = outputs[0].get("url", "")
                    print(f"[DEBUG] Gemini output URL: {url}")
                    # URL ise fetch et
                    if url.startswith("http"):
                        async with httpx.AsyncClient(timeout=30) as c:
                            r = await c.get(url)
                            text = r.text
                            print(f"[DEBUG] Gemini fetched text (first 500): {text[:500]}")
                            return text
                    return url
                # debug output kontrol et
                debug = task.get("debugoutput", "")
                print(f"[DEBUG] Gemini debugoutput (first 500): {debug[:500]}")
                return debug
            elif status == "task_cancel":
                raise Exception("Gemini task cancelled")
            await asyncio.sleep(3)
    raise Exception("Gemini task timeout")

async def generate_script(topic: str, sections: int = 5, language: str = "en") -> dict:
    prompt = f"""You are a YouTube video script writer.
Topic: {topic}
Number of sections: {sections}

Return ONLY this JSON, no markdown, no explanation:
{{
  "title": "engaging video title",
  "intro": {{
    "text": "30-40 word engaging intro narration about {topic}",
    "image_prompt": "cinematic wide shot of {topic}, dramatic lighting, 4K"
  }},
  "sections": [
    {{
      "number": 1,
      "heading": "First point heading",
      "text": "60-80 word unique narration for this specific point about {topic}",
      "image_prompt": "cinematic image representing this specific point, dramatic lighting"
    }}
  ],
  "outro": {{
    "text": "20-30 word call to action",
    "image_prompt": "cinematic motivational image, dark background"
  }}
}}

Make each section completely unique and specific. Do not repeat content between sections."""

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            RUN_URL,
            headers=_auth_headers(),
            data={
                "prompt": prompt,
                "maxOutputTokens": 3000,
                "temperature": "0.8",
                "thinkingBudget": 0,
            }
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"[DEBUG] Gemini run response: {data}")

    taskid = data.get("taskid")
    if not taskid:
        print(f"[ERROR] No taskid from Gemini: {data}")
        return _fallback_script(topic, sections)

    raw = await _poll_task(str(taskid))
    print(f"[DEBUG] Raw Gemini response (first 800): {raw[:800]}")

    # JSON parse
    raw = raw.strip()
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                try:
                    result = json.loads(part)
                    print(f"[DEBUG] Script parsed successfully from fence")
                    return result
                except:
                    continue

    # Direkt parse dene
    try:
        # JSON başlangıcını bul
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = raw[start:end]
            result = json.loads(json_str)
            print(f"[DEBUG] Script parsed successfully")
            return result
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parse failed: {e}")

    print(f"[WARN] Falling back to template script")
    return _fallback_script(topic, sections)

def _fallback_script(topic: str, sections: int) -> dict:
    section_topics = [
        f"The most important thing about {topic}",
        f"How {topic} works in practice",
        f"Common mistakes people make with {topic}",
        f"Expert tips for {topic}",
        f"The future of {topic}",
        f"Getting started with {topic}",
        f"Advanced strategies for {topic}",
        f"Why {topic} matters today",
    ]
    return {
        "title": f"Everything You Need to Know About {topic}",
        "intro": {
            "text": f"Are you curious about {topic}? In this video, we'll cover the {sections} most important things you need to know. Let's dive in.",
            "image_prompt": f"cinematic wide establishing shot representing {topic}, dramatic lighting, 4K"
        },
        "sections": [
            {
                "number": i + 1,
                "heading": section_topics[i % len(section_topics)],
                "text": f"When it comes to {section_topics[i % len(section_topics)].lower()}, there are several key factors to consider. Understanding this aspect will completely change how you approach {topic} in your daily life.",
                "image_prompt": f"cinematic image representing {section_topics[i % len(section_topics)]}, realistic, dramatic lighting, 4K"
            }
            for i in range(sections)
        ],
        "outro": {
            "text": f"Now you know the top {sections} things about {topic}. If this was helpful, like and subscribe for more content like this!",
            "image_prompt": "cinematic dark background with glowing subscribe button, motivational atmosphere"
        }
    }
