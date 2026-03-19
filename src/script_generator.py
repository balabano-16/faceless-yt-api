import json
from src.wiro_client import generate_script_text

async def generate_script(topic: str, sections: int = 5, language: str = "en") -> dict:
    system = """You are a YouTube video script writer. Write in English.
Generate a listicle format script for the given topic.
Return ONLY valid JSON, no markdown fences, no explanation, nothing else."""

    prompt = f"""Topic: {topic}
Number of sections: {sections}

Return this exact JSON structure:
{{
  "title": "video title",
  "intro": {{
    "text": "30-40 word intro narration",
    "image_prompt": "cinematic image prompt for intro visual"
  }},
  "sections": [
    {{
      "number": 1,
      "heading": "Section heading",
      "text": "60-80 word narration for this section",
      "image_prompt": "cinematic image prompt for this section"
    }}
  ],
  "outro": {{
    "text": "20-30 word closing narration",
    "image_prompt": "cinematic image prompt for outro"
  }}
}}"""

    raw = await generate_script_text(prompt, system, max_tokens=2000)

    # LLM'den gelen text URL ise fetch et
    if raw.startswith("http"):
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(raw)
            raw = resp.text

    raw = raw.strip()
    # markdown fence temizle
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            try:
                return json.loads(part)
            except:
                continue

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _fallback_script(topic, sections)

def _fallback_script(topic: str, sections: int) -> dict:
    return {
        "title": f"{sections} Things About {topic}",
        "intro": {
            "text": f"Today we cover the top {sections} things you need to know about {topic}.",
            "image_prompt": f"cinematic wide shot related to {topic}, dramatic lighting, 4K"
        },
        "sections": [
            {
                "number": i,
                "heading": f"Point {i}",
                "text": f"This section covers an important aspect of {topic}.",
                "image_prompt": f"cinematic image related to {topic} concept {i}, realistic, dramatic lighting"
            }
            for i in range(1, sections + 1)
        ],
        "outro": {
            "text": "Don't forget to like and subscribe if you found this helpful!",
            "image_prompt": "cinematic dark background with glowing subscribe button, dramatic lighting"
        }
    }
