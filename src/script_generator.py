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

def _extract_text_from_output(outputs: list) -> str:
    """Wiro output listesinden metin çıkar — tüm olası formatları dene"""
    for out in outputs:
        # content.raw içinde
        content = out.get("content", {})
        if isinstance(content, dict):
            raw = content.get("raw", "")
            if raw and len(raw) > 50:
                print(f"[DEBUG] Got text from content.raw: {raw[:100]}")
                return raw
            # answer listesi içinde
            answer = content.get("answer", [])
            if answer:
                text = answer[0] if isinstance(answer[0], str) else str(answer[0])
                if len(text) > 50:
                    print(f"[DEBUG] Got text from content.answer: {text[:100]}")
                    return text
        # Direkt url
        url = out.get("url", "")
        if url and url.startswith("http") and not url.endswith(('.jpg', '.png', '.mp4')):
            return f"__URL__{url}"
    return ""

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
                text = _extract_text_from_output(outputs)
                if text.startswith("__URL__"):
                    url = text[7:]
                    async with httpx.AsyncClient(timeout=30) as c:
                        r = await c.get(url)
                        return r.text
                if text:
                    return text
                debug = task.get("debugoutput", "")
                if debug:
                    return debug
                return str(task)
            elif status == "task_cancel":
                raise Exception("Gemini task cancelled")
            await asyncio.sleep(3)
    raise Exception("Gemini task timeout")

def _parse_json(raw: str) -> dict | None:
    """JSON'u çeşitli formatlarda parse etmeye çalış"""
    raw = raw.strip()
    
    # Markdown fence içinde
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                try:
                    return json.loads(part)
                except:
                    continue
    
    # Direkt JSON
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except:
            pass
    
    # JSON bloğu bul
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except:
            pass
    
    return None

async def generate_script(topic: str, sections: int = 5, language: str = "en") -> dict:
    prompt = f"""You are a YouTube video script writer. Write engaging, unique content.
Topic: {topic}
Number of sections: {sections}

Return ONLY valid JSON, no markdown fences, no explanation:
{{
  "title": "catchy engaging video title",
  "intro": {{
    "text": "MAXIMUM 20 words. Hook the viewer immediately about {topic}.",
    "image_prompt": "cinematic wide establishing shot for {topic}, dramatic lighting, 4K"
  }},
  "sections": [
    {{
      "number": 1,
      "heading": "Unique specific point heading",
      "text": "MAXIMUM 30 words. One punchy sentence about this specific point. No fluff.",
      "image_prompt": "specific cinematic image representing this unique point, dramatic lighting"
    }}
  ],
  "outro": {{
    "text": "MAXIMUM 15 words. Simple call to action.",
    "image_prompt": "motivational cinematic outro scene, dark background, inspiring atmosphere"
  }}
}}

IMPORTANT: Generate exactly {sections} sections. Each section must be completely unique and specific. Never repeat phrases."""

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            RUN_URL,
            headers=_auth_headers(),
            data={
                "prompt": prompt,
                "maxOutputTokens": 3000,
                "temperature": "0.9",
                "thinkingBudget": 0,
            }
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"[DEBUG] Gemini taskid: {data.get('taskid')}")

    taskid = data.get("taskid")
    if not taskid:
        print(f"[ERROR] No taskid: {data}")
        return _fallback_script(topic, sections)

    raw = await _poll_task(str(taskid))
    print(f"[DEBUG] Raw response (first 500): {raw[:500]}")

    result = _parse_json(raw)
    if result:
        # Section sayısını kontrol et
        actual_sections = result.get("sections", [])
        print(f"[DEBUG] Parsed script with {len(actual_sections)} sections")
        # Metinleri kırp — Gemini limiti görmezden gelebilir
        result = _truncate_script(result)
        if len(actual_sections) >= sections:
            return result
        # Az section geldiyse fallback ile doldur
        while len(actual_sections) < sections:
            n = len(actual_sections) + 1
            actual_sections.append({
                "number": n,
                "heading": f"Key Point {n}",
                "text": f"This is another important aspect of {topic} that you should know about. Understanding this will help you get better results.",
                "image_prompt": f"cinematic image representing {topic} concept {n}, dramatic lighting"
            })
        result["sections"] = actual_sections
        return result

    print(f"[WARN] JSON parse failed, using fallback")
    return _truncate_script(_fallback_script(topic, sections))

def _truncate_text(text: str, max_words: int) -> str:
    """Metni max_words kelimeye kırp, cümle ortasında kesme"""
    words = text.split()
    if len(words) <= max_words:
        return text
    truncated = " ".join(words[:max_words])
    # Son noktalama işaretinde bitir
    for punct in [". ", "! ", "? "]:
        last = truncated.rfind(punct)
        if last > len(truncated) // 2:
            return truncated[:last + 1]
    return truncated + "."

def _truncate_script(script: dict, section_max: int = 30, intro_max: int = 20, outro_max: int = 15) -> dict:
    """Tüm script metinlerini kırp"""
    if "intro" in script:
        script["intro"]["text"] = _truncate_text(script["intro"]["text"], intro_max)
    for s in script.get("sections", []):
        s["text"] = _truncate_text(s["text"], section_max)
    if "outro" in script:
        script["outro"]["text"] = _truncate_text(script["outro"]["text"], outro_max)
    return script

def _fallback_script(topic: str, sections: int) -> dict:
    section_topics = [
        f"Why {topic} matters more than you think",
        f"The science behind {topic}",
        f"Common mistakes people make with {topic}",
        f"Expert strategies for {topic}",
        f"The surprising truth about {topic}",
        f"How to get started with {topic} today",
        f"Advanced techniques for {topic}",
        f"Real results from {topic}",
    ]
    return {
        "title": f"The Ultimate Guide to {topic}",
        "intro": {
            "text": f"What if everything you knew about {topic} was wrong? In this video, we reveal the {sections} most important things you need to know right now.",
            "image_prompt": f"cinematic establishing shot representing {topic}, epic atmosphere, dramatic lighting, 4K"
        },
        "sections": [
            {
                "number": i + 1,
                "heading": section_topics[i % len(section_topics)],
                "text": f"When it comes to {section_topics[i % len(section_topics)].lower()}, most people get it completely wrong. The key insight here is that {topic} requires a fundamentally different approach than what most people think. By understanding this principle, you can transform your results dramatically.",
                "image_prompt": f"cinematic image representing {section_topics[i % len(section_topics)]}, realistic, dramatic lighting, 4K"
            }
            for i in range(sections)
        ],
        "outro": {
            "text": f"Now you know the top {sections} things about {topic}. If this helped you, smash that like button and subscribe for more content like this!",
            "image_prompt": "cinematic dark background with glowing subscribe button, motivational atmosphere, dramatic lighting"
        }
    }
